"""Tests for the verifier lab's pure logic (no network): cross_events, the
re-fire classification, and the multi-model entry flags."""

import pandas as pd

from verifier_lab import REFIRE_DAYS, cross_events, cross_model_flags


def series(values, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series([float(v) for v in values], index=idx)


def frame(closes, volumes=None, start="2024-01-01"):
    c = series(closes, start)
    v = series(volumes if volumes is not None else [100] * len(closes), start)
    return pd.DataFrame({"close": c, "volume": v})


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
            assert set(flags) == {"vol_confirm", "slope_up", "rsi_calm", "not_refire"}
        assert events[0][1]["not_refire"] is True
        assert events[1][1]["not_refire"] is False  # quick re-cross
