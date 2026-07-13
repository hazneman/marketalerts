"""Technical indicators: SMA, RSI, MACD, plus price-structure helpers
(Fibonacci retracement, volume-vs-average)."""

from __future__ import annotations

import pandas as pd

RSI_PERIOD = 14

# Standard Fibonacci retracement ratios (fraction retraced from the swing high).
FIB_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]


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


def _pct(price: float, level: float) -> float:
    """Signed distance of price from a level, in % of price.
    + = price above the level (support below); − = price below (resistance above)."""
    return round((price / level - 1.0) * 100, 2)


def fib_retracement(high: float, low: float, price: float) -> dict | None:
    """Fibonacci retracement levels between swing low/high and price's distance
    to each. Pure/testable. Returns None if the swing is degenerate (H<=L).

    Levels descend from the high: level_r = H − r·(H−L) for r in FIB_RATIOS.
    Each level carries a signed `dist_pct` (see _pct). `nearest` is the level
    with the smallest absolute distance; `position_pct` is where price sits in
    the [low, high] range (0 = at low, 100 = at high; can exceed on a breakout).
    """
    rng = high - low
    if rng <= 0:
        return None
    levels = []
    for r in FIB_RATIOS:
        lvl = high - r * rng
        levels.append({"label": f"{r * 100:.1f}%", "price": round(lvl, 4),
                       "dist_pct": _pct(price, lvl)})
    nearest = min(levels, key=lambda x: abs(x["dist_pct"]))
    return {
        "high": round(high, 4), "low": round(low, 4),
        "position_pct": round((price - low) / rng * 100, 1),
        "levels": levels,
        "nearest": nearest,
    }


def volume_signal(volume: pd.Series, n: int = 20) -> dict | None:
    """Latest volume vs its n-day average. None if fewer than n bars.

    ratio > 1 means today traded above its recent average — a breakout on
    above-average volume is more trustworthy than one on thin volume.
    """
    vol = volume.dropna()
    if len(vol) < n:
        return None
    today = float(vol.iloc[-1])
    avg = float(vol.tail(n).mean())
    if avg <= 0:
        return None
    ratio = round(today / avg, 2)
    return {"today": round(today), "avg20": round(avg),
            "ratio": ratio, "above_avg": ratio >= 1.0}
