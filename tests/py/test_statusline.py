import json
import os
import subprocess
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "shared" / "py" / "bin" / "statusline_wrap.py"
PAYLOAD = {"model": {"display_name": "Opus"}, "cost": {"total_cost_usd": 1.234}, "context_window": {"used_percentage": 42.7}}


def run(tmp_path, cfg=None, stdin=None):
    cdir = tmp_path / "cfg" / "harness-habits"
    cdir.mkdir(parents=True, exist_ok=True)
    if cfg is not None:
        (cdir / "statusline.json").write_text(json.dumps(cfg))
    env = {"PATH": os.environ["PATH"], "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)}
    data = json.dumps(PAYLOAD).encode() if stdin is None else stdin
    t = time.time()
    p = subprocess.run([sys.executable, "-I", str(BIN)], input=data, capture_output=True, env=env, timeout=10)
    return p, time.time() - t


def test_no_wrapped_appends_model(tmp_path):
    p, _ = run(tmp_path)
    assert p.returncode == 0
    assert p.stdout.decode().strip() == "$1.23 · 42%  Opus"


def test_wrapped_string_first_line_and_same_stdin(tmp_path):
    p, _ = run(tmp_path, {"wrapped": "head -c 1 >/dev/null; echo first; echo second"})
    assert p.stdout.decode().strip() == "$1.23 · 42%  first"


def test_wrapped_receives_stdin(tmp_path):
    p, _ = run(tmp_path, {"wrapped": {"type": "command", "command": "python3 -c 'import sys,json;print(json.load(sys.stdin)[\"model\"][\"display_name\"])'"}})
    assert p.stdout.decode().strip() == "$1.23 · 42%  Opus"


def test_wrapped_timeout_prints_segment_only(tmp_path):
    p, elapsed = run(tmp_path, {"wrapped": "sleep 5"})
    assert p.stdout.decode().strip() == "$1.23 · 42%"
    assert elapsed < 4.5


def test_wrapped_failure_prints_segment_only(tmp_path):
    p, _ = run(tmp_path, {"wrapped": "exit 3"})
    assert p.stdout.decode().strip() == "$1.23 · 42%"


def test_malformed_stdin(tmp_path):
    p, _ = run(tmp_path, stdin=b"not json")
    assert p.returncode == 0
    assert p.stdout.decode().strip() == "$0.00 · 0%"


def test_segments_config(tmp_path):
    p, _ = run(tmp_path, {"segments": ["model", "cost"]})
    assert p.stdout.decode().startswith("Opus · $1.23")
