"""Claude Code status line: cost and context segment, optionally wrapping another status line."""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, ".."))
sys.path.insert(0, _here)  # installed layout: <data dir>/bin/harness_habits

from harness_habits import hookio, statusline  # noqa: E402


@hookio.safe_main
def main():
    raw = sys.stdin.buffer.read()
    sys.stdout.write(statusline.render(raw, statusline.load_config()) + "\n")


main()
