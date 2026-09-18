"""FastAPI application hosting both the REST API and the MCP endpoint.

Two wiring notes, both easy to get wrong:

1. Mounting a Starlette sub-app into FastAPI does **not** run the sub-app's
   lifespan, and the MCP session manager needs its lifespan running or every
   request fails. So we drive `session_manager.run()` from FastAPI's own
   lifespan instead.
2. The mount is added *last*. Starlette matches routes in registration order, so
   the API routes above resolve first and everything else falls through to MCP.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from macromate import __version__
from macromate.config import settings
from macromate.mcp_server import mcp_server

# Must be built before `session_manager` is reachable -- it is created lazily.
mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=settings.mcp_stateless,
    host=settings.allowed_host_list[0] if settings.allowed_host_list else "127.0.0.1",
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="MacroMate",
    version=__version__,
    description="Cooking and meal-prep assistant: REST API plus an MCP server at /mcp.",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str | bool]:
    """Liveness probe. App Runner health checks point here."""
    return {
        "status": "ok",
        "version": __version__,
        "mcp_endpoint": "/mcp",
        "stateless_mcp": settings.mcp_stateless,
    }


# Registered last on purpose -- see module docstring.
app.mount("/", mcp_app)
