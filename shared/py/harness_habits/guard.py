"""Output guard decision engine (shared rules: shared/rules/output-guard.json)."""
import os
from dataclasses import dataclass
from itertools import islice
from typing import Literal, Optional, Protocol

from . import shellsplit

PREFIXES = ("sudo", "command", "nice", "time")


@dataclass
class Decision:
    action: Literal["allow", "deny", "rewrite", "advise"]
    command: Optional[str] = None
    message: Optional[str] = None


class FileSystem(Protocol):
    def line_count(self, path: str) -> Optional[int]: ...


class RealFS:
    def __init__(self, cwd: str, max_lines: int = 500):
        self.cwd = cwd or os.getcwd()
        self.max_lines = max_lines

    def line_count(self, path: str) -> Optional[int]:
        try:
            full = os.path.join(self.cwd, os.path.expanduser(path))
            if not os.path.isfile(full):
                return None
            with open(full, "rb") as fh:
                if b"\0" in fh.read(8192):
                    return None
                fh.seek(0)
                return sum(1 for _ in islice(fh, self.max_lines + 1))
        except OSError:
            return None


def _fmt(rules: dict, key: str, **kw) -> str:
    return rules["messages"][key].format(max=rules["max_lines"], head=rules["head_n"], **kw)


def _strip_prefixes(seg: list) -> list:
    i = 0
    while i < len(seg) - 1 and os.path.basename(seg[i]) in PREFIXES:
        i += 1
    return seg[i:]


def _has_skip(cmd: str, args: list, rules: dict) -> bool:
    skip = rules["skip_flags"].get(cmd, [])
    return any(a in skip for a in args)


def evaluate(command: str, cwd: str, fs: FileSystem, rules: dict) -> Decision:
    try:
        return _evaluate(command, cwd, fs, rules)
    except Exception:  # noqa: BLE001 - never block on engine errors
        return Decision("allow")


def _evaluate(command, cwd, fs, rules) -> Decision:
    ops = set(rules["operators"])
    tokens = shellsplit.split(command)
    if not tokens:
        return Decision("allow")
    segs = shellsplit.segments(tokens, ops)
    if not segs:
        return Decision("allow")

    if shellsplit.is_composed(tokens, command, ops):
        first = _strip_prefixes(segs[0])
        cmd = os.path.basename(first[0])
        if (
            cmd in rules["unbounded_commands"]
            and not _has_skip(cmd, first[1:], rules)
            and not any(os.path.basename(t) in rules["bounding_commands"] for t in tokens)
        ):
            return Decision("advise", message=_fmt(rules, "advise_unbounded", cmd=cmd))
        return Decision("allow")

    seg = _strip_prefixes(segs[0])
    cmd, args = os.path.basename(seg[0]), seg[1:]

    if cmd in rules["full_read_commands"]:
        paths = [a for a in args if not a.startswith("-")]
        if any(ch in p for p in paths for ch in "*?["):
            return Decision("allow")
        for p in paths:
            n = fs.line_count(p)
            if n is not None and n > rules["max_lines"]:
                return Decision("deny", message=_fmt(rules, "deny_full_read", path=p, lines=n))
        return Decision("allow")

    if cmd == "tail":
        flag = next((a for a in args if a in rules["follow_flags"]), None)
        if flag:
            path = next((a for a in reversed(args) if not a.startswith("-")), "<file>")
            return Decision("deny", message=_fmt(rules, "deny_follow", flag=flag, path=path))
        return Decision("allow")

    rewrite = (cmd in rules["unbounded_commands"] and not _has_skip(cmd, args, rules)) or (
        cmd == "ls" and any(a in rules["ls_recursive_flags"] for a in args)
    )
    if rewrite:
        return Decision(
            "rewrite",
            command=f"{command} | head -n {rules['head_n']}",
            message=_fmt(rules, "rewrite_note"),
        )
    return Decision("allow")


def evaluate_read(file_path: str, limit, cwd: str, fs: FileSystem, rules: dict) -> Decision:
    try:
        if limit or not file_path:
            return Decision("allow")
        n = fs.line_count(file_path)
        if n is not None and n > rules["max_lines"]:
            return Decision("advise", message=_fmt(rules, "advise_read", path=file_path, lines=n))
    except Exception:  # noqa: BLE001
        pass
    return Decision("allow")
