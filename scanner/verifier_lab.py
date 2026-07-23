"""Verifier lab — counterfactual gate analysis over the alert archive.

For every archived BUY alert, computes which CANDIDATE GATES would have blocked
it (nothing is ever actually blocked — this is measurement), joins the live
outcomes from track_record.json, and reports each gate's exchange rate:
how many bad alerts it catches per good alert it would have killed.

Gates only graduate into the real verdict after (a) a favorable live exchange
rate once enough entries have matured AND (b) two-window backtest validation —
per the discipline in docs/ ("no timing model beat buy-and-hold; validate
out-of-sample before shipping").

Usage:
  python scanner/verifier_lab.py            # gate report from live track record
  python scanner/verifier_lab.py --study    # + 2y historical extension event study
  python scanner/verifier_lab.py --write    # also refresh docs/VERIFIERS.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recommend import weak_balance_sheet  # noqa: E402  (needs sys.path above)

SCANNER_DIR = Path(__file__).resolve().parent
ROOT = SCANNER_DIR.parent
ARCHIVE_PATH = ROOT / "archive" / "alerts.jsonl"
TRACK_PATH = ROOT / "frontend" / "public" / "data" / "track_record.json"
DOC_PATH = ROOT / "docs" / "VERIFIERS.md"

EXT_THRESHOLD = 2.5      # % above SMA200 at entry = "chased/extended"
RESIST_THRESHOLD = -2.0  # nearest daily Fib >2% overhead = resistance close above
REFIRE_DAYS = 14         # same ticker+rule fired within this window = re-entry
SEASONED_DAYS = 2        # outcomes younger than this are noise, not evidence


def load_archive(path: Path = ARCHIVE_PATH) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def gates_for(a: dict, prior: dict[tuple[str, str], list[str]]) -> dict[str, bool]:
    """Candidate gates, all computable from archived entry context alone."""
    s200 = (a.get("values") or {}).get("sma200")
    ext = (a["close"] / s200 - 1) * 100 if s200 else 0.0
    fibd = ((((a.get("fib") or {}).get("daily") or {}).get("nearest") or {}).get("dist_pct"))
    m = ((a.get("fundamentals") or {}).get("metrics")) or {}
    prof = ((a.get("fundamentals") or {}).get("profile")) or {}
    sector_name = (a.get("fundamentals") or {}).get("sector")
    entry = dt.date.fromisoformat(a["date"])
    refire = any(
        0 < (entry - dt.date.fromisoformat(d)).days <= REFIRE_DAYS
        for d in prior.get((a["ticker"], a["rule"]), [])
    )
    extended = ext > EXT_THRESHOLD
    resistance = fibd is not None and fibd < RESIST_THRESHOLD
    return {
        "extended": extended,
        "resistance": resistance,
        "extended_and_resistance": extended and resistance,
        "lagging_sector": ((a.get("sector") or {}).get("state")) == "lagging",
        "neg_earnings_growth": (m.get("earnings_growth_pct") or 0) < 0,
        "weak_balance_sheet": weak_balance_sheet(prof, sector_name),
        "refire": refire,
    }


GATE_LABELS = {
    "extended": f"Entry >{EXT_THRESHOLD}% above SMA200 (chased)",
    "resistance": "Fib resistance <2% overhead",
    "extended_and_resistance": "Extended AND resistance overhead",
    "lagging_sector": "Sector lagging at entry",
    "neg_earnings_growth": "Earnings growth negative",
    "weak_balance_sheet": "Weak balance sheet (lev/liquidity, ex fin/REIT/util)",
    "refire": f"Re-fire within {REFIRE_DAYS}d (whipsaw)",
}


def prior_dates(alerts: list[dict]) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    for a in alerts:
        out.setdefault((a["ticker"], a["rule"]), []).append(a["date"])
    return out


def build_report() -> dict:
    alerts = load_archive()
    track = json.loads(TRACK_PATH.read_text())
    prior = prior_dates(alerts)
    by_id = {a["id"]: a for a in alerts}

    rows = []
    for e in track["entries"]:
        a = by_id.get(e["id"])
        if a is None or e["days_held"] < SEASONED_DAYS or e["excess_pct"] is None:
            continue
        rows.append({"entry": e, "gates": gates_for(a, prior)})

    gates_out = []
    for g, label in GATE_LABELS.items():
        blocked = [r["entry"] for r in rows if r["gates"][g]]
        passed = [r["entry"] for r in rows if not r["gates"][g]]
        bb = sum(1 for e in blocked if e["excess_pct"] < 0)
        bg = sum(1 for e in blocked if e["excess_pct"] > 0)
        gates_out.append({
            "gate": g, "label": label,
            "blocked_bad": bb, "blocked_good": bg, "blocked_n": len(blocked),
            "blocked_avg_excess": round(mean([e["excess_pct"] for e in blocked]), 2) if blocked else None,
            "passed_avg_excess": round(mean([e["excess_pct"] for e in passed]), 2) if passed else None,
        })
    losers = sum(1 for r in rows if r["entry"]["excess_pct"] < 0)
    return {"bar_date": track["bar_date"], "seasoned_n": len(rows),
            "losers_n": losers, "gates": gates_out}


def cross_events(close, sma_n: int = 200, refire_days: int = REFIRE_DAYS,
                 min_bars: int | None = None) -> list[tuple[int, bool]]:
    """All bull crosses of `close` over its `sma_n` SMA, as (bar index, is_refire).
    A cross is a re-fire when a prior bull cross happened within the previous
    `refire_days` CALENDAR days — the same definition the live ↩ tag and the
    lab's refire gate use. Pure/testable; `min_bars` defaults to sma_n+1."""
    from indicators import sma

    start = (min_bars if min_bars is not None else sma_n + 1)
    s = sma(close, sma_n)
    above = close > s
    events: list[tuple[int, bool]] = []
    last_cross_date = None
    for i in range(start, len(close)):
        if bool(above.iloc[i]) and not bool(above.iloc[i - 1]):
            d = close.index[i].date()
            refire = (last_cross_date is not None
                      and 0 < (d - last_cross_date).days <= refire_days)
            events.append((i, refire))
            last_cross_date = d
    return events


