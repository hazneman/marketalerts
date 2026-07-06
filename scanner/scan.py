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


def load_universe() -> list[str]:
    with open(SCANNER_DIR / "universe.json") as fh:
        return json.load(fh)["tickers"]


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
        symbols = load_universe()
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

    # Global latest bar date; tickers lagging behind it are stale (Yahoo hiccup)
    # and evaluating them would produce off-by-one crosses.
    bar_date = max(df.index[-1].date() for df in ok.values()).isoformat()

    insufficient = sorted(sym for sym, df in ok.items() if len(df) < MIN_BARS)
    stale = sorted(sym for sym, df in ok.items()
                   if df.index[-1].date().isoformat() != bar_date)

    alerts = []
    for sym, df in ok.items():
        if sym in insufficient or sym in stale:
            continue
        for rule in RULES:
            alerts.extend(rule.evaluate(sym, df))
    alerts.sort(key=lambda a: (a.category, a.ticker))

    meta = {
        "bar_date": bar_date,
        "universe_count": len(symbols),
        "scanned": len(ok) - len(stale),
        "failures": failures + stale,
        "insufficient_history": insufficient,
    }
    write_results(alerts, meta, args.output_dir)
    logger.info("bar_date=%s alerts=%d failures=%d insufficient=%d",
                bar_date, len(alerts), len(meta["failures"]), len(insufficient))

    # Forex snapshot rides along; its failure must never sink the stock scan.
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
