# MacroMate backend

FastAPI service hosting the REST API and MacroMate's self-hosted **MCP server over Streamable HTTP** at `/mcp`.

Stack rationale: [../docs/tech-stack-decision.md](../docs/tech-stack-decision.md) (Plan B).
Project rules: [../AGENTS.md](../AGENTS.md).

## Status

Skeleton and risk spikes. The pure nutrition tools are real and tested; the stateful domain (pantry, cooking sessions, meal logs) is **blocked on the Kiro spec** and deliberately not built. See AGENTS.md → Spec workflow.

## Setup

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS / Linux
cp .env.example .env
```

## Run

```bash
./.venv/Scripts/python.exe -m uvicorn macromate.main:app --port 8080 --reload
```

- `GET /health` — liveness probe; App Runner health checks point here
- `POST /mcp` — MCP Streamable HTTP endpoint
- `GET /docs` — OpenAPI UI

## Verify

```bash
./.venv/Scripts/python.exe -m pytest -q                      # nutrition invariants
./.venv/Scripts/python.exe scripts/spike_mcp_handshake.py    # MCP round trip (server must be running)
./.venv/Scripts/python.exe scripts/spike_bedrock.py          # Bedrock model access
```

`spike_mcp_handshake.py` takes an optional base URL, so the same check runs against a deployed service:

```bash
./.venv/Scripts/python.exe scripts/spike_mcp_handshake.py https://<app-runner-url>
```

That is how risk 1 (host buffering the stream) gets retired — run it against App Runner before building anything else on top.

## Layout

| Path | Purpose |
|---|---|
| `src/macromate/nutrition.py` | All arithmetic. Pure, tested, no LLM involvement. |
| `src/macromate/mcp_server.py` | MCP tool definitions. Delegates every calculation to `nutrition.py`. |
| `src/macromate/main.py` | FastAPI app; mounts the MCP app and drives its lifespan. |
| `src/macromate/bedrock.py` | Bedrock Converse client for the conversational layer. |
| `src/macromate/config.py` | Env-driven settings. |
| `scripts/` | Risk spikes. |

## Things that will bite you

- **The `mcp` SDK is 2.x.** `FastMCP` → `MCPServer`, `streamablehttp_client` → `streamable_http_client`, `structuredContent` → `structured_content`. Online examples are almost all v1. See [../docs/friction-log.md](../docs/friction-log.md).
- **`session_manager` is created lazily** — you must call `streamable_http_app()` before touching it. The ordering in `main.py` is load-bearing.
- **Mounting a Starlette app into FastAPI does not run its lifespan.** `main.py` drives `session_manager.run()` from the parent lifespan for this reason. Removing it yields a server that accepts connections and fails every MCP request.
- **`MACROMATE_ALLOWED_HOSTS` must include the deployed domain.** DNS-rebinding protection rejects unknown `Host` headers, so a fresh App Runner deploy will 400 everything until its domain is added.
- **`MACROMATE_MCP_STATELESS=true` in deployment.** Per-session state lives in process; once App Runner scales past one instance, a stateful session breaks. The Dockerfile sets this. Tradeoff noted in `.env.example`.

## Deploy (App Runner)

```bash
docker build -t macromate-backend .
docker run -p 8080:8080 -e MACROMATE_ALLOWED_HOSTS=127.0.0.1,localhost macromate-backend
```

Push to ECR and point App Runner at the image. Health check path `/health`, port 8080. Set `MACROMATE_ALLOWED_HOSTS` to the App Runner domain and give the instance role `bedrock:InvokeModel` and `bedrock:Converse`.
