# Cost report

`weekly_report.py` prints (or saves) a cost summary for the last week. Run it by hand:

```
python3 -I ~/.local/share/harness-habits/bin/weekly_report.py --since 7d
```

Options: `--since 7d|30d|YYYY-MM-DD` (default `7d`), `--format md|json`, `--write` (also saves
`<data dir>/reports/<ISO-week>.md`, for example `2026-W43.md`), `--registry PATH`, `--usage-log PATH`,
`--claude-projects PATH`. `install.py --report-cron` schedules `weekly_report.py --write` for Monday 09:00.

## What the report contains

The report has two sections from different sources. They are never summed together.

1. **Session-browser registry** (`~/.session-browser/registry.db`, opened read-only). Sessions whose
   `last_activity` is inside the window, totalled per `cli_source` (Claude, Codex, OpenCode) and per
   `model_used`, with the cache-hit ratio `cache_read / (input + cache_read + cache_write)` and the top 10
   sessions by `cost_usd`. Sessions with no recorded cost count as $0 in totals and are left out of the top 10.
2. **OpenCode usage log** (below), grouped per `providerID/modelID`.

### Fallback when there is no registry

The registry is optional. Without it, section 1 is estimated from Claude Code transcripts in
`~/.claude/projects/*/*.jsonl`: each assistant entry's `message.usage` and `message.model`, deduplicated by
`message.id` (a message that is streamed over several lines keeps its last line). Costs are priced with
`pricing.json` and every figure is labelled "estimated". Only Claude Code transcripts are covered.

## pricing.json

`shared/pricing.json` holds placeholder per-million-token prices keyed by model-id prefix (longest prefix wins),
plus a `default` entry. They are estimates, not vendor prices: edit them. The installer copies the file to
`<data dir>/pricing.json` once; that copy takes precedence and is never overwritten.


## OpenCode usage log format

The `cost-logger` feature appends one JSON line per completed assistant message to
`$XDG_DATA_HOME/harness-habits/opencode-usage.jsonl` (default `~/.local/share/harness-habits/opencode-usage.jsonl`).

Fields: `ts` (ISO timestamp), `sessionID`, `messageID`, `providerID`, `modelID`, `cost`, `tokens_last_step`.

`cost` accumulates across all steps within the message. `tokens_last_step` (`input`, `output`, `reasoning`, `cache.read`, `cache.write`) is the usage of the last step only, so it approximates the current context size and does not sum to the message total.
