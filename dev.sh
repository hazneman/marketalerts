#!/usr/bin/env bash
# Market Alerts local runner. Menu-driven: scan + dashboard without memorizing
# commands. First run bootstraps the Python venv and npm deps automatically.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

bootstrap() {
  if [ ! -d "$ROOT/scanner/.venv" ]; then
    echo "Creating scanner venv + installing deps (first run)…"
    python3 -m venv "$ROOT/scanner/.venv"
    "$ROOT/scanner/.venv/bin/pip" install -q -r "$ROOT/scanner/requirements.txt"
  fi
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "Installing frontend deps (first run)…"
    (cd "$ROOT/frontend" && npm install)
  fi
}

dashboard() {
  # Free the port first so this doubles as a restart.
  lsof -ti:3100 2>/dev/null | xargs kill -9 2>/dev/null || true
  echo ""
  echo "  Dashboard  →  http://localhost:3100   (Ctrl+C to stop)"
  echo ""
  ( sleep 3; open "http://localhost:3100" ) &
  (cd "$ROOT/frontend" && npm run dev)
}

echo ""
echo "  Market Alerts"
echo "  1) Quick scan (10 tickers) + dashboard"
echo "  2) Full scan (~517 tickers, ~5 min) + dashboard"
echo "  3) Dashboard only"
echo "  4) Run tests"
echo ""
read -rp "  Choose [1-4]: " choice

bootstrap
case "$choice" in
  1) "$ROOT/scanner/.venv/bin/python" "$ROOT/scanner/scan.py" --limit 10; dashboard ;;
  2) "$ROOT/scanner/.venv/bin/python" "$ROOT/scanner/scan.py"; dashboard ;;
  3) dashboard ;;
  4) "$ROOT/scanner/.venv/bin/python" -m pytest "$ROOT/scanner/tests" -q ;;
  *) echo "Unknown choice"; exit 1 ;;
esac
