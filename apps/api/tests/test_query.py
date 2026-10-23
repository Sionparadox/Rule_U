import asyncio
import json

from rule_u.providers import ProviderError
from rule_u.rag import answer_question, needs_rewrite, search_query


class Fenced:
    async def generate(self, messages):
        return '```json\n{"query": "암살 저지 방법"}\n```'


def test_fenced_rewrite_is_accepted(configured):
    context = turns("암살자는 어떻게 쓰나요?", "그거 막을 수 있어요?")
    assert query(configured[0], context, Fenced())[0] == "암살 저지 방법"


class Rewriter:
    def __init__(self, value=None, error=False):
        self.value, self.error, self.calls = value, error, 0

    async def generate(self, messages):
        self.calls += 1
        if self.error:
            raise ProviderError("provider_call_failed")
        return json.dumps({"query": self.value}, ensure_ascii=False)


def turns(*questions):
    messages = []
    for q in questions:
        messages += [{"role": "user", "content": q}, {"role": "assistant", "content": "답"}]
    return {"messages": messages[:-1]}


def query(settings, context, provider):
    return asyncio.run(search_query(settings, context, lambda: provider))


def test_first_question_and_topic_switch_use_latest_only(configured):
    settings = configured[0]
    provider = Rewriter("unused")
    assert query(settings, turns("암살자는 어떻게 쓰나요?"), provider)[0] == "암살자는 어떻게 쓰나요?"
    # A self-contained new question must not carry earlier topics into the search.
    value, detail = query(settings, turns("암살자는 어떻게 쓰나요?", "게임 준비 때 은화는 몇 개 받나요?"),
                          provider)
    assert value == "게임 준비 때 은화는 몇 개 받나요?" and detail["query_method"] == "latest"
    assert provider.calls == 0
    assert query(settings, {"messages": []}, provider)[0] == ""


def test_followup_is_rewritten_once_and_cached(configured):
    settings = configured[0]
    context = turns("암살자는 어떻게 쓰나요?", "그거 막을 수 있어요?")
    provider = Rewriter("암살자 능력을 막을 수 있나요?")
    value, detail = query(settings, context, provider)
    assert value == "암살자 능력을 막을 수 있나요?" and detail["query_method"] == "rewritten"
    assert query(settings, context, provider)[1]["query_method"] == "rewrite_cached"
    assert provider.calls == 1
    assert needs_rewrite("그럼 3장이면요?", ["앞 질문"])
    assert needs_rewrite("2장이면?", ["앞 질문"])  # short ellipsis
    assert needs_rewrite("그 캐릭터 금화를 도둑이 훔칠 수 있어요?", ["앞 질문"])
    assert not needs_rewrite("게임 준비 때 은화는 몇 개 받나요?", ["앞 질문"])
    assert not needs_rewrite("그거 막을 수 있어요?", [])


def test_rewrite_failure_falls_back_and_situation_is_added(configured):
    settings = configured[0]
    context = turns("암살자는 어떻게 쓰나요?", "그럼 비용은요?")
    for provider in (Rewriter(error=True), Rewriter("")):
        value, detail = query(settings, context, provider)
        assert value == "암살자는 어떻게 쓰나요?\n그럼 비용은요?" and detail["query_method"] == "fallback"
    context = {**turns("저지할 수 있나요?"), "situation": {"element": "백작 부인"}}
    assert query(settings, context, Rewriter("x"))[0] == "저지할 수 있나요?\n백작 부인"


def test_retriever_receives_query_and_detail_is_recorded(configured):
    settings = configured[0]
    settings.bgg_enabled = False
    seen = []

    async def found(settings, sessions, context):
        seen.append(context["search_query"])
        return []

    context = turns("암살자는 어떻게 쓰나요?", "그거 막을 수 있어요?")
    result = asyncio.run(answer_question(settings, None, context, Rewriter("암살자 저지 방법"), found))
    assert seen == ["암살자 저지 방법"]
    assert result["diagnostic_detail"]["search_query"] == "암살자 저지 방법"
