---
title: CodeOracle — Startup Package
subtitle: Launch context for all future Claude Code sessions on this project
date: 2026-07-10
author: founding Claude session
status: canonical — read this before touching anything
project_root: C:\CodeOracle
sibling_projects:
  - Pythia (bluechipsignal — Bitget spot/futures signal caller)
  - mm-radar / shitcoinmaster (basket-regime detector)
discipline_source: _bootstrap/UNIVERSAL_DISCIPLINE.md
mission_source: _bootstrap/MISSION.md
edge_guide_source: _bootstrap/ONCHAIN_EDGE_GUIDE.md
---

# CodeOracle — Startup Package

> Read this document in full before writing a single line of code. Then read `_bootstrap/UNIVERSAL_DISCIPLINE.md` in full. Both are non-optional. If you are a fresh Claude session invoked here, your first tool call after reading these two files is to skim any project-specific memory under `~/.claude/projects/C--CodeOracle/memory/` — if absent, that is expected: you are early.

---

## 1. Identity & Mission

**CodeOracle is a profitable long/short signal caller specialized in Bitget's Onchain venue** (`bitget.com/asia/on-chain/`) — the pre-listing DEX board covering Solana, BSC, Ethereum, Base, Morph, Monad plus Bitget's tokenized-stock roster. Product surface: Telegram. Cadence: setup cards on trigger + one daily digest. Every signal is traceable to a pre-registered mechanical edge and gets a resolution measurement (TP1 / SL / EXPIRED, R-multiple recorded). Operator is human-in-loop, capital-constrained ($50–$200 initial), Windows-native. Progression arc: signal caller → semi-automated → small-capital auto-trader — never skipping stages.

**CodeOracle is explicitly NOT** a centralized-exchange scanner (Pythia already owns Bitget spot/futures), a general crypto news aggregator, a hype/shill account, an academic edge-discovery research pipeline, a multi-user product, or a fork/extension of a sibling project. It does not compete with sibling projects on their universes; cross-project handoffs go through operator relay, never direct file access. It ships mechanical edges, not narrative takes. If a proposed feature does not clearly serve "call a profitable trade a human can execute in 30 seconds via Telegram, with honest R-tracked resolution," it does not ship in v1.

---

## 2. Universe Definition

### 2.1 Chain scope (in order of priority)

| Priority | Chain | Cadence | v1? | Rationale |
|---|---|---|---|---|
| P0 | Solana | 5 min | YES | Largest population on Bitget Onchain; deepest DEX data infra (Helius, Birdeye) |
| P0 | Tokenized stocks (Bitget roster) | 5 min US-open / 60 min off-hours | YES | Distinct edge class (weekend/hours arb) — free underlying data via yfinance |
| P1 | BSC | 15 min | v1.1 | DexScreener-covered; secondary volume source |
| P1 | Ethereum | 15 min | v1.1 | Larger caps, less noise |
| P1 | Base | 15 min | v1.1 | Coinbase L2 memes; farcaster-adjacent |
| P2 | Morph | 15 min | backlog | Small population; revisit when volume justifies |
| P2 | Monad | 15 min | backlog | Pre-mainnet / early ecosystem |

**Decision:** v1 ships **Solana + tokenized stocks only**. This buys one narrow, one orthogonal edge class each, and defers the multi-chain ops burden by two weeks. BSC/ETH/Base come online in week 2–3 once Solana pipeline is proven.

### 2.2 Listing-status rules

