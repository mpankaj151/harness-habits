#!/usr/bin/env bash
# Smoke test: load the built plugin in a real OpenCode run.
#   scenario 1: the output guard rewrites/denies a big cat
#   scenario 2: idle compaction is forced (absoluteTokens=1) and a handoff note is written
# Uses OPENCODE_CONFIG_DIR=<sandbox>; the real ~/.config/opencode is read for auth but never written.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SANDBOX="$HERE/.sandbox"
PROMPT=${1:-"Run exactly this shell command and show me the result: cat big.txt"}
LOG="$SANDBOX/last-run.log"
LOG2="$SANDBOX/last-run-compaction.log"

# Keep the system prompt small so a local model answers in reasonable time.
export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 OPENCODE_DISABLE_EXTERNAL_SKILLS=1 OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1 OPENCODE_DISABLE_DEFAULT_PLUGINS=1
POLL=150   # x 2 s = 300 s

command -v opencode >/dev/null || { echo "opencode not found on PATH" >&2; exit 1; }
[ -f "$ROOT/opencode/dist/harness-habits.js" ] || { echo "run 'npm run build' in opencode/ first" >&2; exit 1; }

rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/plugins" "$SANDBOX/work" "$SANDBOX/xdg/harness-habits"
# XDG_CONFIG_HOME is redirected below, so OpenCode no longer sees ~/.config/opencode: copy only the
# provider and model settings from it (read-only) into the sandbox config.
python3 - "$HOME/.config/opencode/opencode.json" "$SANDBOX/opencode.json" <<'PY'
import json, sys
cfg = {"$schema": "https://opencode.ai/config.json", "model": "ollama/qwen3.8-fast"}
try:
    real = json.load(open(sys.argv[1]))
    for k in ("provider", "model"):
        if k in real:
            cfg[k] = real[k]
except Exception:
    pass
json.dump(cfg, open(sys.argv[2], "w"))
PY
cp "$ROOT/opencode/dist/harness-habits.js" "$SANDBOX/plugins/harness-habits.js"
# its own git repo, so OpenCode treats the sandbox work dir (not this repo) as the worktree
git init -q "$SANDBOX/work"
seq 1 800 | sed 's/^/line /' > "$SANDBOX/work/big.txt"

# wait_for <log> <pid> <pattern>: poll up to 300 s, then 5 s grace
wait_for() {
  for _ in $(seq 1 "$POLL"); do
    if grep -q "$3" "$1" 2>/dev/null; then sleep 5; return 0; fi
    kill -0 "$2" 2>/dev/null || return 1
    sleep 2
  done
  return 1
}
stop() { kill "$1" 2>/dev/null || true; sleep 1; kill -9 "$1" 2>/dev/null || true; }

cd "$SANDBOX/work"

echo "== scenario 1: output guard (log: $LOG) =="
# XDG_CONFIG_HOME points at the sandbox so the real ~/.config/harness-habits is never read or written.
XDG_CONFIG_HOME="$SANDBOX/xdg" OPENCODE_CONFIG_DIR="$SANDBOX" opencode run --print-logs --log-level DEBUG "$PROMPT" >"$LOG" 2>&1 &
PID=$!
wait_for "$LOG" "$PID" "more than 500 lines" || echo "(scenario 1: proof line not seen before timeout or exit)"
stop "$PID"

echo "== scenario 2: forced idle compaction (log: $LOG2) =="
cat > "$SANDBOX/xdg/harness-habits/opencode.json" <<'J'
{"features":{"idle-compaction":true},"compaction":{"absoluteTokens":1,"disableForProviders":[]},"debounceMs":0}
J
XDG_CONFIG_HOME="$SANDBOX/xdg" OPENCODE_CONFIG_DIR="$SANDBOX" opencode run --print-logs --log-level DEBUG "Reply with the single word: ok" >"$LOG2" 2>&1 &
PID=$!
wait_for "$LOG2" "$PID" "compacted the session" || echo "(scenario 2: proof line not seen before timeout or exit)"
stop "$PID"

echo
echo "== proof lines: output guard =="
if ! grep -E 'service=harness-habits|more than 500 lines|failed to load plugin|Failed to load plugin' "$LOG" | sed -E 's/timestamp=[^ ]+ //' | cut -c1-240; then
  echo "(no harness-habits lines: the plugin did not fire. Check $LOG)"
fi
echo
echo "== proof lines: idle compaction =="
echo "compacted-the-session lines: $(grep -c 'compacted the session' "$LOG2" || true)"
grep -E 'compacted the session|harness-habits.*(failed|error)' "$LOG2" | sed -E 's/timestamp=[^ ]+ //' | cut -c1-240 || echo "(no compaction line. Check $LOG2)"
if ls "$SANDBOX"/work/.opencode/handoff/*.md >/dev/null 2>&1; then
  echo "handoff note: $(ls "$SANDBOX"/work/.opencode/handoff/*.md)"
  echo "exclude entry: $(grep -c '^.opencode/handoff/$' "$SANDBOX/work/.git/info/exclude" 2>/dev/null || true)"
else
  echo "(no handoff note under $SANDBOX/work/.opencode/handoff)"
fi
