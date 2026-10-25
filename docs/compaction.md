# Idle compaction (OpenCode)

## Why

OpenCode compacts only when the context overflows, so a long session carries a large history on every turn until then. Idle compaction summarises earlier, at a share of the window you choose, so later turns carry less. It is a trade-off and is off by default.

## What you see

A toast: `harness-habits compacted the session at <n>% of context`. The conversation is replaced by its summary.

## Setup

### Claude Code

Not applicable. Claude Code compacts itself; to compact earlier see [autocompact-pct.md](autocompact-pct.md).

### OpenCode

`./install.sh --opencode`, then turn the feature on (it is off by default): set `"idle-compaction": true` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_IDLE_COMPACTION=1`, or use the `"features"` block in `opencode.json` shown below. (`--features` would switch every unlisted feature off, so list all the features you want.)

### Codex CLI

Not available.

## Switch it off

Feature key: `idle-compaction` (off by default). Leave it off, or set `"idle-compaction": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_IDLE_COMPACTION=0`.

## Just this one

OpenCode: each feature has its own dependency-free bundle with plugin id `harness-habits-idle-compaction`. Copy it without the all-in-one plugin:

```sh
cp opencode/dist/features/idle-compaction.js ~/.config/opencode/plugins/
```

Options come from `~/.config/harness-habits/opencode.json`: set `"features": {"idle-compaction": true}` and a `compaction` block as above. Do not install it together with `harness-habits.js`, which already contains the feature.

## Details / Limits

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

### Trade-off

A compaction costs one summary call and breaks the prompt cache, so the next turn re-reads the whole
(now shorter) context uncached. Later turns are cheaper because each carries less history. It pays off
when sessions keep going well past the threshold and loses on short sessions. It is off by default, and
the default provider exclusion keeps it away from local models, where cached tokens are free and a summary
call is slow.

### Setting absoluteTokens

When the context window is unknown or wrong for a model, pin the trigger directly in
`<config dir>/opencode.json`:

```json
{"features": {"idle-compaction": true}, "compaction": {"absoluteTokens": 90000, "disableForProviders": []}}
```

Or give the window and keep the percentage: `"compaction": {"contextLimits": {"anthropic/claude-sonnet-5": 200000}}`.
