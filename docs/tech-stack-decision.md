# MacroMate — Tech Stack Decision

Ranked stack options for the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/).

**Status:** ✅ **DECIDED — Plan B**, 2026-09-18. Backend skeleton and risk spikes landed; see [../backend/README.md](../backend/README.md).
**Deadline:** 2026-10-23, 12:00 PDT — **5 weeks**

---

## 1. Constraints we are optimizing against

### Hackathon (Alexa+ track)

| Item | Detail |
|---|---|
| Required tech | Working Agent Skill **or** self-hosted MCP server, spec **2025-11-25+**, over **Streamable HTTP**. A simulated Alexa+ web experience is an accepted fallback. |
| Repo proof | Must demonstrate *runtime* use — imported and called in code, or loaded MCP/agent config. |
| Judging | 4 criteria, **equally weighted**: Tech Implementation · Design · Potential Impact · Quality of Idea. |
| Friction logs | Up to **+10% bonus**. Assessed in Stage 1 downselect. |
| Novelty | Project must be new, or significantly updated during the submission window. Our repo is new — fine. |
| Team size | No maximum. |

**Prizes in reach:** Alexa+ 1st = $25,000 + $15K AWS credits. Mini-challenges stack on top:

- **AWS Builder** ($5,000 + $5K credits) — needs AWS services with *documented integrations* (Bedrock, AgentCore, Strands SDK, SageMaker…). **Kiro qualifies on its own as a development tool**, with no runtime AWS service required.
- **Open Source** ($5,000 + $5K credits) — requires a **new, additional** open-source project or contribution *alongside* the main submission. Publishing MacroMate itself does **not** satisfy this. Overlaps Hacktoberfest 2026.

### The 25% trap

Tech Implementation is one quarter of the score. Design, Potential Impact, and Quality of Idea are the other three quarters, and all three are judged on the **finished experience**. A complete, polished Plan C submission outscores a half-built Plan A submission. Weight "ease of implementation" accordingly — it is not a comfort metric here, it is a scoring metric.

### Resume gaps (from CV review)

Present and well-evidenced: Python, ML/CV (PyTorch, OpenCV, MediaPipe), robotics/ROS, pandas/SQL analysis, React (Dell dashboard), FastAPI, LLM *evaluation* (Scale AI), Llama fine-tuning.

Genuine gaps this project can close, highest leverage first:

1. **Building agentic systems, not evaluating them.** Scale AI is evaluation work; the Agentic AI coursework is coursework. Authoring an MCP server with real tool schemas is the 2026 hiring signal for "builds agent systems."
2. **AWS with evidence.** Listed under Infrastructure & Tools, but no project on the CV demonstrates a deployed AWS service. Interviewers probe this exact kind of line.
3. **Relational data modeling + migrations.** SQL and MongoDB appear; no schema-design story does. Available / Prepared / Consumed is a genuinely interesting modeling problem to be able to talk through.
4. **TypeScript.** Absent entirely. The most common second language requirement for new-grad SWE roles after Python.
5. **Production deployment, CI/CD, testing.** Nothing on the CV shows shipping to real users behind a pipeline.
6. **Auth and multi-user state.** None.

The CV is **breadth-rich and backend-depth-poor**. Another ML component adds nothing; a real backend does. This has a direct staffing consequence — see §5.

---

## 2. The candidate plans

All five satisfy the Alexa+ track requirement. They differ in what else they buy.

### Plan A — AWS Agentic (maximum ceiling)

Python FastAPI + official `mcp` SDK over Streamable HTTP · **Strands Agents SDK** + **Bedrock (Claude)** for the conversational layer · Postgres on RDS/Aurora Serverless v2 with SQLAlchemy + Alembic · containerized on **ECS Fargate** behind an ALB · Next.js TypeScript frontend on **Amplify Hosting** · **AWS CDK (TypeScript)** for IaC · Kiro as the dev tool.

