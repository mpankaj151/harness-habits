# Cache-break notices

The prompt cache covers the prefix: `CLAUDE.md`, `.mcp.json`, settings and `.claude/rules/`. After an Edit, Write or MultiEdit
of one of those files (`PostToolUse`), or a `ConfigChange` event, harness-habits adds one factual note per session and file:
the next request re-reads the whole prefix at full input price. A `PostModelSwitch` hook adds a line that the cache is per model.
Markers live under `<data dir>/cachebreak/<session_id>.json` (`CLAUDE_PLUGIN_DATA` if set). Disable with feature `cache-break`.
