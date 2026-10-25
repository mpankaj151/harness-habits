"""Cache-break notices: edits to files that sit in the prompt prefix."""
import json
import os
from pathlib import Path

from .paths import data_dir

NAMES = {"CLAUDE.md", ".mcp.json", "settings.json", "settings.local.json"}


def plugin_data_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(env) if env else data_dir()


def is_prefix_file(file_path: str) -> bool:
    return bool(file_path) and (os.path.basename(file_path) in NAMES or "/.claude/rules/" in file_path.replace("\\", "/"))


def message(file_path: str) -> str:
    return (f"{file_path} is part of the prompt prefix; the next request re-reads the whole prefix "
            "at full input price (cache miss).")


def first_time(session_id: str, file_path: str) -> bool:
    """True once per (session, file); records a marker."""
    marker = plugin_data_dir() / "cachebreak" / f"{os.path.basename(session_id or 'unknown')}.json"
    try:
        seen = json.loads(marker.read_text())
        if not isinstance(seen, list):
            seen = []
    except (OSError, ValueError):
        seen = []
    if file_path in seen:
        return False
    seen.append(file_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(seen))
    return True
