"""Tests for provider connection-string normalisation.

These cover the shape of URL that Neon, Supabase, and RDS hand you on the
dashboard, which is libpq syntax and not directly usable by asyncpg.
"""

from __future__ import annotations

from macromate.database import normalise_database_url

NEON_STYLE = (
    "postgresql://user:pw@ep-cool-thing-123456.us-east-2.aws.neon.tech/macromate"
    "?sslmode=require&channel_binding=require"
)


def test_bare_postgresql_scheme_is_upgraded_to_asyncpg() -> None:
    """Providers hand out postgresql://, which would resolve to psycopg2."""
    url, _ = normalise_database_url("postgresql://u:p@localhost:5432/macromate")
    assert url.drivername == "postgresql+asyncpg"


def test_sslmode_moves_from_query_string_to_connect_args() -> None:
    url, connect_args = normalise_database_url(NEON_STYLE)
    assert "sslmode" not in url.query
    assert connect_args["ssl"] == "require"


def test_channel_binding_is_dropped() -> None:
    """asyncpg rejects it outright; it is a libpq-only parameter."""
    url, _ = normalise_database_url(NEON_STYLE)
    assert "channel_binding" not in url.query


def test_host_and_database_survive_normalisation() -> None:
    url, _ = normalise_database_url(NEON_STYLE)
    assert url.host == "ep-cool-thing-123456.us-east-2.aws.neon.tech"
    assert url.database == "macromate"
    assert url.username == "user"


def test_plain_local_url_needs_no_connect_args() -> None:
    url, connect_args = normalise_database_url(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/macromate"
    )
    assert connect_args == {}
    assert url.drivername == "postgresql+asyncpg"


def test_non_postgres_url_is_left_alone() -> None:
    """SQLite is not a target, but normalisation must not corrupt it."""
    url, connect_args = normalise_database_url("sqlite+aiosqlite:///./local.db")
    assert url.drivername == "sqlite+aiosqlite"
    assert connect_args == {}
