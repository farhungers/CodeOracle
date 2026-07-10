---
title: On-chain signal-caller edge guide — curated domain knowledge for CodeOracle
date: 2026-07-10
type: strategic reference
audience: CodeOracle's founding Claude session designing STARTUP_PACKAGE.md
---

# On-chain edge guide

This document consolidates what a successful on-chain signal caller needs to know, curated specifically for Bitget's Onchain venue (emerging DEX tokens + tokenized stocks). Use it to inform every section of `STARTUP_PACKAGE.md`, particularly the Data-Source Inventory, Edge Hypothesis Catalog, Risk & Safety Layer, and Universe Definition sections.

Not everything here needs to ship in v1. Prioritize; sequence over the first-week / first-month milestones; leave the rest as backlog for future edge cycles.

---

## Part 1 — The venue and what makes it different

**Bitget Onchain is a pre-listing DEX aggregator experience.** Tokens on this board are DEX-native (Solana / BSC / ETH / Base / Morph / Monad). They are NOT on Bitget spot or futures. Some may graduate to spot listing later; most will not. This has several implications:

1. **No centralized order book.** "Bid wall" / "ask wall" concepts from CEX perp trading do NOT apply. The liquidity IS the AMM pool. Depth is quoted as "how much slippage does an $X order incur." Always convert your position size to slippage estimate BEFORE emitting a signal.
2. **No leverage.** Onchain trades are spot buys with real cash. Position sizing math is $ in / $ out, not $ margin × leverage. This changes stop-loss logic materially — the stop is where you sell for a realized loss, not where a liquidation engine touches you.
3. **No shorting native to the venue.** Bitget Onchain is buy-only. A "SHORT signal" on CodeOracle means one of: (a) advise the operator to close existing long exposure to that token, (b) advise external short via perp on another venue if the token is also listed there, (c) skip-and-wait signal if there's no short instrument available. Design the card schema to be explicit about which mode.
4. **Token mortality is high.** Median half-life of a launch-day meme coin is measured in days. The universe churns. Signals must account for tokens dying between emission and resolution — this is a design constraint, not an edge case.
5. **Fees are DEX fees, not exchange fees.** Swap fees on the AMM (typically 25 bps on Raydium / Uniswap V3-like) plus gas plus MEV. Round-trip drag on a small trade can be 100+ bps easily. Signals must clear this hurdle by more than a comfortable margin.
6. **MEV attacks are real.** Sandwiching, frontrunning, JIT liquidity — small trades on Solana with private RPC (Jito) mitigate but do not eliminate. Signal quality must survive expected MEV drag.
7. **Tokenized stocks are a separate universe** with different mechanics. They wrap an underlying US equity. Their edges include: weekend gap arb (crypto trades 24/7, US market doesn't), off-hours mean reversion, listing arbitrage vs. underlying spot, earnings-day volatility premium.

---

## Part 2 — Data source inventory (candidates for the Data-Source section)

### Bitget-native
- **Bitget Onchain page** (`bitget.com/asia/on-chain/`) — the canonical venue. Investigate whether they expose a public API. Their app clearly has: contract-risk badge, trading-risk badge, 24h volume, market cap, liquidity, holder count, price OHLC. If no official API, HTML scraping is possible but fragile. If they have API — priority 1 use it.
- **Bitget REST API** — for the roster of "which tokens are on the Onchain page today." Cross-reference against DEX indexers.

### Chain indexers (choose one or two per chain, redundancy is worth the ops cost)

**Solana** (highest priority — largest population on Bitget Onchain):
- **Helius** — full-featured Solana indexer. Free tier: 100k credits/day, enough for a scanner covering ~50 tokens at 5-min cadence. Paid tier if scaling. Best for enriched transaction data.
- **Birdeye** — Solana DEX aggregator + analytics API. Free tier good for OHLC + trending. Prices, holders, top wallets.
- **DexScreener API** — free multi-chain, includes Solana. Good for cross-chain unified queries. Rate-limited (~300 req/min).
- **Bitquery** — GraphQL multi-chain indexer, generous free tier. Excellent for whale-tracking queries.
- **Solana RPC** direct — Jito or QuickNode. For live transaction monitoring, not historical.

**BSC / ETH / Base / Morph / Monad**:
- **DexScreener** — covers all of these; use for baseline cross-chain uniformity
- **Moralis** — multi-chain, decent free tier
- **Alchemy** — reliable RPC + enriched APIs. Free tier generous.
- **GeckoTerminal** (CoinGecko's DEX product) — decent for pool metadata
- **DeFi Llama** — TVL, protocol-level flows (not per-token, but per-DEX flow context is useful)

### On-chain analytics (whale + wallet intelligence)
- **Arkham Intelligence** — free tier includes some labelled wallets. Best for entity attribution ("this wallet is a KOL", "this wallet is Wintermute").
- **Nansen** — the gold standard for wallet labels but paid ($150/mo minimum). Defer until proven edge justifies cost.
- **Debank** — free for individual wallet lookups. Good for verifying claims about specific whale movements.
- **Bubblemaps** — cluster visualization, free. Excellent for spotting connected-wallet coordination on new tokens.
- **RugCheck.xyz** (Solana), **TokenSniffer** (multi-chain), **GoPlus Labs** — contract-risk verifiers. Cross-reference with Bitget's own contract-risk badge.

### Social velocity
- **LunarCrush** — social score aggregation, paid tiers but has a free API tier
- **Twitter/X Premium API** — expensive; defer
- **Farcaster** (public API, free) — signal-rich for Base tokens
- **Telegram public group scraping** — legal grey zone; skip
- **Dune Analytics** — public dashboards for community-tracked whales; often free

### Tokenized stocks specific
- **Yahoo Finance** (via yfinance library) — free, US equity underlying prices, delayed 15min
- **Alpaca** — free tier includes real-time US equity data (limited)
- **IEX Cloud** — paid but reasonable; real-time equity
- **Underlying equity for Bitget tokenized roster** — build the mapping table manually; there are ~20-50 tokenized stocks max

### Selection principle
Do not integrate more than 3-4 sources in v1. Every source is an ops burden (API-key rotation, rate-limit handling, schema drift, downtime handling). Pick the minimum set that covers: (a) token discovery, (b) OHLC price data, (c) holder / whale data, (d) contract-risk data. Everything else is v2.

---

## Part 3 — Edge hypothesis catalog (candidates for the Edge Hypothesis section)

Rank these by (edge magnitude × ease-of-implementation × data-availability). Ship the top 3 in v1; rest go to backlog.

### High-conviction, well-documented in the on-chain literature

**E1 — Early holder-concentration anomaly**
- Mechanism: launched tokens where the top-10 holders own <40% AND holder count grew organically (not via airdrop farming) tend to survive the first-week mortality curve better. Combine with dev-wallet <5% and no unlocked LP → filter for "not-obviously-scam" tokens.
- Pre-reg: n=30 tokens surviving the filter, tracked 7 days from Bitget Onchain listing. Success = median survival > 7d + median R-return > 0.
- Data needed: holder distribution snapshot at emission; dev-wallet identification; LP-lock status.

**E2 — Whale-buy first-mover signal**
- Mechanism: a known "smart money" wallet buys a token before it hits Bitget Onchain trending. Follow-the-smart-money is a documented edge, but only for wallets with pre-labelled positive track record.
- Pre-reg: n=25 whale-tagged buys, follow-in signal within 15min, hold 4-24h. Success = median R > +0.3 with CI clear of zero.
- Data needed: whale wallet labels (Arkham free tier + community-sourced smart-money lists); mempool or block-level buy detection.

**E3 — Cross-chain narrative rotation**
- Mechanism: when a meme narrative (dogs, cats, AI, politics, etc.) heats up on chain A, similar-narrative tokens on chain B often lag by 24-72h. Rotation is a proven pattern in meme cycles.
- Pre-reg: define a narrative-cluster taxonomy; watch for cluster-A ignition; long cluster-B tokens 12-24h post cluster-A peak.
- Data needed: narrative-tag mapping (manual + LLM-assisted); cross-chain volume data (DexScreener).

**E4 — Liquidity-migration event**
- Mechanism: when a pump.fun-style token graduates from bonding curve to Raydium (Solana) or similar events on other chains, a predictable liquidity injection + price re-rating happens. The graduation event itself is a signal.
- Pre-reg: track pump.fun graduations; buy first 5min post-graduation with a tight stop; hold 1-4h.
- Data needed: pump.fun graduation event stream (public); Raydium pool creation detection.

**E5 — LP-unlock cliff**
- Mechanism: LP tokens locked for X days often see coordinated dump behavior at unlock time. Short (or exit long) 24-48h before public unlock date.
- Pre-reg: n=20 unlocks; measure -24h to +24h price change; success = median negative return.
- Data needed: LP-lock service data (Team Finance, PinkSale, UNCX); manual verification for now.

### Medium-conviction, novel

**E6 — Contract-risk badge downgrade**
- Mechanism: when Bitget flips a token from Normal → Warning, expect a coordinated dump within 1-6h. Even if the badge change is UI-only, Bitget users see it and react.
- Pre-reg: n=15 badge downgrades; measure -1h to +6h price impact; success = median negative move > 5%.
- Data needed: Bitget contract-risk badge polling; badge-change detection.

**E7 — Volume authenticity gap**
- Mechanism: on-chain volume that is largely wash (few unique buyers, high volume) is a bearish leading indicator vs. tokens with high unique-buyer velocity per USD of volume.
- Pre-reg: define a "buyer authenticity" metric (unique buyers per $100k volume). Compare top vs. bottom deciles over 7d holding; success = decile gap > 20%.
- Data needed: transaction-level buyer address extraction; wallet uniqueness within a rolling window.

**E8 — Sniper-cohort exit velocity**
- Mechanism: tokens where sniper wallets (first 5 buyers) have already exited profitably tend to have a cleaner runway for continued upside vs. tokens where snipers are still holding an overhang.
- Pre-reg: identify snipers per token; measure "sniper wallet %" at emission; run edge test on tokens where snipers have exited >80%.
- Data needed: transaction reconstruction for the first N transactions post-launch; sniper wallet balance tracking.

### Novel + operator-specific

**E9 — Tokenized-stock weekend arbitrage**
- Mechanism: tokenized US equities trade 24/7 on crypto rails; underlying trades M-F 9:30-16:00 ET. Weekend and off-hours price drift on the token often reverses at Monday market open. Fade the weekend move.
- Pre-reg: n=30 weekend closes on tokenized stocks; measure Friday-16:00-ET-to-Monday-9:30-ET drift; enter reverse position Sunday PM ET, close 2h after market open.
- Data needed: Bitget tokenized-stock roster + underlying-equity mapping; yfinance for underlying; a mapping table CodeOracle owns.

**E10 — Tokenized-stock premium/discount arb**
- Mechanism: tokenized stock trades at a premium or discount to its underlying (which trades on real US markets during market hours). Bounded arbitrage: when the tokenized version trades > 2% away from underlying during US market hours, expect mean reversion.
- Pre-reg: measure premium/discount time-series for 4 tokenized stocks over 30 days; identify natural bounds; short premium extremes, long discount extremes.
- Data needed: real-time equity price (Alpaca free tier); tokenized-stock price (Bitget or DEX).

### Discovery-mode candidates (backlog)
- Attention-decay curves (24-48h half-life for meme launches — buy the dip at hour 30)
- Realized loss / underwater cohort capitulation
- Bridge-inflow leading indicator (large CEX-to-DEX transfers)
- Failed-listing rejection (tokens that miss Bitget spot listing after Onchain hype often flush)
- New-holder acceleration (velocity of unique buyers as leading indicator)
- Dev-wallet drawdown (dev cashing out is a lagging indicator; leading = increased dev-wallet-to-CEX transfers)
- Coordinated basket-ignition (like mm-radar but for on-chain baskets — cross-token correlated pumps)

---

## Part 4 — Risk & safety layer

### Universe-entry gate (survivorship filter — GATE ZERO)

Before ANY edge evaluates a token, the token must pass survivorship:
- Liquidity > $50k both sides of the primary pool (raise threshold as capital grows)
- Contract-risk badge = Normal (Bitget's own signal — do not override)
- No mint authority OR mint authority provably renounced
- LP-lock status = locked (or verifiable burn)
- 24h volume > 3× current market cap (dead-token filter — reject tokens that traded once then died)
- Age > 6h AND < 30d (launch-day is a separate signal class; ancient dead tokens excluded)
- Holder count > 100 (avoid pure-scam single-wallet setups)

Tokens failing survivorship do not get signals. They may still be tracked in a "watchlist" table for future re-evaluation if they later pass.

### Slippage-adjusted position sizing

Never emit a signal where the operator's assumed position size would cause > 2% slippage against the current pool. Signal card must include: "at $X position size, expected slippage = Y%." If Y > 2%, either reduce recommended size or don't emit.

### MEV awareness

Signals with entry windows < 30 seconds are dangerous on non-Jito-protected Solana RPC and on public Ethereum mempool. Prefer entry windows > 1 min. Warn operator when the edge specifically requires fast entry.

### Contract-risk fallback

Even if Bitget's own badge says Normal, cross-check against RugCheck.xyz (Solana) or TokenSniffer (multi-chain). If BOTH external checkers show clean but Bitget says Warning → downgrade signal quality by 1 medal; do not veto. If external checkers show scam-flags → veto regardless of Bitget badge.

### Tokenized-stock market-hours gate

Signals on tokenized stocks must be explicit about market-hours state: `US_MARKET_OPEN` / `US_MARKET_CLOSED` / `WEEKEND`. Different edges apply in different regimes. E10 (premium-discount arb) requires US_MARKET_OPEN; E9 (weekend fade) requires WEEKEND transitioning to US_MARKET_OPEN.

### Kill-switch conventions

Every edge module gets an env var: `EDGE_E1_DISABLED=true` disables E1. Every data source gets a graceful-degradation path: if Helius fails, log + skip Solana-specific enrichment, continue on baseline DexScreener data. Never let a single data-source failure block the entire scanner cycle.

### Capital-scale awareness

At $100 capital, position size is $10-$25 per signal max. That fits inside the 2% slippage window of any survivable universe token. As capital grows, universe filter tightens (higher liquidity floor) so signal-emission universe naturally shrinks with capital growth — this is the correct default behavior, not a bug.

---

## Part 5 — Cadence + operating rhythm

### Scanner cadence
- Solana: 5-min cadence (heaviest volume, fastest signals)
- BSC / ETH / Base / Morph / Monad: 15-min cadence (slower narrative movement)
- Tokenized stocks during US market hours: 5-min cadence
- Tokenized stocks off-hours: 60-min cadence
- Daily digest: 20:00 UTC (aligns with operator's Istanbul evening — adjust in MISSION.md if operator has a preference)

### Signal-emission cadence
- Hard limit: no more than 5 setup cards per 24h to Telegram to preserve signal-to-noise
- Muted cards path exists (visible in a dedicated "muted-cards" chat/thread) — signals that fired the detector but did not clear the emission gate. Operator has visibility without noise pollution.
- Regime alerts (chain-level state changes): unlimited but rare

### Resolution cadence
- Every 15 min: resolve any open setups whose entry window has closed
- Every 4h: check if any open setups hit TP1 / SL
- Every 24h: expire setups past their thesis-time window with an EXPIRED resolution at final price

---

## Part 6 — Statistical discipline (mirrors Pythia's proven approach)

- Every edge is pre-registered BEFORE its first live SHADOW signal. Pre-reg doc lives at `research/pre_reg_<edge_code>.md`.
- SHADOW mode: signals fire to a shadow log, not to the main Telegram. Track for n≥20 resolutions.
- Bootstrap CI + Bonferroni correction across the family of concurrent edges.
- Promotion decision: SHADOW→LIVE only if CI clears zero AND the pre-registered promotion threshold is hit.
- LIVE mode: signals go to main Telegram + optional auto-execution.
- Ongoing monitoring: rolling 30-day performance, alert on drift.
- Kill decision: any LIVE edge with 30-day rolling mean R < 0 AND CI overlapping zero → auto-disable, park for retrospective.

---

## Part 7 — Anti-patterns (things that have killed similar projects)

1. **Ship-then-backtest.** Never. Pre-register first, ship after.
2. **Over-fit edges.** An edge tuned to 30 historical winners will regress to zero mean out-of-sample. Prefer robust mechanical edges (holder concentration, LP-lock) over indicator-stack tuning.
3. **Free-tier data source lock-in.** Every free tier gets rate-limited or discontinued eventually. Have a second source for every critical signal.
4. **Universe drift.** The Bitget Onchain roster changes daily. Cache the roster as a snapshot each scanner cycle, not a live query mid-cycle.
5. **Telegram formatting bugs.** HTML-escape every dynamic value. This has shipped the same bug three times in a similar project — do not repeat.
6. **Silent scanner failure.** If the scanner doesn't run for 6h, someone needs to know within 15 min. Heartbeat + digest-freshness monitor is non-negotiable.
7. **Manual data-capture dependencies.** If any signal requires the operator to manually input something to work, it will fail on the days it matters most. Automate capture or don't ship the feature.
8. **Confidence in on-chain data quality.** DEX transaction data is noisy — wash trades, MEV bots, contract self-buys. Every quantitative claim needs a "how was this measured" audit trail.

---

## Part 8 — Operator interaction principles (from the discipline export)

- Bare-verb replies from the operator = full consent. Ship.
- Terse senior tone. No filler summaries at end of every response.
- Windows environment; no OneDrive paths for code / venvs / logs / runtime.
- Sibling AIs exist for other projects (Pythia for bluechipsignal, mm-radar's AI for shitcoinmaster). Cross-project = research handoffs via operator relay, never direct.
- Preserve state. If a task threatens the project's coherence or principles: STOP + surface concern before executing.

---

## Part 9 — What to explicitly punt to v2 or beyond

- Multi-user support / auth
- Web dashboard (Telegram-first is the whole point)
- Auto-execution (defer until at least one edge has 30+ resolutions with proven LIVE profitability)
- Paid data source integration (defer until edge justifies cost)
- Complex NLP / LLM narrative-tagging (start with hand-labelled clusters, augment later)
- Cross-chain narrative rotation edge (E3) — punt to v2 unless the first-week milestones have room
- Novel edge discovery / research pipeline (this project is about executing pre-registered edges, not doing academic research)

---

## Closing frame

The way to make CodeOracle profitable is not to have the fanciest edge model. It's to:

1. Pick 3 mechanical edges rooted in on-chain data reality
2. Pre-register them honestly
3. SHADOW-track them with clean resolution rules
4. Promote the ones that clear statistical gates, kill the ones that don't
5. Present the promoted edges via Telegram cards a human can act on in 30 seconds
6. Iterate slowly — 1-2 new edges per month, not 10

That's the whole game. Everything else in `STARTUP_PACKAGE.md` should serve those six steps.
