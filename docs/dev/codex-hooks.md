# Codex CLI hooks, memories and skills (doc-verified 2026-10-25; no live binary tested)

Docs moved: `developers.openai.com/codex/*` now redirects to `https://learn.chatgpt.com/docs/*`
(`/docs/hooks`, `/docs/customization/memories`, `/docs/build-skills`, `/docs/config-file/config-reference`).

## Hooks
- On by default; `[features] hooks = false` disables (`codex_hooks` is a deprecated alias).
- Files: `~/.codex/hooks.json`, `~/.codex/config.toml` inline `[[hooks.PreToolUse]]`, `<repo>/.codex/hooks.json` (trusted projects only), plugin `hooks/hooks.json`, managed `requirements.toml` `[hooks] managed_dir`.
- Shape:
```json
{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"...","timeout":30}]}]}}
```
- Events: `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStart`, `SubagentStop`, `Stop`, `Interrupt`, `SessionStart`, `SessionEnd`.
- Stdin: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, sometimes `permission_mode`; tool events add `turn_id`, `tool_name`, `tool_use_id`, `tool_input` (PostToolUse adds `tool_response`); compaction events add `trigger`; SessionStart adds `source`.
- Blocking: exit 2 with stderr reason (PreToolUse, PostToolUse, UserPromptSubmit, SubagentStop, Stop) or JSON `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}`. Legacy `decision:"block"` + `reason`.
- Rewriting: PreToolUse only, REQUIRES `permissionDecision:"allow"` plus `updatedInput`; for Bash/apply_patch `updatedInput.command` must be a string. This auto-approves the rewritten command → harness-habits defaults to deny-with-suggestion and enables rewrite only with `HH_CODEX_REWRITE=1`.
- Not supported in PreToolUse: `"ask"`, `continue:false`, `stopReason`. `additionalContext` adds context without blocking.
- Matcher is a regex; `"*"`/empty = all. Tool names: `Bash`, `apply_patch` (also matches Edit/Write), `mcp__server__tool`. UserPromptSubmit/Stop/Interrupt ignore matchers.
- Trust: non-managed hooks must be reviewed with `/hooks`; trust is bound to the hook's hash, so every edit requires re-trust. `--dangerously-bypass-hook-trust` for one run.
- Handler types: `command` (runs), `mcp_tool`; `prompt`/`agent` parsed but skipped. Fields: `command`, `timeout` (600 s default), `statusMessage`, `async`, `additionalContextLimit`.

## Memories
`[features] memories = true` (off by default). Stored in `~/.codex/memories/` (generated; do not hand-edit). Keys: `memories.generate_memories`, `memories.use_memories`, `memories.disable_on_external_context`, `memories.min_rate_limit_remaining_percent`, `memories.extract_model`, `memories.consolidation_model`. Per-chat toggle via `/memories`. No per-project toggle.

## Skills
Locations: `$CWD/.agents/skills` up to repo root, `$HOME/.agents/skills`, `/etc/codex/skills`. (`.codex/skills` is NOT documented.) `SKILL.md` frontmatter: `name`, `description`. Optional `agents/openai.yaml` with `interface.*`, `policy.allow_implicit_invocation`. Invoke with `$name` or `/skills`.

## Config
`model`, `model_reasoning_effort` (`low|medium|high|xhigh|max|ultra`), `plan_mode_reasoning_effort`. Profiles since 0.134.0 are separate files `~/.codex/<name>.config.toml` (`[profiles.x]` removed). Admin enforcement via `requirements.toml` (`/etc/codex/requirements.toml`, MDM).

## This machine
`~/.codex/config.toml` has `model = "gpt-5.5"`, `model_reasoning_effort = "medium"`, trusted projects, plugin marketplaces; no `[features]`, no hooks, `~/.codex/memories/` and `~/.codex/skills/` exist but are empty. The npm `codex` wrapper is broken (vendored binary missing); Codex.app is installed. Python `tomllib` reads TOML; nothing in the stdlib writes it, so the installer prints the snippet instead of editing `config.toml`.
