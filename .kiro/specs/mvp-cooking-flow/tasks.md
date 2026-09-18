# Tasks — MVP Cooking Flow

**Spec:** `mvp-cooking-flow`
**Status:** Draft — pending Nicholas review
**Executor:** Claude Code (reads this as a contract; does not edit it)

Ordering is designed so that backend and frontend can proceed in parallel after Task 2 is merged. Every task references the requirements and design sections it satisfies.

---

## Sequencing overview

```
T1 (DB foundation)
  └─► T2 (OAuth layer — required before any stateful tool)
        └─► T3 (profile + pantry tools)  ──────────────────┐
              └─► T4 (session + ingredient tools)           │  Frontend can start
                    └─► T5 (recipe + batch tools)           │  from T3 onward
                          └─► T6 (logging tools)            │
                                └─► T7 (Bedrock + nutrition APIs)
                                      └─► T8 (hardening + hooks) ◄──┘
```

---

## Task 1 — Database foundation

**Blocks:** everything else
**Satisfies:** design.md §1 (all entities), §6 (DB notes)

### Steps

1. Create `backend/src/macromate/models.py`:
   - Define all SQLAlchemy 2.x declarative models: `User`, `Profile`, `Equipment`, `Preference`, `PantryItem`, `CookingSession`, `SessionIngredient`, `RecipeBatch`, `Portion`, `MealLog`.
   - All enums: `ItemState`, `SessionStatus`, `NutritionSource`.
   - Use `uuid_generate_v4()` default for all UUID PKs.
   - `CookingSession.equipment_override` → `ARRAY(Text)`, nullable.
   - `CookingSession.preference_overrides` → `ARRAY(Text)`, nullable.
   - All timestamps → `TIMESTAMPTZ`.

2. Create `backend/src/macromate/database.py`:
   - SQLAlchemy async engine (use `asyncpg`).
   - `AsyncSession` factory.
   - `get_db()` FastAPI dependency.

3. Create the initial Alembic migration:
   - `alembic init backend/alembic`
   - Generate migration from models.
   - The unique partial index on `MealLog(portion_id) WHERE voided=false` MUST be hand-written in the migration (Alembic does not generate partial indexes automatically).

4. Add `DATABASE_URL` to `config.py` and `.env.example`.

5. Add `sqlalchemy[asyncio]`, `asyncpg`, `alembic` to `pyproject.toml` dependencies.

### Acceptance
- `alembic upgrade head` runs against a local Postgres without error.
- `python -c "from macromate.models import Portion, MealLog; print('ok')"` exits 0.

---

## Task 2 — OAuth layer (Alexa+ account-linking)

**Blocks:** all stateful tools (T3+), add-on deployment
**Satisfies:** design.md §4 (stateless MCP + token-derived identity), REQ-X.3

Alexa+ requires OAuth 2.0 M2M (`client_credentials`) for service-level calls and OAuth 2.1 `authorization_code` + PKCE for user-level tool invocations. Your server must expose two well-known endpoints and issue Bearer tokens. The `user_id` in all stateful tools is derived from the validated Bearer token — it is never a caller-supplied parameter.

### Steps

1. Add `authlib` (OAuth 2.x server library) and `python-jose` (JWT) to `pyproject.toml` dependencies.

2. Create `backend/src/macromate/auth.py`:
   - `/.well-known/oauth-authorization-server` — returns OAuth authorization server metadata per RFC 8414. Must include `client_credentials` in `grant_types_supported` and `S256` in `code_challenge_methods_supported`.
   - `/.well-known/oauth-protected-resource` — Protected Resource Metadata per RFC 9728.
   - `POST /oauth/token` — issues Bearer tokens for `client_credentials` (M2M) and `authorization_code` + PKCE (user) grants.
   - `GET /oauth/authorize` — authorization endpoint for PKCE flow (account-linking).

3. Create `backend/src/macromate/dependencies.py`:
   - `get_current_user_id(token: str = Depends(oauth2_scheme)) -> str` — FastAPI dependency that validates the Bearer token and returns `user_id`. All stateful MCP tools use this dependency instead of accepting `user_id` as a parameter.

