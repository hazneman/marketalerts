"""Sector rotation snapshot — where money is flowing.

Tracks the 11 SPDR Select Sector ETFs against SPY. The core signal is
RELATIVE STRENGTH (sector return minus SPY return): money rotates toward
sectors outperforming the market and away from those lagging. For each sector
we compute:
  - multi-horizon returns (1w..1y)
  - relative strength vs SPY at 1m / 3m / 6m
  - a composite rs_score (recency-weighted) used to rank leaders -> laggards
  - trend regime (above/below its own 200-day SMA)
  - an RRG-style rotation state from the sign of short vs medium relative
    strength: leading / improving / weakening / lagging

Each sector row also carries its `top` constituents — the 10 biggest members
by market cap (shares from the sector_membership.json cache x the close the
scan already fetched) with compact fundamentals, fetched only for those ~110
tickers. Without fresh prices (standalone run, partial scan) the previous
`top` lists are carried forward instead of wiped.

US sectors only — the SPDR ETFs are the standard, liquid way to read rotation.
Writes frontend/public/data/sectors.json (byte-stable when unchanged).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import fetch_us
from indicators import sma
from recommend import SECTOR_TO_SPDR, score_info

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
MEMBERSHIP_PATH = SCANNER_DIR / "sector_membership.json"
SCHEMA_VERSION = 1
BENCHMARK = "SPY"
TOP_N = 10
FETCH_WORKERS = 6

# SPDR Select Sector ETFs — the 11 GICS sectors.
SECTORS = [
    ("XLK", "Technology"),
    ("XLC", "Communication Services"),
    ("XLY", "Consumer Discretionary"),
    ("XLP", "Consumer Staples"),
    ("XLE", "Energy"),
    ("XLF", "Financials"),
    ("XLV", "Health Care"),
    ("XLI", "Industrials"),
    ("XLB", "Materials"),
    ("XLRE", "Real Estate"),
    ("XLU", "Utilities"),
]

# horizon label -> trading-day lookback
HORIZONS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}


def horizon_returns(close) -> dict[str, float | None]:
    """Percent return over each horizon (None if not enough history)."""
    out: dict[str, float | None] = {}
    px = float(close.iloc[-1])
    for label, n in HORIZONS.items():
        out[label] = round((px / float(close.iloc[-1 - n]) - 1.0) * 100, 2) \
            if len(close) > n else None
    return out


def rs_score(rs_1m: float, rs_3m: float, rs_6m: float) -> float:
    """Recency-weighted composite relative strength used for ranking.

    Weights the freshest money-flow signal (1m) highest while keeping the
    medium-term trend in the mix so a single hot month can't dominate.
    """
    return round(0.5 * rs_1m + 0.35 * rs_3m + 0.15 * rs_6m, 2)


def rotation_state(rs_1m: float, rs_3m: float) -> tuple[str, str]:
    """RRG-style quadrant from short vs medium relative strength."""
    if rs_1m >= 0 and rs_3m >= 0:
        return "leading", "Outperforming the market short and medium term — money flowing in"
    if rs_1m >= 0 > rs_3m:
        return "improving", "Turning up vs the market — early rotation in"
    if rs_1m < 0 <= rs_3m:
        return "weakening", "Was strong, now lagging vs the market — rotation out"
    return "lagging", "Underperforming short and medium term — money flowing out"


def load_membership() -> dict[str, dict] | None:
    """{ticker: {sector, name, shares}} from the cache, or None if absent."""
    try:
        return json.loads(MEMBERSHIP_PATH.read_text())["tickers"]
    except (OSError, ValueError, KeyError):
        return None


def top_constituents(membership: dict[str, dict], prices: dict[str, dict],
                     n: int = TOP_N) -> dict[str, list[dict]]:
    """Ten biggest members per SPDR sector: market cap = shares x close.

    Pure/testable. `prices` is {ticker: {"close": x, "chg_1d_pct": y}} (the
    same shape scan.py writes to prices.json); tickers without a price or an
    unmapped sector are skipped.
    """
    by_spdr: dict[str, list[dict]] = {}
    for ticker, m in membership.items():
        spdr = SECTOR_TO_SPDR.get(m["sector"])
        px = prices.get(ticker)
        if not spdr or not px:
            continue
        by_spdr.setdefault(spdr, []).append({
            "ticker": ticker,
            "name": m["name"],
            "cap": int(m["shares"] * px["close"]),
            "price": px["close"],
            "chg_1d_pct": px.get("chg_1d_pct"),
        })
    return {spdr: sorted(rows, key=lambda r: -r["cap"])[:n]
            for spdr, rows in by_spdr.items()}


def constituent_metrics(info: dict) -> dict:
    """Compact fundamentals for a constituent row from a yfinance .info dict.

    Reuses the 5-factor score for the strong/neutral/weak badge (consistent
    with alert verdicts) plus the display metrics the sector table shows.
    NOTE: .info's dividendYield is already in percent points (0.34 = 0.34%);
    revenueGrowth/profitMargins are fractions.
    """
    scored = score_info(info)
    out = {"score": scored["score"], "rating": scored["rating"]}
    if info.get("forwardPE") is not None:
        out["forward_pe"] = round(info["forwardPE"], 1)
    if info.get("dividendYield") is not None:
        out["div_yield_pct"] = round(info["dividendYield"], 2)
    if info.get("revenueGrowth") is not None:
        out["rev_growth_pct"] = round(info["revenueGrowth"] * 100, 1)
    if info.get("profitMargins") is not None:
        out["margin_pct"] = round(info["profitMargins"] * 100, 1)
    key = info.get("recommendationKey")
    if key and key != "none":
        out["consensus"] = key
    target, price = info.get("targetMeanPrice"), info.get("currentPrice")
    if target and price:
        out["target_upside_pct"] = round((target / price - 1) * 100, 1)
    return out


def _fetch_metrics(ticker: str) -> tuple[str, dict | None]:
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        logger.warning("constituent fundamentals failed for %s (%s)", ticker, exc)
        return ticker, None
    if not info.get("marketCap") and not info.get("recommendationMean"):
        return ticker, None
    return ticker, constituent_metrics(info)


def attach_fundamentals(tops: dict[str, list[dict]]) -> None:
    """Fetch .info fundamentals for every top constituent (threaded, ~110
    tickers). Any failure leaves that row's fundamentals as None — the
    dashboard still shows name/cap/price."""
    tickers = sorted({r["ticker"] for rows in tops.values() for r in rows})
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        fetched = dict(pool.map(_fetch_metrics, tickers))
    for rows in tops.values():
        for r in rows:
            r["fundamentals"] = fetched.get(r["ticker"])


def build(output_dir: Path = DEFAULT_OUTPUT_DIR,
          prices: dict[str, dict] | None = None) -> dict:
    spy = fetch_us(BENCHMARK, period="2y")
    if spy.empty or len(spy) < 260:
        raise RuntimeError("benchmark SPY unavailable — skipping sectors")
    spy_ret = horizon_returns(spy["close"])
    bar_dates = [spy.index[-1].date().isoformat()]

    rows = []
    for symbol, name in SECTORS:
        df = fetch_us(symbol, period="2y")
        if df.empty or len(df) < 260:
            continue
        close = df["close"]
        ret = horizon_returns(close)
        # relative strength = sector return - SPY return (percentage points)
        rs = {h: round(ret[h] - spy_ret[h], 2)
              for h in ("1m", "3m", "6m") if ret[h] is not None and spy_ret[h] is not None}
        if len(rs) < 3:
            continue
        score = rs_score(rs["1m"], rs["3m"], rs["6m"])
        state, comment = rotation_state(rs["1m"], rs["3m"])
        s200 = float(sma(close, 200).iloc[-1])
        px = float(close.iloc[-1])
        bar_dates.append(df.index[-1].date().isoformat())
        rows.append({
            "symbol": symbol, "name": name,
            "price": round(px, 2),
            "above_sma200": px > s200,
            "vs_sma200_pct": round((px / s200 - 1.0) * 100, 2),
            "chg": ret, "rs": rs, "rs_score": score,
            "state": state, "comment": comment,
        })

    rows.sort(key=lambda r: r["rs_score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    # Top-10 constituents per sector. Only rebuild from a FULL price set —
    # a partial scan (--tickers/--limit) or a standalone run without prices
    # must not shrink the lists; carry the previous ones forward instead.
    path = output_dir / "sectors.json"
    try:
        prev = json.loads(path.read_text())
    except (OSError, ValueError):
        prev = None
    membership = load_membership()
    covered = sum(1 for t in (membership or {}) if t in (prices or {}))
    if membership and covered >= 0.8 * len(membership):
        tops = top_constituents(membership, prices)
        attach_fundamentals(tops)
        for r in rows:
            r["top"] = tops.get(r["symbol"], [])
        logger.info("constituents: %d sectors, %d tickers priced",
                    len(tops), covered)
    else:
        prev_tops = {r["symbol"]: r.get("top") for r in (prev or {}).get("sectors", [])}
        for r in rows:
            r["top"] = prev_tops.get(r["symbol"]) or []
        logger.info("constituents: no full price set (%d/%d) — carried forward",
                    covered, len(membership or {}))

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": max(bar_dates),
        "benchmark": {"symbol": BENCHMARK, "chg": spy_ret},
        "sectors": rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    path.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # standalone run: reuse the closes from the last full scan's prices.json
    # so the constituent lists rebuild without refetching the whole universe
    try:
        px = json.loads((DEFAULT_OUTPUT_DIR / "prices.json").read_text())["prices"]
    except (OSError, ValueError, KeyError):
        px = None
    d = build(prices=px)
    print(f"sectors.json written: {len(d['sectors'])} sectors, bar_date={d['bar_date']}")
    for r in d["sectors"]:
        print(f"  {r['rank']:>2}. {r['symbol']:<5} {r['name']:<24} "
              f"score={r['rs_score']:+6.2f}  {r['state']}  top={len(r['top'])}")
