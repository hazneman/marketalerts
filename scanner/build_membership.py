"""Build scanner/sector_membership.json — the sector-constituent cache.

For every US-universe ticker, fetches yfinance .info once and stores the GICS
sector, company name, and shares outstanding. The daily scan combines shares
with the closes it already has in memory to rank each sector's members by
market cap (sectors.py) — so this slow ~517-ticker sweep runs only when the
cache is refreshed, never inside the daily Action.

Refresh occasionally (index membership and share counts drift slowly):
  scanner/.venv/bin/python scanner/build_membership.py   # or dev.sh option 5
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("membership")

SCANNER_DIR = Path(__file__).resolve().parent
OUTPUT = SCANNER_DIR / "sector_membership.json"
WORKERS = 6  # modest concurrency — stay friendly with Yahoo


def fetch_one(ticker: str) -> tuple[str, dict | None]:
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        logger.warning("%s: fetch failed (%s)", ticker, exc)
        return ticker, None
    sector, shares = info.get("sector"), info.get("sharesOutstanding")
    if not sector or not shares:
        logger.warning("%s: no sector/shares — skipped", ticker)
        return ticker, None
    return ticker, {
        "sector": sector,  # raw GICS name; mapped to SPDR in sectors.py
        "name": info.get("shortName") or ticker,
        "shares": int(shares),
    }


def main() -> int:
    with open(SCANNER_DIR / "universe.json") as fh:
        symbols = json.load(fh)["markets"]["us"]
    logger.info("fetching sector/shares for %d US tickers…", len(symbols))

    members: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, (sym, row) in enumerate(pool.map(fetch_one, symbols), 1):
            if row:
                members[sym] = row
            if i % 50 == 0:
                logger.info("  %d/%d", i, len(symbols))

    if len(members) < len(symbols) * 0.8:
        logger.error("only %d/%d resolved — Yahoo likely throttling, NOT "
                     "overwriting existing cache", len(members), len(symbols))
        return 1

    data = {
        "as_of": dt.date.today().isoformat(),
        "tickers": dict(sorted(members.items())),
    }
    OUTPUT.write_text(json.dumps(data, indent=1) + "\n")

    by_sector: dict[str, int] = {}
    for row in members.values():
        by_sector[row["sector"]] = by_sector.get(row["sector"], 0) + 1
    logger.info("wrote %s: %d tickers", OUTPUT.name, len(members))
    for sec, n in sorted(by_sector.items(), key=lambda kv: -kv[1]):
        logger.info("  %-24s %d", sec, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
