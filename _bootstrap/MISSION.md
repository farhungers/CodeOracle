---
title: CodeOracle — mission, universe, output vision
date: 2026-07-10
type: project brief
---

# CodeOracle — mission brief

## Identity

**CodeOracle** is a profitable signal caller specialized in **Bitget's Onchain venue**: the pre-listing DEX board at `bitget.com/asia/on-chain/` where emerging tokens on Solana, BSC, Ethereum, Base, Morph, and Monad trade before (or without ever) reaching Bitget's centralized spot or futures markets. Also within scope: Bitget's tokenized-stock roster on the same page ("Full crypto assets & select tokenized stocks").

The project's goal is simple and non-negotiable: **make money by calling profitable long AND short trade setups on this venue, delivered via Telegram, with statistically pre-registered edge and honest post-hoc resolution tracking.**

## What CodeOracle is NOT

- Not a centralized-exchange scanner. Do not compete with sibling projects on Bitget spot/futures universes.
- Not a general-purpose crypto news aggregator.
- Not a hype-farming shill account. Every signal must trace to a mechanical, pre-registered edge with a survivable stop and a resolution rule.
- Not a fork or extension of any existing project. CodeOracle is a **distinct third project** built ground-up for the Onchain venue.

## Universe

**Primary universe** — tokens visible on `bitget.com/asia/on-chain/` across:
- Solana (SOL) — expect majority of daily volume; heavy meme + AI narrative
- BSC — memes, DeFi tails, launchpad graduations
- Ethereum (ETH) — larger caps, less noise, but pre-listing gems exist
- Base — Coinbase L2 memes, farcaster-adjacent tokens
- Morph — emerging L2, small population
- Monad — pre-mainnet / early ecosystem
- Tokenized stocks — the roster of equity-wrapped tokens Bitget lists in this venue

**Universe filters must handle** (design as gates, not as universe elimination — some tokens deserve a signal even at low liquidity if the setup is right):
- Liquidity floor (below this, entries slip catastrophically)
- Holder count floor (single-holder rugs)
- 24h volume floor (dead tokens)
- Contract-risk badge (Bitget flags Normal / Warning / Danger — treat non-Normal as tier reduction, not auto-reject)
- Trading-risk badge (same)
- Age (brand-new tokens carry launch-day risk; may warrant separate signal class)

## Output vision — Telegram-first

CodeOracle's primary product is the Telegram signal card. Two output styles referenced by the operator:

### Style A — the setup card (per-signal)

Inspired by the operator's existing Pythia project. The card carries every piece of context a competent trader needs to act in 30 seconds. Blocks include:

- **Header row**: quality medal (⭐ 1-5), direction (LONG / SHORT), symbol, rank in last 24h, source (which edge fired), prior-call reference if the symbol has traded recently
- **LEVELS block**: live price, entry, stop (with adverse-move %), TP1 (with R multiple), historical Adverse P90 before revert (statistical context, not a fixed number pulled from thin air)
- **WINDOW block**: how urgent is entry (5m FAST, 30m, 1h), thesis time-horizon (4h / 12h / 24h / 3d)
- **CONTEXT block**: chain-level regime (SOL memes hot?), event calendar (upcoming unlocks, exchange listings, macro), narrative tag
- **ONCHAIN block** (CodeOracle-native, replaces the ORDER BOOK block from centralized-exchange formats): contract badge, liquidity depth ($X USD each side of the pool at ±1%, ±2%, ±5%), holder concentration (top 10 %, Nakamoto coefficient), LP-lock status + unlock date, dev-wallet balance %, sniper-cohort presence
- **TYPICAL block**: historical median time-to-TP1, median time-to-SL, median timeout duration for this edge class (n=X)
- **WHY THIS SETUP**: 2-4 bulleted reasons the signal fired
- **Resolution lifecycle**: card updates in-place (or as reply) when the setup resolves — TP1 (+XR), SL (-YR), EXPIRED (+ZR), or CHASED (operator note)

### Style B — the daily digest (once per day, fixed UTC)

Inspired by the operator's existing mm-radar project daily digest. Includes:

- **Engine status**: last scanner beat, cycles in last 24h, symbol count covered, last-cycle latency
- **Chain regime**: which chains are hot, which are cold, is there a cross-chain rotation in progress
- **Basket-level regime** (if a basket-detection edge is live): which basket is HOT, which is COOL
- **Macro regime**: BTC dominance, ETH/BTC, funding rates (as backdrop), any market-neutral bearish/bullish tilt
- **Open signals from last 24h**: list with medals + status
- **Setup funnel**: how many candidates screened, how many passed universe filter, how many passed edge gate, how many fired
- **Resolved setups from last 24h**: with R measurement + one-line post-mortem
- **Post-mortem corpus**: rolling ledger of resolutions used for pre-registered edge audit

Both styles must be **HTML-escaped rigorously**. The universal discipline document flags this as the most-shipped bug class in the operator's history. Zero exceptions: every dynamic value inserted into a Telegram HTML message goes through `html.escape()` (or equivalent). Regression tests mandatory.

## Progression path

CodeOracle's ambition arc, in order:

1. **Signal caller** — Telegram-only, operator-executed. Pre-registered edges reach LIVE promotion after n=20+ SHADOW resolutions with statistical significance.
2. **Semi-automated** — once a specific edge class has proven live LIVE profitability over 30+ resolutions, evaluate auto-execution scoped to that edge on Bitget Onchain (only if Bitget Onchain has an API — this is an early data-source question to answer).
3. **Full auto-trader** — a small capital ($100-$500) auto-trader scoped to the highest-edge class only, with strict per-position caps, per-day risk caps, and kill-switches. Follows the same additive + kill-switch + backtest discipline as Pythia's auto-trader.

Do not skip stages. Do not ship auto-execution before SHADOW edge is proven. Do not size up before track record is proven.

## Success criteria (12 weeks)

By ~2026-10-01 the project should have:
- 2+ pre-registered edges that passed SHADOW → LIVE promotion
- 100+ resolved signals with honest R-tracked outcomes
- A published aggregate R-multiple > 0 with confidence interval separated from zero (Bonferroni-corrected)
- Documented survivorship-filter effectiveness (what % of universe entries survive the first 48h)
- Operator has taken at least 20 live trades based on the signals with reconciled real vs. reported R

If those criteria aren't met by 12 weeks: pause new-edge development, run a full retrospective, decide continue vs. pivot vs. shelve.

## Operating constraints

- **Windows only.** Native paths under `C:\` (not OneDrive). Task Scheduler for cadence.
- **Capital-constrained operator.** Free-tier data sources whenever possible. Paid tiers require a written justification with expected edge lift.
- **Human-in-loop for months.** Do not design for autonomy first. Design for a human reading the Telegram cards and making the call.
- **Solo operator.** No multi-user features. No auth systems. No admin panels. If the operator needs a knob, an env var is the answer.
- **Preservation over velocity.** The operator has been burned by silent-fail refactors. Additive-only, kill-switch every new feature, backtest before live.
