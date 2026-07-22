from recommend import (analyst_block, fundamental_flags, fundamental_summary,
                       leverage_level, profile_metrics, score_info, sector_factor,
                       verdict, weak_balance_sheet)


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


class TestProfileMetrics:
    def test_extracts_and_scales(self):
        p = profile_metrics({
            "returnOnEquity": 0.223, "operatingMargins": 0.31, "grossMargins": 0.68,
            "profitMargins": 0.24, "revenueGrowth": 0.092, "debtToEquity": 88.4,
            "totalDebt": 30e9, "totalCash": 10e9, "ebitda": 20e9,  # nd/ebitda = 1.0
            "enterpriseToEbitda": 18.2, "trailingPegRatio": 1.6,
            "freeCashflow": 8e9, "marketCap": 2e11, "netIncomeToCommon": 10e9,
            "dividendRate": 3.0, "currentPrice": 100.0, "currentRatio": 1.4,
        })
        assert p["roe"] == 22.3
        assert p["op_margin"] == 31.0
        assert p["debt_to_equity"] == 0.88          # Yahoo percent -> ratio
        assert p["net_debt_to_ebitda"] == 1.0
        assert p["p_fcf"] == 25.0
        assert p["fcf_to_net_income"] == 0.8
        assert p["div_yield"] == 3.0                 # from $ rate, not the ambiguous field
        assert p["ev_ebitda"] == 18.2

    def test_missing_data_omits_keys(self):
        assert profile_metrics({}) == {}
        assert "peg" not in profile_metrics({"pegRatio": 0})  # non-positive dropped

    def test_display_metrics_never_touch_the_score(self):
        # a name with rich profile data but no scoring factors stays neutral/0
        info = {"returnOnEquity": 0.4, "operatingMargins": 0.5, "marketCap": 1e11}
        assert score_info(info)["score"] == 0
        assert profile_metrics(info)  # ...yet profile is populated


class TestFundamentalFlags:
    def test_high_leverage(self):
        assert "high_leverage" in fundamental_flags({}, {"net_debt_to_ebitda": 5.0})
        assert "high_leverage" in fundamental_flags({}, {"debt_to_equity": 2.5})

    def test_value_trap_cheap_but_shaky(self):
        flags = fundamental_flags({"valuation": 1, "fcf_yield": -1}, {})
        assert "value_trap" in flags

    def test_no_trap_when_cheap_and_healthy(self):
        flags = fundamental_flags({"valuation": 1}, {"net_debt_to_ebitda": 0.5})
        assert "value_trap" not in flags

    def test_earnings_not_cash_backed(self):
        assert "earnings_not_cash_backed" in fundamental_flags({}, {"fcf_to_net_income": 0.4})
        assert "earnings_not_cash_backed" not in fundamental_flags({}, {"fcf_to_net_income": 0.9})


class TestLeverageCoherence:
    """The summary wording and the high_leverage flag must never disagree —
    both derive from leverage_level (coherence gap #1 fix)."""

    def _summary_and_flags(self, profile):
        return (fundamental_summary({}, profile), fundamental_flags({}, profile))

    def test_high_via_de_shows_de_and_flags(self):
        # low net-debt/EBITDA but high D/E: must read "high leverage" AND flag it,
        # citing the driver (D/E) — the old code said "low leverage" + a high badge
        p = {"net_debt_to_ebitda": 0.8, "debt_to_equity": 2.5}
        assert leverage_level(p) == ("high", "D/E 2.5×")
        summary, flags = self._summary_and_flags(p)
        assert "high leverage (D/E 2.5×)" in summary
        assert "high_leverage" in flags

    def test_between_thresholds_is_moderate_and_unflagged(self):
        # net-debt/EBITDA 3.5 is below the flag bar (>4): summary must NOT say
        # "high leverage" while no badge shows
        p = {"net_debt_to_ebitda": 3.5}
        assert leverage_level(p)[0] == "moderate"
        summary, flags = self._summary_and_flags(p)
        assert "moderate leverage (3.5× net debt/EBITDA)" in summary
        assert "high_leverage" not in flags

    def test_high_via_nde_shows_nde(self):
        assert leverage_level({"net_debt_to_ebitda": 5.0}) == ("high", "5.0× net debt/EBITDA")

    def test_net_cash(self):
        level, _ = leverage_level({"net_debt_to_ebitda": -0.5})
        assert level == "net cash"
        assert "net cash" in fundamental_summary({}, {"net_debt_to_ebitda": -0.5})

    def test_none_when_no_gauge(self):
        assert leverage_level({}) is None

    def test_flag_set_matches_high_level_exactly(self):
        # the flag fires iff leverage_level says "high", across a spread of inputs
        for p in ({"net_debt_to_ebitda": 4.1}, {"debt_to_equity": 2.1},
                  {"net_debt_to_ebitda": 1.0}, {"debt_to_equity": 0.4},
                  {"net_debt_to_ebitda": 0.5, "debt_to_equity": 3.0}):
            lev = leverage_level(p)
            is_high = lev is not None and lev[0] == "high"
            assert ("high_leverage" in fundamental_flags({}, p)) == is_high


