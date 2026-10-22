"""Isolated E2E database, never the developer's data/app.db."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic import command
from alembic.config import Config

from rule_u.cli import seed
from rule_u.config import ROOT, Settings
from rule_u.main import create_app

with TemporaryDirectory(prefix="rule-u-e2e-") as folder:
    os.environ["DATA_DIR"] = folder
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(folder).as_posix()}/app.db"
    os.environ["CHAT_PROVIDER"] = "mock"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    command.upgrade(Config(str(ROOT / "apps/api/alembic.ini")), "head")
    settings = Settings(_env_file=None)
    seed(settings)
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8100)
