"""Shared flight-check logic used by both the CLI (check_flights.py) and the web UI (app.py)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from serpapi_client import SerpApiError, extract_flight_summaries, get_booking_options, search_flights

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
HISTORY_PATH = BASE_DIR / "price_history.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


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
    """Second SerpApi call to resolve a real booking link for one flight result."""
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


def cheapest_summary(payload: dict) -> dict | None:
    summaries = extract_flight_summaries(payload)
    priced = [s for s in summaries if isinstance(s.get("price"), (int, float))]
    if not priced:
        return None
    return min(priced, key=lambda s: s["price"])


def search(
    *,
    api_key: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str | None = None,
    cabin: str = "economy",
    adults: int = 1,
) -> list[dict]:
    """Ad-hoc search: return every priced flight option, cheapest first."""
    payload = search_flights(
        api_key=api_key,
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        return_date=return_date,
        cabin=cabin,
        adults=adults,
    )
    summaries = extract_flight_summaries(payload)
    priced = [s for s in summaries if isinstance(s.get("price"), (int, float))]
    priced.sort(key=lambda s: s["price"])
    return priced


def cheapest_price_for_date(
    *,
    api_key: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str | None = None,
    cabin: str = "economy",
    adults: int = 1,
) -> dict | None:
    payload = search_flights(
        api_key=api_key,
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        return_date=return_date,
        cabin=cabin,
        adults=adults,
    )
    return cheapest_summary(payload)


def check_route(api_key: str, route: dict) -> dict | None:
    return cheapest_price_for_date(
        api_key=api_key,
        departure_id=route["departure_id"],
        arrival_id=route["arrival_id"],
        outbound_date=route["outbound_date"],
        return_date=route.get("return_date"),
        cabin=route.get("cabin", "economy"),
        adults=route.get("adults", 1),
    )


MONTH_SCAN_INTERVAL_DAYS = 4  # ~7-8 SerpApi calls per month scan (free tier: 250/month)


def month_candidate_dates(year: int, month: int, interval_days: int = MONTH_SCAN_INTERVAL_DAYS) -> list[str]:
    import calendar as _calendar
    from datetime import date as _date, timedelta as _timedelta

    _, days_in_month = _calendar.monthrange(year, month)
    d = _date(year, month, 1)
    dates = []
    while d.month == month:
        dates.append(d)
        d += _timedelta(days=interval_days)
    return [d.isoformat() for d in dates]


def scan_month(
    *,
    api_key: str,
    departure_id: str,
    arrival_id: str,
    year: int,
    month: int,
    nights: int = 0,
    cabin: str = "economy",
    adults: int = 1,
) -> list[dict]:
    """Sample cheapest price across a month (one SerpApi call per sampled date)."""
    from datetime import date as _date, timedelta as _timedelta

    results = []
    for outbound in month_candidate_dates(year, month):
        return_date = None
        if nights > 0:
            d = _date.fromisoformat(outbound) + _timedelta(days=nights)
            return_date = d.isoformat()

        try:
            cheapest = cheapest_price_for_date(
                api_key=api_key,
                departure_id=departure_id,
                arrival_id=arrival_id,
                outbound_date=outbound,
                return_date=return_date,
                cabin=cabin,
                adults=adults,
            )
        except SerpApiError:
            cheapest = None

        results.append(
            {
                "date": outbound,
                "return_date": return_date,
                "price": cheapest["price"] if cheapest else None,
                "airlines": cheapest["airlines"] if cheapest else [],
            }
        )
    return results


def evaluate_alert(route: dict, cheapest: dict, last_price: float | None) -> tuple[bool, str]:
    threshold = route.get("price_alert_threshold")
    if threshold is not None and cheapest["price"] <= threshold:
        return True, f"price {cheapest['price']:,} KRW is at/below your threshold {threshold:,} KRW"
    if last_price is not None and cheapest["price"] < last_price:
        return True, f"price dropped from {last_price:,} to {cheapest['price']:,} KRW"
    return False, ""


def run_checks(api_key: str, routes: list[dict]) -> list[dict]:
    """Check each tracked route, update price_history.json, return per-route results."""
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()
    results = []

    for route in routes:
        entry = {
            "route": route,
            "error": None,
            "cheapest": None,
            "link": None,
            "should_alert": False,
            "reason": "",
        }
        try:
            cheapest = check_route(api_key, route)
        except SerpApiError as e:
            entry["error"] = str(e)
            results.append(entry)
            continue
        except Exception as e:  # network errors etc.
            entry["error"] = f"request failed: {e}"
            results.append(entry)
            continue

        if cheapest is None:
            entry["error"] = "no priced flights found for this search"
            results.append(entry)
            continue

        link = resolve_booking_link(api_key, route, cheapest)
        route_history = history.setdefault(route["name"], [])
        last_price = route_history[-1]["price"] if route_history else None
        route_history.append({"checked_at": now_iso, "price": cheapest["price"]})

        should_alert, reason = evaluate_alert(route, cheapest, last_price)
        entry.update(cheapest=cheapest, link=link, should_alert=should_alert, reason=reason)
        results.append(entry)

    save_history(history)
    return results
