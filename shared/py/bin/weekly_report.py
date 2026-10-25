"""Weekly cost report. Usage: weekly_report.py [--since 7d] [--format md|json] [--write]."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import report  # noqa: E402
from harness_habits.hookio import warn  # noqa: E402
from harness_habits.paths import data_dir  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="7d")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--registry", default=str(Path.home() / ".session-browser" / "registry.db"))
    ap.add_argument("--usage-log", default=str(data_dir() / "opencode-usage.jsonl"))
    ap.add_argument("--claude-projects", default=str(Path.home() / ".claude" / "projects"))
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    try:
        since = report.parse_since(a.since, now)
    except ValueError as e:
        ap.error(str(e))
    shipped = Path(__file__).resolve().parents[2] / "pricing.json"
    pricing = report.load_pricing(data_dir(), shipped)
    try:
        data = report.build(Path(a.registry), Path(a.usage_log), Path(a.claude_projects), since, pricing)
    except Exception as e:  # unreadable registry etc.
        warn(f"cost report failed: {e}")
        return 1
    iso = now.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    text = json.dumps(data, indent=2) + "\n" if a.format == "json" else report.render_md(data, week)
    if a.write:
        out = data_dir() / "reports" / f"{week}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.render_md(data, week) if a.format == "json" else text)
        warn(f"wrote {out}")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