### Plan B — Pragmatic Hybrid ★ recommended

Python FastAPI + official `mcp` SDK over Streamable HTTP · **Bedrock (Claude)** via `boto3` · Postgres (Neon free tier, or RDS) with SQLAlchemy + Alembic · deployed as a container on **AWS App Runner** · Next.js TypeScript frontend on **Amplify** (Vercel as escape hatch) · Kiro as dev tool · MCP server extracted to a standalone OSS repo.

Plan B is Plan A with the infrastructure yak-shaving removed. Every Plan A component is reachable from it as a stretch upgrade without a rewrite.

### Plan C — All TypeScript on Vercel (fastest)

Next.js + TypeScript, single codebase · MCP server as a route handler at `/api/mcp` via `@modelcontextprotocol/sdk` · Prisma + Neon Postgres · Anthropic API (or Bedrock via SDK) · deployed on Vercel · Kiro as dev tool for AWS Builder floor eligibility.

### Plan D — Full Serverless AWS

Lambda + API Gateway / Function URLs · DynamoDB · CDK · Bedrock · Next.js on Amplify.

### Plan E — Simulated Alexa+ only

Next.js web app with a chat UI driving an agent loop in-process. No self-hosted MCP server. Explicitly an accepted route.

---

## 3. Scoring

Scored 1–10 per category. Ease is "probability this is genuinely finished and demo-ready by Oct 23 with two part-time people."

| Plan | 1. Hackathon | 2. Resume | 3. Ease | Equal-weight |
|---|---|---|---|---|
| **B — Pragmatic Hybrid** | **9.0** | **8.5** | **7.5** | **8.3** ★ |
| A — AWS Agentic | 9.5 | 10.0 | 5.0 | 8.2 |
| C — All TypeScript | 7.5 | 6.5 | 9.5 | 7.8 |
| D — Full Serverless | 7.0 | 9.0 | 4.0 | 6.7 |
| E — Simulated only | 5.0 | 4.5 | 9.5 | 6.3 |

### Sensitivity — the ranking is not weight-stable

| If you weight… | Winner | Runner-up |
|---|---|---|
| Equal (33/33/33) | **B** (8.3) | A (8.2) |
| Win-first (50/25/25) | **A** (8.6) | B (8.5) |
| Career-first (25/50/25) | **A** (8.6) | B (8.6) |
| Ship-safe (25/25/50) | **B** (8.1) | C (8.4) → **C** |

A and B are within noise of each other on every weighting; the real decision is **A/B vs C**, and that is a bet on execution bandwidth. Plan D and E are dominated — D costs more than A in effort for less hackathon value, E is the fallback if the semester goes sideways.

### Why B over A

Identical architecture, different hosting. ECS Fargate + ALB + CDK is roughly a week of infrastructure work for a demo that will serve approximately four requests. App Runner takes a Dockerfile. That week buys more in Design and Impact score than it does in Tech Implementation, and Plan A's resume advantage is recoverable afterward — migrating App Runner → Fargate + CDK in November, with the deadline gone, is a clean weekend and still lands on the CV.

### Why B over C

Three reasons, in order:

1. **Resume.** Plan C's AWS footprint is Kiro, a dev tool. It closes the TypeScript gap and leaves gaps 1–3 and 5 open. Plan B closes 1, 2, 3, and 5, and partially 4.
2. **Tech Implementation score.** "Self-hosted MCP server on AWS, Bedrock-backed, deterministic nutrition engine" is a stronger 25% than "Next.js API route."
3. **AWS Builder competitiveness.** Kiro-only meets the bar for *eligibility*. Documented Bedrock integration makes you a contender for the actual $5,000.

Plan C's counter-argument is real and should not be dismissed: it is the only plan where the Oct 23 demo is close to guaranteed.

---

## 4. Recommendation — Plan B, with staged upgrades

