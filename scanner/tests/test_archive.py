import json

from archive import alert_id, load_archive, merge, update


def hist(days):
    return {"days": days}


def alert(ticker="AAPL", rule="R", date="2026-07-10", **kw):
    return {"ticker": ticker, "rule": rule, "date": date, "category": "c",
            "direction": "bullish", "close": 100.0, "verdict": "buy", **kw}


H1 = hist([
    {"bar_date": "2026-07-10", "alerts": [alert(), alert("SAP.DE")]},
    # same AAPL event repeated on a later history day — must not duplicate
    {"bar_date": "2026-07-11", "alerts": [alert()]},
])


def test_alert_id():
    assert alert_id(alert()) == "AAPL|R|2026-07-10"


def test_first_run_backfills_and_dedups(tmp_path):
    p = tmp_path / "alerts.jsonl"
    r = update(p, history=H1)
    assert r["total"] == 2 and r["added"] == 2 and r["changed"]
    recs = load_archive(p)
    assert set(recs) == {"AAPL|R|2026-07-10", "SAP.DE|R|2026-07-10"}
    # full context preserved on the line
    assert recs["AAPL|R|2026-07-10"]["verdict"] == "buy"


def test_rerun_is_byte_identical(tmp_path):
    p = tmp_path / "alerts.jsonl"
    update(p, history=H1)
    before = p.read_bytes()
    r = update(p, history=H1)
    assert not r["changed"]
    assert p.read_bytes() == before


def test_new_day_appends_and_aged_out_preserved(tmp_path):
    p = tmp_path / "alerts.jsonl"
    update(p, history=H1)
    # window rolled: AAPL/SAP gone from history, a new NVDA alert appears
    h2 = hist([{"bar_date": "2026-08-20", "alerts": [alert("NVDA", date="2026-08-20")]}])
    r = update(p, history=h2)
    assert r["added"] == 1
    recs = load_archive(p)
    assert set(recs) == {"AAPL|R|2026-07-10", "SAP.DE|R|2026-07-10", "NVDA|R|2026-08-20"}


def test_changed_content_refreshes_in_window(tmp_path):
    p = tmp_path / "alerts.jsonl"
    update(p, history=H1)
    # rescan of the same bar with better data (e.g. fundamentals now present)
    h2 = hist([{"bar_date": "2026-07-10",
                "alerts": [alert(verdict="hold"), alert("SAP.DE")]}])
    r = update(p, history=h2)
    assert r["refreshed"] == 1 and r["added"] == 0
    assert load_archive(p)["AAPL|R|2026-07-10"]["verdict"] == "hold"


def test_deterministic_ordering(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    update(a, history=H1)
    # same content arriving in a different day order → identical bytes
    reversed_hist = hist(list(reversed(H1["days"])))
    update(b, history=reversed_hist)
    assert a.read_bytes() == b.read_bytes()


def test_corrupt_line_skipped(tmp_path):
    p = tmp_path / "alerts.jsonl"
    update(p, history=H1)
    p.write_text(p.read_text() + "{not json\n")
    recs = load_archive(p)
    assert len(recs) == 2  # corrupt line ignored, archive still loads


def test_merge_counts():
    merged, added, refreshed = merge({}, H1)
    assert added == 2 and refreshed == 0 and len(merged) == 2
