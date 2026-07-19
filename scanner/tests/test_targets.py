import datetime as dt
import json

from targets import build, pick_stale


def ts(hour):
    return dt.datetime(2026, 7, 17, hour, 0, tzinfo=dt.timezone.utc)


def fake_fetch(values):
    def f(ticker):
        v = values.get(ticker, 'FAIL')
        if v == 'FAIL':
            return ticker, None, False
        return ticker, {"target_mean": v}, True
    return f


class TestPickStale:
    UNIVERSE = ['A', 'B', 'C', 'D']

    def test_missing_first_then_oldest(self):
        prev = {'A': {'as_of': '2026-07-01'}, 'B': {'as_of': '2026-07-16'}}
        # C, D missing -> first; A stale (>7d); B fresh -> excluded
        assert pick_stale(self.UNIVERSE, prev, '2026-07-17') == ['C', 'D', 'A']

    def test_batch_cap_and_determinism(self):
        assert pick_stale(self.UNIVERSE, {}, '2026-07-17', batch=2) == ['A', 'B']

    def test_boundary_exactly_max_age_is_stale(self):
        prev = {'A': {'as_of': '2026-07-10'}}  # exactly 7 days before
        assert pick_stale(['A'], prev, '2026-07-17') == ['A']


def test_build_caches_and_records_null_coverage(tmp_path):
    d = build(tmp_path, bar_date='2026-07-17', universe=['A', 'B'],
              fetch=fake_fetch({'A': 100.0, 'B': None}), now=ts(22))
    assert d['targets']['A'] == {'target_mean': 100.0, 'as_of': '2026-07-17'}
    assert d['targets']['B']['target_mean'] is None  # no coverage, recorded (not retried daily)


def test_build_fetch_failure_keeps_previous(tmp_path):
    build(tmp_path, bar_date='2026-07-01', universe=['A'],
          fetch=fake_fetch({'A': 100.0}), now=ts(22))
    d = build(tmp_path, bar_date='2026-07-17', universe=['A'],
              fetch=fake_fetch({}), now=ts(23))  # A fetch fails
    assert d['targets']['A']['target_mean'] == 100.0
    assert d['targets']['A']['as_of'] == '2026-07-01'  # unchanged -> retried next run


def test_build_rerun_same_bar_is_byte_identical(tmp_path):
    build(tmp_path, bar_date='2026-07-17', universe=['A'],
          fetch=fake_fetch({'A': 100.0}), now=ts(22))
    before = (tmp_path / 'targets.json').read_bytes()
    build(tmp_path, bar_date='2026-07-17', universe=['A'],
          fetch=fake_fetch({'A': 100.0}), now=ts(23))  # holiday re-run
    assert (tmp_path / 'targets.json').read_bytes() == before


def test_build_fresh_entries_not_refetched(tmp_path):
    build(tmp_path, bar_date='2026-07-17', universe=['A'],
          fetch=fake_fetch({'A': 100.0}), now=ts(22))
    calls = []
    def spy(t):
        calls.append(t)
        return t, {"target_mean": 999.0}, True
    d = build(tmp_path, bar_date='2026-07-18', universe=['A'], fetch=spy, now=ts(23))
    assert calls == [] and d['targets']['A']['target_mean'] == 100.0
