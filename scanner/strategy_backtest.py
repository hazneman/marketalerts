"""Backtest a full in/out trading strategy on every universe ticker.

Rules (Hasan's SMA200 trend filter):
  BUY  when the close has been above the 200-day SMA for N consecutive days
  SELL when the close has been below the 200-day SMA for N consecutive days
  (N = --confirm, default 2). Orders execute at the NEXT day's open — you
  can't trade a close you haven't seen yet. Cash earns nothing while out.

Compared against buy-and-hold of the same ticker over the same window.
Dividends are ignored on both sides (raw Close); since buy-and-hold is always
invested, this understates buy-and-hold slightly more than the strategy.

Usage:
  python scanner/strategy_backtest.py                # full universe, 5 years
  python scanner/strategy_backtest.py --confirm 2 --sma 200 --years 5
  python scanner/strategy_backtest.py --limit 20     # quick sample
  python scanner/strategy_backtest.py --report docs/STRATEGY.md --curves PATH.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import iter_us_chunks
from indicators import sma
from scan import load_universe


def max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0))


def simulate(df: pd.DataFrame, years: int, sma_n: int, confirm: int) -> dict | None:
    """Run the strategy on one ticker. Returns stats or None if not enough data."""
    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * years))
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    s = sma(df["close"], sma_n)
    above = (df["close"] > s).to_numpy()
    below = (df["close"] < s).to_numpy()
    valid = ~np.isnan(s.to_numpy())

    idx = df.index
    window = np.where((idx >= cutoff) & valid)[0]
    if len(window) < 250 or idx[window[0]] > cutoff + pd.Timedelta(days=90):
        return None  # joined too late for a fair 5y comparison

    start, end = window[0], window[-1]
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()

    def confirmed(mask: np.ndarray, t: int) -> bool:
        return t - confirm + 1 >= 0 and mask[t - confirm + 1: t + 1].all()

    equity = np.empty(end - start + 1)
    in_pos = False
    entry_px = 0.0
    cash = 1.0
    trades: list[float] = []
    pos_days = 0

    for t in range(start, end + 1):
        # execute yesterday's confirmed signal at today's open
        if t > start:
            if not in_pos and confirmed(above, t - 1):
                in_pos, entry_px = True, opens[t]
            elif in_pos and confirmed(below, t - 1):
                cash *= opens[t] / entry_px
                trades.append(opens[t] / entry_px - 1.0)
                in_pos = False
        if in_pos:
            pos_days += 1
        equity[t - start] = cash * (closes[t] / entry_px) if in_pos else cash

    if in_pos:  # mark open position to market at the end
        trades.append(closes[end] / entry_px - 1.0)

    bh = closes[start: end + 1] / closes[start]
    return {
        "dates": idx[start: end + 1],
        "equity": equity,
        "bh": bh,
        "strategy_return": float(equity[-1] - 1.0),
        "bh_return": float(bh[-1] - 1.0),
        "trades": trades,
        "exposure": pos_days / (end - start + 1),
        "max_dd": max_drawdown(equity),
        "bh_max_dd": max_drawdown(bh),
    }


def run(symbols: list[str], years: int, sma_n: int, confirm: int):
    results: dict[str, dict] = {}
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="10y"):
        for sym, df in chunk.items():
            fetched += 1
            if df.empty:
                continue
            r = simulate(df, years, sma_n, confirm)
            if r is not None:
                results[sym] = r
        print(f"  simulated {fetched}/{len(symbols)}", file=sys.stderr)
    return results


def summarize(results: dict[str, dict]) -> dict:
    strat = np.array([r["strategy_return"] for r in results.values()])
    bh = np.array([r["bh_return"] for r in results.values()])
    all_trades = np.concatenate([r["trades"] for r in results.values() if r["trades"]])
    dd = np.array([r["max_dd"] for r in results.values()])
    bh_dd = np.array([r["bh_max_dd"] for r in results.values()])
    return {
        "tickers": len(results),
        "strategy_mean": float(strat.mean()), "strategy_median": float(np.median(strat)),
        "bh_mean": float(bh.mean()), "bh_median": float(np.median(bh)),
        "beat_bh_pct": float(np.mean(strat > bh)),
        "trades_total": int(len(all_trades)),
        "trades_per_ticker": float(len(all_trades) / len(results)),
        "trade_win_rate": float(np.mean(all_trades > 0)),
        "avg_trade": float(all_trades.mean()), "median_trade": float(np.median(all_trades)),
        "avg_max_dd": float(dd.mean()), "avg_bh_max_dd": float(bh_dd.mean()),
        "avg_exposure": float(np.mean([r["exposure"] for r in results.values()])),
    }


def portfolio_curves(results: dict[str, dict]) -> dict:
    """Equal-weight average equity across tickers, weekly samples."""
    eq = pd.DataFrame({sym: pd.Series(r["equity"], index=r["dates"])
                       for sym, r in results.items()})
    bh = pd.DataFrame({sym: pd.Series(r["bh"], index=r["dates"])
                       for sym, r in results.items()})
    # only average dates where most tickers have data (avoids join artifacts)
    good = eq.notna().sum(axis=1) >= 0.9 * len(eq.columns)
    strat_curve = eq[good].mean(axis=1).resample("W").last().dropna()
    bh_curve = bh[good].mean(axis=1).resample("W").last().dropna()
    return {
        "dates": [d.date().isoformat() for d in strat_curve.index],
        "strategy": [round(float(v), 4) for v in strat_curve],
        "buy_hold": [round(float(v), 4) for v in bh_curve],
    }


def fmt(x: float) -> str:
    return f"{x * 100:+.1f}%"


def print_report(s: dict, years: int, sma_n: int, confirm: int) -> str:
    lines = [
        f"# Strategy backtest — SMA{sma_n} trend filter, {confirm}-day confirmation, last {years} years",
        "",
        f"Buy after {confirm} consecutive closes above the SMA{sma_n}, sell after "
        f"{confirm} consecutive closes below; execution at next day's open. "
        f"Per-ticker, all-in/all-out, vs buy-and-hold of the same ticker. "
        f"{s['tickers']} tickers (today's index members — survivorship bias applies to both sides).",
        "",
        "| Metric | Strategy | Buy & hold |",
        "|---|---|---|",
        f"| Mean total return | {fmt(s['strategy_mean'])} | {fmt(s['bh_mean'])} |",
        f"| Median total return | {fmt(s['strategy_median'])} | {fmt(s['bh_median'])} |",
        f"| Average max drawdown | {fmt(s['avg_max_dd'])} | {fmt(s['avg_bh_max_dd'])} |",
        "",
        f"- Strategy beat buy-and-hold on **{s['beat_bh_pct'] * 100:.0f}%** of tickers",
        f"- {s['trades_total']} round trips (~{s['trades_per_ticker']:.1f} per ticker, "
        f"~{s['trades_per_ticker'] / years:.1f}/yr)",
        f"- Trade win rate {s['trade_win_rate'] * 100:.0f}%, average trade {fmt(s['avg_trade'])}, "
        f"median trade {fmt(s['median_trade'])}",
        f"- Average time in market: {s['avg_exposure'] * 100:.0f}% of days",
        "",
    ]
    report = "\n".join(lines)
    print(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strategy backtest")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--sma", type=int, default=200)
    parser.add_argument("--confirm", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--curves", type=Path, help="write weekly portfolio curves JSON")
    args = parser.parse_args(argv)

    symbols = load_universe()
    if args.limit:
        symbols = symbols[: args.limit]

    results = run(symbols, args.years, args.sma, args.confirm)
    summary = summarize(results)
    report = print_report(summary, args.years, args.sma, args.confirm)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    if args.curves:
        args.curves.write_text(json.dumps(portfolio_curves(results)))
    print(json.dumps(summary, indent=1), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
