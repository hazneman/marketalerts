"""Technical indicators: SMA and RSI."""

from __future__ import annotations

import pandas as pd

RSI_PERIOD = 14


def sma(close: pd.Series, n: int) -> pd.Series:
    """Simple mean of the last n closes; NaN until n bars exist (min_periods=n
    means never a partial SMA). Matches TradingView's SMA with source=close."""
    return close.rolling(window=n, min_periods=n).mean()


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing (matches TradingView).

    First `period` rows are NaN (insufficient lookback). A run with no losses
    yields 100, no gains yields 0.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's smoothing == EMA with alpha = 1/period, no adjustment.
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 -> no downside -> fully overbought (avoids inf/NaN artifacts).
    out = out.where(avg_loss != 0, 100.0)
    # Mask the warm-up window so we never emit a value before `period` bars.
    out[avg_gain.isna()] = pd.NA
    return out
