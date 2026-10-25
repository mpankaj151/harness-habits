# Claude Code hooks and plugin facts (verified 2026-10-25)

Source: https://code.claude.com/docs/en/hooks, /plugins/manifest-reference, /statusline, /monitoring-usage, /env-vars.

## Events used by harness-habits
`SessionStart`, `SessionEnd`, `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`,
`ConfigChange`, `PostModelSwitch`. (Full list has 33 events incl. `PreModelSwitch`, `Stop`, `SubagentStop`.)

## Stdin (every event)
`session_id`, `prompt_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `permission_mode`, `effort`, `hook_event_name`.
- PreToolUse adds `tool_name`, `tool_input`, `tool_use_id`. Bash input: `{command, description?, timeout?, run_in_background?}`. Read input: `{file_path, offset?, limit?}`. Edit/Write: `{file_path, ...}`.
- PostToolUse adds `tool_response`, `duration_ms`.
- SessionStart adds `source`: `startup | resume | clear | compact | fork`, optional `model`.
- PreCompact adds `trigger`: `manual | auto`, `custom_instructions` (null for auto). PostCompact adds `trigger`, `compact_summary`.

## Stdout / exit codes
- Exit 0 + JSON on stdout is applied. Plain stdout reaches the model ONLY for `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`, `PostModelSwitch`.
- Exit 2 = blocking error, stderr is the reason (blocks PreToolUse, PreCompact, Stop…; does NOT block PostToolUse, SessionStart, SessionEnd, PostCompact).
- Other exit codes = non-blocking error, action proceeds. We always exit 0.

### PreToolUse output
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse",
  "permissionDecision":"deny|allow|ask|defer",
  "permissionDecisionReason":"...",
  "updatedInput":{ "...full replacement input object..." },
  "additionalContext":"..."}}
```
`updatedInput` replaces the whole input object (include unchanged fields). Docs pair it with `allow` (auto-approve) or `ask`; we omit the decision so normal permission flow applies and verify in smoke. Deny/ask rules in settings still apply.

### PostToolUse output
Plain stdout goes to the debug log only. Use `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}`.
Also available: `updatedToolOutput`, `decision:"block"` + `reason`.

### SessionStart output
Plain stdout on exit 0 is added to context, or `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}`.

### ConfigChange
Stdin adds `source` (`user_settings | project_settings | local_settings | policy_settings | skills`) and optional `file_path`. Output supports ONLY `decision: "block"` (`reason` accepted but never shown); `systemMessage` and `continue` are discarded; no `additionalContext`, plain stdout does not reach the model. A hook here can audit or block, never inform Claude. (Verified 2026-10-25; harness-habits therefore ships no ConfigChange hook.)

### PreCompact
Cannot inject text into the compaction (systemMessage/continue discarded). Can only block (exit 2). Workaround: write a snapshot file here; re-inject it from `SessionStart` with `source: "compact"`.

Docs warn: write context as factual statements; imperative system-style wording can trigger prompt-injection defenses.

## Matchers
`"Edit|Write"` is an exact-name list; any other character makes it a regex. MCP tools are `mcp__<server>__<tool>`.

## hooks.json (plugin)
```json
{"description":"...","hooks":{"PreToolUse":[{"matcher":"Bash|Read","hooks":[{"type":"command","command":"python3 -I \"${CLAUDE_PLUGIN_ROOT}/shared/py/bin/x.py\"","timeout":10}]}]}}
```
Handler fields: `type` (`command|http|mcp_tool|prompt|agent`), `command`, `timeout` (default 600 s), `if`, `statusMessage`, `once`, `async`, `onFailure`.
Env in hook process: `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` (`~/.claude/plugins/data/<id>/`, survives updates), `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_OPTION_<KEY>`.

## Plugin packaging
- `.claude-plugin/plugin.json`: `name` required (kebab-case; names starting `claude-`/`anthropic-`/`cc-plugin-` rejected). Optional: `version`, `description`, `author{name,email,url}`, `repository`, `license`, `keywords`, `userConfig`, `settings`, component paths (`./`-prefixed).
- Layout at plugin root: `skills/<name>/SKILL.md`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, `bin/` (added to PATH), `settings.json` (only `agent` and `subagentStatusLine` honoured — a plugin CANNOT set the main `statusLine`).
- No `CLAUDE.md` at plugin root is loaded; no `.claude/rules` component. Instructions ship as skills.
- `.claude-plugin/marketplace.json`: `{"name","owner":{"name"},"plugins":[{"name","source":"./" | {"source":"github","repo":"o/r"}}]}`.
- Install: `claude plugin marketplace add <owner>/<repo>` then `claude plugin install <plugin>@<marketplace>`; dev: `claude --plugin-dir <path>`. Validate: `claude plugin validate <path>` (local CLI has `--json`, no `--strict`).
- Team sharing: `extraKnownMarketplaces` + `enabledPlugins` in the repo's `.claude/settings.json`.

## Status line
settings.json: `{"statusLine":{"type":"command","command":"...","padding":0,"refreshInterval":N}}`.
Stdin JSON: `session_id, transcript_path, cwd, version, model{id,display_name}, workspace{current_dir,project_dir}, cost{total_cost_usd,total_duration_ms,total_api_duration_ms}, context_window{total_input_tokens,total_output_tokens,context_window_size,used_percentage,remaining_percentage,current_usage{input_tokens,output_tokens,cache_creation_input_tokens,cache_read_input_tokens}|null}, exceeds_200k_tokens, rate_limits?, output_style{name}, vim{mode}, agent{name}`.
Debounced 300 ms; a slow run is cancelled when the next update starts.

## Auto-compact knobs
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (1-100, can only lower; third-party reports say it is ignored in settings `env`, so export in the shell), `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (100000-1000000 tokens), settings `autoCompactWindow`, `autoCompactEnabled`, `/autocompact 500k`, `DISABLE_AUTO_COMPACT=1`.

## Telemetry
`CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp|prometheus|console`, `OTEL_LOGS_EXPORTER`, `OTEL_EXPORTER_OTLP_ENDPOINT`. Metrics: `claude_code.cost.usage`, `claude_code.token.usage{type=input|output|cacheRead|cacheCreation}`, session/commit/PR counts.

## Transcript JSONL (for `transcript.py`)
Files: `~/.claude/projects/<slug>/<session_id>.jsonl`, slug = cwd with every non-alphanumeric char replaced by `-` (e.g. `/Users/alice` → `-Users-alice`). Lines are JSON objects with `type` (`user|assistant|...`), `message{role, content: string | [{type:"text",text}|{type:"tool_use",name,input}|{type:"tool_result",...}]}`, `uuid`, `timestamp`. Inspect one real file read-only before writing the fixture; shapes vary by version.

## Coexistence on this machine
`~/.claude/settings.json` already has: `statusLine` → `bash ~/.claude/statusline-command.sh`; `Stop` and `SessionEnd` hooks → session-browser's python; plugin `claude-mods` hooks `PreToolUse(Bash)`, `PostToolUse(Write|Edit)`, `SessionStart`, `ConfigChange` (none use `updatedInput`). Same-event hooks run side by side.
