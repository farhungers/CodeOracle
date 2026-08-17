---
edge_code: E1d
edge_name: Holder-concentration anomaly with uptrend-pullback filter (Solana)
version: 1
status: shadow
created: 2026-08-17
project: CodeOracle
parent_edge: E1
plan_ref: research/pre_reg_E1.md + operator decision 2026-08-17 (shadow variants)
---

# Pre-registration — Edge E1d (E1 + pullback filter)

Per UNIVERSAL_DISCIPLINE §I.3: this document is frozen at commit time. Its SHA-256 will be stored in `edges.prereg_sha256` when the DB layer lands. Mid-experiment mutation is a scientific integrity violation.

E1d is a shadow variant of E1. It runs in parallel with E1 (E1 is untouched). Its purpose is to test whether E1's losing streak (4/4 SL at time of writing) can be corrected by an entry-timing filter.

## Hypothesis

E1 loses because it enters at velocity peaks that mean-revert. Adding a "pullback within uptrend" filter to E1's trigger will improve median R-multiple vs unfiltered E1 by avoiding entries at short-term exhaustion.

## Mechanism

Same as E1 (see `research/pre_reg_E1.md` §Mechanism). Additional refinement: entering during a brief pullback within a broader uptrend catches the token during momentum consolidation rather than at momentum climax; historical meme-token behavior shows continuations from pullbacks resolve toward TP1 more often than continuations from tops.

## Trigger

A token fires an E1d SHADOW signal at cycle time t if ALL of the following are true:

1. All conditions from E1's trigger (see `pre_reg_E1.md` §Trigger 1-5), AND
2. `price_change_h24 > 0` (uptrending over the past 24h), AND
3. `price_change_h1 < 0` (currently pulling back over the past hour)

Both fields come from DexScreener's `priceChange.h24` / `priceChange.h1` on the best pair.

## Proxy caveat

The intended criterion is `current_price <= 0.85 * high_24h` (i.e., token is at least 15% off its 24h high). DexScreener does not expose 24h high on the pair object, and fetching per-candidate OHLC from GeckoTerminal at emission time was rejected on cost + latency grounds. The `h24 > 0 AND h1 < 0` proxy captures the direction of the concept without the exact 15% distance. This proxy may include tokens only marginally pulling back (small negative h1) that the strict rule would exclude, and exclude tokens deeply pulled back over multiple hours where the h1 has recovered slightly. Post-analysis at n=30 should compute the actual `distance_from_h24_high` for each fired signal and report the proxy's confusion vs the strict rule.

## Direction, entry, exit

Identical to E1: LONG only, entry at emission price, `stop = entry * 0.82`, `tp1 = entry * 1.40`, 72h thesis window, R = (exit/entry - 1) / 0.18.

Env overrides (all default to E1's defaults):
- `EDGE_E1D_STOP_PCT` (default 0.18)
- `EDGE_E1D_TP1_PCT` (default 0.40)
- `EDGE_E1D_WINDOW_HOURS` (default 72)

## Sample size for promotion decision

n = 30 resolved SHADOW signals for E1d itself (independent of E1's count).

## Test statistic and promotion threshold

Same as E1 (bootstrap 95% CI of median R, ship-rate, drawdown envelope). Bonferroni family now includes E1, E1d, E1e concurrent shadows — per-edge alpha = 0.05/3 = 0.0167 at v1 commit time.

**Additional comparative statistic:** if both E1 and E1d reach n=30, compute pairwise difference-of-medians (E1d - E1) with bootstrap 95% CI on the difference. If CI excludes zero and E1d > E1, E1d is preferred over E1 for LIVE consideration. If CI includes zero, no preference is claimed.

## Failure of ANY condition -> PARK

Same discipline as E1. No relaxation.

## Resolution rule

Same as E1 (v1 resolver authoritative per pre-reg; v2 resolver per addendum v1.2 provides corrected measurement).

## Kill switch

`EDGE_E1D_DISABLED=true` -> signal path skipped.

## Version log

- v1 — 2026-08-17 — operator decision to test pullback filter as shadow variant of E1
