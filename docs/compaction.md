# Idle compaction (OpenCode)

Feature key: `idle-compaction` (off by default). OpenCode only.

OpenCode compacts only at overflow, with no percentage threshold. When this feature is on, the plugin
checks the last assistant message after each turn (debounced, subagents skipped, after the handoff note
is written) and calls `session.summarize` once the context in use reaches the limit.

- tokens: `tokens.total`, else input + output + cache read + cache write
- limit: `compaction.absoluteTokens` if set, else `compaction.pct` (default 0.6) times the context window
- context window, first match wins: `compaction.contextLimits["provider/model"]`, then
  `provider.<p>.models.<m>.limit.context` from the OpenCode config, then 200000
- skipped when the last assistant message is itself a summary (loop guard: a compaction ends with another
  `session.idle`), while a compaction is in flight (cleared by `session.compacted` or after 120 s), within
  `compaction.cooldownMs` (default 60000) of the last one, or for providers in
  `compaction.disableForProviders` (default `["ollama"]`, case-insensitive exact match)

## Trade-off

A compaction costs one summary call and breaks the prompt cache, so the next turn re-reads the whole
(now shorter) context uncached. Later turns are cheaper because each carries less history. It pays off
when sessions keep going well past the threshold and loses on short sessions. It is off by default, and
the default provider exclusion keeps it away from local models, where cached tokens are free and a summary
call is slow.

## Setting absoluteTokens

When the context window is unknown or wrong for a model, pin the trigger directly in
`<config dir>/opencode.json`:

```json
{"features": {"idle-compaction": true}, "compaction": {"absoluteTokens": 90000, "disableForProviders": []}}
```

Or give the window and keep the percentage: `"compaction": {"contextLimits": {"anthropic/claude-sonnet-5": 200000}}`.
