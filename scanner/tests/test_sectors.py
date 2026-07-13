import pandas as pd

from sectors import horizon_returns, rotation_state, rs_score


def test_horizon_returns_computes_and_handles_short_history():
    close = pd.Series(range(100, 400))  # values 100..399, last=399
    r = horizon_returns(close)
    # 1w = 5 trading days back: iloc[-6] = 394
    assert r["1w"] == round((399 / 394 - 1) * 100, 2)
    assert r["1y"] is not None  # 252 < 300
    short = horizon_returns(pd.Series(range(100, 150)))  # 50 bars
    assert short["1w"] is not None
    assert short["3m"] is None  # 63 > 50


def test_rs_score_recency_weighted():
    # a hot 1m dominates but doesn't fully drown a weak medium term
    assert rs_score(10, 0, 0) == 5.0
    assert rs_score(0, 0, 10) == 1.5
    assert rs_score(4, 4, 4) == 4.0


class TestRotationState:
    def test_leading(self):
        assert rotation_state(3, 5)[0] == "leading"

    def test_improving(self):
        assert rotation_state(2, -1)[0] == "improving"

    def test_weakening(self):
        assert rotation_state(-2, 3)[0] == "weakening"

    def test_lagging(self):
        assert rotation_state(-4, -2)[0] == "lagging"

    def test_boundary_zero_is_leading(self):
        assert rotation_state(0, 0)[0] == "leading"
