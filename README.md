# harness-habits

Install-once token, memory and cost hygiene for Claude Code, OpenCode and Codex CLI. It bounds runaway shell output, flags oversized instruction files, keeps handoff notes across compaction, and reports what a week of sessions cost. Every feature is a switch; pick one or all.

**Status:** Claude Code and OpenCode tested locally (OpenCode smoke against a local Ollama model); Codex doc-verified, not yet run against a live binary.

## The problem

| Habit | What it costs | What harness-habits does |
|---|---|---|
| `grep -r`, `find`, `ls -R`, `cat` on big files | Thousands of lines land in context and are re-read every turn | [Output guard](docs/output-guard.md) denies, advises or suggests a bounded rewrite |
| Growing CLAUDE.md / AGENTS.md / MEMORY.md | A larger prefix on every request | [Size lint](docs/size-lint.md) reports files over the guideline at session start |
| Editing CLAUDE.md, `.mcp.json` or settings mid-session | The prompt cache prefix is invalidated | [Cache-break notices](docs/cache-break.md) state the cost once per file |
| Compaction loses the thread | Re-explaining work | [Pre-compaction snapshot](docs/precompact-snapshot.md), [handoff notes](docs/handoff.md), [idle compaction](docs/compaction.md) |
| Many MCP servers on OpenAI-compatible endpoints | Requests rejected above 128 tools | [Tool budget guard](docs/tool-budget.md), [MCP sets](docs/mcp-sets.md) |
| Not knowing where tokens go | Surprise bills | [Cost report](docs/cost-report.md), status line cost and context segments |

Also: [auto-compact threshold](docs/autocompact-pct.md).

## Install

```sh
# Claude Code
claude plugin marketplace add mpankaj151/harness-habits
claude plugin install harness-habits@harness-habits
# develop against a checkout instead: claude --plugin-dir <checkout>

# OpenCode (copies opencode/dist/harness-habits.js to ~/.config/opencode/plugins/)
./install.sh --opencode

# Codex CLI (see docs/codex.md)
./install.sh --codex
```

Optional: `./install.sh --statusline` (status line wrapper), `./install.sh --report-cron` (weekly cost report), `./install.sh --features output-guard,handoff` (only those features on). All flags and what they touch: [docs/install.md](docs/install.md). Requires Python 3.11+, stdlib only.

## Features and pluggability

| Feature key | Claude Code | OpenCode | Codex | Default |
|---|---|---|---|---|
| `output-guard` | yes | yes | yes | on |
| `size-lint` | yes | | yes | on |
| `cache-break` | yes | | | on |
| `handoff` | | yes | skill | on |
| `idle-compaction` | | yes | | off |
| `cost-logger` | | yes | | on |
| `tool-budget` | | yes | | off |
| `precompact-snapshot` | yes | | yes | on |

Three levels of choice:

1. **Feature flags, one install.** `~/.config/harness-habits/features.json`, `HH_FEATURE_<KEY>` env vars, or Claude plugin options. Env wins over the file. `--features` writes the file.
2. **Per harness.** `--claude`, `--opencode`, `--codex`, `--statusline`, `--report-cron` are independent; none implies another.
3. **Standalone, no plugin.** Each feature doc has a section for using just that one script or snippet.

## Docs

[install](docs/install.md), [codex](docs/codex.md), [output guard](docs/output-guard.md), [size lint](docs/size-lint.md), [cache break](docs/cache-break.md), [pre-compaction snapshot](docs/precompact-snapshot.md), [handoff](docs/handoff.md), [idle compaction](docs/compaction.md), [tool budget](docs/tool-budget.md), [MCP sets](docs/mcp-sets.md), [cost report](docs/cost-report.md), [auto-compact threshold](docs/autocompact-pct.md). Developer notes live in `docs/dev/`.

## Development

`make test`, `make build` (rebuilds the committed `opencode/dist`), `make lint`, `make validate`, `make smoke-opencode` (needs `opencode` and a local model).

Release steps for the maintainer, not done by the build: create the GitHub repo, push, tag `v0.1.0`, optionally `npm publish`.

## Credits

- [session-browser](https://github.com/mpankaj151/session-browser) provides the registry the cost report reads.
- Related work for the OpenCode tool-cap problem: a colleague's lazy-mcp plugin, documented separately in the author's tutorial repo. No code was copied from it.

MIT licensed.
