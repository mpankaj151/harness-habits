# Codex CLI

> Doc-verified. Not yet exercised against a live Codex binary. Hooks need trust via `/hooks` after every change.

Install with `python3 -I install.py --codex` (add `--features a,b` to choose features; otherwise
`<config dir>/features.json` or the defaults apply). The installer:

- merges `codex/hooks.json` into `~/.codex/hooks.json`, replacing `$HH_ROOT` with this checkout's absolute path
  and adding only the entries whose feature is on (`output-guard`, `size-lint`, `precompact-snapshot`);
- copies the `handoff-note` skill to `~/.agents/skills/handoff-note`;
- prints `codex/config.toml.snippet` (`[features] memories = true`). It never writes `config.toml`.

`--codex --uninstall` removes only the hook entries whose command points at this checkout's `codex_*.py`
scripts, and the skill. Re-running the install is a no-op.

## Hooks

| Event | Script | Feature | Behaviour |
|---|---|---|---|
| PreToolUse (Bash) | `codex_pretooluse.py` | `output-guard` | deny, advise, or suggest a bounded rewrite |
| SessionStart | `codex_sessionstart.py` | `size-lint` | instruction-file size findings as plain stdout |
| SessionEnd, PreCompact | `codex_sessionend.py`, `codex_precompact.py` | `precompact-snapshot` | handoff note at `~/.codex/handoff/<session_id>.md` |

Codex trusts hooks by hash. After installing or editing, review them with `/hooks`; until then they do not run.

### Rewrites and auto-approval

On Codex, `updatedInput` is only honoured together with `permissionDecision: "allow"`, which auto-approves the
rewritten command. By default a rewrite decision is therefore reported as a deny whose reason ends with
`Suggested: <command>`, and the model re-issues the bounded command itself. Setting `HH_CODEX_REWRITE=1`
switches to `allow` plus `updatedInput.command`, accepting the auto-approval.

### Handoff notes

The transcript shape of Codex rollouts is not verified. The extractor tries the Claude Code shape first, then
falls back to any `{role, content}` message (top level, `payload` or `message`). An unrecognised file yields a
note with whatever user and assistant text was found. Override the directory with `HH_CODEX_HANDOFF_DIR`.

## Memories

`[features] memories = true` enables Codex's own memories (stored in `~/.codex/memories/`, generated; do not
hand-edit). Toggle per chat with `/memories`.

## Skills

Codex reads skills from `~/.agents/skills` (not `~/.codex/skills`). Invoke with `$handoff-note` or `/skills`.
