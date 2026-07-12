"""Which kinds of stocks does the trend strategy actually work on?

Computes per-ticker price characteristics and relates them to the strategy's
edge (strategy return minus buy-and-hold) under the baseline model
(SMA200, 2-day confirm). Two views:

1. HINDSIGHT: traits and edge measured in the SAME window (last 5y).
   Explains where the model won, but can't be traded.
2. PREDICTIVE: traits measured 10->5 years ago, edge measured in the last
   5 years. If a trait ranks stocks here, it was detectable IN ADVANCE.

Traits (all from price data only):
  ann_vol    annualized daily volatility
  total_ret  total return over the trait window
  max_dd     deepest drawdown of the stock itself
  chop       SMA200 crossings per year (whipsaw frequency)

Usage:
  python scanner/profile.py [--limit N] [--report docs/PROFILE.md]
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
from strategy_backtest import max_drawdown, simulate

TRAITS = ["ann_vol", "total_ret", "max_dd", "chop"]
TRAIT_LABELS = {
    "ann_vol": "Volatility (annualized)",
    "total_ret": "Past total return",
    "max_dd": "Past worst drawdown",
    "chop": "SMA200 crossings / year",
}


def traits_for(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict | None:
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    s = sma(df["close"], 200)
    w = df[(df.index >= start) & (df.index <= end)]
    sw = s[(s.index >= start) & (s.index <= end)]
    if len(w) < 500 or sw.isna().all():
        return None
    close = w["close"]
    rets = close.pct_change().dropna()
    diff = np.sign((close - sw).dropna())
    crossings = int((diff.diff().abs() > 0).sum())
    years = (w.index[-1] - w.index[0]).days / 365.25
    return {
        "ann_vol": float(rets.std() * np.sqrt(252)),
        "total_ret": float(close.iloc[-1] / close.iloc[0] - 1),
        "max_dd": max_drawdown((close / close.iloc[0]).to_numpy()),
        "chop": crossings / years,
    }


def quintile_table(data: pd.DataFrame, trait: str) -> list[str]:
    d = data.dropna(subset=[trait, "edge"]).copy()
    d["q"] = pd.qcut(d[trait], 5, labels=False, duplicates="drop")
    rank_corr = d[trait].rank().corr(d["edge"].rank())  # Spearman without scipy
    lines = [f"**{TRAIT_LABELS[trait]}** — rank correlation with edge: {rank_corr:+.2f}",
             "",
             "| Quintile | Trait range | Mean edge vs B&H | Beat B&H |",
             "|---|---|---|---|"]
    for q in sorted(d["q"].unique()):
        sub = d[d["q"] == q]
        lines.append(
            f"| {'lowest' if q == 0 else 'highest' if q == d['q'].max() else f'Q{int(q) + 1}'} "
            f"| {sub[trait].min():.2f} … {sub[trait].max():.2f} "
            f"| {sub['edge'].mean() * 100:+.1f}% | {(sub['edge'] > 0).mean() * 100:.0f}% |")
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stock trait vs strategy edge profile")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    symbols = load_universe()["us"]  # research tools stay US-only
    if args.limit:
        symbols = symbols[: args.limit]

    today = pd.Timestamp(dt.date.today())
    five_ago = today - pd.Timedelta(days=365 * 5)
    ten_ago = today - pd.Timedelta(days=365 * 10)

    rows = []
    fetched = 0
    for chunk in iter_us_chunks(symbols, period="max"):
        for sym, df in chunk.items():
            fetched += 1
            if df.empty:
                continue
            r = simulate(df, 5, 200, 2)  # baseline model, last 5y
            if r is None:
                continue
            recent = traits_for(df, five_ago, today)
            past = traits_for(df, ten_ago, five_ago)
            if recent is None:
                continue
            row = {"ticker": sym, "edge": r["strategy_return"] - r["bh_return"]}
            row.update({f"now_{k}": v for k, v in recent.items()})
            if past is not None:
                row.update({f"past_{k}": v for k, v in past.items()})
            rows.append(row)
        print(f"  processed {fetched}/{len(symbols)}", file=sys.stderr)

    data = pd.DataFrame(rows)
    n_past = data[[f"past_{t}" for t in TRAITS]].dropna().shape[0]

    lines = [
        "# Stock traits vs strategy edge (baseline SMA200/2d model)",
        "",
        f"{len(data)} tickers. Edge = strategy return − buy-and-hold return, last 5 years. "
        f"Positive edge = the model beat holding that stock.",
        "",
        "## 1. Hindsight view — traits measured in the SAME window as the edge",
        "",
    ]
    hind = data.rename(columns={f"now_{t}": t for t in TRAITS})
    for t in TRAITS:
        lines += quintile_table(hind, t)
    lines += [
        f"## 2. Predictive view — traits from 2016-2021, edge from 2021-2026 ({n_past} tickers)",
        "",
    ]
    pred = data.rename(columns={f"past_{t}": t for t in TRAITS})
    for t in TRAITS:
        lines += quintile_table(pred, t)
    lines += ["Hindsight correlations explain; only predictive correlations are tradeable.", ""]

    report = "\n".join(lines)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
