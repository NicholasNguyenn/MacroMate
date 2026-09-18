# Handoff to Kiro — Spec Phase

**From:** Claude Code session, 2026-09-18
**To:** Kiro (spec authoring)
**Read first:** [../AGENTS.md](../AGENTS.md) · [tech-stack-decision.md](tech-stack-decision.md) · [dual-tool-workflow.md](dual-tool-workflow.md)

You are picking up a repo with a working backend skeleton and no domain model. Your job this phase is the domain model and the MCP tool contract, as a spec — **not** implementation.

---

## 1. Where the project stands

Plan B is decided (see [tech-stack-decision.md](tech-stack-decision.md)): Python FastAPI + self-hosted MCP over Streamable HTTP + Bedrock + Postgres + Next.js, containerized on App Runner. Deadline **2026-10-23, 12:00 PDT** — roughly 5 weeks.

### What exists and is verified working

| Path | What it is | State |
|---|---|---|
| `backend/src/macromate/nutrition.py` | All nutrition arithmetic. Pure functions. | **Done, 9 tests passing.** Do not re-specify. |
| `backend/src/macromate/mcp_server.py` | MCP server + 3 pure tools | Working over the wire |
| `backend/src/macromate/main.py` | FastAPI app, MCP mounted at `/mcp`, lifespan wired | Working |
| `backend/src/macromate/bedrock.py` | Bedrock Converse client | Written, **unverified** — needs model access |
| `backend/src/macromate/config.py` | Env settings | Working |
| `backend/Dockerfile` | App Runner container, port 8080 | Written, not yet deployed |
| `backend/scripts/spike_mcp_handshake.py` | MCP round-trip check, takes a URL | Passing locally |
| `backend/scripts/spike_bedrock.py` | Bedrock access check | **Unrun** — blocked on model enablement |

Verified end to end against a running server:

```
server              : macromate v0.1.0
negotiated protocol : 2026-07-28        <- track floor is 2025-11-25
tools               : calculate_portions, remaining_daily_targets, scale_ingredient
calculate_portions  : 450.0 kcal / 37.5 g per portion
```

### The three pure tools already built

Stateful tools must **compose with** these, never reimplement the math:

- `calculate_portions(total_calories, total_protein_g, portions, estimated)` — batch ÷ N
- `remaining_daily_targets(calorie_target, protein_target_g, consumed_calories, consumed_protein_g, estimated)`
- `scale_ingredient(calories, protein_g, factor, estimated)` — mid-cook correction

`nutrition.py` also provides `Macros` (with a contagious `estimated` flag), `total()`, `split_batch()`, and `remaining_against_targets()`.

### What was deliberately NOT built

Everything stateful: profiles, pantry, equipment, preferences, cooking sessions, recipe batches, portions, meal logs, grocery lists. No database, no SQLAlchemy models, no Alembic migrations. **That is your spec's subject matter.** It was left out on purpose so the spec leads the code rather than documenting it after the fact.

