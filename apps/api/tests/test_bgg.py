import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from test_rag import Answer, evidence

from rule_u.bgg import BggClient, BggError, fallback
from rule_u.db import make_engine, make_sessions
from rule_u.main import create_app
from rule_u.models import Document
from rule_u.rag import answer_question


def context():
    return {"game": {"id": "demo-game", "name": "Demo", "name_original": "Demo",
                     "external_source": "local_catalog", "external_id": "123"},
            "edition": {"id": "demo-edition", "label": "First"},
            "expansion_ids": [], "messages": [{"role": "user", "content": "Turn timing?"}]}


class Selector:
    async def generate(self, messages):
        return '{"thread_ids":["3"]}'


def test_xml_resolution_caching_and_community_provenance(configured, monkeypatch):
    settings = configured[0]
    settings.bgg_api_token = SecretStr("test-token")
    calls = []
    responses = {
        "search": '<items><item type="boardgame" id="1"><name value="Demo"/></item></items>',
        "forumlist": '<forums><forum id="2" title="Rules"/><forum id="9" title="General"/></forums>',
        "forum": '<forum id="2"><threads><thread id="3" subject="Turn timing"/></threads></forum>',
        "thread": '<thread id="3"><articles><article><body>Can I play?</body></article>'
                  '<article><body>Only after your turn.</body></article></articles></thread>',
    }

    def handler(request):
        assert request.url.host == "boardgamegeek.com"
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["User-Agent"].startswith("Rule_U/")
        endpoint = request.url.path.rsplit("/", 1)[-1]
        calls.append(endpoint)
        if endpoint == "search":
            assert request.url.params["query"] == "Demo"
        if endpoint == "forumlist":
            assert request.url.params["id"] == "1"  # Never confuse local catalog ID with BGG ID.
        return httpx.Response(200, text=responses[endpoint])

    async def no_wait(_):
        pass

    monkeypatch.setattr("rule_u.bgg.asyncio.sleep", no_wait)
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    client = BggClient(settings, httpx.MockTransport(handler))

    async def run():
        first = await client.evidence(sessions, context(), Selector())
        assert await client.evidence(sessions, context(), Selector()) == first
        return first

    result, status = asyncio.run(run())
    assert status == "found" and calls == ["search", "forumlist", "forum", "thread"]
    assert result[0]["source_type"] == "bgg_community"
    assert result[0]["page_start"] is None
    assert result[0]["source_url_snapshot"] == "https://boardgamegeek.com/thread/3"
    with sessions() as db:
        doc = db.scalar(select(Document).where(Document.id == result[0]["document_id"]))
        assert doc and doc.storage_key is None
    engine.dispose()


@pytest.mark.parametrize("status,body", [(401, ""), (429, ""), (202, ""),
                                       (200, '<!DOCTYPE foo><items/>')])
def test_xml_errors_no_cache_or_redirect(configured, status, body):
    settings = configured[0]
    client = BggClient(settings, httpx.MockTransport(lambda r: httpx.Response(status, text=body)))
    with pytest.raises(BggError):
        asyncio.run(client.xml("search", query="Demo"))
    assert not (settings.data_dir / "bgg-cache").exists()


@pytest.mark.parametrize("ids", [["1", "2"], []])
def test_ambiguous_game_not_guessed(configured, ids):
    body = '<items>' + ''.join(f'<item type="boardgame" id="{i}"><name value="Demo"/></item>'
                              for i in ids) + '</items>'
    client = BggClient(configured[0], httpx.MockTransport(lambda r: httpx.Response(200, text=body)))
    assert asyncio.run(client.evidence(None, context(), Selector())) == ([], "game_unresolved")


def test_fallback_requires_token_and_handles_timeout(configured, monkeypatch):
    settings = configured[0]
    settings.bgg_api_token = SecretStr("")
    assert asyncio.run(fallback(settings, None, context(), Selector())) == ([], "not_configured")
    settings.bgg_api_token = SecretStr("test")

    async def fail(*args):
        raise httpx.ReadTimeout("secret response must not leak")

    monkeypatch.setattr(BggClient, "evidence", fail)
    assert asyncio.run(fallback(settings, None, context(), Selector())) == ([], "unavailable")


