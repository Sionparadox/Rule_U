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
    min_minutes: int = 0
    max_minutes: int = 0
    categories: list[str] = Field(default_factory=list)
    source_review: str = "unverified"


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
    edition_ids: list[str] = Field(default_factory=list)


class GameSearchIn(BaseModel):
    query: str = Field(default="", max_length=1000)
    players: int | None = Field(default=None, ge=1, le=100)
    max_minutes: int | None = Field(default=None, ge=1, le=1440)
    category: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=100)


class SourceExplanationOut(BaseModel):
    rule_summary: str
    application: str


class SourceOut(BaseModel):
    id: str
    document_id: str
    number: int = 0
    title: str
    edition: str
    url: str
    page_start: int | None = None
    page_end: int | None = None
    excerpt: str
    source_version: str
    source_type: str = "unverified"
    language: str = ""
    extraction_method: str = ""
    review_note: str = ""
    original_available: bool = False
    explanation: SourceExplanationOut | None = None
    source_review: str = "unverified"


class GameDetail(GameOut):
    editions: list[EditionOut]
    expansions: list[ExpansionOut]


class ConversationIn(BaseModel):
    game_id: str
    edition_id: str
    expansion_ids: list[str] = Field(default_factory=list, max_length=30)


class ConversationCreated(BaseModel):
    conversation_id: str


class FeedbackIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rating: Literal["helpful", "wrong"]
    reason: Literal["rule_differs", "wrong_page", "missing_info", "other"] | None = None
    note: str = Field(default="", max_length=500)


class FeedbackOut(ORMModel):
    rating: Literal["helpful", "wrong"]
    reason: Literal["rule_differs", "wrong_page", "missing_info", "other"] | None = None
    note: str = ""


class MessageOut(ORMModel):
    id: str
    role: str
    content: str
    verdict: str | None
    created_at: datetime
    cited_source_ids: list[str] = Field(default_factory=list)
    mode: str = "qa"
    citations: list[SourceOut] = Field(default_factory=list)
    feedback: FeedbackOut | None = None
    saved: bool = False


class BookmarkIn(BaseModel):
    saved: bool


class BookmarkOut(BaseModel):
    message_id: str
    saved: bool


class SavedRuleOut(BaseModel):
    message_id: str
    conversation_id: str
    edition_id: str
    question: str
    answer: str
    verdict: str | None
    citations: list[SourceOut] = Field(default_factory=list)
    saved_at: datetime


class SavedRuleList(BaseModel):
    items: list[SavedRuleOut]


class SituationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    element: str = Field(default="", max_length=300)
    phase: str = Field(default="", max_length=300)
    action: str = Field(default="", max_length=300)


class SituationOut(BaseModel):
    element: str = ""
    phase: str = ""
    action: str = ""


class ConversationOut(BaseModel):
    id: str
    game_id: str
    edition_id: str
    expansion_ids: list[str]
    messages: list[MessageOut]
    situation: SituationOut | None = None
    active_request_id: str | None = None
    latest_request_id: str | None = None
    latest_client_request_id: str | None = None


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
    citations: list[SourceOut] = Field(default_factory=list)
    citation_notice: str = "이 답변에 인용된 근거가 없습니다."


class RequestOut(RequestAccepted):
    stage: str
    error_code: str | None
    result: AnswerOut | None
    skip_external: bool = False
    # Text being written before validation; never shown as a final answer.
    draft: str | None = None
    # Internal reason code for refusals; the UI does not show it.
    diagnostic: str | None = None


class HealthOut(BaseModel):
    status: str
    database: str
    chat_provider: str
    embedding_provider: str
    live_connections_verified: bool = False
    rules_ready: bool = False
