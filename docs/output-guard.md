# Output guard

## Why

`grep -r`, `find`, `ls -R` and `cat` on a large file can put thousands of lines into the conversation, and every later turn re-reads them. The guard bounds that output before it is loaded, so the cost never accrues.

## What you see

Messages come from `shared/rules/output-guard.json`:

- Oversized `cat`, `less`, `more`: refused with `harness-habits: <path> has more than 500 lines (limit 500). A line range keeps output bounded, for example: sed -n '1,200p' <path>`
- `tail -f`: refused with ``harness-habits: `tail -f` never returns. `tail -n 200 <path>` shows the end once.``
- `grep`, `rg`, `find`, `ls -R`: ` | head -n 200` is appended and the model is told `harness-habits appended `| head -n 200` to bound the output.`
- Piped `grep`/`rg`/`find` with no bound: advice ``harness-habits: `<cmd>` in this pipeline has no output bound. `| head -n 200`, `-l` or `-c` keeps the result small.``
- Claude Code `Read` without `limit` on a long file: advice `harness-habits: <path> has more than 500 lines. Read without `limit` loads all of them; `offset`/`limit` or a grep first keeps context small.`

The decision table below lists every case. Claude Code transcripts record the model's original command, not the rewritten one, so a bounded rewrite never shows up in the session history.

## Setup

### Claude Code

Included in the plugin install (`claude plugin marketplace add mpankaj151/harness-habits`, then `claude plugin install harness-habits@harness-habits`). Nothing else to do; to turn it off see below.

### OpenCode

`./install.sh --opencode` (all features in one plugin; feature `output-guard`). On OpenCode a refusal is shown as the error; rewrites and advice are written to the OpenCode log with service `harness-habits`.

### Codex CLI

`./install.sh --codex` (then trust the hooks via `/hooks`). Rewrites are advisory by default; see [codex.md](codex.md).

## Switch it off

Set `"output-guard": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_OUTPUT_GUARD=0` in the shell that launches the harness. On Claude Code `CLAUDE_PLUGIN_OPTION_OUTPUT_GUARD=0` works too. Any hook error allows the command and writes one `harness-habits:` line to stderr.

## Just this one

To use the guard without installing the plugin, add the hook to `~/.claude/settings.json` (or a project `.claude/settings.json`) with an absolute path to your checkout:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Read",
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"/absolute/path/to/harness-habits/shared/py/bin/claude_pretooluse.py\" && python3 -I \"/absolute/path/to/harness-habits/shared/py/bin/claude_pretooluse.py\" || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

## Details / Limits

The rules live in `shared/rules/output-guard.json` (500-line limit, 200-line head) and are shared with the OpenCode plugin. The PreToolUse hook runs for the `Bash` and `Read` tools.

### Decision table

| Command | Decision |
|---|---|
| `cat`, `less`, `more` on a file over 500 lines | deny, with a `sed -n '1,200p'` suggestion |
| `cat` on a missing, binary or glob path | allow |
| `tail -f`, `-F`, `--follow` | deny (never returns); allowed on Claude Code when the call has `run_in_background: true` |
| `grep`, `rg`, `find` without `-c`, `-l`, `-q`, `--files`, `-exec`, `-delete` and similar | rewrite: ` \| head -n 200` appended |
| `ls -R`, `ls --recursive` | rewrite: ` \| head -n 200` appended |
| Piped or composed command whose first segment is `grep`, `rg` or `find` with no `head`, `tail`, `wc` anywhere | advise (context note only) |
| Any other composed command (`\|`, `&&`, `;`, `$(...)`, backticks, heredocs) | allow, never rewritten or denied |
| `Read` tool without `limit` on a file over 500 lines | advise |
| `sudo`, `command`, `nice`, `time` prefix | stripped before matching |

Unbalanced quotes and any engine error allow the command. Line counts for files stop at 501, so messages say `more than 500 lines` for any larger file. A newline in the command counts as a composed command.
