import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_ingestion import bundle

from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import import_metadata, index_bundle, ingest_documents, vector_collections
from rule_u.main import create_app
from rule_u.models import Document, DocumentScope, Expansion, expansion_editions
from rule_u.providers import ProviderError
from rule_u.rag import GeneratedAnswer, answer_question, retrieve, validate_answer


def evidence():
    return {"number": 1, "document_id": "doc", "chunk_id": "chunk", "source_version": "v1",
            "title_snapshot": "규칙서", "source_url_snapshot": "https://example.test/rules",
            "edition_snapshot": "초판", "page_start": 2, "page_end": 2,
            "excerpt": "자신의 턴 이후에만 사용합니다.", "language": "ko",
            "source_type": "user_provided", "extraction_method": "reviewed_transcription",
            "review_note": "정리 전사"}


class Answer:
    def __init__(self, verdict="conditional", ids=None, answer="자신의 턴 이후에만 가능합니다. [1]",
                 clarification=""):
        self.value = dict(answer=answer, verdict=verdict,
                          cited_ids=[1] if ids is None else ids, clarification=clarification)
        self.messages = None

    async def generate(self, messages):
        self.messages = messages
        return json.dumps(self.value, ensure_ascii=False)


@pytest.mark.parametrize("verdict,ids,text,question,expected", [
    ("conditional", [1], "턴 이후에만 가능합니다. [1]", "", "conditional"),
    ("not_allowed", [1], "턴 이전에는 불가합니다. [1]", "", "not_allowed"),
    ("allowed", [99], "가능 [99]", "", "insufficient_evidence"),
    ("allowed", [], "가능", "", "insufficient_evidence"),
    ("allowed", [1], "가능 [2]", "", "insufficient_evidence"),
    ("needs_clarification", [], "확인 필요", "어떤 카드이며 현재 누구의 턴인가요?", "needs_clarification"),
    ("needs_clarification", [], "확인 필요", "", "insufficient_evidence"),
    ("insufficient_evidence", [], "추측", "", "insufficient_evidence"),
])
def test_answer_validation(verdict, ids, text, question, expected):
    result = validate_answer(GeneratedAnswer(answer=text, verdict=verdict, cited_ids=ids,
                                             clarification=question), [evidence()])
    assert result["verdict"] == expected
    if expected in {"insufficient_evidence", "needs_clarification"}:
        assert result["citations"] == []


def test_graph_no_evidence_does_not_generate(configured):
    class Never:
        async def generate(self, messages):
            raise AssertionError("No evidence must not call the model")

    async def empty(*args):
        return []

    stages = []
    result = asyncio.run(answer_question(configured[0], None, {}, Never(), empty, stages.append))
    assert stages == ["retrieve", "generate"]
    assert result["verdict"] == "insufficient_evidence"


def test_graph_provider_failure_is_not_evidence_refusal(configured):
    class Failing:
        async def generate(self, messages):
            raise ProviderError("provider_call_failed")

    async def found(*args):
        return [evidence()]

    with pytest.raises(ProviderError, match="provider_call_failed"):
        asyncio.run(answer_question(configured[0], None, {}, Failing(), found))


def test_invalid_model_json_is_bounded(configured):
    class Invalid:
        calls = 0

        async def generate(self, messages):
            self.calls += 1
            return "not JSON"

    async def found(*args):
        return [evidence()]

    provider = Invalid()
    result = asyncio.run(answer_question(configured[0], None, {}, provider, found))
    assert provider.calls == 2 and result["verdict"] == "insufficient_evidence"


def test_scoped_retrieval_and_expansion_exclusion(configured, tmp_path):
    settings, _ = configured
    rows = bundle(tmp_path)
    import_metadata(settings, rows)
    ingest_documents(settings, rows, tmp_path)
    asyncio.run(index_bundle(settings, rows))
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    context = {"game": {"id": "test-game"}, "edition": {"id": "test-edition", "label": "Test"},
               "expansion_ids": [], "messages": [{"role": "user", "content": "When?"}]}
    result = asyncio.run(retrieve(settings, sessions, context))
    assert result and all(e["page_start"] == 1 for e in result)
    context["edition"]["id"] = "demo-edition"
    assert asyncio.run(retrieve(settings, sessions, context)) == []
    context["edition"]["id"] = "test-edition"
    with sessions.begin() as db:
        db.add(Expansion(id="exp", game_id="test-game", name="Expansion"))
        db.flush()
        db.execute(expansion_editions.insert().values(
            expansion_id="exp", edition_id="test-edition", game_id="test-game"))
        scope = db.scalar(select(DocumentScope).where(DocumentScope.game_id == "test-game"))
        scope.expansion_id = "exp"
    assert asyncio.run(retrieve(settings, sessions, context)) == []
    context["expansion_ids"] = ["exp"]
    assert asyncio.run(retrieve(settings, sessions, context))
    engine.dispose()


