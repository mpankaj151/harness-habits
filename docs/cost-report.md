
## OpenCode usage log format

The `cost-logger` feature appends one JSON line per completed assistant message to
`$XDG_DATA_HOME/harness-habits/opencode-usage.jsonl` (default `~/.local/share/harness-habits/opencode-usage.jsonl`).

Fields: `ts` (ISO timestamp), `sessionID`, `messageID`, `providerID`, `modelID`, `cost`, `tokens_last_step`.

`cost` accumulates across all steps within the message. `tokens_last_step` (`input`, `output`, `reasoning`, `cache.read`, `cache.write`) is the usage of the last step only, so it approximates the current context size and does not sum to the message total.
