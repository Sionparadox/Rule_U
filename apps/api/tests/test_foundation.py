import asyncio
import json

import httpx
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine
from rule_u.main import create_app
from rule_u.models import (
    Citation,
    CollectionState,
    Conversation,
    Document,
    DocumentScope,
    Edition,
    Expansion,
    Game,
    Message,
    Request,
    conversation_expansions,
    expansion_editions,
)
from rule_u.providers import CompatibleChat, CompatibleEmbedding, ProviderError


def conversation(client):
    response = client.post(
        "/api/v1/conversations",
        json={
            "game_id": "demo-game",
            "edition_id": "demo-edition",
            "expansion_ids": [],
        },
    )
    assert response.status_code == 201
    return response.json()["conversation_id"]


def test_migration_roundtrip(configured):
    settings, config = configured
    command.check(config)
    command.downgrade(config, "base")
    engine = make_engine(settings)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
    command.upgrade(config, "head")
    engine = make_engine(settings)
    assert len(inspect(engine).get_table_names()) == 15
    engine.dispose()


def test_chat_persists_across_restart_and_is_private(app, configured):
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["live_connections_verified"] is False
        assert client.get("/api/v1/games").json()["total"] == 1
        cid = conversation(client)
        body = {"message": "질문", "client_request_id": "unique-1"}
        result = client.post(f"/api/v1/conversations/{cid}/messages", json=body)
        assert result.status_code == 202
        rid = result.json()["request_id"]
        result = client.get(f"/api/v1/requests/{rid}").json()
        assert result["status"] == "completed"
        assert result["result"]["citations"] == []
        assert "테스트 응답" in result["result"]["answer"]
        duplicate = client.post(f"/api/v1/conversations/{cid}/messages", json=body)
        assert duplicate.json()["request_id"] == rid
        assert len(client.get(f"/api/v1/conversations/{cid}").json()["messages"]) == 2
        cookies = dict(client.cookies)
    with TestClient(create_app(configured[0])) as restarted:
        assert restarted.get(f"/api/v1/conversations/{cid}").status_code == 404
        assert restarted.get(f"/api/v1/requests/{rid}").status_code == 404
        restarted.cookies.update(cookies)
        assert len(restarted.get(f"/api/v1/conversations/{cid}").json()["messages"]) == 2


