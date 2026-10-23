import asyncio
import json

from fastapi.testclient import TestClient
from test_rag import Answer, evidence

from rule_u.main import create_app
from rule_u.models import Document, Request
from rule_u.rag import GeneratedAnswer, answer_question, validate_answer


class Sequence:
    """Returns prepared model outputs in order and counts calls."""

    def __init__(self, *values):
        self.values, self.calls, self.messages = list(values), 0, []

    async def generate(self, messages):
        self.calls += 1
        self.messages.append(messages)
        return json.dumps(self.values.pop(0), ensure_ascii=False)


def reply(verdict="not_allowed", ids=(1,), answer="돌려받지 못합니다. [1]", clarification=""):
    return {"answer": answer, "verdict": verdict, "cited_ids": list(ids),
            "clarification": clarification}


async def found(*args):
    return [evidence()]


def run(settings, provider, **kwargs):
    return asyncio.run(answer_question(settings, None, {}, provider, found, **kwargs))


def test_diagnostic_codes_separate_refusal_causes():
    def code(**value):
        return validate_answer(GeneratedAnswer(**reply(**value)), [evidence()])["diagnostic"]

    assert validate_answer(None, [evidence()])["diagnostic"] == "invalid_json"
    assert code() == "ok"
    assert code(answer="돌려받지 못합니다.") == "citation_mismatch"
    assert code(ids=(), answer="돌려받지 못합니다.") == "missing_citation"
    assert code(ids=(2,), answer="불가 [2]") == "citation_mismatch"
    assert code(verdict="insufficient_evidence", ids=(), answer="모름") == "model_insufficient"
    assert code(verdict="needs_clarification", ids=(), answer="확인", clarification="어느 카드인가요?") \
        == "model_clarification"


def test_citation_mismatch_is_repaired_once(configured):
    settings = configured[0]
    settings.bgg_enabled = False
    provider = Sequence(reply(answer="돌려받지 못합니다."), reply())
    result = run(settings, provider)
    assert provider.calls == 2 and result["verdict"] == "not_allowed"
    assert result["diagnostic"] == "ok" and result["diagnostic_detail"]["repaired"]
    feedback = provider.messages[1][-1]["content"]
    assert "응답 형식 오류" in feedback and "[1]" in feedback
    # A second violation is not retried again and stays a refusal.
    provider = Sequence(reply(answer="불가"), reply(answer="불가"))
    result = run(settings, provider)
    assert provider.calls == 2 and result["verdict"] == "insufficient_evidence"
    assert result["diagnostic"] == "citation_mismatch"


def test_model_refusal_is_not_retried(configured):
    settings = configured[0]
    settings.bgg_enabled = False
    provider = Sequence(reply(verdict="insufficient_evidence", ids=(), answer="모름"))
    result = run(settings, provider)
    assert provider.calls == 1 and result["diagnostic"] == "model_insufficient"
    assert result["diagnostic_detail"] == {"evidence": 1, "repaired": False}


def test_bgg_lookup_can_be_skipped(configured):
    settings = configured[0]
    started = asyncio.Event()

    async def slow(*args):
        started.set()
        await asyncio.sleep(60)
        return [], "no_results"

    polls = []

    def skip():
        polls.append(1)
        return started.is_set()

    provider = Sequence(reply(verdict="insufficient_evidence", ids=(), answer="모름"))
    result = run(settings, provider, bgg_retriever=slow, should_skip=skip)
    assert result["diagnostic"] == "bgg_skipped" and "중단" in result["answer"]
    assert result["diagnostic_detail"]["before_bgg"] == "model_insufficient"
    assert polls and provider.calls == 1


def api_app(settings, provider=None):
    app = create_app(settings, provider=provider or Answer(verdict="not_allowed"), retriever=found)
    with app.state.sessions.begin() as db:
        db.add(Document(id="doc", title="규칙서", source_type="user_provided", source_url="",
                        language="ko", version="v1", content_hash="test"))
    return app


def answered(client):
    cid = client.post("/api/v1/conversations", json={
        "game_id": "demo-game", "edition_id": "demo-edition"}).json()["conversation_id"]
    rid = client.post(f"/api/v1/conversations/{cid}/messages",
                      json={"message": "비용을 돌려받나요?", "client_request_id": "q1"}).json()["request_id"]
    messages = client.get(f"/api/v1/conversations/{cid}").json()["messages"]
    return cid, rid, messages[0]["id"], messages[1]["id"]


