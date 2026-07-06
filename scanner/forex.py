"""Forex snapshot: policy rates + currency trend vs USD + rule-based suggestion.

Policy rates come from the manually-maintained rates.json (central banks move
~8x/year; there is no reliable free API). FX prices come from Yahoo daily bars
for the XXXUSD=X pairs, so "above SMA200" always means "this currency is
strengthening against the dollar".

The suggestion is a transparent rule on two inputs, not advice:
  carry  = policy rate minus the USD rate
  trend  = pair above/below its 200-day SMA
Writes frontend/public/data/forex.json (byte-stable when nothing changed,
same idempotency contract as output.py).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alerts import RULES
from fetcher import fetch_us
from indicators import sma

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCANNER_DIR.parent / "frontend" / "public" / "data"
SCHEMA_VERSION = 1

# Major pairs scanned with the SAME alert rules as stocks (price x SMA200,
# golden/death cross, 200-week SMA, RSI>75). Yahoo symbol = pair + "=X".
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "USDTRY",
]


def pair_read(carry: float, above: bool) -> tuple[str, str]:
    """Combined reading of a pair's rate balance and 200-day trend.

    carry = base-currency rate minus quote-currency rate. Alignment of the two
    forces is the signal; conflict between them is the warning.
    """
    if carry >= 0.5 and above:
        return "aligned_bull", "Carry and trend agree — cleanest bullish setup"
    if carry <= -0.5 and not above:
        return "aligned_bear", "Negative carry and downtrend agree — cleanest bearish setup"
    if carry >= 0.5 and not above:
        return "conflict", "Positive carry but below SMA200 — carry is fighting the trend"
    if carry <= -0.5 and above:
        return "conflict", "Uptrend despite negative carry — momentum outrunning rates"
    trend = "up" if above else "down"
    return "trend_only", f"Flat rate balance — trend is the whole story ({trend})"


def suggestion(carry: float, above: bool | None) -> str:
    if above is None:
        return "No trend data"
    if carry >= 1.0:
        return ("Positive carry, strengthening — attractive" if above
                else "Positive carry but weakening — carry at risk")
    if carry <= -1.0:
        return ("Low yield but strengthening" if above
                else "Low yield and weakening — funding currency")
    return "Neutral carry, " + ("positive trend" if above else "negative trend")


def build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    cfg = json.loads((SCANNER_DIR / "rates.json").read_text())
    usd_rate = next(c["rate"] for c in cfg["currencies"] if c["code"] == "USD")

    currencies = []
    bar_dates = []
    for c in cfg["currencies"]:
        entry = {
            "code": c["code"], "country": c["country"], "bank": c["bank"],
            "rate": c["rate"],
            "change_bps": round((c["rate"] - c["prev_rate"]) * 100),
            "changed_on": c["changed_on"],
            "carry_vs_usd": round(c["rate"] - usd_rate, 2),
            "outlook": c.get("outlook"),
        }
        if c["code"] == "USD":
            entry.update({"vs_usd": None, "suggestion": "Benchmark currency"})
        else:
            df = fetch_us(f"{c['code']}USD=X", period="2y")
            if df.empty or len(df) < 210:
                entry.update({"vs_usd": None,
                              "suggestion": suggestion(entry["carry_vs_usd"], None)})
            else:
                close = df["close"]
                s200 = float(sma(close, 200).iloc[-1])
                px = float(close.iloc[-1])
                above = px > s200
                chg_1m = float(px / close.iloc[-22] - 1.0)
                bar_dates.append(df.index[-1].date().isoformat())
                entry["vs_usd"] = {
                    "price": round(px, 5), "sma200": round(s200, 5),
                    "above_sma200": above, "chg_1m_pct": round(chg_1m * 100, 2),
                }
                entry["suggestion"] = suggestion(entry["carry_vs_usd"], above)
        currencies.append(entry)

    rate_of = {c["code"]: c["rate"] for c in cfg["currencies"]}
    pairs = []
    pair_alerts = []
    for symbol in PAIRS:
        df = fetch_us(f"{symbol}=X", period="6y")  # 6y: enough for the 200-week rule
        if df.empty or len(df) < 210:
            continue
        close = df["close"]
        s200 = float(sma(close, 200).iloc[-1])
        px = float(close.iloc[-1])
        above = px > s200
        base, quote = symbol[:3], symbol[3:]
        carry = round(rate_of[base] - rate_of[quote], 2)
        alignment, comment = pair_read(carry, above)
        bar_dates.append(df.index[-1].date().isoformat())
        pairs.append({
            "symbol": symbol,
            "price": round(px, 5),
            "sma200": round(s200, 5),
            "above_sma200": above,
            "vs_sma200_pct": round((px / s200 - 1.0) * 100, 2),
            "chg_1m_pct": round((px / float(close.iloc[-22]) - 1.0) * 100, 2),
            "carry_pct": carry,
            "alignment": alignment,
            "comment": comment,
        })
        for rule in RULES:
            pair_alerts.extend(a.to_dict() for a in rule.evaluate(symbol, df))
    pair_alerts.sort(key=lambda a: (a["category"], a["ticker"]))

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bar_date": max(bar_dates) if bar_dates else None,
        "rates_as_of": cfg["as_of"],
        "outlook_as_of": cfg.get("outlook_as_of"),
        "usd_rate": usd_rate,
        "currencies": currencies,
        "pairs": pairs,
        "pair_alerts": pair_alerts,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "forex.json"
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
    print(f"forex.json written: {len(d['currencies'])} currencies, "
          f"bar_date={d['bar_date']}, rates_as_of={d['rates_as_of']}")
