import numpy as np
import pandas as pd

from indicators import fib_retracement, volume_signal
from levels import DAILY_WINDOW, WEEKLY_WINDOW, fib_block


class TestFibRetracement:
    def test_known_swing_levels(self):
        # swing low 100 -> high 200, range 100. Levels descend from the high.
        r = fib_retracement(200.0, 100.0, 150.0)
        prices = {lvl["label"]: lvl["price"] for lvl in r["levels"]}
        assert prices["23.6%"] == 176.4   # 200 - 0.236*100
        assert prices["38.2%"] == 161.8
        assert prices["50.0%"] == 150.0
        assert prices["61.8%"] == 138.2
        assert prices["78.6%"] == 121.4

    def test_position_and_bounds(self):
        r = fib_retracement(200.0, 100.0, 150.0)
        assert r["position_pct"] == 50.0
        assert r["high"] == 200.0 and r["low"] == 100.0

    def test_signed_distance_and_nearest(self):
        # price exactly on the 50% level (150) -> that's nearest, distance 0
        r = fib_retracement(200.0, 100.0, 150.0)
        assert r["nearest"]["label"] == "50.0%"
        assert r["nearest"]["dist_pct"] == 0.0
        # price just above 61.8% (138.2): distance positive (support below)
        r2 = fib_retracement(200.0, 100.0, 140.0)
        assert r2["nearest"]["label"] == "61.8%"
        assert r2["nearest"]["dist_pct"] > 0

    def test_breakout_above_high_position_over_100(self):
        r = fib_retracement(200.0, 100.0, 210.0)
        assert r["position_pct"] > 100
        # every level sits below price -> all distances positive
        assert all(lvl["dist_pct"] > 0 for lvl in r["levels"])

    def test_degenerate_swing_returns_none(self):
        assert fib_retracement(100.0, 100.0, 100.0) is None
        assert fib_retracement(90.0, 100.0, 95.0) is None


class TestVolumeSignal:
    def test_above_average(self):
        vol = pd.Series([100] * 19 + [300])  # last is 3x the ~100 average
        v = volume_signal(vol)
        assert v["above_avg"] is True
        assert v["ratio"] > 1

    def test_below_average(self):
        vol = pd.Series([100] * 19 + [40])
        v = volume_signal(vol)
        assert v["above_avg"] is False
        assert v["ratio"] < 1

    def test_boundary_ratio_one_is_above(self):
        v = volume_signal(pd.Series([100] * 20))
        assert v["ratio"] == 1.0 and v["above_avg"] is True

    def test_insufficient_bars_returns_none(self):
        assert volume_signal(pd.Series([100] * 19)) is None


def _ohlc(closes, highs=None, lows=None, vols=None):
    n = len(closes)
    idx = pd.bdate_range("2022-01-03", periods=n)
    return pd.DataFrame({
        "open": closes,
        "high": highs if highs is not None else closes,
        "low": lows if lows is not None else closes,
        "close": closes,
        "volume": vols if vols is not None else [1000] * n,
    }, index=idx)


class TestFibBlock:
    def test_daily_present_weekly_none_on_short_history(self):
        # 255 business days from a Monday = exactly 51 completed weeks: enough
        # for the daily window (252) but far short of the 104-week weekly.
        closes = list(np.linspace(100, 200, 255))
        block = fib_block(_ohlc(closes))
        assert block["daily"] is not None
        assert block["weekly"] is None

    def test_both_present_with_two_years(self):
        n = 550  # ~2.2 years of daily bars -> >104 completed weeks
        closes = list(100 + 20 * np.sin(np.linspace(0, 8, n)))
        block = fib_block(_ohlc(closes))
        assert block["daily"] is not None
        assert block["weekly"] is not None
        assert set(block["daily"]) == {"high", "low", "position_pct", "levels", "nearest"}

    def test_too_short_for_daily(self):
        block = fib_block(_ohlc(list(range(100, 100 + DAILY_WINDOW - 1))))
        assert block["daily"] is None
