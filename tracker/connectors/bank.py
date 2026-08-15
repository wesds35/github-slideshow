"""Banking connector: daily money flow (expenses out, income in).

Two backends, picked automatically from which env vars are set:

1. SimpleFIN Bridge (recommended for personal use, ~$1.50/mo):
   https://bridge.simplefin.org -> connect your bank -> claim the setup
   token once (see claim_simplefin_token below or `track.py claim-simplefin`)
   -> store the resulting access URL in SIMPLEFIN_ACCESS_URL.

2. Plaid (developer account required):
   set PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ACCESS_TOKEN,
   and optionally PLAID_ENV (production|sandbox, default production).

Both return {iso_date: {"expenses": float, "income": float}} where amounts
are positive numbers: expenses = total outflow, income = total inflow.
Transfers between your own accounts will show on both sides; refine with
per-account filtering if that becomes noisy.
"""

from __future__ import annotations

import base64
import os
import time
from datetime import date, datetime, timezone

import requests


def fetch_money(start: date, end: date) -> dict[str, dict]:
    if os.environ.get("SIMPLEFIN_ACCESS_URL"):
        return _fetch_simplefin(start, end)
    if os.environ.get("PLAID_ACCESS_TOKEN"):
        return _fetch_plaid(start, end)
    raise RuntimeError(
        "No banking backend configured: set SIMPLEFIN_ACCESS_URL or PLAID_* env vars")


# --------------------------------------------------------------------------
# SimpleFIN
# --------------------------------------------------------------------------

def claim_simplefin_token(setup_token: str) -> str:
    """One-time exchange of a SimpleFIN setup token for a permanent access URL."""
    claim_url = base64.b64decode(setup_token).decode()
    r = requests.post(claim_url, timeout=30)
    r.raise_for_status()
    return r.text.strip()


def _fetch_simplefin(start: date, end: date) -> dict[str, dict]:
    access_url = os.environ["SIMPLEFIN_ACCESS_URL"].rstrip("/")
    start_ts = int(datetime(start.year, start.month, start.day,
                            tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(end.year, end.month, end.day,
                          tzinfo=timezone.utc).timestamp()) + 86400
    r = requests.get(f"{access_url}/accounts",
                     params={"start-date": start_ts, "end-date": end_ts},
                     timeout=60)
    r.raise_for_status()
    data = r.json()

    out: dict[str, dict] = {}
    for account in data.get("accounts", []):
        for tx in account.get("transactions", []):
            ts = tx.get("transacted_at") or tx.get("posted") or 0
            day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            amount = float(tx.get("amount", 0))
            entry = out.setdefault(day, {"expenses": 0.0, "income": 0.0})
            if amount < 0:
                entry["expenses"] = round(entry["expenses"] - amount, 2)
            else:
                entry["income"] = round(entry["income"] + amount, 2)
    return out


# --------------------------------------------------------------------------
# Plaid
# --------------------------------------------------------------------------

def _fetch_plaid(start: date, end: date) -> dict[str, dict]:
    env = os.environ.get("PLAID_ENV", "production")
    host = f"https://{env}.plaid.com"
    body = {
        "client_id": os.environ["PLAID_CLIENT_ID"],
        "secret": os.environ["PLAID_SECRET"],
        "access_token": os.environ["PLAID_ACCESS_TOKEN"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "options": {"count": 500, "offset": 0},
    }

    out: dict[str, dict] = {}
    while True:
        r = requests.post(f"{host}/transactions/get", json=body, timeout=60)
        if r.status_code == 400 and "PRODUCT_NOT_READY" in r.text:
            time.sleep(5)
            continue
        r.raise_for_status()
        data = r.json()
        for tx in data.get("transactions", []):
            if tx.get("pending"):
                continue
            day = tx["date"]
            amount = float(tx["amount"])  # Plaid: positive = money out
            entry = out.setdefault(day, {"expenses": 0.0, "income": 0.0})
            if amount > 0:
                entry["expenses"] = round(entry["expenses"] + amount, 2)
            else:
                entry["income"] = round(entry["income"] - amount, 2)
        body["options"]["offset"] += len(data.get("transactions", []))
        if body["options"]["offset"] >= data.get("total_transactions", 0):
            break
    return out
