"""Uptime/latency checker for monitored services.

Runs on a schedule (see .github/workflows/monitor.yml), checks each service's
HTTP status and response time, tracks SSL certificate expiry, persists results
to status.json, and sends an email alert whenever a service's status changes
(e.g. up -> down, down -> up, up -> degraded).
"""

import json
import os
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

STATUS_FILE = Path(__file__).parent / "status.json"
MAX_HISTORY = 1000
TIMEOUT_SECONDS = 10
SLOW_THRESHOLD_MS = 3000

SERVICES = [
    {
        "id": "job-tracker",
        "name": "AI Job Application Tracker",
        "url": "https://job-tracker-eosin-two.vercel.app/",
    },
    {
        "id": "shalhevet",
        "name": "Shalhevet Community Center",
        "url": "https://shalhevet-website.vercel.app/",
    },
]


def get_ssl_expiry(hostname):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=TIMEOUT_SECONDS) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                return expires.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return None


def check_service(service):
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "timestamp": now,
        "status": "down",
        "status_code": None,
        "response_ms": None,
        "error": None,
    }
    try:
        start = datetime.now()
        resp = requests.get(service["url"], timeout=TIMEOUT_SECONDS)
        elapsed_ms = round((datetime.now() - start).total_seconds() * 1000)
        result["status_code"] = resp.status_code
        result["response_ms"] = elapsed_ms
        if resp.status_code < 400:
            result["status"] = "degraded" if elapsed_ms > SLOW_THRESHOLD_MS else "up"
        else:
            result["status"] = "down"
            result["error"] = f"HTTP {resp.status_code}"
    except requests.RequestException as e:
        result["error"] = str(e)
    return result


def load_status():
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"services": {}, "last_run": None}


def calc_uptime_pct(history, hours):
    if not history:
        return None
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    recent = [h for h in history if datetime.fromisoformat(h["timestamp"]).timestamp() >= cutoff]
    if not recent:
        return None
    up_count = sum(1 for h in recent if h["status"] in ("up", "degraded"))
    return round(up_count / len(recent) * 100, 2)


def send_alert(subject, body):
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("ALERT_EMAIL_TO")
    from_email = os.environ.get("ALERT_EMAIL_FROM", "onboarding@resend.dev")
    if not api_key or not to_email:
        print(f"[alert skipped, no RESEND_API_KEY/ALERT_EMAIL_TO] {subject}")
        return
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": from_email, "to": [to_email], "subject": subject, "text": body},
            timeout=10,
        )
        print(f"Alert sent ({subject}): HTTP {resp.status_code}")
    except Exception as e:
        print(f"Failed to send alert: {e}")


def main():
    data = load_status()

    for service in SERVICES:
        result = check_service(service)
        hostname = urlparse(service["url"]).hostname

        entry = data["services"].setdefault(
            service["id"], {"name": service["name"], "url": service["url"], "history": []}
        )
        previous_status = entry.get("current_status")

        entry["name"] = service["name"]
        entry["url"] = service["url"]
        entry["current_status"] = result["status"]
        entry["last_checked"] = result["timestamp"]
        entry["last_response_ms"] = result["response_ms"]
        entry["last_status_code"] = result["status_code"]
        entry["last_error"] = result["error"]

        entry["history"].append(result)
        entry["history"] = entry["history"][-MAX_HISTORY:]

        entry["uptime_24h_pct"] = calc_uptime_pct(entry["history"], 24)
        entry["uptime_7d_pct"] = calc_uptime_pct(entry["history"], 24 * 7)

        today = datetime.now(timezone.utc).date().isoformat()
        if entry.get("ssl_checked_date") != today:
            entry["ssl_expires"] = get_ssl_expiry(hostname)
            entry["ssl_checked_date"] = today

        if previous_status is not None and previous_status != result["status"]:
            if result["status"] == "down":
                send_alert(
                    f"[DOWN] {service['name']}",
                    f"{service['name']} ({service['url']}) went down at {result['timestamp']}.\n"
                    f"Error: {result['error']}",
                )
            elif result["status"] == "up" and previous_status == "down":
                send_alert(
                    f"[RECOVERED] {service['name']}",
                    f"{service['name']} ({service['url']}) is back up as of {result['timestamp']}.",
                )
            elif result["status"] == "degraded":
                send_alert(
                    f"[DEGRADED] {service['name']}",
                    f"{service['name']} ({service['url']}) response time is "
                    f"{result['response_ms']}ms as of {result['timestamp']}.",
                )

        print(f"{service['id']}: {result['status']} ({result['response_ms']}ms)")

    data["last_run"] = datetime.now(timezone.utc).isoformat()
    STATUS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
