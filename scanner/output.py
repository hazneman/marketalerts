"""Write scan results: latest.json (today) + history.json (rolling 30 days).

History is keyed by bar_date and replace-on-rescan. Serialization is
deterministic (sort_keys, fixed indent), and generated_at is preserved from
the previous run when the scan content is unchanged — so a weekend/holiday
re-run rewrites identical bytes and the Action's commit-if-changed step
becomes a no-op (no pointless Netlify deploys).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from alerts.base import Alert

SCHEMA_VERSION = 1
HISTORY_DAYS = 30


def _dump(obj: dict, path: Path) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=1) + "\n")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_prices(prices: dict, bar_dates: dict, output_dir: Path,
                 now: dt.datetime | None = None) -> None:
    """prices.json: latest close (+1d change) for every scanned ticker.

    Lets the portfolio page value ANY universe holding client-side, not just
    tickers that alerted today. Same generated_at-preserving idempotency as
    the other outputs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "bar_dates": bar_dates,
        "prices": prices,
    }
    prev = _load(output_dir / "prices.json")
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    _dump(data, output_dir / "prices.json")


def write_results(alerts: list[Alert] | list[dict], meta: dict, output_dir: Path,
                  now: dt.datetime | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    alert_dicts = [a.to_dict() if hasattr(a, "to_dict") else a for a in alerts]

    latest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "alerts": alert_dicts,
        **meta,
    }
    prev = _load(output_dir / "latest.json")
    if prev is not None and {**prev, "generated_at": None} == {**latest, "generated_at": None}:
        latest["generated_at"] = prev["generated_at"]
    _dump(latest, output_dir / "latest.json")

    history = _load(output_dir / "history.json") or {
        "schema_version": SCHEMA_VERSION, "days": [],
    }
    day_entry = {
        "bar_date": meta["bar_date"],
        "generated_at": latest["generated_at"],
        "scanned": meta["scanned"],
        "alerts": alert_dicts,
    }
    prev_day = next((d for d in history["days"] if d["bar_date"] == meta["bar_date"]), None)
    if prev_day is not None and {**prev_day, "generated_at": None} == {**day_entry, "generated_at": None}:
        day_entry = prev_day
    days = [d for d in history["days"] if d["bar_date"] != meta["bar_date"]]
    days.append(day_entry)
    days.sort(key=lambda d: d["bar_date"], reverse=True)
    history["days"] = days[:HISTORY_DAYS]
    _dump(history, output_dir / "history.json")
