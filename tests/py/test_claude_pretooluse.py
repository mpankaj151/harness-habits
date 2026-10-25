import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).resolve().parents[2] / "shared" / "py" / "bin" / "claude_pretooluse.py")


@pytest.fixture
def work(tmp_path):
    (tmp_path / "big.txt").write_text("line\n" * 800)
    return tmp_path


def run(payload, tmp_path, extra_env=None, raw=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HH_", "CLAUDE_PLUGIN_OPTION_"))}
    env["XDG_CONFIG_HOME"] = str(tmp_path / "cfg")
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-I", SCRIPT],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True, text=True, env=env,
    )


def bash(cmd, cwd, **extra):
    return {"tool_name": "Bash", "tool_input": {"command": cmd, **extra}, "cwd": str(cwd)}


def test_deny(work):
    r = run(bash("cat big.txt", work), work)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out == {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": out["hookSpecificOutput"]["permissionDecisionReason"],
    }}
    assert "more than 500 lines (limit 500)" in out["hookSpecificOutput"]["permissionDecisionReason"]  # RealFS stops counting at max+1


def test_rewrite_keeps_other_input_fields(work):
    r = run(bash("grep -r foo .", work, description="d", timeout=5), work)
    out = json.loads(r.stdout)
    h = out["hookSpecificOutput"]
    assert set(h) == {"hookEventName", "updatedInput", "additionalContext"}
    assert h["updatedInput"] == {"command": "grep -r foo . | head -n 200", "description": "d", "timeout": 5}
    assert "head -n 200" in h["additionalContext"]


def test_advise_bash(work):
    r = run(bash("grep -r foo . | sort", work), work)
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert set(h) == {"hookEventName", "additionalContext"}


def test_allow_is_silent(work):
    r = run(bash("git log --oneline", work), work)
    assert (r.returncode, r.stdout) == (0, "")


def test_read_advise_and_limit(work):
    p = {"tool_name": "Read", "tool_input": {"file_path": str(work / "big.txt")}, "cwd": str(work)}
    h = json.loads(run(p, work).stdout)["hookSpecificOutput"]
    assert set(h) == {"hookEventName", "additionalContext"}
    assert "more than 500 lines" in h["additionalContext"]
    p["tool_input"]["limit"] = 50
    assert run(p, work).stdout == ""


def test_relative_read_uses_cwd(work):
    p = {"tool_name": "Read", "tool_input": {"file_path": "big.txt"}, "cwd": str(work)}
    assert "more than 500 lines" in run(p, work).stdout


def test_other_tool_silent(work):
    r = run({"tool_name": "Edit", "tool_input": {"file_path": "x"}, "cwd": str(work)}, work)
    assert (r.returncode, r.stdout) == (0, "")


def test_disabled_feature(work):
    r = run(bash("cat big.txt", work), work, {"HH_FEATURE_OUTPUT_GUARD": "0"})
    assert (r.returncode, r.stdout) == (0, "")


@pytest.mark.parametrize("raw", ["", "not json", "[1,2]"])
def test_invalid_stdin(work, raw):
    r = run(None, work, raw=raw)
    assert (r.returncode, r.stdout) == (0, "")


@pytest.mark.parametrize("payload", [
    {"tool_name": "Bash", "tool_input": "oops", "cwd": "/tmp"},
    {"tool_name": "Read", "tool_input": ["x"], "cwd": "/tmp"},
])
def test_handler_exception_is_swallowed(work, payload):
    r = run(payload, work)
    assert r.returncode == 0
    assert r.stdout == ""
    assert r.stderr.startswith("harness-habits:")


def test_tail_follow_denied_in_foreground(work):
    r = run(bash("tail -f app.log", work), work)
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h["permissionDecision"] == "deny" and "never returns" in h["permissionDecisionReason"]


def test_tail_follow_allowed_when_run_in_background(work):
    r = run(bash("tail -f app.log", work, run_in_background=True), work)
    assert r.returncode == 0 and r.stdout == ""


def test_background_still_applies_other_rules(work):
    r = run(bash("cat big.txt", work, run_in_background=True), work)
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    r = run(bash("grep -r foo .", work, run_in_background=True), work)
    assert "updatedInput" in json.loads(r.stdout)["hookSpecificOutput"]
