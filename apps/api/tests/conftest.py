from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from rule_u.cli import seed
from rule_u.config import Settings
from rule_u.main import create_app


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv("RULE_U_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RULE_U_DATABASE_URL", f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    monkeypatch.setenv("RULE_U_CHAT_PROVIDER", "mock")
    monkeypatch.setenv("RULE_U_EMBEDDING_PROVIDER", "mock")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    settings = Settings(_env_file=None)
    seed(settings)
    return settings, config


@pytest.fixture
def app(configured):
    application = create_app(configured[0])
    yield application
    application.state.engine.dispose()
