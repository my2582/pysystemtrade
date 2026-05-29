#!/bin/bash
# PostToolUse hook: lint pre-registration files after Edit/Write.
# Reads Claude Code hook JSON from stdin; runs validate_preregistration.py
# on the file if it matches the pre-reg pattern. Non-blocking (prints to stderr
# so user sees output without aborting Claude's loop).
#
# Wired in .claude/settings.json under hooks.PostToolUse matcher "Edit|Write".

set -euo pipefail

# Read hook payload from stdin
PAYLOAD="$(cat)"

# Extract file_path using python (jq not assumed)
FILE_PATH="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys, json; data = json.load(sys.stdin); print(data.get("tool_input", {}).get("file_path", ""))' 2>/dev/null || echo "")"

# Only lint pre-registration files inside ars/evidence_packs/
case "$FILE_PATH" in
  */ars/evidence_packs/*/*_preregistration.md)
    PROJ="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    PY="$PROJ/venv/bin/python"
    SCRIPT="$PROJ/scripts/validate_preregistration.py"
    if [ -x "$PY" ] && [ -f "$SCRIPT" ]; then
      OUTPUT="$("$PY" "$SCRIPT" "$FILE_PATH" 2>&1 || true)"
      # If there are any violations, surface them to stderr so the agent + user see them
      if echo "$OUTPUT" | grep -qE '\[FAIL\]|\[WARN\]'; then
        echo "[ars-citation-lint] pre-registration lint on $FILE_PATH:" >&2
        echo "$OUTPUT" >&2
      fi
    fi
    ;;
esac

exit 0
