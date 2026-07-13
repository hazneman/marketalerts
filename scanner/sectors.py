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

US sectors only — the SPDR ETFs are the standard, liquid way to read rotation.
Writes frontend/public/data/sectors.json (byte-stable when unchanged).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetcher import fetch_us
from indicators import sma

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
SCHEMA_VERSION = 1
BENCHMARK = "SPY"

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


def build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
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

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": max(bar_dates),
        "benchmark": {"symbol": BENCHMARK, "chg": spy_ret},
        "sectors": rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "sectors.json"
    try:
        prev = json.loads(path.read_text())
    except (OSError, ValueError):
        prev = None
    if prev is not None and {**prev, "generated_at": None} == {**data, "generated_at": None}:
        data["generated_at"] = prev["generated_at"]
    path.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n")
    return data


if __name__ == "__main__":
    d = build()
    print(f"sectors.json written: {len(d['sectors'])} sectors, bar_date={d['bar_date']}")
    for r in d["sectors"]:
        print(f"  {r['rank']:>2}. {r['symbol']:<5} {r['name']:<24} "
              f"score={r['rs_score']:+6.2f}  {r['state']}")
