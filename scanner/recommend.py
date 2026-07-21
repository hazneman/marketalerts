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


def profile_metrics(info: dict) -> dict[str, float]:
    """Display-only company metrics — profitability, balance sheet, growth,
    valuation breadth, income. These make the review richer but DELIBERATELY do
    NOT feed the verdict: the gate stays the audited 5-factor score_info model
    (repo discipline: verdict factors need backtest validation; display does not).
    Only keys with usable data are returned.
    """
    m: dict[str, float] = {}

    def as_pct(key: str, dst: str, digits: int = 1) -> None:
        v = info.get(key)
        if isinstance(v, (int, float)):
            m[dst] = round(v * 100, digits)

    as_pct("returnOnEquity", "roe")
    as_pct("grossMargins", "gross_margin")
    as_pct("operatingMargins", "op_margin")
    as_pct("profitMargins", "net_margin")
    as_pct("revenueGrowth", "rev_growth")
    as_pct("payoutRatio", "payout")

    de = info.get("debtToEquity")
    if isinstance(de, (int, float)) and de >= 0:
        m["debt_to_equity"] = round(de / 100, 2)  # Yahoo reports it as a percent

    debt, cash, ebitda = info.get("totalDebt"), info.get("totalCash"), info.get("ebitda")
    if isinstance(debt, (int, float)) and isinstance(ebitda, (int, float)) and ebitda > 0:
        m["net_debt_to_ebitda"] = round((debt - (cash or 0)) / ebitda, 2)

    peg = info.get("trailingPegRatio") or info.get("pegRatio")
    if isinstance(peg, (int, float)) and peg > 0:
        m["peg"] = round(peg, 2)

    ev_ebitda = info.get("enterpriseToEbitda")
    if isinstance(ev_ebitda, (int, float)) and ev_ebitda > 0:
        m["ev_ebitda"] = round(ev_ebitda, 1)

    fcf, mcap = info.get("freeCashflow"), info.get("marketCap")
    if isinstance(fcf, (int, float)) and fcf > 0 and mcap:
        m["p_fcf"] = round(mcap / fcf, 1)

    # earnings quality: is reported profit backed by cash?
    ni = info.get("netIncomeToCommon")
    if isinstance(fcf, (int, float)) and isinstance(ni, (int, float)) and ni > 0:
        m["fcf_to_net_income"] = round(fcf / ni, 2)

    # dividend yield from the $ rate to dodge yfinance's fraction/percent ambiguity
    rate, price = info.get("dividendRate"), info.get("currentPrice")
    if isinstance(rate, (int, float)) and rate > 0 and price:
        m["div_yield"] = round(rate / price * 100, 2)

    cr = info.get("currentRatio")
    if isinstance(cr, (int, float)) and cr > 0:
        m["current_ratio"] = round(cr, 2)

    return m


def fundamental_flags(factors: dict, profile: dict) -> list[str]:
    """Risk/quality caveats surfaced in the review (display-only)."""
    flags: list[str] = []
    nde = profile.get("net_debt_to_ebitda")
    high_lev = (nde is not None and nde > 4) or profile.get("debt_to_equity", 0) > 2
    if high_lev:
        flags.append("high_leverage")
    # cheap on P/E but a shaky balance sheet or burning cash = classic value trap
    if factors.get("valuation", 0) == 1 and (high_lev or factors.get("fcf_yield", 0) == -1):
        flags.append("value_trap")
    f2ni = profile.get("fcf_to_net_income")
    if f2ni is not None and f2ni < 0.6:
        flags.append("earnings_not_cash_backed")
    return flags


def fundamental_summary(metrics: dict, profile: dict) -> str:
    """One-line plain-English synthesis of the fundamental picture. Deterministic
    (same inputs -> same string, so it stays byte-stable); clauses are dropped
    when their data is missing."""
    parts: list[str] = []

    op, roe = profile.get("op_margin"), profile.get("roe")
    if op is not None:
        label = ("highly profitable" if op >= 20 else "profitable" if op >= 8
                 else "thin margins" if op > 0 else "unprofitable")
        extra = f", ROE {roe:.0f}%" if roe is not None else ""
        parts.append(f"{label} (op margin {op:.0f}%{extra})")
    elif roe is not None:
        parts.append(f"ROE {roe:.0f}%")

    nde = profile.get("net_debt_to_ebitda")
    de = profile.get("debt_to_equity")
    if nde is not None:
        lev = ("net cash" if nde < 0 else "low leverage" if nde <= 1
               else "moderate leverage" if nde <= 3 else "high leverage")
        parts.append(lev if nde < 0 else f"{lev} ({nde:.1f}× net debt/EBITDA)")
    elif de is not None:
        lev = "low" if de <= 0.5 else "moderate" if de <= 1.5 else "high"
        parts.append(f"{lev} leverage (D/E {de:.1f}×)")

    pe = metrics.get("forward_pe")
    if pe is not None and pe > 0:
        val = ("cheap" if pe <= 15 else "fair" if pe <= 25
               else "premium" if pe <= 40 else "expensive")
        parts.append(f"{val} valuation (fwd P/E {pe:.0f})")

    rg = profile.get("rev_growth")
    eg = metrics.get("earnings_growth_pct")
    g, src = (rg, "rev") if rg is not None else (eg, "EPS")
    if g is not None:
        gl = ("strong growth" if g >= 15 else "growing" if g >= 5
              else "flat" if g >= 0 else "shrinking")
        parts.append(f"{gl} ({src} {g:+.0f}%)")

    return " · ".join(parts)


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
    # Display-only enrichment (does not touch score/verdict):
    profile = profile_metrics(info)
    result["profile"] = profile
    result["flags"] = fundamental_flags(result["factors"], profile)
    result["coverage"] = {"present": len(result["factors"]), "total": 5}
    result["summary"] = fundamental_summary(result["metrics"], profile)
    return result


def verdict(direction: str, macd_confirms: bool, score: int | None,
            sector_state: str | None = None,
            category: str | None = None) -> tuple[str, str]:
    """Combine signal x MACD x (fundamentals + sector) into (verdict, reason)."""
    base = 0 if score is None else score
    eff = base + sector_factor(sector_state)  # combined tailwind/headwind
    fund_note = "" if score is not None else " (fundamentals unavailable)"
    sec_note = (", sector leading" if sector_state == "leading"
                else ", sector lagging" if sector_state == "lagging" else "")

    # RSI>75 fires on stocks in UPTRENDS as a take-profit alert; backtests
    # (docs/EXITS.md) showed exiting uptrend strength outright loses — so this
    # category never escalates to SELL, whatever MACD/fundamentals say.
    if category == "rsi_extended":
        return "hold", "Overbought in an uptrend — take-profit/trim signal, not an exit"

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
