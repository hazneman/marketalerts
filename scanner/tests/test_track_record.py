import datetime as dt
import json

import pandas as pd
import pytest

import track_record as tr
from track_record import (
    build, entry_id, finalize_seed, merge, nearest_prior,
    new_entries_from_history, update_entry,
)


# ── fixtures (injected — every test is offline) ──────────────────────────────

def benches():
    us_by = {"2026-06-01": 500.0, "2026-06-15": 527.10, "2026-07-17": 543.21}
    de_by = {"2026-06-15": 18000.0, "2026-07-17": 18500.0}
    return {
        "us": {"symbol": "SPY", "by_date": us_by, "sorted_dates": sorted(us_by),
               "last_date": "2026-07-17", "last_close": 543.21},
        "de": {"symbol": "^GDAXI", "by_date": de_by, "sorted_dates": sorted(de_by),
               "last_date": "2026-07-17", "last_close": 18500.0},
    }


def history():
    return {"days": [
        {"bar_date": "2026-06-15", "alerts": [
            {"ticker": "AAPL", "rule": "PRICE_SMA200_BULL", "category": "price_sma200",
             "direction": "bullish", "date": "2026-06-15", "close": 195.20, "verdict": "buy",
             "fib": {"daily": {}}, "fundamentals": {"score": 3}},  # heavy blobs must be dropped
            {"ticker": "MSFT", "rule": "GOLDEN_CROSS", "category": "sma50_sma200",
             "direction": "bullish", "date": "2026-06-15", "close": 410.0, "verdict": "hold"},
            {"ticker": "SAP.DE", "rule": "PRICE_SMA200_BULL", "category": "price_sma200",
             "direction": "bullish", "date": "2026-06-15", "close": 180.0, "verdict": "buy"},
        ]},
        # same AAPL cross event repeated on another day — must dedup to one entry
        {"bar_date": "2026-06-16", "alerts": [
            {"ticker": "AAPL", "rule": "PRICE_SMA200_BULL", "category": "price_sma200",
             "direction": "bullish", "date": "2026-06-15", "close": 195.20, "verdict": "buy"},
        ]},
    ]}


PRICES = {"AAPL": {"close": 210.50}, "SAP.DE": {"close": 190.0}}


def ts(hour):
    return dt.datetime(2026, 7, 17, hour, 0, tzinfo=dt.timezone.utc)


# ── pure functions ───────────────────────────────────────────────────────────

def test_entry_id_format():
    assert entry_id("AAPL", "PRICE_SMA200_BULL", "2026-06-15") == "AAPL|PRICE_SMA200_BULL|2026-06-15"


class TestNearestPrior:
    dates = ["2026-06-01", "2026-06-15", "2026-07-17"]

    def test_exact_hit(self):
        assert nearest_prior("2026-06-15", self.dates) == "2026-06-15"

    def test_between_returns_prior(self):
        assert nearest_prior("2026-06-20", self.dates) == "2026-06-15"

    def test_before_first_is_none(self):
        assert nearest_prior("2026-05-01", self.dates) is None

    def test_after_last_returns_last(self):
        assert nearest_prior("2026-08-01", self.dates) == "2026-07-17"


def test_new_entries_from_history_filters_maps_and_dedups():
    seeds = new_entries_from_history(history())
    ids = sorted(s["id"] for s in seeds)
    assert ids == ["AAPL|PRICE_SMA200_BULL|2026-06-15", "SAP.DE|PRICE_SMA200_BULL|2026-06-15"]
    aapl = next(s for s in seeds if s["ticker"] == "AAPL")
    assert aapl["entry_date"] == "2026-06-15" and aapl["entry_price"] == 195.20
    assert aapl["market"] == "us" and aapl["benchmark"] == "SPY"
    sap = next(s for s in seeds if s["ticker"] == "SAP.DE")
    assert sap["market"] == "de" and sap["benchmark"] == "^GDAXI"
    # lean: none of the heavy nested blobs carried over
    assert "fib" not in aapl and "fundamentals" not in aapl


def test_finalize_seed_freezes_bench_anchor_nearest_prior():
    seed = {"id": "X|R|2026-06-20", "ticker": "X", "market": "us", "rule": "R",
            "entry_date": "2026-06-20", "entry_price": 100.0, "benchmark": "SPY"}
    e = finalize_seed(seed, benches())
    assert e["entry_bench_close"] == 527.10  # nearest-prior to 06-20 is 06-15
    assert e["status"] == "open" and e["last_price"] is None and e["days_held"] == 0


