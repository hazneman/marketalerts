"""Backtest a full in/out trading strategy on every universe ticker.

Rules (Hasan's SMA200 trend filter):
  BUY  when the close has been above the 200-day SMA for N consecutive days
  SELL when the close has been below the 200-day SMA for N consecutive days
  (N = --confirm, default 2). Orders execute at the NEXT day's open — you
  can't trade a close you haven't seen yet. Cash earns nothing while out.

Optional entry filter: --rsi-max X blocks BUYs while RSI(14) > X on the
confirmation day (entry is delayed, not cancelled — it happens on the first
later day when the trend condition still holds and RSI has cooled off).
Exits are never blocked.

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
from indicators import rsi, sma
from scan import load_universe


def max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0))


def _streak(mask: np.ndarray, n: int) -> np.ndarray:
    """True at t when mask has been True for the n days ending at t."""
    return pd.Series(mask).rolling(n).sum().eq(n).to_numpy()


def simulate(df: pd.DataFrame, years: int, sma_n: int, confirm: int,
             rsi_max: float | None = None, band: float = 0.0,
             until: pd.Timestamp | None = None,
             mode: str = "trend", fast_n: int = 30,
             min_window: int = 250) -> dict | None:
    """Run one strategy on one ticker. Returns stats or None if not enough data.

    mode="trend": buy/sell after `confirm` consecutive closes beyond the
    SMA(sma_n) with optional hysteresis `band`.
    mode="pullback": regime + trigger — buy when close is above SMA(sma_n)
    AND crosses above SMA(fast_n); sell when close crosses below SMA(fast_n)
    or falls below SMA(sma_n). (`confirm`/`band` are unused here.)
    mode="hybrid": same entry as pullback, but sell ONLY on regime break
    (close below SMA(sma_n)) — enter on dips, let winners run.
    `until` caps the window end (for out-of-sample validation on old data).
    """
    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * years))
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    s = sma(df["close"], sma_n)
    closes_s = df["close"]
    above = (closes_s > s * (1.0 + band)).to_numpy()
    below = (closes_s < s * (1.0 - band)).to_numpy()
    valid = ~np.isnan(s.to_numpy())
    if rsi_max is not None:
        r = rsi(closes_s).to_numpy(dtype=float)
        rsi_ok = ~np.isnan(r) & (r <= rsi_max)
    else:
        rsi_ok = np.ones(len(df), dtype=bool)

    if mode in ("pullback", "hybrid"):
        f = sma(closes_s, fast_n).to_numpy()
        c = closes_s.to_numpy()
        above_fast = ~np.isnan(f) & (c > f)
        cross_up = np.zeros(len(df), dtype=bool)
        cross_up[1:] = above_fast[1:] & ~above_fast[:-1] & ~np.isnan(f[:-1])
        cross_dn = np.zeros(len(df), dtype=bool)
        cross_dn[1:] = ~above_fast[1:] & above_fast[:-1] & ~np.isnan(f[1:])
        entry_sig = cross_up & (c > s.to_numpy()) & rsi_ok
        exit_sig = (c < s.to_numpy()) if mode == "hybrid" \
            else cross_dn | (c < s.to_numpy())
    else:
        entry_sig = _streak(above, confirm) & rsi_ok
        exit_sig = _streak(below, confirm)

    idx = df.index
    in_range = (idx >= cutoff) if until is None else ((idx >= cutoff) & (idx <= until))
    window = np.where(in_range & valid)[0]
    if len(window) < min_window or idx[window[0]] > cutoff + pd.Timedelta(days=90):
        return None  # joined too late for a fair comparison

    start, end = window[0], window[-1]
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()

    equity = np.empty(end - start + 1)
    in_pos = False
    entry_px = 0.0
    cash = 1.0
    trades: list[float] = []
    pos_days = 0

    for t in range(start, end + 1):
        # execute yesterday's signal at today's open
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


def run(symbols: list[str], years: int, sma_n: int, confirm: int,
        rsi_max: float | None = None, band: float = 0.0,
        mode: str = "trend", fast_n: int = 30, interval: str = "1d"):
    weekly = interval == "1wk"
    results: dict[str, dict] = {}
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="max" if weekly else "10y",
                                interval=interval):
        for sym, df in chunk.items():
            fetched += 1
            if df.empty:
                continue
            r = simulate(df, years, sma_n, confirm, rsi_max, band, None, mode,
                         fast_n, 200 if weekly else 250)
            if r is not None:
                results[sym] = r
        print(f"  simulated {fetched}/{len(symbols)}", file=sys.stderr)
    return results


def validate(symbols: list[str], args) -> int:
    """One fetch, four evaluations: {model, trend baseline} x {recent, earlier}."""
    weekly = args.interval == "1wk"
    min_window = 200 if weekly else 250
    frames: dict[str, pd.DataFrame] = {}
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="max", interval=args.interval):
        frames.update({s: d for s, d in chunk.items() if not d.empty})
        fetched += len(chunk)
        print(f"  fetched {fetched}/{len(symbols)}", file=sys.stderr)
    until = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * args.years))

    def ev(mode: str, years: int, cap: pd.Timestamp | None,
           sma_n: int | None = None, confirm: int | None = None) -> dict:
        results = {}
        for sym, df in frames.items():
            r = simulate(df, years, sma_n or args.sma, confirm or args.confirm,
                         args.rsi_max, args.band, cap, mode, args.fast, min_window)
            if r is not None:
                results[sym] = r
        return summarize(results)

    def fmt(x: float) -> str:
        return f"{x * 100:+.1f}%"

    unit = "w" if weekly else "d"
    bars = "weekly" if weekly else "daily"
    model_name = {
        "pullback": f"pullback (>SMA{args.sma} + SMA{args.fast} cross, {bars})",
        "hybrid": f"hybrid (SMA{args.fast}-cross entry, SMA{args.sma}-break exit, {bars})",
        "trend": f"trend SMA{args.sma}/{args.confirm}{unit} ({bars})",
    }[args.model]
    base_name = f"trend SMA200/2{unit} ({bars} baseline)"
    lines = [f"# Model validation — {model_name} vs {base_name}, two windows", ""]
    for title, years, cap in [(f"Last {args.years} years", args.years, None),
                              (f"{2 * args.years}→{args.years} years ago", 2 * args.years, until)]:
        m = ev(args.model, years, cap)
        b = ev("trend", years, cap, sma_n=200, confirm=2)
        print(f"  window '{title}' done", file=sys.stderr)
        lines += [
            f"## {title}  ({m['tickers']} tickers)", "",
            "| Model | Median | Mean | Beat B&H | Avg max DD | Trades/ticker | Exposure |",
            "|---|---|---|---|---|---|---|",
            f"| {model_name} | {fmt(m['strategy_median'])} | {fmt(m['strategy_mean'])} "
            f"| {m['beat_bh_pct'] * 100:.0f}% | {fmt(m['avg_max_dd'])} "
            f"| {m['trades_per_ticker']:.1f} | {m['avg_exposure'] * 100:.0f}% |",
            f"| {base_name} | {fmt(b['strategy_median'])} "
            f"| {fmt(b['strategy_mean'])} | {b['beat_bh_pct'] * 100:.0f}% | {fmt(b['avg_max_dd'])} "
            f"| {b['trades_per_ticker']:.1f} | {b['avg_exposure'] * 100:.0f}% |",
            f"| buy & hold | {fmt(m['bh_median'])} | {fmt(m['bh_mean'])} | — "
            f"| {fmt(m['avg_bh_max_dd'])} | — | 100% |",
            "",
            f"Model trades: win rate {m['trade_win_rate'] * 100:.0f}%, "
            f"avg {fmt(m['avg_trade'])}, median {fmt(m['median_trade'])}.",
            "",
        ]
    report = "\n".join(lines)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return 0


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


def print_report(s: dict, years: int, sma_n: int, confirm: int,
                 rsi_max: float | None = None) -> str:
    rsi_note = f", RSI≤{rsi_max:g} entry filter" if rsi_max is not None else ""
    rsi_rule = (f"Entries are skipped while RSI(14) > {rsi_max:g}. "
                if rsi_max is not None else "")
    lines = [
        f"# Strategy backtest — SMA{sma_n} trend filter, {confirm}-day confirmation{rsi_note}, last {years} years",
        "",
        f"Buy after {confirm} consecutive closes above the SMA{sma_n}, sell after "
        f"{confirm} consecutive closes below; execution at next day's open. {rsi_rule}"
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
    parser.add_argument("--rsi-max", type=float, default=None,
                        help="skip entries while RSI(14) is above this value")
    parser.add_argument("--band", type=float, default=0.0,
                        help="hysteresis buffer, e.g. 0.02 = trade only 2%% beyond the SMA")
    parser.add_argument("--model", choices=["trend", "pullback", "hybrid"], default="trend",
                        help="trend = SMA cross hold; pullback = SMA30-cross entry+exit in "
                             "SMA200 regime; hybrid = pullback entry, regime-break exit only")
    parser.add_argument("--fast", type=int, default=30,
                        help="fast SMA length for pullback mode")
    parser.add_argument("--interval", choices=["1d", "1wk"], default="1d",
                        help="bar size; 1wk makes confirm/SMA lengths weekly")
    parser.add_argument("--validate", action="store_true",
                        help="compare model vs trend baseline on recent AND earlier window")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--curves", type=Path, help="write weekly portfolio curves JSON")
    args = parser.parse_args(argv)

    symbols = load_universe()
    if args.limit:
        symbols = symbols[: args.limit]

    if args.validate:
        return validate(symbols, args)

    results = run(symbols, args.years, args.sma, args.confirm, args.rsi_max, args.band,
                  args.model, args.fast, args.interval)
    summary = summarize(results)
    report = print_report(summary, args.years, args.sma, args.confirm, args.rsi_max)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    if args.curves:
        args.curves.write_text(json.dumps(portfolio_curves(results)))
    print(json.dumps(summary, indent=1), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
