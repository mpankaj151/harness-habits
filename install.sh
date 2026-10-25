#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "harness-habits: Python 3.11+ is required (found: $(python3 --version 2>&1 || echo none))" >&2
  exit 1
fi
exec python3 -I "$here/install.py" "$@"
