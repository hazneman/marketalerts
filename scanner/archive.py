"""Permanent alert archive — every alert ever fired, with full entry context.

history.json rolls off after 30 days; this archive keeps one JSON line per
alert event (id = ticker|rule|date) FOREVER, including the heavy entry-time
context (fundamentals, sector state, volume, Fib, MACD, verdict) that the
verifier lab and future gate backtests need. It lives in archive/alerts.jsonl
at the repo root — versioned with the data commits but never shipped to the
site (Netlify publishes only frontend/dist).

Same unified-ingestion pattern as track_record.py: the source of truth is
history.json, so the first run backfills the whole 30-day window, daily runs
add the new day, an outage self-heals on the next healthy run, and re-runs
are idempotent. Records whose id is still inside the history window are
refreshed if their content changed (history is replace-on-rescan); records
that have aged out are preserved untouched. The file is rewritten only when
content actually changed, so holiday re-runs stay no-op commits.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCANNER_DIR = Path(__file__).resolve().parent
DEFAULT_ARCHIVE_PATH = SCANNER_DIR.parent / "archive" / "alerts.jsonl"
DEFAULT_HISTORY_PATH = SCANNER_DIR.parent / "frontend" / "public" / "data" / "history.json"


def alert_id(a: dict) -> str:
    return f"{a['ticker']}|{a['rule']}|{a['date']}"


def load_archive(path: Path) -> dict[str, dict]:
    """{id: record}. Tolerates a missing file (first run) and skips any
    corrupt line rather than losing the archive."""
    records: dict[str, dict] = {}
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                records[rec["id"]] = rec
            except (ValueError, KeyError):
                logger.warning("archive: skipping corrupt line: %.80s", line)
    except OSError:
        pass
    return records


def merge(existing: dict[str, dict], history: dict) -> tuple[dict[str, dict], int, int]:
    """Union history's alerts into the archive. Returns (merged, added, refreshed).

    The same event (id) can appear on several history days — a lagging market's
    bar is re-scanned the next day and fundamentals drift between fetches. The
    OLDEST occurrence wins: it is the context closest to the entry day, which is
    what the verifier lab must analyze. Adds unseen ids; refreshes an existing
    record only when that oldest version's content changed (replace-on-rescan);
    never drops ids that aged out of the history window.
    """
    wanted: dict[str, dict] = {}
    for day in sorted(history.get("days", []), key=lambda d: d.get("bar_date", "")):
        for a in day.get("alerts", []):
            rec = {"id": alert_id(a), **a}
            wanted.setdefault(rec["id"], rec)  # first (oldest) occurrence wins
    merged = dict(existing)
    added = refreshed = 0
    for _id, rec in wanted.items():
        prev = merged.get(_id)
        if prev is None:
            merged[_id] = rec
            added += 1
        elif prev != rec:
            merged[_id] = rec
            refreshed += 1
    return merged, added, refreshed


def _serialize(records: dict[str, dict]) -> str:
    # Deterministic order (date, category, ticker, rule) + sorted keys per
    # line → identical bytes for identical content, whatever the merge order.
    rows = sorted(records.values(),
                  key=lambda r: (r["date"], r.get("category", ""), r["ticker"], r["rule"]))
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def update(path: Path = DEFAULT_ARCHIVE_PATH,
           history: dict | None = None,
           history_path: Path = DEFAULT_HISTORY_PATH) -> dict:
    if history is None:
        try:
            history = json.loads(history_path.read_text())
        except (OSError, ValueError):
            history = {"days": []}
    existing = load_archive(path)
    merged, added, refreshed = merge(existing, history)
    text = _serialize(merged)
    path.parent.mkdir(parents=True, exist_ok=True)
    changed = True
    try:
        changed = path.read_text() != text
    except OSError:
        pass
    if changed:
        path.write_text(text)
    return {"total": len(merged), "added": added, "refreshed": refreshed, "changed": changed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    r = update()
    print(f"alerts.jsonl: {r['total']} alerts archived "
          f"(+{r['added']} new, {r['refreshed']} refreshed, "
          f"{'written' if r['changed'] else 'unchanged'})")
