"""Engine and sessions. SQLite in WAL mode so the API can read while the writer thread commits."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  (registers tables)

SCHEMA_VERSION = 1
_engine: Engine | None = None


def init_engine(db_path: Path | str) -> Engine:
    global _engine
    url = "sqlite://" if str(db_path) == ":memory:" else f"sqlite:///{db_path}"
    kwargs: dict = {"connect_args": {"check_same_thread": False, "timeout": 15}}
    if url == "sqlite://":
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    SQLModel.metadata.create_all(engine)
    with engine.connect() as c:
        c.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
    _engine = engine
    return engine


def engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database not initialised")
    return _engine


def get_session() -> Iterator[Session]:
    with Session(engine()) as s:
        yield s
