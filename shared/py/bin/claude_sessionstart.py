"""Claude Code SessionStart hook: size lint, snapshot re-injection, optional startup handoff."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import cachebreak, features, hookio, lint  # noqa: E402

WEEK = 7 * 24 * 3600


def _newest_for_cwd(snap_dir: Path, cwd: str):
    best = None
    for p in snap_dir.glob("*.md"):
        try:
            if time.time() - p.stat().st_mtime >= WEEK:
                continue
            head = p.read_text().splitlines()[:4]
            if f"cwd: {cwd}" in head and (best is None or p.stat().st_mtime > best.stat().st_mtime):
                best = p
        except OSError:
            continue
    return best


@hookio.safe_main
def main():
    data = hookio.read_json_stdin()
    source = data.get("source")
    cwd = data.get("cwd") or os.getcwd()
    parts = []
    snap_dir = cachebreak.plugin_data_dir() / "precompact"
    if source in ("startup", "clear") and features.enabled("size-lint"):
        text = lint.format(lint.lint(Path(cwd), Path.home()))
        if text:
            parts.append(text)
    if source in ("compact", "resume") and features.enabled("precompact-snapshot"):
        sid = os.path.basename(str(data.get("session_id") or ""))
        p = snap_dir / f"{sid}.md"
        if sid and p.is_file():
            parts.append("Snapshot taken before the last compaction of this session:\n" + p.read_text())
    if source == "startup" and os.environ.get("HH_STARTUP_HANDOFF") == "1" and snap_dir.is_dir():
        p = _newest_for_cwd(snap_dir, cwd)
        if p:
            parts.append("Snapshot from the most recent earlier session in this directory:\n" + p.read_text())
    if parts:
        hookio.emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(parts)}})


main()
