# CLAUDE.md — Market Alerts

Codebase guide for AI assistants. README.md is the user-facing overview; this
file is the working knowledge: architecture, conventions, gotchas, and the
reasoning behind decisions.

## What this is

A $0/month market-alerts platform: a Python scanner runs in a **GitHub Action**
each weekday (22:30 UTC, after all market closes), commits JSON results into
`frontend/public/data/`, and **Netlify** auto-builds a static React dashboard
from the push. No backend, no database. Live: https://market-alerts.netlify.app
(repo: hazneman/marketalerts).

- **Universe:** ~624 tickers in `scanner/universe.json` — `markets: {us, de, bist}`
  (S&P 500 + Nasdaq 100; DAX `.DE`; BIST `.IS`). Bar dates are tracked
  **per market** (different holidays/close times) — never mark a market stale
  because another market traded.
- **Owner:** solo dev (Hasan); validates all indicators against TradingView;
  prefers GUI over CLI (see `dev.sh` menu + `MarketAlerts.app`), git checkpoints,
  one feature at a time, opinion before big changes.

## Run it

```bash
./dev.sh                  # menu: quick scan / full scan / dashboard (:3100) / tests
scanner/.venv/bin/python -m pytest scanner/tests -q     # 70 tests
cd frontend && npx tsc --noEmit && npm run build         # type-check + build
scanner/.venv/bin/python scanner/scan.py --tickers META,SAP.DE --dry-run
```

## Architecture (scanner/)

Pipeline per daily run (`scan.py`):
1. Fetch 6y daily OHLCV for all markets in one pass (`fetcher.iter_us_chunks`,
   yfinance batches of 80, `auto_adjust=False` — **raw Close matches TradingView**).
2. Guards: >50% fetch failure → abort keeping old data; per-ticker skip for
   <201 bars (`insufficient_history`) or per-market stale bar.
