# harness-habits

Small guard rails for people who use AI coding assistants every day. harness-habits stops a single `cat` or `grep -r` from dumping thousands of lines into the conversation, tells you when your instruction files have grown too big, keeps a short note of your work so a compaction or a new session does not start from zero, and shows what your sessions cost. It works with Claude Code, OpenCode and Codex CLI.

Install once; every feature is a switch, so you can keep all of it or only the part you want.

## What you get

### Bounding output

**Output guard** (`output-guard`)
- What it does: stops commands from flooding the conversation with output you did not mean to load.
- When it fires: before every shell command (and, on Claude Code, every file read).
- What you see: `cat` on a long file is refused: `harness-habits: <path> has more than 500 lines (limit 500). A line range keeps output bounded, for example: sed -n '1,200p' <path>`. `grep`, `rg`, `find` and `ls -R` get `| head -n 200` appended. `tail -f` is refused: ``harness-habits: `tail -f` never returns. …``
- Harnesses: Claude Code, OpenCode, Codex. Default: on.
- Doc: [docs/output-guard.md](docs/output-guard.md)

### Keeping context small

**Size lint** (`size-lint`)
- What it does: warns when `CLAUDE.md`, `AGENTS.md` or your auto-memory file is longer than the guideline, because that text is re-read on every turn.
- When it fires: at session start.
- What you see: `<path> has <n> lines (guideline 200; <b> bytes).` (OpenCode: `AGENTS.md has <n> lines (guideline 200). Long instruction files cost tokens on every turn.`)
- Harnesses: Claude Code, OpenCode, Codex (AGENTS.md only). Default: on.
- Doc: [docs/size-lint.md](docs/size-lint.md)

**Cache-break notices** (`cache-break`)
- What it does: tells you, once per file, that editing a file at the start of the prompt makes the next request more expensive.
- When it fires: after an edit or write of `CLAUDE.md`, `.mcp.json` or settings (Claude Code); `opencode.json`, `AGENTS.md`, `CLAUDE.md` (OpenCode); and after a model switch on Claude Code.
- What you see: Claude Code: `<path> is part of the prompt prefix; the next request re-reads the whole prefix at full input price (cache miss).` OpenCode toast: `AGENTS.md changed; it is part of the prompt prefix, so the next turn re-reads the full prefix (cache miss).`
- Harnesses: Claude Code, OpenCode. Default: on.
- Doc: [docs/cache-break.md](docs/cache-break.md)

**Tool budget** (`tool-budget`)
- What it does: warns when too many MCP servers are attached for a provider that rejects more than 128 tools, and can switch named servers off on the next run.
- When it fires: at OpenCode startup (server count), and when the provider rejects a request.
- What you see: a toast, for example `The provider rejected the request because too many tools were attached (…). Disable MCP servers for this project or enable lazy loading.`
- Harnesses: OpenCode. Default: off.
- Doc: [docs/tool-budget.md](docs/tool-budget.md), [docs/mcp-sets.md](docs/mcp-sets.md)

### Carrying work across sessions

**Pre-compaction snapshot** (`precompact-snapshot`)
- What it does: saves your last messages, todo list and edited files before a compaction, and hands them back afterwards.
- When it fires: on compaction and at session end; restored when a session continues after a compaction.
- What you see: Claude Code: `Snapshot taken before the last compaction of this session:` followed by the saved text, added to Claude's context; files in `<data dir>/precompact/<session_id>.md`. Codex: `~/.codex/handoff/<session_id>.md`.
- Harnesses: Claude Code, Codex. Default: on.
- Doc: [docs/precompact-snapshot.md](docs/precompact-snapshot.md)

**Handoff notes** (`handoff`)
- What it does: writes a short Markdown note after each turn so the next session knows where you left off.
- When it fires: after each OpenCode turn; announced when a new session starts in the same worktree.
- What you see: a file at `~/.local/share/harness-habits/handoff/<worktree-slug>/<session>.md`; the new session is told `A handoff note from a previous session in this project exists at <path>. …`
- Harnesses: OpenCode; on Codex a `handoff-note` skill (`$handoff-note`) writes `HANDOFF.md` on request. Default: on.
- Doc: [docs/handoff.md](docs/handoff.md)

