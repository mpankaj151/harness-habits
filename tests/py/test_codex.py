import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "shared" / "py" / "bin"
CLAUDE_FIX = ROOT / "tests" / "fixtures" / "transcripts" / "sample.jsonl"


def run(script, payload, tmp_path, extra_env=None, raw=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HH_", "CLAUDE_PLUGIN_"))}
    env.update(HOME=str(tmp_path / "home"), XDG_CONFIG_HOME=str(tmp_path / "cfg"), XDG_DATA_HOME=str(tmp_path / "data"))
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-I", str(BIN / script)],
                          input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, env=env)


@pytest.fixture
def work(tmp_path):
    (tmp_path / "big.txt").write_text("line\n" * 800)
    return tmp_path


def bash(cmd, cwd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd), "hook_event_name": "PreToolUse"}


# --- PreToolUse
def test_deny(work):
    r = run("codex_pretooluse.py", bash("cat big.txt", work), work)
    assert r.returncode == 0
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h["hookEventName"] == "PreToolUse" and h["permissionDecision"] == "deny"
    assert "limit 500" in h["permissionDecisionReason"]


def test_rewrite_default_is_advisory_with_suggestion(work):
    r = run("codex_pretooluse.py", bash("grep -r foo .", work), work)
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert set(h) == {"hookEventName", "additionalContext"}
    assert h["additionalContext"].endswith("Suggested: grep -r foo . | head -n 200")


def test_rewrite_deny_mode_is_opt_in(work):
    r = run("codex_pretooluse.py", bash("grep -r foo .", work), work, {"HH_CODEX_DENY": "1"})
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h["permissionDecision"] == "deny" and "updatedInput" not in h
    assert h["permissionDecisionReason"].endswith("Suggested: grep -r foo . | head -n 200")


def test_oversized_cat_and_tail_follow_still_deny_by_default(work):
    for cmd in ("cat big.txt", "tail -f app.log"):
        h = json.loads(run("codex_pretooluse.py", bash(cmd, work), work).stdout)["hookSpecificOutput"]
        assert h["permissionDecision"] == "deny"


def test_rewrite_enabled_allows_with_updated_input(work):
    r = run("codex_pretooluse.py", bash("grep -r foo .", work), work, {"HH_CODEX_REWRITE": "1"})
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h["permissionDecision"] == "allow"
    assert h["updatedInput"] == {"command": "grep -r foo . | head -n 200"}


def test_advise(work):
    r = run("codex_pretooluse.py", bash("grep -r foo . | sort", work), work)
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert set(h) == {"hookEventName", "additionalContext"}


def test_allow_other_tool_disabled_and_garbage(work):
    assert run("codex_pretooluse.py", bash("ls", work), work).stdout == ""
    assert run("codex_pretooluse.py", {**bash("cat big.txt", work), "tool_name": "apply_patch"}, work).stdout == ""
    assert run("codex_pretooluse.py", bash("cat big.txt", work), work, {"HH_FEATURE_OUTPUT_GUARD": "0"}).stdout == ""
    r = run("codex_pretooluse.py", None, work, raw="not json")
    assert (r.returncode, r.stdout) == (0, "")


# --- SessionStart
def test_sessionstart_plain_stdout(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "AGENTS.md").write_text("x\n" * 5)
    (proj / "CLAUDE.md").write_text("x\n" * 201)
    r = run("codex_sessionstart.py", {"cwd": str(proj), "source": "startup"}, tmp_path)
    assert r.returncode == 0
    assert not r.stdout.lstrip().startswith("{")
    assert "CLAUDE.md" not in r.stdout and r.stdout == ""  # Codex does not read CLAUDE.md
    (proj / "AGENTS.md").write_text("x\n" * 205)
    (tmp_path / "home" / ".codex").mkdir(parents=True)
    (tmp_path / "home" / ".codex" / "AGENTS.md").write_text("x\n" * 210)
    r = run("codex_sessionstart.py", {"cwd": str(proj), "source": "startup"}, tmp_path)
    assert f"{proj}/AGENTS.md has 205 lines (guideline 200 lines;" in r.stdout
    assert ".codex/AGENTS.md has 210 lines" in r.stdout and "CLAUDE.md" not in r.stdout
    off = run("codex_sessionstart.py", {"cwd": str(proj), "source": "startup"}, tmp_path, {"HH_FEATURE_SIZE_LINT": "0"})
    assert off.stdout == ""


