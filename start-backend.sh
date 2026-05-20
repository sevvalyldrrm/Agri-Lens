#!/usr/bin/env zsh
# ─────────────────────────────────────────
# start-backend.sh  –  Run FastAPI backend
# Usage: ./start-backend.sh
# ─────────────────────────────────────────
set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR/backend"

# Activate venv if present
if [[ -f venv/bin/activate ]]; then
  source venv/bin/activate
  echo "✅ venv activated"
fi

echo "🚀 Starting Agri-Lens backend on http://localhost:8000 ..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
