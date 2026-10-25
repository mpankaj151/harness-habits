# OpenCode 1.18.15 plugin API facts (verified from source and SDK d.ts, 2026-10-25)

Type definitions: `@opencode-ai/plugin@1.18.15` `dist/index.d.ts` (a copy is installed at
`~/knowledge/opencode-lazy-mcp-tutorial/sandbox/node_modules/@opencode-ai/plugin/`), SDK v1 client at
`.../node_modules/@opencode-ai/sdk/dist/gen/{sdk.gen.d.ts,types.gen.d.ts}`.

## Module shape
```ts
const server = async (input: PluginInput, options?: Record<string, unknown>) => ({ ...hooks })
export default { id: "harness-habits", server }   // nothing else exported from a file plugin
```
`PluginInput`: `{ client, project: {id, worktree, vcsDir?, vcs?}, directory, worktree, serverUrl, $ /* Bun shell */, experimental_workspace? }`. There is no `app`. One plugin instance per directory, so closures give per-project state.

## Hooks (all optional, run in load order, hooks mutate `output` in place)
| Hook | Signature |
|---|---|
| `config` | `(cfg: Config) => Promise<void>` — merged config object, mutations persist (bootstrap runs plugins before all other services). No directory param. `cfg.mcp[name].enabled`, `cfg.model` ("provider/model"), `cfg.plugin` (array), `cfg.provider?.[p]?.models?.[m]?.limit?.context`. |
| `event` | `({event: {type, properties}}) => Promise<void>` — fire-and-forget, NOT awaited, errors uncaught → always wrap in try/catch. Only this directory's events. |
| `tool.execute.before` | `({tool, sessionID, callID}, {args}) => Promise<void>` — mutate `output.args.x` in place (reassigning `output.args` is ignored); `throw new Error(msg)` blocks the call and the model sees `msg`. Shell tool id is `"bash"`, args `{command, timeout?, workdir?}`. Runs before the permission prompt and before schema validation. User-typed `!cmd` does NOT trigger it. |
| `tool.execute.after` | `({tool, sessionID, callID, args}, {title, output, metadata}) => Promise<void>` |
| `experimental.chat.system.transform` | `({sessionID?, model}, {system: string[]}) => Promise<void>` — push strings to append to the system prompt (every request). |
| `experimental.session.compacting` | `({sessionID}, {context: string[], prompt?}) => Promise<void>` — push extra context into the compaction prompt. |
| `experimental.chat.messages.transform` | `({}, {messages}) ` |
| `chat.message`, `chat.params`, `chat.headers`, `shell.env`, `tool.definition` (built-in/plugin tools only, not MCP), `tool` (custom tools), `dispose` (`() => Promise<void>`, instance shutdown), `experimental.compaction.autocontinue` |
| `permission.ask` | DECLARED BUT NEVER CALLED in 1.18.15. Do not use. |

## Events seen by `event`
`session.created|updated|deleted|status|idle|compacted|error|diff`, `message.updated|removed`, `message.part.updated|removed|delta`, `permission.asked|replied`, `todo.updated`, `file.edited`, `file.watcher.updated`, `mcp.tools.changed`, `command.executed`, `tui.toast.show`, `server.instance.disposed`, `global.disposed`.
- `session.idle` → `{sessionID}`. Fires EVERY time status becomes idle: every turn, every subagent (child) session, and after a compaction run. Loop guard mandatory.
- `message.updated` → `{sessionID, info}`. Assistant `info`: `{id, role:"assistant", sessionID, providerID, modelID, agent, mode, summary?: boolean, cost: number, tokens: {total?, input, output, reasoning, cache:{read, write}}, time:{created, completed?}, error?, finish?}`. `cost` ACCUMULATES across steps within the message; `tokens` is REPLACED by the last step's usage (≈ current context size). Final update sets `time.completed`.
- `message.part.updated` with `part.type === "step-finish"` carries per-step `{cost, tokens}`.
- `todo.updated` → `{sessionID, todos: [{content, status, priority?, id?}]}` (check `types.gen.d.ts` for exact fields).
- `file.edited` → `{file}` (no sessionID).
- `session.compacted` → `{sessionID}` (only on success).
There are NO `tool.execute.*` events (those are hooks).

