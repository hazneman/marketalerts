"""Phase 1 rules: price × SMA200 crosses and SMA50 × SMA200 (golden/death)."""

from __future__ import annotations

import pandas as pd

from indicators import sma
from .base import Alert, AlertRule, crossed_down, crossed_up, px_round


def _bar_date(df: pd.DataFrame) -> str:
    return df.index[-1].date().isoformat()


class PriceSma200Rule(AlertRule):
    category = "price_sma200"
    min_bars = 201

    def evaluate(self, ticker: str, df: pd.DataFrame) -> list[Alert]:
        if len(df) < self.min_bars:
            return []
        close = df["close"]
        sma200 = sma(close, 200)
        prev_c, c = float(close.iloc[-2]), float(close.iloc[-1])
        prev_s, s = float(sma200.iloc[-2]), float(sma200.iloc[-1])

        common = dict(ticker=ticker, category=self.category, date=_bar_date(df),
                      close=px_round(c), values={"sma200": px_round(s)})
        if crossed_up(prev_c, c, prev_s, s):
            return [Alert(rule="PRICE_SMA200_BULL", direction="bullish", **common)]
        if crossed_down(prev_c, c, prev_s, s):
            return [Alert(rule="PRICE_SMA200_BEAR", direction="bearish", **common)]
        return []


class GoldenCrossRule(AlertRule):
    category = "sma50_sma200"
    min_bars = 201

    def evaluate(self, ticker: str, df: pd.DataFrame) -> list[Alert]:
        if len(df) < self.min_bars:
            return []
        close = df["close"]
        sma50, sma200 = sma(close, 50), sma(close, 200)
        prev_f, f = float(sma50.iloc[-2]), float(sma50.iloc[-1])
        prev_s, s = float(sma200.iloc[-2]), float(sma200.iloc[-1])

        common = dict(ticker=ticker, category=self.category, date=_bar_date(df),
                      close=px_round(float(close.iloc[-1])),
                      values={"sma50": px_round(f), "sma200": px_round(s)})
        if crossed_up(prev_f, f, prev_s, s):
            return [Alert(rule="GOLDEN_CROSS", direction="bullish", **common)]
        if crossed_down(prev_f, f, prev_s, s):
            return [Alert(rule="DEATH_CROSS", direction="bearish", **common)]
        return []
