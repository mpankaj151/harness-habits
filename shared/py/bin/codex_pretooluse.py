"""Codex CLI PreToolUse hook: output guard for Bash.

updatedInput on Codex requires permissionDecision "allow", which auto-approves the rewritten command.
Rewrites are therefore reported as deny-with-suggestion unless HH_CODEX_REWRITE=1.
"""
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
    if data.get("tool_name") != "Bash" or not features.enabled("output-guard"):
        return
    rules = json.loads(rules_path().read_text())
    cwd = data.get("cwd") or os.getcwd()
    fs = guard.RealFS(cwd, rules["max_lines"])
    tin = data.get("tool_input") or {}
    d = guard.evaluate(tin.get("command", ""), cwd, fs, rules)
    if d.action == "deny":
        _out(permissionDecision="deny", permissionDecisionReason=d.message)
    elif d.action == "rewrite":
        if os.environ.get("HH_CODEX_REWRITE") == "1":
            _out(permissionDecision="allow", updatedInput={"command": d.command})
        else:
            _out(permissionDecision="deny", permissionDecisionReason=f"{d.message} Suggested: {d.command}")
    elif d.action == "advise":
        _out(additionalContext=d.message)


main()
