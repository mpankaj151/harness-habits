import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_habits import report

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "transcripts" / "usage.jsonl"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

SCHEMA = """CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY, project_path TEXT, cwd TEXT, folder_name TEXT,
    start_time TEXT, last_activity TEXT, first_message TEXT, summary TEXT,
    topics TEXT, session_type TEXT, outcome TEXT, turn_count INTEGER DEFAULT 0
, title TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, model_used TEXT, models_used TEXT, cli_source TEXT NOT NULL DEFAULT 'claude', cli_version TEXT, archived INTEGER NOT NULL DEFAULT 0, notes TEXT, end_logged_at TIMESTAMP, cost_usd REAL, enriched_at TIMESTAMP, reasoning_path TEXT, archived_reason TEXT, archived_at TIMESTAMP);"""


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    for r in rows:
        con.execute(
            "INSERT INTO sessions (session_id,title,folder_name,cli_source,model_used,last_activity,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?)", r)
    con.commit()
    con.close()


ROWS = [
    ("s1", "one", "projA", "claude", "claude-sonnet-5-5", "2026-10-24T10:00:00.000Z", 100, 10, 800, 100, 5.0),
    ("s2", "two", "projB", "codex", "gpt-x", "2026-10-23T10:00:00.000Z", 50, 5, 0, 0, 2.0),
    ("s3", "three", "projC", "opencode", "gpt-x", "2026-10-22T10:00:00.000Z", 10, 1, 0, 0, None),
    ("s4", "epoch", "projD", "claude", "claude-sonnet-5-5", str(int(datetime(2026, 10, 21, tzinfo=timezone.utc).timestamp())), 0, 0, 0, 0, 1.0),
    ("s5", "old", "projE", "claude", "claude-sonnet-5-5", "2026-01-01T00:00:00Z", 1, 1, 1, 1, 100.0),
]


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "registry.db"
    make_db(p, ROWS)
    return p


def test_parse_since():
    assert report.parse_since("7d", NOW) == datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    assert report.parse_since("30d", NOW) == datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    assert report.parse_since("2026-10-01", NOW) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        report.parse_since("banana", NOW)


def test_parse_ts_handles_iso_epoch_and_junk():
    iso = report.parse_ts("2026-10-24T10:00:00.000Z")
    assert iso == datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    assert report.parse_ts(1761300000) == report.parse_ts("1761300000") == report.parse_ts(1761300000000)
    assert report.parse_ts(None) is None and report.parse_ts("nope") is None


def test_registry_totals_sources_models_top(db):
    sec = report.registry_section(db, report.parse_since("7d", NOW))
    assert sec["sessions"] == 4  # s5 outside window
    assert sec["by_source"]["claude"]["cost"] == 6.0
    assert sec["by_source"]["codex"]["cost"] == 2.0
    assert sec["by_source"]["opencode"]["cost"] == 0.0  # NULL cost counts as 0
    assert sec["by_source"]["opencode"]["sessions"] == 1
    assert sec["by_model"]["gpt-x"]["sessions"] == 2
    assert [t["session_id"] for t in sec["top"]] == ["s1", "s2", "s4"]  # NULL cost excluded
    assert sec["cache_hit_ratio"] == pytest.approx(800 / (160 + 800 + 100))


def test_zero_division_guard(tmp_path):
    p = tmp_path / "r.db"
    make_db(p, [("z", "t", "f", "claude", "m", "2026-10-24T00:00:00Z", 0, 0, 0, 0, 1.0)])
    sec = report.registry_section(p, report.parse_since("7d", NOW))
    assert sec["cache_hit_ratio"] == 0.0


def test_registry_opened_read_only(db):
    before = db.read_bytes()
    report.registry_section(db, report.parse_since("7d", NOW))
    assert db.read_bytes() == before
    assert not list(db.parent.glob("registry.db-*"))


def test_top_limited_to_ten(tmp_path):
    p = tmp_path / "r.db"
    make_db(p, [(f"s{i}", "t", "f", "claude", "m", "2026-10-24T00:00:00Z", 1, 1, 1, 1, float(i)) for i in range(15)])
    sec = report.registry_section(p, report.parse_since("7d", NOW))
    assert len(sec["top"]) == 10 and sec["top"][0]["cost"] == 14.0


def test_usage_log_section(tmp_path):
    log = tmp_path / "u.jsonl"
    lines = [
        {"ts": "2026-10-24T00:00:00Z", "sessionID": "a", "messageID": "1", "providerID": "openai", "modelID": "gpt", "cost": 0.5, "tokens_last_step": {}},
        {"ts": "2026-10-24T01:00:00Z", "sessionID": "a", "messageID": "2", "providerID": "openai", "modelID": "gpt", "cost": 0.25, "tokens_last_step": {}},
        {"ts": "2026-10-24T01:00:00Z", "sessionID": "a", "messageID": "3", "providerID": "anthropic", "modelID": "c", "cost": 1.0},
        {"ts": "2020-01-01T00:00:00Z", "providerID": "openai", "modelID": "gpt", "cost": 50},
    ]
    log.write_text("\n".join(json.dumps(l) for l in lines) + "\nbad line\n")
    sec = report.usage_section(log, report.parse_since("7d", NOW))
    assert sec["by_model"]["openai/gpt"] == {"messages": 2, "cost": 0.75}
    assert sec["by_model"]["anthropic/c"]["messages"] == 1
    assert report.usage_section(tmp_path / "missing.jsonl", report.parse_since("7d", NOW)) is None


