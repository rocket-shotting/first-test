"""Check tracked flight routes on Google Flights (via SerpApi) and print/alert on price.

Usage:
    python check_flights.py                # check all routes, send email on alert
    python check_flights.py --no-email      # console output only, never sends mail
    python check_flights.py --route ICN-NRT # check a single route by its config "name"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from notifier import send_email
from serpapi_client import SerpApiError, extract_flight_summaries, get_booking_options, search_flights

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
HISTORY_PATH = BASE_DIR / "price_history.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def fallback_booking_url(route: dict) -> str:
    query = f"Flights from {route['departure_id']} to {route['arrival_id']} on {route['outbound_date']}"
    if route.get("return_date"):
        query += f" through {route['return_date']}"
    return "https://www.google.com/travel/flights?q=" + query.replace(" ", "%20")


def resolve_booking_link(api_key: str, route: dict, cheapest: dict) -> str:
    token = cheapest.get("booking_token")
    if not token:
        return fallback_booking_url(route)
    try:
        payload = get_booking_options(
            api_key=api_key,
            booking_token=token,
            departure_id=route["departure_id"],
            arrival_id=route["arrival_id"],
            outbound_date=route["outbound_date"],
            return_date=route.get("return_date"),
            cabin=route.get("cabin", "economy"),
            adults=route.get("adults", 1),
        )
        options = payload.get("booking_options", [])
        for opt in options:
            for key in ("together", "departing", "returning"):
                book = opt.get(key)
                if book and book.get("booking_request", {}).get("url"):
                    return book["booking_request"]["url"]
    except SerpApiError:
        pass
    return fallback_booking_url(route)


def check_route(api_key: str, route: dict) -> dict | None:
    payload = search_flights(
        api_key=api_key,
        departure_id=route["departure_id"],
        arrival_id=route["arrival_id"],
        outbound_date=route["outbound_date"],
        return_date=route.get("return_date"),
        cabin=route.get("cabin", "economy"),
        adults=route.get("adults", 1),
    )
    summaries = extract_flight_summaries(payload)
    if not summaries:
        return None

    priced = [s for s in summaries if isinstance(s.get("price"), (int, float))]
    if not priced:
        return None

    return min(priced, key=lambda s: s["price"])


def format_console_line(route: dict, cheapest: dict, link: str) -> str:
    airlines = "/".join(cheapest["airlines"])
    duration_h = (cheapest["total_duration_min"] or 0) // 60
    duration_m = (cheapest["total_duration_min"] or 0) % 60
    return (
        f"[{route['name']}] {route['departure_id']}->{route['arrival_id']} "
        f"{route['outbound_date']}"
        f"{' ~ ' + route['return_date'] if route.get('return_date') else ''} "
        f"| {cheapest['price']:,} KRW | {airlines} | "
        f"{cheapest['stops']} stop(s) | {duration_h}h{duration_m}m\n  -> {link}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip sending email even on alert")
    parser.add_argument("--route", help="only check the route with this config name")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")

    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("ERROR: SERPAPI_KEY is not set (check your .env file).", file=sys.stderr)
        return 1

    config = load_config()
    routes = config["routes"]
    if args.route:
        routes = [r for r in routes if r["name"] == args.route]
        if not routes:
            print(f"ERROR: no route named '{args.route}' in config.json", file=sys.stderr)
            return 1

    history = load_history()
    alerts: list[tuple[dict, dict, str]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for route in routes:
        try:
            cheapest = check_route(api_key, route)
        except SerpApiError as e:
            print(f"[{route['name']}] SerpApi error: {e}", file=sys.stderr)
            continue
        except Exception as e:  # network errors etc.
            print(f"[{route['name']}] request failed: {e}", file=sys.stderr)
            continue

        if cheapest is None:
            print(f"[{route['name']}] no priced flights found for this search.")
            continue

        link = resolve_booking_link(api_key, route, cheapest)
        print(format_console_line(route, cheapest, link))

        route_history = history.setdefault(route["name"], [])
        last_price = route_history[-1]["price"] if route_history else None
        route_history.append({"checked_at": now_iso, "price": cheapest["price"]})

        threshold = route.get("price_alert_threshold")
        should_alert = False
        reason = ""
        if threshold is not None and cheapest["price"] <= threshold:
            should_alert = True
            reason = f"price {cheapest['price']:,} KRW is at/below your threshold {threshold:,} KRW"
        elif last_price is not None and cheapest["price"] < last_price:
            should_alert = True
            reason = f"price dropped from {last_price:,} to {cheapest['price']:,} KRW"

        if should_alert:
            alerts.append((route, cheapest, link))
            print(f"  ALERT: {reason}")

    save_history(history)

    if alerts and not args.no_email:
        send_alert_email(alerts)

    return 0


def send_alert_email(alerts: list[tuple[dict, dict, str]]) -> None:
    sender = os.environ.get("EMAIL_ADDRESS")
    app_password = os.environ.get("EMAIL_APP_PASSWORD")
    to_address = os.environ.get("NOTIFY_EMAIL") or sender

    if not sender or not app_password or not to_address:
        print(
            "Skipping email: EMAIL_ADDRESS / EMAIL_APP_PASSWORD / NOTIFY_EMAIL not fully set in .env",
            file=sys.stderr,
        )
        return

    lines = []
    for route, cheapest, link in alerts:
        airlines = "/".join(cheapest["airlines"])
        lines.append(
            f"[{route['name']}] {route['departure_id']} -> {route['arrival_id']}\n"
            f"  Date: {route['outbound_date']}"
            f"{(' ~ ' + route['return_date']) if route.get('return_date') else ''}\n"
            f"  Price: {cheapest['price']:,} KRW ({airlines}, {cheapest['stops']} stop(s))\n"
            f"  Book: {link}\n"
        )
    body = "\n".join(lines)

    send_email(
        sender_address=sender,
        app_password=app_password,
        to_address=to_address,
        subject=f"[Flight Tracker] Price alert for {len(alerts)} route(s)",
        body=body,
    )
    print(f"Alert email sent to {to_address}")


if __name__ == "__main__":
    raise SystemExit(main())
