# Changelog

## 0.1.0

First release.

- Claude Code plugin: output guard, size lint, cache-break notices, pre-compaction snapshot, status line wrapper, weekly cost report.
- OpenCode plugin (`opencode/dist/harness-habits.js`): output guard, handoff notes, idle compaction (opt-in), tool budget guard (opt-in), cost logger.
- Codex CLI hooks and `handoff-note` skill: output guard, size lint, pre-compaction snapshot (doc-verified, not yet run against a live binary).
- Feature flags (`features.json`, `HH_FEATURE_*`, plugin options), per-harness installs, MCP set templates.
- Installer: `install.sh` with `--claude`, `--claude-dev`, `--statusline`, `--opencode`, `--codex`, `--report-cron`, `--features`, `--uninstall`, `--dry-run`.

### Release steps (maintainer)

Not done by the build: create the GitHub repo, push `main`, tag `v0.1.0`, optionally `npm publish` the OpenCode package.