**Core (must ship):** FastAPI + `mcp` SDK Streamable HTTP · Bedrock Claude · Postgres + Alembic · App Runner · Next.js TS frontend · in-app timers · simulated Alexa+ chat panel as demo fallback.

**Stretch, in priority order:** extract `macromate-mcp` as a standalone OSS repo (Open Source mini-challenge) → Strands Agents SDK for the agent loop → CDK + Fargate migration → real Alexa+ device integration.

### Three free wins, do these in week 1

1. **Friction log from day one.** Up to +10%, and it is the single highest return-per-hour item in the entire competition. One markdown file, appended to as you hit rough edges in MCP, Bedrock, and App Runner. You will hit them regardless — the only question is whether you wrote them down. Start `docs/friction-log.md` before writing application code.
2. **Extract the MCP server as a separate public repo.** A standalone, reusable `macromate-mcp` package is a legitimate new open-source project, satisfies the Open Source mini-challenge (which the main repo does *not*), and reads well on a CV as "authored an open-source MCP server." Costs almost nothing if planned from the start; costs a refactor if bolted on in week 5.
3. **Use Kiro for a real slice of the build.** Already installed. Qualifies for AWS Builder with zero runtime dependency, as insurance in case the Bedrock integration slips — and it feeds the friction log and the Open Source entry. See §8 for the split.

### Positioning for the 75% that is not Tech Implementation

- **Quality of Idea** — the hook is mid-cook correction by voice: *"actually, I used half as much rice."* Lead the demo video with it. Nicholas's conversational-robotics background (turn-taking from diarized multi-party transcripts, Living with Robots Lab) is a real and defensible edge to state in the writeup — it is why this team is credible on voice interaction specifically.
- **Potential Impact** — macro tracking is crowded. The differentiator is the **Available / Prepared / Consumed** separation and batch→portion math. Cooking a batch is not eating it; no mainstream tracker models this correctly.
- **Tech Implementation** — say explicitly that the **LLM never does arithmetic**. It interprets and converses; application code computes nutrition from confirmed quantities; uncertain data stays visibly uncertain. That is a strong, concrete claim and it is also just correct engineering.
- **Design** — four screens, finished, mobile-first. Three polished screens beat six rough ones.

---

## 5. Work split

The handoff proposes one person on backend/nutrition/MCP and one on web/conversational/demo. **Nicholas should take backend + MCP + AWS.**

That is where every significant CV gap lives. The frontend half is the half he already has evidence for — the Dell React dashboard with an LLM chat interface covers substantially the same ground. Taking the frontend again produces a great hackathon and a CV that looks the same as it does today.

To avoid losing the TypeScript gap entirely: write the **shared types and any IaC in TypeScript**, and own the MCP tool-schema contract. That keeps real TS in the commit history on the backend side.

Agree on shared data structures and MCP tool signatures **first**, per the handoff, so both halves proceed in parallel.

---

## 6. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | Nutrition data source | USDA FoodData Central (free API key, whole foods) + Open Food Facts (branded/barcode, open data). Both free, neither needs a contract. |
| 2 | Auth model | MCP spec 2025-11-25 includes OAuth. For a demo, a pairing code + bearer token is likely sufficient. Decide in week 1 — it gates the shared-account requirement between Alexa+ and web. |
| 3 | Frontend host | Amplify for an airtight all-AWS story; Vercel if Amplify fights us. Either way, log the friction. |
| 4 | Postgres host | Neon free tier for speed; RDS if we want the AWS story tighter. |

## 7. Risks to retire in week 1

These are unverified assumptions, not facts. Spike each before committing a week of work to it.