def test_api_citation_snapshot_privacy_restart(configured):
    settings, _ = configured
    provider = Answer()

    async def found(*args):
        return [evidence()]

    app = create_app(settings, provider, found)
    with app.state.sessions.begin() as db:
        db.add(Document(id="doc", title="Original", source_type="user_provided", source_url="",
                        language="ko", version="v1", content_hash="hash"))
    with TestClient(app) as client:
        cid = client.post("/api/v1/conversations", json={"game_id": "demo-game",
                          "edition_id": "demo-edition"}).json()["conversation_id"]
        rid = client.post(f"/api/v1/conversations/{cid}/messages", json={"message": "가능한가요?",
                          "mode": "ruling", "client_request_id": "first"}).json()["request_id"]
        result = client.get(f"/api/v1/requests/{rid}").json()
        assert result["status"] == "completed"
        citation = result["result"]["citations"][0]
        assert citation["number"] == 1 and citation["page_start"] == 2
        assert citation["source_type"] == "user_provided"
        prompt = json.loads(provider.messages[1]["content"])
        assert prompt["game"]["id"] == "demo-game" and prompt["mode"] == "ruling"
        assert prompt["edition"]["id"] == "demo-edition"
        cookies = dict(client.cookies)
        with app.state.sessions.begin() as db:
            db.get(Document, "doc").title = "Changed"
        assert client.get(f"/api/v1/sources/{citation['id']}").json()["title"] == "규칙서"
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/v1/sources/{citation['id']}").status_code == 404
        restarted.cookies.update(cookies)
        assert restarted.get(f"/api/v1/sources/{citation['id']}").json() == citation
        history = restarted.get(f"/api/v1/conversations/{cid}").json()["messages"]
        assert history[-1]["cited_source_ids"] == [citation["id"]]


def test_partial_staging_failure_keeps_active_generation(configured, tmp_path, monkeypatch):
    settings, _ = configured
    rows = bundle(tmp_path)
    import_metadata(settings, rows)
    ingest_documents(settings, rows, tmp_path)
    asyncio.run(index_bundle(settings, rows))
    _, before = vector_collections(settings)
    old = before["rule_docs"].get(include=["documents"])
    manifest = json.loads((settings.data_dir / "manifests/test-game.json").read_text(encoding="utf-8"))
    artifact_path = settings.data_dir / manifest[0]["extracted_key"]
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    chunk = artifact["chunks"][0]
    artifact["chunks"] = [{**chunk, "id": str(i), "text": f"Changed {i}"} for i in range(30)]
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    class Failing:
        calls = 0

        async def embed(self, texts):
            self.calls += 1
            if self.calls == 2:
                raise ValueError("injected_failure")
            return [[1.0] * settings.embedding_dimensions for _ in texts]

    monkeypatch.setattr("rule_u.ingestion.embedding_provider", lambda _: Failing())
    with pytest.raises(ValueError, match="injected_failure"):
        asyncio.run(index_bundle(settings, rows))
    _, after = vector_collections(settings)
    assert after["rule_docs"].name == before["rule_docs"].name
    assert after["rule_docs"].get(include=["documents"]) == old
    from rule_u.providers import MockEmbedding

    monkeypatch.setattr("rule_u.ingestion.embedding_provider",
                        lambda _: MockEmbedding(settings.embedding_dimensions))
    asyncio.run(index_bundle(settings, rows))
    _, published = vector_collections(settings)
    assert published["rule_docs"].name != before["rule_docs"].name
    assert published["rule_docs"].count() == 30
    assert before["rule_docs"].get(include=["documents"]) == old
