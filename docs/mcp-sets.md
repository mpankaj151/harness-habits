# MCP sets

Every MCP server adds its tool definitions to each request. Keeping the set small per project keeps the
prompt prefix small. The files in `templates/mcp-sets/` are minimal examples to copy and edit; nothing
installs them.

| Tool | Template | Where it goes | Mechanism |
|---|---|---|---|
| Claude Code | `claude/.mcp.json`, `claude/settings.json` | project root `.mcp.json`; `.claude/settings.json` | `enableAllProjectMcpServers: false` plus an `enabledMcpjsonServers` allow-list |
| OpenCode | `opencode/opencode.json` | project `opencode.json` | per-server `enabled: true/false` |
| lazy-mcp | `lazy-mcp/lazy-mcp.json` | the plugin's config | `{"only": [...]}` lists the servers exposed up front; JSON has no comments, so the meaning is stated here |

The server names (`github`, `playwright`) are placeholders. OpenCode's tool-budget guard
(`docs/tool-budget.md`) is the feature that notices when a provider rejects a request for too many tools.
