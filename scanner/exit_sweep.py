"""Exit-rule study: same entry, six different exits.

Every variant holds long only while price is above the SMA200 regime line
(entry needs 2 consecutive daily closes satisfying the variant's in-state;
orders execute next open). What differs is HOW the position exits:

  sma200 (baseline)  exit on 2 closes below SMA200
  sma90              exit on 2 closes below SMA90 (or SMA200)
  sma50              exit on 2 closes below SMA50 (or SMA200)
  macd               exit when MACD(12,26) < signal(9) for 2 days (or SMA200 break)
  rsi-momentum       exit when RSI(14) < 45 for 2 days (or SMA200 break)
  rsi-takeprofit     exit when RSI(14) > 75 for 2 days (or SMA200 break);
                     re-entry armed once RSI cools below 70

Exits that fire inside an intact SMA200 uptrend re-enter when their own
condition clears (state-based), so each variant is a coherent system, not a
one-way filter. Tested on the last 5 years AND on 2016-2021.

Usage: python scanner/exit_sweep.py [--limit N] [--report docs/EXITS.md]
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
from indicators import macd, rsi, sma
from scan import load_universe
from strategy_backtest import _streak, max_drawdown, summarize

CONFIRM = 2


def variant_signals(df: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(entry_sig, exit_sig) per variant — all streak-confirmed states."""
    c = df["close"]
    cn = c.to_numpy()
    s200 = sma(c, 200).to_numpy()
    above200, below200 = cn > s200, cn < s200
    s90, s50 = sma(c, 90).to_numpy(), sma(c, 50).to_numpy()
    line, sig_line = (x.to_numpy() for x in macd(c))
    r = rsi(c).to_numpy(dtype=float)

    def pair(in_state, out_state):
        return _streak(in_state, CONFIRM), _streak(out_state, CONFIRM)

    return {
        "sma200 (baseline)": pair(above200, below200),
        "sma90": pair(above200 & (cn > s90), (cn < s90) | below200),
        "sma50": pair(above200 & (cn > s50), (cn < s50) | below200),
        "macd": pair(above200 & (line > sig_line), (line < sig_line) | below200),
        "rsi-momentum": pair(above200 & (r > 50), (r < 45) | below200),
        "rsi-takeprofit": pair(above200 & (r <= 70), (r > 75) | below200),
    }


def run_signals(df: pd.DataFrame, entry_sig: np.ndarray, exit_sig: np.ndarray,
                years: int, until: pd.Timestamp | None) -> dict | None:
    """Same window/eligibility/state machine as strategy_backtest.simulate."""
    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * years))
    idx = df.index
    valid = ~np.isnan(sma(df["close"], 200).to_numpy())
    in_range = (idx >= cutoff) if until is None else ((idx >= cutoff) & (idx <= until))
    window = np.where(in_range & valid)[0]
    if len(window) < 250 or idx[window[0]] > cutoff + pd.Timedelta(days=90):
        return None
    start, end = window[0], window[-1]
    opens, closes = df["open"].to_numpy(), df["close"].to_numpy()

    equity = np.empty(end - start + 1)
    in_pos, entry_px, cash, pos_days = False, 0.0, 1.0, 0
    trades: list[float] = []
    for t in range(start, end + 1):
        if t > start:
            if not in_pos and entry_sig[t - 1]:
                in_pos, entry_px = True, opens[t]
            elif in_pos and exit_sig[t - 1]:
                cash *= opens[t] / entry_px
                trades.append(opens[t] / entry_px - 1.0)
                in_pos = False
        if in_pos:
            pos_days += 1
        equity[t - start] = cash * (closes[t] / entry_px) if in_pos else cash
    if in_pos:
        trades.append(closes[end] / entry_px - 1.0)

    bh = closes[start: end + 1] / closes[start]
    return {
        "strategy_return": float(equity[-1] - 1.0), "bh_return": float(bh[-1] - 1.0),
        "trades": trades, "exposure": pos_days / (end - start + 1),
        "max_dd": max_drawdown(equity), "bh_max_dd": max_drawdown(bh),
    }


def fmt(x: float) -> str:
    return f"{x * 100:+.1f}%"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exit-rule sweep")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    symbols = load_universe()["us"]  # research tools stay US-only
    if args.limit:
        symbols = symbols[: args.limit]

    frames: dict[str, pd.DataFrame] = {}
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="max"):
        for sym, df in chunk.items():
            if df.empty:
                continue
            df = df.copy()
            df.index = pd.DatetimeIndex(df.index).tz_localize(None)
            frames[sym] = df
        fetched += len(chunk)
        print(f"  fetched {fetched}/{len(symbols)}", file=sys.stderr)

    signals = {sym: variant_signals(df) for sym, df in frames.items()}
    variants = list(next(iter(signals.values())).keys())
    until = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * args.years))

    lines = [f"# Exit-rule study — fixed SMA200/{CONFIRM}d entry, six exits", "",
             "Every variant is long only while above the SMA200 regime; the exit "
             "rule (and its symmetric re-entry) is the only difference.", ""]
    for title, years, cap in [(f"Last {args.years} years", args.years, None),
                              (f"{2 * args.years}→{args.years} years ago",
                               2 * args.years, until)]:
        rows = []
        for v in variants:
            results = {}
            for sym, df in frames.items():
                e, x = signals[sym][v]
                r = run_signals(df, e, x, years, cap)
                if r is not None:
                    results[sym] = r
            s = summarize(results)
            rows.append((v, s))
            print(f"  {title}: {v} done", file=sys.stderr)
        bh = rows[0][1]
        lines += [
            f"## {title}  ({bh['tickers']} tickers)", "",
            "| Exit rule | Median | Mean | Beat B&H | Avg max DD | Trades/ticker "
            "| Exposure | Win rate | Median trade |",
            "|---|---|---|---|---|---|---|---|---|",
            *[f"| {v} | {fmt(s['strategy_median'])} | {fmt(s['strategy_mean'])} "
              f"| {s['beat_bh_pct'] * 100:.0f}% | {fmt(s['avg_max_dd'])} "
              f"| {s['trades_per_ticker']:.1f} | {s['avg_exposure'] * 100:.0f}% "
              f"| {s['trade_win_rate'] * 100:.0f}% | {fmt(s['median_trade'])} |"
              for v, s in rows],
            f"| buy & hold | {fmt(bh['bh_median'])} | {fmt(bh['bh_mean'])} | — "
            f"| {fmt(bh['avg_bh_max_dd'])} | — | 100% | — | — |",
            "",
        ]
    report = "\n".join(lines)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
