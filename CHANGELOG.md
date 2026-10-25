# Changelog

## Unreleased

- docs: README rewritten as a feature inventory with per-harness quick start and verification checks; feature docs normalised to one template.

## 0.1.0

First release.

- Claude Code plugin: output guard, size lint, cache-break notices, pre-compaction snapshot.
- Installer features (not part of the plugin): status line wrapper with cost and context segments (`--statusline`), weekly cost report (`--report-cron`).
- OpenCode plugin (`opencode/dist/harness-habits.js`): output guard, size lint, cache-break notices, handoff notes (stored under the data dir, per worktree), idle compaction (opt-in), tool budget guard (opt-in), cost logger.
- Codex CLI hooks and `handoff-note` skill: output guard (rewrites are advisory by default; `HH_CODEX_REWRITE=1` and `HH_CODEX_DENY=1` change that), size lint (AGENTS.md only), pre-compaction snapshot. Doc-verified, not yet run against a live binary. The installer copies the scripts, package and rules to the data dir, so the hooks survive a moved checkout.
- Feature flags (`features.json`, `HH_FEATURE_*` env vars; `CLAUDE_PLUGIN_OPTION_*` env vars are honoured, but the plugin declares no `userConfig`), per-harness installs, MCP set templates.
- Hook commands are written as `test -f "<script>" && python3 -I "<script>" || true`, so a deleted or moved script exits 0 instead of blocking the harness.
- Installer: `install.sh` with `--claude`, `--claude-dev`, `--statusline`, `--opencode`, `--codex`, `--report-cron`, `--features`, `--uninstall`, `--dry-run`. JSON edits go through symlinks, keep file modes and never overwrite a backup.
- Verification: PreToolUse guard exercised live on Claude Code (`tests/smoke/claude.sh`); OpenCode smoke against a local Ollama model (`tests/smoke/opencode.sh`).
- Known issues (v0.1.0): see [KNOWN-ISSUES.md](KNOWN-ISSUES.md).
