"""Registry of active alert rules. Append new rules here (Phase 2+)."""

from .base import Alert, AlertRule
from .sma_cross import GoldenCrossRule, PriceSma200Rule

RULES: list[AlertRule] = [
    PriceSma200Rule(),
    GoldenCrossRule(),
]

__all__ = ["Alert", "AlertRule", "RULES"]
