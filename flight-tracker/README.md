# Flight Tracker

Search and track flight prices via [SerpApi's Google Flights engine](https://serpapi.com/google-flights-api).
Comes with a local web UI (search by departure/arrival/dates, save routes to
track, see price history) and a CLI for automation. Emails an alert (Gmail
SMTP) when a tracked route's price hits your threshold or drops since the
last check.

## Setup (one command)

```bash
cd flight-tracker
bash setup.sh
```

This creates a virtualenv, installs dependencies, asks for your credentials
on first run (or leave them blank and fill them in later from the Settings
page in the UI), and starts the web server. Then open **http://127.0.0.1:5001**
in your browser.

Credentials needed (all optional at setup time, required to actually search/alert):

| Value | Where to get it |
|---|---|
| SerpApi key | https://serpapi.com/manage-api-key (free tier: 250 searches/month) |
| Gmail address (sender) | The Gmail account that sends alert emails |
| Gmail App Password | https://myaccount.google.com/apppasswords (requires 2-Step Verification on) |
| Notify email | Address that receives alerts (can be the same as the sender) |

Everything is written to a local `.env` file — gitignored, never leaves your
machine, and is never sent to SerpApi/Gmail except as normal HTTPS API calls.

## Using the web UI

- **Search**: enter departure/arrival airport codes, dates, cabin, and hit
  Search to see live results sorted by price.
- **Track a route**: after searching, give it a name and (optionally) a
  price-alert threshold, then "이 노선 추적 목록에 추가" adds it to
  `config.json`.
- **추적 중인 노선**: shows every tracked route with its last-checked price.
  "지금 전체 가격 확인" runs a check immediately and emails you if any route's
  price hits its threshold or dropped since the last check.
- **설정**: update your SerpApi key / Gmail credentials at any time.

## CLI (for automation / GitHub Actions)

```bash
source .venv/bin/activate
python check_flights.py            # check all tracked routes, email on alert
python check_flights.py --no-email # console only, never sends mail
python check_flights.py --route ICN-NRT
```

Both the UI and the CLI read/write the same `config.json` (tracked routes)
and `price_history.json` (gitignored — lets either one detect price drops
between checks).

`config.json` route fields: `departure_id`/`arrival_id` (airport codes),
`outbound_date`/`return_date` (omit `return_date` for one-way), `cabin`
(`economy`/`premium_economy`/`business`/`first`), `adults`,
`price_alert_threshold` (alert fires at/below this price, or on any drop
versus the previous check regardless of threshold).

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
