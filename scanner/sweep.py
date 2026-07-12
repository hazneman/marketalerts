"""Parameter sweep for the SMA trend strategy + out-of-sample validation.

Grid: SMA length x confirmation days x hysteresis band. Every combo is
backtested on the RECENT window (last `--years`), ranked by median per-ticker
return, and the top combos are then re-tested on the EARLIER window
(years 2x..1x ago, e.g. 2016-2021) that played no part in selecting them.
A combo that only wins in-sample is curve-fitting; one that also holds up
out-of-sample deserves some trust.

Usage:
  python scanner/sweep.py                     # full universe, 5y select + 5y validate
  python scanner/sweep.py --limit 50          # quick sample
  python scanner/sweep.py --report docs/SWEEP.md
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
from scan import load_universe
from strategy_backtest import simulate, summarize

SMA_LENGTHS = [100, 150, 200]
CONFIRM_DAYS = [2, 5, 10]
BANDS = [0.0, 0.01, 0.02, 0.03]
TOP_N_VALIDATE = 3


def fetch_all(symbols: list[str]) -> dict[str, pd.DataFrame]:
    # "max" (not 10y): the out-of-sample window starts 10y ago and the SMA
    # warm-up consumes ~10 months before that, so we need pre-2016 history.
    frames: dict[str, pd.DataFrame] = {}
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="max"):
        frames.update({s: d for s, d in chunk.items() if not d.empty})
        fetched += len(chunk)
        print(f"  fetched {fetched}/{len(symbols)}", file=sys.stderr)
    return frames


def evaluate(frames: dict[str, pd.DataFrame], years: int, sma_n: int,
             confirm: int, band: float,
             until: pd.Timestamp | None = None) -> dict | None:
    results = {}
    for sym, df in frames.items():
        r = simulate(df, years, sma_n, confirm, None, band, until)
        if r is not None:
            results[sym] = r
    if not results:
        return None
    s = summarize(results)
    s["params"] = {"sma": sma_n, "confirm": confirm, "band": band}
    return s


def fmt(x: float) -> str:
    return f"{x * 100:+.1f}%"


def row(s: dict) -> str:
    p = s["params"]
    return (f"| SMA{p['sma']} / {p['confirm']}d / {p['band'] * 100:.0f}% "
            f"| {fmt(s['strategy_median'])} | {fmt(s['strategy_mean'])} "
            f"| {s['beat_bh_pct'] * 100:.0f}% | {fmt(s['avg_max_dd'])} "
            f"| {s['trades_per_ticker']:.1f} | {s['avg_exposure'] * 100:.0f}% |")


HEADER = ("| Model (SMA / confirm / band) | Median | Mean | Beat B&H | Avg max DD "
          "| Trades/ticker | Exposure |\n|---|---|---|---|---|---|---|")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strategy parameter sweep")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    symbols = load_universe()["us"]  # research tools stay US-only
    if args.limit:
        symbols = symbols[: args.limit]

    frames = fetch_all(symbols)
    print(f"{len(frames)} tickers loaded; sweeping "
          f"{len(SMA_LENGTHS) * len(CONFIRM_DAYS) * len(BANDS)} combos…", file=sys.stderr)

    rows = []
    for sma_n in SMA_LENGTHS:
        for confirm in CONFIRM_DAYS:
            for band in BANDS:
                s = evaluate(frames, args.years, sma_n, confirm, band)
                if s:
                    rows.append(s)
                print(f"  done SMA{sma_n}/{confirm}d/{band:.2f}", file=sys.stderr)

    rows.sort(key=lambda s: s["strategy_median"], reverse=True)
    bh_med, bh_mean = rows[0]["bh_median"], rows[0]["bh_mean"]
    bh_dd = rows[0]["avg_bh_max_dd"]

    # out-of-sample: the earlier window (e.g. 2016-2021), untouched by selection
    until = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * args.years))
    oos = []
    for s in rows[:TOP_N_VALIDATE] + [next((r for r in rows
                                             if r["params"] == {"sma": 200, "confirm": 2, "band": 0.0}), None)]:
        if s is None:
            continue
        p = s["params"]
        v = evaluate(frames, args.years * 2, p["sma"], p["confirm"], p["band"], until)
        if v:
            oos.append(v)

    lines = [
        f"# Parameter sweep — SMA trend strategy, selected on last {args.years} years",
        "",
        f"{len(frames)} tickers. Buy-and-hold benchmark: median {fmt(bh_med)}, "
        f"mean {fmt(bh_mean)}, avg max drawdown {fmt(bh_dd)}.",
        "",
        f"## In-sample ranking (last {args.years} years) — all {len(rows)} combos",
        "",
        HEADER,
        *[row(s) for s in rows],
        "",
        f"## Out-of-sample check ({2 * args.years}→{args.years} years ago) — "
        f"top {TOP_N_VALIDATE} + original model",
        "",
    ]
    if oos:
        v_bh_med, v_bh_mean, v_bh_dd = oos[0]["bh_median"], oos[0]["bh_mean"], oos[0]["avg_bh_max_dd"]
        lines += [
            f"Buy-and-hold in that window: median {fmt(v_bh_med)}, mean {fmt(v_bh_mean)}, "
            f"avg max drawdown {fmt(v_bh_dd)}.",
            "",
            HEADER,
            *[row(s) for s in oos],
            "",
        ]
    lines += [
        "Selection metric: median per-ticker total return. Same caveats as all "
        "backtests here: survivorship bias, no costs/taxes/dividends.", "",
    ]
    report = "\n".join(lines)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
