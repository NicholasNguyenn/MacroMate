# Friction Log

Rough edges hit while building MacroMate, recorded as they happen.

**Why this file exists.** The hackathon awards **up to a 10% bonus** for friction logs, assessed by Amazon's review team during Stage 1 downselection. The submission separately *requires* product feedback on every tool, API, and SDK used. Both are close to free if written in the moment, and close to worthless if reconstructed from memory the night before the deadline.

It also feeds the Open Source mini-challenge: friction you hit in Kiro is a candidate PR to [Kiro Crew](https://github.com/kirodotdev), which is Apache-2.0. A fix you already understand because you just tripped over it is the cheapest contribution you will ever write.

**How to use it.** Append an entry whenever something costs you more than ~10 minutes, surprises you, or sends you to the docs twice. One entry per issue, newest first. Do not polish the tone — the raw reaction is the useful part, and it is what reviewers are actually reading for.

Cover every tool you touch: Kiro, Claude Code, the MCP SDK and spec, Bedrock, App Runner, Alexa+ integration, nutrition APIs.

---

## Template

```markdown
### [YYYY-MM-DD] <Tool / SDK> — one-line summary

**Trying to do:**

**What happened:**

**What I expected:**

**Time lost:**

**Workaround:**

**Would fix by:**
```

---

## Entries

<!-- newest first -->

### [2026-09-18] MCP Python SDK — `CallToolResult` field is snake_case while the wire format is camelCase

**Trying to do:** read the structured result of a tool call in a client script.

**What happened:** `result.structuredContent` raised `AttributeError`. The attribute is `structured_content`.

**What I expected:** the MCP wire format uses `structuredContent`, and the SDK's own type names keep camelCase elsewhere (`protocolVersion`, `serverInfo`). The inconsistency is between the JSON field and the Python attribute for the same value.

**Time lost:** ~5 min (the error message suggested the right name, which helped a lot).

**Workaround:** use `structured_content`.

**Would fix by:** either aliasing both, or noting the wire-vs-Python naming convention prominently in the client docs. The helpful `Did you mean:` in the traceback is good design and saved most of the time here.

---

### [2026-09-18] MCP Python SDK — `session_manager` raises if accessed before `streamable_http_app()`

**Trying to do:** wire the session manager's lifespan into a FastAPI app.

**What happened:** `RuntimeError: Session manager can only be accessed after calling streamable_http_app(). The session manager is created lazily to avoid unnecessary initialization.`

**What I expected:** to reference `server.session_manager` while composing the app, in any order.

**Time lost:** ~10 min.

**Workaround:** call `streamable_http_app()` first and hold the result, then reference `session_manager` afterwards. Ordering is now load-bearing and needs a comment to survive refactoring.

**Would fix by:** the error message is genuinely excellent — it names the cause and the fix. The remaining gap is that nothing in the *docs* hints at the ordering constraint, so you only learn it by hitting it.

---

### [2026-09-18] MCP Python SDK — mounting the Starlette app into FastAPI silently skips its lifespan

**Trying to do:** serve the MCP endpoint alongside a REST API in one FastAPI app.

**What happened:** Starlette does not run a mounted sub-app's lifespan. The MCP app's lifespan is where the session manager starts, so a naive `app.mount(...)` produces a server that accepts connections and then fails every MCP request.

**What I expected:** mounting to be self-contained, or to warn.

**Time lost:** ~15 min, and only avoided at runtime because I knew this Starlette behaviour beforehand. Someone who does not would likely lose an hour to a confusing runtime failure with no obvious link to mounting.

**Workaround:** drive `session_manager.run()` from the *parent* app's lifespan.

**Would fix by:** a short "mounting into an existing ASGI app" section in the docs with this exact snippet. This is going to be the single most common integration shape — everyone with an existing API will hit it.

---

### [2026-09-18] MCP Python SDK — v1 → v2 rename breaks essentially every tutorial online

**Trying to do:** stand up a Streamable HTTP MCP server from the documented `FastMCP` API.

**What happened:** `pip install mcp` gives 2.2.0, where `FastMCP` is renamed `MCPServer` (`mcp.server.mcpserver`) and `streamablehttp_client` is renamed `streamable_http_client`. Every blog post, tutorial, and LLM-generated example targets v1 and fails on import.

**What I expected:** the most common published examples to run against a fresh install.

**Time lost:** ~15 min, almost entirely recovered by the error message.

**Workaround:** use the 2.x names, or pin `mcp<2`. The high-level `mcp.Client` in 2.x is notably nicer than the v1 `streamablehttp_client` + `ClientSession` pairing — worth surfacing more prominently, since it is easy to miss.

**Would fix by:** the `ModuleNotFoundError` here is a model of how to do this — it names the old API, the new API, the migration guide URL, *and* the pin to stay on v1. Nothing to fix; this is the standard other SDKs should copy. Worth saying so explicitly in the submission feedback.
