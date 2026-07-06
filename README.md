# Market Alerts Dashboard

Daily alerts for financial opportunities in US stocks (S&P 500 + Nasdaq 100, ~517 tickers), shown on a static dashboard. **$0/month**: GitHub stores the code and the scan results; Netlify hosts the dashboard.

## Phase 1 alerts

| Category | Rules | Meaning |
|---|---|---|
| Price × SMA 200 | `PRICE_SMA200_BULL` / `PRICE_SMA200_BEAR` | Daily close crossed above/below its 200-day SMA |
| Golden / Death cross | `GOLDEN_CROSS` / `DEATH_CROSS` | SMA 50 crossed above/below SMA 200 |

## How it works

No backend, no database. On weekends/holidays the scan produces identical JSON → no commit → no deploy.

```mermaid
flowchart TD
    CRON["⏰ Cron schedule<br/>weekdays 22:30 UTC<br/>(always after US close)"]
    MANUAL["🖱️ Manual trigger<br/>Actions tab → Run workflow"]

    subgraph GHA["GitHub Action · daily-scan (ubuntu, ~1–2 min)"]
        SETUP["checkout → Python 3.12 + pip cache<br/>pip install yfinance 1.4.1, pandas"]
        RUN["python scanner/scan.py"]
        DIFF{"git diff:<br/>did the JSON change?"}
        COMMIT["commit 'scan: YYYY-MM-DD'<br/>and push to main"]
        NOOP["🛑 no commit, no deploy<br/>(weekend / holiday:<br/>same bar → identical bytes)"]
    end

    subgraph SCANNER["Scanner (Python)"]
        UNI["📋 universe.json<br/>517 tickers<br/>S&amp;P 500 + Nasdaq 100"]
        FETCH["fetcher.iter_us_chunks<br/>yfinance · batches of 80 · 2y daily bars<br/>auto_adjust=False (matches TradingView)<br/>retries + 1s throttle"]
        ABORT{"&gt;50% of universe<br/>failed?"}
        DEAD["🛑 abort, keep old data<br/>(Yahoo outage guard)"]
        GUARD{"per-ticker guards"}
        SKIPPED["metadata only:<br/>failures[] · empty data<br/>insufficient_history[] · &lt;201 bars<br/>stale · bar older than global bar_date"]
        RULES["🔌 RULES registry (pluggable)"]
        R1["PriceSma200Rule<br/>close crosses SMA 200<br/>→ PRICE_SMA200_BULL / _BEAR"]
        R2["GoldenCrossRule<br/>SMA 50 crosses SMA 200<br/>→ GOLDEN_CROSS / DEATH_CROSS"]
        OUT["output.py · deterministic JSON<br/>(sorted keys, timestamp preserved<br/>when content unchanged)"]
        LATEST["latest.json<br/>current bar's alerts + scan metadata"]
        HIST["history.json<br/>rolling 30 trading days"]
    end

    subgraph NETLIFY["Netlify"]
        HOOK["webhook fires on push to main"]
        BUILD["npm run build (tsc + vite)<br/>base=frontend · publish=dist"]
        CDN["🌐 market-alerts.netlify.app<br/>/data/* → Cache-Control: no-cache"]
    end

    subgraph DASH["Dashboard (React + TypeScript + Tailwind)"]
        HOOKS["useAlerts()<br/>fetch /data/latest.json + history.json<br/>(cache-busted)"]
        STATUS["ScanStatus<br/>last scan · bar date · 517/517<br/>amber warning on failures/stale bar"]
        FILTER["FilterBar<br/>ticker search · bull/bear toggle<br/>history day picker"]
        CATS["CategorySection ×2<br/>Price × SMA 200 · Golden/Death"]
        TABLE["AlertTable<br/>▲/▼ badge · close · SMA values<br/>· % vs SMA 200"]
        TV["↗ TradingView chart link<br/>per ticker"]
    end

    subgraph LOCAL["Local dev (Mac)"]
        APP["🖥️ MarketAlerts.app<br/>(double-click, in /Applications)"]
        DEVSH["dev.sh menu<br/>1) quick scan (10) + dashboard<br/>2) full scan (517) + dashboard<br/>3) dashboard only · vite :3100<br/>4) pytest · 17 tests"]
    end

    USER(("👤 Hasan"))

    CRON --> SETUP
    MANUAL --> SETUP
    SETUP --> RUN
    RUN --> UNI --> FETCH --> ABORT
    ABORT -- yes --> DEAD
    ABORT -- no --> GUARD
    GUARD -- "bad ticker" --> SKIPPED
    GUARD -- "ok: ≥201 bars, fresh bar" --> RULES
    RULES --> R1
    RULES --> R2
    R1 --> OUT
    R2 --> OUT
    SKIPPED --> OUT
    OUT --> LATEST
    OUT --> HIST
    LATEST --> DIFF
    HIST --> DIFF
    DIFF -- changed --> COMMIT
    DIFF -- identical --> NOOP
    COMMIT --> HOOK --> BUILD --> CDN
    CDN --> HOOKS
    HOOKS --> STATUS
    HOOKS --> FILTER
    FILTER --> CATS --> TABLE --> TV
    USER -- "double-click" --> APP --> DEVSH
    DEVSH -- "scans write into<br/>frontend/public/data/" --> LATEST
    USER -- "views daily" --> CDN
    TV -- "validate SMA values<br/>on TradingView" --> USER
```

