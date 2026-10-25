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
