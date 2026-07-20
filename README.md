# NOC Monitor

A small uptime/incident monitoring system, built to demonstrate the core concepts behind NOC (Network Operations Center) work: continuous service monitoring, incident detection, alerting, and status reporting.

**Live status page:** https://wolfhouse12.github.io/noc-monitor/

## What it does

- Periodically checks a list of monitored services (currently two of my own deployed apps) over HTTP: response status, response time, and TLS certificate expiry.
- Tracks each service's state (`up` / `degraded` / `down`) and keeps a rolling history of checks.
- Calculates 24-hour and 7-day uptime percentages per service.
- Sends an **email alert** the moment a service's state changes (goes down, comes back up, or becomes slow) — not on every check, only on transitions, the same way real monitoring/alerting tools avoid alert spam.
- Publishes a public, auto-updating **status page** showing current status, uptime, and recent check history for each service.

## How it runs

There's no server to keep running. A **GitHub Actions workflow** (`.github/workflows/monitor.yml`) runs `check.py` on a cron schedule (every 10 minutes), and commits the updated `status.json` back to the repo. The static status page (`index.html` + `app.js`) reads that same `status.json` and is served for free via GitHub Pages — so the whole system costs nothing to run and needs no infrastructure of its own to monitor infrastructure.

## Architecture

```
check.py                    -> runs on a schedule, does the actual checking
  |-- HTTP GET each service, measure latency and status code
  |-- check TLS certificate expiry (once per day per service)
  |-- compare against previous status.json to detect state changes
  |-- send an email (via Resend) on any state change
  |-- write updated status.json

.github/workflows/monitor.yml -> cron trigger, runs check.py, commits status.json

index.html / style.css / app.js -> static status page, reads status.json client-side
```

## Setup

```sh
pip install -r requirements.txt
python check.py
```

Alerting requires two GitHub Actions secrets (Settings → Secrets and variables → Actions):

- `RESEND_API_KEY` — API key from [resend.com](https://resend.com) (free tier)
- `ALERT_EMAIL_TO` — where alerts get sent

Without these set, `check.py` still runs and updates `status.json` normally — it just skips sending the alert (and logs that it did).

## Adding a service to monitor

Add an entry to the `SERVICES` list in `check.py`:

```python
{"id": "my-service", "name": "My Service", "url": "https://example.com/"}
```
