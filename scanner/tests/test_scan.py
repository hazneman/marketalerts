"""Tests for scan.py's final-bar guard: a bar dated today is dropped until
that market's session has closed (plus settle buffer), so daytime runs never
evaluate a forming intraday close."""

import datetime as dt

import pandas as pd

from scan import drop_forming_bars, market_of


def frame(dates):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return pd.DataFrame({"close": [100.0] * len(idx)}, index=idx)


def at(day, hh, mm):
    return dt.datetime(2026, 8, day, hh, mm, tzinfo=dt.timezone.utc)


class TestDropFormingBars:
    def test_us_forming_bar_dropped_eu_final_kept(self):
        # 16:00 UTC Tuesday: US session open (forming bar dropped), BIST
        # closed 15:00 UTC + buffer passed (final bar kept), DE still inside
        # its settle window (dropped).
        frames = {
            "AAPL": frame(["2026-08-03", "2026-08-04"]),
            "GARAN.IS": frame(["2026-08-03", "2026-08-04"]),
            "SAP.DE": frame(["2026-08-03", "2026-08-04"]),
        }
        trimmed = drop_forming_bars(frames, now=at(4, 16, 0))
        assert sorted(trimmed) == ["AAPL", "SAP.DE"]
        assert frames["AAPL"].index[-1].date().isoformat() == "2026-08-03"
        assert frames["SAP.DE"].index[-1].date().isoformat() == "2026-08-03"
        assert frames["GARAN.IS"].index[-1].date().isoformat() == "2026-08-04"

    def test_evening_run_keeps_everything(self):
        # 23:35 UTC: all sessions closed and settled — nothing dropped.
        frames = {s: frame(["2026-08-04"]) for s in ["AAPL", "SAP.DE", "GARAN.IS"]}
        assert drop_forming_bars(frames, now=at(4, 23, 35)) == []

    def test_morning_run_keeps_yesterdays_bars(self):
        # 05:10 UTC: every last bar is dated yesterday — final by definition.
        frames = {s: frame(["2026-08-03"]) for s in ["AAPL", "SAP.DE", "GARAN.IS"]}
        assert drop_forming_bars(frames, now=at(4, 5, 10)) == []

    def test_delayed_morning_run_drops_fresh_eu_open(self):
        # Cron delay pushed the morning run past the 07:00 UTC EU open and
        # Yahoo already serves today's forming bar — the guard drops it.
        frames = {"SAP.DE": frame(["2026-08-03", "2026-08-04"])}
        assert drop_forming_bars(frames, now=at(4, 7, 30)) == ["SAP.DE"]
        assert frames["SAP.DE"].index[-1].date().isoformat() == "2026-08-03"

    def test_empty_frame_untouched(self):
        frames = {"AAPL": pd.DataFrame({"close": []})}
        assert drop_forming_bars(frames, now=at(4, 16, 0)) == []
        assert frames["AAPL"].empty

    def test_trim_to_empty_is_safe(self):
        # A single forming bar trims to an empty frame, which the scan then
        # counts as a fetch failure instead of crashing.
        frames = {"AAPL": frame(["2026-08-04"])}
        assert drop_forming_bars(frames, now=at(4, 16, 0)) == ["AAPL"]
        assert frames["AAPL"].empty

    def test_market_of_boundaries(self):
        assert market_of("GARAN.IS") == "bist"
        assert market_of("SAP.DE") == "de"
        assert market_of("AAPL") == "us"
