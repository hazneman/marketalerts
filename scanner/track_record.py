"""Alert track record — a live scoreboard of whether BUY alerts beat their market.

Unlike the other outputs this JSON ACCUMULATES: each run reads its own previous
output and adds to it. When a stock gets a BUY verdict it becomes a tracked
`entry` (captured at its alert-day close); every subsequent daily scan updates
that entry with the latest close and its return SINCE the alert, compared to the
stock's own-market index (US→SPY, DE→DAX, BIST→XU100 — same currency as the
stock, so the excess return has no FX distortion). success = beat the benchmark.

Entries are ingested from history.json (not the live alert list) so first-run
backfill, steady-state daily adds, and self-healing of benchmark-outage days are
one code path. An entry matures after EVAL_WINDOW_DAYS and freezes forever.

Rides the daily scan like sectors.py / forex.py: self-contained, failure-isolated
(raises on benchmark outage → scan keeps the previous file), and byte-stable
(generated_at preserved when nothing changed → holiday re-runs are no-op commits).
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import fetch_us

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
SCHEMA_VERSION = 1

# Each market benchmarked against its own index (same currency as the stock).
MARKET_BENCHMARK = {"us": "SPY", "de": "^GDAXI", "bist": "XU100.IS"}
EVAL_WINDOW_DAYS = 180  # entry "matures" (freezes) once held this long — a settled window
MAX_ENTRIES = 1000      # safety cap; drops oldest matured first (won't trigger for years)
MIN_BENCH_BARS = 200    # a 2y daily index series has ~500 bars; guard against garbage


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def market_of(symbol: str) -> str:
    if symbol.endswith(".IS"):
        return "bist"
    if symbol.endswith(".DE"):
        return "de"
    return "us"


def entry_id(ticker: str, rule: str, entry_date: str) -> str:
    """Dedup key. entry_date is part of it so a genuine re-fire of the same
    (ticker, rule) months later is a distinct tracked event, not an overwrite."""
    return f"{ticker}|{rule}|{entry_date}"


def nearest_prior(date_iso: str, sorted_dates: list[str]) -> str | None:
    """Largest date <= target in a sorted list (the index bar to anchor to when
    the exact entry_date has no bar). None if target precedes all dates."""
    i = bisect.bisect_right(sorted_dates, date_iso)
    return sorted_dates[i - 1] if i > 0 else None


def _days(entry_date: str, bar_date: str) -> int:
    return (dt.date.fromisoformat(bar_date) - dt.date.fromisoformat(entry_date)).days


def new_entries_from_history(history: dict) -> list[dict]:
    """Identity seeds for every BUY alert across the history window, deduped by
    id. Pure (no benchmark data). An alert fires only on its cross bar, so each
    event appears on exactly one history day — no duplicate events."""
    seen: dict[str, dict] = {}
    for day in history.get("days", []):
        for a in day.get("alerts", []):
            if a.get("verdict") != "buy":
                continue
            ticker, rule, date = a["ticker"], a["rule"], a["date"]
            _id = entry_id(ticker, rule, date)
            if _id in seen:
                continue
            m = market_of(ticker)
            seen[_id] = {
                "id": _id,
                "ticker": ticker,
                "market": m,
                "category": a.get("category"),
                "rule": rule,
                "direction": a.get("direction"),
                "verdict": "buy",
                "entry_date": date,
                "entry_price": a["close"],
                "benchmark": MARKET_BENCHMARK.get(m),
            }
    return list(seen.values())


def finalize_seed(seed: dict, benches: dict) -> dict:
    """Turn an identity seed into a full 'open' entry, freezing the benchmark's
    close on the entry date (nearest-prior trading day)."""
    b = benches.get(seed["market"])
    anchor = None
    if b:
        d = seed["entry_date"]
        anchor = b["by_date"].get(d)
        if anchor is None:
            nd = nearest_prior(d, b["sorted_dates"])
            anchor = b["by_date"].get(nd) if nd else None
    return {
        **seed,
        "entry_bench_close": anchor,
        "last_date": None,
        "last_price": None,
        "stock_return_pct": None,
        "bench_return_pct": None,
        "excess_pct": None,
        "success": None,
        "days_held": 0,
        "status": "open",
    }


def merge(existing: list[dict], seeds: list[dict], benches: dict) -> list[dict]:
    """existing + new seeds (finalized). Only ADDS unseen ids — never drops or
    resets a tracked entry, so accumulation is preserved and an entry that aged
    out of the 30-day history keeps being tracked."""
    by_id = {e["id"] for e in existing}
    out = list(existing)
    for s in seeds:
        if s["id"] not in by_id:
            out.append(finalize_seed(s, benches))
    return out


def update_entry(entry: dict, prices: dict, benches: dict, bar_date: str) -> dict:
    """Recompute an open entry's daily fields. Matured entries are frozen."""
    if entry.get("status") == "matured":
        return entry
    e = dict(entry)
    px = prices.get(e["ticker"])
    # carry the previous price forward if this ticker isn't in today's prices
    # (partial scan / left universe) — never a false 0%.
    last_price = px["close"] if px and px.get("close") is not None else e.get("last_price")
    e["last_price"] = last_price
    e["last_date"] = bar_date

    ep = e["entry_price"]
    e["stock_return_pct"] = round((last_price / ep - 1) * 100, 2) if last_price and ep else None

    b = benches.get(e["market"])
    bench_last = b["last_close"] if b else None
    ebc = e.get("entry_bench_close")
    e["bench_return_pct"] = round((bench_last / ebc - 1) * 100, 2) if bench_last and ebc else None

    if e["stock_return_pct"] is not None and e["bench_return_pct"] is not None:
        e["excess_pct"] = round(e["stock_return_pct"] - e["bench_return_pct"], 2)
        e["success"] = e["excess_pct"] > 0
    else:
        e["excess_pct"] = None
        e["success"] = None

    # bar_date only moves forward in production, so this is never negative; the
    # clamp defends against a backfill run against an older bar than an entry.
    e["days_held"] = max(0, _days(e["entry_date"], bar_date))
    if e["days_held"] >= EVAL_WINDOW_DAYS:
        e["status"] = "matured"
    return e


