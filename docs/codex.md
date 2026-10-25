# Codex CLI

> Doc-verified. Not yet exercised against a live Codex binary. Hooks need trust via `/hooks` after every change.

Install with `python3 -I install.py --codex` (add `--features a,b` to choose features; otherwise
`<config dir>/features.json` or the defaults apply). The installer:

- copies the `codex_*.py` scripts, the `harness_habits` package and `shared/rules/` to `<data dir>/bin`, so the hooks
  keep working when this checkout is moved or deleted;
- merges `codex/hooks.json` into `~/.codex/hooks.json`, replacing `$HH_BIN` with `<data dir>/bin`
  and adding only the entries whose feature is on (`output-guard`, `size-lint`, `precompact-snapshot`).
  Each command is `test -f "<script>" && python3 -I "<script>" || true`, so a missing script exits 0 silently;
- copies the `handoff-note` skill to `~/.agents/skills/handoff-note`;
- prints `codex/config.toml.snippet` (`[features] memories = true`). It never writes `config.toml`.

`--codex --uninstall` removes only the hook entries whose command runs our `codex_*.py` scripts (installed or
from this checkout), those installed scripts, and the skill. Re-running the install is a no-op.

## Hooks

| Event | Script | Feature | Behaviour |
|---|---|---|---|
| PreToolUse (Bash) | `codex_pretooluse.py` | `output-guard` | deny oversized `cat` and `tail -f`; advise; suggest a bounded rewrite |
| SessionStart | `codex_sessionstart.py` | `size-lint` | instruction-file size findings as plain stdout |
| SessionEnd, PreCompact | `codex_sessionend.py`, `codex_precompact.py` | `precompact-snapshot` | handoff note at `~/.codex/handoff/<session_id>.md` |

Codex trusts hooks by hash. After installing or editing, review them with `/hooks`; until then they do not run.

### Rewrites and auto-approval

On Codex, `updatedInput` is only honoured together with `permissionDecision: "allow"`, which auto-approves the
rewritten command. By default a rewrite decision (bare `rg`, `grep`, `find`, `ls -R`) is therefore advisory:
the hook returns `additionalContext` ending with `Suggested: <command>` and lets the call run, so no extra
model turn is spent. Two switches change that:

- `HH_CODEX_REWRITE=1`: `allow` plus `updatedInput.command`, accepting the auto-approval.
- `HH_CODEX_DENY=1`: the stricter earlier behaviour, a deny whose reason ends with `Suggested: <command>`
  (costs one extra turn per rewrite). `HH_CODEX_REWRITE` wins when both are set.

Oversized `cat` and `tail -f` are denied in every mode.

### Handoff notes

The transcript shape of Codex rollouts is not verified. The extractor tries the Claude Code shape first, then
falls back to any `{role, content}` message (top level, `payload` or `message`). An unrecognised file yields a
note with whatever user and assistant text was found. Override the directory with `HH_CODEX_HANDOFF_DIR`.

## Memories

`[features] memories = true` enables Codex's own memories (stored in `~/.codex/memories/`, generated; do not
hand-edit). Toggle per chat with `/memories`.

## Skills

Codex reads skills from `~/.agents/skills` (not `~/.codex/skills`). Invoke with `$handoff-note` or `/skills`.
