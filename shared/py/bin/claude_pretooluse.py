"""Claude Code PreToolUse hook: output guard for Bash and Read."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import features, guard, hookio  # noqa: E402
from harness_habits.paths import rules_path  # noqa: E402


def _out(**fields):
    hookio.emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}})


@hookio.safe_main
def main():
    data = hookio.read_json_stdin()
    tool = data.get("tool_name")
    if tool not in ("Bash", "Read") or not features.enabled("output-guard"):
        return
    rules = json.loads(rules_path().read_text())
    cwd = data.get("cwd") or os.getcwd()
    fs = guard.RealFS(cwd, rules["max_lines"])
    tin = data.get("tool_input") or {}
    if tool == "Bash":
        d = guard.evaluate(tin.get("command", ""), cwd, fs, rules)
    else:
        d = guard.evaluate_read(tin.get("file_path", ""), tin.get("limit"), cwd, fs, rules)
    if d.action == "deny":
        _out(permissionDecision="deny", permissionDecisionReason=d.message)
    elif d.action == "rewrite":
        _out(updatedInput={**tin, "command": d.command}, additionalContext=d.message)
    elif d.action == "advise":
        _out(additionalContext=d.message)


main()
