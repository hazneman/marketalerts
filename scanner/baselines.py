"""Sector baselines — per-GICS-sector quartiles for the company-profile metrics.

Powers the green/red coloring of the Buys review's Company profile: a metric is
judged against ITS OWN SECTOR's distribution (3.4x net debt/EBITDA is alarming
for tech, unremarkable for utilities), never against one absolute cutoff.

How the data accumulates (the nightly update mechanism):
- `archive/fundamentals_cache.json` holds the latest observed profile metrics
  per ticker with an `as_of` date. It rides the daily scan: each run ingests
  the profiles ALREADY fetched for alerted tickers (free), then refreshes the
  REFRESH_N stalest tickers via threaded .info calls (~40/night -> the whole
  ~624-ticker universe cycles in ~3 weeks, forever).
- Per-sector quartiles (p25/median/p75) are recomputed from the cache and
  written to `frontend/public/data/baselines.json` for the dashboard. Sectors
  need MIN_SECTOR_N tickers carrying a metric before that metric is published —
  a thin sector yields no baseline and the UI stays neutral.

Display-only: nothing here touches the verdict. Byte-stable: `as_of` derives
from the scan bar_date (never now()), and generated_at is preserved when
content is unchanged, so holiday runs stay no-op commits.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median, quantiles

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
ROOT = SCANNER_DIR.parent
CACHE_PATH = ROOT / "archive" / "fundamentals_cache.json"
DEFAULT_OUTPUT_DIR = ROOT / "frontend" / "public" / "data"

SCHEMA_VERSION = 1
REFRESH_N = 40        # stalest tickers re-fetched per nightly run
MIN_SECTOR_N = 8      # metric published only with at least this many observations
FETCH_WORKERS = 8


def _dump(obj: dict, path: Path) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=1) + "\n")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def load_cache(path: Path = CACHE_PATH) -> dict:
    raw = _load(path)
    if not raw or not isinstance(raw.get("tickers"), dict):
        return {"schema_version": SCHEMA_VERSION, "tickers": {}}
    return raw


def pick_stalest(cache: dict, universe: list[str], n: int,
                 exclude: set[str] | None = None) -> list[str]:
    """The n tickers most in need of a refresh: never-seen first, then oldest
    `as_of`. Deterministic (ties break by symbol) so runs are reproducible."""
    exclude = exclude or set()
    tickers = cache.get("tickers", {})

    def key(sym: str) -> tuple[str, str]:
        return (tickers.get(sym, {}).get("as_of") or "", sym)

    return sorted((s for s in universe if s not in exclude), key=key)[:n]


def merge_observations(cache: dict, observed: dict[str, dict], as_of: str) -> int:
    """Fold {ticker: {sector, metrics}} into the cache. Only tickers with a
    sector AND at least one metric are stored; failures (None) leave any
    previous observation in place. Returns how many entries changed."""
    changed = 0
    tickers = cache.setdefault("tickers", {})
    for sym, obs in observed.items():
        if not obs or not obs.get("sector") or not obs.get("metrics"):
            continue
        entry = {"as_of": as_of, "sector": obs["sector"], "metrics": obs["metrics"]}
        prev = tickers.get(sym)
        if prev is None or {**prev, "as_of": None} != {**entry, "as_of": None}:
            changed += 1
        tickers[sym] = entry
    return changed


def compute_baselines(cache: dict, min_n: int = MIN_SECTOR_N) -> dict:
    """Per-sector, per-metric quartiles from every cached observation."""
    by_sector: dict[str, dict[str, list[float]]] = {}
    for entry in cache.get("tickers", {}).values():
        sector = entry.get("sector")
        for metric, value in (entry.get("metrics") or {}).items():
            if isinstance(value, (int, float)):
                by_sector.setdefault(sector, {}).setdefault(metric, []).append(float(value))

    out: dict[str, dict] = {}
    for sector, metrics in by_sector.items():
        stats = {}
        for metric, values in metrics.items():
            if len(values) < min_n:
                continue
            q = quantiles(values, n=4, method="inclusive")
            stats[metric] = {"p25": round(q[0], 2), "med": round(median(values), 2),
                            "p75": round(q[2], 2), "n": len(values)}
        if stats:
            out[sector] = stats
    return out


def _fetch_profile(ticker: str) -> tuple[str, dict | None]:
    from recommend import profile_metrics

    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        logger.debug("baseline fetch failed for %s (%s)", ticker, exc)
        return ticker, None
    if not info.get("marketCap"):
        return ticker, None
    metrics = profile_metrics(info)
    sector = info.get("sector")
    if not metrics or not sector:
        return ticker, None
    return ticker, {"sector": sector, "metrics": metrics}


def refresh(output_dir: Path = DEFAULT_OUTPUT_DIR, *,
            bar_date: str,
            universe: list[str],
            fresh: dict[str, dict] | None = None,
            cache_path: Path = CACHE_PATH,
            refresh_n: int = REFRESH_N,
            now: dt.datetime | None = None) -> dict:
    """Nightly update: ingest already-fetched profiles, top up the stalest
    tickers, recompute sector baselines, write both files byte-stably."""
    cache = load_cache(cache_path)
    changed = merge_observations(cache, fresh or {}, bar_date)

    stale = pick_stalest(cache, universe, refresh_n, exclude=set(fresh or {}))
    if stale:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            fetched = dict(pool.map(_fetch_profile, stale))
        changed += merge_observations(
            cache, {s: o for s, o in fetched.items() if o}, bar_date)

    if changed:
        _dump(cache, cache_path)

    baselines = compute_baselines(cache)
    generated_at = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "as_of": bar_date,
        "min_n": MIN_SECTOR_N,
        "coverage": len(cache.get("tickers", {})),
        "sectors": baselines,
    }
    out_path = output_dir / "baselines.json"
    prev = _load(out_path)
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    _dump(data, out_path)
    return {"coverage": data["coverage"], "sectors": len(baselines), "refreshed": len(stale),
            "changed": changed}


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(SCANNER_DIR))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    uni = json.loads((SCANNER_DIR / "universe.json").read_text())["markets"]
    symbols = [s for market in uni.values() for s in market]
    latest = _load(DEFAULT_OUTPUT_DIR / "latest.json") or {}
    res = refresh(bar_date=latest.get("bar_date") or dt.date.today().isoformat(),
                  universe=symbols)
    print(res)