def _cap(entries: list[dict]) -> list[dict]:
    if len(entries) <= MAX_ENTRIES:
        return entries
    open_e = [e for e in entries if e.get("status") != "matured"]
    matured = sorted((e for e in entries if e.get("status") == "matured"),
                     key=lambda e: e["entry_date"])
    drop = len(entries) - MAX_ENTRIES
    kept = open_e + matured[drop:]  # drop oldest matured first; never drop open
    kept.sort(key=lambda e: e["id"])
    return kept


def _fetch_benches(markets: set[str], bar_dates: dict | None = None) -> dict:
    """{market: {symbol, by_date, sorted_dates, last_date, last_close}} for the
    given markets. Raises if any needed index is unavailable (failure-isolated
    upstream) — keeps the output deterministic rather than flapping columns.

    `last_close` is the benchmark's close AS OF that market's scan bar date
    (nearest-prior), not merely Yahoo's latest bar — so each stock's return is
    measured over the same window as its benchmark, and the output is immune to
    an intraday-forming latest bar (e.g. backfilling while a market is open)."""
    bar_dates = bar_dates or {}
    out: dict[str, dict] = {}
    for m in sorted(markets):
        sym = MARKET_BENCHMARK[m]
        df = fetch_us(sym, period="2y")
        if df.empty or len(df) < MIN_BENCH_BARS:
            raise RuntimeError(f"benchmark {sym} ({m}) unavailable")
        by_date = {ix.date().isoformat(): round(float(c), 2)
                   for ix, c in zip(df.index, df["close"])}
        sorted_dates = sorted(by_date)
        as_of = nearest_prior(bar_dates.get(m, sorted_dates[-1]), sorted_dates) or sorted_dates[-1]
        out[m] = {
            "symbol": sym, "by_date": by_date, "sorted_dates": sorted_dates,
            "last_date": as_of, "last_close": by_date[as_of],
        }
    return out


def build(output_dir: Path = DEFAULT_OUTPUT_DIR, prices: dict | None = None,
          bar_date: str | None = None, bar_dates: dict | None = None,
          benches: dict | None = None, history: dict | None = None,
          now: dt.datetime | None = None) -> dict:
    prices = prices or {}
    if history is None:
        history = _load(output_dir / "history.json") or {"days": []}
    prev = _load(output_dir / "track_record.json")
    existing = prev.get("entries", []) if prev else []
    seeds = new_entries_from_history(history)

    if benches is None:
        # only the markets we actually track-open need a live index this run
        needed = {s["market"] for s in seeds}
        needed |= {e["market"] for e in existing if e.get("status") != "matured"}
        needed &= set(MARKET_BENCHMARK)
        benches = _fetch_benches(needed, bar_dates)

    entries = merge(existing, seeds, benches)
    entries = [update_entry(e, prices, benches, bar_date) for e in entries]
    entries.sort(key=lambda e: e["id"])
    entries = _cap(entries)

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": bar_date,
        "benchmarks": {m: {"symbol": b["symbol"], "last_date": b["last_date"],
                           "last_close": b["last_close"]}
                       for m, b in sorted(benches.items())},
        "entries": entries,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "track_record.json"
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    path.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # standalone: reuse the last full scan's prices.json + history.json
    pd_data = _load(DEFAULT_OUTPUT_DIR / "prices.json") or {}
    px = pd_data.get("prices", {})
    bar_dates = pd_data.get("bar_dates", {})
    bar = max(bar_dates.values()) if bar_dates else "1970-01-01"
    d = build(prices=px, bar_date=bar, bar_dates=bar_dates)
    ok = [e for e in d["entries"] if e["success"]]
    print(f"track_record.json: {len(d['entries'])} entries, "
          f"{len(ok)} beating benchmark, bar_date={d['bar_date']}")
    for e in sorted(d["entries"], key=lambda e: (e["excess_pct"] is None, -(e["excess_pct"] or 0)))[:12]:
        print(f"  {e['ticker']:<8} {e['market']:<4} entry {e['entry_date']} "
              f"ret={e['stock_return_pct']} vs {e['benchmark']} "
              f"excess={e['excess_pct']} {'WIN' if e['success'] else 'lag'} ({e['status']})")
