import datetime as dt
import json

import pandas as pd

from health import build, recent_warnings, ticker_health


def frame(closes):
    idx = pd.bdate_range('2024-01-01', periods=len(closes))
    return pd.DataFrame({'open': closes, 'high': closes, 'low': closes,
                         'close': closes, 'volume': [1000] * len(closes)}, index=idx)


def ts(hour):
    return dt.datetime(2026, 7, 17, hour, 0, tzinfo=dt.timezone.utc)


def test_ticker_health_rising_series():
    df = frame([100 + i * 0.5 for i in range(300)])  # steady uptrend
    h = ticker_health(df)
    assert h['close'] > h['sma200'] and h['vs_sma200_pct'] > 0
    assert h['macd_bullish'] is True
    assert h['chg_20d_pct'] > 0
    assert h['drawdown_pct'] == 0.0  # at its peak


def test_ticker_health_flags_drawdown_and_weakness():
    up = [100 + i for i in range(250)]      # peak ~349
    down = [349 - i * 2 for i in range(60)]  # sharp fall
    h = ticker_health(frame(up + down))
    assert h['drawdown_pct'] < -20
    assert h['vs_sma200_pct'] < 0           # now below the 200-day line
    assert h['macd_bullish'] is False
    assert h['chg_20d_pct'] < 0


def test_ticker_health_needs_enough_bars():
    assert ticker_health(frame([100] * 30)) is None
    assert ticker_health(None) is None
    # 60+ bars but <200: no sma200 key, still returns a dict
    h = ticker_health(frame([100 + i for i in range(80)]))
    assert h is not None and 'sma200' not in h and 'sma50' in h


def test_ticker_health_carries_sector_state():
    h = ticker_health(frame([100 + i * 0.5 for i in range(300)]), sector_state='lagging')
    assert h['sector_state'] == 'lagging'


HIST = {'days': [
    {'bar_date': '2026-07-16', 'alerts': [
        {'ticker': 'AAA', 'date': '2026-07-16', 'direction': 'bearish',
         'category': 'price_sma200', 'rule': 'PRICE_SMA200_BEAR'},
        {'ticker': 'BBB', 'date': '2026-07-16', 'direction': 'bullish',
         'category': 'rsi_extended', 'rule': 'RSI_OVERBOUGHT'},
        {'ticker': 'CCC', 'date': '2026-07-16', 'direction': 'bullish',
         'category': 'price_sma200', 'rule': 'PRICE_SMA200_BULL'},
    ]},
    {'bar_date': '2026-05-01', 'alerts': [  # older than the 30-day window
        {'ticker': 'DDD', 'date': '2026-05-01', 'direction': 'bearish',
         'category': 'price_sma200', 'rule': 'PRICE_SMA200_BEAR'},
    ]},
]}


class TestRecentWarnings:
    def test_keeps_bearish_and_trim_only(self):
        w = recent_warnings(HIST, '2026-07-17')
        assert set(w) == {'AAA', 'BBB'}  # CCC bullish excluded, DDD too old

    def test_trim_alert_counted_though_bullish_direction(self):
        w = recent_warnings(HIST, '2026-07-17')
        assert w['BBB'][0]['category'] == 'rsi_extended'

    def test_window_is_respected(self):
        w = recent_warnings(HIST, '2026-07-17', days=120)
        assert 'DDD' in w  # widen the window and the old one reappears

    def test_dedups_same_event_across_days(self):
        dup = {'days': [HIST['days'][0], HIST['days'][0]]}
        assert len(recent_warnings(dup, '2026-07-17')['AAA']) == 1


def test_build_writes_and_attaches_warnings(tmp_path):
    frames = {'AAA': frame([100 + i * 0.5 for i in range(300)])}
    d = build(tmp_path, frames=frames, bar_date='2026-07-17', history=HIST, now=ts(22))
    assert 'AAA' in d['tickers']
    assert d['tickers']['AAA']['recent_warnings'][0]['rule'] == 'PRICE_SMA200_BEAR'
    assert d['warn_days'] == 30


def test_build_rerun_is_byte_identical(tmp_path):
    frames = {'AAA': frame([100 + i * 0.5 for i in range(300)])}
    build(tmp_path, frames=frames, bar_date='2026-07-17', history=HIST, now=ts(22))
    before = (tmp_path / 'health.json').read_bytes()
    build(tmp_path, frames=frames, bar_date='2026-07-17', history=HIST, now=ts(23))
    assert (tmp_path / 'health.json').read_bytes() == before


def test_build_skips_short_series(tmp_path):
    d = build(tmp_path, frames={'SHORT': frame([100] * 20)}, bar_date='2026-07-17',
              history={'days': []}, now=ts(22))
    assert d['tickers'] == {}
