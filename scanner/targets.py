"""Universe-wide analyst target cache → frontend/public/data/targets.json.

The Portfolio page wants an analyst mean target for ANY held ticker, but the
portfolio lives in the browser — the scanner can't know which tickers to fetch.
Fetching .info for all ~624 tickers daily is too slow/flaky, so this keeps a
ROLLING cache: each scan refreshes the ~130 stalest entries (missing first,
then oldest as_of), which cycles the whole universe in about a week. Fetch
failures keep the previous value untouched (retried next run); a ticker Yahoo
definitively has no target for is recorded as null so it isn't hammered daily.

Rides the daily scan like sectors/forex (failure-isolated) and is byte-stable:
as_of derives from the scan bar_date — never the wall clock — so weekend
re-runs rewrite identical bytes and stay no-op commits.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
SCHEMA_VERSION = 1
MAX_AGE_DAYS = 7   # refresh a ticker once its target is older than this
BATCH = 130        # per-run refresh cap → full universe cycles in ~a week
WORKERS = 6


def pick_stale(universe: list[str], prev: dict, today: str, batch: int = BATCH) -> list[str]:
    """Tickers to refresh this run: never-fetched first, then oldest as_of;
    ties broken alphabetically so the rotation is deterministic."""
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=MAX_AGE_DAYS)).isoformat()
    def key(t: str):
        e = prev.get(t)
        return (e is not None, (e or {}).get("as_of", ""), t)
    stale = [t for t in universe if prev.get(t) is None or prev[t].get("as_of", "") <= cutoff]
    return sorted(stale, key=key)[:batch]


def fetch_target(ticker: str) -> tuple[str, dict | None, bool]:
    """(ticker, entry|None, fetched_ok). entry is None only on FETCH FAILURE;
    a ticker with no analyst coverage returns a null-target entry."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        logger.warning("target fetch failed for %s (%s)", ticker, exc)
        return ticker, None, False
    t = info.get("targetMeanPrice")
    entry: dict = {"target_mean": round(float(t), 2) if t else None}
    n = info.get("numberOfAnalystOpinions")
    if n:
        entry["n_analysts"] = int(n)
    return ticker, entry, True


def build(output_dir: Path = DEFAULT_OUTPUT_DIR, bar_date: str | None = None,
          universe: list[str] | None = None, batch: int = BATCH,
          fetch=fetch_target, now: dt.datetime | None = None) -> dict:
    if universe is None:
        with open(SCANNER_DIR / "universe.json") as fh:
            markets = json.load(fh)["markets"]
        universe = [s for syms in markets.values() for s in syms]
    bar_date = bar_date or dt.date.today().isoformat()

    path = output_dir / "targets.json"
    try:
        prev = json.loads(path.read_text())
    except (OSError, ValueError):
        prev = None
    targets: dict[str, dict] = dict((prev or {}).get("targets", {}))

    todo = pick_stale(universe, targets, bar_date, batch)
    refreshed = 0
    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for ticker, entry, ok in pool.map(fetch, todo):
                if not ok:
                    continue  # keep previous value; retried next run
                targets[ticker] = {**entry, "as_of": bar_date}
                refreshed += 1

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "targets": dict(sorted(targets.items())),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    path.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n")
    data["_refreshed"] = refreshed
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="prime the full universe now")
    a = ap.parse_args()
    d = build(batch=10_000 if a.all else BATCH)
    have = sum(1 for v in d["targets"].values() if v.get("target_mean"))
    print(f"targets.json: {len(d['targets'])} cached ({have} with a target, "
          f"{d['_refreshed']} refreshed this run)")
