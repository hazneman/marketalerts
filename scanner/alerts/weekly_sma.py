"""200-week SMA cross — the secular trend line.

Weekly closes are derived from the daily data (W-FRI resample, Friday close =
weekly close, matching Yahoo/TradingView weekly bars). Only COMPLETED weeks
are evaluated: mid-week the current bucket is dropped, so a cross fires once,
on the Friday scan, and can never flicker as the week develops.

These crosses are rare (~once per 18 months per stock) and mark genuine
regime changes; backtests showed them to be the highest-quality cross signal
tested (docs/WEEKLY.md).
"""

from __future__ import annotations

import pandas as pd

from indicators import sma
from .base import Alert, AlertRule, crossed_down, crossed_up

WEEKS = 200


class Sma200WeeklyRule(AlertRule):
    category = "price_sma200_weekly"
    min_bars = 201  # daily-bar gate in scan.py; weekly sufficiency checked below

    def evaluate(self, ticker: str, df: pd.DataFrame) -> list[Alert]:
        weekly = df["close"].resample("W-FRI").last().dropna()
        weekly = weekly[weekly.index <= df.index[-1]]  # completed weeks only
        if len(weekly) < WEEKS + 1:
            return []
        s = sma(weekly, WEEKS)
        prev_c, c = float(weekly.iloc[-2]), float(weekly.iloc[-1])
        prev_s, sm = float(s.iloc[-2]), float(s.iloc[-1])

        common = dict(ticker=ticker, category=self.category,
                      date=weekly.index[-1].date().isoformat(),
                      close=round(c, 2), values={"sma200": round(sm, 2)})
        if crossed_up(prev_c, c, prev_s, sm):
            return [Alert(rule="PRICE_SMA200W_BULL", direction="bullish", **common)]
        if crossed_down(prev_c, c, prev_s, sm):
            return [Alert(rule="PRICE_SMA200W_BEAR", direction="bearish", **common)]
        return []