4. Mount the auth routes in `main.py` under `/oauth` and the well-known endpoints at root.

5. `main.py` must return `401` (no `WWW-Authenticate` header — Alexa+ requirement) for unauthenticated requests to MCP tools.

6. Write tests in `backend/tests/test_auth.py`:
   - `/.well-known/oauth-authorization-server` returns correct metadata shape.
   - `/.well-known/oauth-protected-resource` returns correct metadata shape.
   - `POST /oauth/token` with valid `client_credentials` returns a Bearer token.
   - `POST /oauth/token` with invalid credentials returns 401.
   - `get_current_user_id` with a valid token returns the correct `user_id`.
   - `get_current_user_id` with an expired/invalid token raises 401 with no `WWW-Authenticate` header.

### Acceptance
- All new tests pass.
- Ruff passes.
- `curl -s https://localhost:8080/.well-known/oauth-authorization-server | python -m json.tool` returns valid JSON with required fields.

---

## Task 3 — Profile, pantry, and nutrition lookup tools

**Blocks:** frontend integration, all subsequent tool tasks
**Satisfies:** REQ-1.1–REQ-1.5, REQ-2.3–REQ-2.5, design.md §5.1–§5.5

**Note on `user_id`:** all tools derive `user_id` from the validated Bearer token via the `get_current_user_id` dependency (Task 2). Tools do NOT accept `user_id` as a parameter.

This task produces the contract the frontend needs to begin its parallel track.

### Steps

1. In `mcp_server.py`, implement:
   - `get_profile()`
   - `update_profile(calorie_target?, protein_target_g?)`
   - `set_preference(text, action, scope, session_id?)`
   - `update_equipment(name, action, scope, session_id?)`
   - `list_pantry()`
   - `update_pantry(name, action, quantity_g?, calories_per_100g?, protein_g_per_100g?, nutrition_source?)`
   - `search_nutrition(query)` — stub returning a hardcoded fixture for now; real USDA/OFF integration is Task 7.

2. Each tool must:
   - Resolve `user_id` from the auth dependency, never from a tool argument.
   - Delegate all math to `nutrition.py` (invariant 2).
   - Carry `estimated` through every response that touches macros (invariant 3).
   - Write session overrides to `CookingSession` columns, never to `Equipment`/`Preference` tables (design.md §3).

3. Write tests in `backend/tests/test_profile_tools.py` and `backend/tests/test_pantry_tools.py`:
   - Happy path for each tool.
   - `set_preference` with `scope="session"` — verify profile row is unchanged.
   - `update_equipment` with `scope="session"` — verify profile row is unchanged.
   - `update_pantry` add + remove round trip.
   - `search_nutrition` ambiguous stub returns multiple candidates, none silently selected.

### Acceptance
- All new tests pass (`pytest -q`).
- Ruff passes (`ruff check backend/src`).
- A human can call `get_profile` and `update_profile` via the MCP handshake script.

---

## Task 4 — Cooking session and ingredient tools

**Blocks:** T5
**Satisfies:** REQ-2.1–REQ-2.6, REQ-4.1–REQ-4.3, design.md §5.6

### Steps

1. In `mcp_server.py`, implement:
   - `start_cooking_session()`
   - `add_session_ingredient(session_id, name, quantity_g, calories_per_100g, protein_g_per_100g, estimated?)`
   - `adjust_session_ingredient(session_id, ingredient_id, new_quantity_g, estimated?)`

2. `add_session_ingredient`:
   - Computes ingredient macros using `Macros(calories=..., protein_g=...)` scaled by `quantity_g / 100`.
   - Stores result on `SessionIngredient`. Does NOT call the LLM.
   - Sets `state=AVAILABLE`.

3. `adjust_session_ingredient`:
   - Derives `correction_factor = new_quantity_g / old_quantity_g`.
   - Calls `Macros.scaled(factor)` to recompute.
   - Stores the updated macros and `correction_factor`.
   - Estimated propagation: if `new_quantity_g` is estimated, set `estimated=true`; otherwise inherit original.

