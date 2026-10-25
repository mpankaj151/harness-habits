# Cache-break notices

## Why

The model provider caches the start of every request (`CLAUDE.md`, `.mcp.json`, settings, `.claude/rules/`) so repeated turns are cheap. Editing one of those files, or switching model, invalidates the cache and the next request is paid at full input price. A single factual note makes that cost visible instead of surprising.

## What you see

- Claude Code messages are sent to the model as context, not shown on screen; only the OpenCode toast is visible.
- Claude Code, after an Edit, Write or MultiEdit of a prefix file: `<path> is part of the prompt prefix; the next request re-reads the whole prefix at full input price (cache miss).` Once per session and file.
- Claude Code, after a model switch: `Model switched; the prompt cache is per model, so this first turn re-reads the full context at full price.`
- OpenCode toast, after an edit or write of `opencode.json`, `opencode.jsonc`, `AGENTS.md` or `CLAUDE.md`: `<file> changed; it is part of the prompt prefix, so the next turn re-reads the full prefix (cache miss).` Once per session and file.

## Setup

### Claude Code

Included in the plugin install (`claude plugin marketplace add mpankaj151/harness-habits`, then `claude plugin install harness-habits@harness-habits`). Nothing else to do; to turn it off see below.

### OpenCode

`./install.sh --opencode` (feature `cache-break`).

### Codex CLI

Not available.

## Switch it off

Set `"cache-break": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_CACHE_BREAK=0` in the shell that launches the harness. On Claude Code `CLAUDE_PLUGIN_OPTION_CACHE_BREAK=0` works too.

## Just this one

Add both hooks to `~/.claude/settings.json` with an absolute path to your checkout. `shared/py/harness_habits/` must sit next to `bin/` (copy the whole `shared/py/` directory if you move the script); the scripts import only that package and the standard library.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_posttooluse.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_posttooluse.py\" || true",
            "timeout": 10
          }
        ]
      }
    ],
    "PostModelSwitch": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_postmodelswitch.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_postmodelswitch.py\" || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

OpenCode: `cp opencode/dist/features/cache-break.js ~/.config/opencode/plugins/` (plugin id `harness-habits-cache-break`).

## Details / Limits

The prompt cache covers the prefix: `CLAUDE.md`, `.mcp.json`, settings and `.claude/rules/`. After an Edit, Write or MultiEdit
of one of those files (`PostToolUse`) harness-habits adds one factual note per session and file:
the next request re-reads the whole prefix at full input price. A `PostModelSwitch` hook adds a line that the cache is per model.
Markers live under `<data dir>/cachebreak/<session_id>.json` (`CLAUDE_PLUGIN_DATA` if set).

Settings edits made outside the session (the `ConfigChange` event) cannot be reported by a hook, because ConfigChange hooks can only block and have no context channel; only in-session Edit/Write of config files is reported.
