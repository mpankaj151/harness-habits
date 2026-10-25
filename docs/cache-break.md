# Cache-break notices

The prompt cache covers the prefix: `CLAUDE.md`, `.mcp.json`, settings and `.claude/rules/`. After an Edit, Write or MultiEdit
of one of those files (`PostToolUse`) harness-habits adds one factual note per session and file:
the next request re-reads the whole prefix at full input price. A `PostModelSwitch` hook adds a line that the cache is per model.
Markers live under `<data dir>/cachebreak/<session_id>.json` (`CLAUDE_PLUGIN_DATA` if set). Disable with feature `cache-break`.

Settings edits made outside the session (the `ConfigChange` event) cannot be reported by a hook, because ConfigChange hooks can only block and have no context channel; only in-session Edit/Write of config files is reported.

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
            "command": "python3 -I /absolute/path/to/harness-habits/shared/py/bin/claude_posttooluse.py",
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
            "command": "python3 -I /absolute/path/to/harness-habits/shared/py/bin/claude_postmodelswitch.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

OpenCode: `cp opencode/dist/features/cache-break.js ~/.config/opencode/plugins/` (plugin id `harness-habits-cache-break`).
