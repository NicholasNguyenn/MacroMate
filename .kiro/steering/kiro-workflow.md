# Kiro steering — MacroMate

This file covers Kiro-specific workflow only.
For domain rules, invariants, and stack decisions see: #[[file:../AGENTS.md]]

---

## Spec status (as of 2026-09-18)

- `mvp-cooking-flow` spec: **Draft, pending Nicholas review**
  - `requirements.md` — complete
  - `design.md` — complete (domain model, state machine, MCP tool contract)
  - `tasks.md` — complete (7 tasks, backend + parallel frontend track)

The spec covers the full 7-step MVP demo path.
The backend nutrition module (`nutrition.py`) and three pure MCP tools are done and must not be re-specified.

## Open decisions blocking spec finalization

See `docs/kiro-handoff.md` §7. Items that directly affect the spec before Claude Code starts implementing:

| # | Decision | Impact |
|---|---|---|
| 1 | Bedrock model access | Blocks Task 6 (Bedrock wiring) |
| 2 | Auth model | `user_id` handling in all stateful tools; tool contract may need amending |
| 3 | Alexa+ MCP discovery/auth | May require additional session/auth tools |
| 4 | Postgres host | Blocks Task 1 (Alembic against real DB) |
| 5 | Nutrition data source (USDA + OFF confirmed?) | Blocks Task 6 (search_nutrition real impl) |

Until these are resolved, Claude Code should implement Tasks 1–5 against a local Postgres and stub `search_nutrition` (as specified in tasks.md Task 6 step 1).

## Spec amendment protocol

If Claude Code reports `SPEC DRIFT:`, amend the relevant spec file in Kiro and commit before implementation continues.
Do NOT let the spec drift from the code — `.kiro/specs/` is hackathon evidence.

## What Kiro does NOT own

- `backend/` implementation files
- `nutrition.py` and the three pure MCP tools (done, tested, frozen)
- The Next.js frontend
