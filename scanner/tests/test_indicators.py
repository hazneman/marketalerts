import numpy as np
import pandas as pd

from indicators import kama, macd, rsi, sma


def test_sma_equals_hand_computed_mean():
    close = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0])
    result = sma(close, 3)
    assert result.iloc[-1] == (12 + 13 + 14) / 3
    assert result.iloc[2] == (10 + 11 + 12) / 3


def test_sma_is_nan_before_window_fills():
    close = pd.Series(np.arange(250, dtype=float))
    result = sma(close, 200)
    assert result.iloc[:199].isna().all()
    assert not result.iloc[199:].isna().any()


def test_sma200_first_valid_value():
    close = pd.Series(np.ones(250))
    assert sma(close, 200).iloc[199] == 1.0


def test_rsi_bounds_and_warmup():
    close = pd.Series(100 + np.sin(np.arange(60)) * 5)
    result = rsi(close)
    assert result.iloc[:14].isna().all()
    valid = result.iloc[14:].astype(float)
    assert ((valid >= 0) & (valid <= 100)).all()


def test_rsi_extremes():
    rising = pd.Series(np.arange(1.0, 61.0))     # only gains -> 100
    falling = pd.Series(np.arange(60.0, 0.0, -1))  # only losses -> ~0
    assert float(rsi(rising).iloc[-1]) == 100.0
    assert float(rsi(falling).iloc[-1]) < 1.0


def test_rsi_uptrend_is_high_downtrend_is_low():
    up = pd.Series(np.cumsum(np.tile([2.0, -0.5], 30)) + 100)
    down = pd.Series(100 - np.cumsum(np.tile([2.0, -0.5], 30)))
    assert float(rsi(up).iloc[-1]) > 65
    assert float(rsi(down).iloc[-1]) < 35


def test_macd_flat_series_is_zero():
    line, sig = macd(pd.Series(np.full(100, 50.0)))
    assert abs(float(line.iloc[-1])) < 1e-9
    assert abs(float(sig.iloc[-1])) < 1e-9


def test_macd_sign_follows_trend():
    up = pd.Series(np.linspace(100, 200, 100))
    down = pd.Series(np.linspace(200, 100, 100))
    assert float(macd(up)[0].iloc[-1]) > 0
    assert float(macd(down)[0].iloc[-1]) < 0


def test_macd_line_crosses_signal_on_turn():
    # rise then fall: MACD line must drop below its (lagging) signal line
    closes = pd.Series(np.concatenate([np.linspace(100, 150, 60),
                                       np.linspace(150, 120, 20)]))
    line, sig = macd(closes)
    assert float(line.iloc[-1]) < float(sig.iloc[-1])
    assert float(line.iloc[59]) > float(sig.iloc[59])


def test_kama_warmup_is_nan_then_seeds_at_price():
    close = pd.Series(np.linspace(100, 130, 40))
    k = kama(close, er_n=10)
    assert k.iloc[:10].isna().all()
    assert k.iloc[10] == close.iloc[10]  # seeded at price, no zero warm-up


def test_kama_tracks_a_clean_trend_fast():
    # strictly directional: ER = 1 -> smoothing at the fast bound (0.444),
    # so the line stays within a few percent of price
    close = pd.Series(np.linspace(100, 200, 120))
    k = kama(close, er_n=10)
    gap_pct = abs(k.iloc[-1] / close.iloc[-1] - 1) * 100
    assert gap_pct < 3


def test_kama_stays_flat_in_chop():
    # alternating noise around 100: ER ~ 0 -> smoothing at the slow bound,
    # so KAMA barely moves while an SMA of the same span wiggles with price
    rng = np.random.RandomState(7)
    close = pd.Series(100 + rng.choice([-2.0, 2.0], size=200).cumsum() * 0 + rng.uniform(-2, 2, 200))
    k = kama(close, er_n=10).dropna()
    assert k.max() - k.min() < (close.max() - close.min()) / 2


def test_kama_moves_less_than_price_day_to_day_in_noise():
    rng = np.random.RandomState(3)
    close = pd.Series(100 + rng.uniform(-3, 3, 150))
    k = kama(close, er_n=10)
    assert k.diff().abs().mean() < close.diff().abs().mean() / 3
