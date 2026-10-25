#!/usr/bin/env bash
# Smoke test: load the plugin in a real Claude Code run (`--plugin-dir`) and exercise the PreToolUse guard.
#   scenario 1: `grep -r foo .` is rewritten to `... | head -n 200` (the model sees 200 lines)
#   scenario 2: `cat big.txt` (800 lines) is denied with "more than 500 lines"
# Uses the real `claude` CLI and its login (a few cents on --model haiku), in a temp working directory.
# XDG_CONFIG_HOME / XDG_DATA_HOME point at a temp dir so no real harness-habits config is read or written.
# Exit codes: 0 both proofs seen (or `claude` not installed: skipped), 1 a proof is missing.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)

command -v claude >/dev/null || { echo "SKIP: claude not found on PATH" >&2; exit 0; }
command -v jq >/dev/null || { echo "jq not found on PATH" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/cwd" "$WORK/xdg-config" "$WORK/xdg-data"
export XDG_CONFIG_HOME="$WORK/xdg-config" XDG_DATA_HOME="$WORK/xdg-data"
unset HH_FEATURE_OUTPUT_GUARD CLAUDE_PLUGIN_OPTION_OUTPUT_GUARD
seq 1 300 | sed 's/^/foo /' > "$WORK/cwd/notes.txt"
seq 1 800 | sed 's/^/row /' > "$WORK/cwd/big.txt"
cd "$WORK/cwd"

ask() {
  claude -p "$1" --plugin-dir "$ROOT" --model haiku --allowedTools Bash --output-format json </dev/null | jq -r '.result // empty'
}

FAIL=0

echo "== scenario 1: bounded rewrite =="
R1=$(ask "Run exactly this shell command once, with no pipes or extra arguments: grep -r foo .  Then reply with only the number of output lines the tool result contained.")
echo "result: $R1"
case "$R1" in *200*) echo "PROOF: rewrite applied (200 lines)";; *) echo "MISSING: expected 200 in the result"; FAIL=1;; esac

echo "== scenario 2: oversized cat denied =="
R2=$(ask "Run exactly: cat big.txt  If the tool call is refused, quote the refusal message verbatim; otherwise report the first line of output.")
echo "result: $R2"
case "$R2" in *"more than 500 lines"*) echo "PROOF: deny message seen";; *) echo "MISSING: expected 'more than 500 lines' in the result"; FAIL=1;; esac

exit "$FAIL"