def test_request_records_diagnostic_and_skip_rules(configured):
    app = api_app(configured[0])
    with TestClient(app) as client:
        cid, rid, _, _ = answered(client)
        request = client.get(f"/api/v1/requests/{rid}").json()
        assert request["diagnostic"] == "ok" and request["skip_external"] is False
        with app.state.sessions() as db:
            assert db.get(Request, rid).diagnostic["evidence"] == 1
        # A finished request cannot be changed, and other sessions cannot touch it.
        assert client.post(f"/api/v1/requests/{rid}/skip-external").status_code == 409
        with TestClient(app) as stranger:
            # Insert after the second client's startup recovery, which fails running requests.
            with app.state.sessions.begin() as db:
                db.add(Request(id="live", conversation_id=cid, client_request_id="q2",
                               status="running", stage="bgg"))
            assert stranger.post("/api/v1/requests/live/skip-external").status_code == 404
            assert client.post("/api/v1/requests/live/skip-external").status_code == 200
        assert client.get("/api/v1/requests/live").json()["skip_external"] is True
    app.state.engine.dispose()


def test_feedback_upsert_ownership_and_restore(configured):
    app = api_app(configured[0])
    with TestClient(app) as client:
        cid, _, question, answer = answered(client)
        url = f"/api/v1/messages/{answer}/feedback"
        assert client.post(f"/api/v1/messages/{question}/feedback",
                           json={"rating": "helpful"}).status_code == 422
        assert client.post(url, json={"rating": "wrong", "reason": "nope"}).status_code == 422
        assert client.post(url, json={"rating": "wrong", "note": "x" * 501}).status_code == 422
        value = client.post(url, json={"rating": "wrong", "reason": "rule_differs",
                                       "note": " 7쪽과 달라요 "}).json()
        assert value == {"rating": "wrong", "reason": "rule_differs", "note": "7쪽과 달라요"}
        # Changing to helpful clears the wrong-answer reason; one row per message.
        assert client.post(url, json={"rating": "helpful", "reason": "other"}).json() == {
            "rating": "helpful", "reason": None, "note": ""}
        restored = client.get(f"/api/v1/conversations/{cid}").json()["messages"][1]
        assert restored["feedback"]["rating"] == "helpful"
        with TestClient(app) as stranger:
            assert stranger.post(url, json={"rating": "wrong"}).status_code == 404
    app.state.engine.dispose()


def test_bookmarks_are_session_scoped(configured):
    app = api_app(configured[0])
    with TestClient(app) as client:
        cid, _, question, answer = answered(client)
        url = f"/api/v1/messages/{answer}/bookmark"
        assert client.post(f"/api/v1/messages/{question}/bookmark",
                           json={"saved": True}).status_code == 422
        for _ in range(2):  # idempotent
            assert client.post(url, json={"saved": True}).json()["saved"] is True
        items = client.get("/api/v1/games/demo-game/saved-rules").json()["items"]
        assert len(items) == 1 and items[0]["question"] == "비용을 돌려받나요?"
        assert items[0]["conversation_id"] == cid and items[0]["citations"][0]["number"] == 1
        assert client.get(f"/api/v1/conversations/{cid}").json()["messages"][1]["saved"] is True
        with TestClient(app) as stranger:
            assert stranger.post(url, json={"saved": True}).status_code == 404
            assert stranger.get("/api/v1/games/demo-game/saved-rules").json()["items"] == []
        client.post(url, json={"saved": False})
        assert client.get("/api/v1/games/demo-game/saved-rules").json()["items"] == []
    app.state.engine.dispose()


def test_feedback_export_is_review_only(configured):
    from rule_u.feedback import export

    app = api_app(configured[0])
    with TestClient(app) as client:
        _, _, _, answer = answered(client)
        client.post(f"/api/v1/messages/{answer}/feedback",
                    json={"rating": "wrong", "reason": "wrong_page", "note": "3쪽"})
    result = export(configured[0])
    item = result["items"][0]
    assert result["count"] == 1 and item["status"] == "needs_review"
    assert item["question"] == "비용을 돌려받나요?" and item["reason"] == "wrong_page"
    assert item["cited"] == [{"document_id": "doc", "page_start": 2}]
    assert "pages" not in item  # expected pages are decided by a reviewer
    app.state.engine.dispose()