**Idle compaction** (`idle-compaction`)
- What it does: compacts the conversation for you once it reaches a set share of the context window.
- When it fires: after a turn, when usage passes the threshold (60% of the window by default).
- What you see: a toast `harness-habits compacted the session at <n>% of context`.
- Harnesses: OpenCode. Default: off.
- Doc: [docs/compaction.md](docs/compaction.md)

### Seeing the cost

**Cost logger** (`cost-logger`)
- What it does: records the cost and token use of every OpenCode reply.
- When it fires: when an assistant message completes.
- What you see: one JSON line per reply in `~/.local/share/harness-habits/opencode-usage.jsonl`, read by the weekly report.
- Harnesses: OpenCode. Default: on.
- Doc: [docs/cost-report.md](docs/cost-report.md)

**Status line** (installer feature, `--statusline`)
- What it does: shows cost and context use in the Claude Code status line, and keeps your existing status line command.
- When it fires: whenever Claude Code redraws the status line.
- What you see: for example `$0.42 · 31%` followed by your previous status line text. Segments `cost`, `ctx`, `model` are set in `~/.config/harness-habits/statusline.json`.
- Harnesses: Claude Code. Default: not installed until you run `./install.sh --statusline`.
- Doc: [docs/install.md](docs/install.md)

**Weekly report** (installer feature, `--report-cron`)
- What it does: summarises a week of cost per harness and per model, with the ten most expensive sessions.
- When it fires: Mondays 09:00 (launchd on macOS; on Linux the installer prints a crontab line to add).
- What you see: `<data dir>/reports/<ISO-week>.md`, titled `harness-habits cost report`. Run by hand: `python3 -I ~/.local/share/harness-habits/bin/weekly_report.py --since 7d`.
- Harnesses: reads Claude, Codex and OpenCode sessions. Default: not installed until you run `./install.sh --report-cron`.
- Doc: [docs/cost-report.md](docs/cost-report.md)

## Quick start

### Claude Code

```sh
claude plugin marketplace add mpankaj151/harness-habits
claude plugin install harness-habits@harness-habits
# or, to try a checkout: claude --plugin-dir <checkout>
```

What it wrote: nothing by the installer itself; the plugin carries all Claude Code hooks (output guard, size lint, cache-break, snapshot). State goes to the plugin data dir (snapshots, cache-break markers). `./install.sh --statusline` additionally edits `~/.claude/settings.json`.

Check it works: start `claude` in a folder with a file over 500 lines and ask: "Run exactly: `cat big.txt`". Expected refusal: `harness-habits: big.txt has more than 500 lines (limit 500). A line range keeps output bounded, …`. Then ask "Run exactly: `grep -r foo .` and tell me how many lines came back"; the answer is at most 200, because `| head -n 200` was appended (the transcript still shows your original command). This is what `make smoke-claude` does.

### OpenCode

```sh
./install.sh --opencode
```

What it wrote: `~/.config/opencode/plugins/harness-habits.js`. Features are read from `~/.config/harness-habits/features.json`; tuning options from `opencode.json` in the same folder (optional).

Check it works: ask OpenCode to run `cat big.txt` on a file over 500 lines; the command is refused with the `more than 500 lines` message. After any reply, look for a handoff note: `ls ~/.local/share/harness-habits/handoff/*/*.md`; the folder name is your worktree path with non-alphanumeric characters replaced by `-`. A cost line appears in `~/.local/share/harness-habits/opencode-usage.jsonl`. `make smoke-opencode` automates the guard and handoff checks against a local Ollama model.

### Codex CLI

```sh
./install.sh --codex
```

What it wrote: the `codex_*.py` scripts, the `harness_habits` package and rules in `~/.local/share/harness-habits/bin/`; hook entries merged into `~/.codex/hooks.json`; the `handoff-note` skill in `~/.agents/skills/handoff-note`. It prints a `config.toml` snippet and never edits TOML.

Check it works: Codex only runs hooks you have trusted, so open `/hooks` and trust the harness-habits entries first. By default the guard is advisory: a bounded rewrite shows up as a note ending `Suggested: <command>` and the command still runs; only an oversized `cat` and `tail -f` are refused. Details and the `HH_CODEX_REWRITE` / `HH_CODEX_DENY` switches: [docs/codex.md](docs/codex.md).

## What gets installed where

Add `--dry-run` to preview any of these, and `--home PATH` to redirect every path under PATH.

