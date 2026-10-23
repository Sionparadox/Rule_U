import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from test_improvements import answered, api_app, found, reply

from rule_u.config import Settings
from rule_u.providers import CompatibleChat, ProviderError
from rule_u.rag import answer_question, partial_answer, streamed


def test_partial_answer_decodes_incrementally():
    bs = chr(92)  # backslash, kept out of literals for readability
    raw = '{"answer":"돌려받지 ' + bs + '"못' + bs + '"합니다.' + bs + 'n다만 [1]","verdict"'
    assert partial_answer(raw) == '돌려받지 "못"합니다.' + chr(10) + '다만 [1]'
    assert partial_answer('{"verdict":"x","answer":"반') == "반"
    assert partial_answer('{"answer":"끝' + bs) == "끝"  # escape split across chunks
    assert partial_answer('{"answer":"' + bs + 'uAC00' + bs + 'uAC') == "가"
    assert partial_answer('{"verdict":"allowed"') == ""


class Streaming:
    def __init__(self, chunks, fail=False):
        self.chunks, self.fail, self.generated = chunks, fail, 0

    async def stream(self, messages):
        for chunk in self.chunks:
            yield chunk
        if self.fail:
            raise ProviderError("provider_stream_failed")

    async def generate(self, messages):
        self.generated += 1
        return json.dumps(reply(), ensure_ascii=False)


def test_stream_reports_drafts_and_falls_back(configured):
    settings = configured[0]
    settings.bgg_enabled = False
    text = json.dumps(reply(), ensure_ascii=False)
    drafts = []
    model = Streaming([text[i:i + 7] for i in range(0, len(text), 7)])
    result = asyncio.run(answer_question(settings, None, {}, model, found, on_draft=drafts.append))
    assert result["verdict"] == "not_allowed" and model.generated == 0
    assert drafts[-1] == "돌려받지 못합니다. [1]"
    assert all(drafts[-1].startswith(d) for d in drafts)
    # A broken stream is replaced by one normal request.
    drafts.clear()
    model = Streaming(['{"answer":"돌려'], fail=True)
    result = asyncio.run(answer_question(settings, None, {}, model, found, on_draft=drafts.append))
    assert result["verdict"] == "not_allowed" and model.generated == 1
    # Disabled streaming never calls stream().
    settings.chat_stream = False
    model = Streaming([], fail=True)
    asyncio.run(answer_question(settings, None, {}, model, found, on_draft=drafts.append))
    assert model.generated == 1


def test_streamed_throttles_updates():
    sent = []
    chunks = ['{"answer":"', "가", "나", "다", '"}']
    raw = asyncio.run(streamed(Streaming(chunks), [], sent.append, interval=60))
    assert raw == "".join(chunks) and sent == ["가"]  # later changes wait for the interval


def test_compatible_chat_parses_sse(monkeypatch):
    settings = Settings(_env_file=None, chat_provider="compatible", chat_api_key="key",
                        chat_model="model")
    lines = ['data: {"choices":[{"delta":{"role":"assistant"}}]}',
             'data: {"choices":[{"delta":{"content":"{\\"answer\\":\\"O"}}]}',
             ": keep-alive",
             'data: {"choices":[{"delta":{"content":"K\\"}"}}]}', "data: [DONE]"]

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content="\n".join(lines).encode())

    chat = CompatibleChat(settings, transport=httpx.MockTransport(handler))

    async def collect():
        return [x async for x in chat.stream([])]

    assert "".join(asyncio.run(collect())) == '{"answer":"OK"}'
    plain = CompatibleChat(settings, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": []})))

    async def broken():
        return [x async for x in plain.stream([])]

    with pytest.raises(ProviderError, match="provider_stream_failed"):
        asyncio.run(broken())


def test_situation_memo_is_saved_owned_and_sent_to_model(configured):
    class Capture:
        def __init__(self):
            self.payloads = []

        async def generate(self, messages):
            self.payloads.append(json.loads(messages[-1]["content"]))
            return json.dumps(reply(), ensure_ascii=False)

    provider = Capture()
    app = api_app(configured[0], provider)
    with TestClient(app) as client:
        cid, _, _, _ = answered(client)
        url = f"/api/v1/conversations/{cid}/situation"
        assert client.post(url, json={"element": "x" * 301}).status_code == 422
        value = {"element": " 백작 부인 ", "phase": "상대 차례", "action": ""}
        assert client.post(url, json=value).json() == {
            "element": "백작 부인", "phase": "상대 차례", "action": ""}
        assert client.get(f"/api/v1/conversations/{cid}").json()["situation"]["element"] == "백작 부인"
        client.post(f"/api/v1/conversations/{cid}/messages",
                    json={"message": "막을 수 있나요?", "client_request_id": "q2"})
        assert provider.payloads[-1]["situation"]["phase"] == "상대 차례"
        with TestClient(app) as stranger:
            assert stranger.post(url, json=value).status_code == 404
        client.post(url, json={})
        assert client.get(f"/api/v1/conversations/{cid}").json()["situation"] is None
    app.state.engine.dispose()


def test_request_draft_is_cleared_when_finished(configured):
    app = api_app(configured[0])
    with TestClient(app) as client:
        _, rid, _, _ = answered(client)
        assert client.get(f"/api/v1/requests/{rid}").json()["draft"] is None
    app.state.engine.dispose()
