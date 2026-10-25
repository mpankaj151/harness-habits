"""Claude Code PreCompact hook: write a session snapshot (never blocks)."""
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, ".."))
sys.path.insert(0, here)

from harness_habits import hookio  # noqa: E402
from _snapshot import write_snapshot  # noqa: E402


@hookio.safe_main
def main():
    write_snapshot()


main()
