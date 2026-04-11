#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  Flash Tool v2 — SuperLiving Ad Pipeline"
echo "  ─────────────────────────────────────────"
echo ""

# ── Backend ─────────────────────────────────────────────────────────────────
echo "  [1/4] Installing backend dependencies…"
cd "$ROOT/backend"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  ⚠  Created backend/.env from .env.example — add your GOOGLE_API_KEY"
fi
pip install -r requirements.txt -q

echo "  [2/4] Starting backend on :8000…"
cd "$ROOT"
uvicorn backend.main:app --reload --reload-dir "$ROOT/backend" --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "  [3/4] Installing frontend dependencies…"
cd "$ROOT/frontend"
if [ ! -f .env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
  echo "  Created frontend/.env.local"
fi
npm install --silent

echo "  [4/4] Starting frontend on :3000…"
npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# ── Info ─────────────────────────────────────────────────────────────────────
echo ""
echo "  ─────────────────────────────────────────"
echo "  Backend  →  http://localhost:8000"
echo "  Frontend →  http://localhost:3000"
echo "  API docs →  http://localhost:8000/docs"
echo "  ─────────────────────────────────────────"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Keep script alive; kill both on exit
trap "echo '  Shutting down…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
