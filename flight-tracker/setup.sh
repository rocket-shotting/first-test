#!/usr/bin/env bash
# One-shot setup + launch for the flight tracker web UI.
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
    echo "   (you can leave any of these blank and fill them in later from the Settings page)"

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
    echo "-- .env already exists, keeping it as-is (edit values anytime from the Settings page)"
fi

echo
echo "== Starting the web UI =="
echo "   Open this in your browser: http://127.0.0.1:5001"
echo "   Press Ctrl+C here to stop the server."
echo
python3 app.py
