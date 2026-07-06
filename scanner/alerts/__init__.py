"""Registry of active alert rules. Append new rules here (Phase 2+)."""

from .base import Alert, AlertRule
from .rsi_extended import RsiOverboughtRule
from .sma_cross import GoldenCrossRule, PriceSma200Rule
from .weekly_sma import Sma200WeeklyRule

RULES: list[AlertRule] = [
    PriceSma200Rule(),
    GoldenCrossRule(),
    Sma200WeeklyRule(),
    RsiOverboughtRule(),
]

__all__ = ["Alert", "AlertRule", "RULES"]
