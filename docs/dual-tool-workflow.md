# Working Agreement — Running Claude Code and Kiro on One Repo

Companion to [tech-stack-decision.md](tech-stack-decision.md) §8, which decides *what* each tool owns. This decides *how* they coexist.

**Short version:** yes, both work on the same repo — they are both just editing files and git. Nothing technical blocks it. Every real failure mode is a coordination failure, and there are five of them.

---

## 1. One source of truth for project instructions

Kiro natively supports **`AGENTS.md`** ([agents.md](https://agents.md/) standard) as an always-included instruction source. It does **not** read `CLAUDE.md`.

So:

```
AGENTS.md          ← canonical. All project standards live here.
CLAUDE.md          ← thin. Imports AGENTS.md, plus Claude-Code-only notes.
```

`CLAUDE.md` should be roughly:

```markdown
@AGENTS.md

## Claude Code specific
<!-- only things that genuinely do not apply to Kiro -->
```

The explicit `@AGENTS.md` import means this works whether or not Claude Code picks up `AGENTS.md` on its own.

**Do not write the standards twice.** Two copies drift within a week, and then the two agents are enforcing different rules on the same codebase — which is worse than having no standards at all, because the damage is invisible until review.

**Check your global steering.** Kiro merges `~/.kiro/steering/` with the project's `.kiro/steering/`, closer scope winning. You already have a `~/.kiro`. Make sure nothing global contradicts the project standards before you start.

---

## 2. The spec is the interface between the tools

This is the part that makes the whole arrangement work rather than just doubling your tool count.

| Step | Tool | Output |
|---|---|---|
| 1. Author spec | Kiro | `.kiro/specs/<feature>/{requirements,design,tasks}.md` |
| 2. Review spec | You | approve before any code exists |
| 3. Implement | Claude Code | code, reading the spec as the contract |
| 4. Spec turns out wrong | Claude Code | writes a note — **does not rewrite the spec** |
| 5. Amend spec | Kiro | updated spec, then back to step 3 |

**Claude Code reads specs; it never edits them.** The moment implementation starts silently diverging from the spec, your `.kiro/specs/` directory stops describing the product — and that directory is the evidence you are citing for the AWS Builder mini-challenge. Drifted specs turn documented integration into theater, and judges read the repo.

Steering files can reference live workspace files with `#[[file:<relative_path>]]`, so a steering file can point at the real MCP tool contract instead of restating it. Use this for anything that would otherwise be copied.

---

## 3. Never run both on the same working tree at once

Neither tool locks files. Concurrent writes to the same file mean one agent's edit silently overwrites the other's.

- **Default: sequential.** One tool active at a time, by phase. For one person driving both, this is almost always right — you cannot meaningfully supervise two agents on one task anyway.
- **For real parallelism: `git worktree`.** Kiro in one worktree, Claude Code in another, each on its own branch, merged by PR. This is the only safe way to have both running simultaneously.

### Hook caveat

Kiro agent hooks fire on file-save events, including saves made by *other* tools. A hook that **mutates** files — e.g. regenerating TypeScript types from Pydantic models — will race Claude Code if both are open.

- Mutating hooks: fine when Kiro is the only tool running. Disable them otherwise.
- **Verification-only hooks** (run tests, lint, typecheck) are safe either way. Prefer these.

---

## 4. Git hygiene — the common advice is wrong for this project

The widely repeated practice is to add `/.kiro/` to `.gitignore` and keep Kiro config local. **Do not do that here.** Two reasons: `.kiro/specs/` is the artifact you cite as documented Kiro usage for AWS Builder, and your teammate needs the shared spec to work in parallel.

```gitignore
# Kiro — commit specs, steering, and hooks; they are project artifacts
.kiro/settings/mcp.json      # may carry credentials
.kiro/cache/
```

Commit a `.kiro/settings/mcp.json.example` with the secrets stripped.

| Path | Commit? | Why |
|---|---|---|
| `.kiro/specs/` | **yes** | mini-challenge evidence; teammate needs it |
| `.kiro/steering/` | **yes** | shared project standards |
| `.kiro/hooks/` | **yes** | reproducible for the teammate |
| `.kiro/settings/mcp.json` | **no** | credentials; ship `.example` instead |

---

## 5. Register MacroMate's own MCP server in both tools

Once the server runs, add it to Kiro (`.kiro/settings/mcp.json`) and Claude Code (`.mcp.json`) and actually use it while building.

This is not just convenience. **"Our MCP server was validated against two independent MCP clients, not only Alexa+"** is a concrete, checkable Tech Implementation claim — and that criterion is judged on effective use of the required protocol. Dogfooding also surfaces spec-compliance bugs early, when they are cheap, instead of during the Alexa+ integration in week 4.

It is also the fastest source of friction-log material, which is worth up to 10%.

---

## 6. Suggested week-1 sequence

1. Write `AGENTS.md` and the thin `CLAUDE.md`. Reconcile against global `~/.kiro/steering/`.
2. Set the `.gitignore` entries above.
3. **Kiro:** spec the MVP cooking flow — data model, the Available / Prepared / Consumed boundary, and the MCP tool contract. This is the handoff's "agree on shared data structures first," and it unblocks your teammate.
4. Review and approve the spec. Commit it.
5. **Claude Code:** spike the two risks that can invalidate the stack — App Runner SSE behavior, and Bedrock Claude model enablement ([tech-stack-decision.md](tech-stack-decision.md) §7, items 1 and 3).
6. Start `docs/friction-log.md` at step 3, not later. Both tools generate entries.

---

## 7. For the submission

Describe the split explicitly in the writeup. "Specs authored in Kiro, implementation in Claude Code, MCP server validated in both" is a clearer and more credible story than an unexplained mixed commit history — and it is the difference between *documented* integration and incidental usage.
