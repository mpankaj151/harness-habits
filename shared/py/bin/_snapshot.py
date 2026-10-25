"""Shared body of the PreCompact and SessionEnd hooks."""
import os
from pathlib import Path

from harness_habits import cachebreak, features, hookio, transcript


def write_snapshot():
    data = hookio.read_json_stdin()
    if not features.enabled("precompact-snapshot"):
        return
    tp, sid = data.get("transcript_path"), os.path.basename(str(data.get("session_id") or ""))
    if not tp or not sid:
        return
    cwd = data.get("cwd") or os.getcwd()
    text = transcript.render(transcript.extract(Path(tp)), cwd, sid)
    out = cachebreak.plugin_data_dir() / "precompact" / f"{sid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
