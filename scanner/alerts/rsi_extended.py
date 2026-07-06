"""RSI > 75 in an uptrend — "extended, consider trimming".

Fires when RSI(14) crosses above 75 while the close is above its SMA200.
Backtests (docs/EXITS.md) found selling into RSI>75 strength was the only
exit refinement that beat the plain SMA200 exit in both test windows, so
this is surfaced as a trim/take-profit alert, not an automatic sell.
Event-based: fires on the crossing day only, not every overbought day.
"""

from __future__ import annotations

import pandas as pd

from indicators import rsi, sma
from .base import Alert, AlertRule

THRESHOLD = 75.0


class RsiOverboughtRule(AlertRule):
    category = "rsi_extended"
    min_bars = 201

    def evaluate(self, ticker: str, df: pd.DataFrame) -> list[Alert]:
        if len(df) < self.min_bars:
            return []
        close = df["close"]
        r = rsi(close)
        prev_r, cur_r = float(r.iloc[-2]), float(r.iloc[-1])
        if pd.isna(prev_r) or pd.isna(cur_r):
            return []
        s200 = float(sma(close, 200).iloc[-1])
        c = float(close.iloc[-1])
        if prev_r <= THRESHOLD < cur_r and c > s200:
            return [Alert(
                ticker=ticker, rule="RSI_OVERBOUGHT", category=self.category,
                direction="bearish", date=df.index[-1].date().isoformat(),
                close=round(c, 2),
                values={"rsi": round(cur_r, 1), "sma200": round(s200, 2)},
            )]
        return []