4. Write tests in `backend/tests/test_session_tools.py`:
   - `start_cooking_session` returns a UUID.
   - `add_session_ingredient` stores macros computed from per-100g × quantity (spot check: 400g chicken at 120 kcal/100g = 480 kcal).
   - `adjust_session_ingredient` with factor 0.5 halves calories.
   - Tool on a `FINALIZED` session returns `SESSION_NOT_ACTIVE`.
   - `estimated=True` ingredient propagates flag.

### Acceptance
- All new tests pass.
- Ruff passes.

---

## Task 5 — Recipe suggestion and batch finalization

**Blocks:** T6
**Satisfies:** REQ-3.1–REQ-3.4, REQ-5.1–REQ-5.5, design.md §5.7–§5.8

### Steps

1. In `mcp_server.py`, implement:
   - `suggest_recipe(session_id)` — assembles context dict (ingredients, effective equipment, effective preferences, targets). Returns structured dict with NO macro numbers (REQ-3.2).
   - `finalize_batch(session_id, portions)` — calls `total()` then `split_batch()`, creates `RecipeBatch`, creates `portions` × `Portion` rows, transitions `SessionIngredient` state to `PREPARED`, sets `CookingSession.status=FINALIZED`.

2. `suggest_recipe` effective equipment/preference resolution (design.md §3):
   - If `CookingSession.equipment_override IS NOT NULL`, use that.
   - Otherwise, join `Equipment` for user.
   - Preferences: saved list + session overrides appended.

3. Write tests in `backend/tests/test_batch_tools.py`:
   - `suggest_recipe` includes ingredients and effective equipment; asserts NO calories/protein keys in response.
   - `finalize_batch` with 3 portions: verify `RecipeBatch.portions_intended=3`, 3 `Portion` rows created, all `SessionIngredient` rows in `PREPARED` state.
   - `finalize_batch` on empty session returns `NO_INGREDIENTS`.
   - `finalize_batch` on `FINALIZED` session returns `SESSION_NOT_ACTIVE`.
   - `estimated` flag propagates from any estimated ingredient to batch and portions.

### Acceptance
- All new tests pass.
- Ruff passes.

---

## Task 6 — Meal logging

**Blocks:** T7 (full integration), T8 (hardening)
**Satisfies:** REQ-6.1–REQ-6.6, REQ-7.1–REQ-7.3, design.md §5.9

### Steps

1. In `mcp_server.py`, implement:
   - `log_meal(portion_id)` — transitions `Portion` to `CONSUMED`, creates `MealLog`, calls `remaining_against_targets` and returns daily summary.
   - `void_meal_log(meal_log_id)` — sets `voided=true`, transitions `Portion` back to `PREPARED`.
   - `get_today()` — sums non-voided `MealLog` entries for UTC today, calls `remaining_against_targets`, returns summary.

2. `log_meal` idempotency: the unique partial index catches the duplicate; the server catches the DB constraint violation and returns `ALREADY_CONSUMED` (not a 500).

3. Write tests in `backend/tests/test_logging_tools.py`:
   - `log_meal` transitions `Portion.state` to `CONSUMED`.
   - `log_meal` duplicate call returns `ALREADY_CONSUMED`.
   - `void_meal_log` sets `voided=true` and transitions `Portion` back to `PREPARED`.
   - `void_meal_log` on already-voided log returns `ALREADY_VOIDED`.
   - `get_today` excludes voided logs from totals.
   - `get_today` with no logs returns zero consumption and full remaining targets.
   - `log_meal` on a `Portion` in `AVAILABLE` state (not yet in a batch) returns `STATE_VIOLATION`.

### Acceptance
- All new tests pass.
- Ruff passes.
- End-to-end: can run the full 7-step demo flow in a single pytest integration test.

---

## Task 7 — Bedrock and nutrition API integration

**Blocks:** T8
**Depends on:** Bedrock model access (auto-granted as of 2026-09-18), USDA API key (set `MACROMATE_USDA_API_KEY` in `.env`)
**Satisfies:** REQ-3.1 (live), REQ-2.3–REQ-2.5 (live)

### Steps

1. Wire `bedrock.py` into the Bedrock Converse API.
   - Run `spike_bedrock.py` to verify access first.
   - Implement the conversation loop in a new `backend/src/macromate/conversation.py`: receives user text + list of MCP tool definitions, calls Bedrock, dispatches tool calls back to `mcp_server`.

