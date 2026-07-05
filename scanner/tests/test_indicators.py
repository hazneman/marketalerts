import numpy as np
import pandas as pd

from indicators import rsi, sma


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