## SDK client (v1)
- `client.session.get({path:{id}})` → `Session {id, parentID?, title, directory, time:{created, updated, compacting?}, ...}`
- `client.session.messages({path:{id}, query:{limit?}})` → `Array<{info: Message, parts: Part[]}>` (parts: `{type:"text", text}` etc.)
- `client.session.summarize({path:{id}, body:{providerID, modelID}})` → `boolean`. Server calls `compaction.create({auto:false})` then waits for the loop; with `auto` false no synthetic "continue" turn is added. The summary assistant message has `summary: true`. It ends with another `session.idle`.
- `client.session.prompt({path:{id}, body:{parts, model?, agent?, noReply?, system?}})`, `client.session.list()`, `client.session.children({path:{id}})`, `client.session.status()`.
- `client.tui.showToast({body:{title?, message, variant:"info"|"success"|"warning"|"error", duration?}})`
- `client.app.log({body:{service, level:"debug"|"info"|"warn"|"error", message, extra?}})` → appears in `--print-logs` output as `service=<service> ... message=<message>`.
- `client.tool.ids()` → string[] of built-in + plugin + custom tool ids (no MCP in some builds; verify live). `client.mcp.status()` → per-server status.
- Message info also has `info.model`-like fields; for compaction use the last assistant message's `providerID`/`modelID`.

## Compaction config (`opencode.json`)
`compaction.auto` (true), `compaction.prune` (FALSE by default), `compaction.tail_turns` (2), `compaction.preserve_recent_tokens`, `compaction.reserved`. No percentage threshold exists; auto compaction fires only at overflow (`tokens ≥ context - reserved`). Env `OPENCODE_DISABLE_AUTOCOMPACT`, `OPENCODE_DISABLE_PRUNE`.

## Installing plugins
- File plugins: flat glob `{plugin,plugins}/*.{ts,js}` (no subfolders, no `.mjs`) in every config dir: `~/.config/opencode`, each `.opencode/` from cwd up to the worktree, `~/.opencode`, `$OPENCODE_CONFIG_DIR`. A file plugin's default export MUST have `id`. Never export non-function constants from a file plugin (legacy loader throws). Imports resolve from that config dir's `node_modules`, so a zero-import bundle is the safest file plugin.
- npm plugins: config `"plugin": ["pkg@1.2.3", ["pkg", {options}]]`; installed with `@npmcli/arborist` into `~/.cache/opencode/packages/<spec>`; a bare name means `@latest` and is never upgraded once present → always pin. Entry: `exports["./server"]` → `main`. `engines.opencode` semver is enforced for npm plugins. Install failures surface as `session.error` events, not log lines.
- First launch after adding a dependency to a config dir's `package.json` loads nothing (background install). Pre-install with `npm install` in that dir.
- Existing plugin on this machine: `~/.config/opencode/plugins/session-browser.js` (uses `event` on `session.idle`). Pick distinct file and id names.

## Testing pattern (from the lazy-mcp tutorial sandbox)
`OPENCODE_CONFIG_DIR=<sandbox> opencode run --print-logs --log-level DEBUG "<prompt>" > log 2>&1 &` from a work dir, poll the log for a proof line, kill the process (macOS has no `timeout`). Real `~/.config/opencode` is still read (model `ollama/qwen3.8-fast`), never written. Log lines look like `timestamp=... level=INFO service=<svc> message=<msg> key=value`.
Experimental flags of interest: `OPENCODE_EXPERIMENTAL_CODE_MODE`, `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`, `OPENCODE_ENABLE_QUESTION_TOOL`.
