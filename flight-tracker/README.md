# Flight Tracker

Tracks flight prices via [SerpApi's Google Flights engine](https://serpapi.com/google-flights-api),
prints results to the console, and emails an alert (Gmail SMTP) when a price
hits your threshold or drops from the last check.

## Setup

```bash
cd flight-tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `SERPAPI_KEY` | https://serpapi.com/manage-api-key (free tier: 250 searches/month) |
| `EMAIL_ADDRESS` | The Gmail address that sends the alert |
| `EMAIL_APP_PASSWORD` | https://myaccount.google.com/apppasswords (requires 2-Step Verification on) |
| `NOTIFY_EMAIL` | Address that receives alerts (can equal `EMAIL_ADDRESS`) |

## Configure routes

Edit `config.json`:

```json
{
  "currency": "KRW",
  "routes": [
    {
      "name": "ICN-NRT",
      "departure_id": "ICN",
      "arrival_id": "NRT",
      "outbound_date": "2026-10-20",
      "return_date": "2026-10-24",
      "cabin": "economy",
      "adults": 1,
      "price_alert_threshold": 300000
    }
  ]
}
```

- Omit `return_date` for a one-way search.
- `cabin`: `economy` | `premium_economy` | `business` | `first`.
- `price_alert_threshold`: alert fires when the cheapest price is at or below
  this value. An alert also fires any time the price drops versus the
  previous check, regardless of threshold.

## Run

```bash
python check_flights.py            # check all routes, email on alert
python check_flights.py --no-email # console only, never sends mail
python check_flights.py --route ICN-NRT
```

Price history is kept in `price_history.json` (gitignored) so the script can
detect drops between runs.

## Quota math (free tier: 250 searches/month)

```
monthly searches = number of routes × runs per day × 30
```

The bundled GitHub Actions workflow runs **once a day**, so:

| Routes tracked | Searches/month | Fits free tier? |
|---|---|---|
| 1 | 30 | Yes |
| 5 | 150 | Yes |
| 8 | 240 | Yes (barely) |
| 9+ | 270+ | No — upgrade or reduce frequency |

Each route also triggers a second SerpApi call to resolve a real booking
link (`booking_token` lookup) *only when an alert fires* — normal runs
that don't hit an alert don't spend that extra call.

## Automating with GitHub Actions

`.github/workflows/check-flights.yml` runs daily. Add these repo secrets
(Settings → Secrets and variables → Actions):

- `SERPAPI_KEY`
- `EMAIL_ADDRESS`
- `EMAIL_APP_PASSWORD`
- `NOTIFY_EMAIL`

Price history is cached between runs via `actions/cache` so drop-detection
keeps working across scheduled runs.