class TestMerge:
    def test_adds_new_and_ignores_duplicate_id(self):
        existing = [finalize_seed({"id": "AAPL|PRICE_SMA200_BULL|2026-06-15", "ticker": "AAPL",
                                   "market": "us", "rule": "PRICE_SMA200_BULL",
                                   "entry_date": "2026-06-15", "entry_price": 999.0,
                                   "benchmark": "SPY"}, benches())]
        out = merge(existing, new_entries_from_history(history()), benches())
        ids = sorted(e["id"] for e in out)
        assert ids == ["AAPL|PRICE_SMA200_BULL|2026-06-15", "SAP.DE|PRICE_SMA200_BULL|2026-06-15"]

    def test_preserves_existing_and_does_not_reset_entry_price(self):
        # existing AAPL has a (deliberately wrong) entry_price; re-seeding must NOT overwrite it
        existing = [finalize_seed({"id": "AAPL|PRICE_SMA200_BULL|2026-06-15", "ticker": "AAPL",
                                   "market": "us", "rule": "PRICE_SMA200_BULL",
                                   "entry_date": "2026-06-15", "entry_price": 999.0,
                                   "benchmark": "SPY"}, benches())]
        out = merge(existing, new_entries_from_history(history()), benches())
        aapl = next(e for e in out if e["ticker"] == "AAPL")
        assert aapl["entry_price"] == 999.0  # untouched


class TestUpdateEntry:
    def _open(self, market="us", ticker="AAPL", entry_price=195.20, entry_bench=527.10):
        return {"id": f"{ticker}|R|2026-06-15", "ticker": ticker, "market": market,
                "rule": "R", "entry_date": "2026-06-15", "entry_price": entry_price,
                "benchmark": "SPY", "entry_bench_close": entry_bench, "status": "open",
                "last_price": None, "days_held": 0}

    def test_return_excess_and_success_us(self):
        e = update_entry(self._open(), PRICES, benches(), "2026-07-17")
        assert e["stock_return_pct"] == round((210.50 / 195.20 - 1) * 100, 2)   # +7.84
        assert e["bench_return_pct"] == round((543.21 / 527.10 - 1) * 100, 2)   # +3.06
        assert e["excess_pct"] == round(e["stock_return_pct"] - e["bench_return_pct"], 2)
        assert e["success"] is True
        assert e["days_held"] == 32 and e["last_date"] == "2026-07-17"

    def test_per_market_benchmark_selection(self):
        e = update_entry(self._open(market="de", ticker="SAP.DE", entry_price=180.0,
                                    entry_bench=18000.0), PRICES, benches(), "2026-07-17")
        # SAP.DE benchmarked against ^GDAXI last_close, not SPY
        assert e["bench_return_pct"] == round((18500.0 / 18000.0 - 1) * 100, 2)  # +2.78

    def test_success_boundary_zero_and_negative_are_false(self):
        # stock return exactly equals bench return -> excess 0 -> not a success
        e = self._open(entry_price=195.20, entry_bench=527.10)
        # craft prices so stock return == bench return (+3.06%)
        px = {"AAPL": {"close": round(195.20 * 543.21 / 527.10, 2)}}
        out = update_entry(e, px, benches(), "2026-07-17")
        assert out["excess_pct"] == pytest.approx(0.0, abs=0.02)
        assert out["success"] is False

    def test_missing_price_carries_previous(self):
        e = self._open()
        e["last_price"] = 200.0
        out = update_entry(e, {}, benches(), "2026-07-17")  # AAPL absent from prices
        assert out["last_price"] == 200.0  # carried forward, not None/0

    def test_matured_entry_is_frozen(self):
        e = {**self._open(), "status": "matured", "last_price": 111.0, "stock_return_pct": 1.0}
        out = update_entry(e, PRICES, benches(), "2026-07-17")
        assert out is e  # untouched

    def test_open_matures_after_window(self):
        e = self._open()
        e["entry_date"] = "2026-01-01"  # ~198 days before bar_date
        out = update_entry(e, PRICES, benches(), "2026-07-17")
        assert out["status"] == "matured"