2. Replace the `search_nutrition` stub with real USDA FoodData Central queries:
   - `GET https://api.nal.usda.gov/fdc/v1/foods/search?query=<name>&api_key=<MACROMATE_USDA_API_KEY>`
   - Map response to `search_nutrition` return shape.
   - Return up to 3 ranked candidates when multiple matches; never silently select one (REQ-2.5, invariant 3).

3. Add Open Food Facts as a secondary source:
   - `GET https://world.openfoodfacts.org/cgi/search.pl?search_terms=<name>&json=1`
   - Merge results; rank USDA first, OFF second.

4. Write integration tests (skipped if `MACROMATE_USDA_API_KEY` is absent, not failures):
   - `search_nutrition("chicken breast")` returns at least one candidate with `estimated=false`.
   - `search_nutrition("xyzzy_nonexistent_12345")` returns `matched=false`.

### Acceptance
- `spike_bedrock.py` exits 0.
- `search_nutrition` stub is replaced.
- Ruff passes.

---

## Task 8 — Alexa+ add-on registration and hardening

**Blocks:** nothing (final task)
**Depends on:** App Runner deployed, OAuth layer live, `alexa-ai` CLI installed
**Satisfies:** design.md §6 (DB notes), REQ-X.1–REQ-X.5

### Steps

1. Write `backend/tests/test_integration.py` — the full 7-step demo flow as a single test:
   - Create user → set goals → add equipment → add preferences
   - Start session → add ingredients → adjust one quantity
   - Suggest recipe (assert no macros in response)
   - Finalize batch → verify portions created
   - Log one portion → verify daily totals
   - Verify remaining portions still in `PREPARED` state

2. Register the Alexa+ add-on:
   ```bash
   npm install -g @alexa-ai/cli
   alexa-ai new mcp --mcp-server-url "https://<your-apprunner-domain>.awsapprunner.com"
   alexa-ai deploy
   ```
   The CLI creates `addon-package/addon.json`. Commit this file to the repo.

3. Create `.kiro/hooks/pre-save-verify.json`:
   ```json
   {
     "trigger": "file_save",
     "glob": "backend/**/*.py",
     "command": ["backend/.venv/Scripts/python.exe", "-m", "pytest", "-q", "--tb=short"],
     "blocking": false
   }
   ```

4. Create `.kiro/hooks/pre-save-lint.json`:
   ```json
   {
     "trigger": "file_save",
     "glob": "backend/**/*.py",
     "command": ["backend/.venv/Scripts/python.exe", "-m", "ruff", "check", "backend/src"],
     "blocking": false
   }
   ```

5. Final ruff pass on all backend source.

6. Update `docs/friction-log.md` with OAuth implementation friction and any Alexa+ add-on registration friction.

### Acceptance
- `pytest -q` green, all tests passing.
- Ruff reports no errors.
- `.kiro/hooks/` committed to repo.
- `addon-package/addon.json` committed to repo.
- Integration test covers all 7 demo steps.
- `alexa-ai deploy` exits 0 and add-on shows as registered in the Alexa developer console.

---

## Parallel frontend track (for Nicholas's teammate)

Can start after Task 3 is merged. The MCP tool contract in `design.md` §5 is the interface.

Note: tools no longer accept `user_id` as a parameter — `user_id` is derived from the OAuth Bearer token by the server. The frontend is responsible for the OAuth account-linking flow (redirecting to `/oauth/authorize`, exchanging the code for a token, and passing the Bearer token in `Authorization` headers).

Suggested order:
1. Call `get_profile` / `update_profile` to wire goal-setting UI.
2. Call `list_pantry` / `update_pantry` for the pantry management screen.
3. Call `start_cooking_session` + `add_session_ingredient` for session creation.
4. Call `suggest_recipe` (mock the LLM response for now with a hardcoded recipe string).
5. Call `finalize_batch` for the batch summary screen.
6. Call `log_meal` + `get_today` for the daily tracking screen.

All tools return `estimated: bool` — the frontend should display a visual indicator (e.g., a `~` prefix or a tooltip) on any value where `estimated=true`.
