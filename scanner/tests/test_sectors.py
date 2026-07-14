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


class TestTopConstituents:
    MEMBERSHIP = {
        "AAA": {"sector": "Technology", "name": "Aaa Inc.", "shares": 1000},
        "BBB": {"sector": "Technology", "name": "Bbb Corp", "shares": 100},
        "CCC": {"sector": "Technology", "name": "Ccc Co", "shares": 500},
        "DDD": {"sector": "Energy", "name": "Ddd Plc", "shares": 50},
        "EEE": {"sector": "Unknown Sector", "name": "Eee", "shares": 999},
        "FFF": {"sector": "Technology", "name": "No price", "shares": 9999},
    }
    PRICES = {
        "AAA": {"close": 10.0, "chg_1d_pct": 1.0},   # cap 10_000
        "BBB": {"close": 500.0, "chg_1d_pct": -2.0}, # cap 50_000 -> biggest
        "CCC": {"close": 20.0, "chg_1d_pct": None},  # cap 10_000
        "DDD": {"close": 100.0, "chg_1d_pct": 0.5},
        "EEE": {"close": 1.0, "chg_1d_pct": 0.0},
    }

    def test_ranks_by_shares_times_close(self):
        from sectors import top_constituents
        tops = top_constituents(self.MEMBERSHIP, self.PRICES)
        assert [r["ticker"] for r in tops["XLK"]] == ["BBB", "AAA", "CCC"]
        assert tops["XLK"][0]["cap"] == 50_000
        assert tops["XLE"][0]["ticker"] == "DDD"

    def test_caps_at_n(self):
        from sectors import top_constituents
        tops = top_constituents(self.MEMBERSHIP, self.PRICES, n=1)
        assert len(tops["XLK"]) == 1

    def test_skips_unmapped_sector_and_missing_price(self):
        from sectors import top_constituents
        tickers = {r["ticker"] for rows in top_constituents(
            self.MEMBERSHIP, self.PRICES).values() for r in rows}
        assert "EEE" not in tickers  # GICS name with no SPDR mapping
        assert "FFF" not in tickers  # no price for this ticker


def test_constituent_metrics_compact_fields():
    from sectors import constituent_metrics
    info = {
        "forwardPE": 32.827, "dividendYield": 0.34,  # already percent points
        "revenueGrowth": 0.166, "profitMargins": 0.27152,
        "recommendationKey": "buy", "recommendationMean": 2.0,
        "targetMeanPrice": 110.0, "currentPrice": 100.0,
    }
    m = constituent_metrics(info)
    assert m["forward_pe"] == 32.8
    assert m["div_yield_pct"] == 0.34
    assert m["rev_growth_pct"] == 16.6
    assert m["margin_pct"] == 27.2
    assert m["consensus"] == "buy"
    assert m["target_upside_pct"] == 10.0
    assert m["rating"] in ("strong", "neutral", "weak")  # from score_info


def test_constituent_metrics_handles_empty_info():
    from sectors import constituent_metrics
    m = constituent_metrics({})
    assert m["rating"] == "neutral" and m["score"] == 0
    assert "forward_pe" not in m and "consensus" not in m
