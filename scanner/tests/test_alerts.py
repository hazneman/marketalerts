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


def test_registry_has_rules():
    assert [type(r).__name__ for r in RULES] == [
        "PriceSma200Rule", "GoldenCrossRule", "Sma200WeeklyRule",
        "RsiOverboughtRule"]
    assert {r.category for r in RULES} == {
        "price_sma200", "sma50_sma200", "price_sma200_weekly", "rsi_extended"}


class TestSma200Weekly:
    from alerts.weekly_sma import Sma200WeeklyRule
    rule = Sma200WeeklyRule()

    def weekly(self, *a, **kw):
        # bdate_range starting a Monday with full weeks -> ends on a Friday,
        # so the final week counts as completed
        closes = [100.0] * ((kw.get("n_weeks", 210) - 2) * 5) + \
                 [kw.get("prev", 100.0)] * 5 + [kw.get("last", 100.0)] * 5
        idx = pd.bdate_range("2019-01-07", periods=len(closes))
        return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                             "close": closes, "volume": 1000}, index=idx)

    def test_bull_cross_fires_on_completed_week(self):
        df = self.weekly(prev=99.0, last=105.0)
        alerts = self.rule.evaluate("TEST", df)
        assert [a.rule for a in alerts] == ["PRICE_SMA200W_BULL"]
        a = alerts[0]
        assert a.category == "price_sma200_weekly"
        assert a.close == 105.0
        assert abs(a.values["sma200"] - 100.0) < 0.1
        assert pd.Timestamp(a.date).dayofweek == 4  # dated to the Friday

    def test_bear_cross_fires(self):
        alerts = self.rule.evaluate("TEST", self.weekly(prev=101.0, last=95.0))
        assert [a.rule for a in alerts] == ["PRICE_SMA200W_BEAR"]

    def test_partial_week_is_ignored(self):
        # same cross, but 3 extra days into a new (incomplete) week whose
        # closes sit back at the SMA: the partial bucket must be dropped and
        # the alert still fires off the last COMPLETED week
        df = self.weekly(prev=99.0, last=105.0)
        extra_idx = pd.bdate_range(df.index[-1] + pd.Timedelta(days=1), periods=3)
        extra = pd.DataFrame({"open": 105.0, "high": 105.0, "low": 105.0,
                              "close": 105.0, "volume": 1000}, index=extra_idx)
        alerts = self.rule.evaluate("TEST", pd.concat([df, extra]))
        assert [a.rule for a in alerts] == ["PRICE_SMA200W_BULL"]
        assert alerts[0].date == df.index[-1].date().isoformat()

    def test_insufficient_weeks_is_silent(self):
        assert self.rule.evaluate("TEST", self.weekly(prev=99.0, last=105.0,
                                                      n_weeks=150)) == []


class TestRsiOverbought:
    from alerts.rsi_extended import RsiOverboughtRule
    rule = RsiOverboughtRule()

    @staticmethod
    def rally_df():
        # mild alternation (RSI ~ 50), then a strong rally that pushes RSI
        # through 75 somewhere near the end
        base = 100 + np.cumsum(np.tile([0.3, -0.3], 120))
        rally = base[-1] + np.cumsum(np.full(20, 1.5))
        return make_df(np.concatenate([base, rally]))

    def crossing_index(self, df):
        from indicators import rsi
        r = rsi(df["close"]).astype(float)
        hits = np.where((r.shift(1) <= 75) & (r > 75))[0]
        assert len(hits) > 0
        return hits[-1]

    def test_fires_exactly_on_crossing_day(self):
        df = self.rally_df()
        t = self.crossing_index(df)
        alerts = self.rule.evaluate("TEST", df.iloc[: t + 1])
        assert [a.rule for a in alerts] == ["RSI_OVERBOUGHT"]
        a = alerts[0]
        assert a.category == "rsi_extended"
        assert a.direction == "bearish"
        assert a.values["rsi"] > 75
        # the day BEFORE the crossing: silent
        assert self.rule.evaluate("TEST", df.iloc[:t]) == []

    def test_silent_when_already_overbought(self):
        df = self.rally_df()
        t = self.crossing_index(df)
        if t + 2 <= len(df):  # a day later RSI is still >75 -> no re-fire
            assert self.rule.evaluate("TEST", df.iloc[: t + 2]) == []

    def test_needs_uptrend_context(self):
        # same RSI cross engineered below the SMA200: long decline, then a
        # sharp bounce that lifts RSI above 75 while price is far below SMA200
        closes = np.concatenate([np.linspace(200, 80, 230),
                                 80 + np.cumsum(np.full(15, 1.2))])
        df = make_df(closes)
        from indicators import rsi, sma
        r = rsi(df["close"]).astype(float)
        hits = np.where((r.shift(1) <= 75) & (r > 75))[0]
        for t in hits:
            sub = df.iloc[: t + 1]
            if len(sub) >= 201 and float(sub["close"].iloc[-1]) < float(
                    sma(sub["close"], 200).iloc[-1]):
                assert self.rule.evaluate("TEST", sub) == []
                return
        # if no below-SMA crossing existed the guard wasn't exercised
        raise AssertionError("test setup produced no below-SMA200 RSI crossing")
