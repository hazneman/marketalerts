"""Technical indicators. Phase 1: simple moving average only."""

from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, n: int) -> pd.Series:
    """Simple mean of the last n closes; NaN until n bars exist (min_periods=n
    means never a partial SMA). Matches TradingView's SMA with source=close."""
    return close.rolling(window=n, min_periods=n).mean()
