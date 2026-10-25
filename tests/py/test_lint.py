from pathlib import Path

from harness_habits import lint


def mk(p: Path, lines: int, size: int = 0):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n" * lines if not size else "x" * size)


def test_slug_matches_real_rule():
    assert lint.slug(Path("/Users/nehamodi")) == "-Users-nehamodi"
    assert lint.slug(Path("/Users/a/Documents/my_proj.x")) == "-Users-a-Documents-my-proj-x"


def test_claude_md_boundary(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    cwd.mkdir(); home.mkdir()
    mk(cwd / "CLAUDE.md", 200)
    assert lint.lint(cwd, home) == []
    mk(cwd / "CLAUDE.md", 201)
    f = lint.lint(cwd, home)
    assert len(f) == 1 and f[0].lines == 201 and f[0].guideline == "200 lines"
    assert "path-scoped rules in .claude/rules/ load only when matching files are touched" in f[0].note


def test_no_rules_note_when_rules_dir_exists(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    home.mkdir()
    mk(cwd / "CLAUDE.md", 250)
    (cwd / ".claude" / "rules").mkdir(parents=True)
    assert "rules" not in lint.lint(cwd, home)[0].note


def test_other_files(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    mk(cwd / ".claude" / "CLAUDE.md", 201)
    mk(cwd / "AGENTS.md", 201)
    mk(home / ".claude" / "CLAUDE.md", 201)
    assert len(lint.lint(cwd, home)) == 3


def test_memory_thresholds(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    cwd.mkdir()
    mem = home / ".claude" / "projects" / lint.slug(cwd) / "memory" / "MEMORY.md"
    mk(mem, 180)
    assert lint.lint(cwd, home) == []
    mk(mem, 181)
    assert lint.lint(cwd, home)[0].guideline == "180 lines"
    mk(mem, 0, 22528)
    assert lint.lint(cwd, home) == []
    mk(mem, 0, 22529)
    f = lint.lint(cwd, home)
    assert len(f) == 1 and f[0].bytes == 22529 and f[0].guideline == "22528 bytes"


def test_format(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    home.mkdir()
    mk(cwd / "AGENTS.md", 300)
    out = lint.format(lint.lint(cwd, home))
    assert out.count("\n") == 0
    assert "AGENTS.md has 300 lines (guideline 200 lines; 600 bytes)" in out
    assert lint.format([]) == ""


def test_codex_checks_only_agents_files(tmp_path):
    cwd, home = tmp_path / "p", tmp_path / "h"
    mk(cwd / "CLAUDE.md", 300)
    mk(cwd / ".claude" / "CLAUDE.md", 300)
    mk(home / ".claude" / "CLAUDE.md", 300)
    mk(home / ".claude" / "projects" / lint.slug(cwd) / "memory" / "MEMORY.md", 300)
    assert lint.lint(cwd, home, harness="codex") == []
    mk(cwd / "AGENTS.md", 201)
    mk(home / ".codex" / "AGENTS.md", 201)
    found = lint.lint(cwd, home, harness="codex")
    assert [f.path for f in found] == [cwd / "AGENTS.md", home / ".codex" / "AGENTS.md"]
    assert all(f.note == "" for f in found)
    assert len(lint.lint(cwd, home)) >= 3  # claude default unchanged
