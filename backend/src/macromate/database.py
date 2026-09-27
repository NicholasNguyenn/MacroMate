"""Async database engine, session factory, and the FastAPI dependency.

Implements `.kiro/specs/mvp-cooking-flow/tasks.md` Task 1 step 2.

The engine is created lazily rather than at import time so that importing
`macromate.models` (or anything that pulls it in) does not require a reachable
database -- tests, Alembic's offline mode, and `--help` all need that.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from macromate.config import settings

#: Query parameters that libpq accepts but asyncpg rejects outright. Hosted
#: Postgres providers put these in the connection string they give you.
_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "options", "target_session_attrs")


def normalise_database_url(raw: str) -> tuple[URL, dict[str, Any]]:
    """Make a copy-pasted provider URL usable by asyncpg.

    Two incompatibilities bite here, and both produce errors that point
    nowhere near the real cause:

    1. Hosted providers hand out ``postgresql://``, which SQLAlchemy resolves
       to psycopg2. We only install asyncpg, so that fails with a driver
       error rather than anything about the URL.
    2. ``?sslmode=require`` is libpq syntax. asyncpg raises
       ``TypeError: connect() got an unexpected keyword argument 'sslmode'``.
       The equivalent is an ``ssl`` connect arg, which asyncpg accepts as the
       same string value.

    Returns the cleaned URL and the connect args it implies.
    """
    url = make_url(raw)

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername != "postgresql+asyncpg":
        return url, {}

    query = dict(url.query)
    connect_args: dict[str, Any] = {}

    sslmode = query.get("sslmode")
    if sslmode:
        # asyncpg takes the same vocabulary ('require', 'verify-full', ...)
        # under a different keyword.
        connect_args["ssl"] = sslmode

    # A '-pooler' host is PgBouncer in transaction mode. asyncpg caches
    # prepared statements per connection, and the pooler can hand that
    # connection to a different session between statements, so the cache has
    # to be off. Symptom otherwise is an intermittent
    # "prepared statement _pg_N does not exist" under concurrency -- which
    # passes every local test and only shows up under real load.
    if url.host and "-pooler" in url.host:
        connect_args["statement_cache_size"] = 0

    for param in _LIBPQ_ONLY_PARAMS:
        query.pop(param, None)

    return url.set(query=query), connect_args


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Process-wide async engine.

    `pool_pre_ping` matters in deployment: App Runner keeps containers warm
    between bursts of traffic, long enough for Postgres to have dropped the
    connection underneath an idle pool.
    """
    url, connect_args = normalise_database_url(settings.database_url)
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session, committing on success.

    Rolls back and re-raises on any exception, so a tool that fails partway
    through cannot leave a half-applied state transition behind.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
