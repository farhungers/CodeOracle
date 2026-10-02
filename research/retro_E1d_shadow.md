---
edge_code: E1d
status_before: shadow
status_after: parked
park_date: 2026-10-02
park_reason: prereg_v1_promotion_failed
prereg_ref: research/pre_reg_E1d.md
parent_edge: E1
---

# Retrospective — E1d SHADOW promotion decision

## Timeline

- **2026-08-17** — pre-reg v1 committed. E1d is a shadow variant of E1 adding `price_change_h24 > 0 AND price_change_h1 < 0` as a pullback-within-uptrend proxy.
- **2026-08-18** — first E1d SHADOW signal.
- **2026-09-10** — n=30 reached. Promotion decision owed.
- **2026-10-02** — retrospective written. Decision: PARK.

Delay n=30 → PARK: 22 days. ~33 further signals emitted post-fail. Breach acknowledged.

## Pre-reg criteria vs measured outcome at n=30

| # | Criterion | Threshold | Measured @ n=30 | Pass? |
|---|-----------|-----------|-----------------|-------|
| 1 | Bootstrap 95% CI lower bound of median R | > 0 | median R = −1.00, CI = [−1.00, −1.00] | FAIL |
| 2 | Median R | ≥ +0.20 | −1.00 | FAIL |
| 3 | Ship-rate (TP1 fraction) | ≥ 0.30 | 4/30 = 0.133 | FAIL |
| 4 | Bonferroni-adjusted p < 0.0167 (per-edge alpha with family {E1, E1d, E1e}) | n/a — three others fail | FAIL |
| 5 | Cum-R envelope ≥ −5R | −17.11R @ n=30 | FAIL |

All five criteria fail. Pre-reg §Failure: PARK.

## Comparative stat vs parent E1 (per pre-reg)

Pre-reg specified: "if both E1 and E1d reach n=30, compute pairwise difference-of-medians (E1d − E1) with bootstrap 95% CI on the difference." Both reached n=30 (E1 on 2026-08-28, E1d on 2026-09-10). Pairwise difference-of-medians is zero — both edges' medians are pinned at −1.00. The pullback filter did not improve on E1 at the median; small ship-rate difference (0.133 vs 0.200) favors unfiltered E1 if anything, i.e., the filter made things worse on this sample.

**Conclusion on hypothesis:** E1d's "E1 loses because it enters at velocity peaks; pullback filter will improve median R" hypothesis is **rejected by the data**. The h24>0 + h1<0 proxy did not improve outcomes.

## Current state at retrospective time (n=62)

- TP1: 8 (0.129), SL: 54 (0.871), EXPIRED: 0
- Median R: −1.00  Mean R: −0.584
- Cum-R final/min: −36.22R

## Resolver v2 alternative measurement

- V2 E1d (n=63): 18 TP1, 45 SL → ship-rate 0.286.
- V2 vs V1: v2 flips several SL to TP1 (consistent with v1's known polling bias).

Same honesty argument as E1: v2 is informational, not authoritative. Any v=2 pre-reg for E1d-style filters should designate v2 as authoritative from the start.

## Decision

**PARK E1d v1.** Emission disabled via `EDGE_E1D_DISABLED=true` in workflow. Open signals resolve normally.

## Lessons for a potential E1d v=2

- The h24+h1 proxy was documented in pre-reg §Proxy caveat as a weaker substitute for the strict `current_price <= 0.85 * high_24h` rule. The strict rule remains untested.
- Post-analysis at n=30 was supposed to compute `distance_from_h24_high` for each fired signal (pre-reg §Proxy caveat). Deferred to v=2 draft; preserved as token_history data where available.
- Pullback-in-uptrend may still be the right idea with a stricter implementation (e.g., OHLC-based distance from 24h high) — but that is a v=2 pre-reg question, not a v=1 continuation.
