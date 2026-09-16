"""Thin wrapper around SerpApi's Google Flights engine.

Docs: https://serpapi.com/google-flights-api
"""
from __future__ import annotations

import requests

SERPAPI_BASE_URL = "https://serpapi.com/search.json"

CABIN_TO_TRAVEL_CLASS = {
    "economy": 1,
    "premium_economy": 2,
    "business": 3,
    "first": 4,
}


class SerpApiError(RuntimeError):
    pass


def _request(params: dict, api_key: str) -> dict:
    params = {**params, "api_key": api_key}
    resp = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    error = data.get("error")
    if error:
        raise SerpApiError(f"SerpApi error: {error}")

    return data


def search_flights(
    *,
    api_key: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str | None = None,
    cabin: str = "economy",
    adults: int = 1,
    currency: str = "KRW",
    language: str = "ko",
    country: str = "kr",
) -> dict:
    """Run a Google Flights search and return the raw SerpApi JSON payload."""
    travel_class = CABIN_TO_TRAVEL_CLASS.get(cabin, 1)
    trip_type = 1 if return_date else 2  # 1 = round trip, 2 = one way

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "type": trip_type,
        "travel_class": travel_class,
        "adults": adults,
        "currency": currency,
        "hl": language,
        "gl": country,
    }
    if return_date:
        params["return_date"] = return_date

    return _request(params, api_key)


def get_booking_options(
    *,
    api_key: str,
    booking_token: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str | None = None,
    cabin: str = "economy",
    adults: int = 1,
    currency: str = "KRW",
    language: str = "ko",
    country: str = "kr",
) -> dict:
    """Second-step call required by SerpApi to resolve a real booking link
    for a specific flight result (identified by its booking_token)."""
    travel_class = CABIN_TO_TRAVEL_CLASS.get(cabin, 1)
    trip_type = 1 if return_date else 2

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "type": trip_type,
        "travel_class": travel_class,
        "adults": adults,
        "currency": currency,
        "hl": language,
        "gl": country,
        "booking_token": booking_token,
    }
    if return_date:
        params["return_date"] = return_date

    return _request(params, api_key)


def extract_flight_summaries(payload: dict) -> list[dict]:
    """Flatten best_flights + other_flights into a simple, uniform list."""
    summaries = []
    for bucket, is_best in ((payload.get("best_flights", []), True), (payload.get("other_flights", []), False)):
        for entry in bucket:
            legs = entry.get("flights", [])
            if not legs:
                continue
            first_leg = legs[0]
            last_leg = legs[-1]
            airlines = sorted({leg.get("airline", "?") for leg in legs})

            summaries.append(
                {
                    "is_best": is_best,
                    "price": entry.get("price"),
                    "total_duration_min": entry.get("total_duration"),
                    "stops": max(len(legs) - 1, 0),
                    "airlines": airlines,
                    "departure_airport": first_leg.get("departure_airport", {}).get("id"),
                    "departure_time": first_leg.get("departure_airport", {}).get("time"),
                    "arrival_airport": last_leg.get("arrival_airport", {}).get("id"),
                    "arrival_time": last_leg.get("arrival_airport", {}).get("time"),
                    "booking_token": entry.get("booking_token"),
                }
            )
    return summaries