def test_scope_validation_and_interrupted_requests(app, configured):
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/conversations", json={"game_id": "wrong", "edition_id": "demo-edition"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/conversations",
                json={
                    "game_id": "demo-game",
                    "edition_id": "demo-edition",
                    "expansion_ids": ["wrong"],
                },
            ).status_code
            == 422
        )
        cid = conversation(client)
        with app.state.sessions.begin() as db:
            request = Request(
                conversation_id=cid, client_request_id="interrupted", status="running"
            )
            db.add(request)
            db.flush()
            rid = request.id
        assert (
            client.post(
                f"/api/v1/conversations/{cid}/messages",
                json={"message": "x", "client_request_id": "other"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/conversations/{cid}/messages",
                json={"message": "  ", "client_request_id": "empty"},
            ).status_code
            == 422
        )
        cookies = dict(client.cookies)
    with TestClient(create_app(configured[0])) as restarted:
        restarted.cookies.update(cookies)
        result = restarted.get(f"/api/v1/requests/{rid}").json()
        assert result["status"] == "failed" and result["error_code"] == "server_restarted"
        assert (
            restarted.post(
                f"/api/v1/conversations/{cid}/messages",
                json={"message": "retry", "client_request_id": "retry"},
            ).status_code
            == 202
        )


def test_all_entities_and_snapshot_integrity(app):
    with app.state.sessions.begin() as db:
        db.add(Expansion(id="exp", game_id="demo-game", name="확장"))
        db.add(
            Document(
                id="doc",
                title="Original title",
                source_type="rulebook",
                source_url="https://example.test/rules",
                language="ko",
                version="1",
                content_hash="hash",
            )
        )
        db.add(
            Conversation(
                id="conv", session_id="session", game_id="demo-game", edition_id="demo-edition"
            )
        )
        db.flush()
        db.execute(
            expansion_editions.insert().values(
                expansion_id="exp", edition_id="demo-edition", game_id="demo-game"
            )
        )
        db.add(
            DocumentScope(
                document_id="doc",
                game_id="demo-game",
                edition_id="demo-edition",
                expansion_id="exp",
            )
        )
        db.add(CollectionState(source_id="source", game_id="demo-game", edition_id="demo-edition"))
        db.execute(
            conversation_expansions.insert().values(
                conversation_id="conv", expansion_id="exp", edition_id="demo-edition"
            )
        )
        db.add(Message(id="msg", conversation_id="conv", role="assistant", content="answer"))
        db.flush()
        db.add(
            Citation(
                id="cite",
                message_id="msg",
                document_id="doc",
                source_version="1",
                title_snapshot="Original title",
                page_start=2,
                page_end=3,
                excerpt="preserved",
            )
        )
    with app.state.sessions.begin() as db:
        db.get(Document, "doc").title = "Changed title"
    with app.state.sessions() as db:
        assert db.get(Citation, "cite").title_snapshot == "Original title"
        assert db.scalar(select(CollectionState)).index_status == "pending"
        assert db.execute(select(conversation_expansions)).one().expansion_id == "exp"


def test_db_constraints(app):
    with app.state.sessions.begin() as db:
        db.add(Game(id="other", name_ko="Other"))
        db.flush()
        db.add(Edition(id="other-ed", game_id="other", label="v1", language="en"))
        db.add(
            Document(
                id="doc",
                title="Doc",
                source_type="rulebook",
                source_url="",
                language="ko",
                version="1",
                content_hash="unique",
            )
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as db:
        db.add(Conversation(session_id="s", game_id="demo-game", edition_id="other-ed"))
    with pytest.raises(IntegrityError), app.state.sessions.begin() as db:
        db.add(Game(name_ko="Duplicate", external_source="test-fixture", external_id="demo"))
    with app.state.sessions.begin() as db:
        db.add(DocumentScope(document_id="doc", game_id="demo-game", edition_id="demo-edition"))
    with pytest.raises(IntegrityError), app.state.sessions.begin() as db:
        db.add(DocumentScope(document_id="doc", game_id="demo-game", edition_id="demo-edition"))


def test_generation_failure_has_no_secret(configured):
    class Failing:
        async def generate(self, messages):
            raise RuntimeError("secret-token-and-internal-body")

    with TestClient(create_app(configured[0], provider=Failing())) as client:
        cid = conversation(client)
        rid = client.post(
            f"/api/v1/conversations/{cid}/messages", json={"message": "x", "client_request_id": "a"}
        ).json()["request_id"]
        result = client.get(f"/api/v1/requests/{rid}")
        assert result.json()["status"] == "failed"
        assert "secret-token" not in result.text
        assert len(client.get(f"/api/v1/conversations/{cid}").json()["messages"]) == 1


def provider_settings():
    return Settings(
        _env_file=None,
        chat_api_key="secret",
        chat_base_url="https://example.test/v1/",
        embedding_api_key="separate-secret",
        embedding_base_url="https://embed.test/v1/",
        embedding_model="confirmed-test-model",
        embedding_dimensions=2,
    )


def test_provider_wire_formats_and_separation():
    settings = provider_settings()

    def chat(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        assert json.loads(request.content)["model"] == "gpt-5.4-nano"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    def embedding(request):
        assert request.url.host == "embed.test"
        assert request.headers["Authorization"] == "Bearer separate-secret"
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [3, 4]}, {"index": 0, "embedding": [1, 2]}]},
        )

    assert asyncio.run(CompatibleChat(settings, httpx.MockTransport(chat)).generate([])) == "OK"
    assert asyncio.run(
        CompatibleEmbedding(settings, httpx.MockTransport(embedding)).embed(["a", "b"])
    ) == [[1, 2], [3, 4]]


@pytest.mark.parametrize(
    "data",
    [
        {"data": [{"index": 0, "embedding": [1]}]},
        {"data": [{"index": 1, "embedding": [1, 2]}]},
        {"data": [{"index": 0, "embedding": ["bad", 2]}]},
    ],
)
def test_embedding_rejects_invalid_vectors(data):
    provider = CompatibleEmbedding(
        provider_settings(), httpx.MockTransport(lambda r: httpx.Response(200, json=data))
    )
    with pytest.raises(ProviderError, match="invalid_embedding"):
        asyncio.run(provider.embed(["a"]))


def test_http_error_is_sanitized():
    provider = CompatibleChat(
        provider_settings(), httpx.MockTransport(lambda r: httpx.Response(401, text="secret"))
    )
    with pytest.raises(ProviderError, match="^provider_call_failed$"):
        asyncio.run(provider.generate([]))


def test_relative_data_path_is_root_relative(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, data_dir="data")
    assert settings.data_dir == ROOT / "data"


def test_committed_openapi_is_current(app):
    committed = json.loads((ROOT / "apps/api/openapi.json").read_text(encoding="utf-8"))
    assert app.openapi() == committed, "run `corepack pnpm sync:api` and commit the result"
