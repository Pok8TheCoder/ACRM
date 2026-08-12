#!/bin/bash
# ─────────────────────────────────────────────
# InfinityPane3 — start backend (FastAPI)
# Run from InfinityPane3/ root
# ─────────────────────────────────────────────
set -e

VENV="../../.venv"

if [ ! -d "$VENV" ]; then
  echo "❌  ACRM .venv not found at $VENV"
  echo "    Run: python3 -m venv ../../.venv && ../../.venv/bin/pip install -r ../../requirements.txt"
  exit 1
fi

echo "🚀  Starting InfinityPane3 backend on http://localhost:8000"
echo "    API docs: http://localhost:8000/docs"
echo "    WebSocket: ws://localhost:8000/ws/{institution_id}"
echo ""

cd backend
../../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
