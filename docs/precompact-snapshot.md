# Pre-compaction snapshot

`PreCompact` cannot inject text into a compaction, so `PreCompact` and `SessionEnd` write a snapshot to
`<data dir>/precompact/<session_id>.md` (`CLAUDE_PLUGIN_DATA` if set): last 5 user messages, last assistant message, latest
TodoWrite list and edited files. `SessionStart` with source `compact` or `resume` re-injects it. With `HH_STARTUP_HANDOFF=1`,
a `startup` session also receives the newest snapshot for the same `cwd` younger than 7 days.
Disable with feature `precompact-snapshot`.