3. `alerts/` **RULES registry** (pluggable — add a module + append to
   `alerts/__init__.py`; scan, verdict, forex pairs, and dashboard all pick it
   up automatically):
   - `PriceSma200Rule` — daily close × SMA200 cross
   - `GoldenCrossRule` — SMA50 × SMA200
   - `Sma200WeeklyRule` — 200-**week** SMA cross, completed weeks only (fires
     on Friday's scan; rare ≈ once/18mo per stock; highest-quality signal per backtests)
   - `RsiOverboughtRule` — RSI(14) crosses >75 while above SMA200 (take-profit alert)
4. Sector rotation (`sectors.py`): 11 SPDR ETFs vs SPY → relative-strength rank
   + RRG state (leading/improving/weakening/lagging) → `sectors.json`.
5. **Verdict per alert** (`recommend.py`): buy/hold/sell =
   signal direction × **MACD gate** (momentum disagrees → cap HOLD, the
   false-signal filter) × (5-factor fundamentals score + US-only sector factor
   leading +1 / lagging −1). Special case: `rsi_extended` is **hard-capped at
   HOLD** ("trim, not exit") — per docs/EXITS.md, exiting uptrend strength
   outright loses. Fundamentals (yfinance `.info`) fetched **only for alerted
   tickers**; every failure degrades to technicals-only.
6. Alert enrichment (display-only, all markets): `levels.fib_block` — Fibonacci
   retracement ladders, daily (252-day swing) + weekly (104-week swing),
   deterministic highest-high/lowest-low anchors; `indicators.volume_signal`
   (today ÷ 20-day avg).
7. Outputs (`output.py`, all byte-stable — generated_at preserved when content
   unchanged, so holiday runs are no-op commits): `latest.json`,
   `history.json` (30 days), `prices.json` (latest close + 1d% for ALL scanned
   tickers — feeds Portfolio valuation), `forex.json`, `sectors.json`.
8. Forex (`forex.py`): central-bank rates from **manually maintained**
   `rates.json` (no free API; bump `as_of` — displayed in UI; also holds
   Claude's discretionary 6-month outlook per currency) + 11 major pairs run
   through the same RULES + carry×trend combined reads.

## Frontend (frontend/src/) — 5 tabs

- **Stocks** — alert categories with market filter (US/DE/BIST badges),
  per-market bar-date chips, nearest-daily-Fib + volume columns, verdict badges.
- **Buys** — BUY verdicts as a **collapsed ranked list** sorted by
  `qualityScore()` (BuysPage.tsx): display-only confluence score — base 3;
  fundamentals strong +2/neutral +1; sector leading +1.5/improving +0.5/
  weakening −0.25/lagging −0.5 (US-only → non-US max 8.5/10); volume ≥2× +1.5/
  ≥1.25× +1/≥1× +0.5; analyst kicker strong_buy +0.5/buy +0.25 (rating already
  counts analyst factors — don't double-count); 200wk rule +1/golden +0.5; Fib
  support +0.5. Grades: Strong+ ≥7.5 / Strong ≥6 / Good ≥5 / Fair. Expand a row
  for fundamentals table, analyst view (consensus, target-range bar, recent
  rating changes), sector row, Fib ladders, volume. "+ portfolio" quick-add.
- **Sectors** — rotation leaderboard + returns heatmap (SectorsPage).
- **Forex** — rates/outlook table, pairs board, pair signals.
- **Portfolio** — trade backlog in **browser localStorage only** (key
  `market-alerts-portfolio-v1`; export/import JSON backup). Open positions
  valued from `prices.json`; **"↻ Update prices"** fetches live quotes via the
  Netlify function `frontend/netlify/functions/quotes.js` (Yahoo v8 chart
  proxy — the stack's only serverless piece; graceful fallback in local dev).
  Sell flow → closed-trades log with historic P&L (win rate, avg win/loss,
  best/worst, cumulative realized-P&L sparkline).

Shared conventions: `lib/tradingview.ts` maps `.IS→BIST:` / `.DE→XETR:`;
`tnum` class for tabular numerals; hooks in `hooks/useAlerts.ts`; types in
`types.ts`. Design system: dark, Inter font, `bg-white/[0.03] ring-1
ring-white/5` panels, segmented pill controls.

## The research library (docs/) — read before changing strategy logic

Every strategy idea was backtested before shipping; each doc is reproducible
with one command. Recurring finding: **no timing model beat buy-and-hold**;
signals are attention triggers, not autopilot. Only the RSI>75 take-profit
exit beat the baseline in BOTH test windows (→ became the rsi_extended alert).
Parameter tuning flipped out-of-sample (SWEEP.md) — resist re-tuning without
two-window validation. Tools: `backtest.py` (event study), `strategy_backtest.py`
(`--model trend|pullback|hybrid`, `--interval 1d|1wk`, `--validate` = recent +
2016-21 windows), `sweep.py`, `profile.py`, `exit_sweep.py`.

**Discipline:** new factors enter the VERDICT only after backtest evidence
(sector factor did; Fib/volume are display-only pending backtests). The Buys
quality score is presentational and may use unbacktested context — that's the
deliberate boundary.

## Workflow / operations

- `.github/workflows/scan.yml`: cron `30 22 * * 1-5` + workflow_dispatch;
  commit-if-changed with **rebase-retry push** (`git pull --rebase -X theirs`,
  5 attempts) — survives races with manual pushes. Triggered only on
  schedule/dispatch; GITHUB_TOKEN commits can't loop.
- **Data-commit discipline:** partial `--tickers`/`--limit` scans overwrite
  `frontend/public/data/*` — NEVER commit those; `git restore frontend/public/data`
  or run a FULL `scan.py` first. After any feature that adds fields to alerts,
  run a full scan and commit the data, else the live site serves stale JSON
  without the new fields.
- Manual pushes: commit, then `git pull --rebase -X theirs origin main`, push.

## Gotchas

- **yfinance pinned 1.4.1** — 0.2.x breaks on Yahoo's API. `.info` is
  slow/flaky per ticker; everything degrades gracefully.
- Yahoo's upgrades/downgrades feed is stale for some tickers (e.g. META);
  the 90-day filter hides stale entries automatically.
- European (DE/BIST) daily bars sometimes lag on Yahoo right after US close —
  the per-market bar logic keeps their last complete bar; self-heals next run.
- `rates.json` (policy rates + 6m outlooks) is **manual**; verify/update after
  central-bank meetings and bump `as_of`/`outlook_as_of`.
- GitHub disables cron workflows after 60 days of repo inactivity — daily data
  commits keep it alive; if alerts stop, check the Actions tab first.
- Prices are split-adjusted, NOT dividend-adjusted (TradingView parity);
  ex-dividend dates can cause rare spurious crosses on high-yield names.
- Fib anchors are fixed windows (252d/104w) — reproducible but one specific
  choice; document any change in README + BuysPage footer + this file.
- GOOG/GOOGL and NWS/NWSA fire near-duplicate alerts — expected, documented.

## Candidate next steps (not started)

- Backtest Fib-support proximity and volume-confirmation edges → fold winners
  into the verdict as ±1 factors (two-window validation, like sector).
- Consider paid data (EODHD ~$25/mo covers BIST+global fundamentals) ONLY if
  Yahoo gaps demonstrably hurt; Polygon is US-only — irrelevant for BIST.
- European sector rotation (STOXX 600 sectors) if wanted; SPDR set is US-only.
