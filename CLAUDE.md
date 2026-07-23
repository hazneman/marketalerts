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
   + RRG state (leading/improving/weakening/lagging) → `sectors.json`. Each
   sector also carries `top`: its 10 biggest members (cap = shares from the
   `sector_membership.json` cache × the close already in memory) with compact
   fundamentals fetched for just those ~110 tickers (threaded, degrades
   per-ticker). Rebuilt only from a FULL price set (≥80% membership coverage);
   partial scans / standalone runs carry the previous lists forward.
5. **Verdict per alert** (`recommend.py`): buy/hold/sell =
   signal direction × **MACD gate** (momentum disagrees → cap HOLD, the
   false-signal filter) × (5-factor fundamentals score + US-only sector factor
   leading +1 / lagging −1). Special case: `rsi_extended` is **hard-capped at
   HOLD** ("trim, not exit") — per docs/EXITS.md, exiting uptrend strength
   outright loses. Fundamentals (yfinance `.info`) fetched **only for alerted
   tickers**; every failure degrades to technicals-only. The scored gate stays
   the audited 5 factors, but each fundamentals block also carries **display-only**
   enrichment (`recommend.py`: `profile_metrics` — ROE/margins/leverage/growth/
   valuation-breadth/dividend; `coverage` present-of-5; `flags` value-trap /
   high-leverage / earnings-not-cash-backed; `summary` one-line synthesis). These
   feed the Buys review UI and **never touch `score`/`verdict`** — richer scoring
   is a separate, backtest-gated track (Lane B), per the display-vs-verdict rule.
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
9. Track record (`track_record.py` → `track_record.json`): the ONE
   **accumulating** output — reads its own previous file and ADDS to it (all
   others recompute). Ingests every `verdict=='buy'` alert from `history.json`
   (so first-run backfill = last 30 days, steady-state daily adds, and
   benchmark-outage self-heal are one path), captures entry_date + entry-day
   close, and updates each entry's return vs its **own-market index** (US→SPY,
   DE→`^GDAXI`, BIST→`XU100.IS` — same currency as the stock, so excess has no
   FX distortion). success = beat the benchmark. id = `ticker|rule|entry_date`
   (re-fires stay distinct). Entries mature at 180 days then freeze. Rides the
   scan like sectors/forex (failure-isolated; raises on benchmark outage →
   previous file kept). Byte-stability hinges on `days_held`/benchmark closes
   deriving from the scan **bar_date**, never `now()` — and the benchmark's
   "last close" is anchored to each market's bar_date (nearest-prior), so it's
   immune to an intraday-forming bar when backfilling. Entries also freeze the
   analyst mean target from their alert day (`target_mean`) and flag
   `target_reached`.
10. Position health (`health.py` → `health.json`): daily technical STATE for
   every scanned ticker (vs SMA200/SMA50, RSI, MACD, 20d trend, drawdown from
   the 252d peak, sector state) PLUS `recent_warnings` — bearish/RSI-trim
   alerts from the last 30 days, so a warning you missed on Tuesday is still
   visible Friday. Alerts are events; this is the state between them. Powers
   the Portfolio Health column. **Display-only and deliberately NOT an exit
   rule** — docs/EXITS.md found stop-loss and SMA-exit rules underperformed
   buy-and-hold; only RSI>75 trim helped, and it's flagged as such.
11. Alert archive (`archive.py` → `archive/alerts.jsonl`, repo root — NOT
   served): every alert ever fired with full entry context, one JSON line per
   event, forever (history.json rolls off at 30 days). Same history-ingestion
   pattern as track_record (backfill/daily/self-heal in one path); the OLDEST
   occurrence of a re-scanned event wins (context closest to entry day);
   byte-stable. Feeds the verifier lab.

## Frontend (frontend/src/) — 6 tabs

- **Stocks** — alert categories with market filter (US/DE/BIST badges),
  per-market bar-date chips, nearest-daily-Fib + volume columns, verdict badges.
- **Buys** — stocks already in the portfolio are grouped into a collapsed
  "Already held" section (fresh opportunities only in the main list); ↩
  re-entry tags on signals that re-fired within 14d. BUY verdicts as a
  **collapsed ranked list** sorted by
  `qualityScore()` (BuysPage.tsx): display-only confluence score — base 3;
  fundamentals strong +2/neutral +1; sector leading +1.5/improving +0.5/
  weakening −0.25/lagging −0.5 (US-only → non-US max 8.5/10); volume ≥2× +1.5/
  ≥1.25× +1/≥1× +0.5; analyst kicker strong_buy +0.5/buy +0.25 (rating already
  counts analyst factors — don't double-count); 200wk rule +1/golden +0.5; Fib
  support +0.5. Grades: Strong+ ≥7.5 / Strong ≥6 / Good ≥5 / Fair. Expand a row
  for fundamentals table, analyst view (consensus, target-range bar, recent
  rating changes), sector row, Fib ladders, volume. "+ portfolio" quick-add.
- **Sectors** — rotation leaderboard + returns heatmap (SectorsPage); each row
  expands to the sector's 10 biggest companies with fundamentals (cap, 1d%,
  fwd P/E, div yield, rev growth, margin, consensus, target upside, rating).
- **Track record** — scoreboard of every BUY alert's forward return vs its own
  market index (`TrackRecordPage`, `useTrackRecord`, from `track_record.json`):
  aggregate hit-rate/excess Chips + a sortable, filterable (category/result)
  table (entry, current, return, bench, excess, held, ✓ beat / ✗ lag).
  Honesty rules: entries held <2d show **pending** and are excluded from the
  headline chips; ↩ re-entry = same ticker+rule re-fired within 14d; 🎯 =
  analyst mean target (frozen at entry) reached.
