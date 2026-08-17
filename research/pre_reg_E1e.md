---
edge_code: E1e
edge_name: Holder-concentration anomaly on post-graduation pools only (Solana)
version: 1
status: shadow
created: 2026-08-17
project: CodeOracle
parent_edge: E1
plan_ref: research/pre_reg_E1.md + operator decision 2026-08-17 (shadow variants)
---

# Pre-registration — Edge E1e (E1 excluding pump.fun pre-graduation pools)

Per UNIVERSAL_DISCIPLINE §I.3: frozen at commit time. Runs in parallel with E1 and E1d. E1 is untouched.

## Hypothesis

E1 loses because pump.fun pre-graduation pools (dex_id="pumpswap") are structurally reflexive — the pool's price-impact curve amplifies whales, and the "graduate to Raydium at $69k mcap" mechanic distorts trend continuations. Restricting E1's premise to already-graduated pools (raydium, meteora, orca, etc.) will improve median R-multiple vs unfiltered E1.

## Mechanism

Same as E1 for holder-distribution and velocity rationale. The additional filter reflects an observation from E1's first 4 signals: TikTok, RAMEN, Doom were all pumpswap; TOAD was meteora (also lost, but from a mature pool). Even 4/4 is thin evidence, so E1e formally tests whether removing the pumpswap population shifts the distribution.

## Trigger

A token fires an E1e SHADOW signal at cycle time t if ALL of the following are true:

1. All conditions from E1's trigger (see `pre_reg_E1.md` §Trigger 1-5), AND
2. `dex_id.lower() not in {'pumpswap'}` — best pair is NOT on pump.fun's pre-graduation AMM

The `EXCLUDED_DEXES` set is frozen at v1 = `{'pumpswap'}`. Any addition or removal requires a fresh pre-reg at v=2.

## Direction, entry, exit

Identical to E1: LONG only, entry at emission price, `stop = entry * 0.82`, `tp1 = entry * 1.40`, 72h thesis window.

Env overrides:
- `EDGE_E1E_STOP_PCT` (default 0.18)
- `EDGE_E1E_TP1_PCT` (default 0.40)
- `EDGE_E1E_WINDOW_HOURS` (default 72)

## Sample size for promotion decision

n = 30 resolved SHADOW signals for E1e itself.

## Coverage caveat

Excluding pumpswap may collapse the E1e universe to near-empty given that pump.fun is currently the dominant meme launch venue on Solana. If E1e emits < 5 signals in the first 30 days, the failure mode is universe-starvation, not edge-invalidation, and should be documented as such in the 60-day retro. Consider whether to broaden EXCLUDED_DEXES to include only truly-reflexive venues, or to keep the strict exclusion and accept lower n.

## Test statistic and promotion threshold

Same as E1. Bonferroni family includes E1, E1d, E1e -> per-edge alpha = 0.0167.

**Comparative statistic:** if both E1 and E1e reach n=30, compute pairwise difference-of-medians and difference in ship-rate.

## Kill switch

`EDGE_E1E_DISABLED=true` -> signal path skipped.

## Version log

- v1 — 2026-08-17 — operator decision to test post-graduation-only filter as shadow variant of E1