# --- SessionEnd / PreCompact
def codex_rollout(path):
    lines = [
        {"type": "session_meta", "payload": {"id": "x"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
                                              "content": [{"type": "input_text", "text": "fix the parser"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                              "content": [{"type": "output_text", "text": "parser fixed"}]}},
        {"type": "weird", "payload": 5},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")


@pytest.mark.parametrize("script", ["codex_sessionend.py", "codex_precompact.py"])
def test_handoff_unknown_shape_keeps_text(script, tmp_path):
    t = tmp_path / "rollout.jsonl"
    codex_rollout(t)
    out = tmp_path / "ho"
    r = run(script, {"session_id": "s1", "transcript_path": str(t), "cwd": "/p"}, tmp_path, {"HH_CODEX_HANDOFF_DIR": str(out)})
    assert (r.returncode, r.stdout) == (0, "")
    text = (out / "s1.md").read_text()
    assert "fix the parser" in text and "parser fixed" in text and text.startswith("session: s1")


def test_handoff_claude_shape_and_default_dir(tmp_path):
    r = run("codex_sessionend.py", {"session_id": "s2", "transcript_path": str(CLAUDE_FIX), "cwd": "/p"}, tmp_path)
    assert r.returncode == 0
    assert "/proj/tests/test_parser.py" in (tmp_path / "home/.codex/handoff/s2.md").read_text()


def test_handoff_disabled_missing_transcript_and_sid_sanitised(tmp_path):
    out = tmp_path / "ho"
    env = {"HH_CODEX_HANDOFF_DIR": str(out)}
    p = {"session_id": "s3", "transcript_path": str(CLAUDE_FIX), "cwd": "/p"}
    run("codex_sessionend.py", p, tmp_path, {**env, "HH_FEATURE_PRECOMPACT_SNAPSHOT": "0"})
    assert not out.exists()
    r = run("codex_sessionend.py", {**p, "transcript_path": str(tmp_path / "none")}, tmp_path, env)
    assert r.returncode == 0
    run("codex_sessionend.py", {**p, "session_id": "../../evil"}, tmp_path, env)
    assert (out / "evil.md").exists() and not (tmp_path / "evil.md").exists()


# --- static files
def test_hooks_json_valid_and_scripts_exist():
    d = json.loads((ROOT / "codex" / "hooks.json").read_text())
    feats = {"PreToolUse": "output-guard", "SessionStart": "size-lint",
             "SessionEnd": "precompact-snapshot", "PreCompact": "precompact-snapshot"}
    assert set(d["hooks"]) == set(feats)
    for event, entries in d["hooks"].items():
        for e in entries:
            assert e["feature"] == feats[event]
            for h in e["hooks"]:
                script = h["command"].split('"')[1].replace("$HH_BIN", str(BIN))
                assert Path(script).is_file(), script


def test_templates_and_skill_valid():
    for rel in ["claude/.mcp.json", "claude/settings.json", "opencode/opencode.json", "lazy-mcp/lazy-mcp.json"]:
        json.loads((ROOT / "templates/mcp-sets" / rel).read_text())
    s = (ROOT / "codex/skills/handoff-note/SKILL.md").read_text()
    assert s.startswith("---\nname: handoff-note\ndescription: ")
    assert "memories = true" in (ROOT / "codex/config.toml.snippet").read_text()
