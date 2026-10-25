# Pre-compaction snapshot

`PreCompact` cannot inject text into a compaction, so `PreCompact` and `SessionEnd` write a snapshot to
`<data dir>/precompact/<session_id>.md` (`CLAUDE_PLUGIN_DATA` if set): last 5 user messages, last assistant message, latest
TodoWrite list and edited files. `SessionStart` with source `compact` re-injects it (not on `resume`: the history is already restored). With `HH_STARTUP_HANDOFF=1`,
a `startup` session also receives the newest snapshot for the same `cwd` younger than 7 days.
Disable with feature `precompact-snapshot`.

## Just this one

Claude Code: add the three hooks to `~/.claude/settings.json` with an absolute path to your checkout (`SessionStart` does the re-injection). `shared/py/harness_habits/` must sit next to `bin/` (copy the whole `shared/py/` directory if you move the script); the scripts import only that package and the standard library.

```json
{
  "hooks": {
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_precompact.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_precompact.py\" || true",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_sessionend.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_sessionend.py\" || true",
            "timeout": 30
          }
        ]
      }
    ],
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

The `SessionStart` script `claude_sessionstart.py` serves both `size-lint` (startup and clear) and `precompact-snapshot` (compact re-injection), and both are on by default, so this snippet enables size lint too. To keep only precompact-snapshot, write `~/.config/harness-habits/features.json` with the other key off:

```json
{"size-lint": false}
```

Exporting `HH_FEATURE_SIZE_LINT=0` in the shell that launches Claude Code works too.

Codex CLI: add to `~/.codex/hooks.json` (then trust it via `/hooks`):

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/codex_sessionend.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/codex_sessionend.py\" || true",
            "timeout": 30
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/codex_precompact.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/codex_precompact.py\" || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