| Flag | Files written | Config read | Remove |
|---|---|---|---|
| (Claude plugin) `--claude` | none by the installer; runs `claude plugin marketplace add` and `claude plugin install` | `features.json`, `HH_FEATURE_*`, `CLAUDE_PLUGIN_OPTION_*` | `./install.sh --claude --uninstall` (runs `claude plugin uninstall harness-habits@harness-habits`) |
| `--claude-dev` | none; prints `claude --plugin-dir <repo>` | same | n/a |
| `--statusline` | `~/.local/share/harness-habits/bin/statusline_wrap.py` (+ package, rules); `statusLine` in `~/.claude/settings.json`; previous status line recorded in `~/.config/harness-habits/statusline.json` | `statusline.json` | `./install.sh --statusline --uninstall` restores the recorded status line |
| `--opencode` | `~/.config/opencode/plugins/harness-habits.js` | `~/.config/harness-habits/features.json`, optional `opencode.json` | `./install.sh --opencode --uninstall` |
| `--codex` | scripts, package and rules in `~/.local/share/harness-habits/bin/`; `~/.codex/hooks.json`; `~/.agents/skills/handoff-note/` | `features.json` | `./install.sh --codex --uninstall` |
| `--report-cron` | `~/.local/share/harness-habits/bin/weekly_report.py` (+ package, rules, `pricing.json` once); macOS: `~/Library/LaunchAgents/com.harness-habits.weekly-report.plist` | session-browser registry, usage log | `./install.sh --report-cron --uninstall` |
| `--features a,b` | `~/.config/harness-habits/features.json`: listed features on, all others off | n/a | edit or delete the file |
| `--all` | everything above except `--claude-dev` and `--features` | | |

JSON edits keep a `<file>.bak.<epoch>` backup when content changes. More: [docs/install.md](docs/install.md).

## Choosing features

1. **Feature flags, one install.** Flags come from `~/.config/harness-habits/features.json` (`{"cache-break": false}`), overridable by `HH_FEATURE_<KEY>` env vars (`HH_FEATURE_CACHE_BREAK=0`) and, on Claude Code, `CLAUDE_PLUGIN_OPTION_<KEY>`. Env wins over the file. `--features` writes the file. Keys: `output-guard`, `size-lint`, `cache-break`, `handoff`, `idle-compaction`, `cost-logger`, `tool-budget`, `precompact-snapshot`.
2. **Per harness.** `--claude`, `--opencode`, `--codex`, `--statusline`, `--report-cron` are independent; none implies another.
3. **Standalone, no plugin.** Each feature doc has a "Just this one" section: a hooks snippet pointing at the single script (Claude Code, Codex; `size-lint` and `precompact-snapshot` share the SessionStart script, and the docs show how to switch one off), or the per-feature OpenCode bundle `opencode/dist/features/<name>.js` (plugin id `harness-habits-<name>`).

Also: [install](docs/install.md), [Codex](docs/codex.md), [MCP sets](docs/mcp-sets.md), [auto-compact threshold](docs/autocompact-pct.md). Developer notes live in `docs/dev/`.

## Maturity

Claude Code: the PreToolUse guard is exercised live via `tests/smoke/claude.sh` with `--plugin-dir`; the other hooks are unit-tested only. OpenCode: smoke-tested against a local Ollama model. Codex: doc-verified, not yet run against a live binary. See [KNOWN-ISSUES.md](KNOWN-ISSUES.md) (v0.1.0).

Supported platforms: macOS and Linux (Python 3.9+ for hooks, 3.11+ for the installer and report). The hooks were run on Python 3.9.6 during the final review; CI runs 3.11 and 3.12 on Linux and macOS.

## Development

`make test`, `make build` (rebuilds the committed `opencode/dist`), `make lint`, `make validate`, `make smoke-opencode` (needs `opencode` and a local model), `make smoke-claude` (needs `claude`; a few cents on `--model haiku`).

Releases: see [CHANGELOG.md](CHANGELOG.md).

## Credits

- [session-browser](https://github.com/mpankaj151/session-browser) provides the registry the cost report reads.
- Related work for the OpenCode tool-cap problem: a colleague's lazy-mcp plugin, documented separately in the author's tutorial repo. No code was copied from it.

MIT licensed.
