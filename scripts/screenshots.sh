#!/usr/bin/env bash
# Refresh docs/screenshot_*.png with headless Chrome (services must be up: scripts/dev_up.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
WEB=${WEB:-http://localhost:3000}
CHROME=${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser)}
pages="overview: risk alerts capex valuation supply_chain:supply-chain pricing benchmarks roi methodology pipeline backtest events watchlist ai_monetization:ai-monetization credit"
for p in $pages; do
  name=${p%%:*}; path=${p#*:}; [ "$p" = "$name" ] && path=$name; [ "$name" = overview ] && path=""
  h=1800; case $name in backtest|events|methodology|ai_monetization) h=3200;; esac
  "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars --window-size=1600,$h \
    --virtual-time-budget=15000 --screenshot="docs/screenshot_${name}.png" "$WEB/$path" >/dev/null 2>&1
  echo "docs/screenshot_${name}.png <- $WEB/$path"
done
