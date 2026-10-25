import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "shared" / "py" / "bin"
FIX = ROOT / "tests" / "fixtures" / "transcripts" / "sample.jsonl"
MSG = "is part of the prompt prefix; the next request re-reads the whole prefix at full input price (cache miss)."


def run(script, payload, tmp_path, extra_env=None, raw=None, args=()):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HH_", "CLAUDE_PLUGIN_"))}
    env.update(HOME=str(tmp_path / "home"), XDG_CONFIG_HOME=str(tmp_path / "cfg"), XDG_DATA_HOME=str(tmp_path / "data"))
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-I", str(BIN / script), *args],
                          input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, env=env)


def snap_path(tmp_path, sid="s-1"):
    return tmp_path / "data" / "harness-habits" / "precompact" / f"{sid}.md"


def ctx(r):
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


# --- snapshot writers
@pytest.mark.parametrize("script", ["claude_precompact.py", "claude_sessionend.py"])
def test_snapshot_written(script, tmp_path):
    r = run(script, {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/proj"}, tmp_path)
    assert (r.returncode, r.stdout) == (0, "")
    text = snap_path(tmp_path).read_text()
    assert text.startswith("session: s-1\ncwd: /proj\nwritten: ")
    assert "/proj/tests/test_parser.py" in text


def test_snapshot_uses_plugin_data_env(tmp_path):
    d = tmp_path / "pd"
    run("claude_precompact.py", {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/p"}, tmp_path,
        {"CLAUDE_PLUGIN_DATA": str(d)})
    assert (d / "precompact" / "s-1.md").exists() and not snap_path(tmp_path).exists()


def test_snapshot_disabled_or_bad_transcript(tmp_path):
    p = {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/p"}
    run("claude_precompact.py", p, tmp_path, {"HH_FEATURE_PRECOMPACT_SNAPSHOT": "0"})
    assert not snap_path(tmp_path).exists()
    r = run("claude_sessionend.py", {**p, "transcript_path": str(tmp_path / "missing")}, tmp_path)
    assert r.returncode == 0 and r.stderr == ""


# --- SessionStart
def mkfile(p, lines):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n" * lines)


def test_sessionstart_lint(tmp_path):
    cwd = tmp_path / "proj"
    mkfile(cwd / "CLAUDE.md", 250)
    r = run("claude_sessionstart.py", {"source": "startup", "cwd": str(cwd)}, tmp_path)
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart" and "CLAUDE.md has 250 lines" in out["additionalContext"]
    assert run("claude_sessionstart.py", {"source": "clear", "cwd": str(cwd)}, tmp_path).stdout
    assert run("claude_sessionstart.py", {"source": "startup", "cwd": str(cwd)}, tmp_path, {"HH_FEATURE_SIZE_LINT": "0"}).stdout == ""
    assert run("claude_sessionstart.py", {"source": "resume", "cwd": str(cwd), "session_id": "none"}, tmp_path).stdout == ""


def test_sessionstart_clean_is_silent(tmp_path):
    (tmp_path / "proj").mkdir()
    r = run("claude_sessionstart.py", {"source": "startup", "cwd": str(tmp_path / "proj")}, tmp_path)
    assert (r.returncode, r.stdout) == (0, "")


@pytest.mark.parametrize("source", ["compact", "resume"])
def test_sessionstart_reinjects_snapshot(source, tmp_path):
    run("claude_precompact.py", {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/proj"}, tmp_path)
    r = run("claude_sessionstart.py", {"source": source, "session_id": "s-1", "cwd": "/proj"}, tmp_path)
    assert ctx(r).startswith("Snapshot taken before the last compaction of this session:\nsession: s-1")
    off = run("claude_sessionstart.py", {"source": source, "session_id": "s-1", "cwd": "/proj"}, tmp_path,
              {"HH_FEATURE_PRECOMPACT_SNAPSHOT": "0"})
    assert off.stdout == ""


def test_sessionstart_startup_handoff(tmp_path):
    run("claude_sessionend.py", {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/proj"}, tmp_path)
    p = {"source": "startup", "session_id": "new", "cwd": "/proj"}
    assert run("claude_sessionstart.py", p, tmp_path).stdout == ""
    r = run("claude_sessionstart.py", p, tmp_path, {"HH_STARTUP_HANDOFF": "1"})
    assert "session: s-1" in ctx(r)
    assert run("claude_sessionstart.py", {**p, "cwd": "/other"}, tmp_path, {"HH_STARTUP_HANDOFF": "1"}).stdout == ""
    old = snap_path(tmp_path)
    t = old.stat().st_mtime - 8 * 24 * 3600
    os.utime(old, (t, t))
    assert run("claude_sessionstart.py", p, tmp_path, {"HH_STARTUP_HANDOFF": "1"}).stdout == ""


def test_handoff_gated_by_snapshot_feature(tmp_path):
    run("claude_sessionend.py", {"session_id": "s-1", "transcript_path": str(FIX), "cwd": "/proj"}, tmp_path)
    r = run("claude_sessionstart.py", {"source": "startup", "session_id": "new", "cwd": "/proj"}, tmp_path,
            {"HH_STARTUP_HANDOFF": "1", "HH_FEATURE_PRECOMPACT_SNAPSHOT": "0"})
    assert (r.returncode, r.stdout) == (0, "")


def test_sessionstart_lint_and_handoff_concatenate(tmp_path):
    cwd = tmp_path / "proj"
    mkfile(cwd / "AGENTS.md", 300)
    run("claude_sessionend.py", {"session_id": "s-1", "transcript_path": str(FIX), "cwd": str(cwd)}, tmp_path)
    r = run("claude_sessionstart.py", {"source": "startup", "cwd": str(cwd)}, tmp_path, {"HH_STARTUP_HANDOFF": "1"})
    assert "AGENTS.md has 300 lines" in ctx(r) and "session: s-1" in ctx(r)


# --- PostToolUse
def edit(path, sid="s-1", tool="Edit"):
    return {"tool_name": tool, "session_id": sid, "tool_input": {"file_path": path}}


@pytest.mark.parametrize("path", ["/p/CLAUDE.md", "/p/.mcp.json", "/p/.claude/settings.json",
                                  "/p/.claude/settings.local.json", "/p/.claude/rules/a.md"])
def test_posttooluse_notice_once(path, tmp_path):
    r = run("claude_posttooluse.py", edit(path), tmp_path)
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h == {"hookEventName": "PostToolUse", "additionalContext": f"{path} {MSG}"}
    assert run("claude_posttooluse.py", edit(path), tmp_path).stdout == ""
    assert run("claude_posttooluse.py", edit(path, sid="s-2"), tmp_path).stdout != ""


def test_posttooluse_ignored(tmp_path):
    assert run("claude_posttooluse.py", edit("/p/main.py"), tmp_path).stdout == ""
    assert run("claude_posttooluse.py", edit("/p/CLAUDE.md", tool="Read"), tmp_path).stdout == ""
    assert run("claude_posttooluse.py", edit("/p/CLAUDE.md"), tmp_path, {"HH_FEATURE_CACHE_BREAK": "0"}).stdout == ""
    assert run("claude_posttooluse.py", {"tool_name": "Edit", "tool_input": "oops"}, tmp_path).returncode == 0


# --- PostModelSwitch
def test_postmodelswitch(tmp_path):
    r = run("claude_postmodelswitch.py", {}, tmp_path)
    assert r.stdout == "Model switched; the prompt cache is per model, so this first turn re-reads the full context at full price."
    assert run("claude_postmodelswitch.py", {}, tmp_path, {"HH_FEATURE_CACHE_BREAK": "off"}).stdout == ""


@pytest.mark.parametrize("script", ["claude_sessionstart.py", "claude_precompact.py", "claude_sessionend.py",
                                    "claude_posttooluse.py", "claude_postmodelswitch.py"])
@pytest.mark.parametrize("raw", ["", "garbage", "[1]"])
def test_invalid_stdin_exits_zero(script, raw, tmp_path):
    r = run(script, None, tmp_path, raw=raw)
    assert r.returncode == 0


# --- lint_cli
def test_lint_cli(tmp_path):
    cwd = tmp_path / "proj"
    mkfile(cwd / "AGENTS.md", 300)
    r = run("lint_cli.py", None, tmp_path, args=["--cwd", str(cwd)], raw="")
    assert r.returncode == 0 and "AGENTS.md has 300 lines" in r.stdout
    assert run("lint_cli.py", None, tmp_path, args=["--strict", "--cwd", str(cwd)], raw="").returncode == 1
    (tmp_path / "ok").mkdir()
    assert run("lint_cli.py", None, tmp_path, args=["--strict", "--cwd", str(tmp_path / "ok")], raw="").returncode == 0


def test_hooks_json_events():
    h = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    assert set(h) == {"PreToolUse", "SessionStart", "PostToolUse", "PostModelSwitch", "PreCompact", "SessionEnd"}
    assert h["PostToolUse"][0]["matcher"] == "Edit|Write|MultiEdit"
    assert h["PreCompact"][0]["hooks"][0]["timeout"] == 30
