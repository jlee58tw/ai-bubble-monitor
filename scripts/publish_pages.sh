#!/usr/bin/env bash
# Regenerate the GitHub Pages static snapshot from the LOCAL DB and publish it
# to the gh-pages branch (normal commit + push, never force).
#   Usage: scripts/publish_pages.sh [--no-push]
# Result: https://jlee58tw.github.io/ai-bubble-monitor/  (static snapshot, NOT live)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_PATH="${PAGES_BASE_PATH:-/ai-bubble-monitor}"
WT="$ROOT/.pages-worktree"
PUSH=1; [[ "${1:-}" == "--no-push" ]] && PUSH=0

echo "[1/4] bake snapshot JSON/CSV from backend/data/aibm.db (in-process API, secret scan)"
( cd "$ROOT/backend" && ../.venv/bin/python ../scripts/pages/bake_snapshot.py )

echo "[2/4] static Next export (basePath=$BASE_PATH)"
( cd "$ROOT/frontend" && rm -rf .next-static && \
  STATIC_EXPORT=1 NEXT_PUBLIC_STATIC_SNAPSHOT=1 NEXT_PUBLIC_BASE_PATH="$BASE_PATH" npx next build )
git -C "$ROOT" checkout -- frontend/tsconfig.tsbuildinfo 2>/dev/null || true
OUT="$ROOT/frontend/.next-static"
[[ -f "$OUT/index.html" && -f "$OUT/snapshot/meta.json" ]] || { echo "export missing" >&2; exit 1; }

echo "[3/4] sync into gh-pages worktree"
git -C "$ROOT" fetch -q origin gh-pages 2>/dev/null || true
if [[ ! -d "$WT/.git" && ! -f "$WT/.git" ]]; then
  if git -C "$ROOT" rev-parse -q --verify origin/gh-pages >/dev/null; then
    git -C "$ROOT" worktree add -B gh-pages "$WT" origin/gh-pages
  else
    git -C "$ROOT" worktree add --orphan -b gh-pages "$WT"
  fi
fi
git -C "$WT" pull -q --ff-only origin gh-pages 2>/dev/null || true
find "$WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -a "$OUT"/. "$WT"/
rm -rf "$WT/cache" "$WT/types" "$WT/server" "$WT"/*.json.tmp 2>/dev/null || true
touch "$WT/.nojekyll"
# Defence in depth: refuse to publish if the local Tiingo token value appears (prints counts only).
ENVF="$ROOT/backend/.env"
if [[ -f "$ENVF" ]]; then
  TOK="$(grep -E '^TIINGO_API_KEY=' "$ENVF" | head -1 | cut -d= -f2- | tr -d '"' || true)"
  if [[ -n "$TOK" ]]; then
    HITS=$(grep -rlF -f <(printf "%s\n" "$TOK") "$WT" --exclude-dir=.git | wc -l || true)
    echo "token_scan files_with_hits=$HITS"
    [[ "$HITS" == "0" ]] || { echo "ABORT: secret found in export" >&2; exit 1; }
  fi
  unset TOK
fi

echo "[4/4] commit + push gh-pages"
STAMP="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["snapshot_at_taipei"])' "$WT/snapshot/meta.json")"
git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then echo "no changes"; else
  git -C "$WT" commit -q -m "Static snapshot $STAMP (Asia/Taipei)"
fi
if [[ $PUSH == 1 ]]; then git -C "$WT" push origin gh-pages; fi
echo "done: https://jlee58tw.github.io${BASE_PATH}/  (snapshot $STAMP Asia/Taipei)"
