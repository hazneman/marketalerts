"""Registry of active alert rules. Append new rules here (Phase 2+)."""

from .base import Alert, AlertRule
from .sma_cross import GoldenCrossRule, PriceSma200Rule
from .weekly_sma import Sma200WeeklyRule

RULES: list[AlertRule] = [
    PriceSma200Rule(),
    GoldenCrossRule(),
    Sma200WeeklyRule(),
]

__all__ = ["Alert", "AlertRule", "RULES"]
