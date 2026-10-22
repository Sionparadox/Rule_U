from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="", env_file=ROOT / ".env", extra="ignore", populate_by_name=True
    )
    data_dir: Path = ROOT / "data"
    database_url: str | None = None
    chat_provider: Literal["mock", "compatible"] = "mock"
    chat_base_url: str = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/"
    chat_model: str = "gpt-5.4-nano"
    chat_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("CHAT_API_KEY", "GMS_KEY", "chat_api_key"),
    )
    embedding_provider: Literal["mock", "compatible"] = "mock"
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_dimensions: int = Field(default=8, ge=1)
    api_timeout_seconds: float = Field(default=30, gt=0, le=120)
    bgg_enabled: bool = True
    bgg_api_token: SecretStr = SecretStr("")
    bgg_timeout_seconds: float = Field(default=45, ge=5, le=90)
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    external_top_k: int = Field(default=5, gt=0)
    candidate_k: int = Field(default=20, gt=0)
    search_mode: Literal["similarity", "hybrid", "mmr"] = "similarity"

    @model_validator(mode="after")
    def resolve_paths(self):
        if not self.data_dir.is_absolute():
            self.data_dir = (ROOT / self.data_dir).resolve()
        if self.database_url is None:
            self.database_url = f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only local SQLite databases are supported")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    def prepare_storage(self):
        for name in ("", "chroma", "originals", "extracted"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
