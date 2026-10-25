#!/usr/bin/env bash
# Smoke test: load the built plugin in a real OpenCode run and watch the output guard fire.
# Uses OPENCODE_CONFIG_DIR=<sandbox>; the real ~/.config/opencode is read for auth but never written.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SANDBOX="$HERE/.sandbox"
PROMPT=${1:-"Run exactly this shell command and show me the result: cat big.txt"}
LOG="$SANDBOX/last-run.log"

command -v opencode >/dev/null || { echo "opencode not found on PATH" >&2; exit 1; }
[ -f "$ROOT/opencode/dist/harness-habits.js" ] || { echo "run 'npm run build' in opencode/ first" >&2; exit 1; }

rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/plugins" "$SANDBOX/work"
cat > "$SANDBOX/opencode.json" <<'J'
{"$schema":"https://opencode.ai/config.json","model":"ollama/qwen3.8-fast"}
J
cp "$ROOT/opencode/dist/harness-habits.js" "$SANDBOX/plugins/harness-habits.js"
seq 1 800 | sed 's/^/line /' > "$SANDBOX/work/big.txt"

cd "$SANDBOX/work"
echo "starting opencode (log: $LOG) ..."
OPENCODE_CONFIG_DIR="$SANDBOX" opencode run --print-logs --log-level DEBUG "$PROMPT" >"$LOG" 2>&1 &
PID=$!
for _ in $(seq 1 90); do   # up to 180 s
  if grep -q "has 800 lines" "$LOG" 2>/dev/null; then sleep 5; break; fi
  kill -0 "$PID" 2>/dev/null || break
  sleep 2
done
kill "$PID" 2>/dev/null || true; sleep 1; kill -9 "$PID" 2>/dev/null || true

echo
echo "== proof lines =="
if ! grep -E 'service=harness-habits|has 800 lines|failed to load plugin|Failed to load plugin' "$LOG" | sed -E 's/timestamp=[^ ]+ //' | cut -c1-240; then
  echo "(no harness-habits lines: the plugin did not fire. Check $LOG)"
fi
