"""Tests for the verifier lab's pure logic (no network): cross_events, the
re-fire classification that both the live gate and the two-window study use."""

import pandas as pd

from verifier_lab import REFIRE_DAYS, cross_events


def series(values, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series([float(v) for v in values], index=idx)


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
