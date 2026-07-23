"""Tests for the sector-baselines pure logic (no network)."""

from baselines import compute_baselines, load_cache, merge_observations, pick_stalest


def cache_with(entries: dict) -> dict:
    return {"schema_version": 1, "tickers": entries}


class TestPickStalest:
    def test_never_seen_first_then_oldest(self):
        cache = cache_with({
            "AAA": {"as_of": "2026-07-20", "sector": "S", "metrics": {"roe": 1}},
            "BBB": {"as_of": "2026-07-01", "sector": "S", "metrics": {"roe": 1}},
        })
        assert pick_stalest(cache, ["AAA", "BBB", "CCC"], 2) == ["CCC", "BBB"]

    def test_deterministic_tiebreak_by_symbol(self):
        assert pick_stalest(cache_with({}), ["ZZZ", "MMM", "AAA"], 2) == ["AAA", "MMM"]

    def test_exclude(self):
        assert pick_stalest(cache_with({}), ["AAA", "BBB"], 2, exclude={"AAA"}) == ["BBB"]


class TestMergeObservations:
    def test_merges_and_counts_changes(self):
        cache = cache_with({})
        n = merge_observations(
            cache, {"AAA": {"sector": "Tech", "metrics": {"roe": 12.0}}}, "2026-07-22")
        assert n == 1
        assert cache["tickers"]["AAA"]["sector"] == "Tech"

    def test_failure_keeps_previous_observation(self):
        cache = cache_with({"AAA": {"as_of": "2026-07-01", "sector": "Tech",
                                    "metrics": {"roe": 12.0}}})
        n = merge_observations(cache, {"AAA": None}, "2026-07-22")
        assert n == 0
        assert cache["tickers"]["AAA"]["metrics"]["roe"] == 12.0

    def test_same_content_only_bumps_nothing(self):
        # identical metrics on a later date: not counted as a change (byte-stable
        # cache — no nightly churn when nothing moved)... as_of is ignored in diff
        cache = cache_with({"AAA": {"as_of": "2026-07-01", "sector": "Tech",
                                    "metrics": {"roe": 12.0}}})
        n = merge_observations(cache, {"AAA": {"sector": "Tech", "metrics": {"roe": 12.0}}},
                               "2026-07-22")
        assert n == 0

    def test_sector_or_metrics_missing_is_skipped(self):
        cache = cache_with({})
        assert merge_observations(cache, {"AAA": {"sector": None, "metrics": {"roe": 1}},
                                          "BBB": {"sector": "Tech", "metrics": {}}},
                                  "2026-07-22") == 0
        assert cache["tickers"] == {}


class TestComputeBaselines:
    def test_quartiles_per_sector_metric(self):
        entries = {f"T{i}": {"as_of": "2026-07-22", "sector": "Tech",
                             "metrics": {"roe": float(i)}} for i in range(1, 9)}  # 1..8
        out = compute_baselines(cache_with(entries), min_n=8)
        s = out["Tech"]["roe"]
        assert s["n"] == 8
        assert s["med"] == 4.5
        assert s["p25"] == 2.75 and s["p75"] == 6.25  # inclusive quartiles

    def test_thin_sector_metric_omitted(self):
        entries = {f"T{i}": {"as_of": "d", "sector": "Tech", "metrics": {"roe": 1.0}}
                   for i in range(5)}
        assert compute_baselines(cache_with(entries), min_n=8) == {}

    def test_sectors_isolated(self):
        entries = {}
        for i in range(8):
            entries[f"U{i}"] = {"as_of": "d", "sector": "Utilities",
                                "metrics": {"net_debt_to_ebitda": 5.0}}
            entries[f"K{i}"] = {"as_of": "d", "sector": "Tech",
                                "metrics": {"net_debt_to_ebitda": 0.5}}
        out = compute_baselines(cache_with(entries), min_n=8)
        assert out["Utilities"]["net_debt_to_ebitda"]["med"] == 5.0
        assert out["Tech"]["net_debt_to_ebitda"]["med"] == 0.5


class TestLoadCache:
    def test_missing_or_garbage_yields_empty(self, tmp_path):
        assert load_cache(tmp_path / "nope.json")["tickers"] == {}
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        assert load_cache(p)["tickers"] == {}
