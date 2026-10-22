import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_rag import Answer, evidence

from rule_u.main import create_app
from rule_u.models import Document, Edition, Expansion, Game, Request, expansion_editions


def test_search_constraints_and_semantic_ranking(configured):
    async def rank(*args):
        return ["too-long", "fits", "too-many", "missing"]

    app = create_app(configured[0], game_ranker=rank)
    with app.state.sessions.begin() as db:
        for gid, players, minutes in [("fits", 4, 30), ("too-long", 4, 31), ("too-many", 5, 20)]:
            db.add(Game(id=gid, name_ko=gid, min_players=players, max_players=6,
                        min_minutes=10, max_minutes=minutes, categories=["전략"], aliases=["별칭"]))
    with TestClient(app) as client:
        body = {"query": "4명이 30분 이내 전략 게임", "page_size": 1}
        result = client.post("/api/v1/games/search", json=body).json()
        assert result["total"] == 1 and result["items"][0]["id"] == "fits"
        # Explicit values override conditions extracted from natural language.
        result = client.post("/api/v1/games/search", json={**body, "players": 5}).json()
        assert result["total"] == 2
        assert client.get("/api/v1/games?query=별칭&players=4&max_minutes=30").json()["total"] == 1
        assert client.post("/api/v1/games/search", json={"players": 0}).status_code == 422
        assert "전략" in client.get("/api/v1/game-categories").json()


def test_compatibility_and_pending_request(app):
    with app.state.sessions.begin() as db:
        db.add(Edition(id="other", game_id="demo-game", label="다른 판본", language="en"))
        db.add(Expansion(id="exp", game_id="demo-game", name="확장", supported=True))
        db.flush()
        db.execute(expansion_editions.insert().values(expansion_id="exp", edition_id="other", game_id="demo-game"))
    with TestClient(app) as client:
        detail = client.get("/api/v1/games/demo-game").json()
        assert detail["expansions"][0]["edition_ids"] == ["other"]
        body = {"game_id": "demo-game", "edition_id": "demo-edition", "expansion_ids": ["exp"]}
        assert client.post("/api/v1/conversations", json=body).status_code == 422
        cid = client.post("/api/v1/conversations", json={**body, "expansion_ids": []}).json()["conversation_id"]
        with app.state.sessions.begin() as db:
            db.add(Request(id="pending", conversation_id=cid, client_request_id="client", status="running", stage="retrieve"))
        value = client.get(f"/api/v1/conversations/{cid}").json()
        assert value["active_request_id"] == value["latest_request_id"] == "pending"
        assert value["latest_client_request_id"] == "client"
        assert client.post(f"/api/v1/conversations/{cid}/messages", json={"message": "test", "client_request_id": "different"}).status_code == 409


def test_original_ownership_and_path_traversal(configured):
    settings, _ = configured

    async def found(*args):
        return [evidence()]

    app = create_app(settings, provider=Answer(), retriever=found)
    path = settings.data_dir / "originals/test.pdf"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"%PDF-1.4 test fixture")
    with app.state.sessions.begin() as db:
        db.add(Document(id="doc", title="규칙서", source_type="user_provided", source_url="https://example.test",
                        storage_key="originals/test.pdf", language="ko", version="v1", content_hash="test"))
    with TestClient(app) as owner:
        cid = owner.post("/api/v1/conversations", json={"game_id": "demo-game", "edition_id": "demo-edition"}).json()["conversation_id"]
        owner.post(f"/api/v1/conversations/{cid}/messages", json={"message": "질문", "client_request_id": "once"})
        conversation = owner.get(f"/api/v1/conversations/{cid}").json()
        source = conversation["messages"][-1]["citations"][0]
        assert source["number"] == 1 and source["original_available"]
        original = owner.get("/api/v1/documents/doc/original")
        assert original.status_code == 200 and "attachment" in original.headers["content-disposition"]
        with TestClient(app) as stranger:
            assert stranger.get("/api/v1/documents/doc/original").status_code == 404
            assert stranger.get(f"/api/v1/sources/{source['id']}").status_code == 404
        with app.state.sessions.begin() as db:
            db.get(Document, "doc").storage_key = "../outside.pdf"
        assert owner.get("/api/v1/documents/doc/original").status_code == 404


def test_semantic_search_real_mock_index(configured, tmp_path):
    from test_ingestion import bundle

    from rule_u.game_search import semantic_ids
    from rule_u.ingestion import import_metadata, index_bundle, ingest_documents

    settings, _ = configured
    rows = bundle(tmp_path)
    import_metadata(settings, rows)
    ingest_documents(settings, rows, tmp_path)
    asyncio.run(index_bundle(settings, rows))
    assert "test-game" in asyncio.run(semantic_ids(settings, "test"))


def test_failed_request_recovery_preserves_id(configured):
    app = create_app(configured[0])
    with TestClient(app) as client:
        cid = client.post("/api/v1/conversations", json={"game_id": "demo-game", "edition_id": "demo-edition"}).json()["conversation_id"]
        cookies = dict(client.cookies)
        with app.state.sessions.begin() as db:
            db.add(Request(id="interrupted", conversation_id=cid, client_request_id="same", status="running", stage="generate"))
    with TestClient(create_app(configured[0])) as restarted:
        restarted.cookies.update(cookies)
        value = restarted.get(f"/api/v1/conversations/{cid}").json()
        assert value["active_request_id"] is None and value["latest_request_id"] == "interrupted"
        assert restarted.get("/api/v1/requests/interrupted").json()["error_code"] == "server_restarted"
        result = restarted.post(f"/api/v1/conversations/{cid}/messages", json={"message": "retry", "client_request_id": "same"})
        assert result.json()["request_id"] == "interrupted"
        with restarted.app.state.sessions() as db:
            assert len(list(db.scalars(select(Request)))) == 1
