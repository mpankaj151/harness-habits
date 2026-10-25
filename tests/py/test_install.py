import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIG = {"type": "command", "command": "bash /Users/nehamodi/.claude/statusline-command.sh"}


def run(home, *args):
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    p = subprocess.run([sys.executable, "-I", str(ROOT / "install.py"), "--home", str(home), *args],
                       capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def setup(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"statusLine": ORIG, "other": 1}))
    return home


def snapshot(home):
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}


FLAGS = ["--statusline", "--opencode", "--features", "output-guard,handoff"]


def test_dry_run_writes_nothing(tmp_path):
    home = setup(tmp_path)
    before = snapshot(home)
    out = run(home, *FLAGS, "--dry-run")
    assert "statusline" in out.lower() and "opencode" in out.lower()
    assert snapshot(home) == before


def test_install_idempotent_and_uninstall(tmp_path):
    home = setup(tmp_path)
    run(home, *FLAGS)
    settings = json.loads((home / ".claude/settings.json").read_text())
    data = home / ".local/share/harness-habits/bin"
    assert settings["statusLine"] == {"type": "command", "command": f"python3 -I {data}/statusline_wrap.py"}
    assert settings["other"] == 1
    assert (data / "statusline_wrap.py").exists() and (data / "harness_habits/statusline.py").exists()
    cfg = home / ".config/harness-habits"
    assert json.loads((cfg / "statusline.json").read_text())["wrapped"] == ORIG
    feats = json.loads((cfg / "features.json").read_text())
    assert feats["output-guard"] is True and feats["handoff"] is True and feats["size-lint"] is False
    assert len(feats) == 8
    assert json.loads((cfg / "opencode.json").read_text())["features"]["handoff"] is True
    assert (home / ".config/opencode/plugins/harness-habits.js").read_bytes() == (ROOT / "opencode/dist/harness-habits.js").read_bytes()
    baks = list(home.rglob("*.bak.*"))
    assert len(baks) == 1  # only settings.json changed from a pre-existing file

    before = snapshot(home)
    run(home, *FLAGS)
    assert snapshot(home) == before  # no new .bak, nothing changed
    assert json.loads((cfg / "statusline.json").read_text())["wrapped"] == ORIG

    run(home, "--statusline", "--opencode", "--uninstall")
    assert json.loads((home / ".claude/settings.json").read_text())["statusLine"] == ORIG
    assert not (home / ".config/opencode/plugins/harness-habits.js").exists()
    assert not (data / "statusline_wrap.py").exists()


def test_no_prior_statusline_removed_on_uninstall(tmp_path):
    home = tmp_path / "home"
    run(home, "--statusline")
    assert "statusLine" in json.loads((home / ".claude/settings.json").read_text())
    run(home, "--statusline", "--uninstall")
    assert "statusLine" not in json.loads((home / ".claude/settings.json").read_text())


def test_opencode_skips_foreign_same_id(tmp_path):
    home = setup(tmp_path)
    plug = home / ".config/opencode/plugins"
    plug.mkdir(parents=True)
    (plug / "other.js").write_text('export default { id: "harness-habits", server() {} }')
    out = run(home, "--opencode")
    assert "skip" in out.lower()
    assert not (plug / "harness-habits.js").exists()


def test_claude_dry_run_prints_commands(tmp_path):
    home = setup(tmp_path)
    out = run(home, "--claude", "--claude-dev", "--dry-run")
    assert "claude plugin marketplace add mpankaj151/harness-habits" in out
    assert "claude plugin install harness-habits@harness-habits" in out
    assert f"claude --plugin-dir {ROOT}" in out


def test_codex_absent_notice(tmp_path):
    home = setup(tmp_path)
    out = run(home, "--codex")
    assert "codex" in out.lower() and "not" in out.lower()
    assert not (home / ".codex").exists()


def test_report_cron_dry_run(tmp_path):
    home = setup(tmp_path)
    before = snapshot(home)
    out = run(home, "--report-cron", "--dry-run")
    assert "weekly_report.py" in out
    assert snapshot(home) == before


def run_env(home, path, *args):
    env = {"PATH": path, "HOME": str(home)}
    p = subprocess.run([sys.executable, "-I", str(ROOT / "install.py"), *args],
                       capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def test_missing_claude_binary_does_not_abort(tmp_path):
    home = setup(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    # real home semantics are simulated by HOME only; claude is absent from PATH
    out = run_env(home, str(empty), "--home", str(home), "--claude", "--statusline", "--opencode")
    assert (home / ".config/opencode/plugins/harness-habits.js").exists()
    assert "statusline_wrap.py" in (home / ".claude/settings.json").read_text()
    assert "claude plugin install" in out


def test_missing_binary_on_real_home_path(tmp_path):
    # exercise the OSError branch directly
    sys.path.insert(0, str(ROOT))
    import importlib
    inst = importlib.import_module("install")
    ctx = inst.Ctx(tmp_path, False, False)
    old = os.environ["PATH"]
    os.environ["PATH"] = str(tmp_path)
    try:
        ctx.run(["claude", "plugin", "install", "x"])
    finally:
        os.environ["PATH"] = old


def test_custom_home_does_not_run_claude(tmp_path):
    home = setup(tmp_path)
    fake = tmp_path / "bin"
    fake.mkdir()
    marker = tmp_path / "ran"
    (fake / "claude").write_text(f"#!/bin/sh\ntouch {marker}\n")
    (fake / "claude").chmod(0o755)
    out = run_env(home, f"{fake}:{os.environ['PATH']}", "--home", str(home), "--claude")
    assert not marker.exists()
    assert "claude plugin install" in out


def test_claude_dev_silent_on_uninstall(tmp_path):
    home = setup(tmp_path)
    assert "--plugin-dir" not in run(home, "--claude-dev", "--uninstall")


def test_banner_copy_under_other_name_detected(tmp_path):
    home = setup(tmp_path)
    plug = home / ".config/opencode/plugins"
    plug.mkdir(parents=True)
    (plug / "copy.js").write_bytes((ROOT / "opencode/dist/harness-habits.js").read_bytes())
    out = run(home, "--opencode")
    assert "skip" in out.lower()
    assert not (plug / "harness-habits.js").exists()


def test_banner_file_at_target_is_overwritten(tmp_path):
    home = setup(tmp_path)
    plug = home / ".config/opencode/plugins"
    plug.mkdir(parents=True)
    (plug / "harness-habits.js").write_text("// harness-habits v0.0.1 old\n")
    run(home, "--opencode")
    assert (plug / "harness-habits.js").read_bytes() == (ROOT / "opencode/dist/harness-habits.js").read_bytes()


def test_uninstall_leaves_foreign_target(tmp_path):
    home = setup(tmp_path)
    plug = home / ".config/opencode/plugins"
    plug.mkdir(parents=True)
    (plug / "harness-habits.js").write_text("export default { id: 'mine' }")
    out = run(home, "--opencode", "--uninstall")
    assert (plug / "harness-habits.js").exists()
    assert "leaving" in out


def test_install_sh_relative_home(tmp_path):
    (tmp_path / "h").mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    p = subprocess.run([str(ROOT / "install.sh"), "--home", "./h", "--features", "handoff"],
                       cwd=tmp_path, capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "h/.config/harness-habits/features.json").exists()
