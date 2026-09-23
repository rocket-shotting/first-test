"""Local web UI for the flight tracker.

Run with:  python3 app.py
Then open: http://127.0.0.1:5001
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

import airports_data
import core
from notifier import send_email
from serpapi_client import SerpApiError

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    ENV_PATH.touch()
load_dotenv(ENV_PATH)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # local-only server, session doesn't need to survive restarts

CABIN_LABELS = {
    "economy": "이코노미",
    "premium_economy": "프리미엄 이코노미",
    "business": "비즈니스",
    "first": "퍼스트",
}


def routes_with_last_price() -> list[dict]:
    config = core.load_config()
    history = core.load_history()
    routes = []
    for r in config["routes"]:
        r = dict(r)
        h = history.get(r["name"], [])
        r["last_price"] = h[-1]["price"] if h else None
        r["last_checked"] = h[-1]["checked_at"] if h else None
        r["cabin_label"] = CABIN_LABELS.get(r.get("cabin", "economy"), r.get("cabin"))
        routes.append(r)
    return routes


@app.route("/")
def index():
    return render_template(
        "index.html",
        routes=routes_with_last_price(),
        has_key=bool(os.environ.get("SERPAPI_KEY")),
        cabin_labels=CABIN_LABELS,
    )


@app.route("/api/airports")
def api_airports():
    query = request.args.get("q", "")
    matches = airports_data.search(query, limit=8)
    return jsonify(
        [
            {
                "iata": e["iata"],
                "label": airports_data.label_for_code(e["iata"]) + f" — {e['name']}, {e['country']}",
            }
            for e in matches
        ]
    )


@app.route("/search", methods=["POST"])
def search():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        flash("SerpApi 키가 설정되지 않았습니다. 먼저 설정 페이지에서 입력하세요.", "error")
        return redirect(url_for("settings"))

    search_params = {
        "departure_id": request.form["departure_id"].strip().upper(),
        "arrival_id": request.form["arrival_id"].strip().upper(),
        "outbound_date": request.form["outbound_date"],
        "return_date": request.form.get("return_date") or None,
        "cabin": request.form.get("cabin", "economy"),
        "adults": int(request.form.get("adults") or 1),
    }

    results = []
    error = None
    try:
        results = core.search(api_key=api_key, **search_params)
    except SerpApiError as e:
        error = str(e)
    except Exception as e:
        error = f"요청 실패: {e}"

    return render_template(
        "index.html",
        routes=routes_with_last_price(),
        has_key=True,
        cabin_labels=CABIN_LABELS,
        search_params=search_params,
        search_results=results,
        search_error=error,
        search_link=core.fallback_booking_url(search_params),
        departure_label=airports_data.label_for_code(search_params["departure_id"]),
        arrival_label=airports_data.label_for_code(search_params["arrival_id"]),
    )


@app.route("/search-flex", methods=["POST"])
def search_flex():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        flash("SerpApi 키가 설정되지 않았습니다. 먼저 설정 페이지에서 입력하세요.", "error")
        return redirect(url_for("settings"))

    departure_id = request.form["departure_id"].strip().upper()
    arrival_id = request.form["arrival_id"].strip().upper()
    month_str = request.form["month"]  # "YYYY-MM"
    nights = int(request.form.get("nights") or 0)
    cabin = request.form.get("cabin", "economy")
    adults = int(request.form.get("adults") or 1)
    year, month = (int(part) for part in month_str.split("-"))

    flex_results = core.scan_month(
        api_key=api_key,
        departure_id=departure_id,
        arrival_id=arrival_id,
        year=year,
        month=month,
        nights=nights,
        cabin=cabin,
        adults=adults,
    )
    priced = [r for r in flex_results if r["price"] is not None]
    flex_cheapest = min(priced, key=lambda r: r["price"]) if priced else None

    flex_params = {
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "month": month_str,
        "nights": nights,
        "cabin": cabin,
        "adults": adults,
    }

    return render_template(
        "index.html",
        routes=routes_with_last_price(),
        has_key=True,
        cabin_labels=CABIN_LABELS,
        flex_params=flex_params,
        flex_results=flex_results,
        flex_cheapest=flex_cheapest,
        flex_calls_used=len(flex_results),
        departure_label=airports_data.label_for_code(departure_id),
        arrival_label=airports_data.label_for_code(arrival_id),
    )


@app.route("/track", methods=["POST"])
def track():
    name = request.form["name"].strip()
    route = {
        "name": name,
        "departure_id": request.form["departure_id"].strip().upper(),
        "arrival_id": request.form["arrival_id"].strip().upper(),
        "outbound_date": request.form["outbound_date"],
        "return_date": request.form.get("return_date") or None,
        "cabin": request.form.get("cabin", "economy"),
        "adults": int(request.form.get("adults") or 1),
        "price_alert_threshold": int(request.form["price_alert_threshold"])
        if request.form.get("price_alert_threshold")
        else None,
    }

    config = core.load_config()
    if any(r["name"] == name for r in config["routes"]):
        flash(f"'{name}' 이름의 추적 노선이 이미 있습니다. 다른 이름을 사용하세요.", "error")
        return redirect(url_for("index"))

    config["routes"].append(route)
    core.save_config(config)
    flash(f"'{name}' 노선을 추적 목록에 추가했습니다.", "success")
    return redirect(url_for("index"))


@app.route("/routes/<name>/delete", methods=["POST"])
def delete_route(name):
    config = core.load_config()
    config["routes"] = [r for r in config["routes"] if r["name"] != name]
    core.save_config(config)
    flash(f"'{name}' 노선을 삭제했습니다.", "success")
    return redirect(url_for("index"))


def _send_alert_emails(alerts: list[tuple[dict, dict, str]]) -> str | None:
    sender = os.environ.get("EMAIL_ADDRESS")
    app_password = os.environ.get("EMAIL_APP_PASSWORD")
    to_address = os.environ.get("NOTIFY_EMAIL") or sender
    if not sender or not app_password or not to_address:
        return "이메일 설정이 완료되지 않아 알림 메일을 보내지 못했습니다 (설정 페이지 확인)."

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
    send_email(
        sender_address=sender,
        app_password=app_password,
        to_address=to_address,
        subject=f"[Flight Tracker] Price alert for {len(alerts)} route(s)",
        body="\n".join(lines),
    )
    return None


@app.route("/check-all", methods=["POST"])
def check_all():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        flash("SerpApi 키가 설정되지 않았습니다.", "error")
        return redirect(url_for("settings"))

    config = core.load_config()
    if not config["routes"]:
        flash("추적 중인 노선이 없습니다.", "error")
        return redirect(url_for("index"))

    results = core.run_checks(api_key, config["routes"])
    alerts = []
    messages = []
    for r in results:
        route = r["route"]
        if r["error"]:
            messages.append(f"[{route['name']}] 오류: {r['error']}")
            continue
        price = r["cheapest"]["price"]
        messages.append(f"[{route['name']}] {price:,} KRW" + (" — 알림 조건 충족!" if r["should_alert"] else ""))
        if r["should_alert"]:
            alerts.append((route, r["cheapest"], r["link"]))

    for m in messages:
        flash(m, "info")

    if alerts:
        err = _send_alert_emails(alerts)
        if err:
            flash(err, "error")
        else:
            flash(f"알림 이메일을 {len(alerts)}건 발송했습니다.", "success")

    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        for key in ("SERPAPI_KEY", "EMAIL_ADDRESS", "EMAIL_APP_PASSWORD", "NOTIFY_EMAIL"):
            value = request.form.get(key, "").strip()
            if value:
                set_key(str(ENV_PATH), key, value)
                os.environ[key] = value
        flash("설정을 저장했습니다.", "success")
        return redirect(url_for("index"))

    return render_template(
        "settings.html",
        serpapi_key_set=bool(os.environ.get("SERPAPI_KEY")),
        email_address=os.environ.get("EMAIL_ADDRESS", ""),
        email_app_password_set=bool(os.environ.get("EMAIL_APP_PASSWORD")),
        notify_email=os.environ.get("NOTIFY_EMAIL", ""),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
