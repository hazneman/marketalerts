"""Tests for the verifier lab's pure logic (no network): cross_events, the
re-fire classification, and the multi-model entry flags."""

import pandas as pd

from verifier_lab import REFIRE_DAYS, cross_events, cross_model_flags


def series(values, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series([float(v) for v in values], index=idx)


def frame(closes, volumes=None, highs=None, lows=None, start="2024-01-01"):
    c = series(closes, start)
    v = series(volumes if volumes is not None else [100] * len(closes), start)
    h = series(highs if highs is not None else closes, start)
    l = series(lows if lows is not None else closes, start)
    return pd.DataFrame({"close": c, "volume": v, "high": h, "low": l})


class TestCrossEvents:
    def test_single_cross_is_not_refire(self):
        c = series([50, 50, 50, 50, 200, 200])
        events = cross_events(c, sma_n=3, min_bars=4)
        assert len(events) == 1
        i, refire = events[0]
        assert c.iloc[i] == 200 and refire is False

    def test_quick_recross_is_refire(self):
        # cross up, dip below, cross up again 2 business days later (<=14 calendar)
        c = series([50, 50, 50, 50, 200, 50, 200, 200])
        events = cross_events(c, sma_n=3, min_bars=4)
        assert [r for _, r in events] == [False, True]

    def test_distant_recross_is_not_refire(self):
        # ~30 calendar days below the line between the two crosses
        c = series([50, 50, 50, 50, 200] + [50] * 22 + [200, 200])
        events = cross_events(c, sma_n=3, min_bars=4)
        assert len(events) == 2
        assert [r for _, r in events] == [False, False]
        gap = (c.index[events[1][0]].date() - c.index[events[0][0]].date()).days
        assert gap > REFIRE_DAYS

    def test_no_cross_no_events(self):
        assert cross_events(series([100] * 20), sma_n=3, min_bars=4) == []
        assert cross_events(series(range(100, 120)), sma_n=3, min_bars=25) == []

    def test_default_min_bars_gates_short_series(self):
        # default min_bars = sma_n+1 = 201 — a 50-bar series yields nothing
        assert cross_events(series([50] * 25 + [200] * 25)) == []


class TestCrossModelFlags:
    def _one_cross(self, volumes=None, closes=None):
        closes = closes if closes is not None else [50] * 30 + [200, 200]
        df = frame(closes, volumes)
        events = cross_model_flags(df, sma_n=3, vol_n=5, min_bars=25)
        assert len(events) >= 1
        return events[0][1]

    def test_volume_confirmation(self):
        # cross-day volume 2x its recent average -> confirmed
        vols = [100] * 30 + [200, 100]
        assert self._one_cross(volumes=vols)["vol_confirm"] is True
        # flat volume -> not confirmed (needs >= 1.25x)
        assert self._one_cross(volumes=[100] * 32)["vol_confirm"] is False

    def test_slope_up_vs_falling_line(self):
        # rising base, brief dip below the line, then the cross -> rising line
        rising = list(range(50, 80)) + [40, 200, 200]
        assert self._one_cross(closes=rising)["slope_up"] is True
        # falling base into the cross -> the line being crossed is falling
        falling = list(range(120, 90, -1)) + [200, 200]
        assert self._one_cross(closes=falling)["slope_up"] is False

    def test_flags_present_for_every_cross(self):
        df = frame([50] * 30 + [200, 50, 200, 200])
        events = cross_model_flags(df, sma_n=3, vol_n=5, min_bars=25)
        assert len(events) == 2
        for _, flags in events:
            assert set(flags) == {"vol_confirm", "slope_up", "rsi_calm",
                                  "fib_support", "fib_clear", "not_refire"}
        assert events[0][1]["not_refire"] is True
        assert events[1][1]["not_refire"] is False  # quick re-cross

    def _fib_cross(self, cross_close):
        # swing high 200 / low 100 inside the fib window -> retracement levels
        # at 176.4 / 161.8 / 150 / 138.2 / 121.4 (production math)
        closes = [120] * 28 + [110, cross_close]
        highs = list(closes)
        lows = list(closes)
        highs[-5], lows[-5] = 200, 100
        df = frame(closes, highs=highs, lows=lows)
        events = cross_model_flags(df, sma_n=3, vol_n=5, min_bars=25, fib_window=10)
        assert len(events) == 1
        return events[0][1]

    def test_fib_support_just_above_level(self):
        # close 151 sits +0.67% above the 50% level (150) -> support credit
        flags = self._fib_cross(151)
        assert flags["fib_support"] is True and flags["fib_clear"] is True

    def test_fib_resistance_overhead(self):
        # close 130 is -5.9% under the 61.8% level (138.2) -> resistance, no support
        flags = self._fib_cross(130)
        assert flags["fib_support"] is False and flags["fib_clear"] is False

    def test_fib_unknowable_defaults(self):
        # no high/low columns -> no credit, no penalty
        df = pd.DataFrame({"close": series([50] * 30 + [200, 200]),
                           "volume": series([100] * 32)})
        events = cross_model_flags(df, sma_n=3, vol_n=5, min_bars=25, fib_window=10)
        assert events[0][1]["fib_support"] is False
        assert events[0][1]["fib_clear"] is True
        # window longer than history -> same defaults
        df2 = frame([50] * 30 + [200, 200])
        events2 = cross_model_flags(df2, sma_n=3, vol_n=5, min_bars=25, fib_window=999)
        assert events2[0][1]["fib_support"] is False
        assert events2[0][1]["fib_clear"] is True
