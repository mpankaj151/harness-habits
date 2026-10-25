"""Codex CLI PreCompact hook: write a handoff note (never blocks)."""
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, ".."))
sys.path.insert(0, here)

from harness_habits import hookio  # noqa: E402
from _codex_handoff import write_handoff  # noqa: E402


@hookio.safe_main
def main():
    write_handoff()


main()
