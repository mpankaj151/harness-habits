"""Claude Code PostToolUse hook: note edits to prompt-prefix files (cache miss)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import cachebreak, features, hookio  # noqa: E402


@hookio.safe_main
def main():
    data = hookio.read_json_stdin()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit") or not features.enabled("cache-break"):
        return
    fp = (data.get("tool_input") or {}).get("file_path")
    if not isinstance(fp, str) or not cachebreak.is_prefix_file(fp):
        return
    if cachebreak.first_time(str(data.get("session_id") or ""), fp):
        hookio.emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": cachebreak.message(fp)}})


main()
