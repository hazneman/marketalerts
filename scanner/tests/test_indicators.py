import numpy as np
import pandas as pd

from indicators import sma


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
