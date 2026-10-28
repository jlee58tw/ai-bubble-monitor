#!/usr/bin/env bash
# Idempotent local bring-up: venv + deps, backend/.env, SQLite DB (migrate; ingest only if empty),
# frontend deps + build, API on :8000 and web on :3000 (nohup), then health checks.
# Safe to re-run: every step is skipped when already done.
#   scripts/dev_up.sh            # bring everything up
#   scripts/dev_up.sh --test     # also run backend pytest
#   scripts/dev_up.sh --rebuild  # force `npm run build` and restart running services
# Env: SEC_CONTACT (email used if backend/.env must be created), API_PORT (8000), WEB_PORT (3000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"; WEB_PORT="${WEB_PORT:-3000}"
RUN_TESTS=0; REBUILD=0
for a in "$@"; do case "$a" in --test) RUN_TESTS=1;; --rebuild) REBUILD=1;; *) echo "unknown arg $a"; exit 2;; esac; done
log() { printf '\033[1;33m[dev_up]\033[0m %s\n' "$*"; }
port_up() { curl -s -o /dev/null --max-time 2 "http://localhost:$1${2:-/}"; }

# 1. Python venv + backend deps
if [ ! -x "$ROOT/.venv/bin/python" ]; then log "creating .venv"; python3 -m venv "$ROOT/.venv"; fi
PY="$ROOT/.venv/bin/python"
log "pip install backend deps (no-op if satisfied)"
"$PY" -m pip install -q --disable-pip-version-check -r "$ROOT/backend/requirements.txt"

# 2. backend/.env (never overwritten if present)
ENVF="$ROOT/backend/.env"
if [ ! -f "$ENVF" ]; then
  log "backend/.env missing -> creating from .env.example"; cp "$ROOT/.env.example" "$ENVF"
fi
if ! grep -qE '^SEC_USER_AGENT=.+@' "$ENVF"; then
  if [ -z "${SEC_CONTACT:-}" ]; then echo "SEC_USER_AGENT is empty in backend/.env; set SEC_CONTACT=you@example.com and re-run" >&2; exit 1; fi
  sed -i "s|^SEC_USER_AGENT=.*|SEC_USER_AGENT=AIBubbleMonitor/0.1 research-prototype contact: ${SEC_CONTACT}|" "$ENVF"
  log "set SEC_USER_AGENT contact to $SEC_CONTACT"
fi
log "$(grep '^SEC_USER_AGENT=' "$ENVF")"

# 3. Database: migrations are idempotent; ingest only when there is no data
cd "$ROOT/backend"; mkdir -p data
"$ROOT/.venv/bin/alembic" upgrade head
NOBS=$("$PY" - <<'PY'
from sqlalchemy import text
from app.db import get_engine
with get_engine().connect() as c: print(c.execute(text("select count(*) from observations")).scalar())
PY
)
if [ "$NOBS" -eq 0 ]; then
  log "DB empty -> ingesting (refresh, datasets, risk); respects source rate limits, takes a few minutes"
  "$PY" -m app.cli refresh; "$PY" -m app.cli datasets; "$PY" -m app.cli risk
else
  log "DB has $NOBS observations -> skipping ingest"
fi
[ "$RUN_TESTS" = 1 ] && { log "pytest"; "$ROOT/.venv/bin/pytest" -q; }

# 4. Frontend deps + build
cd "$ROOT/frontend"
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then log "npm ci"; npm ci --no-audit --no-fund; fi
if [ "$REBUILD" = 1 ] || [ ! -f .next/BUILD_ID ]; then
  log "npm run build"; NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:$API_PORT}" npm run build
fi

# 5. Services (nohup); restart only with --rebuild
if [ "$REBUILD" = 1 ]; then fuser -k "$API_PORT/tcp" "$WEB_PORT/tcp" 2>/dev/null || true; sleep 1; fi
if port_up "$API_PORT" /docs; then log "API already up on :$API_PORT"; else
  log "starting API :$API_PORT (log /tmp/aibm_api.log)"; cd "$ROOT/backend"
  nohup "$ROOT/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$API_PORT" > /tmp/aibm_api.log 2>&1 &
fi
if port_up "$WEB_PORT"; then log "web already up on :$WEB_PORT"; else
  log "starting web :$WEB_PORT (log /tmp/aibm_web.log)"; cd "$ROOT/frontend"
  nohup npm run start -- -p "$WEB_PORT" > /tmp/aibm_web.log 2>&1 &
fi

# 6. Health checks
for i in $(seq 1 30); do port_up "$API_PORT" /docs && port_up "$WEB_PORT" && break; sleep 1; done
fail=0
for u in "http://localhost:$API_PORT/docs" "http://localhost:$API_PORT/api/roi" \
         "http://localhost:$WEB_PORT/" "http://localhost:$WEB_PORT/roi" "http://localhost:$WEB_PORT/risk" \
         "http://localhost:$API_PORT/api/backtest?include_daily=false" "http://localhost:$WEB_PORT/backtest" "http://localhost:$WEB_PORT/ai-monetization" "http://localhost:$WEB_PORT/credit"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$u" || true); echo "  $c $u"; [ "$c" = 200 ] || fail=1
done
[ "$fail" = 0 ] && log "all up" || { log "some checks failed; see /tmp/aibm_api.log /tmp/aibm_web.log"; exit 1; }
