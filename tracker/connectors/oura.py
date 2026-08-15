"""Oura Ring connector (API v2, personal access token).

Setup: https://cloud.ouraring.com/personal-access-tokens -> create token ->
store it in the OURA_TOKEN environment variable (GitHub secret for the
daily workflow).

Sleep for date D means the night that ended on morning D, matching Oura's
own "day" attribution.
"""

from __future__ import annotations

import os
from datetime import date

import requests

API = "https://api.ouraring.com/v2/usercollection"


def _get(path: str, token: str, params: dict) -> dict:
    r = requests.get(f"{API}/{path}",
                     headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_sleep(start: date, end: date, token: str | None = None) -> dict[str, dict]:
    """Return {iso_date: {sleep_hours, sleep_score}} for the range (inclusive)."""
    token = token or os.environ.get("OURA_TOKEN")
    if not token:
        raise RuntimeError("OURA_TOKEN is not set")

    params = {"start_date": start.isoformat(), "end_date": end.isoformat()}
    out: dict[str, dict] = {}

    # Sleep sessions: sum actual sleep seconds per attributed day
    # (long sleep only, so naps don't inflate the number).
    data = _get("sleep", token, params)
    for rec in data.get("data", []):
        if rec.get("type") not in (None, "long_sleep"):
            continue
        day = rec.get("day")
        secs = rec.get("total_sleep_duration") or 0
        if day:
            entry = out.setdefault(day, {})
            entry["sleep_hours"] = round(entry.get("sleep_hours", 0.0) + secs / 3600, 2)

    # Daily sleep score.
    data = _get("daily_sleep", token, params)
    for rec in data.get("data", []):
        day = rec.get("day")
        score = rec.get("score")
        if day and score is not None:
            out.setdefault(day, {})["sleep_score"] = score

    return out
