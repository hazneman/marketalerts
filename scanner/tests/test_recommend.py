from recommend import score_info, verdict


class TestScoreInfo:
    def test_all_strong_factors(self):
        info = {
            "recommendationMean": 1.8,       # strong buy consensus
            "forwardPE": 12,                  # cheap
            "freeCashflow": 5e9, "marketCap": 1e11,   # 5% FCF yield
            "targetMeanPrice": 120, "currentPrice": 100,  # +20% upside
            "earningsGrowth": 0.25,
        }
        s = score_info(info)
        assert s["score"] == 5
        assert s["rating"] == "strong"

    def test_all_weak_factors(self):
        info = {
            "recommendationMean": 4.0,
            "forwardPE": -5,                  # expected losses
            "freeCashflow": -1e9, "marketCap": 1e10,
            "targetMeanPrice": 90, "currentPrice": 100,
            "earningsGrowth": -0.3,
        }
        s = score_info(info)
        assert s["score"] == -5
        assert s["rating"] == "weak"

    def test_missing_data_is_neutral(self):
        s = score_info({})
        assert s["score"] == 0
        assert s["rating"] == "neutral"
        assert s["factors"] == {}


class TestVerdict:
    def test_bullish_confirmed_neutral_fund_is_buy(self):
        assert verdict("bullish", True, 0)[0] == "buy"

    def test_bullish_unconfirmed_is_hold(self):
        v, reason = verdict("bullish", False, 5)
        assert v == "hold"
        assert "MACD" in reason

    def test_bullish_confirmed_weak_fund_is_hold(self):
        assert verdict("bullish", True, -3)[0] == "hold"

    def test_bullish_confirmed_strong_fund_is_buy(self):
        v, reason = verdict("bullish", True, 4)
        assert v == "buy"
        assert "strong fundamentals" in reason

    def test_bearish_confirmed_is_sell(self):
        assert verdict("bearish", True, 0)[0] == "sell"

    def test_bearish_unconfirmed_is_hold(self):
        assert verdict("bearish", False, -5)[0] == "hold"

    def test_bearish_on_strong_name_is_hold(self):
        v, reason = verdict("bearish", True, 3)
        assert v == "hold"
        assert "trim" in reason

    def test_no_fundamentals_falls_back_to_technicals(self):
        assert verdict("bullish", True, None)[0] == "buy"
        assert verdict("bearish", True, None)[0] == "sell"
