# Handoff to Claude Code — Implementation Phase

**From:** Kiro spec session, 2026-09-18
**Branch:** `feat/plan-b-foundation`
**Repo:** https://github.com/NicholasNguyenn/MacroMate

---

## Read first

In this order:

1. `AGENTS.md` — domain invariants, stack, and conventions. Non-negotiable.
2. `.kiro/specs/mvp-cooking-flow/requirements.md` — EARS requirements
3. `.kiro/specs/mvp-cooking-flow/design.md` — entity model, state machine, full MCP tool contract (15 tools)
4. `.kiro/specs/mvp-cooking-flow/tasks.md` — 8 sequenced tasks with acceptance criteria

---

## What is already built and frozen

Do not re-implement or re-specify these. They are done and tested.

| Path | What it is |
|---|---|
| `backend/src/macromate/nutrition.py` | All nutrition arithmetic. Pure functions. 9 tests passing. |
| `backend/src/macromate/mcp_server.py` | MCP server + 3 pure tools (calculate_portions, remaining_daily_targets, scale_ingredient) |
| `backend/src/macromate/main.py` | FastAPI app, MCP mounted at `/mcp`, lifespan wired |
| `backend/src/macromate/bedrock.py` | Bedrock Converse client (written, unverified — run spike_bedrock.py first) |
| `backend/src/macromate/config.py` | Env settings via pydantic-settings |
| `backend/scripts/spike_mcp_handshake.py` | MCP round-trip check |
| `backend/scripts/spike_bedrock.py` | Bedrock access check |

---

## Where to start — Task 1 (DB foundation)

Full details in `.kiro/specs/mvp-cooking-flow/tasks.md` Task 1. Summary:

1. Create `backend/src/macromate/models.py` — all SQLAlchemy 2.x declarative models per `design.md §1`:
   - Entities: `User`, `Profile`, `Equipment`, `Preference`, `PantryItem`, `CookingSession`, `SessionIngredient`, `RecipeBatch`, `Portion`, `MealLog`
   - Enums: `ItemState`, `SessionStatus`, `NutritionSource`
   - `CookingSession.equipment_override` → `ARRAY(Text)`, nullable
   - `CookingSession.preference_overrides` → `ARRAY(Text)`, nullable
   - All timestamps → `TIMESTAMPTZ`
   - All PKs → UUID

2. Create `backend/src/macromate/database.py` — SQLAlchemy async engine (asyncpg), `AsyncSession` factory, `get_db()` FastAPI dependency.

3. Alembic init + initial migration. **The unique partial index on `MealLog(portion_id) WHERE voided=false` must be hand-written in the migration** — Alembic does not auto-generate partial indexes.

4. Add to `pyproject.toml`: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`.

**Acceptance:** `alembic upgrade head` runs clean against a local Postgres.

---

## Task 2 must come before any stateful tool

The OAuth layer gates everything. Full details in `tasks.md` Task 2. Key points:

- **`user_id` is NEVER a tool parameter.** It is derived server-side from the Bearer token via a `get_current_user_id` FastAPI dependency. Every stateful tool uses this dependency.
- Must expose `/.well-known/oauth-authorization-server` (RFC 8414) and `/.well-known/oauth-protected-resource` (RFC 9728).
- `401` responses must NOT include a `WWW-Authenticate` header — Alexa+ hard requirement.
- Supports two grant types: `client_credentials` (M2M) and `authorization_code` + PKCE S256 (user).

---

## Non-negotiable rules (from AGENTS.md)

1. **The LLM never does arithmetic.** All macro math goes through `nutrition.py`. Never compute calories, protein, or scaling inline in a tool.

2. **`estimated` propagates everywhere.** Every response involving macros must carry `estimated: bool`. Never strip it.

3. **Available → Prepared → Consumed are three distinct states.** Any code path that skips a state is a bug. See `design.md §2` for the state machine.

4. **If you find a spec error, output `SPEC DRIFT:` and stop.** Do not silently work around it. Nicholas will take it back to Kiro to amend the spec, then re-commit before you continue. `.kiro/specs/` is hackathon evidence — judges read it.

---

## MCP SDK version

The SDK is **2.x**. Every online tutorial and LLM-generated example targets v1 and is wrong.

| v1 (wrong) | v2 (correct) |
|---|---|
| `FastMCP` | `MCPServer` (`mcp.server.mcpserver`) |
| `streamablehttp_client` | `streamable_http_client` |
| `structuredContent` | `structured_content` |

See `docs/friction-log.md` for more v1→v2 gotchas.

---

## Running tests and lint

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src
```

---

## Environment

Copy `backend/.env.example` to `backend/.env` and set:
- `MACROMATE_DATABASE_URL` — local Postgres for dev (e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/macromate`)
- `MACROMATE_USDA_API_KEY` — Nicholas has this key; ask him to set it
- `AWS_REGION=us-east-1` — for Bedrock

---

## Task sequence

```
T1 (DB foundation)
  └─► T2 (OAuth layer)
        └─► T3 (profile + pantry tools)
              └─► T4 (session + ingredient tools)
                    └─► T5 (recipe + batch tools)
                          └─► T6 (logging tools)
                                └─► T7 (Bedrock + USDA/OFF integration)
                                      └─► T8 (Alexa+ add-on + hardening)
```

Frontend can start in parallel once T3 is done (the tool contract is stable at that point).

---

## Spec ownership

**Only Kiro edits `.kiro/specs/`.** If you need a spec change, output `SPEC DRIFT: <description>` and stop. Nicholas will bring it back to Kiro.
