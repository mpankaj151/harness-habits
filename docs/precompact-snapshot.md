# Pre-compaction snapshot

## Why

A compaction replaces the conversation with a summary, and details such as your last requests, the todo list and the files you were editing can be lost. The snapshot keeps them on disk and puts them back, so you do not have to re-explain the work.

## What you see

- Claude Code: a file `<data dir>/precompact/<session_id>.md` (`CLAUDE_PLUGIN_DATA` if set) with the last 5 user messages, the last assistant message, the latest TodoWrite list and edited files. After a compaction Claude's context starts with `Snapshot taken before the last compaction of this session:` followed by that file.
- With `HH_STARTUP_HANDOFF=1`, a new session in the same directory also receives `Snapshot from the most recent earlier session in this directory:` (newest snapshot younger than 7 days).
- Codex: the note is written to `~/.codex/handoff/<session_id>.md` (override with `HH_CODEX_HANDOFF_DIR`).

## Setup

### Claude Code

Included in the plugin install (`claude plugin marketplace add mpankaj151/harness-habits`, then `claude plugin install harness-habits@harness-habits`). Nothing else to do; to turn it off see below.

### OpenCode

Not applicable; OpenCode uses [handoff notes](handoff.md) instead.

### Codex CLI

`./install.sh --codex` (feature `precompact-snapshot`; trust the hooks via `/hooks`). Doc-verified only, see [codex.md](codex.md).

## Switch it off

Set `"precompact-snapshot": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_PRECOMPACT_SNAPSHOT=0` in the shell that launches the harness. On Claude Code `CLAUDE_PLUGIN_OPTION_PRECOMPACT_SNAPSHOT=0` works too.

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

## Details / Limits

`PreCompact` cannot inject text into a compaction, so `PreCompact` and `SessionEnd` write a snapshot and `SessionStart` with source `compact` re-injects it (not on `resume`: the history is already restored). The `SessionStart` script is shared with size lint; see the note in "Just this one".
