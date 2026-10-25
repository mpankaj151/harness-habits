"""Codex CLI PreToolUse hook: output guard for Bash.

updatedInput on Codex requires permissionDecision "allow", which auto-approves the rewritten command.
Rewrites are therefore advisory by default (additionalContext carrying the suggested command, no extra turn).
HH_CODEX_REWRITE=1 -> allow + updatedInput; HH_CODEX_DENY=1 -> deny with the suggestion in the reason.
"""
import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, ".."))
sys.path.insert(0, _here)  # installed layout: <data dir>/bin/harness_habits

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
        elif os.environ.get("HH_CODEX_DENY") == "1":
            _out(permissionDecision="deny", permissionDecisionReason=f"{d.message} Suggested: {d.command}")
        else:
            _out(additionalContext=f"{d.message} Suggested: {d.command}")
    elif d.action == "advise":
        _out(additionalContext=d.message)


main()
