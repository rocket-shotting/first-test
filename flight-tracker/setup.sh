#!/usr/bin/env bash
# One-shot setup + test run for the flight tracker.
# Usage: bash setup.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "== Flight Tracker setup =="

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install it from https://python.org first, then re-run this script."
    exit 1
fi

if [ ! -d .venv ]; then
    echo "-- creating virtual environment (.venv)"
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "-- installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f .env ]; then
    echo
    echo "== Enter your credentials (input is hidden for secrets) =="

    read -r -p "SerpApi key (from https://serpapi.com/manage-api-key): " SERPAPI_KEY
    read -r -p "Gmail address that will SEND alerts: " EMAIL_ADDRESS
    read -r -s -p "Gmail App Password (from https://myaccount.google.com/apppasswords): " EMAIL_APP_PASSWORD
    echo
    read -r -p "Email address to RECEIVE alerts [default: same as sender]: " NOTIFY_EMAIL
    NOTIFY_EMAIL=${NOTIFY_EMAIL:-$EMAIL_ADDRESS}

    cat > .env <<EOF
SERPAPI_KEY=$SERPAPI_KEY
EMAIL_ADDRESS=$EMAIL_ADDRESS
EMAIL_APP_PASSWORD=$EMAIL_APP_PASSWORD
NOTIFY_EMAIL=$NOTIFY_EMAIL
EOF
    echo "-- wrote .env"
else
    echo "-- .env already exists, keeping it as-is"
fi

echo
echo "== Edit config.json now if you want different routes/dates =="
echo "   (current routes:)"
python3 - <<'PY'
import json
with open("config.json", encoding="utf-8") as f:
    cfg = json.load(f)
for r in cfg["routes"]:
    print(f"   - {r['name']}: {r['departure_id']} -> {r['arrival_id']} on {r['outbound_date']}"
          + (f" ~ {r['return_date']}" if r.get('return_date') else "")
          + f" ({r.get('cabin', 'economy')})")
PY

read -r -p $'\nPress Enter to run a console-only test check now (no email sent)...'
python3 check_flights.py --no-email

echo
read -r -p "Run again with email alerts enabled? [y/N] " send_email
if [[ "$send_email" =~ ^[Yy]$ ]]; then
    python3 check_flights.py
fi

echo
echo "Done. To run checks later:"
echo "  cd $(pwd)"
echo "  source .venv/bin/activate"
echo "  python3 check_flights.py"
