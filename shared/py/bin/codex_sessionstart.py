"""Codex CLI SessionStart hook: size lint findings as plain stdout."""
import os
import sys
from pathlib import Path

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, ".."))
sys.path.insert(0, _here)  # installed layout: <data dir>/bin/harness_habits

from harness_habits import features, hookio, lint  # noqa: E402


@hookio.safe_main
def main():
    data = hookio.read_json_stdin()
    if data.get("source") not in (None, "startup", "clear") or not features.enabled("size-lint"):
        return
    text = lint.format(lint.lint(Path(data.get("cwd") or os.getcwd()), Path.home(), harness="codex"))
    if text:
        sys.stdout.write(text)


main()