The Bitget Onchain roster is the **source of truth for universe inclusion**. A token is IN if:
- It currently appears on `bitget.com/asia/on-chain/` in a chain we cover.
- It is not simultaneously listed on Bitget spot or futures (that universe belongs to Pythia — checked once per snapshot against Bitget's public spot/futures roster; if a token appears on both, `venue = 'crosslisted'` and we defer to Pythia).
- Roster snapshot is cached each scanner cycle (Part 4 anti-pattern: "universe drift"). A mid-cycle roster query would give inconsistent results; the snapshot is the atomic unit.

### 2.3 Tokenized-stock inclusion criteria

- Must appear in Bitget's tokenized-stock roster on the Onchain page.
- Must have an identifiable underlying US equity (mapping table `tokenized_stock_map` — hand-maintained; ~20–50 entries max).
- Underlying must be tradeable on a data source we integrate (yfinance covers virtually all US-listed).
- Underlying's exchange calendar must be trackable (NYSE / NASDAQ standard hours — pandas-market-calendars).

Tokens where the underlying is not identifiable (wrapped indices, obscure ADRs) go to a `tokenized_stock_unmapped` table for future manual curation; they do not receive signals.

### 2.4 Exclusion filters (GATE ZERO — survivorship)

A token failing ANY of these does not receive signals in v1. It is tracked in `watchlist_pending` for future re-eval:

| Filter | Threshold | Rationale |
|---|---|---|
| Primary pool liquidity | ≥ $50,000 both sides | Below this, $25 position slippage > 2% |
| Contract-risk badge | Bitget = Normal | External override only via RugCheck+TokenSniffer BOTH clean; then downgrade tier −1 medal |
| Mint authority | Renounced or provably burned | Non-renounced mint = rug primitive |
| LP-lock status | Locked (Team Finance / PinkSale / UNCX / verified burn) | Un-locked LP = rug primitive |
| 24h volume | ≥ 3× current market cap | Dead-token filter (traded once then died) |
| Age | ≥ 6h AND ≤ 30d | Launch-day is separate signal class; excludes ancient dead tokens |
| Holder count | ≥ 100 unique holders | Below = single-wallet setups |
| Top-10 holder concentration | ≤ 60% | Above = coordinated dump risk (this is the survivorship floor; E1 uses tighter 40% for its signal) |

Thresholds are v1 defaults. They are **env-var overridable** (`GATE_LIQ_MIN_USD`, `GATE_HOLDER_MIN`, etc.) so tightening/loosening does not require code deploy. Every threshold change is logged with rationale in `universe_config_history`.

### 2.5 Anti-rug heuristics (informational — not GATE ZERO vetos, but downgrade signals)

- Dev-wallet % > 5% → −1 medal
- Sniper-cohort still holds > 40% → −1 medal
- Nakamoto coefficient < 5 → −1 medal
- LP unlock < 14d away → cannot LONG; can SHORT via E5
- Contract age < 24h → separate signal class (launch-window), stricter rules TBD

---

## 3. Data-Source Inventory

**Selection principle (from edge guide Part 2):** ≤ 4 sources in v1. Every source is ops burden (rotation, rate limits, schema drift, downtime). v1 targets: token discovery, OHLC, holder/whale data, contract-risk data.

### 3.1 v1 sources (integrate week 1)

| # | Source | Purpose | Endpoint / lib | Rate limit | Cost | Reliability | Fallback if down |
|---|---|---|---|---|---|---|---|
| 1 | **Bitget Onchain page** | Universe roster + contract-risk badge + Bitget-native volume/liq | Investigate official API first (`api.bitget.com`). If no public API for the Onchain board, HTML scrape `bitget.com/asia/on-chain/` with polite headers, snapshot every 15 min | Unknown until confirmed | Free | B (scrape-fragile) | If unreachable → use last cached snapshot (staleness flag in every signal); alert if > 60 min stale |
| 2 | **DexScreener API** | Cross-chain OHLC + pool metadata + liquidity depth baseline | `api.dexscreener.com/latest/dex/tokens/{addr}` | ~300 req/min | Free | A | GeckoTerminal (`api.geckoterminal.com`) as cold fallback |
| 3 | **Helius** (Solana only) | Solana holder distribution, token metadata, tx-level buyer extraction | `mainnet.helius-rpc.com` + Enhanced APIs | 100k credits/day free | Free tier | A | Birdeye free API for holders; Solana public RPC for basic tx data |
| 4 | **yfinance** (Python lib) | Tokenized-stock underlying prices + US market hours | `pip install yfinance` + `pandas-market-calendars` | Effectively unmetered | Free | B (unofficial) | Alpaca free tier as cold fallback |

### 3.2 v1 supporting sources (integrate week 2)

| # | Source | Purpose | Endpoint | Rate limit | Cost | Reliability | Fallback |
|---|---|---|---|---|---|---|---|
| 5 | **RugCheck.xyz** | Solana contract-risk cross-check | `api.rugcheck.xyz/v1/tokens/{addr}` | Reasonable | Free | B | TokenSniffer for non-SOL |
| 6 | **TokenSniffer** | Multi-chain contract-risk cross-check | Public HTML endpoint, may need scraping | Low | Free | B | Manual review flag |
| 7 | **pump.fun graduation feed** (E4 dep) | Solana bonding-curve graduation events | Public feed / Helius webhook | Free | Free | B | Poll Raydium new-pool events via Helius |

### 3.3 Deferred (v2+)

Arkham (free tier — whale labels; defer to E2), Nansen (paid $150/mo — defer until edge justifies), Bitquery, LunarCrush, Farcaster, Alchemy multi-chain, Dune. All require ROI justification; each new source needs a written "expected edge lift" note before integration.

### 3.4 Cross-cutting requirements

- **Every source gets a `data_source_health` row per cycle**: `(source, cycle_ts, latency_ms, ok, error_class, cached_used)`. Digest surfaces sources that have degraded.
- **Every API key** in `.env`, never in code, never in commits. Env-var names: `CODEORACLE_HELIUS_KEY`, `CODEORACLE_TG_TOKEN`, etc. (See §5.5.)
- **Every source has an explicit kill-switch**: `SOURCE_HELIUS_DISABLED=true` skips Helius, degrades enrichment; scanner continues on baseline DexScreener data (edge guide: "never let a single data-source failure block the entire scanner cycle").
- **Free-tier lock-in mitigation** (edge guide Part 7 anti-pattern #3): every critical signal traces to ≥ 2 sources by end of first month, or gets a "single-source" warning in the digest.

---

## 4. Edge Hypothesis Catalog

Six candidates. **v1 ships E1, E4, E9** (chosen for: two orthogonal domains, tractable data, distinct mechanisms — reduces correlation risk across the family). E2, E5, E6 enter SHADOW in weeks 2–4 pending data availability. Every edge follows: mechanism → pre-registration → SHADOW → promotion gate → LIVE.

**Bonferroni family:** all concurrently-SHADOW edges are one family. With 3 v1 edges, α = 0.05/3 = 0.0167 per-edge threshold for LIVE promotion; expand denominator as more edges enter SHADOW simultaneously.

### E1 — Early holder-concentration anomaly `[v1, SHIP FIRST]`

- **Mechanism.** Post-launch Solana tokens where top-10 holders < 40%, dev wallet < 5%, LP locked, and holder count growth is organic (not airdrop farming — measured as unique-buyer/USD-volume ratio) survive the first-week mortality curve at higher rates and re-rate on second-wave interest.
- **Trigger.** Token enters universe (passes GATE ZERO), plus: top-10 concentration < 40% at signal time, holder velocity > median for chain last 24h, dev wallet balance < 5%, LP lock duration > 30d remaining.
- **Direction.** LONG only. Entry: current price with ±0.5% band. Stop: −18% (per-chain median 7d drawdown from surviving tokens in a backtest of the last 90d — encoded as `E1_STOP_PCT` env). TP1: +40% (1.5R after fees). Thesis window: 72h.
- **Pre-registration.**
  - Hypothesis: median R-return of E1 signals > 0 at 72h resolution.
  - Sample size for promotion decision: n = 30 resolved SHADOW signals.
  - Test statistic: bootstrap 95% CI of median R (10,000 resamples).
  - Decision threshold: CI lower bound > 0 AND median R ≥ +0.20 AND SHIP-rate (fraction reaching TP1) ≥ 30% AND Bonferroni-corrected p < 0.0167.
  - Resolution window: 72h from emission → forced EXPIRED at final mid-price.
  - Pre-reg doc: `research/pre_reg_E1.md` (mandatory before first SHADOW signal fires).
- **SHADOW→LIVE gate.** Meet all pre-reg thresholds; additionally, drawdown envelope (max cumulative R across resolved SHADOW signals) must not exceed −5R at any point during accumulation (protection against right-tail-driven false pass).
- **Kill-switch.** `EDGE_E1_DISABLED=true` — signal path skipped, existing open E1 signals resolve normally.
- **Data deps.** DexScreener (price/liquidity), Helius (holder distribution + tx-level buyers), Bitget Onchain roster.

### E4 — Liquidity-migration graduation `[v1, SHIP FIRST]`

- **Mechanism.** pump.fun tokens graduating to Raydium receive a mechanical liquidity injection ($LP added by protocol) + observable re-rating window (first 5–60 min). The graduation event itself is the trigger, not narrative.
- **Trigger.** Detected pump.fun graduation event; token also on Bitget Onchain roster within 60 min of graduation; passes GATE ZERO immediately post-graduation.
- **Direction.** LONG only. Entry: within 5 min of graduation detection (WARN operator on card: FAST 5m window; MEV-risk flag). Stop: −12%. TP1: +25% (2R after fees). Thesis window: 4h.
- **Pre-registration.**
  - Hypothesis: median R > 0 at 4h resolution.
  - Sample size: n = 25 resolved SHADOW signals.
  - Test statistic: bootstrap 95% CI of median R.
  - Decision threshold: CI lower bound > 0 AND median R ≥ +0.30 AND SHIP-rate ≥ 35% AND Bonferroni-corrected p < 0.0167.
  - Resolution window: 4h from emission.
  - Pre-reg doc: `research/pre_reg_E4.md`.
- **SHADOW→LIVE gate.** Same as E1 plus: median time-to-TP1 must be < 90 min (if the edge takes longer than the window in most cases, the window is wrong).
- **Kill-switch.** `EDGE_E4_DISABLED=true`.
- **Data deps.** pump.fun graduation feed, Helius (Raydium pool creation), DexScreener (post-grad price), Bitget Onchain roster.

### E9 — Tokenized-stock weekend arbitrage `[v1, SHIP FIRST]`

- **Mechanism.** Tokenized US equities trade 24/7 on Bitget Onchain; underlyings trade M–F 09:30–16:00 ET. Weekend/off-hours drift on the token often reverses at Monday market open (edge guide E9). Fade the weekend move.
- **Trigger.** Fri 16:00 ET underlying close is captured. From Sat 00:00 UTC through Sun 22:00 UTC, cumulative token drift from Fri-close > +3% (SHORT candidate) or < −3% (LONG candidate). Fires as a signal at Sun 22:00 UTC with entry at then-current price.
- **Direction.** LONG or SHORT. On Bitget Onchain there is no native short — SHORT signal advises: (a) close/reduce any existing long exposure, (b) external perp short if the underlying tokenized equity is listed on a perp venue elsewhere (rare), or (c) skip-and-wait. Card carries this mode explicitly in the WHY block.
- **Direction, entry, exit.** Entry: Sun 22:00 UTC. Stop: ±6% from entry. TP1: revert to Fri-16:00-ET-close level, capped at ±3% (2R after fees). Thesis window: close 2h after US market open Monday (Mon 11:30 ET).
- **Pre-registration.**
  - Hypothesis: median R > 0 at close-time resolution.
  - Sample size: n = 30 weekends × per-symbol (require aggregation ≥ 30 total signals; if not enough per-symbol → pooled across roster).
  - Test statistic: bootstrap 95% CI of median R.
  - Decision threshold: CI lower bound > 0 AND median R ≥ +0.25 AND SHIP-rate ≥ 40% AND Bonferroni p < 0.0167.
  - Pre-reg doc: `research/pre_reg_E9.md`.
- **SHADOW→LIVE gate.** All above plus: rejection of any weekend where underlying had a scheduled earnings release Fri after close or Mon before open (calendar gate — pre-registered exclusion, not post-hoc).
- **Kill-switch.** `EDGE_E9_DISABLED=true`.
- **Data deps.** Bitget tokenized-stock roster + underlying map, yfinance (underlying price), pandas-market-calendars (holidays), Bitget Onchain token price.

### E2 — Whale-buy first-mover `[v1.1, week 2 SHADOW start]`

- **Mechanism.** Known smart-money wallet buys a token pre-Bitget-Onchain-trending; follow-in signal within 15 min captures the second-wave interest. Only wallets pre-labelled positive track-record (n ≥ 10 prior trades, mean R > +0.4 last 90d).
- **Trigger.** Smart-money buy > $5k on a token that passes GATE ZERO; token 24h volume not already > 5× median (not chasing a pump).
- **Direction.** LONG. Entry: within 15 min of detection. Stop: −15%. TP1: +30% (2R after fees). Window: 12h.
- **Pre-reg.** n = 25; median R > +0.30; CI lower bound > 0; ship-rate ≥ 30%; Bonferroni; pre-reg doc `research/pre_reg_E2.md`. **Additional pre-reg exclusion:** wallets from the smart-money list must be frozen at pre-reg time — no adding wallets mid-experiment (avoids selection bias).
- **Kill-switch.** `EDGE_E2_DISABLED=true`.
- **Data deps.** Arkham free tier + hand-curated smart-money list (`smart_wallets` table, versioned).

### E5 — LP-unlock cliff `[v1.1, week 3 SHADOW start]`

- **Mechanism.** LP unlocks within 24–48h often trigger coordinated dumps. SHORT (or exit-long-advisory) 24–48h before public unlock.
- **Trigger.** LP unlock scheduled within 24–48h AND token has been on Bitget Onchain > 7d AND token has run > +50% since listing (otherwise nothing to dump).
- **Direction.** SHORT-mode signal (advisory: close longs, or external short — see E9 handling).
- **Pre-reg.** n = 20; median R > +0.20 (short-signed); CI < 0 for token price; Bonferroni; pre-reg doc `research/pre_reg_E5.md`.
- **Kill-switch.** `EDGE_E5_DISABLED=true`.
- **Data deps.** LP-lock services (Team Finance, PinkSale, UNCX — public APIs where available; manual entry `lp_unlock_calendar` table otherwise).

### E6 — Contract-risk badge downgrade `[v1.1, week 4 SHADOW start]`

- **Mechanism.** Bitget flipping a token Normal → Warning triggers user-visible fear; expect coordinated exit within 1–6h.
- **Trigger.** Delta detected in Bitget contract-risk badge snapshot vs. previous cycle: transition Normal → Warning or Warning → Danger.
- **Direction.** SHORT-mode advisory.
- **Pre-reg.** n = 15; median negative move > 5% in +1h to +6h window; CI clear of 0; Bonferroni; pre-reg doc `research/pre_reg_E6.md`.
- **Kill-switch.** `EDGE_E6_DISABLED=true`.
- **Data deps.** Bitget Onchain badge polling (part of source #1); badge-history table for delta detection.

### Punted to backlog (v2)

E3 (cross-chain narrative rotation — requires manual/LLM narrative tagging, high setup cost), E7 (volume authenticity — nice-to-have, not first cut), E8 (sniper-cohort exit — data-heavy for marginal edge in v1), E10 (tokenized-stock premium/discount — requires real-time underlying feed, defer until yfinance proves reliable).

---

## 5. Pipeline Architecture

### 5.1 Module map

```
C:\CodeOracle\
├── _bootstrap\          # canonical brief (never modified by future sessions)
├── STARTUP_PACKAGE.md   # this file
├── .claude\
│   ├── settings.json    # committed — statusLine + SessionStart hook (identity "CodeOracle")
│   └── settings.local.json  # gitignored — API keys ONLY in .env, not here
├── .env                 # gitignored — all secrets
├── .env.example         # committed — schema only, no values
├── research\            # pre-reg docs, retrospectives
│   ├── pre_reg_E1.md
│   ├── pre_reg_E4.md
│   └── pre_reg_E9.md
├── src\
│   ├── ingest\
│   │   ├── bitget_onchain.py     # roster + badges (source #1)
│   │   ├── dexscreener.py         # cross-chain OHLC/liq (source #2)
│   │   ├── helius.py              # Solana enrichment (source #3)
│   │   ├── yfinance_client.py     # tokenized-stock underlyings (source #4)
│   │   ├── rugcheck.py            # v1.1 — SOL contract risk
│   │   └── pump_fun.py            # v1.1 — graduation events
│   ├── universe\
│   │   ├── snapshotter.py         # per-cycle roster snapshot
│   │   ├── survivorship.py        # GATE ZERO
│   │   └── tokenized_stock_map.py # underlying-equity mapping
│   ├── edges\
│   │   ├── base.py                # Edge ABC — evaluate(token_snapshot) -> Optional[Signal]
│   │   ├── e1_holder_concentration.py
│   │   ├── e4_liquidity_migration.py
│   │   ├── e9_tokenized_weekend.py
│   │   ├── e2_whale_buy.py        # week 2
│   │   ├── e5_lp_unlock.py        # week 3
│   │   └── e6_badge_downgrade.py  # week 4
│   ├── signals\
│   │   ├── composer.py            # Signal object + medal computation
│   │   ├── dedup.py               # 24h dedup per (edge, symbol)
│   │   └── emission_gate.py       # 5-per-24h hard cap; muted-cards path
│   ├── telegram\
│   │   ├── _esc.py                # html.escape wrapper — CENTRAL, USED BY ALL FORMATTERS
│   │   ├── formatter.py           # Style A setup card
│   │   ├── digest_formatter.py    # Style B daily digest
│   │   └── sender.py              # HTTP to Bot API + retries
│   ├── resolver\
│   │   ├── open_scanner.py        # TP1/SL check every 15m
│   │   └── expirer.py             # thesis-window EXPIRED at deadline
│   ├── digest\
│   │   └── daily_digest.py        # 20:00 UTC composer
│   ├── audit\
│   │   ├── heartbeat.py           # writes health row every scanner cycle
│   │   ├── drift_monitor.py       # 30d rolling edge R; auto-disable if CI < 0
│   │   └── stale_alarm.py         # source freshness > 60m => alert
│   └── db\
│       ├── conn.py                # psycopg conn, DSN from env
│       ├── migrations\            # numbered .sql, additive-only
│       │   ├── 001_init.sql
│       │   ├── 002_signals.sql
│       │   └── ...
│       └── models.py              # thin dataclasses, not ORM
├── scripts\
│   ├── run_scan_solana.py         # entry called by Task Scheduler
│   ├── run_scan_tokenized.py
│   ├── run_resolver.py
│   ├── run_digest.py
│   └── run_heartbeat.py
├── tests\
│   ├── test_esc.py                # xss regression — mandatory
│   ├── test_survivorship.py
│   ├── test_edges_e1.py
│   └── ...
└── logs\                          # gitignored, rotated
```

### 5.2 Data flow (per Solana 5-min scanner cycle)

```
Task Scheduler fires run_scan_solana.py
  │
  ├─► ingest.bitget_onchain.snapshot_roster()  ── writes universe_snapshots row
  │       │
  │       └─► for each token: ingest.dexscreener.enrich_prices()
  │           │
  │           └─► if chain=SOL: ingest.helius.enrich_holders_and_devwallet()
  │
  ├─► universe.survivorship.filter(snapshot)  ── GATE ZERO
  │       │
  │       └─► writes token_states row per token (pass/fail + reasons)
  │
  ├─► for each active edge in [E1, E4]:
  │       edge.evaluate(passing_tokens) ── returns list[Signal]
  │       │
  │       └─► signals.dedup + signals.emission_gate
  │           │
  │           └─► SHADOW MODE: write shadow_log row; NO Telegram send
  │           └─► LIVE MODE (post-promotion): telegram.sender.send(card)
  │                                                     │
  │                                                     └─► write signals row
  │
  ├─► audit.heartbeat.write_cycle_row(cycle_id, latency, ok)
  │
  └─► audit.stale_alarm.check_source_freshness()
```

### 5.3 Postgres schema (sketch — additive-only from day 1)

```sql
-- 001_init.sql
CREATE TABLE IF NOT EXISTS universe_snapshots (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    snapshot_ts     TIMESTAMPTZ NOT NULL,
    chain           TEXT NOT NULL,
    token_count     INT NOT NULL,
    source_used     TEXT NOT NULL,       -- 'bitget_api' | 'bitget_scrape' | 'cache'
    stale_flag      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ON universe_snapshots (snapshot_ts DESC);

CREATE TABLE IF NOT EXISTS tokens (
    token_addr      TEXT NOT NULL,
    chain           TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    name            TEXT,
    first_seen_ts   TIMESTAMPTZ NOT NULL,
    tokenized_stock BOOLEAN NOT NULL DEFAULT FALSE,
    underlying_ticker TEXT,              -- populated when tokenized_stock
    PRIMARY KEY (chain, token_addr)
);

CREATE TABLE IF NOT EXISTS token_states (
    snapshot_id     BIGINT REFERENCES universe_snapshots,
    token_addr      TEXT NOT NULL,
    chain           TEXT NOT NULL,
    price_usd       NUMERIC(30,10),
    liq_usd         NUMERIC(20,2),
    vol_24h_usd     NUMERIC(20,2),
    mcap_usd        NUMERIC(20,2),
    holder_count    INT,
    top10_pct       NUMERIC(6,4),
    dev_wallet_pct  NUMERIC(6,4),
    lp_locked_until TIMESTAMPTZ,
    contract_badge  TEXT,                -- 'normal' | 'warning' | 'danger'
    trading_badge   TEXT,
    survives_gate0  BOOLEAN NOT NULL,
    fail_reasons    TEXT[],
    PRIMARY KEY (snapshot_id, chain, token_addr)
);
CREATE INDEX ON token_states (chain, token_addr, snapshot_id DESC);

-- 002_signals.sql
CREATE TABLE IF NOT EXISTS edges (
    edge_code       TEXT PRIMARY KEY,    -- 'E1','E4','E9', ...
    version         INT NOT NULL,
    status          TEXT NOT NULL,       -- 'shadow' | 'live' | 'parked' | 'killed'
    prereg_path     TEXT NOT NULL,
    prereg_sha256   TEXT NOT NULL,       -- frozen pre-reg doc hash
    promoted_at     TIMESTAMPTZ,
    parked_at       TIMESTAMPTZ,
    kill_reason     TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id       BIGSERIAL PRIMARY KEY,
    emitted_ts      TIMESTAMPTZ NOT NULL,
    edge_code       TEXT NOT NULL REFERENCES edges,
    mode            TEXT NOT NULL,       -- 'shadow' | 'live'
    chain           TEXT NOT NULL,
    token_addr      TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,       -- 'long' | 'short_advisory' | 'short_perp'
    medal           SMALLINT NOT NULL,   -- 1..5
    entry_price     NUMERIC(30,10) NOT NULL,
    stop_price      NUMERIC(30,10) NOT NULL,
    tp1_price       NUMERIC(30,10) NOT NULL,
    thesis_window_min INT NOT NULL,
    entry_window_min  INT NOT NULL,
    slip_est_bps    INT,
    tg_message_id   BIGINT,              -- null in shadow mode
    tg_chat_id      BIGINT,
    card_json       JSONB NOT NULL       -- exact fields rendered — audit trail
);
CREATE INDEX ON signals (edge_code, emitted_ts DESC);
CREATE INDEX ON signals (chain, token_addr);

CREATE TABLE IF NOT EXISTS resolutions (
    signal_id       BIGINT PRIMARY KEY REFERENCES signals,
    resolved_ts     TIMESTAMPTZ NOT NULL,
    outcome         TEXT NOT NULL,       -- 'tp1' | 'sl' | 'expired' | 'chased' | 'invalid'
    exit_price      NUMERIC(30,10),
    r_multiple      NUMERIC(8,4) NOT NULL,
    minutes_to_res  INT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS shadow_log (
    shadow_id       BIGSERIAL PRIMARY KEY,
    would_have_fired_ts TIMESTAMPTZ NOT NULL,
    edge_code       TEXT NOT NULL,
    chain           TEXT NOT NULL,
    token_addr      TEXT NOT NULL,
    card_json       JSONB NOT NULL,
    resolved_ts     TIMESTAMPTZ,
    outcome         TEXT,
    r_multiple      NUMERIC(8,4)
);

-- 003_ops.sql
CREATE TABLE IF NOT EXISTS data_source_health (
    id              BIGSERIAL PRIMARY KEY,
    cycle_ts        TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,
    latency_ms      INT,
    ok              BOOLEAN NOT NULL,
    error_class     TEXT,
    cached_used     BOOLEAN NOT NULL
);
CREATE INDEX ON data_source_health (source, cycle_ts DESC);

CREATE TABLE IF NOT EXISTS heartbeats (
    id              BIGSERIAL PRIMARY KEY,
    cycle_ts        TIMESTAMPTZ NOT NULL,
    task_name       TEXT NOT NULL,
    duration_ms     INT NOT NULL,
    ok              BOOLEAN NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS universe_config_history (
    id              BIGSERIAL PRIMARY KEY,
    changed_ts      TIMESTAMPTZ NOT NULL,
    param           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    rationale       TEXT NOT NULL
);
```

Every migration is additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`). Never drops or renames without a migration path in the same file.

### 5.4 Scheduler (Windows Task Scheduler, not cron)

Each scheduled task runs a python entrypoint under a dedicated venv (`C:\CodeOracle\.venv\Scripts\python.exe`). Never OneDrive path. Task Scheduler is configured via a `scripts/register_tasks.ps1` script (idempotent — safe to re-run).

| Task name | Trigger | Runs |
|---|---|---|
| `CodeOracle_ScanSolana` | Every 5 min | `scripts\run_scan_solana.py` |
| `CodeOracle_ScanTokenizedLive` | Every 5 min, M–F 09:30–16:00 ET (with DST) | `scripts\run_scan_tokenized.py --mode=live` |
| `CodeOracle_ScanTokenizedOff` | Every 60 min outside live window | `scripts\run_scan_tokenized.py --mode=off` |
| `CodeOracle_ScanOtherChains` | Every 15 min | `scripts\run_scan_others.py` (v1.1, no-op in v1) |
| `CodeOracle_Resolver` | Every 15 min | `scripts\run_resolver.py` |
| `CodeOracle_Expirer` | Every 4 h | `scripts\run_expirer.py` |
| `CodeOracle_Digest` | Daily 20:00 UTC | `scripts\run_digest.py` |
| `CodeOracle_Heartbeat` | Every 5 min | `scripts\run_heartbeat.py` |

Each task writes a heartbeat row on completion; digest surfaces missing beats. Task Scheduler `Settings → If the task fails, restart every: 5 min, up to 3 times`.

### 5.5 Env-var conventions

Prefix `CODEORACLE_` for secrets/config, prefix `EDGE_<CODE>_` for edge-specific knobs, prefix `GATE_` for GATE ZERO thresholds, prefix `SOURCE_` for source-specific knobs, no prefix for kill-switches ending in `_DISABLED`.

```
# --- .env.example (committed) ---
# Secrets
CODEORACLE_DB_URL=postgresql://codeoracle:<password>@localhost:5432/codeoracle
CODEORACLE_TG_TOKEN=<bot-token>
CODEORACLE_TG_CHAT_LIVE=<chat-id>
CODEORACLE_TG_CHAT_MUTED=<chat-id>
CODEORACLE_TG_CHAT_DIGEST=<chat-id>
CODEORACLE_HELIUS_KEY=<key>
CODEORACLE_ARKHAM_KEY=

# GATE ZERO thresholds (numeric — see §2.4)
GATE_LIQ_MIN_USD=50000
GATE_HOLDER_MIN=100
GATE_TOP10_MAX_PCT=0.60
GATE_VOL_MCAP_RATIO_MIN=3.0
GATE_AGE_MIN_HOURS=6
GATE_AGE_MAX_DAYS=30

# Edge tunables
EDGE_E1_STOP_PCT=0.18
EDGE_E1_TP1_PCT=0.40
EDGE_E1_WINDOW_HOURS=72
EDGE_E4_STOP_PCT=0.12
EDGE_E4_TP1_PCT=0.25
EDGE_E4_WINDOW_HOURS=4
EDGE_E9_STOP_PCT=0.06
EDGE_E9_TP1_PCT=0.03

# Kill switches — set to "true" to disable
EMISSION_DISABLED=false            # NUCLEAR — kills all Telegram sends
SIGNAL_EMISSION_DISABLED=false     # kill live signals only, digest continues
DIGEST_DISABLED=false
EDGE_E1_DISABLED=false
EDGE_E4_DISABLED=false
EDGE_E9_DISABLED=false
EDGE_E2_DISABLED=false
EDGE_E5_DISABLED=false
EDGE_E6_DISABLED=false
SOURCE_BITGET_DISABLED=false
SOURCE_DEXSCREENER_DISABLED=false
SOURCE_HELIUS_DISABLED=false
SOURCE_YFINANCE_DISABLED=false
SCANNER_SOLANA_DISABLED=false
SCANNER_TOKENIZED_DISABLED=false
```

### 5.6 Kill-switch inventory (one per module — non-negotiable per UNIVERSAL_DISCIPLINE.md §I.2)

| Feature | Env var | Behavior when true |
|---|---|---|
| ALL Telegram sends | `EMISSION_DISABLED` | Formatters run, sender no-ops with log line |
| Live signal Telegram sends | `SIGNAL_EMISSION_DISABLED` | Signals write to DB with mode='shadow', no TG send |
| Daily digest | `DIGEST_DISABLED` | Digest task no-ops |
| Any edge | `EDGE_<CODE>_DISABLED` | Edge evaluator skipped in scanner loop |
| Any data source | `SOURCE_<NAME>_DISABLED` | Ingest skipped, graceful degrade to fallback |
| Any scanner | `SCANNER_<CHAIN>_DISABLED` | Whole task no-ops |

Every deploy runs `scripts/verify_kill_switches.py` which asserts each switch actually skips its path in a dry-run harness.

---

## 6. Risk & Safety Layer

### 6.1 GATE ZERO (universe survivorship)

Defined in §2.4. Enforced by `universe.survivorship.filter()` — every token that fails is written to `token_states` with `survives_gate0=false` and `fail_reasons` array. Signal composers see only the survivors.

### 6.2 Contract-risk gate

- Bitget badge = Normal → pass.
- Bitget badge = Warning → require **both** RugCheck AND TokenSniffer clean → pass at medal −1.
- Bitget badge = Warning + any external checker shows scam-flags → veto.
- Bitget badge = Danger → veto unconditional.
- Bitget badge missing / stale > 60 min → treat as Warning.

### 6.3 Liquidity-depth vs position-size rule

Every signal card computes and displays:
```
slippage_est = f(position_usd, pool_liq_usd, pool_type)
```
For AMM v2: `slip_bps ≈ 10000 * (position / (position + pool_liq_side))`.
For CLMM (Uniswap V3 / Raydium CLMM): use tick-based simulation; fall back to v2 approximation if tick data unavailable.

**Emission rule:** for a default assumed position size = `min(operator_capital * 0.15, $30)` (v1 defaults; env-var `POSITION_DEFAULT_USD`), if estimated slippage > 2%: either (a) reduce position and re-check; (b) if still > 2%, do not emit — write to muted-cards channel with reason.

### 6.4 Honeypot detection

- Solana: RugCheck.xyz's honeypot flag (v1.1).
- All chains: attempted "test sell" simulation via public API if available; if not, flag any token where 0 sells have been observed in the transaction history (buy-only history is a honeypot tell).
- Muted-cards channel gets any veto with reason.

### 6.5 Slippage estimation

Per §6.3. Additionally, signal card carries **expected round-trip drag** (buy slip + sell slip + DEX fees + typical MEV allowance):
```
drag_bps = buy_slip + sell_slip + dex_fee_bps + mev_allowance_bps
```
`mev_allowance_bps` defaults: SOL = 30 (Jito-protected assumption), BSC = 40, ETH = 60. Signals with round-trip drag > 200 bps require median R > +0.5 to emit (edge guide anti-pattern: signals must clear the drag hurdle with margin).

### 6.6 MEV awareness

- Entry windows < 30s are refused in v1 (no realistic MEV mitigation on operator infrastructure).
- Entry windows 30s–5min → card carries `MEV_RISK: HIGH` label.
- Entry windows > 5min → `MEV_RISK: LOW`.
- Suggested private-RPC hint on Solana signals: "Use Jito-protected RPC or bundle sender."

### 6.7 Tokenized-stock hours awareness

Every tokenized-stock signal carries market-hours state:
- `US_MARKET_OPEN` (M–F 09:30–16:00 ET, adjusted for holidays via pandas-market-calendars)
- `US_MARKET_CLOSED` (weekday off-hours)
- `WEEKEND` (Sat 00:00 UTC – Mon 09:29 ET)
- `HOLIDAY` (NYSE closed weekday)

Edges declare which regimes they operate in — E9 fires only during WEEKEND-approaching-open transition; E10 (v2) would fire only during US_MARKET_OPEN. Mis-regime signals are rejected pre-emit.

### 6.8 Universe survivorship filter (retrospective)

Weekly job computes % of universe entries from 30d ago that still pass GATE ZERO today. If < 40%, digest surfaces "high-mortality universe" warning; may indicate need to tighten GATE ZERO thresholds. Actual tightening decision is operator-authorized (crosses trading-philosophy line — logs in `universe_config_history`).

### 6.9 Drift monitor + auto-park

Each LIVE edge tracks rolling 30d mean R and 95% CI. If mean R < 0 AND CI overlaps zero → `edges.status = 'parked'`, `parked_at = now()`, and `kill_reason = 'drift_auto_park'`. Signal path skipped. Operator notified in daily digest. No auto-revive; requires a retrospective + re-promotion review.

### 6.10 Capital-scale awareness

At $100 capital, `POSITION_DEFAULT_USD=15`. Every ~2× capital growth, revisit `GATE_LIQ_MIN_USD` (raise it) so the universe naturally tightens with size. This is intentional (edge guide Part 4), not a bug.

---

## 7. Telegram Output Schema

Every field routed through `_esc()` (which wraps `html.escape(str, quote=True)`). The **only** unescaped strings are literal author-typed markup tags. Tests in `tests/test_esc.py` assert that inserting `<script>`, `&amp;`, and Telegram-special metachars into every field produces escaped output.

### 7.1 Style A — Setup card (per-signal)

Telegram parse mode: `HTML`.

```
{medal}  {DIR}  {SYMBOL}   #{rank_24h}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 EDGE: {edge_code} — {edge_short_name}
🕒 EMITTED: {emitted_ts_utc}   MODE: {SHADOW|LIVE}
📎 PRIOR: {prior_call_ref or "—"}

💰 LEVELS
 • Price now:   ${price_now}
 • Entry:       ${entry_lo}–${entry_hi}   ({entry_window_label})
 • Stop:        ${stop_price}   ({stop_pct_signed}%)
 • TP1:         ${tp1_price}    (+{tp1_r_multiple}R)
 • Adverse P90: {adverse_p90_pct}%   (n={adverse_sample_n})

⏱ WINDOW
 • Entry urgency: {entry_urgency}   ({entry_window_label})
 • Thesis window: {thesis_window_label}

🌐 CONTEXT
 • Chain regime: {chain_regime_line}
 • Narrative:    {narrative_tag}
 • Calendar:     {calendar_note or "—"}

🔗 ONCHAIN
 • Contract badge: {contract_badge}   (Trading: {trading_badge})
 • Liq depth:      ${liq_1pct}/±1%   ${liq_2pct}/±2%   ${liq_5pct}/±5%
 • Slip est:       {slip_est_bps} bps @ ${position_default_usd} pos
 • MEV risk:       {mev_risk_label}
 • Holders:        {holder_count}   (top10 {top10_pct}%   Nakamoto {nakamoto})
 • LP:             locked → {lp_unlock_ts or "burn"}
 • Dev wallet:     {dev_wallet_pct}%
 • Snipers:        {sniper_pct}% held / {sniper_exit_pct}% exited

📊 TYPICAL (n={typical_n})
 • Median t→TP1:   {median_min_to_tp1} min
 • Median t→SL:    {median_min_to_sl} min
 • Median timeout: {median_min_to_expiry} min

🧠 WHY THIS SETUP
 • {reason_1}
 • {reason_2}
 • {reason_3}
 • {reason_4}

📎 SIGNAL_ID: {signal_id}
```

**Medal rules** (base 3, adjusted):
- Start at 3 stars.
- +1 if contract badge = Normal AND both external checkers clean.
- +1 if edge is LIVE (not SHADOW) AND has n ≥ 50 resolutions.
- −1 if dev wallet > 5%, or sniper hold > 40%, or Nakamoto < 5.
- −1 if MEV risk = HIGH.
- Clamped to [1, 5].

**Direction rendering:**
- `LONG` → 🟢 LONG
- `SHORT_ADVISORY` → 🟠 CLOSE-LONG (advisory) — WHY block explicitly states "no native short on this venue"
- `SHORT_PERP` → 🔴 SHORT (external perp) — WHY block names the venue

**Resolution lifecycle:** original card is replied-to (Telegram `reply_to_message_id = tg_message_id`) with one of:

```
✅ TP1  {SYMBOL}   {R:+.2f}R   in {minutes}m
 → SIGNAL_ID: {signal_id}
```
```
❌ SL   {SYMBOL}   {R:+.2f}R   in {minutes}m
 → SIGNAL_ID: {signal_id}
```
```
⌛ EXPIRED  {SYMBOL}   {R:+.2f}R   final @ ${final_price}
 → SIGNAL_ID: {signal_id}
```
```
✋ CHASED  {SYMBOL}   operator note: {note}
 → SIGNAL_ID: {signal_id}
```

### 7.2 Style B — Daily digest (20:00 UTC)

```
🔮 CodeOracle Daily Digest — {utc_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ ENGINE
 • Last beat:   {last_beat_utc}
 • Cycles 24h:  {cycles_total} ({cycles_ok} ok / {cycles_fail} fail)
 • Universe:    {tokens_covered} tokens ({sol_count} SOL / {tok_count} tokenized)
 • Sources ok:  {sources_ok}/{sources_total}   ⚠ {sources_degraded_list}

🌐 CHAIN REGIME
 • SOL:  {sol_regime_label}  ({sol_hot_narratives})
 • Tokenized: {tok_regime_label}

📈 MACRO BACKDROP
 • BTC.D: {btc_dominance}   ETH/BTC: {eth_btc}
 • Notes: {macro_note or "—"}

🎯 OPEN SIGNALS ({open_count})
 {for each open}
 • {medal} {DIR} {SYMBOL} — {edge_code} — {age_hours}h open — status: {live_status}

📊 RESOLVED 24h ({resolved_count})
 • Wins:      {win_count}    ({win_r_total:+.2f}R)
 • Losses:    {loss_count}   ({loss_r_total:+.2f}R)
 • Expired:   {expired_count}({expired_r_total:+.2f}R)
 • Total:     {total_r:+.2f}R
 {for each resolved}
 • {outcome_emoji} {SYMBOL} — {edge_code} — {r_multiple:+.2f}R — {post_mortem_line}

🔍 FUNNEL 24h
 • Universe entries: {universe_count}
 • Passed GATE ZERO: {passed_gate0}
 • Passed edge gate: {passed_edges}
 • Emitted:          {emitted}
 • Muted:            {muted}

🧪 SHADOW EDGES
 {for each shadow edge}
 • {edge_code} — n={resolved_shadow}/{n_target} — median R {shadow_r:+.2f} — CI [{ci_lo:+.2f},{ci_hi:+.2f}]

📁 PROMOTIONS
 • {promotion_summary_line}

⚠ HEALTH FLAGS
 {for each flag}
 • {flag_text}
```

**Escape rule:** every `{...}` in every template above resolves through `_esc()`. `test_esc.py` covers the entire field enumeration by parameterized test.

### 7.3 Muted-cards channel

Separate chat ID. Same Style A layout, prefixed:

```
🔇 MUTED — {mute_reason}
{full setup card unchanged}
```

Mute reasons: `EMISSION_CAP_HIT` (5/24h), `DUP_24H`, `SLIP_EXCEEDS_LIMIT`, `HONEYPOT_FLAG`, `SHADOW_MODE`, `EDGE_KILLED`.

---

## 8. Universal Discipline Application

Each principle from `_bootstrap/UNIVERSAL_DISCIPLINE.md` mapped to enforcement in CodeOracle:

| Discipline principle | CodeOracle enforcement |
|---|---|
| **Additive-only** (§I.1) | Every DB migration `IF NOT EXISTS` / `ADD COLUMN` only. Edges are new modules, never modify signatures of existing edges. New GATE ZERO checks cascade after existing ones. Style A card additions go into new sub-sections wrapped in try/except; existing sections untouched. |
| **Kill-switch every feature** (§I.2) | Env-var inventory in §5.6. `scripts/verify_kill_switches.py` asserts every switch actually cuts its path. Every commit message adding a feature names the switch. |
| **Backtest before live** (§I.3) | Every edge has `research/pre_reg_<E>.md` committed BEFORE first SHADOW signal. Frozen SHA-256 stored in `edges.prereg_sha256`. Promotion decision is CI + threshold gate; rejection = PARK not "loosen threshold." |
| **Try/except non-critical** (§I.4) | Digest sub-sections, ONCHAIN enrichment fields, TYPICAL block, PRIOR call reference — all wrapped in try/except so field-level failure drops the field, not the card. Signal core (levels, direction, edge, symbol) is NOT try/except — a failure there means the signal is malformed, and it must be caught in tests. |
| **Self-audit before ship** (§II) | Pre-commit checklist in `docs/AUDIT.md` (create week 1). Every commit that touches `telegram/formatter.py` or `digest_formatter.py` runs `tests/test_esc.py`. Every commit that touches an edge module runs the edge-specific pre-reg-consistency check. Every commit that touches migrations runs `verify_kill_switches.py`. |
| **Reviewer-stance prompt** (§II) | In `docs/AUDIT.md`: "before commit, read the diff as reviewer. Ask: what's weak?" |
| **STOP discipline** (§II) | If tests fail, don't ship. If pre-reg doc isn't committed, don't SHADOW-fire. If kill switch verify fails, don't merge. Enforced via CI later; enforced by discipline now. |
| **Markup escape** (§III) | Central `telegram/_esc.py`. `tests/test_esc.py` iterates every field of Style A and Style B, injects `<script>alert(1)</script>&amp;` and Telegram-special chars, asserts escaped in output. Any new field added to a card MUST have a corresponding test row added — enforced by a `docs/AUDIT.md` checklist item. |
| **Don't ask micro-decisions** (§IV) | Constants inlined in this doc — thresholds, cadences, medal rules, drag hurdles chosen with reasoning. §11 (Open Questions) contains ONLY philosophy/capital/calendar items. |
| **Bare-verb consent** (§IV) | Operator says "go" → ship. No re-confirmation. |
| **Honest closure** (§IV) | End-of-session self-check: "would I cite this in a month?" If no → mark low-value, do not ship. Digest surfaces edges with low accept-rate — auto-park kicks in. |
| **Preserve state — flag when endangered** (§IV) | If a session is asked to modify `_bootstrap/*` or the frozen pre-reg files: STOP, warn, escalate. Those are canonical. |
| **Verify before acting on internal sources** (§IV) | Before implementing something from a doc-referenced file, `ls` / `git log` verify the referenced file still exists and matches. |
| **Automated capture over manual** (§V) | Operator does NOT manually input signal data. All capture is automated. The one manual input allowed (`CHASED` note) is optional and post-hoc. |
| **Fact-check state before "fine"** (§V) | `audit/heartbeat.py` writes a row per cycle. Digest freshness alarm fires at > 60 min without new beat. `stale_alarm.py` runs every scanner cycle. |
| **Loop discipline (Kopadze)** (§V) | Every scheduled task follows: (1) manual run verified → (2) saved as script → (3) wrapped with gate + kill switch → (4) THEN registered in Task Scheduler. `docs/AUDIT.md` includes the 4-box gate check for each. |
| **Breadth = compounding** (§VI) | Edge catalog favors 3 orthogonal mechanical edges over one polished edge. |
| **Research only on request** (§VI) | Do not proliferate `research/exploration_*.md` files unless operator asks. Backlog edges live in this doc, not standalone files. |
| **Backup before risky ops** (§VI) | Before any migration that renames/drops, before any restructure: push a commit checkpoint. |
| **Edit-vs-append safety** (§VI) | Windows CRLF/LF: prefer `>>` append idiom in bash for large-file appends. |
| **Stay in project lane** (§VII) | Never read from `C--Users-farha-OneDrive-Desktop-bluechipsignal` or `shitcoinmaster`. Cross-project work = paste-relay only. |
| **Identity persistence** (§VII) | `.claude/settings.json` sets `statusLine: printf '\033[36mCodeOracle\033[0m'` and `SessionStart` hook renames session title to "CodeOracle". This is a day-1 task. |
| **Relay format for cross-AI** (§VII) | If a task requires Pythia or mm-radar AI action (e.g., de-dup a token now listed on Bitget spot), produce a `========== BEGIN [Pythia] RELAY ==========` block for operator to paste. |
| **Windows / OneDrive avoidance** (§VIII) | Code, venv, logs, DB data — none under any OneDrive path. Enforced by refusing to run if `C:\CodeOracle` resolves to a OneDrive-synced path (add check to `scripts/bootstrap_check.py`). |
| **`.claude/settings.json` conventions** (§VIII) | Committed. `.claude/settings.local.json` gitignored — Telegram tokens and API keys go in `.env`, not settings. |
| **Never allowlist Python/Node wildcards** (§VIII) | `.claude/settings.json` `permissions.allow` entries are narrow: `Bash(python scripts/run_*.py)` not `Bash(python *)`. |

---

## 9. First-Week Milestones

Day-by-day from empty repo to first SHADOW E1 signal fired to Telegram. Each day is ~4–6 hours of focused work. Each day ends with the operator able to see something concrete.

### Day 1 — Foundation

- Init git repo at `C:\CodeOracle` (not OneDrive; verify path).
- `.gitignore` (`.env`, `logs/`, `.venv/`, `__pycache__/`, `.claude/settings.local.json`).
- Python 3.11 venv at `C:\CodeOracle\.venv`.
- `requirements.txt`: psycopg[binary], httpx, python-dotenv, yfinance, pandas-market-calendars, pytest, tenacity.
- `.claude/settings.json` with `statusLine` (CodeOracle) + `SessionStart` hook.
- `.env.example` per §5.5. `.env` created locally with real values.
- Local Postgres — DB `codeoracle`, user `codeoracle`.
- Run `001_init.sql`, `002_signals.sql`, `003_ops.sql` migrations.
- `scripts/bootstrap_check.py` — verifies venv, DB connectivity, no OneDrive path, all env vars present. Exits non-zero if anything wrong. Run it; it passes.
- Commit: `feat: bootstrap repo + schema`.

### Day 2 — Ingest + universe

- `ingest/bitget_onchain.py` — first attempt at official API (try common Bitget REST endpoints). If none exists for the Onchain board, HTML scrape with polite `User-Agent` and 15 min cache. Snapshot returns list[TokenRow].
- `ingest/dexscreener.py` — token enrichment by address.
- `universe/snapshotter.py` — combines the two, writes `universe_snapshots` + `token_states` rows.
- Manual run: `python -m src.universe.snapshotter --chain solana` → prints token count, writes rows.
- Commit: `feat: universe snapshotter (SOL v0)`.

### Day 3 — GATE ZERO + Helius enrichment

- `ingest/helius.py` — holder distribution, dev-wallet identification.
- `universe/survivorship.py` — implements §2.4 gates, writes `survives_gate0` + `fail_reasons`.
- Manual run: shows N tokens surviving, M failing with reasons.
- Unit test: known-good token passes, known-rug token fails with correct reason set.
- Commit: `feat: GATE ZERO + Helius holder enrichment`.

### Day 4 — E1 pre-reg + evaluator + SHADOW plumbing

- Write `research/pre_reg_E1.md` — the full pre-reg per §4.E1. Commit before any code that emits an E1 signal.
- SHA-256 the file; insert `edges` row for E1 with `status='shadow'` and `prereg_sha256`.
- `edges/base.py` + `edges/e1_holder_concentration.py`.
- `signals/composer.py`, `signals/dedup.py`, `signals/emission_gate.py`.
- Wire scanner to iterate active edges; write to `shadow_log` (NOT `signals` — that's LIVE only).
- Test: synthetic token that meets E1 criteria produces a shadow_log row.
- Commit: `feat: E1 SHADOW (holder concentration)`.

### Day 5 — Telegram formatter + `_esc` + regression tests

- `telegram/_esc.py` — 5-line wrapper on `html.escape`.
- `telegram/formatter.py` — Style A per §7.1. Every field routed through `_esc`.
- `telegram/sender.py` — httpx POST to Bot API with tenacity retries.
- `tests/test_esc.py` — every field name from §7.1 gets a row; injects `<script>alert(1)</script>&amp;<b>bad</b>`, asserts output is escaped in the rendered card. NO exceptions.
- `EMISSION_DISABLED=true` still by default. `SIGNAL_EMISSION_DISABLED=true` (SHADOW-only). Muted-cards chat created.
- Commit: `feat: telegram formatter + xss regression suite`.

### Day 6 — Resolver + scheduler

- `resolver/open_scanner.py` — for each row in `signals` (or `shadow_log` in SHADOW), poll current price; if TP1 hit → write `resolutions` row + reply to Telegram card; if SL hit → same; if window elapsed → EXPIRED.
- `resolver/expirer.py` — separate 4h expirer for missed cases.
- `audit/heartbeat.py`.
- `scripts/register_tasks.ps1` — registers the 8 tasks from §5.4. Idempotent.
- Manual dry-run per task. Verify heartbeats land.
- Commit: `feat: resolver + Task Scheduler registration`.

### Day 7 — First SHADOW E1 signal + digest skeleton

- Flip Solana scanner ON in Task Scheduler.
- Wait for the first E1-eligible token in the universe.
- SHADOW signal writes to `shadow_log` AND to muted-cards Telegram chat (so operator can see the card).
- `digest/daily_digest.py` — v0 skeleton (engine + funnel + shadow status blocks only).
- Register `CodeOracle_Digest` task for 20:00 UTC.
- Manual digest run: sends a real message.
- Day-7 self-audit: reviewer-stance pass on all code from days 1–7. Check for missed `_esc`, missed kill switch, missed try/except, hardcoded threshold that should be an env var.
- Commit: `feat: daily digest v0 + week 1 audit`.

**Week 1 exit criterion:** a real SHADOW E1 signal has appeared in the muted-cards Telegram chat, referencing a real Bitget Onchain token, with all fields rendered, all fields escaped, resolver running, heartbeat rows accumulating, digest fired.

---

## 10. First-Month Milestones

### Week 2 — E4 + BSC/ETH/Base

- Write `research/pre_reg_E4.md`. Commit before code.
- `ingest/pump_fun.py` — pump.fun graduation event feed.
- `edges/e4_liquidity_migration.py` — SHADOW.
- Expand universe to BSC + ETH + Base via DexScreener (Solana Helius stays SOL-only; other chains use DexScreener baseline only for now).
- `ingest/rugcheck.py` — Solana contract-risk cross-check.
- Muted-cards channel starts showing E4 SHADOW cards where relevant.
- Digest v1 — full section coverage per §7.2.

### Week 3 — E9 tokenized-stock arbitrage

- Write `research/pre_reg_E9.md`.
- `universe/tokenized_stock_map.py` — hand-populate the mapping table (~20 entries to start).
- `ingest/yfinance_client.py` — underlying price fetcher; `pandas-market-calendars` for holiday awareness.
- `edges/e9_tokenized_weekend.py` — SHADOW.
- Weekend Sun 22:00 UTC job schedule.
- Market-hours gate module.
- First weekend cycle: at least one E9 SHADOW candidate emerges.

### Week 4 — E1 promotion decision + drift monitor

- E1 SHADOW should have accumulated n ≥ 15–20 resolved signals by end of week 4 (assuming 5–8 SHADOW signals/week for E1 candidates — depending on universe flow).
- If n ≥ 30 reached: run pre-registered promotion decision per §4.E1. Honor verdict.
- `audit/drift_monitor.py` — 30d rolling R + CI for LIVE edges (initially empty, but plumbing ready).
- Weekly retrospective note: `research/retro_week_4.md` — what worked, what surprised, what to iterate. Operator-authored input welcome.
- Universe survivorship report — % of tokens from week-1 snapshot still in universe today.
- Decision point: promote E1 to LIVE, keep in SHADOW pending more n, or PARK.

**Month 1 exit criterion:** three edges (E1, E4, E9) have each fired ≥ 5 SHADOW signals with resolution data collected; E1 has reached its pre-registered promotion decision point and the verdict has been applied honestly. Digest is producing a full report daily. Heartbeat has zero > 60 min gaps. No `_esc` bugs shipped.

---

## 11. Open Questions for Operator

Only philosophy / capital / calendar. Technical constants are decided inline throughout this doc.

1. **Initial capital.** MISSION brief assumes $50–$200 to start. Confirm the specific number so `POSITION_DEFAULT_USD` and `GATE_LIQ_MIN_USD` can be calibrated. Recommendation absent input: start at $100 nominal, `POSITION_DEFAULT_USD=15`, `GATE_LIQ_MIN_USD=50000`.

2. **Escalation triggers.** At what proven track record does capital move up? E.g., "after 30 resolved LIVE signals with mean R > +0.3, add $100"? Recommendation absent input: define after E1 promotion.

3. **Telegram channels.** Reuse an existing personal channel or spin up dedicated `@codeoracle_live`, `@codeoracle_muted`, `@codeoracle_digest`? Recommendation: 3 dedicated private channels; operator invites self only.

4. **Weekend / vacation behavior.** When operator is unavailable, do signals keep firing (operator reviews later) or pause? Recommendation: keep firing (auto-resolvers handle exits); operator can flip `SIGNAL_EMISSION_DISABLED=true` before travel.

5. **Digest UTC hour.** Default 20:00 UTC = 23:00 Istanbul (evening). Adjust?

6. **Calendar events next 12 weeks.** Are there windows where the operator wants CodeOracle silenced (personal calendar, Ramadan observance, professional-license periods)? Feed into a `silence_calendar` env-driven schedule.

7. **SHORT signals — advisory only or external-perp routing?** MISSION frames SHORT as advisory (close longs) or external perp. Which venue does the operator use for shorts if any? (Impacts E5/E6/E9 SHORT-mode card content.)

8. **Sibling-project data sharing.** If Pythia already has a smart-money wallet list for its edge, is a read-only export usable here, or does CodeOracle build an independent list? Cross-project handoff would use the relay format from §8.

9. **Auto-trader trigger conditions.** MISSION brief mentions progression to a small-capital auto-trader after edge is proven and Bitget Onchain has an API. Confirm: is API existence a hard prerequisite, or would operator accept broker-agent wrapping (e.g., a bot signing txs on a self-custodied wallet)?

10. **Cadence of retrospectives.** Weekly `research/retro_week_N.md` — is that the right cadence, or monthly? Recommendation: weekly for the first month, biweekly thereafter.

---

## Appendix A — First-day bootstrap checklist (copy-paste)

```
[ ] path is C:\CodeOracle (NOT OneDrive)
[ ] git init done, .gitignore committed
[ ] Python 3.11 venv at .venv
[ ] requirements.txt installed
[ ] Postgres role + DB created
[ ] migrations 001/002/003 applied
[ ] .env populated (schema in .env.example)
[ ] .claude/settings.json committed (statusLine + SessionStart)
[ ] scripts/bootstrap_check.py exits 0
[ ] first commit: "feat: bootstrap repo + schema"
```

## Appendix B — Pre-reg document skeleton (research/pre_reg_<E>.md)

```
---
edge_code: E?
version: 1
status: shadow
created: <UTC-date>
frozen_sha256: <computed after commit>
---

# Pre-registration — Edge <name>

## Hypothesis
<one-sentence testable claim>

## Mechanism
<why this should work>

## Trigger
<precise criteria — no ambiguity>

## Direction / entry / stop / TP1 / thesis window
<precise>

## Sample size
n = ?

## Test statistic
<bootstrap CI method, N resamples>

## Decision threshold
<exact numeric threshold — Bonferroni-corrected p and R threshold>

## Resolution rule
<what constitutes TP1, SL, EXPIRED, CHASED, INVALID>

## Exclusions
<pre-registered — no post-hoc filtering allowed>

## Failure mode + PARK plan
<what triggers PARK, and what re-eval trigger unlocks a revisit>

## Kill switch
EDGE_E?_DISABLED
```

## Appendix C — Card-render checklist (for the person adding a new field)

```
[ ] Field routed through _esc()
[ ] tests/test_esc.py parameterized row added
[ ] Field optional? Guarded with try/except if computation may fail
[ ] Field name in card_json JSONB — auditable after emission
[ ] Docs updated in this file §7.1 or §7.2
[ ] Muted-cards path also renders correctly (same formatter)
```

---

**End of Startup Package v1.0.** Version 1.0 — founding session, 2026-07-10.

---

# ADDENDUM v1.1 — 2026-07-10 probe revisions

Applied after the founding-session data-source probe (see `research/data_source_probe.md` for evidence). This ADDENDUM is authoritative where in conflict with the body above; the original text is preserved for audit trail per additive-only discipline. Future sessions should read both body and ADDENDUM; when body says X and ADDENDUM says NOT-X, ADDENDUM wins.

## ADD-1: Bitget Onchain data source — DEFERRED (body §3.1 source #1)

Bitget provides **no documented public API** for the Onchain venue. Confirmed via: empty React hydration cache, all 9 candidate endpoints returned 404, api-doc SPA lists spot only, no GitHub docs repo, JS-bundle URLs opaque. See `research/data_source_probe.md` §1.

**v1 behavior:** `ingest/bitget_onchain.py` is NOT implemented in v1. Universe roster comes from DexScreener chain-filtered search (ADD-2). Bitget-specific fields (contract-risk badge, trading-risk badge, Bitget-native volume/liq) are UNAVAILABLE in v1 signal cards — render as "n/a" in the ONCHAIN block.

**Reactivation path:** Operator captures the Onchain-page XHR endpoint via Chrome DevTools (F12 → Network → filter XHR, reload `bitget.com/asia/on-chain/`, find the roster-populating request, share URL + headers + sample response). Then Bitget ingest is added back in a follow-up cycle, additively.

## ADD-2: DexScreener promoted to primary universe source (body §3.1 source #2)

DexScreener is now the roster + price + liquidity + volume + age source for all chains in v1 scope. Response shape verified — richer than assumed (per-pair chainId, priceUsd, liquidity.usd/base/quote, volume.{m5,h1,h6,h24}, txns.{m5,h1,h6,h24}.{buys,sells}, priceChange.{m5,h1,h6,h24}, fdv, marketCap, pairCreatedAt). Rate limit ~300 req/min uncontested.

**Universe query pattern (v1):**
- Roster discovery: `GET /latest/dex/search?q={chain-keyword}` — with `User-Agent: Mozilla/5.0` header (403 without).
- Per-token enrichment: `GET /latest/dex/tokens/{addr}` returns all pairs across all chains; filter locally by target chain.
- Best pool per token = pair with highest `liquidity.usd` on the target chain.

**`ingest/bitget_onchain.py` in the module map** (body §5.1) is renamed to `ingest/dexscreener.py` with expanded scope: roster + enrichment. The original `dexscreener.py` module is folded in.

## ADD-3: GATE_LIQ_MIN_USD tightened $50k → $100k (body §2.4, §5.5)

Without Bitget's curation, the universe pulled from DexScreener alone is much larger and dirtier. Compensate by raising the liquidity floor.

- **New default:** `GATE_LIQ_MIN_USD=100000` (was 50000).
- Effect on §6.3 slippage rule: at `POSITION_DEFAULT_USD=15`, slip against $100k pool ≈ 15 bps — comfortable margin.
- Tighten further as capital grows per body §6.10.

## ADD-4: Contract-risk gate — RugCheck/TokenSniffer only in v1 (body §6.2)

Since Bitget badges are unavailable in v1, the contract-risk gate uses external checkers as the sole authority (not the "cross-reference against Bitget's own badge" pattern in the body).

**v1 gate rule:**
- SOL tokens: RugCheck.xyz clean → pass. Any scam-flags → veto.
- Non-SOL tokens: TokenSniffer clean → pass. Any scam-flags → veto.
- BOTH checkers unreachable > 60 min: treat as scam-flag (fail safe).
- GoPlus Labs added as tertiary fallback (defer integration to week 2).

When Bitget access is added back (ADD-1 reactivation), the body §6.2 four-tier gate resumes.

## ADD-5: E6 (Contract-risk badge downgrade edge) → BACKLOG (body §4 E6)

E6 depends on polling Bitget's badge state per token per cycle. Without Bitget access, E6 has no signal source.

**v1.1 SHADOW roster** (revised): E2 (whale-buy), E5 (LP-unlock). No E6.
**Backlog:** E6 reactivates when Bitget access returns.

## ADD-6: Tokenized-stock inclusion — `{TICKER}x` naming convention (body §2.3)

Discovery: Backed Finance's xStocks roster uses the convention `{TICKER}x` (e.g., AAPLx, TSLAx, NVDAx, GOOGLx, MSFTx, COINx). Confirmed all 6 candidates return matching Solana pairs on DexScreener.

**v1 mapping rule:** For any Solana token with symbol matching `^[A-Z]{1,5}x$`, strip trailing `x` and treat the remaining ticker as the underlying US equity. Verify by fetching from yfinance — if underlying returns valid OHLC, the mapping stands. Exceptions are logged for hand-review in `tokenized_stock_unmapped`.

**Roster is discoverable programmatically** — no hand-populated mapping needed for v1. The `tokenized_stock_map` table becomes a cache/override layer, not the primary lookup.

**Liquidity floor for tokenized stocks:** apply the same `GATE_LIQ_MIN_USD=100000` floor. AAPLx (best pool $67k) fails; NVDAx / TSLAx / COINx / GOOGLx / MSFTx pass. E9 sample-size implication: uneven per-symbol coverage is expected.

## ADD-7: E1 authenticity metric — DexScreener proxy (body §4 E1 data deps)

The body describes E1 authenticity via Helius transaction-level buyer extraction (unique-buyer/USD-volume ratio). Helius Enhanced v0 is paid-tier only on free account — not available in v1 without upgrade.

**v1 substitute (DexScreener-derived):**
- **Trade-count velocity:** `txns.h24.buys / volume.h24_usd` — high-authenticity tokens have many small buys per dollar of volume; wash-heavy tokens have few large trades.
- **Buy/sell balance:** `txns.h24.buys / max(txns.h24.sells, 1)` — extreme skew flags manipulation.
- **Median-trade proxy:** `volume.h24_usd / (txns.h24.buys + txns.h24.sells)` — micro-trade size distribution proxy.

E1 pre-registration (body §4 E1) uses these proxies at signal time; the trigger criterion "holder velocity > median for chain last 24h" is replaced with:
- "trade-count velocity > median for chain last 24h" (same rank-order intent, different measurement).

The proxy replacement is documented in `research/pre_reg_E1.md` when that file is authored, so the pre-reg is frozen against the v1-actual measurement, not the body's aspirational Helius-Enhanced measurement.

## ADDENDUM env-var changes to §5.5 `.env.example`

Add / change:
```
# CHANGED per ADDENDUM v1.1:
GATE_LIQ_MIN_USD=100000        # was 50000

# REMOVE (no longer used in v1):
# SOURCE_BITGET_DISABLED — Bitget ingest module doesn't exist in v1
# EDGE_E6_DISABLED — E6 not in v1.1 SHADOW roster

# ADD:
SOURCE_RUGCHECK_DISABLED=false
SOURCE_TOKENSNIFFER_DISABLED=false
```

## ADD-8: Dead-token filter reframed from vol/mcap to vol/liq (body §2.4)

Empirical Day-3 finding: `GATE_VOL_MCAP_RATIO_MIN=3.0` incorrectly rejected 3/3 otherwise-qualifying tokens (CATWIF top10=29%, tolywifhat top10=22%, both 1000 holders, both in E1 age window). These tokens have high mcap ($50M+) relative to their pool depth, so vol/mcap is <<1 even during healthy $700k+ daily volume.

The plan's stated intent was "dead-token filter — reject tokens that traded once then died" (edge guide Part 4). The correct primitive for THAT intent is **pool turnover**: `vol_24h / liq_usd >= 1.0` means the pool has traded through at least once in 24h. A truly dead token (one trade, then silence) has vol close to 0 while its pool still exists — this filter catches it. An established meme with $50M mcap and $200k pool has vol/liq of 4–25× — it passes.

**Change:**
- `GATE_VOL_MCAP_RATIO_MIN=3.0` → **`GATE_VOL_LIQ_RATIO_MIN=1.0`**
- Env var renamed; downstream code updated
- Body §2.4 row "24h volume ≥ 3× current market cap" is superseded by "24h volume ≥ 1× primary-pool liquidity"

**Confirmation:** re-run showed 2 survivors of 44 (was 0/44) — realistic recovery of the E1 candidate universe.

## ADDENDUM version log

- v1.1 — 2026-07-10 — probe-driven revisions after founding session
- v1.1 patch — 2026-07-10 — ADD-8 empirical vol/liq reframing after Day-3 run

## ADDENDUM Week-1 milestone changes to §9

- **Day 2 (Ingest + universe):** replace "`ingest/bitget_onchain.py`" bullet with "`ingest/dexscreener.py` — universe roster via `/dex/search`, per-token enrichment via `/dex/tokens/{addr}`, chain filtering to SOL in v1."
- **Day 3 (GATE ZERO + Helius enrichment):** unchanged. Helius verified working (§5 of probe doc).
- **Day 4 (E1 pre-reg + evaluator):** author `research/pre_reg_E1.md` with the ADD-7 DexScreener-proxy authenticity metric, not the body's Helius-Enhanced metric. Freeze the SHA-256 of the DexScreener-proxy version.

## Files created / touched during probe

- `.env` — Helius key stored (gitignored)
- `.gitignore` — created
- `research/data_source_probe.md` — full probe evidence
- `_probe/` — raw response captures (gitignored)

---

If you are a fresh Claude reading this: your next action is to read `_bootstrap/UNIVERSAL_DISCIPLINE.md` in full (if you haven't already), then check `~/.claude/projects/C--CodeOracle/memory/` for any project-specific memory left by prior sessions. Then, and only then, act on the operator's request.
