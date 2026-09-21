"""Alert track record — a live scoreboard of whether BUY alerts beat their market.

Unlike the other outputs this JSON ACCUMULATES: each run reads its own previous
output and adds to it. When a stock gets a BUY verdict it becomes a tracked
`entry` (captured at its alert-day close); every subsequent daily scan updates
that entry with the latest close and its return SINCE the alert, compared to the
stock's own-market index (US→SPY, DE→DAX, BIST→XU100 — same currency as the
stock, so the excess return has no FX distortion). success = beat the benchmark.

US entries carry a SECOND, equal-weight comparison (vs RSP) alongside the
cap-weighted one. The two answer different questions: cap-weighted asks "did the
signal beat the index you could have bought", equal-weight asks "did it beat the
average stock". In a narrow tape a handful of megacaps can carry SPY while the
median stock falls, which makes a breadth-driven scanner look broken when it is
merely long the average name — measuring both separates signal quality from
regime. Both are reported; neither gates anything.

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
SCHEMA_VERSION = 2

# Each market benchmarked against its own index (same currency as the stock).
MARKET_BENCHMARK = {"us": "SPY", "de": "^GDAXI", "bist": "XU100.IS"}
# Equal-weight counterpart — the "average stock" control, same 500 names as SPY
# at equal weight. US-only: the free feed has no comparable equal-weight index
# for the DAX or BIST 100, so those markets report the cap-weighted number
# alone (same US-only shape as the sector factor in recommend.py). Secondary by
# design — an outage here degrades to null fields, it never fails the output.
MARKET_BENCHMARK_EW = {"us": "RSP"}
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
                # analyst mean target as of the alert day (None if unavailable);
                # lets the scoreboard flag "🎯 target reached" and measure how
                # often buys actually get there
                "target_mean": _target_of(a),
            }
    return list(seen.values())


def _target_of(a: dict) -> float | None:
    return ((a.get("fundamentals") or {}).get("analyst") or {}).get("target_mean")


def anchor_close(series: dict | None, date_iso: str) -> float | None:
    """An index's close on date_iso, falling back to the nearest prior trading
    day (entry dates land on holidays / other markets' closed days)."""
    if not series:
        return None
    c = series["by_date"].get(date_iso)
    if c is None:
        nd = nearest_prior(date_iso, series["sorted_dates"])
        c = series["by_date"].get(nd) if nd else None
    return c


def finalize_seed(seed: dict, benches: dict) -> dict:
    """Turn an identity seed into a full 'open' entry, freezing each benchmark's
    close on the entry date (nearest-prior trading day)."""
    b = benches.get(seed["market"]) or {}
    return {
        **seed,
        "entry_bench_close": anchor_close(b or None, seed["entry_date"]),
        "benchmark_ew": MARKET_BENCHMARK_EW.get(seed["market"]),
        "entry_bench_ew_close": anchor_close(b.get("ew"), seed["entry_date"]),
        "last_date": None,
        "last_price": None,
        "stock_return_pct": None,
        "bench_return_pct": None,
        "excess_pct": None,
        "success": None,
        "bench_ew_return_pct": None,
        "excess_ew_pct": None,
        "success_ew": None,
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


def _vs_benchmark(stock_return_pct: float | None, last_close: float | None,
                  entry_close: float | None) -> tuple[float | None, float | None, bool | None]:
    """(bench_return_pct, excess_pct, success) for one benchmark. Any missing
    leg yields nulls rather than a false 0% — the column reads '—' instead of
    claiming the signal matched its index."""
    bench_ret = (round((last_close / entry_close - 1) * 100, 2)
                 if last_close and entry_close else None)
    if stock_return_pct is None or bench_ret is None:
        return bench_ret, None, None
    excess = round(stock_return_pct - bench_ret, 2)
    return bench_ret, excess, excess > 0


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

    b = benches.get(e["market"]) or {}
    e["bench_return_pct"], e["excess_pct"], e["success"] = _vs_benchmark(
        e["stock_return_pct"], b.get("last_close"), e.get("entry_bench_close"))
    # equal-weight leg: present for US only, null everywhere else (and on an
    # RSP outage) — a separate read of the same entry, never a gate.
    ew = b.get("ew") or {}
    e["bench_ew_return_pct"], e["excess_ew_pct"], e["success_ew"] = _vs_benchmark(
        e["stock_return_pct"], ew.get("last_close"), e.get("entry_bench_ew_close"))

    tgt = e.get("target_mean")
    e["target_reached"] = bool(last_price and tgt and last_price >= tgt) if tgt else None

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


def _index_series(symbol: str, as_of: str | None) -> dict:
    """{symbol, by_date, sorted_dates, last_date, last_close} for one index.
    Raises if the series is missing or too short to trust.

    `last_close` is the index's close AS OF the scan's bar date (nearest-prior),
    not merely Yahoo's latest bar — so each stock's return is measured over the
    same window as its benchmark, and the output is immune to an intraday-forming
    latest bar (e.g. backfilling while a market is open)."""
    df = fetch_us(symbol, period="2y")
    if df.empty or len(df) < MIN_BENCH_BARS:
        raise RuntimeError(f"benchmark {symbol} unavailable")
    by_date = {ix.date().isoformat(): round(float(c), 2)
               for ix, c in zip(df.index, df["close"])}
    sorted_dates = sorted(by_date)
    anchor = nearest_prior(as_of or sorted_dates[-1], sorted_dates) or sorted_dates[-1]
    return {
        "symbol": symbol, "by_date": by_date, "sorted_dates": sorted_dates,
        "last_date": anchor, "last_close": by_date[anchor],
    }


def _fetch_benches(markets: set[str], bar_dates: dict | None = None) -> dict:
    """{market: <index series>, optionally + "ew": <equal-weight series>} for
    the given markets. Raises if a market's PRIMARY index is unavailable
    (failure-isolated upstream) — keeps the output deterministic rather than
    flapping columns. The equal-weight leg is secondary: an outage there logs
    and drops to null fields instead of taking the whole scoreboard down."""
    bar_dates = bar_dates or {}
    out: dict[str, dict] = {}
    for m in sorted(markets):
        try:
            series = _index_series(MARKET_BENCHMARK[m], bar_dates.get(m))
        except RuntimeError as exc:
            raise RuntimeError(f"{exc} ({m})") from exc
        ew_symbol = MARKET_BENCHMARK_EW.get(m)
        if ew_symbol:
            try:
                series["ew"] = _index_series(ew_symbol, bar_dates.get(m))
            except Exception as exc:  # secondary metric — degrade, never abort
                logger.warning("equal-weight benchmark %s (%s) unavailable: %s",
                               ew_symbol, m, exc)
        out[m] = series
    return out


def _bench_meta(series: dict) -> dict:
    meta = {k: series[k] for k in ("symbol", "last_date", "last_close")}
    if series.get("ew"):
        meta["ew"] = _bench_meta(series["ew"])
    return meta


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

    # migration: entries tracked before the target_mean field existed get it
    # filled from history while their alert is still inside the window
    seed_targets = {s["id"]: s.get("target_mean") for s in seeds}
    for e in entries:
        if "target_mean" not in e:
            e["target_mean"] = seed_targets.get(e["id"])
        # migration: the equal-weight anchor is recoverable from the index
        # series for ANY past entry date, so entries tracked before this field
        # existed backfill exactly — no rescan, no gap in the new column.
        # Matured entries are skipped: update_entry won't recompute their
        # derived fields, so anchoring them would leave a half-filled row.
        if e.get("status") != "matured" and e.get("entry_bench_ew_close") is None:
            e["benchmark_ew"] = MARKET_BENCHMARK_EW.get(e["market"])
            e["entry_bench_ew_close"] = anchor_close(
                (benches.get(e["market"]) or {}).get("ew"), e["entry_date"])

    entries = [update_entry(e, prices, benches, bar_date) for e in entries]
    entries.sort(key=lambda e: e["id"])
    entries = _cap(entries)

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": bar_date,
        "benchmarks": {m: _bench_meta(b) for m, b in sorted(benches.items())},
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
    # both reads on the SAME subset — the equal-weight entries — so the two
    # hit-rates are comparable rather than two different denominators
    # .get(): matured entries predate the field and are never recomputed
    ew = [e for e in d["entries"] if e.get("excess_ew_pct") is not None]
    if ew:
        cap_hits = sum(1 for e in ew if e["success"])
        ew_hits = sum(1 for e in ew if e["success_ew"])
        print(f"  equal-weight check ({len(ew)} US entries): "
              f"beat cap-weighted {100 * cap_hits / len(ew):.0f}% · "
              f"beat equal-weighted {100 * ew_hits / len(ew):.0f}%")
    for e in sorted(d["entries"], key=lambda e: (e["excess_pct"] is None, -(e["excess_pct"] or 0)))[:12]:
        print(f"  {e['ticker']:<8} {e['market']:<4} entry {e['entry_date']} "
              f"ret={e['stock_return_pct']} vs {e['benchmark']} "
              f"excess={e['excess_pct']} {'WIN' if e['success'] else 'lag'} ({e['status']})")
