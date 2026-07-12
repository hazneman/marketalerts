"""Buy / Hold / Sell verdict: technical signal x MACD confirmation x fundamentals.

Layers (in order of authority):
  1. The alert's direction is the base case (bullish -> buy-lean, bearish -> sell-lean).
  2. MACD gate: if daily MACD momentum disagrees with the signal direction the
     verdict is capped at HOLD — this is the false-signal filter.
  3. Fundamentals overlay: a 5-factor score (adapted from the ichimoku-screener
     fundamentals module) can veto — bullish signal on fundamentally weak names
     and bearish signals on fundamentally strong names both cap at HOLD.

Fundamentals are fetched ONLY for tickers that alerted today (yfinance .info
is slow/flaky per ticker), and every failure degrades gracefully to a
technicals-only verdict.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

STRONG = 2    # score >= STRONG  -> fundamentally strong
WEAK = -2     # score <= WEAK    -> fundamentally weak


def score_info(info: dict) -> dict:
    """5-factor fundamental score from a yfinance .info dict. Pure/testable.

    Each factor contributes +1 / 0 / -1; missing data contributes 0.
    """
    factors: dict[str, int] = {}

    rec = info.get("recommendationMean")
    if rec is not None:
        factors["analyst"] = 1 if rec <= 2.2 else (-1 if rec >= 3.5 else 0)

    fpe = info.get("forwardPE")
    if fpe is not None and fpe > 0:
        factors["valuation"] = 1 if fpe <= 15 else (-1 if fpe >= 40 else 0)
    elif fpe is not None:  # negative forward P/E = expected losses
        factors["valuation"] = -1

    fcf, mcap = info.get("freeCashflow"), info.get("marketCap")
    if fcf is not None and mcap:
        fcf_yield = fcf / mcap
        factors["fcf_yield"] = 1 if fcf_yield >= 0.04 else (-1 if fcf_yield < 0 else 0)

    target, price = info.get("targetMeanPrice"), info.get("currentPrice")
    if target and price:
        upside = target / price - 1
        factors["target_upside"] = 1 if upside >= 0.15 else (-1 if upside <= -0.05 else 0)

    growth = info.get("earningsGrowth")
    if growth is not None:
        factors["earnings_growth"] = 1 if growth >= 0.10 else (-1 if growth < 0 else 0)

    score = sum(factors.values())
    rating = "strong" if score >= STRONG else ("weak" if score <= WEAK else "neutral")
    return {"score": score, "rating": rating, "factors": factors}


def fetch_fundamentals(ticker: str) -> dict | None:
    """Fetch + score fundamentals; None when Yahoo has nothing usable."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        logger.warning("fundamentals fetch failed for %s (%s)", ticker, exc)
        return None
    if not info.get("marketCap") and not info.get("recommendationMean"):
        return None  # index/unknown symbol — nothing to score
    return score_info(info)


def verdict(direction: str, macd_confirms: bool, score: int | None) -> tuple[str, str]:
    """Combine the three layers into (verdict, reason)."""
    s = 0 if score is None else score
    fund_note = "" if score is not None else " (fundamentals unavailable)"

    if direction == "bullish":
        if not macd_confirms:
            return "hold", "MACD momentum does not confirm — possible false break"
        if s <= WEAK:
            return "hold", "Bullish signal confirmed, but fundamentals are weak"
        if s >= STRONG:
            return "buy", "Bullish signal, MACD confirms, strong fundamentals" + fund_note
        return "buy", "Bullish signal confirmed by MACD" + fund_note

    if not macd_confirms:
        return "hold", "MACD momentum does not confirm — possible false breakdown"
    if s >= STRONG:
        return "hold", "Bearish signal on a fundamentally strong name — trim rather than exit"
    if s <= WEAK:
        return "sell", "Bearish signal, MACD confirms, weak fundamentals" + fund_note
    return "sell", "Bearish signal confirmed by MACD" + fund_note
