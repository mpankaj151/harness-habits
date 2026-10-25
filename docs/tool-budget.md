# Tool budget guard (OpenCode, opt-in)

Feature key `tool-budget` (default off). OpenAI-compatible endpoints reject requests that carry more than 128
tool definitions, and every connected MCP server adds its tools to each request.

## Limitation

Per-tool counting is not available to a plugin in OpenCode 1.18.15. `client.tool.ids()` and `client.tool.list()`
return only built-in tools, and no HTTP route or SDK call exposes the tool lists of MCP servers. The guard
therefore cannot count tools up front and relies on the three mechanisms below.

## Mechanisms

1. **Server-count heuristic.** At startup the `config` hook counts enabled entries in `mcp`. When the count is above
   `maxServers` (default 8) and the provider in `model` (the part before `/`) matches `providerPattern`
   (default `openai|azure`, case-insensitive), a one-time toast reports it. The heuristic is skipped when lazy
   loading is detected (a plugin spec containing `lazy-mcp`, or every `mcp` entry disabled).
2. **Reactive detection.** On `session.error` whose message (or response body) matches a tool-limit pattern such as
   `array too long`, `maximum length 128` or `too many tools`, the guard toasts once per run and records
   `overBudget: true` in `<data dir>/mcp-tool-budget.json`.
3. **Next-run disabling.** When the file says `overBudget` is true, servers named in `disableFirst` that are present in
   `mcp` are set to `enabled: false` for that run, and a toast names them.

The state file also lists MCP-looking tool ids seen in `tool.execute.before` (ids containing `_` that are not
built-ins). This is for reporting only and never gates anything.

## Options

In `~/.config/harness-habits/opencode.json`:

```json
{ "toolBudget": { "maxServers": 8, "providerPattern": "openai|azure", "disableFirst": ["big-server"] } }
```

`overBudget` is sticky until `<data dir>/mcp-tool-budget.json` is deleted. `disableFirst` takes effect on the next run.

## Alternatives

- Lazy MCP loading: a colleague's lazy-mcp plugin, documented separately in `~/knowledge/opencode-lazy-mcp-tutorial`.
  No code from it is used here.
- `OPENCODE_EXPERIMENTAL_CODE_MODE`: a real flag (OpenCode 1.17.14+, undocumented) that removes MCP tool definitions from the request and exposes a single `execute` tool with a catalog.
