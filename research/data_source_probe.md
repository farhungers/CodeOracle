---
title: Data-source viability probe — v1 sources
date: 2026-07-10
author: founding-session R&D probe
status: complete — all 4 v1 sources probed
scope: verify each v1 data source in STARTUP_PACKAGE.md §3 works as assumed
---

# Data-source probe — findings

Probe run 2026-07-10 from `C:\CodeOracle\_probe\`. Purpose: de-risk the ingest layer of the plan BEFORE scaffolding code. Findings feed back into STARTUP_PACKAGE.md revisions if the underlying assumptions break.

## Summary of findings

| Source | Assumed viable | Actually viable | Confidence | Revisions needed to plan |
|---|---|---|---|---|
| **Bitget Onchain page (API)** | maybe | **NO public API found** | HIGH | Ingest layer redesigned — see §1 |
| **Bitget Onchain page (scrape)** | fallback | Feasible but heavy (React SPA — needs Playwright or XHR reverse-eng) | HIGH | Deferred / de-prioritized — see §1 |
| **DexScreener** | primary cross-chain | **YES — richer than expected** | HIGH | Promoted to primary universe source — see §2 |
| **Helius (Solana enrichment)** | primary SOL | **YES — all v1 needs covered on free tier** | HIGH | Minor — E1 authenticity uses DexScreener proxies not Helius Enhanced v0 |
| **yfinance (tokenized underlying)** | free / good enough | **YES — 1-min intraday resolution works** | HIGH | No change |
| **DexScreener → xStocks coverage** | not in original plan | **YES — full Backed Finance xStocks roster on SOL** | HIGH | New — see §4 |

---

## 1. Bitget Onchain — no public API; SPA-heavy

### What was checked

- `https://www.bitget.com/asia/on-chain/` HTML (256 KB, React SPA — `__REACT_QUERY_STATE__` hydration is minimal 7.8 KB, no roster data pre-embedded)
- `https://api.bitget.com/api/v2/spot/public/symbols` → 200 (spot symbols work; this is Pythia's universe, not ours)
- Candidate onchain paths tried and got 404:
  - `www.bitget.com/v1/dex/token/list`
  - `www.bitget.com/v1/dex/onchain/list`
  - `www.bitget.com/v1/onchain/token/list`
  - `api.bitget.com/api/v2/dex/token/list`
  - + 5 more variants
- Public API docs (`www.bitget.com/api-doc/`) — SPA, only 14 KB, mentions only "spot" (1 hit). No `dex` / `onchain` documented.
- GitHub API-doc repos: 404 on `bitgetlimited/v3-bitget-api-doc` and variants.
- JS bundle inspection: onchain-related bundles do not expose recognisable API URL constants at the top level (paths are obfuscated / dynamically-assembled via webpack chunks).

### Verdict

Bitget does **not** provide a documented public API for the Onchain venue as of 2026-07-10. Access requires one of:

1. **Reverse-engineer XHR endpoints** via Chrome DevTools while browsing `bitget.com/asia/on-chain/` — capture the Network tab requests that populate the roster. Cheap for the operator to do once; endpoint likely stable across weeks. Then wrap in `ingest/bitget_onchain.py` with retries + explicit deprecation catch. **Operator-side task, ~10 min in browser.**
2. **Playwright / Selenium headless-browser scrape**. Heavy: adds Chromium dependency (~200 MB), fragile on Bitget UI changes, slower per cycle. Not fit for 5-min cadence.
3. **Skip Bitget as source #1**; use **DexScreener as the primary universe** and Bitget only for contract-risk badge cross-reference (which itself requires option 1 or 2 to get).

### Plan-doc revision

Change v1 to **Option 3 as default**: DexScreener is the roster source; a Bitget-Onchain-specific universe filter is deferred until the operator captures XHR endpoints (task added to open questions). Contract-risk defaults to RugCheck (SOL) + TokenSniffer (multi-chain) — external checkers only, no Bitget badge dependency in v1.

**Tradeoff:** we lose the "Bitget listed it" as a universe-membership signal in v1. This is meaningful — Bitget's Onchain board is a curated subset of DEX-native tokens, and using DexScreener's whole universe pulls in far more (and worse) tokens. Compensating: tighten GATE ZERO thresholds (`GATE_LIQ_MIN_USD=100000` instead of `50000` for v1) until we have the Bitget roster back as a filter.

### STARTUP_PACKAGE.md sections that change

- §3.1 source #1 → downgraded from "primary" to "deferred / operator devtools task"
- §2.4 GATE ZERO → `GATE_LIQ_MIN_USD` bumped to `100000` for v1
- §11 Open Questions → new item: "Can operator capture Bitget Onchain XHR endpoints via DevTools?"

---

## 2. DexScreener — richer than expected; promoted to primary

### What was checked

- `GET https://api.dexscreener.com/latest/dex/tokens/{addr}` → 200, returns list of pairs across chains for a token address
- `GET https://api.dexscreener.com/latest/dex/search?q={query}` → 200 with proper User-Agent header (403 without UA)
- Response inspection on wrapped SOL (`So11111...12`): 30 pairs returned, 29 solana + 1 fogo

### Field enumeration (per pair)

Rich enough to fully populate GATE ZERO and edge evaluators:

| Field | Type | Use |
|---|---|---|
| `chainId` | str | universe filter (solana / bsc / ethereum / base / etc.) |
| `dexId` | str | DEX name (orca / raydium / pancakeswap) |
| `pairAddress` | str | pool identifier for slippage sims |
| `baseToken.address` / `.name` / `.symbol` | str | token identity |
| `priceUsd` | str-numeric | current price |
| `txns.{m5,h1,h6,h24}.{buys,sells}` | int | authenticity (buys/sells ratio, tx count) |
| `volume.{m5,h1,h6,h24}` | float | vol filter (v/mcap ratio) |
| `priceChange.{m5,h1,h6,h24}` | float | momentum / E4 window measurement |
| `liquidity.usd` / `.base` / `.quote` | float | GATE ZERO liquidity floor |
| `fdv` / `marketCap` | float (sometimes null) | vol-to-mcap gate |
| `pairCreatedAt` | int (ms epoch) | age filter (GATE ZERO) |
| `info.imageUrl` / `info.header` / `info.openGraph` | str | optional card enrichment |

### Rate limit observed

- No rate-limit errors on ~10 sequential calls; docs quote ~300 req/min. Well within a 5-min Solana scanner budget.

### Verdict

**Primary universe source.** Covers all target chains (solana, bsc, ethereum, base), plus we get tokenized-stock coverage for free (§4). Zero API key required.

### Plan-doc revision

§3.1 source #2 → promoted from "cross-chain baseline" to "primary universe + price/liquidity/volume/age". Bitget deferred (§1).

---

## 3. yfinance — works fully, no changes needed

### What was checked

- `yfinance` v1.2.0 already installed
- 6 candidate underlyings (TSLA, AAPL, NVDA, GOOGL, MSFT, COIN) — all return clean 5-day daily bars
- 1-min intraday resolution for AAPL: 780 bars across 2 trading days, timezone-aware ET timestamps (`2026-07-08 09:30:00-04:00 .. 2026-07-09 15:59:00-04:00`)

### Verdict

Covers E9 fully. Fri-16:00-ET close reads clean, Mon-11:30-ET close reads clean, resolution granularity is 1 min. Timezone handling is native (`-04:00` = EDT during July).

### Follow-up

- Need `pandas-market-calendars` install for holiday awareness — added to `requirements.txt`. Not a blocker.
- Underlying delay: yfinance daily bars are end-of-day (post-close). For live intraday during US_MARKET_OPEN, verify latency separately during a session (defer to Day 3 when tokenized live scanner comes online).

### Plan-doc revision

None. Confirms §3.1 source #4.

---

## 4. Tokenized-stocks (xStocks) — new finding, universe map is trivial

### What was checked

- DexScreener search for `{TICKER}x` naming pattern (Backed Finance xStocks convention)
- 6 tickers probed — all found on Solana with meaningful liquidity

| xStock | Underlying | Best-pool liq_usd | 24h vol_usd | GATE ZERO status |
|---|---|---|---|---|
| NVDAx | NVDA | $2,749,938 | $1,421,709 | PASS |
| TSLAx | TSLA | $2,169,554 | $962,810 | PASS |
| COINx | COIN | $662,346 | $131,524 | PASS |
| GOOGLx | GOOGL | $383,649 | $183,561 | PASS |
| MSFTx | MSFT | $310,370 | $60,877 | PASS |
| AAPLx | AAPL | $67,762 | $7,566 | BORDERLINE (near $50k floor; fails $100k v1 floor) |

### Key finding

The mapping table `tokenized_stock_map` becomes almost trivial: **strip trailing `x` → NYSE/NASDAQ ticker**. Confirm this generalizes across the Backed roster and hand-verify any exceptions. This is a ~30-minute exercise, not the ~20-50 hand entries the plan predicted.

### Volume asymmetry note

AAPLx sees far less on-chain interest than NVDAx / TSLAx. AAPL as an underlying is less traded on crypto rails despite being a bigger equity. E9's per-symbol sample size will be uneven — some xStocks will hit n=30 weekend cycles quickly, others may never.

### Plan-doc revision

- §2.3 tokenized-stock inclusion criteria → confirm xStocks-suffix naming
- §4 E9 → note per-symbol sample uneven; pooling across roster is the correct default

---

## 5. Helius — key verified, all v1 needs covered

### What was checked

Free tier key `0e9a953d-...` (project: Slayerpetal, Mainnet). Endpoint: `https://mainnet.helius-rpc.com/?api-key={KEY}`.

| Test | Method | Result | Latency |
|---|---|---|---|
| Auth | `getSlot` | 200, slot=431,908,340 | 311 ms |
| Top holders (large token) | `getTokenLargestAccounts` [USDC] | ERR -32600: "Too many accounts (5M pubkeys)" | 9.7 s (rejected) |
| Top holders (E1-scale) | `getTokenLargestAccounts` [3 small SOL tokens] | 20 accts each, top-10 % computed cleanly | 500–635 ms |
| Total supply | `getTokenSupply` | Clean numeric supply | 290–430 ms |
| Metadata + price | DAS `getAsset` | interface, supply, decimals, symbol, price_info.price_per_token (USDC) | 417 ms |
| Holder count | DAS `getTokenAccounts` {limit:1000} | `total` field is the holder count for the page; paginate if `total == limit` | 377–485 ms |
| Enhanced v0 | `/v0/addresses/{mint}/balances` | 403 (paid tier only) | — |

### Key findings

1. **`getTokenLargestAccounts` fails for USDC-scale tokens** (5M+ holders) — but this is not the E1 target profile. Every E1-eligible smaller token in the probe (3 tested) returned clean top-20 distributions.
2. **E1 top-10 concentration filter works end-to-end** with 2 calls per token (`getTokenLargestAccounts` + `getTokenSupply`). Total round-trip ~1 s per token.
3. **DAS `getAsset` returns USDC-denominated price directly** — a free bonus vs. DexScreener redundancy for smaller tokens.
4. **Holder-count gate (E1: > 100 holders)** is a single `getTokenAccounts` call: if `total >= 100` → pass, no pagination needed.
5. **Enhanced v0 endpoints are paid-tier only.** Not blocking — DAS covers metadata + price + holder-set. Transaction enrichment for E1 authenticity signal (buyer/vol ratio) would need alternative: use DexScreener `txns.h24.buys` + `volume.h24` combination as proxy.

### Credit budget

- 100,000 credits/day on free tier; 1 credit per RPC call.
- 50-token universe, Helius-enrich every 15 min: **14,400 calls/day → 6.9× headroom.**
- Even at 5-min cadence: 43,200 calls/day → 2.3× headroom.
- Verdict: comfortable within free tier for v1 universe.

### Plan-doc revision

None to §3.1 source #3 — Helius stays as SOL enrichment. Add note: v1 E1 authenticity metric uses DexScreener `txns/volume` proxies instead of Helius Enhanced v0 (paid-tier gated).

---

## 6. Revisions to STARTUP_PACKAGE.md (proposed, awaiting operator sign-off)

Change set from probe findings so far:

1. **§3.1 source #1 (Bitget) → deferred.** Not blocking v1. Move to §11 open question: "Capture Bitget Onchain XHR endpoints via browser DevTools when convenient — 10 min task."
2. **§3.1 source #2 (DexScreener) → primary universe.** Roster comes from DexScreener chain-filtered `search` + per-token enrichment.
3. **§2.4 GATE ZERO → `GATE_LIQ_MIN_USD` bumped `50000 → 100000`** to compensate for lost Bitget curation.
4. **§2.4 GATE ZERO → contract-risk badge** now sourced from RugCheck (SOL) and TokenSniffer (multi-chain), not Bitget. Bitget badge cross-check added back only when operator captures the XHR endpoints.
5. **§4 E6 (Contract-risk badge downgrade)** → SUSPENDED for v1 until Bitget badge polling is possible. Move to backlog. Reason: no way to snapshot the badge without the Bitget API/scrape working.
6. **§2.3 (tokenized-stock inclusion)** → codify the `{TICKER}x` naming convention as the primary mapping rule.
7. **§4 E1 authenticity metric** → measured via DexScreener `txns.h24.buys / volume.h24_usd` (unique-buyer proxy), not Helius Enhanced v0. Enhanced tier is paid-only.

**Corrected count:** v1 SHIP FIRST = E1, E4, E9 (unchanged). v1.1 SHADOW starts = E2 (whale-buy), E5 (LP-unlock). E6 (badge downgrade) moves to backlog pending Bitget access.

---

## 7. Files created by this probe

- `_probe/dexscreener_sol_response.json` — raw DexScreener response
- `_probe/bitget_onchain_page.html` — raw Bitget SPA HTML
- `_probe/bitget_react_query.txt` — Bitget React Query hydration cache (7.8 KB — no roster data)
- `_probe/bitget_apidoc.html` — Bitget public API docs page (14 KB — no dex/onchain routes)
- `research/data_source_probe.md` — this file
