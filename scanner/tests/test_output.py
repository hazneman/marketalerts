import datetime as dt
import json

from alerts.base import Alert
from output import HISTORY_DAYS, write_results


def alert(ticker="AAPL", date="2026-07-02"):
    return Alert(ticker=ticker, rule="PRICE_SMA200_BULL", category="price_sma200",
                 direction="bullish", date=date, close=105.0, values={"sma200": 100.0})


def meta(bar_date="2026-07-02"):
    return {"bar_date": bar_date, "universe_count": 10, "scanned": 10,
            "failures": [], "insufficient_history": []}


def ts(hour):
    return dt.datetime(2026, 7, 2, hour, 0, tzinfo=dt.timezone.utc)


def test_writes_latest_and_history(tmp_path):
    write_results([alert()], meta(), tmp_path, now=ts(22))
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["bar_date"] == "2026-07-02"
    assert latest["alerts"][0]["ticker"] == "AAPL"
    assert latest["generated_at"] == "2026-07-02T22:00:00Z"
    history = json.loads((tmp_path / "history.json").read_text())
    assert [d["bar_date"] for d in history["days"]] == ["2026-07-02"]


def test_rerun_same_bar_is_byte_identical(tmp_path):
    write_results([alert()], meta(), tmp_path, now=ts(22))
    before = ((tmp_path / "latest.json").read_bytes(),
              (tmp_path / "history.json").read_bytes())
    write_results([alert()], meta(), tmp_path, now=ts(23))  # holiday re-run
    after = ((tmp_path / "latest.json").read_bytes(),
             (tmp_path / "history.json").read_bytes())
    assert before == after


def test_changed_alerts_same_bar_replaces(tmp_path):
    write_results([alert()], meta(), tmp_path, now=ts(22))
    write_results([alert(), alert("MSFT")], meta(), tmp_path, now=ts(23))
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert len(latest["alerts"]) == 2
    assert latest["generated_at"] == "2026-07-02T23:00:00Z"
    history = json.loads((tmp_path / "history.json").read_text())
    assert len(history["days"]) == 1
    assert len(history["days"][0]["alerts"]) == 2


def test_history_newest_first_and_trimmed(tmp_path):
    for i in range(HISTORY_DAYS + 5):
        bar = (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat()
        write_results([alert(date=bar)], meta(bar_date=bar), tmp_path, now=ts(22))
    history = json.loads((tmp_path / "history.json").read_text())
    assert len(history["days"]) == HISTORY_DAYS
    dates = [d["bar_date"] for d in history["days"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2026-02-04"  # newest kept, oldest 5 trimmed
