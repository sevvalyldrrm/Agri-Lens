#!/usr/bin/env zsh
# ─────────────────────────────────────────
# start-mobile.sh  –  Serve Mobile UI
# Usage: ./start-mobile.sh
# ─────────────────────────────────────────
set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR/mobile"

echo "📱 Starting Agri-Lens mobile UI on http://localhost:3000 ..."

# Prefer Python 3
if command -v python3 &>/dev/null; then
  python3 -m http.server 3000
else
  python -m http.server 3000
fi
