"""Daily scan entrypoint.

Fetches daily bars for the universe, runs every alert rule on each ticker,
and writes latest.json + history.json for the dashboard.

Usage:
  python scanner/scan.py                         # full universe
  python scanner/scan.py --tickers AAPL,MSFT     # specific tickers
  python scanner/scan.py --limit 30              # first N of the universe
  python scanner/scan.py --dry-run               # print, don't write files
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import iter_us_chunks
from indicators import sma

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
MIN_BARS = 201  # today's AND yesterday's SMA200

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("scan")


def load_universe() -> dict[str, list[str]]:
    """Return {market: [symbols]} — e.g. {"us": [...], "bist": [...]}."""
    with open(SCANNER_DIR / "universe.json") as fh:
        return json.load(fh)["markets"]


MARKET_ORDER = {"us": 0, "de": 1, "bist": 2}


def market_of(symbol: str) -> str:
    if symbol.endswith(".IS"):
        return "bist"
    if symbol.endswith(".DE"):
        return "de"
    return "us"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SMA cross scanner")
    parser.add_argument("--tickers", help="comma-separated tickers (overrides universe)")
    parser.add_argument("--limit", type=int, help="scan only the first N universe tickers")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true",
                        help="print latest close/SMA50/SMA200 per ticker; write nothing")
    args = parser.parse_args(argv)

    if args.tickers:
        symbols = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        markets = load_universe()
        symbols = [s for market_syms in markets.values() for s in market_syms]
        if args.limit:
            symbols = symbols[: args.limit]

    logger.info("scanning %d tickers", len(symbols))

    frames: dict[str, "pd.DataFrame"] = {}
    done = 0
    # 6y (not 2y): the 200-week SMA rule needs ~201 weekly bars plus buffer
    for chunk in iter_us_chunks(symbols, period="6y"):
        frames.update(chunk)
        done += len(chunk)
        logger.info("fetched %d/%d", done, len(symbols))

    if args.dry_run:
        print(f"{'ticker':<8}{'bars':>6}{'date':>12}{'close':>10}{'sma50':>10}{'sma200':>10}")
        for sym in symbols:
            df = frames.get(sym)
            if df is None or df.empty:
                print(f"{sym:<8}{'FAIL':>6}")
                continue
            s50, s200 = sma(df["close"], 50).iloc[-1], sma(df["close"], 200).iloc[-1]
            print(f"{sym:<8}{len(df):>6}{df.index[-1].date().isoformat():>12}"
                  f"{df['close'].iloc[-1]:>10.2f}{s50:>10.2f}{s200:>10.2f}")
        return 0

    from alerts import RULES
    from output import write_results

    failures = sorted(sym for sym, df in frames.items() if df.empty)
    ok = {sym: df for sym, df in frames.items() if not df.empty}
    if len(symbols) > 10 and len(failures) > len(symbols) / 2:
        logger.error("%d/%d tickers failed — Yahoo likely down, aborting without "
                     "writing output", len(failures), len(symbols))
        return 1

    # Latest bar date PER MARKET: BIST and US have different holidays, so a
    # US-only trading day must not mark every BIST ticker stale (and vice
    # versa). Within its own market, a ticker lagging the market's latest bar
    # is stale (Yahoo hiccup) — evaluating it would produce off-by-one crosses.
    bar_dates = {
        m: max(df.index[-1].date() for s, df in ok.items() if market_of(s) == m).isoformat()
        for m in {market_of(s) for s in ok}
    }
    bar_date = max(bar_dates.values())

    insufficient = sorted(sym for sym, df in ok.items() if len(df) < MIN_BARS)
    stale = sorted(sym for sym, df in ok.items()
                   if df.index[-1].date().isoformat() != bar_dates[market_of(sym)])

    alerts = []
    for sym, df in ok.items():
        if sym in insufficient or sym in stale:
            continue
        for rule in RULES:
            alerts.extend(rule.evaluate(sym, df))
    alerts.sort(key=lambda a: (a.category, MARKET_ORDER.get(market_of(a.ticker), 9),
                               a.ticker))

    # Latest close for every scanned ticker — written to prices.json below and
    # fed to the sectors build, which ranks constituents by shares x close.
    from alerts.base import px_round
    prices = {}
    for sym, df in ok.items():
        c = df["close"]
        last = float(c.iloc[-1])
        prices[sym] = {
            "close": px_round(last),
            "chg_1d_pct": round((last / float(c.iloc[-2]) - 1.0) * 100, 2)
            if len(c) > 1 else None,
        }

    # Sector rotation first, so verdicts can factor in whether a US stock's
    # sector is leading or lagging the market. Failure -> empty map -> no effect.
    sector_states: dict[str, str] = {}
    try:
        from sectors import build as build_sectors
        sec = build_sectors(args.output_dir, prices=prices)
        sector_states = {r["symbol"]: r["state"] for r in sec["sectors"]}
        logger.info("sectors: %d ranked, bar_date=%s", len(sec["sectors"]), sec["bar_date"])
    except Exception as exc:
        logger.warning("sectors build failed (%s) — keeping previous sectors.json", exc)

    # Enrich each alert with a buy/hold/sell verdict: MACD confirmation from
    # the bars already in memory + fundamentals fetched only for alerted names.
    # Also attach price-structure context (Fibonacci) and volume confirmation —
    # display-only for now, computed from the OHLCV already in memory.
    from indicators import macd, volume_signal
    from levels import fib_block
    from recommend import (SECTOR_TO_SPDR, fetch_fundamentals, sector_factor,
                           verdict as combine_verdict)

    fundamentals_cache: dict[str, dict | None] = {}
    alert_dicts = []
    for a in alerts:
        d = a.to_dict()
        mkt = market_of(a.ticker)
        line, sig = macd(ok[a.ticker]["close"])
        macd_ok = bool(line.iloc[-1] > sig.iloc[-1]) if a.direction == "bullish" \
            else bool(line.iloc[-1] < sig.iloc[-1])
        if a.ticker not in fundamentals_cache:
            fundamentals_cache[a.ticker] = fetch_fundamentals(a.ticker)
        fund = fundamentals_cache[a.ticker]

        # Sector rotation applies to US stocks only (SPDR ETFs are US-market).
        sector_name = fund.get("sector") if fund else None
        spdr = SECTOR_TO_SPDR.get(sector_name) if (sector_name and mkt == "us") else None
        state = sector_states.get(spdr) if spdr else None
        sector = ({"name": sector_name, "symbol": spdr, "state": state,
                   "factor": sector_factor(state)} if spdr else None)

        v, reason = combine_verdict(a.direction, macd_ok,
                                    fund["score"] if fund else None, state,
                                    a.category)
        d.update({
            "market": mkt,
            "macd_confirms": macd_ok,
            "fundamentals": fund,  # full detail: score, rating, factors, metrics
            "sector": sector,
            "fib": fib_block(ok[a.ticker]),        # daily + weekly retracements
            "volume": volume_signal(ok[a.ticker]["volume"]),
            "verdict": v,
            "verdict_reason": reason,
        })
        alert_dicts.append(d)

    meta = {
        "bar_date": bar_date,
        "bar_dates": bar_dates,
        "universe_count": len(symbols),
        "scanned": len(ok) - len(stale),
        "failures": failures + stale,
        "insufficient_history": insufficient,
    }
    write_results(alert_dicts, meta, args.output_dir)
    logger.info("bar_date=%s alerts=%d failures=%d insufficient=%d",
                bar_date, len(alerts), len(meta["failures"]), len(insufficient))

    # prices.json: latest close for every scanned ticker, so the portfolio
    # page can value any universe holding (not just today's alerted names).
    from output import write_prices
    write_prices(prices, bar_dates, args.output_dir)
    logger.info("prices.json: %d tickers", len(prices))

    # Per-ticker health snapshot rides along: daily technical STATE (vs SMAs,
    # RSI, MACD, trend, drawdown, sector) + a 30-day memory of bearish/trim
    # alerts, so the Portfolio page can warn about a deteriorating holding
    # instead of only on the day a line is crossed.
    try:
        from health import build as build_health
        # per-ticker sector state via the membership cache -> SPDR -> state
        tsectors: dict[str, str] = {}
        try:
            membership = json.loads(
                (SCANNER_DIR / "sector_membership.json").read_text())["tickers"]
            for sym, m in membership.items():
                spdr = SECTOR_TO_SPDR.get(m.get("sector"))
                if spdr and spdr in sector_states:
                    tsectors[sym] = sector_states[spdr]
        except (OSError, ValueError, KeyError):
            pass
        hl = build_health(args.output_dir, frames=ok, bar_date=bar_date,
                          sector_states=tsectors)
        logger.info("health: %d tickers, %d with recent warnings",
                    len(hl["tickers"]),
                    sum(1 for t in hl["tickers"].values() if t.get("recent_warnings")))
    except Exception as exc:
        logger.warning("health build failed (%s) — keeping previous health.json", exc)

    # Permanent alert archive rides along: unions history.json (just written)
    # into archive/alerts.jsonl so entry context survives the 30-day window.
    try:
        from archive import update as update_archive
        ar = update_archive()
        logger.info("archive: %d alerts (+%d new%s)", ar["total"], ar["added"],
                    ", written" if ar["changed"] else "")
    except Exception as exc:
        logger.warning("archive update failed (%s) — keeping previous alerts.jsonl", exc)

    # Track record rides along: ingests today's BUY verdicts (already persisted
    # to history.json by write_results) and updates every tracked entry's return
    # vs its market index. Failure-isolated + accumulates its own JSON.
    try:
        from track_record import build as build_track_record
        tr = build_track_record(args.output_dir, prices=prices, bar_date=bar_date,
                                bar_dates=bar_dates)
        wins = sum(1 for e in tr["entries"] if e["success"])
        logger.info("track_record: %d entries (%d beating benchmark), bar_date=%s",
                    len(tr["entries"]), wins, tr["bar_date"])
    except Exception as exc:
        logger.warning("track_record build failed (%s) — keeping previous track_record.json", exc)

    # Rolling analyst-target cache rides along: refreshes the stalest ~130
    # tickers each run so every universe ticker's target stays <~1 week old.
    try:
        from targets import build as build_targets
        tg = build_targets(args.output_dir, bar_date=bar_date)
        logger.info("targets: %d cached (%d refreshed)",
                    len(tg["targets"]), tg["_refreshed"])
    except Exception as exc:
        logger.warning("targets build failed (%s) — keeping previous targets.json", exc)

    # Sector baselines ride along: ingest the profiles already fetched for
    # alerted tickers (free) + refresh the stalest ~40 universe tickers, then
    # recompute per-sector quartiles powering the profile green/red coloring.
    try:
        from baselines import refresh as refresh_baselines
        fresh = {t: {"sector": f.get("sector"), "metrics": f.get("profile")}
                 for t, f in fundamentals_cache.items() if f}
        bl = refresh_baselines(args.output_dir, bar_date=bar_date,
                               universe=symbols, fresh=fresh)
        logger.info("baselines: %d tickers cached, %d sectors published (+%d refreshed)",
                    bl["coverage"], bl["sectors"], bl["refreshed"])
    except Exception as exc:
        logger.warning("baselines refresh failed (%s) — keeping previous baselines.json", exc)

    # Forex snapshot rides along (sectors already built above for the verdict);
    # its failure must never sink the stock scan — it keeps its previous JSON.
    try:
        from forex import build as build_forex
        fx = build_forex(args.output_dir)
        logger.info("forex: %d currencies, bar_date=%s",
                    len(fx["currencies"]), fx["bar_date"])
    except Exception as exc:
        logger.warning("forex build failed (%s) — keeping previous forex.json", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