def test_cap_drops_oldest_matured_first(monkeypatch):
    monkeypatch.setattr(tr, "MAX_ENTRIES", 2)
    entries = [
        {"id": "a", "status": "matured", "entry_date": "2026-01-01"},
        {"id": "b", "status": "matured", "entry_date": "2026-02-01"},
        {"id": "c", "status": "open", "entry_date": "2026-03-01"},
    ]
    ids = {e["id"] for e in tr._cap(entries)}
    assert ids == {"b", "c"}  # open kept, newer matured kept, oldest matured dropped


# ── build() (tmp_path, injected benches+history → offline) ───────────────────

def test_build_backfills_from_history(tmp_path):
    d = build(tmp_path, prices=PRICES, bar_date="2026-07-17",
              benches=benches(), history=history(), now=ts(22))
    assert {e["ticker"] for e in d["entries"]} == {"AAPL", "SAP.DE"}
    assert d["benchmarks"]["us"]["symbol"] == "SPY"
    assert d["benchmarks"]["de"]["symbol"] == "^GDAXI"
    aapl = next(e for e in d["entries"] if e["ticker"] == "AAPL")
    assert aapl["success"] is True and aapl["entry_bench_close"] == 527.10


def test_build_rerun_is_byte_identical(tmp_path):
    build(tmp_path, prices=PRICES, bar_date="2026-07-17",
          benches=benches(), history=history(), now=ts(22))
    before = (tmp_path / "track_record.json").read_bytes()
    build(tmp_path, prices=PRICES, bar_date="2026-07-17",
          benches=benches(), history=history(), now=ts(23))  # holiday re-run, later time
    assert (tmp_path / "track_record.json").read_bytes() == before


def test_build_changed_price_changes_bytes_and_timestamp(tmp_path):
    build(tmp_path, prices=PRICES, bar_date="2026-07-17",
          benches=benches(), history=history(), now=ts(22))
    before = (tmp_path / "track_record.json").read_bytes()
    moved = {"AAPL": {"close": 240.0}, "SAP.DE": {"close": 190.0}}
    build(tmp_path, prices=moved, bar_date="2026-07-17",
          benches=benches(), history=history(), now=ts(23))
    data = json.loads((tmp_path / "track_record.json").read_text())
    assert (tmp_path / "track_record.json").read_bytes() != before
    assert data["generated_at"] == "2026-07-17T23:00:00Z"


def test_build_accumulates_across_bars(tmp_path):
    # day 1: only AAPL in history
    h1 = {"days": [{"bar_date": "2026-06-15", "alerts": [
        {"ticker": "AAPL", "rule": "R", "category": "c", "direction": "bullish",
         "date": "2026-06-15", "close": 195.20, "verdict": "buy"}]}]}
    build(tmp_path, prices=PRICES, bar_date="2026-06-15", benches=benches(), history=h1, now=ts(22))
    # day 2: history no longer contains AAPL (aged out), but a new NVDA buy appears
    h2 = {"days": [{"bar_date": "2026-07-17", "alerts": [
        {"ticker": "NVDA", "rule": "R", "category": "c", "direction": "bullish",
         "date": "2026-07-17", "close": 200.0, "verdict": "buy"}]}]}
    px2 = {"AAPL": {"close": 210.50}, "NVDA": {"close": 205.0}}
    d = build(tmp_path, prices=px2, bar_date="2026-07-17", benches=benches(), history=h2, now=ts(22))
    # AAPL still tracked (accumulation) even though it left the history window
    assert {e["ticker"] for e in d["entries"]} == {"AAPL", "NVDA"}


def test_build_raises_on_unavailable_benchmark(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "fetch_us", lambda *a, **k: pd.DataFrame())
    with pytest.raises(RuntimeError):
        build(tmp_path, prices=PRICES, bar_date="2026-07-17", history=history())  # benches=None → fetch


def test_fetch_benches_aligns_last_close_to_bar_date(monkeypatch):
    # index has a later (still-forming) bar than the scan's bar_date; last_close
    # must anchor to the bar_date's close, not the latest bar.
    idx = pd.to_datetime(["2026-07-15", "2026-07-16", "2026-07-17"])
    df = pd.DataFrame({"close": [520.0, 527.10, 999.99]}, index=idx)  # 07-17 = live/garbage
    monkeypatch.setattr(tr, "fetch_us", lambda *a, **k: df)
    monkeypatch.setattr(tr, "MIN_BENCH_BARS", 1)
    out = tr._fetch_benches({"us"}, bar_dates={"us": "2026-07-16"})
    assert out["us"]["last_date"] == "2026-07-16"
    assert out["us"]["last_close"] == 527.10  # not 999.99
