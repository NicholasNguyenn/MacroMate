@AGENTS.md

## Claude Code specific

Everything above applies. These notes cover only what differs for Claude Code.

- **Specs are read-only here.** `.kiro/specs/` is authored in Kiro. Read specs as the contract; never edit them. If implementation reveals a spec is wrong, flag it as `SPEC DRIFT:` in your response and stop rather than working around it — the amendment happens in Kiro.

- **Check Kiro is not active on this worktree** before editing. Neither tool locks files, so concurrent writes clobber each other silently.

- **Kiro agent hooks can fire on your file saves.** If a hook starts mutating files mid-task, disable the hook rather than racing it. Verification-only hooks (test, lint, typecheck) are safe to leave running.