- **Forex** — rates/outlook table, pairs board, pair signals.
- **Portfolio** — trade backlog in **browser localStorage only** (key
  `market-alerts-portfolio-v1`; export/import JSON backup). Open positions
  valued from `prices.json`; **"↻ Update prices"** fetches live quotes via the
  Netlify function `frontend/netlify/functions/quotes.js` (Yahoo v8 chart
  proxy — the stack's only serverless piece; graceful fallback in local dev).
  Sell flow → closed-trades log with historic P&L (win rate, avg win/loss,
  best/worst, cumulative realized-P&L sparkline). Buy-card adds capture the
  analyst mean target (`Position.target_mean`/`target_as_of`) → Target column
  with distance-to-target + 🎯 when reached; a "⚠ Signals on your holdings"
  strip surfaces today's bearish/RSI-trim alerts on held tickers. A **Health**
  column (`lib/health.ts` `assessHealth` + `health.json`) grades each holding
  Strong/OK/Caution/Weak from trend, momentum, drawdown, sector and the 30-day
  warning memory; click it for the plain-English reasons. Caution only, never
  an exit instruction.

Shared conventions: `lib/tradingview.ts` maps `.IS→BIST:` / `.DE→XETR:`;
`tnum` class for tabular numerals; hooks in `hooks/useAlerts.ts`; types in
`types.ts`.

**Design system — "Pro Terminal" (dark + light):** Bloomberg-style: sharp
edges, monospace numerics (JetBrains Mono via `.tnum`/`.nums`), amber accent,
green/red signals, dense tables. Every color is a **CSS-variable token** defined
in `index.css` under `:root` (light "paper") + `.dark` (black terminal) and
surfaced to Tailwind as semantic names via `rgb(var(--x) / <alpha>)`
(`tailwind.config.js`) — so components use `bg-raised`/`text-ink`/`text-up`/
`text-down`/`text-accent`/`ring-hair` etc. and **never `dark:` variants**; the
`.dark` class on `<html>` swaps everything. Tokens: surfaces
`base/raised/overlay/inset`, lines `hair/hair-strong`, text
`ink/ink-2/muted/faint`, signals `accent`(amber/ochre)`/up/down/info/de`. Theme
persists in `localStorage['ma-theme']`; `useTheme.ts` + a FOUC guard in
`index.html` resolve it before paint. **Do NOT rename tokens to Tailwind palette
names** (amber/emerald/…) — they're deliberately non-colliding. Shared UI in
`lib/ui.ts` (class consts + `badgeRing`/`badgeFlat` tone maps, `Tone` type) and
`components/ui/` (`Badge`, `Chip`, `Tabs`, `SectionHeading`, `ThemeToggle`).
Badge colors are a `Tone` (`up/down/accent/info/de/neutral`), never a per-file
class-string map: the cross-cutting ones (`SECTOR_STATE`, `CONSENSUS_LABELS`,
`MARKET_TONES`) live in `types.ts`; page-local ones (verdict, forex
call/alignment, rating) are tiny `Record<…, Tone>` maps beside their use — all
resolved through `badgeRing`/`badgeFlat`. Sharp radius + mono are global config
levers (`borderRadius` override, `.tnum` redefinition). The 4 hand-rolled viz
primitives (sector HeatCell, analyst target-range bar, Fib ladder, P&L
sparkline) read up/down tokens so they theme; SVG strokes use Tailwind
`stroke-*` utilities (`var()` resolves in the CSS `stroke` property, not SVG
presentation attributes).

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

**Verifier lab** (`scanner/verifier_lab.py` → `docs/VERIFIERS.md`): candidate
BUY filters are measured counterfactually against the live track record —
NOTHING is blocked in production. A gate graduates only on a favorable live
exchange rate over months PLUS two-window backtest validation. First finding
(Jul 2026): the "extension" gate looked great over one live week and was then
REFUTED by a 2y event study (710 crosses, no edge) — patterns flip; trust the
process, not a week. Second finding (Jul 2026): the **re-fire gate** (same
ticker+rule within 14d — whipsaw) had the best live exchange rate (13 bad/6
good) and was then REFUTED by its two-window event study
(`verifier_lab.py --refire-study`, needs Yahoo — run locally, not in
sandboxes): re-fires performed the same or slightly BETTER than first crosses
in both windows (recent: −0.35pp vs −0.53pp; 2016-21: +0.27pp vs +0.08pp).
↩ stays a display tag. Two gates in, the lab's track record is 2 refutations —
do not promote a gate on live data alone.

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
- **`track_record.json` accumulates** — it merges onto its own previous content
  and never drops entries, so a bad/partial-scan commit pollutes it permanently
  (a wrong entry stays until manually pruned). Regenerate cleanly by DELETING it
  first (`rm frontend/public/data/track_record.json`) then a FULL scan (or
  `python scanner/track_record.py`, which backfills from the committed
  `history.json`/`prices.json`). Also: only run/commit it from a scan whose bars
  are FINAL (the daily Action runs 22:30 UTC post-close) — an intraday run
  captures live, still-moving closes.
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
- `sector_membership.json` (ticker → GICS sector, name, shares outstanding) is
  a **cache** — refresh occasionally via `dev.sh` option 5 /
  `build_membership.py` (~5 min, 517 .info calls); index membership and share
  counts drift slowly, so quarterly is plenty.
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