class TestFundamentalSummary:
    def test_full_synthesis(self):
        s = fundamental_summary(
            {"forward_pe": 34, "earnings_growth_pct": 20},
            {"op_margin": 45, "roe": 38, "net_debt_to_ebitda": 0.5, "rev_growth": 9},
        )
        assert "highly profitable" in s and "ROE 38%" in s
        assert "low leverage" in s
        assert "premium valuation (fwd P/E 34)" in s
        # both growth gauges point up -> one word, both figures
        assert "growing (rev +9%, EPS +20%)" in s

    def test_growth_diverging_withholds_verdict_word(self):
        # revenue up but earnings down: no "growing" claim (would clash with the
        # -1 earnings-growth factor chip); show both figures instead
        s = fundamental_summary({"earnings_growth_pct": -20}, {"rev_growth": 10})
        assert "rev +10% / EPS -20%" in s
        assert "growing" not in s

    def test_growth_same_direction_uses_conservative_word(self):
        # rev +30 / EPS +6 both positive -> word by the weaker (EPS 6 = "growing")
        s = fundamental_summary({"earnings_growth_pct": 6}, {"rev_growth": 30})
        assert "growing (rev +30%, EPS +6%)" in s

    def test_growth_single_gauge(self):
        assert "shrinking (EPS -8%)" in fundamental_summary({"earnings_growth_pct": -8}, {})
        assert "growing (rev +7%)" in fundamental_summary({}, {"rev_growth": 7})

    def test_missing_clauses_dropped(self):
        assert fundamental_summary({}, {}) == ""
        assert fundamental_summary({"forward_pe": 12}, {}) == "cheap valuation (fwd P/E 12)"


class TestWeakBalanceSheet:
    """Candidate balance-sheet risk (Lane B) — verifier-lab/measurement only,
    must never influence score_info/verdict."""

    def test_over_levered_flags(self):
        assert weak_balance_sheet({"net_debt_to_ebitda": 4.0}, "Industrials")

    def test_illiquid_flags(self):
        assert weak_balance_sheet({"current_ratio": 0.8}, "Technology")

    def test_healthy_is_clean(self):
        assert not weak_balance_sheet({"net_debt_to_ebitda": 1.0, "current_ratio": 2.0}, "Energy")

    def test_exempt_sectors_never_flag(self):
        # leverage is structural for these — a generic gate would misfire
        for s in ("Financial Services", "Real Estate", "Utilities"):
            assert not weak_balance_sheet({"net_debt_to_ebitda": 9.0, "current_ratio": 0.2}, s)

    def test_missing_data_degrades_clean(self):
        assert not weak_balance_sheet({}, "Industrials")
        assert not weak_balance_sheet({"net_debt_to_ebitda": None}, "Industrials")

    def test_does_not_touch_the_verdict(self):
        # a wrecked balance sheet leaves score/verdict untouched (it's not scored)
        info = {"marketCap": 1e11, "totalDebt": 9e9, "totalCash": 0, "ebitda": 1e9}
        assert score_info(info)["score"] == 0
        assert verdict("bullish", True, score_info(info)["score"])[0] == "buy"


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


class TestRsiExtendedCap:
    def test_never_sell_even_with_macd_and_weak_fundamentals(self):
        v, reason = verdict("bearish", True, -5, "lagging", "rsi_extended")
        assert v == "hold"
        assert "trim" in reason

    def test_capped_regardless_of_macd(self):
        assert verdict("bearish", False, 0, None, "rsi_extended")[0] == "hold"

    def test_other_categories_unaffected(self):
        assert verdict("bearish", True, -3, None, "price_sma200")[0] == "sell"
