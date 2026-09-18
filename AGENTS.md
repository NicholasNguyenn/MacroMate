# AGENTS.md — MacroMate

Canonical instructions for all AI coding agents on this repo. Kiro reads this file natively; `CLAUDE.md` imports it.

**Standards live here and only here.** Do not duplicate them into `CLAUDE.md` or `.kiro/steering/` — two copies drift within a week, and then agents enforce different rules on the same codebase without anyone noticing.

---

## What this is

MacroMate is an AI cooking and meal-prep assistant: turn available ingredients into meals that hit calorie and protein targets, talk through cooking by voice, and track portions without re-entering the same information.

Built for the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/), Alexa+ track. **Deadline: 2026-10-23, 12:00 PDT.**

- Stack and rationale → [docs/tech-stack-decision.md](docs/tech-stack-decision.md)
- How Kiro and Claude Code divide work → [docs/dual-tool-workflow.md](docs/dual-tool-workflow.md)

---

## Domain rules — invariants, not preferences

### 1. Available / Prepared / Consumed are three distinct states

- **Available** — food the user has, in pantry or fridge.
- **Prepared** — food that went into a cooked batch.
- **Consumed** — food the user actually ate.

Cooking a batch is not eating it. Preparing moves Available → Prepared. Logging a meal moves Prepared → Consumed and counts against daily targets. **Any code path that skips a state is a bug**, not a shortcut. This separation is the product's core differentiator — no mainstream tracker models it correctly.

### 2. The LLM never does arithmetic

The model interprets requests, suggests recipes, and drives conversation. **Application code computes all nutrition** from confirmed quantities and nutrition data.

If you find yourself asking a model to add, divide, or scale numbers — stop. That is a function.

### 3. Uncertain nutrition data stays visibly uncertain

Never silently substitute a guess for a lookup. If a quantity is unconfirmed or a product match is ambiguous, that uncertainty must survive into the API response and the UI. Do not round it away, and do not let a default stand in for a real value without marking it.

### 4. Explicit preferences beat inferred ones

Saved preferences override guesses. Temporary session context ("I'm cooking at a friend's house") must not mutate the saved profile. Rejecting one recipe does not mark its ingredients disliked.

---

## Spec workflow

Specs live in `.kiro/specs/<feature>/` as `requirements.md`, `design.md`, and `tasks.md`. They are authored in Kiro.

- Specs are **authoritative**. Implementation follows the spec.
- **Only Kiro edits specs.** Every other agent reads them.
- If implementation reveals a spec is wrong, **flag it and stop** — do not silently work around it. Specs are cited as hackathon evidence for the AWS Builder mini-challenge; a spec that has drifted from the code is fiction, and judges read the repo.

---

## Repo conventions

- **Commit** `.kiro/specs/`, `.kiro/steering/`, `.kiro/hooks/` — these are project artifacts, not local config.
- **Never commit** `.kiro/settings/mcp.json`; it may carry credentials. Ship `.kiro/settings/mcp.json.example` instead.
- **Log friction as you hit it** in [docs/friction-log.md](docs/friction-log.md). Worth up to 10% of the hackathon score, and worth nothing reconstructed from memory in week 5.
- **Never run two agents on the same worktree at once.** Neither tool locks files. Use `git worktree` for parallel work.

---

## Stack — Plan B (decided 2026-09-18)

Rationale in [docs/tech-stack-decision.md](docs/tech-stack-decision.md).

| Layer | Choice |
|---|---|
| Backend + MCP | Python 3.11+, FastAPI, `mcp` SDK ≥2.2 over Streamable HTTP |
| Conversation | Amazon Bedrock (Claude) via the Converse API |
| Database | Postgres + SQLAlchemy + Alembic *(not yet wired — blocked on spec)* |
| Hosting | Container on AWS App Runner, port 8080 |
| Frontend | Next.js + TypeScript *(teammate's lane — not scaffolded)* |

### Backend conventions

- Source lives in `backend/src/macromate/`; tests in `backend/tests/`. Editable install, `pythonpath = ["src"]`.
- `from __future__ import annotations` at the top of every module.
- Ruff, line length 100.
- **The `mcp` SDK is 2.x.** `FastMCP` is now `MCPServer` (`mcp.server.mcpserver`), the client helper is `streamable_http_client`, and result fields are snake_case (`structured_content`). Most tutorials online are v1 and will not work — check `docs/friction-log.md` before trusting an example.
- New MCP tools go in `mcp_server.py` and must delegate all arithmetic to `nutrition.py`. A tool that computes inline violates invariant 2.
- Stateful domain tools (pantry, sessions, meal logs) are **blocked on the Kiro spec**. Do not invent the data model here.

### Running it

```bash
cd backend
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m uvicorn macromate.main:app --port 8080
./.venv/Scripts/python.exe scripts/spike_mcp_handshake.py
```
