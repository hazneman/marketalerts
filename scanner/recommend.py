"""Buy / Hold / Sell verdict: technical signal x MACD confirmation x fundamentals.

Layers (in order of authority):
  1. The alert's direction is the base case (bullish -> buy-lean, bearish -> sell-lean).
  2. MACD gate: if daily MACD momentum disagrees with the signal direction the
     verdict is capped at HOLD — this is the false-signal filter.
  3. Fundamentals + sector overlay: a 5-factor company score (adapted from the
     ichimoku-screener fundamentals module) PLUS a sector-rotation factor
     (US only — is the stock's sector leading or lagging the market, from
     sectors.py). Their sum can veto: a bullish signal into weak fundamentals /
     a sinking sector, or a bearish signal on a strong name in a leading
     sector, both cap at HOLD.

Fundamentals are fetched ONLY for tickers that alerted today (yfinance .info
is slow/flaky per ticker), and every failure degrades gracefully to a
technicals-only verdict.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

STRONG = 2    # combined score >= STRONG  -> strong tailwind
WEAK = -2     # combined score <= WEAK    -> weak / headwind

# yfinance .info["sector"] (GICS name) -> SPDR sector ETF used by sectors.py
SECTOR_TO_SPDR = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

# rotation state -> ±1 factor (conservative: reward clear leaders, penalize
# clear laggards, stay neutral through the transition quadrants)
SECTOR_FACTOR = {"leading": 1, "improving": 0, "weakening": 0, "lagging": -1}


def sector_factor(state: str | None) -> int:
    return SECTOR_FACTOR.get(state or "", 0)


def score_info(info: dict) -> dict:
    """5-factor fundamental score from a yfinance .info dict. Pure/testable.

    Each factor contributes +1 / 0 / -1; missing data contributes 0.
    `metrics` carries the raw values behind each factor for display.
    """
    factors: dict[str, int] = {}
    metrics: dict[str, float] = {}

    rec = info.get("recommendationMean")
    if rec is not None:
        factors["analyst"] = 1 if rec <= 2.2 else (-1 if rec >= 3.5 else 0)
        metrics["rec_mean"] = round(rec, 1)

    fpe = info.get("forwardPE")
    if fpe is not None and fpe > 0:
        factors["valuation"] = 1 if fpe <= 15 else (-1 if fpe >= 40 else 0)
        metrics["forward_pe"] = round(fpe, 1)
    elif fpe is not None:  # negative forward P/E = expected losses
        factors["valuation"] = -1
        metrics["forward_pe"] = round(fpe, 1)

    fcf, mcap = info.get("freeCashflow"), info.get("marketCap")
    if fcf is not None and mcap:
        fcf_yield = fcf / mcap
        factors["fcf_yield"] = 1 if fcf_yield >= 0.04 else (-1 if fcf_yield < 0 else 0)
        metrics["fcf_yield_pct"] = round(fcf_yield * 100, 1)

    target, price = info.get("targetMeanPrice"), info.get("currentPrice")
    if target and price:
        upside = target / price - 1
        factors["target_upside"] = 1 if upside >= 0.15 else (-1 if upside <= -0.05 else 0)
        metrics["target_upside_pct"] = round(upside * 100, 1)

    growth = info.get("earningsGrowth")
    if growth is not None:
        factors["earnings_growth"] = 1 if growth >= 0.10 else (-1 if growth < 0 else 0)
        metrics["earnings_growth_pct"] = round(growth * 100, 1)

    score = sum(factors.values())
    rating = "strong" if score >= STRONG else ("weak" if score <= WEAK else "neutral")
    return {"score": score, "rating": rating, "factors": factors, "metrics": metrics}


def analyst_block(info: dict) -> dict | None:
    """Fresh analyst view from .info: consensus, coverage, target range."""
    out: dict = {}
    if info.get("numberOfAnalystOpinions"):
        out["n_analysts"] = int(info["numberOfAnalystOpinions"])
    key = info.get("recommendationKey")
    if key and key != "none":
        out["consensus"] = key  # strong_buy | buy | hold | underperform | sell
    for src, dst in [("targetLowPrice", "target_low"), ("targetMeanPrice", "target_mean"),
                     ("targetHighPrice", "target_high"), ("currentPrice", "price")]:
        v = info.get(src)
        if v:
            out[dst] = round(float(v), 2)
    return out or None


def recent_rating_changes(tkr, days: int = 90, limit: int = 5) -> list[dict]:
    """Recent analyst upgrades/downgrades. NOTE: Yahoo's feed has been stale
    since late 2024 — with the recency cutoff this usually returns [] and the
    dashboard hides the section; it lights up again if Yahoo resumes the feed."""
    import pandas as pd

    try:
        df = tkr.upgrades_downgrades
        if df is None or df.empty:
            return []
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df.index >= cutoff].sort_index(ascending=False).head(limit)
        return [{
            "date": ts.date().isoformat(),
            "firm": str(row["Firm"]),
            "action": str(row["Action"]),          # up | down | init | main | reit
            "from_grade": str(row["FromGrade"]) or None,
            "to_grade": str(row["ToGrade"]),
        } for ts, row in df.iterrows()]
    except Exception as exc:
        logger.warning("rating changes fetch failed (%s)", exc)
        return []


def fetch_fundamentals(ticker: str) -> dict | None:
    """Fetch + score fundamentals; None when Yahoo has nothing usable."""
    import yfinance as yf

    try:
        tkr = yf.Ticker(ticker)
        info = tkr.info or {}
    except Exception as exc:
        logger.warning("fundamentals fetch failed for %s (%s)", ticker, exc)
        return None
    if not info.get("marketCap") and not info.get("recommendationMean"):
        return None  # index/unknown symbol — nothing to score
    result = score_info(info)
    result["analyst"] = analyst_block(info)
    result["rating_changes"] = recent_rating_changes(tkr)
    result["sector"] = info.get("sector")  # raw GICS name; mapped in scan.py
    return result


def verdict(direction: str, macd_confirms: bool, score: int | None,
            sector_state: str | None = None) -> tuple[str, str]:
    """Combine signal x MACD x (fundamentals + sector) into (verdict, reason)."""
    base = 0 if score is None else score
    eff = base + sector_factor(sector_state)  # combined tailwind/headwind
    fund_note = "" if score is not None else " (fundamentals unavailable)"
    sec_note = (", sector leading" if sector_state == "leading"
                else ", sector lagging" if sector_state == "lagging" else "")

    if direction == "bullish":
        if not macd_confirms:
            return "hold", "MACD momentum does not confirm — possible false break"
        if eff <= WEAK:
            return "hold", "Bullish signal confirmed, but fundamentals/sector are weak" + fund_note
        if eff >= STRONG:
            return "buy", "Bullish signal, MACD confirms, strong fundamentals" + sec_note + fund_note
        return "buy", "Bullish signal confirmed by MACD" + sec_note + fund_note

    if not macd_confirms:
        return "hold", "MACD momentum does not confirm — possible false breakdown"
    if eff >= STRONG:
        return "hold", "Bearish signal but fundamentals/sector strong — trim rather than exit" + fund_note
    if eff <= WEAK:
        return "sell", "Bearish signal, MACD confirms, weak fundamentals" + sec_note + fund_note
    return "sell", "Bearish signal confirmed by MACD" + sec_note + fund_note