def test_transcript_fallback_dedupes_and_prices(tmp_path):
    proj = tmp_path / "projects" / "-proj"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(FIX.read_text())
    pricing = {"claude-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
               "default": {"input": 1.0, "output": 1.0, "cache_read": 1.0, "cache_write": 1.0}}
    sec = report.transcript_section(tmp_path / "projects", report.parse_since("7d", NOW), pricing)
    assert sec["estimated"] is True
    assert sec["messages"] == 3  # msg_1 deduped (last kept), msg_old filtered by since
    sonnet = sec["by_model"]["claude-sonnet-5-5"]
    assert sonnet["output_tokens"] == 50  # last occurrence of msg_1
    assert sonnet["cost"] == pytest.approx((100 * 3 + 50 * 15 + 1000 * 0.3 + 200 * 3.75) / 1e6)
    assert sec["by_model"]["claude-opus-9-9"]["cost"] == pytest.approx(30 / 1e6)  # default entry
    assert "(unknown)" in sec["by_model"]


def test_pricing_longest_prefix_and_default():
    p = {"claude": {"input": 1, "output": 1, "cache_read": 1, "cache_write": 1},
         "claude-opus": {"input": 9, "output": 9, "cache_read": 9, "cache_write": 9},
         "default": {"input": 5, "output": 5, "cache_read": 5, "cache_write": 5}}
    assert report.price_for("claude-opus-4", p)["input"] == 9
    assert report.price_for("gpt", p)["input"] == 5
    assert report.price_for("x", {})["input"] >= 0  # built-in default


def run_cli(tmp_path, *extra, env_extra=None):
    env = {"PATH": "/usr/bin:/bin", "XDG_DATA_HOME": str(tmp_path / "data"), "HOME": str(tmp_path / "home")}
    return subprocess.run([sys.executable, "-I", str(ROOT / "shared/py/bin/weekly_report.py"), *extra],
                          capture_output=True, text=True, env=env)


def test_cli_md_sections_separate_and_write(tmp_path, db):
    log = tmp_path / "u.jsonl"
    log.write_text(json.dumps({"ts": "2999-01-01T00:00:00Z", "providerID": "p", "modelID": "m", "cost": 3.0}) + "\n")
    r = run_cli(tmp_path, "--since", "2026-01-01", "--registry", str(db), "--usage-log", str(log), "--write")
    assert r.returncode == 0, r.stderr
    assert "Session-browser registry" in r.stdout and "OpenCode usage log" in r.stdout
    assert "never summed" in r.stdout.lower() or "not added" in r.stdout.lower()
    written = list((tmp_path / "data" / "harness-habits" / "reports").glob("*-W*.md"))
    assert len(written) == 1 and "Session-browser registry" in written[0].read_text()


def test_cli_json_and_fallback(tmp_path):
    proj = tmp_path / "projects" / "-p"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(FIX.read_text())
    r = run_cli(tmp_path, "--since", "2026-01-01", "--format", "json", "--registry", str(tmp_path / "none.db"),
                "--usage-log", str(tmp_path / "none.jsonl"), "--claude-projects", str(tmp_path / "projects"))
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["registry"] is None and data["usage_log"] is None
    assert data["transcripts"]["estimated"] is True
    r2 = run_cli(tmp_path, "--since", "2026-01-01", "--registry", str(tmp_path / "none.db"),
                 "--usage-log", str(tmp_path / "none.jsonl"), "--claude-projects", str(tmp_path / "projects"))
    assert "(estimated)" in r2.stdout


def test_cli_bad_since(tmp_path):
    r = run_cli(tmp_path, "--since", "banana")
    assert r.returncode != 0


def test_installed_layout_runs_under_isolated_python(tmp_path):
    import shutil
    bindir = tmp_path / "data" / "bin"
    shutil.copytree(ROOT / "shared/py/bin", bindir, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "shared/py/harness_habits", bindir / "harness_habits", ignore=shutil.ignore_patterns("__pycache__"))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "home"), "XDG_DATA_HOME": str(tmp_path / "xdg")}
    r = subprocess.run([sys.executable, "-I", str(bindir / "weekly_report.py"), "--since", "7d", "--format", "json",
                        "--registry", str(tmp_path / "none.db"), "--claude-projects", str(tmp_path / "none")],
                       capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "registry" in json.loads(r.stdout)


def test_load_pricing_order_and_fallthrough(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    shipped = tmp_path / "shipped.json"
    shipped.write_text(json.dumps({"default": {"input": 2}}))
    assert report.load_pricing(data, shipped) == {"default": {"input": 2}}  # shipped copy
    (data / "pricing.json").write_text(json.dumps({"default": {"input": 1}}))
    assert report.load_pricing(data, shipped) == {"default": {"input": 1}}  # data dir wins
    (data / "pricing.json").write_text("{not json")
    assert report.load_pricing(data, shipped) == {"default": {"input": 2}}  # malformed falls through
    shipped.write_text("[1]")
    assert report.load_pricing(data, shipped) == {"default": report.DEFAULT_PRICE}  # built-in
    assert report.load_pricing(data, tmp_path / "missing.json") == {"default": report.DEFAULT_PRICE}
