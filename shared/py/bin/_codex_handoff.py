"""Shared body of the Codex PreCompact and SessionEnd hooks."""
import os
from pathlib import Path

from harness_habits import features, hookio, transcript


def write_handoff():
    data = hookio.read_json_stdin()
    if not features.enabled("precompact-snapshot"):
        return
    tp, sid = data.get("transcript_path"), os.path.basename(str(data.get("session_id") or ""))
    if not tp or not sid or sid in (".", ".."):
        return
    cwd = data.get("cwd") or os.getcwd()
    text = transcript.render(transcript.extract_tolerant(Path(tp)), cwd, sid)
    out = Path(os.environ.get("HH_CODEX_HANDOFF_DIR") or Path.home() / ".codex" / "handoff")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{sid}.md").write_text(text)
