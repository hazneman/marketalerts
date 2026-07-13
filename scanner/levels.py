"""Price-structure context per ticker: daily + weekly Fibonacci retracements.

Deterministic recent-swing anchor: the swing high/low is the highest high /
lowest low over a fixed window (daily = 252 trading days ≈ 1 year, weekly = 52
completed weeks), so the levels are reproducible — the trade-off for Fibonacci's
usual subjectivity is one fixed window choice per timeframe.
"""

from __future__ import annotations

import pandas as pd

from indicators import fib_retracement

DAILY_WINDOW = 252   # ~1 year of trading days
WEEKLY_WINDOW = 52   # ~1 year of completed weeks


def _daily_fib(df: pd.DataFrame) -> dict | None:
    if len(df) < DAILY_WINDOW:
        return None
    window = df.tail(DAILY_WINDOW)
    return fib_retracement(float(window["high"].max()), float(window["low"].min()),
                           float(df["close"].iloc[-1]))


def _weekly_fib(df: pd.DataFrame) -> dict | None:
    # Weekly bars from daily OHLCV; completed weeks only (drop the running week),
    # matching the weekly-SMA rule's convention.
    highs = df["high"].resample("W-FRI").max()
    lows = df["low"].resample("W-FRI").min()
    highs = highs[highs.index <= df.index[-1]].dropna()
    lows = lows[lows.index <= df.index[-1]].dropna()
    if len(highs) < WEEKLY_WINDOW or len(lows) < WEEKLY_WINDOW:
        return None
    return fib_retracement(float(highs.tail(WEEKLY_WINDOW).max()),
                           float(lows.tail(WEEKLY_WINDOW).min()),
                           float(df["close"].iloc[-1]))


def fib_block(df: pd.DataFrame) -> dict:
    """{"daily": {...}|None, "weekly": {...}|None} for a ticker's OHLCV frame."""
    return {"daily": _daily_fib(df), "weekly": _weekly_fib(df)}
