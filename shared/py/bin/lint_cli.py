"""Print size-lint findings; exit 1 under --strict when any."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import lint  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    findings = lint.lint(Path(args.cwd), Path.home())
    text = lint.format(findings)
    if text:
        print(text)
    sys.exit(1 if args.strict and findings else 0)


main()
