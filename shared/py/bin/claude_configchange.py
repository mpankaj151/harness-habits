"""Claude Code ConfigChange hook: same cache-break note for config files."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import cachebreak, features, hookio  # noqa: E402


@hookio.safe_main
def main():
    data = hookio.read_json_stdin()
    if data.get("hook_event_name") != "ConfigChange" or not features.enabled("cache-break"):
        return
    fp = data.get("file_path") or "A config file"
    if not isinstance(fp, str):
        fp = "A config file"
    if cachebreak.first_time(str(data.get("session_id") or ""), fp):
        hookio.emit({"hookSpecificOutput": {"hookEventName": "ConfigChange", "additionalContext": cachebreak.message(fp)}})


main()
