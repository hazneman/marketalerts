import numpy as np
import pandas as pd

from alerts import RULES
from alerts.sma_cross import GoldenCrossRule, PriceSma200Rule


def make_df(closes):
    closes = list(closes)
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": 1000}, index=idx)


def flat_then(last_two, n=250, level=100.0):
    return make_df([level] * (n - 2) + list(last_two))


class TestPriceSma200:
    rule = PriceSma200Rule()

    def test_bull_cross_fires(self):
        # SMA200 sits near 100; close goes from below to above it
        df = flat_then([99.0, 105.0])
        alerts = self.rule.evaluate("TEST", df)
        assert len(alerts) == 1
        a = alerts[0]
        assert a.rule == "PRICE_SMA200_BULL"
        assert a.direction == "bullish"
        assert a.close == 105.0
        assert a.date == df.index[-1].date().isoformat()
        assert abs(a.values["sma200"] - 100.0) < 0.1

    def test_bear_cross_fires(self):
        alerts = self.rule.evaluate("TEST", flat_then([101.0, 95.0]))
        assert [a.rule for a in alerts] == ["PRICE_SMA200_BEAR"]

    def test_touch_then_break_counts(self):
        # prev close exactly ON the SMA, then above -> fires (<= -> > convention)
        alerts = self.rule.evaluate("TEST", flat_then([100.0, 105.0]))
        assert [a.rule for a in alerts] == ["PRICE_SMA200_BULL"]

    def test_already_above_is_silent(self):
        assert self.rule.evaluate("TEST", flat_then([110.0, 111.0])) == []

    def test_flat_is_silent(self):
        assert self.rule.evaluate("TEST", flat_then([100.0, 100.0])) == []

    def test_needs_201_bars(self):
        # 200 bars: today's SMA200 exists but yesterday's doesn't
        assert self.rule.evaluate("TEST", flat_then([99.0, 105.0], n=200)) == []


class TestGoldenCross:
    rule = GoldenCrossRule()

    @staticmethod
    def ramp(first, second):
        # 200 bars at 100, 30 at `first`, 25 at `second`: engineered so
        # SMA50 crosses SMA200 exactly on the final bar (see derivation:
        # sma50 = second + 0.8j vs sma200 ~ 97 + 0.1j crosses at j~24.3)
        return make_df([100.0] * 200 + [first] * 30 + [second] * 25)

    def test_golden_cross_fires_on_last_bar_only(self):
        df = self.ramp(80.0, 120.0)
        alerts = self.rule.evaluate("TEST", df)
        assert [a.rule for a in alerts] == ["GOLDEN_CROSS"]
        a = alerts[0]
        assert a.direction == "bullish"
        assert a.values["sma50"] > a.values["sma200"]
        # one bar earlier there was no cross yet
        assert self.rule.evaluate("TEST", df.iloc[:-1]) == []

    def test_death_cross_fires(self):
        alerts = self.rule.evaluate("TEST", self.ramp(120.0, 80.0))
        assert [a.rule for a in alerts] == ["DEATH_CROSS"]
        assert alerts[0].direction == "bearish"

    def test_flat_is_silent(self):
        assert self.rule.evaluate("TEST", flat_then([100.0, 100.0])) == []


def test_registry_has_phase1_rules():
    assert [type(r).__name__ for r in RULES] == ["PriceSma200Rule", "GoldenCrossRule"]
    assert {r.category for r in RULES} == {"price_sma200", "sma50_sma200"}
