"""US equity OHLCV fetching via yfinance.

Trimmed from the ichimoku-screener fetcher: US-only, daily bars. Returns
normalized DataFrames indexed by timestamp with columns
[open, high, low, close, volume] ordered oldest -> newest.

IMPORTANT: auto_adjust=False everywhere. Yahoo's raw Close is split-adjusted
but not dividend-adjusted — the same series TradingView shows on daily charts,
so SMAs computed here match TradingView.
"""

from __future__ import annotations

import logging
import time

import pandas as pd

logger = logging.getLogger(__name__)

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df[_OHLCV_COLS].copy()
    df = df.dropna(subset=["close"]).sort_index()
    return df


def fetch_us(symbol: str, period: str = "2y", interval: str = "1d",
             retries: int = 3) -> pd.DataFrame:
    """Fetch daily candles for one symbol. Yahoo's endpoint is flaky and
    intermittently returns empty/garbage, so we retry with backoff."""
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            raw = yf.download(
                symbol, period=period, interval=interval,
                auto_adjust=False, progress=False,
            )
        except Exception as exc:  # network / JSON decode hiccups
            last_err = exc
            raw = pd.DataFrame()

        if raw is not None and not raw.empty:
            # yfinance may use a (field, ticker) MultiIndex for a single symbol.
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw = raw.rename(columns=str.lower)
            return _normalize(raw)

        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))  # linear backoff

    logger.warning("yfinance returned no data for %s after %d tries (%s)",
                   symbol, retries, last_err)
    return pd.DataFrame(columns=_OHLCV_COLS)


def iter_us_chunks(symbols: list[str], period: str = "2y", interval: str = "1d",
                   chunk_size: int = 80, throttle: float = 1.0):
    """Yield {symbol: normalized OHLCV} one batch at a time.

    Symbols Yahoo can't serve come back as empty frames. Throttling between
    chunks avoids rate limits.
    """
    import yfinance as yf

    empty = pd.DataFrame(columns=_OHLCV_COLS)

    for start in range(0, len(symbols), chunk_size):
        chunk = symbols[start:start + chunk_size]
        try:
            raw = yf.download(
                chunk, period=period, interval=interval, auto_adjust=False,
                progress=False, group_by="ticker", threads=True,
            )
        except Exception as exc:
            logger.warning("batch download failed for chunk %d (%s)", start, exc)
            yield {sym: empty for sym in chunk}
            continue

        multi = isinstance(raw.columns, pd.MultiIndex)
        out: dict[str, pd.DataFrame] = {}
        for sym in chunk:
            try:
                sub = raw[sym] if multi else raw
            except KeyError:
                out[sym] = empty
                continue
            sub = sub.rename(columns=str.lower)
            if "close" not in sub.columns or sub["close"].dropna().empty:
                out[sym] = empty
            else:
                out[sym] = _normalize(sub)
        yield out

        if start + chunk_size < len(symbols):
            time.sleep(throttle)
