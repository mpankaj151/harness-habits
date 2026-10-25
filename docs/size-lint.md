# Size lint

At `SessionStart` (sources `startup` and `clear`) harness-habits reports instruction files over their guideline:
`CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md` in the project and `~/.claude/CLAUDE.md` (over 200 lines), and the
auto-memory `~/.claude/projects/<slug>/memory/MEMORY.md` (over 180 lines or 22528 bytes). `<slug>` is the project path with
every non-alphanumeric character replaced by `-`. A `CLAUDE.md` over 200 lines with no `.claude/rules/` gets a note that
path-scoped rules load only when matching files are touched.

Disable with feature `size-lint`. Run by hand: `python3 -I shared/py/bin/lint_cli.py [--strict] [--cwd PATH]`;
the pre-commit hook id is `harness-habits-size-lint`.
