---
addendum: v1.3
effective: 2026-08-17
applies_to: E1, E1d, E1e (all edges gated by GATE ZERO)
supersedes: STARTUP_PACKAGE.md §2.4 liq_min_usd default
---

# Addendum v1.3 — GATE ZERO liquidity floor lowered from $100k to $50k

## Motivation

First cycle of `gate_stats.jsonl` telemetry (2026-08-17 12:34 UTC, universe=49):

- `liq_under=47` (96% of candidates)
- `top10_over=29` (59%)
- `age_too_young=28` (57%)
- `holders_under=18` (37%)
- `holders_unknown=0`, `top10_unknown=0`

The $100k liquidity floor alone kills nearly the entire funnel. E1 has produced 4 signals over ~14 days at this threshold, and the funnel appears to be *tightening* over time (survivors=0 for multiple recent cycles). E1d and E1e (introduced 2026-08-17) will inherit the same funnel starvation without a change.

## Change

`GATE_LIQ_MIN_USD` in the GitHub Actions `Scan` step is set to `50000` (was: unset, defaulting to `100000` from `GateConfig.from_env`).

No code changed. The GateConfig default of `100_000.0` in `src/universe/survivorship.py` remains — this is a runtime configuration override only. Local development (no env var) continues to use $100k.

## Cohort semantics (SCIENTIFIC INTEGRITY)

E1's pre-registered trigger (`research/pre_reg_E1.md` §Trigger, item 2) references "GATE ZERO (per ADDENDUM v1.1 semantics: liq_usd >= 100000, ...)". Lowering the floor mid-experiment mutates the trigger. To preserve honesty:

- **Cohort A ($100k regime):** the 4 shadow signals emitted between 2026-08-04 and 2026-08-14 (TikTok, RAMEN, Doom, TOAD). Result: 4/4 SL. These remain the authoritative pre-reg dataset for E1 v1 and count toward the n=30 promotion decision as originally frozen.
- **Cohort B ($50k regime, effective 2026-08-17):** all signals emitted after this addendum lands. E1's n=30 promotion decision is computed on the *union* of Cohort A + Cohort B; the addendum log makes the regime shift auditable but does not reset the counter.

For E1d and E1e (no signals emitted yet under either regime), all signals will be Cohort B. Their pre-regs (`pre_reg_E1d.md`, `pre_reg_E1e.md`) reference E1's GATE ZERO by transitive dependency; this addendum applies to them as well.

## Risk acknowledgement

At $50k liq, real-fill slippage on a $15 position (STARTUP_PACKAGE §6 default) is negligible. At larger positions, the 18% SL becomes wider in effect due to entry slip. Since we are SHADOW-only and position size is nominal, this does not change the shadow arithmetic. If E1/E1d/E1e ever promote to LIVE, the pre-reg's TP1/SL levels should be re-validated against realized slippage at the intended position size.

## Rollback

If Cohort B produces materially different distribution than Cohort A (e.g., ship-rate diverges by >15pp or median R differs by >0.5), promotion decisions must analyze both cohorts separately and either:
1. Restrict the promotion decision to whichever cohort is larger and more consistent with the pre-reg intent, or
2. Reject the union and require a fresh v=2 pre-reg with the current threshold documented explicitly.

To roll back this addendum: remove `GATE_LIQ_MIN_USD: "50000"` from `.github/workflows/cycle.yml`. The GateConfig default reverts to $100k. Document the rollback in an addendum v1.4.

## Version log

- 2026-08-17 — addendum v1.3 committed alongside gate_stats.jsonl telemetry evidence
