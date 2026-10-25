"""Size lint for instruction files and auto-memory."""
import re
from dataclasses import dataclass
from pathlib import Path

LINE_LIMIT = 200
MEMORY_LINES = 180
MEMORY_BYTES = 22528
RULES_NOTE = "path-scoped rules in .claude/rules/ load only when matching files are touched"


@dataclass
class Finding:
    path: Path
    lines: int
    bytes: int
    guideline: str
    note: str = ""


def slug(cwd: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(cwd).resolve()))


def _stat(path: Path):
    try:
        if not path.is_file():
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0), len(data)


def lint(cwd: Path, home: Path) -> list:
    cwd, home = Path(cwd), Path(home)
    findings = []
    rules_missing = not (cwd / ".claude" / "rules").is_dir()
    for p in (cwd / "CLAUDE.md", cwd / ".claude" / "CLAUDE.md", cwd / "AGENTS.md", home / ".claude" / "CLAUDE.md"):
        st = _stat(p)
        if st and st[0] > LINE_LIMIT:
            note = RULES_NOTE if rules_missing and p == cwd / "CLAUDE.md" else ""
            findings.append(Finding(p, st[0], st[1], f"{LINE_LIMIT} lines", note))
    mem = home / ".claude" / "projects" / slug(cwd) / "memory" / "MEMORY.md"
    st = _stat(mem)
    if st:
        if st[0] > MEMORY_LINES:
            findings.append(Finding(mem, st[0], st[1], f"{MEMORY_LINES} lines"))
        elif st[1] > MEMORY_BYTES:
            findings.append(Finding(mem, st[0], st[1], f"{MEMORY_BYTES} bytes"))
    return findings


def format(findings) -> str:
    out = []
    for f in findings:
        line = f"{f.path} has {f.lines} lines (guideline {f.guideline}; {f.bytes} bytes)."
        if f.note:
            line += f" Note: {f.note}."
        out.append(line)
    return "\n".join(out)
