#!/usr/bin/env bash
# Usage:
#   ./dashboard.sh          → load the latest run
#   ./dashboard.sh <RUN_ID> → load a specific run

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNS_DIR="$ROOT/results/runs"
DASH_DIR="$ROOT/scripts/dashboard"

# Resolve run ID (arg or latest)
if [ -n "$1" ]; then
  RUN_ID="$1"
else
  RUN_ID=$(ls -1 "$RUNS_DIR" | sort | tail -1)
fi

if [ -z "$RUN_ID" ] || [ ! -d "$RUNS_DIR/$RUN_ID" ]; then
  echo "❌  Run not found: '$RUN_ID'" && exit 1
fi

# Link data
rm -f "$DASH_DIR/data"
ln -sf "$RUNS_DIR/$RUN_ID" "$DASH_DIR/data"

# Restart server
pkill -f "http.server 8889" 2>/dev/null; sleep 0.5
cd "$DASH_DIR" && python3 -m http.server 8889 --bind 127.0.0.1 &>/dev/null &

echo "✅  Dashboard → http://localhost:8889  (run: $RUN_ID)"
open http://localhost:8889
