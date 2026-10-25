# Known issues (v0.1.0)

Found during review and deliberately not fixed in 0.1.0. None loses data or blocks the harness.

## Verification gaps

- Codex CLI: hooks, `hooks.json` merge format and the rollout transcript shape are doc-verified only; never run against a live binary.
- Claude Code: only the PreToolUse guard has been exercised live (`tests/smoke/claude.sh`). The other hooks are unit-tested only.
- `ConfigChange` hook output shape (`hookSpecificOutput.additionalContext`) for cache-break notices is not confirmed in the docs; Claude Code may ignore it.
- The plugin declares no `userConfig`; per-feature switches on Claude Code are env vars and `features.json` only (the manifest schema was not verified).
- CI has never run (nothing pushed); `shellcheck` was not available locally. The committed `opencode/dist` is built on macOS and may differ byte-for-byte from a Linux CI build.
- README install commands for the marketplace flow are unverified end to end (`--plugin-dir` is what the smoke test uses).

## Output guard

- A quoted literal operator (`grep "a|b" f`) is classified as composed, so it is advised instead of rewritten.
- A trailing `# comment` swallows an appended `| head`.
- Combined short flags (`grep -rl`) are not matched by `skip_flags`.
- `shellsplit` loads the rule operators itself instead of requiring them as an argument.
- Codex allow mode (`HH_CODEX_REWRITE=1`) returns `updatedInput` with only `command`, dropping sibling `tool_input` fields.
- A quoted-operator or exotic-quoting command may be advised rather than bounded; the guard errs toward allowing.

## Size lint, snapshot and handoff

- Memory file over both the line and the byte limit yields one finding, not two.
- Snapshot and marker files are written with a plain write, not tmp + rename.
- `plugin_data_dir` lives in `cachebreak.py` and `_snapshot.py` sits in `bin/`; both belong in `paths.py`.
- `read_text` without an encoding or error handler can drop lint output on a non-UTF-8 file.
- `basename("a/")` gives an empty marker name.
- Tolerant (Codex) extraction drops user messages that start with `<`.
- Codex `SessionStart` ignores sources other than `startup`, `clear` and absent (including `resume`); this is undocumented.
- OpenCode size lint reads `~/.config/opencode/AGENTS.md` and ignores `OPENCODE_CONFIG_DIR`.
- OpenCode size-lint and cache-break "seen" sets, and per-session maps in handoff and idle compaction, are never pruned.

## OpenCode runtime

- `file.edited` events carry no session id, so subagent events can steal the attribution; handoff files-edited is approximate.
- A failed summarize has no cooldown or backoff.
- `flush()` does not await a run already in progress.
- `tokens.total: 0` never triggers idle compaction.
- Size lint marks a session done before the subagent check, so a failed `session.get` is not retried.
- Cost logger marks an id as seen before the write, so a failed append is not retried; it dedupes on the first completed update only.
- No `tsconfig` / `tsc --noEmit` type check; option values are not type-validated.
- The parity test does not assert that at least one fixture was found.
- Tool budget: reactive detection still runs when lazy MCP loading is detected (the `skip` flag is dead); the excerpt is the first 120 characters, not the text around the match; state writes are not atomic; `disabled` can list servers that were already disabled; learned ids are not flushed on dispose; pending toasts are not idempotent if `config` runs twice; a non-array `disableFirst` silently turns the heuristic off; the corrupt-file test asserts nothing.
- Tool budget docs: `OPENCODE_EXPERIMENTAL_CODE_MODE` (1.17.14+) swaps MCP tools for a single execute tool and the wording still needs tightening; `overBudget` is sticky until `mcp-tool-budget.json` is deleted; `disableFirst` takes effect on the next run.

## Installer and reports

- `copy_tree` never prunes files removed from the source.
- The launchd plist is rewritten and `launchctl load` re-run on every install (no unload first, no content comparison).
- Non-finite numbers in the status line input raise; an empty `segments` list falls back silently.
- `--codex --uninstall` strips an event list that was empty before install.
- Uninstall crashes if `plugins/harness-habits.js` is a directory, and does not remove a dangling symlink at the target.
- The registry URI path is not escaped; an unreadable registry exits instead of falling back; there is no test for sessions without timestamps.
- `docs/install.md` lacks a note on `--claude --uninstall`.

## Tests and docs

- Several tests are weak: invalid-stdin tests assert only the return code; a tautological deny assertion; the two-file fixture does not assert a line count; `--features` precedence over `features.json` is untested.
- `docs/cost-report.md` starts with a blank line; the SessionStart doc parenthetical omits `HH_STARTUP_HANDOFF` startup re-injection.
- Relative `XDG_*` paths are accepted without complaint; an exception message containing a newline breaks the one-line stderr format.
- The lazy-mcp credit has no link (the colleague's repository is not public).
