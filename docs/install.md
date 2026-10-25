# Installing harness-habits

Requirements: Python 3.11+. The installer uses only the standard library.

```sh
./install.sh --all                 # everything below
./install.sh --claude              # claude plugin marketplace add + install
./install.sh --claude-dev          # prints: claude --plugin-dir <repo>
./install.sh --statusline          # status line wrapper (a plugin cannot set statusLine)
./install.sh --opencode            # copies opencode/dist/harness-habits.js
./install.sh --codex               # merges Codex hooks and skill (needs the codex/ files)
./install.sh --report-cron         # weekly report: launchd on macOS, crontab line elsewhere
./install.sh --features output-guard,handoff   # listed features on, all others off
./install.sh --uninstall --statusline --opencode
./install.sh --dry-run ...         # print every action, write nothing
```

`--home PATH` redirects every path under PATH (used by the tests).

## What each flag touches

- `--claude` runs `claude plugin marketplace add mpankaj151/harness-habits` and
  `claude plugin install harness-habits@harness-habits` (printed, then run unless `--dry-run`).
- `--statusline` copies `statusline_wrap.py` and the `harness_habits` package to
  `~/.local/share/harness-habits/bin/`, records an existing `statusLine` object as `wrapped` in
  `~/.config/harness-habits/statusline.json`, and points `~/.claude/settings.json` at the wrapper.
  `--uninstall` restores the recorded object. Segments (`cost`, `ctx`, `model`) are configurable in
  `statusline.json`: `{"segments":["cost","ctx"]}`.
- `--opencode` writes `~/.config/opencode/plugins/harness-habits.js` (skipped with a warning when
  another file declares the same plugin id) and `~/.config/harness-habits/opencode.json` if absent.
- `--features` writes `~/.config/harness-habits/features.json`.
- `--codex` merges `codex/hooks.json` into `~/.codex/hooks.json`, copies the `handoff-note` skill to
  `~/.agents/skills/`, and prints the `config.toml` snippet. It never writes TOML.

Edits to JSON files are atomic and leave a `<file>.bak.<epoch>` backup only when content changes,
so re-running the installer changes nothing.
