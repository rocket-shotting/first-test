"""CLI: check tracked flight routes (config.json) and print/alert on price.

Usage:
    python check_flights.py                # check all routes, send email on alert
    python check_flights.py --no-email      # console output only, never sends mail
    python check_flights.py --route ICN-NRT # check a single route by its config "name"

For an interactive search UI instead, run app.py and open the printed URL.
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

import core
from notifier import send_email


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip sending email even on alert")
    parser.add_argument("--route", help="only check the route with this config name")
    args = parser.parse_args()

    load_dotenv(core.BASE_DIR / ".env")

    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("ERROR: SERPAPI_KEY is not set (check your .env file).", file=sys.stderr)
        return 1

    config = core.load_config()
    routes = config["routes"]
    if args.route:
        routes = [r for r in routes if r["name"] == args.route]
        if not routes:
            print(f"ERROR: no route named '{args.route}' in config.json", file=sys.stderr)
            return 1

    results = core.run_checks(api_key, routes)

    alerts: list[tuple[dict, dict, str]] = []
    for r in results:
        route = r["route"]
        if r["error"]:
            print(f"[{route['name']}] {r['error']}", file=sys.stderr)
            continue

        print(format_console_line(route, r["cheapest"], r["link"]))
        if r["should_alert"]:
            alerts.append((route, r["cheapest"], r["link"]))
            print(f"  ALERT: {r['reason']}")

    if alerts and not args.no_email:
        send_alert_email(alerts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
