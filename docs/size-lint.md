# Size lint

At `SessionStart` (sources `startup` and `clear`) harness-habits reports instruction files over their guideline:
`CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md` in the project and `~/.claude/CLAUDE.md` (over 200 lines), and the
auto-memory `~/.claude/projects/<slug>/memory/MEMORY.md` (over 180 lines or 22528 bytes). `<slug>` is the project path with
every non-alphanumeric character replaced by `-`. A `CLAUDE.md` over 200 lines with no `.claude/rules/` gets a note that
path-scoped rules load only when matching files are touched.

Disable with feature `size-lint`. Run by hand: `python3 -I shared/py/bin/lint_cli.py [--strict] [--cwd PATH]`;
the pre-commit hook id is `harness-habits-size-lint`.

## pre-commit

Use a local hook with an absolute path to `lint_cli.py` (installed plugin path or a checkout):

```yaml
repos:
  - repo: local
    hooks:
      - id: harness-habits-size-lint
        name: harness-habits size lint
        entry: python3 -I /absolute/path/to/harness-habits/shared/py/bin/lint_cli.py --strict
        language: system
        pass_filenames: false
        always_run: true
```

A packaged remote pre-commit hook is future work.

## Just this one

Claude Code: add the `SessionStart` hook to `~/.claude/settings.json` with an absolute path to your checkout. `shared/py/harness_habits/` must sit next to `bin/` (copy the whole `shared/py/` directory if you move the script); the scripts import only that package and the standard library.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_sessionstart.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_sessionstart.py\" || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

The `SessionStart` script `claude_sessionstart.py` serves both `size-lint` (startup and clear) and `precompact-snapshot` (compact and resume re-injection), and both are on by default, so this snippet enables snapshot re-injection too. To keep only size-lint, write `~/.config/harness-habits/features.json` with the other key off:

```json
{"precompact-snapshot": false}
```

Exporting `HH_FEATURE_PRECOMPACT_SNAPSHOT=0` in the shell that launches Claude Code works too.

Codex CLI: add to `~/.codex/hooks.json` (then trust it via `/hooks`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/codex_sessionstart.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/codex_sessionstart.py\" || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

OpenCode: `cp opencode/dist/features/size-lint.js ~/.config/opencode/plugins/` (plugin id `harness-habits-size-lint`).