Also not built: the Next.js frontend (teammate's lane).

---

## 2. Your responsibilities

**You own:**

1. The spec layer — `.kiro/specs/<feature>/{requirements.md, design.md, tasks.md}`.
2. The domain data model — entities, relationships, state transitions.
3. The MCP tool contract — names, argument schemas, return shapes, error cases.
4. Agent hooks in `.kiro/hooks/` (verification-only: pytest, ruff. See §6.)
5. Amendments when implementation reports `SPEC DRIFT`.

**You do not own:** implementation, the nutrition module, deployment, the frontend.

**Only you edit `.kiro/specs/`.** Claude Code reads specs as a contract and is instructed to flag `SPEC DRIFT:` and stop rather than silently diverge. When that happens, the fix comes back to you.

Commit `.kiro/specs/`, `.kiro/steering/`, `.kiro/hooks/`. Never commit `.kiro/settings/mcp.json` — it may carry credentials; `.gitignore` already blocks it.

---

## 3. First task — spec the MVP cooking flow

One spec, covering the seven steps the handoff defines as the MVP:

1. Save goals, equipment, and preferences
2. Create a cooking session with ingredients and nutrition information
3. Generate one suitable recipe
4. Correct ingredient quantities during cooking
5. Calculate batch totals and serving sizes
6. Log a portion and update daily totals
7. Save the remaining portions

This is also the demo script, so scope the spec to exactly this path. Weekly planning, grocery reminders, and broader recipe features are explicitly later.

### Entities the spec must define

Profile · Equipment · Preference · PantryItem · CookingSession · SessionIngredient · RecipeBatch · Portion · MealLog · (GroceryList — later phase, model it only if free)

### Modeling problems the spec must actually resolve

These are the parts that will be wrong if nobody decides them deliberately:

1. **Available → Prepared → Consumed transitions.** What decrements what, and when. Cooking a batch must not touch Consumed. Logging a meal must decrement remaining portions. Name the exact transitions and their triggers.

2. **Permanent vs session-scoped state.** "I bought a blender" updates the profile; "I'm cooking at a friend's house" applies to one session only. Same for preferences: a temporary request must override the default for that session *without* mutating the saved profile. This needs a real mechanism, not a convention.

3. **Nutrition provenance.** A quantity can come from a confirmed lookup, a label the user read, or a guess. `nutrition.py` already carries a boolean `estimated` that propagates through arithmetic. **Decide whether a boolean is enough** — if the spec needs to distinguish "label-read" from "brand-matched" from "pure guess", say so and flag it, because that changes the `Macros` type and I would need to amend `nutrition.py`.

4. **Ambiguous product matches.** When a brand lookup returns three candidates, what does the tool return, and how does the conversation resolve it? Invariant 3 says the uncertainty must reach the UI.

5. **Portion accounting and idempotency.** "I ate one" over voice may arrive twice. Decide how repeat/duplicate logging is handled. Voice has no undo button, so also decide how a mis-log is corrected.

6. **Explicit vs inferred preference priority.** Explicit wins. Rejecting one recipe must not permanently mark its ingredients disliked. Model the difference.

7. **Units.** Grams and Celsius are defaults. Decide whether storage is canonical-unit-only with display conversion, or stored per-entry.

### MCP tools the spec must define

Roughly this surface — adjust as the model demands, but name every argument and return shape:

| Area | Tools |
|---|---|
| Profile | `get_profile`, `update_profile` |
| Preferences | `set_preference` (permanent vs session scope) |
| Equipment | `update_equipment` (permanent vs session scope) |
| Pantry | `list_pantry`, `update_pantry` |
| Nutrition lookup | `search_nutrition` (+ ambiguity resolution) |
| Session | `start_cooking_session`, `add_session_ingredient`, `adjust_session_ingredient` |
| Recipe | `suggest_recipe` |
| Batch | `finalize_batch` |
| Logging | `log_meal`, `get_today` |

For each: name, argument schema with types and constraints, return shape, and error cases. This contract is what unblocks the frontend to work in parallel — it is the highest-value thing you produce this week.

---

## 4. Hard constraints the spec must respect

### The deployment constraint that has real design impact

The container runs with `MACROMATE_MCP_STATELESS=true`, because once App Runner scales past one instance, per-session in-process state breaks.

**Consequence: a cooking session cannot live in MCP session memory.** It must be a database entity with an explicit ID, and the tools must accept and return that ID (or derive it from the authenticated user). Please design for this from the start — discovering it later means reworking every session tool.

### The four invariants

Non-negotiable, from AGENTS.md. Every entity and tool must be checkable against them:

1. Available / Prepared / Consumed stay distinct.
2. The LLM never does arithmetic — tools compute, the model chooses.
3. Uncertainty stays visible all the way to the UI.
4. Explicit preferences beat inferred ones.

### Alignment with what exists

Your tool return shapes should match the style already in `mcp_server.py` (flat dicts with explicit keys, `estimated` carried through). Read that file before designing the contract.

---

## 5. Definition of done for this spec

- [ ] `requirements.md` covers all seven MVP steps, in EARS notation
- [ ] `design.md` defines every entity, its fields, and the Available/Prepared/Consumed transitions
- [ ] Permanent vs session-scoped mechanism is specified, not implied
- [ ] Nutrition provenance model decided; if richer than a boolean, `nutrition.py` change is flagged
- [ ] Every MCP tool has name, argument schema, return shape, error cases
- [ ] Session identity works under stateless MCP
- [ ] `tasks.md` sequences the work so backend and frontend can proceed in parallel
- [ ] Reviewed by Nicholas and committed

---

## 6. What not to do

- **Do not write implementation code.** The spec leads. If a task is trivial enough to implement inline, it still goes in `tasks.md`.
- **Do not re-specify `nutrition.py` or the three pure tools.** They are built and tested. Compose with them.
- **Do not duplicate AGENTS.md into `.kiro/steering/`.** Kiro reads `AGENTS.md` natively as always-included. A second copy drifts, and then the two tools enforce different rules invisibly. Steering files should cover only Kiro-specific workflow, and should use `#[[file:<path>]]` to reference live files rather than restating them.
- **Do not use mutating agent hooks while Claude Code may be running.** Hooks fire on file saves from any tool, so a type-regenerating hook will race it. Verification-only hooks (pytest, ruff) are safe.
- **Do not edit `backend/` while a Claude Code session is active on this worktree.** Neither tool locks files; concurrent writes clobber silently. Use `git worktree` if you want genuine parallelism.
- **Do not trust MCP examples found online.** The SDK is 2.x: `FastMCP` → `MCPServer`, `streamablehttp_client` → `streamable_http_client`, `structuredContent` → `structured_content`. Essentially every tutorial and generated snippet targets v1. See [friction-log.md](friction-log.md).

---

## 7. Open decisions that need a human, not an agent

Blocking or near-blocking. Nicholas should resolve these in week 1:

| # | Decision | Why it matters now | Owner |
|---|---|---|---|
| 1 | **Bedrock model access** | Per-account, per-region enablement with a real wait. Only risk with an external queue. `spike_bedrock.py` verifies it in one command once granted. | Nicholas, **today** |
| 2 | **Auth model** | Gates the shared-account requirement between Alexa+ and web, and determines whether tools take a user ID or derive one. The spec cannot finalize the tool contract without this. | Nicholas |
| 3 | **How Alexa+ discovers/authenticates a self-hosted MCP server** | Devpost resources never specify hosting, registration, or auth. Ask at office hours or in the Amazon Developer forum. Unknown for every plan equally — but do not find out in week 4. | Nicholas, week 1 |
| 4 | **Postgres host** — Neon vs RDS | Neon is faster to start; RDS tightens the AWS story for the AWS Builder mini-challenge. | Nicholas |
| 5 | **Nutrition data source** | Recommended: USDA FoodData Central (whole foods, free API key) + Open Food Facts (branded/barcode). Needs an API key request. | Either |
| 6 | **Frontend ownership confirmed?** | The work split assumes a teammate takes Next.js. If not, scope must shrink. | Nicholas |

---

## 8. Handback protocol

```
Kiro: author spec  →  Nicholas: review + commit  →  Claude Code: implement
                              ↑                              │
                              └──────── SPEC DRIFT ──────────┘
```

When implementation reports `SPEC DRIFT:`, amend the spec in Kiro and re-commit before implementation continues. Do not let code and spec diverge — `.kiro/specs/` is cited as documented Kiro usage for the AWS Builder mini-challenge, and judges read the repo. A spec that no longer describes the code turns that evidence into fiction.

**Log friction as you go** in [friction-log.md](friction-log.md). Worth up to 10% of the hackathon score, separately required as product feedback on every tool used, and — since Kiro Crew is Apache-2.0 — each entry is a candidate PR that would satisfy the Open Source mini-challenge. Four entries from the backend session are already there as examples of the level of detail worth capturing.
