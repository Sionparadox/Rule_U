import asyncio
import json
import secrets
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response
from fastapi import Request as HTTPRequest
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine, make_sessions
from rule_u.game_search import constraints, semantic_ids
from rule_u.models import (
    Citation,
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
from rule_u.providers import ProviderError, chat_provider
from rule_u.rag import answer_question, explain_source
from rule_u.schemas import (
    AnswerOut,
    ConversationCreated,
    ConversationIn,
    ConversationOut,
    ExpansionOut,
    GameDetail,
    GameList,
    GameOut,
    GameSearchIn,
    HealthOut,
    MessageIn,
    MessageOut,
    RequestAccepted,
    RequestOut,
    SourceOut,
)

COOKIE = "rule_u_session"


def create_app(settings: Settings | None = None, provider=None, retriever=None, game_ranker=None):
    settings = settings or Settings()
    engine = make_engine(settings)
    sessions = make_sessions(engine)

    @asynccontextmanager
    async def lifespan(app):
        # Single-process local worker: recover tasks interrupted by the last shutdown.
        with sessions.begin() as db:
            db.execute(
                update(Request)
                .where(Request.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    stage="failed",
                    error_code="server_restarted",
                )
            )
        yield
        engine.dispose()

    app = FastAPI(title="Rule_U API", version="0.1.0", lifespan=lifespan)
    app.state.sessions = sessions
    app.state.engine = engine

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "database_unavailable"})

    def get_db():
        with sessions() as db:
            yield db

    def session_id(request: HTTPRequest, response: Response):
        token = request.cookies.get(COOKIE)
        if not token or len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            token = secrets.token_hex(32)
            response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=31536000)
        return token

    def owned(db, cid, sid):
        conversation = db.get(Conversation, cid)
        if conversation is None or conversation.session_id != sid:
            raise HTTPException(404, "conversation_not_found")
        return conversation

    @app.get("/api/v1/health", response_model=HealthOut)
    def health(db=Depends(get_db)):
        db.execute(text("SELECT 1"))
        # Table presence matters, not merely an open SQLite connection.
        db.execute(select(Game.id).limit(1))
        return HealthOut(
            status="ok",
            database="ready",
            chat_provider=settings.chat_provider,
            embedding_provider=settings.embedding_provider,
        )

    def game_out(db, row):
        supported = bool(db.scalar(select(Edition.id).where(
            Edition.game_id == row.id, Edition.supported.is_(True)).limit(1)))
        docs = list(db.scalars(select(Document).join(DocumentScope).where(
            DocumentScope.game_id == row.id)).unique())
        review_path = ROOT / "config/source-reviews.json"
        reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
        verified = {r.get("sha256") for r in reviews.values() if r.get("status") == "official_verified"}
        status = "official_verified" if docs and all(d.content_hash in verified for d in docs) else "unverified"
        return GameOut.model_validate(row).model_copy(update={
            "rules_supported": supported, "source_review": status})

    def filtered(db, query="", players=None, max_minutes=None, category=""):
        rows = db.scalars(select(Game).order_by(Game.name_ko, Game.id))
        return [g for g in rows if
                (not query or query.casefold() in " ".join([g.name_ko, g.name_original, *g.aliases]).casefold())
                and (players is None or g.min_players <= players <= g.max_players)
                and (max_minutes is None or 0 < g.max_minutes <= max_minutes)
                and (not category or category in g.categories)]

    def game_page(db, rows, page, page_size):
        return GameList(items=[game_out(db, g) for g in rows[(page-1)*page_size:page*page_size]],
                        page=page, page_size=page_size, total=len(rows))

    @app.get("/api/v1/games", response_model=GameList)
    def games(query: str = "", page: int = Query(1, ge=1),
              page_size: int = Query(12, ge=1, le=100),
              players: int | None = Query(None, ge=1, le=100),
              max_minutes: int | None = Query(None, ge=1, le=1440),
              category: str = "", db=Depends(get_db)):
        return game_page(db, filtered(db, query, players, max_minutes, category), page, page_size)

    @app.get("/api/v1/game-categories", response_model=list[str])
    def categories(db=Depends(get_db)):
        return sorted({c for g in db.scalars(select(Game)) for c in g.categories})

    @app.post("/api/v1/games/search", response_model=GameList)
    async def search_games(body: GameSearchIn, db=Depends(get_db)):
        players, minutes, category = constraints(body, categories(db))
        rows = filtered(db, players=players, max_minutes=minutes, category=category)
        # Release SQLite's read transaction before calling an external provider.
        db.commit()
        if body.query.strip() and rows:
            try:
                ids = await asyncio.wait_for((game_ranker or semantic_ids)(settings, body.query),
                                             settings.api_timeout_seconds)
            except ProviderError as exc:
                raise HTTPException(503, str(exc)) from None
            except TimeoutError:
                raise HTTPException(504, "search_timeout") from None
            except Exception:
                raise HTTPException(503, "search_unavailable") from None
            rank = {gid: index for index, gid in enumerate(ids)}
            # Revalidate from SQLite after the external call; never trust vector metadata.
            rows = [g for g in filtered(db, players=players, max_minutes=minutes, category=category)
                    if g.id in rank]
            rows.sort(key=lambda g: rank[g.id])
        return game_page(db, rows, body.page, body.page_size)

    @app.get("/api/v1/games/{game_id}", response_model=GameDetail)
    def game(game_id: str, db=Depends(get_db)):
        row = db.get(Game, game_id)
        if row is None:
            raise HTTPException(404, "game_not_found")
        return GameDetail(
            **game_out(db, row).model_dump(),
            editions=list(db.scalars(select(Edition).where(Edition.game_id == game_id))),
            expansions=[ExpansionOut.model_validate(e).model_copy(update={"edition_ids": list(
                db.scalars(select(expansion_editions.c.edition_id).where(
                    expansion_editions.c.expansion_id == e.id)))})
                for e in db.scalars(select(Expansion).where(Expansion.game_id == game_id))],
        )

    @app.post("/api/v1/conversations", status_code=201, response_model=ConversationCreated)
    def create_conversation(body: ConversationIn, sid=Depends(session_id), db=Depends(get_db)):
        edition = db.get(Edition, body.edition_id)
        if edition is None or edition.game_id != body.game_id:
            raise HTTPException(422, "invalid_edition")
        # An unverified edition may be queried, but absent evidence produces a refusal.
        ids = set(body.expansion_ids)
        compatible = set(
            db.scalars(
                select(expansion_editions.c.expansion_id).where(
                    expansion_editions.c.edition_id == edition.id
                )
            )
        )
        if not ids.issubset(compatible):
            raise HTTPException(422, "incompatible_expansion")
        if ids and settings.chat_provider != "mock":
            supported = set(
                db.scalars(
                    select(Expansion.id).where(Expansion.id.in_(ids), Expansion.supported.is_(True))
                )
            )
            if ids != supported:
                raise HTTPException(409, "rules_not_ready")
        conversation = Conversation(session_id=sid, game_id=body.game_id, edition_id=edition.id)
        db.add(conversation)
        db.flush()
        for eid in ids:
            db.execute(
                conversation_expansions.insert().values(
                    conversation_id=conversation.id, edition_id=edition.id, expansion_id=eid
                )
            )
        db.commit()
        return ConversationCreated(conversation_id=conversation.id)

    @app.get("/api/v1/conversations/{cid}", response_model=ConversationOut)
    def get_conversation(cid: str, sid=Depends(session_id), db=Depends(get_db)):
        row = owned(db, cid, sid)
        return ConversationOut(
            id=row.id,
            game_id=row.game_id,
            edition_id=row.edition_id,
            expansion_ids=list(
                db.scalars(
                    select(conversation_expansions.c.expansion_id).where(
                        conversation_expansions.c.conversation_id == cid
                    )
                )
            ),
            active_request_id=db.scalar(select(Request.id).where(Request.conversation_id == cid,
                Request.status.in_(["queued", "running"]))),
            latest_request_id=db.scalar(select(Request.id).where(Request.conversation_id == cid)
                .order_by(Request.created_at.desc(), Request.id.desc()).limit(1)),
            latest_client_request_id=db.scalar(select(Request.client_request_id).where(Request.conversation_id == cid)
                .order_by(Request.created_at.desc(), Request.id.desc()).limit(1)),
            messages=[
                MessageOut.model_validate(m).model_copy(update={"citations": [SourceOut(**citation_out(c, db))
                    for c in db.scalars(select(Citation).where(Citation.message_id == m.id))]})
                for m in db.scalars(
                    select(Message)
                    .where(Message.conversation_id == cid)
                    .order_by(Message.created_at, Message.id)
                )
            ],
        )

    async def generate(rid):
        try:
            with sessions.begin() as db:
                row = db.get(Request, rid)
                row.status, row.stage = "running", "retrieve"
                conversation = db.get(Conversation, row.conversation_id)
                game = db.get(Game, conversation.game_id)
                edition = db.get(Edition, conversation.edition_id)
                messages = [
                    {"role": m.role, "content": m.content}
                    for m in db.scalars(
                        select(Message)
                        .where(Message.conversation_id == row.conversation_id)
                        .order_by(Message.created_at, Message.id)
                    )
                ]
                context = {
                    "game": {"id": game.id, "name": game.name_ko,
                             "description": game.description, "players": [game.min_players, game.max_players],
                             "minutes": [game.min_minutes, game.max_minutes]},
                    "edition": {"id": edition.id, "label": edition.label, "language": edition.language},
                    "expansion_ids": list(db.scalars(select(conversation_expansions.c.expansion_id)
                        .where(conversation_expansions.c.conversation_id == conversation.id))),
                    "messages": messages[-12:],
                    "mode": db.scalar(select(Message.mode).where(Message.conversation_id == conversation.id,
                        Message.role == "user").order_by(Message.created_at.desc(), Message.id.desc()).limit(1)),
                }
            # Never hold a DB transaction across external calls.
            def stage(value):
                with sessions.begin() as db:
                    db.get(Request, rid).stage = value

            if settings.chat_provider == "mock" and context["game"]["id"] == "demo-game" and retriever is None:
                answer = {"answer": await asyncio.wait_for(
                    (provider or chat_provider(settings)).generate(messages), settings.api_timeout_seconds),
                    "verdict": "unavailable", "citations": []}
            else:
                answer = await asyncio.wait_for(answer_question(
                    settings, sessions, context, provider, retriever, stage), settings.api_timeout_seconds)
            with sessions.begin() as db:
                row = db.get(Request, rid)
                message = Message(
                    conversation_id=row.conversation_id,
                    role="assistant",
                    content=answer["answer"],
                    verdict=answer["verdict"],
                    mode=context["mode"],
                )
                db.add(message)
                db.flush()
                citations = []
                for evidence in answer["citations"]:
                    citation = Citation(message_id=message.id, **{k: evidence[k] for k in (
                        "document_id", "chunk_id", "source_version", "title_snapshot",
                        "source_url_snapshot", "edition_snapshot", "page_start", "page_end", "excerpt")},
                        evidence_snapshot={k: evidence.get(k, "") for k in (
                            "number", "source_type", "language", "extraction_method", "review_note")})
                    citation.evidence_snapshot = {**citation.evidence_snapshot,
                                                  "explanation": evidence.get("explanation")}
                    db.add(citation)
                    db.flush()
                    citations.append(citation.id)
                message.cited_source_ids = citations
                row.result_message_id = message.id
                row.status, row.stage = "completed", "completed"
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProviderError) else "generation_failed"
            with sessions.begin() as db:
                row = db.get(Request, rid)
                row.status, row.stage, row.error_code = "failed", "failed", code

    @app.post(
        "/api/v1/conversations/{cid}/messages", status_code=202, response_model=RequestAccepted
    )
    def submit(
        cid: str,
        body: MessageIn,
        tasks: BackgroundTasks,
        sid=Depends(session_id),
        db=Depends(get_db),
    ):
        # Reserve the writer before the read/check/insert sequence (SQLite).
        db.connection().exec_driver_sql("UPDATE requests SET id=id WHERE 0")
        owned(db, cid, sid)
        existing = db.scalar(
            select(Request).where(
                Request.conversation_id == cid, Request.client_request_id == body.client_request_id
            )
        )
        if existing:
            return RequestAccepted(request_id=existing.id, status=existing.status)
        if db.scalar(
            select(Request.id).where(
                Request.conversation_id == cid, Request.status.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "request_in_progress")
        row = Request(conversation_id=cid, client_request_id=body.client_request_id)
        db.add_all(
            [row, Message(conversation_id=cid, role="user", content=body.message, mode=body.mode)]
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "request_conflict") from None
        tasks.add_task(generate, row.id)
        return RequestAccepted(request_id=row.id, status=row.status)

    @app.get("/api/v1/requests/{rid}", response_model=RequestOut)
    def get_request(rid: str, sid=Depends(session_id), db=Depends(get_db)):
        row = db.get(Request, rid)
        if row is None:
            raise HTTPException(404, "request_not_found")
        owned(db, row.conversation_id, sid)
        result = db.get(Message, row.result_message_id) if row.result_message_id else None
        return RequestOut(
            request_id=row.id,
            status=row.status,
            stage=row.stage,
            error_code=row.error_code,
            result=AnswerOut(answer=result.content, verdict=result.verdict,
                citations=[citation_out(c, db) for c in db.scalars(select(Citation).where(
                    Citation.message_id == result.id))],
                citation_notice="" if result.cited_source_ids else "이 답변에 인용된 근거가 없습니다.") if result else None,
        )

    def citation_out(c, db):
        doc = db.get(Document, c.document_id)
        review_path = ROOT / "config/source-reviews.json"
        reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
        verified = bool(doc and any(r.get("status") == "official_verified" and
                                   r.get("sha256") == doc.content_hash for r in reviews.values()))
        return {"id": c.id, "document_id": c.document_id, "title": c.title_snapshot,
                "edition": c.edition_snapshot, "url": c.source_url_snapshot,
                "page_start": c.page_start, "page_end": c.page_end, "excerpt": c.excerpt,
                "source_version": c.source_version, "original_available": bool(doc and doc.storage_key),
                **c.evidence_snapshot, "source_review": "official_verified" if verified else "unverified"}

    @app.post("/api/v1/sources/{source_id}/explanation", response_model=SourceOut)
    async def source_explanation(source_id: str, sid=Depends(session_id), db=Depends(get_db)):
        citation = db.get(Citation, source_id)
        if citation is None:
            raise HTTPException(404, "source_not_found")
        message = db.get(Message, citation.message_id)
        owned(db, message.conversation_id, sid)
        if citation.evidence_snapshot.get("explanation"):
            return citation_out(citation, db)
        evidence = {"number": citation.evidence_snapshot.get("number") or 1,
                    "excerpt": citation.excerpt, "title": citation.title_snapshot,
                    "edition": citation.edition_snapshot, "page_start": citation.page_start}
        answer = message.content
        question = db.scalar(select(Message.content).where(
            Message.conversation_id == message.conversation_id, Message.role == "user",
            Message.created_at <= message.created_at).order_by(
                Message.created_at.desc(), Message.id.desc()).limit(1)) or ""
        db.commit()
        try:
            explanation = await asyncio.wait_for(explain_source(
                provider or chat_provider(settings), answer, evidence, question), settings.api_timeout_seconds)
        except (ProviderError, TimeoutError):
            raise HTTPException(503, "explanation_unavailable") from None
        if explanation is None:
            raise HTTPException(503, "explanation_unavailable")
        citation = db.get(Citation, source_id)
        citation.evidence_snapshot = {**citation.evidence_snapshot, "explanation": explanation}
        db.commit()
        return citation_out(citation, db)

    @app.get("/api/v1/sources/{source_id}", response_model=SourceOut)
    def get_source(source_id: str, sid=Depends(session_id), db=Depends(get_db)):
        citation = db.get(Citation, source_id)
        if citation is None:
            raise HTTPException(404, "source_not_found")
        message = db.get(Message, citation.message_id)
        owned(db, message.conversation_id, sid)
        return citation_out(citation, db)

    @app.get("/api/v1/documents/{document_id}/original")
    def original(document_id: str, sid=Depends(session_id), db=Depends(get_db)):
        citation = db.scalar(select(Citation.id).join(Message).join(Conversation).where(
            Citation.document_id == document_id, Conversation.session_id == sid).limit(1))
        if citation is None:
            raise HTTPException(404, "document_not_found")
        doc = db.get(Document, document_id)
        if not doc or not doc.storage_key:
            raise HTTPException(404, "original_unavailable")
        path = (settings.data_dir / doc.storage_key).resolve()
        if not path.is_relative_to((settings.data_dir / "originals").resolve()) or not path.is_file():
            raise HTTPException(404, "original_unavailable")
        # Download untrusted originals; never serve executable HTML on the app origin.
        return FileResponse(path, filename=path.name, media_type="application/octet-stream",
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

    return app
