from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from rule_u.config import Settings


def make_engine(settings: Settings):
    settings.prepare_storage()
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        # Explicit transactions also cover DDL and reads on Python 3.12–3.14.
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")

    @event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    return engine


def make_sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
