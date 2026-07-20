"""Per-ticker technical health → frontend/public/data/health.json.

The Portfolio page needs to warn when a HELD stock is *deteriorating*, not just
on the day it crosses a line. Alerts are events (one bar); this is a daily
STATE snapshot for every scanned ticker: where price sits vs its SMAs, momentum,
recent trend, distance below its recent peak, and whether a bearish/trim alert
fired in the last 30 days (so a warning you missed on Tuesday is still visible
on Friday).

Deliberately DISPLAY-ONLY and deliberately not an exit signal: docs/EXITS.md
found that of six tested exit rules only the RSI>75 trim beat buy-and-hold in
both windows — stop-loss and SMA-exit rules underperformed simply holding. The
frontend grades these into caution levels; nothing here changes a verdict.

Rides the daily scan like sectors/forex (failure-isolated) and is byte-stable:
computed purely from the scan's own bars, so a holiday re-run rewrites identical
bytes and stays a no-op commit.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicators import macd, rsi, sma

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
SCHEMA_VERSION = 1
PEAK_LOOKBACK = 252    # ~1 year of bars for the drawdown reference high
TREND_LOOKBACK = 20    # short-term trend window (~1 month)
WARN_DAYS = 30         # remember bearish/trim alerts this many calendar days

# Alert categories that are a caution for someone HOLDING the stock.
WARN_CATEGORIES = {"rsi_extended"}


def _round(v, dp=2):
    return None if v is None else round(float(v), dp)


def ticker_health(df, sector_state: str | None = None) -> dict | None:
    """Technical state from a single ticker's OHLCV. Pure/testable."""
    if df is None or df.empty or len(df) < 60:
        return None
    c = df["close"]
    px = float(c.iloc[-1])
    out: dict = {"close": _round(px)}

    s200 = sma(c, 200)
    if len(c) >= 200 and not s200.isna().iloc[-1]:
        v = float(s200.iloc[-1])
        out["sma200"] = _round(v)
        out["vs_sma200_pct"] = _round((px / v - 1) * 100)
    s50 = sma(c, 50)
    if len(c) >= 50 and not s50.isna().iloc[-1]:
        v = float(s50.iloc[-1])
        out["sma50"] = _round(v)
        out["vs_sma50_pct"] = _round((px / v - 1) * 100)

    r = rsi(c)
    if not r.isna().iloc[-1]:
        out["rsi"] = _round(float(r.iloc[-1]), 1)

    line, sig = macd(c)
    if not (line.isna().iloc[-1] or sig.isna().iloc[-1]):
        out["macd_bullish"] = bool(line.iloc[-1] > sig.iloc[-1])

    # trend: % change over the last TREND_LOOKBACK bars
    if len(c) > TREND_LOOKBACK:
        out["chg_20d_pct"] = _round((px / float(c.iloc[-1 - TREND_LOOKBACK]) - 1) * 100)

    # drawdown from the highest close in the lookback window
    window = c.tail(PEAK_LOOKBACK)
    peak = float(window.max())
    if peak > 0:
        out["peak_252d"] = _round(peak)
        out["drawdown_pct"] = _round((px / peak - 1) * 100)

    if sector_state:
        out["sector_state"] = sector_state
    return out


def recent_warnings(history: dict, bar_date: str, days: int = WARN_DAYS) -> dict[str, list[dict]]:
    """{ticker: [{date, category, rule, direction}]} for bearish crosses and
    trim alerts within the window — so a warning isn't lost the next day."""
    cutoff = (dt.date.fromisoformat(bar_date) - dt.timedelta(days=days)).isoformat()
    out: dict[str, list[dict]] = {}
    for day in history.get("days", []):
        for a in day.get("alerts", []):
            if a.get("date", "") < cutoff:
                continue
            if a.get("direction") == "bearish" or a.get("category") in WARN_CATEGORIES:
                rec = {"date": a["date"], "category": a.get("category"),
                       "rule": a.get("rule"), "direction": a.get("direction")}
                lst = out.setdefault(a["ticker"], [])
                if rec not in lst:
                    lst.append(rec)
    for lst in out.values():
        lst.sort(key=lambda r: r["date"], reverse=True)
    return out


def build(output_dir: Path = DEFAULT_OUTPUT_DIR, frames: dict | None = None,
          bar_date: str | None = None, sector_states: dict | None = None,
          history: dict | None = None, now: dt.datetime | None = None) -> dict:
    frames = frames or {}
    sector_states = sector_states or {}
    if history is None:
        try:
            history = json.loads((output_dir / "history.json").read_text())
        except (OSError, ValueError):
            history = {"days": []}

    tickers: dict[str, dict] = {}
    for sym, df in frames.items():
        h = ticker_health(df, sector_states.get(sym))
        if h is not None:
            tickers[sym] = h

    warnings = recent_warnings(history, bar_date) if bar_date else {}
    for sym, warns in warnings.items():
        if sym in tickers:
            tickers[sym]["recent_warnings"] = warns

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": bar_date,
        "warn_days": WARN_DAYS,
        "tickers": dict(sorted(tickers.items())),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "health.json"
    try:
        prev = json.loads(path.read_text())
    except (OSError, ValueError):
        prev = None
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    path.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n")
    return data
