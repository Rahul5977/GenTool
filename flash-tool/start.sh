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
if ! python3 -m pip install -r requirements.txt -q; then
  echo "  ⚠  Dependency install failed; attempting httpx metadata cleanup…"
  STALE_HTTPX_DIST="$(python3 - <<'PY'
import importlib.metadata as m
for d in m.distributions():
    path = str(getattr(d, "_path", ""))
    name = (d.metadata.get("Name") or "").strip().lower()
    mv = (d.metadata.get("Metadata-Version") or "").strip()
    if "httpx-" in path and ".dist-info" in path and (not name or not mv):
        print(path)
        break
PY
)"
  if [ -n "$STALE_HTTPX_DIST" ] && [ -d "$STALE_HTTPX_DIST" ]; then
    rm -rf "$STALE_HTTPX_DIST"
  fi
  python3 -m pip install -r requirements.txt -q
fi

echo "  [2/4] Starting backend on :8020…"
cd "$ROOT"
EXISTING_BACKEND_PID="$(lsof -t -iTCP:8020 -sTCP:LISTEN 2>/dev/null | head -n 1)"
if [ -n "$EXISTING_BACKEND_PID" ]; then
  echo "  ⚠  Port 8020 already in use (PID: $EXISTING_BACKEND_PID) — stopping stale backend…"
  kill "$EXISTING_BACKEND_PID" 2>/dev/null || true
fi

# Wait until port is truly free (reload mode can leave child process briefly alive).
for _ in 1 2 3 4 5; do
  CURRENT_PID="$(lsof -t -iTCP:8020 -sTCP:LISTEN 2>/dev/null | head -n 1)"
  if [ -z "$CURRENT_PID" ]; then
    break
  fi
  kill "$CURRENT_PID" 2>/dev/null || true
  sleep 1
done

# Last-resort hard kill if a stale process still owns the port.
CURRENT_PID="$(lsof -t -iTCP:8020 -sTCP:LISTEN 2>/dev/null | head -n 1)"
if [ -n "$CURRENT_PID" ]; then
  echo "  ⚠  Port 8020 still busy (PID: $CURRENT_PID) — force stopping…"
  kill -9 "$CURRENT_PID" 2>/dev/null || true
  sleep 1
fi

uvicorn backend.main:app --reload --reload-dir "$ROOT/backend" --host 0.0.0.0 --port 8020 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "  [3/4] Installing frontend dependencies…"
cd "$ROOT/frontend"
if [ ! -f .env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8020" > .env.local
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
echo "  Backend  →  http://localhost:8020"
echo "  Frontend →  http://localhost:3000"
echo "  API docs →  http://localhost:8020/docs"
echo "  ─────────────────────────────────────────"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Keep script alive; kill both on exit
trap "echo '  Shutting down…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