1. **SSE / streaming behavior on App Runner.** ⚠️ **Half-retired.** The MCP server works end to end locally — handshake, tool listing, and a round-trip calculation all pass via `backend/scripts/spike_mcp_handshake.py`. **The App Runner half is still open:** run that same script against the deployed URL before building on it. *If it buffers: ECS Fargate + ALB.* Still the highest-risk item in Plan B.

   Two deployment constraints surfaced while building the spike, both now handled in code: `MACROMATE_ALLOWED_HOSTS` must include the App Runner domain or DNS-rebinding protection 400s every request, and `MACROMATE_MCP_STATELESS=true` is required once App Runner scales past one instance, because session state lives in process.

   Also confirmed: the `mcp` Python SDK negotiates protocol **2026-07-28**, comfortably clear of the track's 2025-11-25 floor.
2. **How Alexa+ actually discovers and authenticates against a self-hosted MCP server.** The Devpost resources do not spell out hosting, registration, or auth requirements. Ask in the Amazon Developer forum or at office hours in week 1 — the answer may constrain plans 1–4 equally, but we should not find out in week 4.
3. **Bedrock model access.** ⏳ **Open — needs a human.** Claude access on Bedrock requires per-account, per-region model enablement and is not instant. `backend/scripts/spike_bedrock.py` checks it in one command; the enablement itself has to be requested in the Bedrock console. **Do this today** — it is the only risk here with an external wait time.
4. **Strands Agents SDK / AgentCore maturity.** Stretch-tier only. Do not put either on the critical path until someone has run a hello-world.

---

## 8. Dev tooling — Claude Code vs Kiro

**Do not switch wholesale. Split by task type.**

The AWS Builder rule requires Kiro to be *used* during the hackathon. It says nothing about exclusivity. Eligibility is binary, so going 100% Kiro instead of ~30% Kiro buys zero additional points, while switching a primary workflow mid-sprint costs days we do not have. But "documented integrations" means judges read a writeup — token usage is not credible. Kiro needs a real, nameable slice.

Note also that Kiro routes reasoning-heavy work to **Claude Sonnet** and code generation to **Amazon Nova**, both through Bedrock. "Switching off Claude" is largely a question of interface and routing, not of model.

### The split

| Surface | Tool | Why |
|---|---|---|
| Spec layer — `requirements.md` / `design.md` / `tasks.md`, shared data model, MCP tool contract | **Kiro** | Spec-driven flow (EARS notation) maps exactly onto the handoff's "agree on shared data structures and tool inputs first." Produces committed artifacts in `.kiro/specs/` that are directly citable as documented Kiro integration. |
| Agent hooks — regenerate shared TS types from Pydantic models on save; run nutrition-math tests on save | **Kiro** | Cheap, genuinely useful, and concrete evidence of feature depth rather than surface use. |
| Iterative build, multi-file refactors, debugging | **Claude Code** | The App Runner/SSE spike, Bedrock wiring, and MCP handshake debugging are long feedback loops. |
| Project standards | **`.kiro/` steering files** | Shared across IDE, CLI, Web, and Mobile. Both tools read them, so they do not fight each other. |

### Why this matters more than AWS Builder eligibility

Kiro Crew is **Apache-2.0 open source** (released 2026-08-04). That makes one workflow feed three separate scoring surfaces:

> Use Kiro → hit a rough edge → log it (**+10% friction bonus**, and the submission separately *requires* product feedback on all tools used) → fix it → **PR to Kiro Crew** (Open Source mini-challenge: a contribution to an existing public repo, on the sponsor's own project, during Hacktoberfest; PRs do not need to be merged).

That is a materially stronger Open Source entry than a self-extracted package. **Keep the `macromate-mcp` extraction as the guaranteed fallback** — a Kiro Crew PR depends on finding a real issue, which we cannot schedule. Submit whichever lands.

### The honest case for switching fully

Not chosen, but real: unambiguous credibility on Kiro use; spec-driven discipline that a 5-week two-person sprint benefits from; one tool means one context and no split-brain; and Kiro's credit tiers may be cheaper than running both. If the spec phase in week 1 goes unusually well, revisiting this is reasonable.

**Cost note:** Kiro is credit-based (free tier through $200/month). Running both tools has a real cost — check the free tier covers the spec phase before committing.
