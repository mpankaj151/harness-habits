# Tool budget guard (OpenCode, opt-in)

## Why

Every connected MCP server adds its tool definitions to each request, and OpenAI-compatible endpoints reject requests that carry more than 128 tool definitions. The guard tells you early, and can switch heavy servers off on the next run, instead of leaving you with a failing request.

## What you see

Toasts, shown in OpenCode:

- At startup, when more than `maxServers` MCP servers are enabled for a matching provider: `<n> MCP servers enabled for <provider>. OpenAI-compatible endpoints reject requests with more than 128 tool definitions. Fewer servers per project or lazy loading keeps requests under the cap.`
- When the provider rejects a request for too many tools: `The provider rejected the request because too many tools were attached (<excerpt>). Disable MCP servers for this project or enable lazy loading.`
- On the next run, if servers were turned off: `A previous run hit the provider tool limit. MCP servers disabled for this run: <names>.`
- State file: `<data dir>/mcp-tool-budget.json`.

## Setup

### Claude Code

Not applicable. For project-level MCP sets see [mcp-sets.md](mcp-sets.md).

### OpenCode

`./install.sh --opencode`, then turn the feature on (it is off by default): set `"tool-budget": true` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_TOOL_BUDGET=1`, or use `"features": {"tool-budget": true}` in `~/.config/harness-habits/opencode.json`. (`--features` would switch every unlisted feature off, so list all the features you want.)

### Codex CLI

Not available.

## Switch it off

Feature key: `tool-budget` (default off). Leave it off, or set `"tool-budget": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_TOOL_BUDGET=0`.

## Just this one

OpenCode: each feature has its own dependency-free bundle with plugin id `harness-habits-tool-budget`. Copy it without the all-in-one plugin:

```sh
cp opencode/dist/features/tool-budget.js ~/.config/opencode/plugins/
```

The feature is off by default; enable it with `"features": {"tool-budget": true}` in the same file. Options come from `~/.config/harness-habits/opencode.json`: `toolBudget.maxServers`, `toolBudget.providerPattern`, `toolBudget.disableFirst`. Do not install it together with `harness-habits.js`, which already contains the feature.

## Details / Limits

### Limitation

Per-tool counting is not available to a plugin in OpenCode 1.18.15. `client.tool.ids()` and `client.tool.list()`
return only built-in tools, and no HTTP route or SDK call exposes the tool lists of MCP servers. The guard
therefore cannot count tools up front and relies on the three mechanisms below.

### Mechanisms

1. **Server-count heuristic.** At startup the `config` hook counts enabled entries in `mcp`. When the count is above
   `maxServers` (default 8) and the provider in `model` (the part before `/`) matches `providerPattern`
   (default `openai|azure`, case-insensitive), a one-time toast reports it. The heuristic is skipped when lazy
   loading is detected (a plugin spec containing `lazy-mcp`, or every `mcp` entry disabled).
2. **Reactive detection.** On `session.error` whose message (or response body) matches a tool-limit pattern (`array too long`,
   or `128` near `tool`; only the first 4000 characters are scanned, and other tool-related errors such as a
   function-name length limit do not count), the guard toasts once per run and records
   `overBudget: true` in `<data dir>/mcp-tool-budget.json`.
3. **Next-run disabling.** When the file says `overBudget` is true and the configured model's provider matches `providerPattern`, servers named in `disableFirst` that are present in
   `mcp` are set to `enabled: false` for that run, and a toast names them.

The state file also lists MCP-looking tool ids seen in `tool.execute.before` (ids containing `_` that are not
built-ins). This is for reporting only and never gates anything.

### Options

In `~/.config/harness-habits/opencode.json`:

```json
{ "toolBudget": { "maxServers": 8, "providerPattern": "openai|azure", "disableFirst": ["big-server"] } }
```

`overBudget` is sticky until `<data dir>/mcp-tool-budget.json` is deleted. `disableFirst` takes effect on the next run.

### Alternatives

- Lazy MCP loading: a colleague's lazy-mcp plugin, covered by the author's lazy-mcp tutorial (not yet public).
  No code from it is used here.
- `OPENCODE_EXPERIMENTAL_CODE_MODE`: a real flag (OpenCode 1.17.14+, undocumented) that removes MCP tool definitions from the request and exposes a single `execute` tool with a catalog.
