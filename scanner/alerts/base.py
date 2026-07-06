"""Alert plumbing: the Alert record, the rule interface, and cross helpers.

To add a new alert type: subclass AlertRule in a new module and append an
instance to RULES in alerts/__init__.py. scan.py and the dashboard pick it up
automatically.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Alert:
    ticker: str
    rule: str        # e.g. "PRICE_SMA200_BULL"
    category: str    # e.g. "price_sma200" — dashboard groups by this
    direction: str   # "bullish" | "bearish"
    date: str        # bar date, YYYY-MM-DD
    close: float
    values: dict = field(default_factory=dict)  # rule-specific, e.g. {"sma200": ...}

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "rule": self.rule, "category": self.category,
            "direction": self.direction, "date": self.date, "close": self.close,
            "values": self.values,
        }


class AlertRule(ABC):
    """One detector. evaluate() inspects only the last two bars and returns
    [] when there is no signal or inputs are NaN/insufficient."""

    category: str
    min_bars: int

    @abstractmethod
    def evaluate(self, ticker: str, df: pd.DataFrame) -> list[Alert]:
        ...


def px_round(v: float) -> float:
    """Price rounding: 2dp for stock-scale prices, 4dp for FX-scale (<10)."""
    return round(v, 2 if abs(v) >= 10 else 4)


def crossed_up(prev_a: float, a: float, prev_b: float, b: float) -> bool:
    """a crossed above b between the previous and current bar.

    Convention (matches the ichimoku signal engine): touching then breaking
    counts — prev on-or-below, now strictly above.
    """
    if any(math.isnan(x) for x in (prev_a, a, prev_b, b)):
        return False
    return prev_a <= prev_b and a > b


def crossed_down(prev_a: float, a: float, prev_b: float, b: float) -> bool:
    if any(math.isnan(x) for x in (prev_a, a, prev_b, b)):
        return False
    return prev_a >= prev_b and a < b
