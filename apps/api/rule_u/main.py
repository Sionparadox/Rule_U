import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from rule_u.config import Settings
from rule_u.db import make_engine, make_sessions
from rule_u.models import (
    Conversation,
    Edition,
    Expansion,
    Game,
    Message,
    Request,
    conversation_expansions,
    expansion_editions,
)
from rule_u.providers import ProviderError, chat_provider
from rule_u.schemas import (
    AnswerOut,
    ConversationCreated,
    ConversationIn,
    ConversationOut,
    GameDetail,
    GameList,
    GameOut,
    HealthOut,
    MessageIn,
    MessageOut,
    RequestAccepted,
    RequestOut,
)

COOKIE = "rule_u_session"


def create_app(settings: Settings | None = None, provider=None):
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

    @app.get("/api/v1/games", response_model=GameList)
    def games(
        query: str = "",
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db=Depends(get_db),
    ):
        statement = select(Game).where(Game.name_ko.contains(query, autoescape=True))
        total = db.scalar(select(func.count()).select_from(statement.subquery()))
        rows = db.scalars(
            statement.order_by(Game.name_ko, Game.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return GameList(
            items=[GameOut.model_validate(g) for g in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    @app.get("/api/v1/games/{game_id}", response_model=GameDetail)
    def game(game_id: str, db=Depends(get_db)):
        row = db.get(Game, game_id)
        if row is None:
            raise HTTPException(404, "game_not_found")
        return GameDetail(
            **GameOut.model_validate(row).model_dump(),
            editions=list(db.scalars(select(Edition).where(Edition.game_id == game_id))),
            expansions=list(db.scalars(select(Expansion).where(Expansion.game_id == game_id))),
        )

    @app.post("/api/v1/conversations", status_code=201, response_model=ConversationCreated)
    def create_conversation(body: ConversationIn, sid=Depends(session_id), db=Depends(get_db)):
        edition = db.get(Edition, body.edition_id)
        if edition is None or edition.game_id != body.game_id:
            raise HTTPException(422, "invalid_edition")
        # Stage 1 accepts unsupported editions only for the mock storage demonstration.
        if settings.chat_provider != "mock" and not edition.supported:
            raise HTTPException(409, "rules_not_ready")
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
            messages=[
                MessageOut.model_validate(m)
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
                row.status, row.stage = "running", "generate"
                messages = [
                    {"role": m.role, "content": m.content}
                    for m in db.scalars(
                        select(Message)
                        .where(Message.conversation_id == row.conversation_id)
                        .order_by(Message.created_at, Message.id)
                    )
                ]
            # Never hold a DB transaction across external calls.
            if settings.chat_provider != "mock":
                raise ProviderError("rules_not_ready")
            answer = await asyncio.wait_for(
                (provider or chat_provider(settings)).generate(messages),
                settings.api_timeout_seconds,
            )
            with sessions.begin() as db:
                row = db.get(Request, rid)
                message = Message(
                    conversation_id=row.conversation_id,
                    role="assistant",
                    content=answer,
                    verdict="unavailable",
                )
                db.add(message)
                db.flush()
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
            result=AnswerOut(answer=result.content, verdict=result.verdict) if result else None,
        )

    return app
