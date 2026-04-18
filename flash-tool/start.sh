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
  echo "  ⚠  Dependency install failed; retrying with --ignore-installed…"
  if ! python3 -m pip install -r requirements.txt -q --ignore-installed; then
    echo "  ⚠  Still failing; removing broken httpx dist-info trees…"
    while IFS= read -r bad_path; do
      [ -z "$bad_path" ] && continue
      [ -d "$bad_path" ] && rm -rf "$bad_path" && echo "  Removed: $bad_path"
    done < <(python3 - <<'PY'
import importlib.metadata as m
from pathlib import Path

seen = set()
for dist in m.distributions():
    meta = Path(str(getattr(dist, "_path", "")))
    if ".dist-info" not in str(meta):
        continue
    name = (dist.metadata.get("Name") or "").strip().lower()
    if name != "httpx" and "httpx" not in meta.name.lower():
        continue
    record = meta / "RECORD"
    meta_ver = (dist.metadata.get("Metadata-Version") or "").strip()
    if not record.is_file() or not name or not meta_ver:
        s = str(meta.resolve())
        if s not in seen:
            seen.add(s)
            print(s)
PY
)
    python3 -m pip install -r requirements.txt -q
  fi
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

# First free port in range (avoids Next silently jumping to 3001 while we still print 3000).
FRONTEND_PORT=""
for p in 3000 3001 3002 3003 3004 3005; do
  if [ -z "$(lsof -t -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | head -n 1)" ]; then
    FRONTEND_PORT=$p
    break
  fi
done
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

echo "  [4/4] Starting frontend on :${FRONTEND_PORT}…"
npm run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# ── Info ─────────────────────────────────────────────────────────────────────
echo ""
echo "  ─────────────────────────────────────────"
echo "  Backend  →  http://localhost:8020"
echo "  Frontend →  http://localhost:${FRONTEND_PORT}"
echo "  API docs →  http://localhost:8020/docs"
echo "  ─────────────────────────────────────────"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Keep script alive; kill both on exit
trap "echo '  Shutting down…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