def _cohort(v: list[float]) -> dict:
    return {"n": len(v), "avg_excess": round(mean(v), 2) if v else None,
            "median_excess": round(median(v), 2) if v else None,
            "hit_rate": round(100 * sum(1 for x in v if x > 0) / len(v)) if v else None}


def refire_study(sample: int = 150, forward: int = 20) -> dict:
    """TWO-WINDOW event study of the re-fire gate: forward excess (vs SPY) of
    SMA200 bull crosses that re-fired within REFIRE_DAYS vs first crosses.
    Windows: recent (last ~2y) and earlier (2016-2021) — the out-of-sample bar
    from SWEEP.md. One fetch (period=max), events split by date."""
    import pandas as pd

    from fetcher import fetch_us, iter_us_chunks

    universe = json.loads((SCANNER_DIR / "universe.json").read_text())["markets"]["us"][:sample]
    spy = fetch_us("SPY", period="max")
    spyc = spy["close"]
    spy_by_date = {ix.date(): i for i, ix in enumerate(spy.index)}

    today = dt.date.today()
    recent_lo = today - dt.timedelta(days=365 * 2)
    early_lo, early_hi = dt.date(2016, 1, 1), dt.date(2021, 12, 31)

    def fwd(series, i):
        if i + forward >= len(series):
            return None
        return (float(series.iloc[i + forward]) / float(series.iloc[i]) - 1) * 100

    win: dict[str, dict[str, list[float]]] = {
        "recent": {"refire": [], "first": []},
        "earlier": {"refire": [], "first": []},
    }
    for chunk in iter_us_chunks(universe, period="max"):
        for sym, df in chunk.items():
            if df.empty or len(df) < 210:
                continue
            c = df["close"]
            for i, refire in cross_events(c):
                d = df.index[i].date()
                w = ("recent" if d >= recent_lo
                     else "earlier" if early_lo <= d <= early_hi else None)
                if w is None:
                    continue
                si = spy_by_date.get(d)
                if si is None:
                    continue
                sf, ff = fwd(spyc, si), fwd(c, i)
                if sf is None or ff is None:
                    continue
                win[w]["refire" if refire else "first"].append(ff - sf)

    return {"sample_tickers": len(universe), "forward_days": forward,
            "refire_days": REFIRE_DAYS,
            "windows": {w: {k: _cohort(v) for k, v in cohorts.items()}
                        for w, cohorts in win.items()}}


