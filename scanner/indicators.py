"""Technical indicators: SMA, RSI, MACD."""

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


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[pd.Series, pd.Series]:
    """MACD line (EMA12 − EMA26) and its signal line (EMA9 of the MACD line).

    Standard parameters, adjust=False EMAs — matches TradingView's MACD.
    Returns (macd_line, signal_line).
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    return line, line.ewm(span=signal, adjust=False).mean()