## Run locally

Double-click **MarketAlerts.app**, or:

```
./dev.sh
```

Menu: `1)` quick scan (10 tickers) + dashboard · `2)` full scan (~5 min) · `3)` dashboard only · `4)` tests.

## Validating against TradingView

Every alert ticker in the dashboard links to its TradingView chart. To validate:
1. Open the ticker's daily chart, add indicator **SMA 200** (and **SMA 50** for golden/death), source = **close**.
2. Confirm yesterday's close was on the other side of the SMA and today's close on this side.
3. The SMA value should match `values.sma200` within a cent or two.

SMAs are computed on Yahoo's **raw Close** (`auto_adjust=False`): split-adjusted but *not* dividend-adjusted — the same data TradingView uses on daily charts, so values match. Tradeoff: high-dividend names can show an occasional spurious cross around ex-dividend dates; we accept this to stay TradingView-comparable.

## Forex page

The **Forex** tab shows major currencies (EUR, GBP, JPY, CHF, CAD, AUD, NZD, TRY)
with: central-bank policy rate, last change, carry vs USD, the currency's trend
against the dollar (XXXUSD pair vs its 200-day SMA, refreshed by the daily scan),
and a transparent rule-based suggestion (carry × trend). Informational only.

**Maintaining rates:** policy rates have no reliable free API, so they live in
[`scanner/rates.json`](scanner/rates.json) and are updated **manually** after
central-bank meetings (bump `as_of` too — it is displayed on the page so
staleness is always visible). FX prices update automatically.

## Known behaviors

- **GOOG/GOOGL** (and other dual-class shares) are both in the universe and will fire near-duplicate alerts on the same day. Expected.
- Tickers with **< 201 daily bars** (recent IPOs) are skipped and listed under `insufficient_history` in the scan status.
- **Persistent failures** usually mean a delisted/renamed ticker — prune `scanner/universe.json` quarterly.
- GitHub disables scheduled workflows after **60 days of repo inactivity**. Daily data commits keep it alive, but if alerts ever stop, check the repo's **Actions tab** first.
- The cron is fixed at 22:30 UTC → 5:30 pm ET in summer, 6:30 pm ET in winter. Always after the close.

## Adding a new alert type (Phase 2+)

1. Create `scanner/alerts/<your_rule>.py` with a class implementing `AlertRule` (see `alerts/base.py`).
2. Append an instance to `RULES` in `scanner/alerts/__init__.py`.
3. Add a golden-case test in `scanner/tests/test_alerts.py`.

`scan.py` and the dashboard pick it up automatically (new categories render as their own section).
