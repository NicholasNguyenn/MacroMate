"""Alembic environment.

The database URL comes from `macromate.config.settings`, never from
alembic.ini, so there is one source of truth and no credentials in a tracked
config file.

The engine is async (asyncpg), so online migrations run through
`connection.run_sync`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from macromate.config import settings
from macromate.database import normalise_database_url
from macromate.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Same normalisation the app uses, so a provider URL that works at runtime
# also works for migrations. See macromate.database.normalise_database_url.
# Migrations deliberately use the direct endpoint, not the pooled one:
# PgBouncer in transaction mode cannot carry the session state DDL needs.
_url, _connect_args = normalise_database_url(settings.migration_database_url)

# configparser treats '%' as interpolation syntax, and passwords contain it.
config.set_main_option(
    "sqlalchemy.url", _url.render_as_string(hide_password=False).replace("%", "%%")
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting. Useful for reviewing DDL."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
        connect_args=_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
