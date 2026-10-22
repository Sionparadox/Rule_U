from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("external_source", "external_id"),
        CheckConstraint("min_players >= 1 AND max_players >= min_players"),
        CheckConstraint("min_minutes >= 0 AND max_minutes >= min_minutes"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    external_source: Mapped[str | None]
    external_id: Mapped[str | None]
    name_ko: Mapped[str]
    name_original: Mapped[str] = mapped_column(default="")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    min_players: Mapped[int] = mapped_column(default=1)
    max_players: Mapped[int] = mapped_column(default=1)
    min_minutes: Mapped[int] = mapped_column(default=0)
    max_minutes: Mapped[int] = mapped_column(default=0)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint("id", "game_id"),
        UniqueConstraint("game_id", "label", "language"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    label: Mapped[str]
    language: Mapped[str]
    publisher: Mapped[str] = mapped_column(default="")
    supported: Mapped[bool] = mapped_column(Boolean, default=False)


class Expansion(Base):
    __tablename__ = "expansions"
    __table_args__ = (UniqueConstraint("id", "game_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    name: Mapped[str]
    supported: Mapped[bool] = mapped_column(Boolean, default=False)


expansion_editions = Table(
    "expansion_editions",
    Base.metadata,
    Column("expansion_id", String, primary_key=True),
    Column("edition_id", String, primary_key=True),
    Column("game_id", String, nullable=False),
    ForeignKeyConstraint(["expansion_id", "game_id"], ["expansions.id", "expansions.game_id"]),
    ForeignKeyConstraint(["edition_id", "game_id"], ["editions.id", "editions.game_id"]),
)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    title: Mapped[str]
    source_type: Mapped[str]
    source_url: Mapped[str]
    storage_key: Mapped[str | None]
    extracted_text_key: Mapped[str | None]
    language: Mapped[str]
    version: Mapped[str]
    content_hash: Mapped[str] = mapped_column(unique=True)
    license_note: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentScope(Base):
    __tablename__ = "document_scopes"
    __table_args__ = (
        ForeignKeyConstraint(["edition_id", "game_id"], ["editions.id", "editions.game_id"]),
        ForeignKeyConstraint(
            ["expansion_id", "edition_id"],
            ["expansion_editions.expansion_id", "expansion_editions.edition_id"],
        ),
        Index(
            "uq_document_scope_base",
            "document_id",
            "edition_id",
            unique=True,
            sqlite_where=text("expansion_id IS NULL"),
        ),
        UniqueConstraint("document_id", "edition_id", "expansion_id"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    edition_id: Mapped[str]
    expansion_id: Mapped[str | None]


class CollectionState(Base):
    __tablename__ = "collection_states"
    __table_args__ = (
        UniqueConstraint("source_id", "edition_id", "normalized_query", "config_version"),
        ForeignKeyConstraint(["edition_id", "game_id"], ["editions.id", "editions.game_id"]),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    source_id: Mapped[str]
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    edition_id: Mapped[str]
    normalized_query: Mapped[str] = mapped_column(default="")
    fetch_status: Mapped[str] = mapped_column(default="pending")
    index_status: Mapped[str] = mapped_column(default="pending")
    content_hash: Mapped[str | None]
    config_version: Mapped[str] = mapped_column(default="v1")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(["edition_id", "game_id"], ["editions.id", "editions.game_id"]),
        UniqueConstraint("id", "edition_id"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    edition_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


conversation_expansions = Table(
    "conversation_expansions",
    Base.metadata,
    Column("conversation_id", String, primary_key=True),
    Column("expansion_id", String, primary_key=True),
    Column("edition_id", String, nullable=False),
    ForeignKeyConstraint(
        ["conversation_id", "edition_id"], ["conversations.id", "conversations.edition_id"]
    ),
    ForeignKeyConstraint(
        ["expansion_id", "edition_id"],
        ["expansion_editions.expansion_id", "expansion_editions.edition_id"],
    ),
)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')"),
        UniqueConstraint("id", "conversation_id"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str | None]
    mode: Mapped[str] = mapped_column(default="qa")
    cited_source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (
        CheckConstraint(
            "(document_id IS NOT NULL AND game_id IS NULL) OR (document_id IS NULL AND game_id IS NOT NULL)"
        ),
        CheckConstraint("page_start IS NULL OR page_start >= 1"),
        CheckConstraint("page_end IS NULL OR (page_start IS NOT NULL AND page_end >= page_start)"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    game_id: Mapped[str | None] = mapped_column(ForeignKey("games.id"))
    chunk_id: Mapped[str | None]
    source_version: Mapped[str]
    title_snapshot: Mapped[str]
    source_url_snapshot: Mapped[str] = mapped_column(default="")
    edition_snapshot: Mapped[str] = mapped_column(default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("conversation_id", "client_request_id"),
        CheckConstraint("status IN ('queued','running','completed','failed')"),
        ForeignKeyConstraint(
            ["result_message_id", "conversation_id"], ["messages.id", "messages.conversation_id"]
        ),
        Index(
            "uq_active_request",
            "conversation_id",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
        ),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    client_request_id: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    stage: Mapped[str] = mapped_column(default="queued")
    result_message_id: Mapped[str | None]
    error_code: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
