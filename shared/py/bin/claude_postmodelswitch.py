"""Claude Code PostModelSwitch hook: plain stdout reaches the model."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from harness_habits import features, hookio  # noqa: E402


@hookio.safe_main
def main():
    hookio.read_json_stdin()
    if features.enabled("cache-break"):
        sys.stdout.write("Model switched; the prompt cache is per model, so this first turn re-reads the full context at full price.")


main()