@pytest.mark.parametrize("local", [[], [evidence()]])
def test_graph_fallback_once_preserves_numbering(configured, local):
    calls, stages = [], []

    async def found(*args):
        return local

    async def external(*args):
        calls.append("bgg")
        return [{**evidence(), "source_type": "bgg_community"}], "found"

    class Provider:
        async def generate(self, messages):
            sources = json.loads(messages[1]["content"])["evidence"]
            if sources[-1]["source_type"] != "bgg_community":
                return json.dumps({"answer": "Unknown", "verdict": "insufficient_evidence"})
            number = sources[-1]["number"]
            return json.dumps({"answer": f"After your turn [{number}]", "verdict": "allowed",
                               "cited_ids": [number]})

    result = asyncio.run(answer_question(configured[0], None, context(), Provider(), found,
                                         stages.append, external))
    assert calls == ["bgg"]
    assert stages == ["retrieve", "generate", "bgg", "generate"]
    assert result["verdict"] == "conditional"
    assert result["citations"][0]["number"] == len(local) + 1
    assert "BGG" in result["answer"]


@pytest.mark.parametrize("verdict,ids,clarification", [
    ("conditional", [1], ""), ("needs_clarification", [], "Which card?")])
def test_sufficient_or_clarification_never_calls_bgg(configured, verdict, ids, clarification):
    async def found(*args):
        return [evidence()]

    async def never(*args):
        raise AssertionError("BGG must not run")

    provider = Answer(verdict, ids, "Answer [1]" if ids else "Clarify", clarification)
    result = asyncio.run(answer_question(configured[0], None, context(), provider, found,
                                         bgg_retriever=never))
    assert result["verdict"] == verdict


def test_bgg_failure_is_completed_refusal_not_failed_question(configured):
    async def empty(*args):
        return []

    async def failing(*args):
        return [], "unavailable"

    result = asyncio.run(answer_question(configured[0], None, context(), Answer(), empty,
                                         bgg_retriever=failing))
    assert result["verdict"] == "insufficient_evidence" and not result["citations"]
    assert "BGG" in result["answer"]


def test_invalid_generation_is_not_a_reason_for_external_search(configured):
    class Invalid:
        async def generate(self, messages):
            return "invalid JSON"

    async def found(*args):
        return [evidence()]

    async def never(*args):
        raise AssertionError("Malformed generation is not evidence shortage")

    result = asyncio.run(answer_question(configured[0], None, context(), Invalid(), found,
                                         bgg_retriever=never))
    assert result["verdict"] == "insufficient_evidence"


def test_bgg_citation_persists_and_remains_session_owned(configured, monkeypatch):
    settings = configured[0]
    settings.chat_provider = "compatible"

    async def empty(*args):
        return []

    async def external(settings, sessions, context, provider):
        with sessions.begin() as db:
            db.add(Document(id="bgg-doc", title="Discussion", source_type="bgg_community",
                            source_url="https://boardgamegeek.com/thread/3", language="en",
                            version="v1", content_hash="bgg-test-hash"))
        return [{**evidence(), "document_id": "bgg-doc", "source_type": "bgg_community",
                 "source_url_snapshot": "https://boardgamegeek.com/thread/3"}], "found"

    monkeypatch.setattr("rule_u.rag.bgg_fallback", external)
    app = create_app(settings, Answer(), empty)
    with TestClient(app) as client:
        cid = client.post("/api/v1/conversations", json={"game_id": "demo-game",
                          "edition_id": "demo-edition"}).json()["conversation_id"]
        payload = {"message": "Turn?", "mode": "qa", "client_request_id": "bgg-request"}
        rid = client.post(f"/api/v1/conversations/{cid}/messages", json=payload).json()["request_id"]
        result = client.get(f"/api/v1/requests/{rid}").json()
        assert result["status"] == "completed"
        source = result["result"]["citations"][0]
        assert source["source_type"] == "bgg_community"
        assert source["source_review"] == "unverified" and not source["original_available"]
        assert client.post(f"/api/v1/conversations/{cid}/messages", json=payload).json()["request_id"] == rid
        assert client.get(f"/api/v1/sources/{source['id']}").status_code == 200
        assert client.get("/api/v1/documents/bgg-doc/original").status_code == 404
        assert client.get(f"/api/v1/conversations/{cid}").json()["messages"][-1]["citations"][0] == source
        client.cookies.clear()
        assert client.get(f"/api/v1/sources/{source['id']}").status_code == 404
        assert client.post(f"/api/v1/sources/{source['id']}/explanation").status_code == 404
        assert client.get(f"/api/v1/conversations/{cid}").status_code == 404
    app.state.engine.dispose()
