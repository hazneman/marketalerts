from recommend import analyst_block, score_info, sector_factor, verdict


class TestAnalystBlock:
    def test_full_info(self):
        a = analyst_block({
            "numberOfAnalystOpinions": 58, "recommendationKey": "strong_buy",
            "targetLowPrice": 664.46, "targetMeanPrice": 828.341,
            "targetHighPrice": 1015.0, "currentPrice": 669.21,
        })
        assert a == {"n_analysts": 58, "consensus": "strong_buy",
                     "target_low": 664.46, "target_mean": 828.34,
                     "target_high": 1015.0, "price": 669.21}

    def test_empty_info_is_none(self):
        assert analyst_block({}) is None
        assert analyst_block({"recommendationKey": "none"}) is None


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


class TestSectorFactor:
    def test_mapping(self):
        assert sector_factor("leading") == 1
        assert sector_factor("lagging") == -1
        assert sector_factor("improving") == 0
        assert sector_factor("weakening") == 0
        assert sector_factor(None) == 0

    def test_lagging_sector_tips_borderline_bull_to_hold(self):
        # neutral company fundamentals (0) that would be BUY on its own...
        assert verdict("bullish", True, 0)[0] == "buy"
        # ...but a -1 sector plus a -1 company factor sums to WEAK -> HOLD
        assert verdict("bullish", True, -1, "lagging")[0] == "hold"

    def test_leading_sector_mentioned_in_reason(self):
        v, reason = verdict("bullish", True, 3, "leading")
        assert v == "buy"
        assert "sector leading" in reason

    def test_leading_sector_defends_strong_name_from_sell(self):
        # bearish on a +1 company name in a leading sector: 1+1=2 >= STRONG -> HOLD
        assert verdict("bearish", True, 1, "leading")[0] == "hold"
