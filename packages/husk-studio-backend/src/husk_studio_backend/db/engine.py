from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from husk_studio_backend.config import db_url, sync_db_url

_async_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None
_async_factory: async_sessionmaker[AsyncSession] | None = None
_sync_factory: sessionmaker[Session] | None = None


def _apply_pragmas(engine: Engine) -> None:
    """SQLite: WAL + foreign keys + reasonable synchronous level."""

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def async_engine() -> AsyncEngine:
    global _async_engine, _async_factory
    if _async_engine is None:
        _async_engine = create_async_engine(db_url(), echo=False, future=True)
        _async_factory = async_sessionmaker(_async_engine, expire_on_commit=False)
    return _async_engine


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    async_engine()
    assert _async_factory is not None
    return _async_factory


def sync_engine() -> Engine:
    global _sync_engine, _sync_factory
    if _sync_engine is None:
        _sync_engine = create_engine(sync_db_url(), echo=False, future=True)
        _apply_pragmas(_sync_engine)
        _sync_factory = sessionmaker(_sync_engine, expire_on_commit=False)
    return _sync_engine


@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    factory = async_session_factory()
    async with factory() as s:
        yield s


@contextmanager
def sync_session() -> Iterator[Session]:
    sync_engine()
    assert _sync_factory is not None
    with _sync_factory() as s:
        yield s


async def init_db() -> None:
    """Create tables. For MVP we use create_all; Alembic migrations land in M2."""
    from husk_studio_backend.db.models import Base

    engine = async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