def extension_study(sample: int = 150, forward: int = 20) -> dict:
    """Historical event study: every SMA200 bull cross in a universe sample over
    ~2y, split by extension at the cross close; forward return vs SPY. This is
    ONE window — preliminary evidence, not the two-window bar for shipping."""
    from fetcher import fetch_us, iter_us_chunks
    from indicators import sma

    universe = json.loads((SCANNER_DIR / "universe.json").read_text())["markets"]["us"][:sample]
    spy = fetch_us("SPY", period="2y")
    spyc = spy["close"]

    def fwd(series, i):
        if i + forward >= len(series):
            return None
        return (float(series.iloc[i + forward]) / float(series.iloc[i]) - 1) * 100

    spy_by_date = {ix.date(): i for i, ix in enumerate(spy.index)}
    ext_ev, base_ev = [], []
    for chunk in iter_us_chunks(universe, period="2y"):
        for sym, df in chunk.items():
            if df.empty or len(df) < 210:
                continue
            c = df["close"]
            s = sma(c, 200)
            above = (c > s)
            for i in range(201, len(c) - forward):
                if above.iloc[i] and not above.iloc[i - 1]:  # bull cross
                    ext = (float(c.iloc[i]) / float(s.iloc[i]) - 1) * 100
                    si = spy_by_date.get(df.index[i].date())
                    if si is None:
                        continue
                    sf = fwd(spyc, si)
                    ff = fwd(c, i)
                    if sf is None or ff is None:
                        continue
                    (ext_ev if ext > EXT_THRESHOLD else base_ev).append(ff - sf)
    def s(v):
        return {"n": len(v), "avg_excess": round(mean(v), 2) if v else None,
                "median_excess": round(median(v), 2) if v else None,
                "hit_rate": round(100 * sum(1 for x in v if x > 0) / len(v)) if v else None}
    return {"sample_tickers": len(universe), "forward_days": forward,
            "extended": s(ext_ev), "normal": s(base_ev)}


