# Output guard

The output guard keeps shell output and file reads from flooding the context window. It runs as a Claude Code `PreToolUse` hook for the `Bash` and `Read` tools. The rules live in `shared/rules/output-guard.json` (500-line limit, 200-line head) and are shared with the OpenCode plugin.

Switch it off with `HH_FEATURE_OUTPUT_GUARD=0`, or `"output-guard": false` in `~/.config/harness-habits/features.json`. Any hook error allows the command and writes one `harness-habits:` line to stderr.

## Decision table

| Command | Decision |
|---|---|
| `cat`, `less`, `more` on a file over 500 lines | deny, with a `sed -n '1,200p'` suggestion |
| `cat` on a missing, binary or glob path | allow |
| `tail -f`, `-F`, `--follow` | deny (never returns) |
| `grep`, `rg`, `find` without `-c`, `-l`, `-q`, `--files`, `-exec`, `-delete` and similar | rewrite: ` \| head -n 200` appended |
| `ls -R`, `ls --recursive` | rewrite: ` \| head -n 200` appended |
| Piped or composed command whose first segment is `grep`, `rg` or `find` with no `head`, `tail`, `wc` anywhere | advise (context note only) |
| Any other composed command (`\|`, `&&`, `;`, `$(...)`, backticks, heredocs) | allow, never rewritten or denied |
| `Read` tool without `limit` on a file over 500 lines | advise |
| `sudo`, `command`, `nice`, `time` prefix | stripped before matching |

Unbalanced quotes and any engine error allow the command. Line counts for files stop at 501, so messages say `more than 500 lines` for any larger file. A newline in the command counts as a composed command.

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
            "command": "python3 -I /absolute/path/to/harness-habits/shared/py/bin/claude_pretooluse.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```
