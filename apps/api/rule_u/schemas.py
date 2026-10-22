from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GameOut(ORMModel):
    id: str
    name_ko: str
    description: str
    min_players: int
    max_players: int
    rules_supported: bool = False


class GameList(BaseModel):
    items: list[GameOut]
    page: int
    page_size: int
    total: int


class EditionOut(ORMModel):
    id: str
    label: str
    language: str
    supported: bool


class ExpansionOut(ORMModel):
    id: str
    name: str
    supported: bool


class GameDetail(GameOut):
    editions: list[EditionOut]
    expansions: list[ExpansionOut]


class ConversationIn(BaseModel):
    game_id: str
    edition_id: str
    expansion_ids: list[str] = Field(default_factory=list, max_length=30)


class ConversationCreated(BaseModel):
    conversation_id: str


class MessageOut(ORMModel):
    id: str
    role: str
    content: str
    verdict: str | None
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    game_id: str
    edition_id: str
    expansion_ids: list[str]
    messages: list[MessageOut]


class MessageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["qa", "ruling"] = "qa"
    client_request_id: str = Field(min_length=1, max_length=128)


class RequestAccepted(BaseModel):
    request_id: str
    status: str


class AnswerOut(BaseModel):
    answer: str
    verdict: str | None
    citations: list[dict] = Field(default_factory=list)
    citation_notice: str = "이 답변에 인용된 근거가 없습니다."


class RequestOut(RequestAccepted):
    stage: str
    error_code: str | None
    result: AnswerOut | None


class HealthOut(BaseModel):
    status: str
    database: str
    chat_provider: str
    embedding_provider: str
    live_connections_verified: bool = False
    rules_ready: bool = False
