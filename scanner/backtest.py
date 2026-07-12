"""Backtest the Phase-1 alert rules over past years.

Replays the exact cross semantics of the live rules (<= then > on
close/SMA, computed on raw Close like the daily scan) over history and
measures forward returns after each signal at several horizons, against the
unconditional baseline of holding the same universe on any random day.

Usage:
  python scanner/backtest.py                 # full universe, last 5 years
  python scanner/backtest.py --years 3
  python scanner/backtest.py --limit 50      # quicker sample run
  python scanner/backtest.py --report PATH   # also write a markdown report

Caveat baked into any study like this: the universe is TODAY'S index members,
so results carry survivorship bias — stocks that crashed out of the index
aren't tested. Treat absolute numbers as optimistic; relative comparisons
(rule vs baseline, bull vs bear) are the meaningful part.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import iter_us_chunks
from indicators import sma
from scan import load_universe

HORIZONS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
RULE_DIRECTION = {
    "PRICE_SMA200_BULL": "bullish",
    "PRICE_SMA200_BEAR": "bearish",
    "GOLDEN_CROSS": "bullish",
    "DEATH_CROSS": "bearish",
}


def detect_all_events(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Boolean series per rule over the whole history (same <=/> semantics
    as the live alerts in alerts/sma_cross.py)."""
    close = df["close"]
    s50, s200 = sma(close, 50), sma(close, 200)
    pc, p50, p200 = close.shift(1), s50.shift(1), s200.shift(1)
    return {
        "PRICE_SMA200_BULL": (pc <= p200) & (close > s200),
        "PRICE_SMA200_BEAR": (pc >= p200) & (close < s200),
        "GOLDEN_CROSS": (p50 <= p200) & (s50 > s200),
        "DEATH_CROSS": (p50 >= p200) & (s50 < s200),
    }


def forward_returns(close: pd.Series) -> dict[str, pd.Series]:
    return {label: close.shift(-h) / close - 1 for label, h in HORIZONS.items()}


def run_backtest(symbols: list[str], years: int):
    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * years))
    events: list[dict] = []
    baseline: dict[str, list[np.ndarray]] = {h: [] for h in HORIZONS}
    fetched = failed = 0

    for chunk in iter_us_chunks(symbols, period="10y"):
        for sym, df in chunk.items():
            fetched += 1
            if df.empty or len(df) < 260:
                failed += 1
                continue
            df = df.copy()
            df.index = pd.DatetimeIndex(df.index).tz_localize(None)
            fwd = forward_returns(df["close"])
            in_window = df.index >= cutoff

            for label in HORIZONS:
                vals = fwd[label].to_numpy()[in_window]
                baseline[label].append(vals[~np.isnan(vals)].astype(np.float32))

            for rule, mask in detect_all_events(df).items():
                for ts in df.index[mask & in_window]:
                    row = {"ticker": sym, "rule": rule, "date": ts.date().isoformat()}
                    for label in HORIZONS:
                        v = fwd[label].at[ts]
                        row[label] = None if np.isnan(v) else float(v)
                    events.append(row)
        print(f"  fetched {fetched}/{len(symbols)}", file=sys.stderr)

    base_stats = {}
    for label, arrs in baseline.items():
        all_vals = np.concatenate(arrs) if arrs else np.array([])
        base_stats[label] = {
            "n": len(all_vals),
            "mean": float(np.mean(all_vals)) if len(all_vals) else None,
            "median": float(np.median(all_vals)) if len(all_vals) else None,
            "win": float(np.mean(all_vals > 0)) if len(all_vals) else None,
        }
    return events, base_stats, failed


def summarize(events: list[dict], base_stats: dict) -> dict:
    out: dict = {"baseline": base_stats, "rules": {}}
    df = pd.DataFrame(events)
    for rule in RULE_DIRECTION:
        sub = df[df["rule"] == rule] if not df.empty else pd.DataFrame()
        stats = {"events": len(sub), "direction": RULE_DIRECTION[rule], "horizons": {}}
        for label in HORIZONS:
            vals = sub[label].dropna().to_numpy() if len(sub) else np.array([])
            if len(vals) == 0:
                stats["horizons"][label] = None
                continue
            bull = RULE_DIRECTION[rule] == "bullish"
            stats["horizons"][label] = {
                "n": len(vals),
                "mean": float(np.mean(vals)),
                "median": float(np.median(vals)),
                # success: price moved the way the signal pointed
                "success": float(np.mean(vals > 0) if bull else np.mean(vals < 0)),
                "vs_baseline": float(np.mean(vals) - base_stats[label]["mean"]),
            }
        out["rules"][rule] = stats
    return out


def fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:+.1f}%"


def print_report(summary: dict, years: int, universe_n: int) -> str:
    lines = [f"# Backtest — Phase 1 alerts, last {years} years",
             "",
             f"Universe: {universe_n} tickers (today's S&P 500 + Nasdaq 100 — "
             f"survivorship bias inflates absolute numbers; compare vs baseline).",
             "",
             "**Baseline** = forward return of holding any universe stock from any day in the window.",
             "",
             "| Horizon | Baseline mean | Baseline % positive |",
             "|---|---|---|"]
    for label in HORIZONS:
        b = summary["baseline"][label]
        lines.append(f"| {label} | {fmt_pct(b['mean'])} | {b['win'] * 100:.0f}% |")
    for rule, stats in summary["rules"].items():
        arrow = "▲" if stats["direction"] == "bullish" else "▼"
        lines += ["", f"## {arrow} {rule} — {stats['events']} signals", "",
                  "| Horizon | n | Mean return | Median | Success rate | Edge vs baseline |",
                  "|---|---|---|---|---|---|"]
        for label in HORIZONS:
            h = stats["horizons"][label]
            if h is None:
                lines.append(f"| {label} | 0 | — | — | — | — |")
                continue
            lines.append(f"| {label} | {h['n']} | {fmt_pct(h['mean'])} | {fmt_pct(h['median'])} "
                         f"| {h['success'] * 100:.0f}% | {fmt_pct(h['vs_baseline'])} |")
    lines += ["",
              "Success rate: share of signals where price moved in the signal's direction ",
              "(up after bullish, down after bearish) by the horizon.",
              "Edge vs baseline: signal's mean return minus the unconditional mean.", ""]
    report = "\n".join(lines)
    print(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest alert rules")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--limit", type=int, help="first N universe tickers only")
    parser.add_argument("--report", type=Path, help="write markdown report here")
    args = parser.parse_args(argv)

    symbols = load_universe()["us"]  # research tools stay US-only
    if args.limit:
        symbols = symbols[: args.limit]

    events, base_stats, failed = run_backtest(symbols, args.years)
    print(f"\n{len(events)} signals from {len(symbols) - failed}/{len(symbols)} tickers "
          f"({failed} skipped)\n", file=sys.stderr)
    summary = summarize(events, base_stats)
    report = print_report(summary, args.years, len(symbols))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