def render_markdown(rep: dict, study: dict | None, refire: dict | None = None) -> str:
    L = []
    L.append("# VERIFIERS — candidate gate lab\n")
    L.append("Counterfactual analysis of candidate BUY filters ('verifiers') against the live")
    L.append("track record. **Nothing is blocked in production** — this measures what each gate")
    L.append("*would have* done. Regenerate with:\n")
    L.append("```bash\nscanner/.venv/bin/python scanner/verifier_lab.py --study --write\n```\n")
    L.append(f"_Last refreshed from bar **{rep['bar_date']}** — {rep['seasoned_n']} seasoned "
             f"entries (≥{SEASONED_DAYS}d held), {rep['losers_n']} negative-excess._\n")
    L.append("## Live exchange rates\n")
    L.append("| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |")
    L.append("|---|---|---|---|---|")
    for g in rep["gates"]:
        L.append(f"| {g['label']} | {g['blocked_bad']} | {g['blocked_good']} | "
                 f"{g['blocked_avg_excess']}pp | {g['passed_avg_excess']}pp |")
    L.append("\nA gate earns promotion only if, over months, it blocks clearly negative excess")
    L.append("while the passed set stays positive — AND it survives two-window backtest")
    L.append("validation (see SWEEP.md for why single-window results flip).\n")
    if study:
        e, n = study["extended"], study["normal"]
        L.append(f"## Historical event study — extension gate ({study['sample_tickers']} US tickers, "
                 f"~2y, forward {study['forward_days']} trading days vs SPY)\n")
        L.append("| Cohort | Crosses | Avg excess | Median excess | Beat SPY |")
        L.append("|---|---|---|---|---|")
        L.append(f"| Extended (> {EXT_THRESHOLD}% above SMA200) | {e['n']} | {e['avg_excess']}pp | "
                 f"{e['median_excess']}pp | {e['hit_rate']}% |")
        L.append(f"| Normal (≤ {EXT_THRESHOLD}%) | {n['n']} | {n['avg_excess']}pp | "
                 f"{n['median_excess']}pp | {n['hit_rate']}% |")
        L.append("\n_One window only — preliminary. Promotion requires the full two-window bar._\n")
    if refire:
        L.append(f"## Two-window event study — re-fire gate ({refire['sample_tickers']} US tickers, "
                 f"forward {refire['forward_days']} trading days vs SPY)\n")
        L.append(f"A cross is a *re-fire* when the same signal fired within the prior "
                 f"{refire['refire_days']} calendar days (the live ↩ tag). This IS the "
                 f"two-window bar: both windows must agree before the gate can touch the verdict.\n")
        L.append("| Window | Cohort | Crosses | Avg excess | Median excess | Beat SPY |")
        L.append("|---|---|---|---|---|---|")
        for w in ("recent", "earlier"):
            for k, label in (("refire", "Re-fire"), ("first", "First cross")):
                c = refire["windows"][w][k]
                L.append(f"| {w} | {label} | {c['n']} | {c['avg_excess']}pp | "
                         f"{c['median_excess']}pp | {c['hit_rate']}% |")
        L.append("")
    L.append("## Caveats\n")
    L.append("- Live sample is tiny and young; patterns have already flipped week-to-week.")
    L.append("- Returns are split- but not dividend-adjusted; entries assume alert-day close.")
    L.append("- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).\n")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--study", action="store_true", help="run the 2y extension event study")
    p.add_argument("--refire-study", action="store_true",
                   help="run the TWO-WINDOW re-fire event study (needs Yahoo; ~2-4 min)")
    p.add_argument("--write", action="store_true", help="refresh docs/VERIFIERS.md")
    args = p.parse_args(argv)

    rep = build_report()
    print(f"bar {rep['bar_date']} · {rep['seasoned_n']} seasoned entries · {rep['losers_n']} losers")
    print(f"{'gate':<34}{'bad':>5}{'good':>6}{'blocked avg':>13}{'passed avg':>12}")
    for g in rep["gates"]:
        print(f"{g['label']:<34}{g['blocked_bad']:>5}{g['blocked_good']:>6}"
              f"{str(g['blocked_avg_excess']):>11}pp{str(g['passed_avg_excess']):>10}pp")

    study = None
    if args.study:
        print("\nrunning extension event study (~1 min)…")
        study = extension_study()
        e, n = study["extended"], study["normal"]
        print(f"extended: n={e['n']} avg {e['avg_excess']}pp beat {e['hit_rate']}% | "
              f"normal: n={n['n']} avg {n['avg_excess']}pp beat {n['hit_rate']}%")

    refire = None
    if args.refire_study:
        print("\nrunning two-window re-fire event study (~2-4 min)…")
        refire = refire_study()
        for w in ("recent", "earlier"):
            r, f = refire["windows"][w]["refire"], refire["windows"][w]["first"]
            print(f"{w:>8}: refire n={r['n']} avg {r['avg_excess']}pp beat {r['hit_rate']}% | "
                  f"first n={f['n']} avg {f['avg_excess']}pp beat {f['hit_rate']}%")

    if args.write:
        DOC_PATH.write_text(render_markdown(rep, study, refire))
        print(f"\nwrote {DOC_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
