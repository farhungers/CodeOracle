---
edge_code: E1
status_before: shadow
status_after: parked
park_date: 2026-10-02
park_reason: prereg_v1_promotion_failed
prereg_ref: research/pre_reg_E1.md (frozen SHA-256 4c796c9ad2788b9444bffdadce826473326488272edf4e288117534ef5ee7651)
cohorts: A ($100k liq floor, 2026-08-03 .. 2026-08-16), B ($50k liq floor, addendum v1.3, 2026-08-17 onward)
---

# Retrospective — E1 SHADOW promotion decision

## Timeline

- **2026-07-10** — pre-reg v1 frozen, SHA-256 locked.
- **2026-08-03** — first SHADOW scan cycle on GitHub Actions.
- **2026-08-04** — first E1 signal (TikTok). Four signals total under Cohort A.
- **2026-08-17** — addendum v1.3 lowers liq floor to $50k (Cohort B opens). Addendum v1.2 adds resolver v2 (OHLC) as informational-only.
- **2026-08-28** — n=30 resolved shadow signals reached. **Promotion decision owed per pre-reg.**
- **2026-10-02** — retrospective written. Decision: PARK. Edge disabled via `EDGE_E1_DISABLED=true` in `.github/workflows/cycle.yml`.

Delay between n=30 (2026-08-28) and PARK (2026-10-02): 35 days. During that window E1 emitted ~75 further SHADOW signals that should not have been emitted per pre-reg. This retro acknowledges the breach; the signals are not retroactively deleted (append-only discipline) but they do not count toward any future v=2 analysis.

## Pre-reg criteria vs measured outcome at n=30

Pre-reg §Decision threshold:

| # | Criterion | Threshold | Measured @ n=30 | Pass? |
|---|-----------|-----------|-----------------|-------|
| 1 | Bootstrap 95% CI lower bound of median R | > 0 | median R = −1.00 (all-SL floor), CI = [−1.00, −1.00] | FAIL |
| 2 | Median R | ≥ +0.20 | −1.00 | FAIL |
| 3 | Ship-rate (TP1 fraction) | ≥ 0.30 | 6/30 = 0.200 | FAIL |
| 4 | Bonferroni-adjusted p (median R == 0) | < 0.0167 | not computed — three other criteria already fail | FAIL |
| 5 | Drawdown envelope cumulative-R | never ≤ −5R | −10.67R @ n=30 | FAIL |

All five criteria fail. The pre-reg §Failure mode says: "Failure of ANY condition → PARK." Four of the five fail hard; drawdown blew the −5R envelope on 2026-08-19 before n=30 was even reached.

## Current state at retrospective time (n=102)

- TP1: 15 (0.147), SL: 86 (0.843), EXPIRED: 1
- Median R: −1.00  Mean R: −0.523
- Cumulative R: −53.40  Minimum (envelope): −53.40

The pattern deepened after n=30. Nothing in the 72 post-promotion-fail signals shifted the verdict toward "the test was premature."

## Cohort analysis (A vs B)

- **Cohort A (n=4):** 0 TP1, 4 SL. Ship-rate 0.000. (TikTok, RAMEN, Doom, TOAD.)
- **Cohort B (n=98):** 15 TP1, 82 SL, 1 EXP. Ship-rate 0.153.

Cohort B's ship-rate is marginally higher, consistent with the hypothesis that A was a tiny-sample fluke rather than a regime effect. Per addendum v1.3 §Rollback, cohorts should be analyzed separately if ship-rate diverges by >15pp or median R by >0.5. Divergences here are smaller: ship-rate 0.000 vs 0.153 (15.3pp, right at threshold); median R identical at −1.00. Union is defensible but moot — both cohorts fail promotion individually.

## Resolver v2 (addendum v1.2) alternative measurement

Resolver v2 uses GeckoTerminal 5-min OHLC and honors the pre-reg's TP1-first tie-break; v1 polls current price and systematically under-counts TP1 outcomes.

- V2 E1 (n=101 valid, 2 INVALID): 31 TP1, 70 SL → ship-rate 0.307.
- V1 vs V2 disagreements on common keys (n=103): 38 cases v1=SL and v2=TP1; 11 cases v1=TP1 and v2=SL.

If v2 were authoritative, ship-rate at n=30 would be ~0.30 and the promotion decision would be at least closer. **But v2 is not authoritative per pre-reg + addendum v1.2.** Flipping authority mid-experiment is a pre-reg mutation, which §Failure mode explicitly disallows ("Do not relax any threshold").

The honest reading: v1's measurement bias is real; the correct remedy is to incorporate v2 as authoritative in a v=2 pre-reg, not to swap it in retroactively.

## Decision

**PARK E1 v1.** `edges.status = 'parked'`, `parked_at = 2026-10-02`, `kill_reason = 'prereg_v1_promotion_failed'`.

Emission disabled via workflow env var. Open signals continue to resolve under both v1 and v2 resolvers (append-only JSONL preserves the full record).

## Re-evaluation path

Per pre-reg §Failure mode: "A parked edge may be re-eval'd only via a fresh pre-registration document at v=2, with any changes explicitly documented against v=1." A v=2 pre-reg is in draft (`research/pre_reg_E1_v2_draft.md`); it is NOT frozen until operator sign-off. V=2 requires 30 fresh resolved signals from first-emission under its new trigger — the v1 record does not count.

## What v=2 should re-examine (not re-decide here)

- Trigger tightness — the top10_pct < 0.40 and trade-count-median proxy may not be the operative filters; which features actually separate TP1 from SL in the v2 OHLC data?
- Resolver authority — promote v2 (OHLC) to authoritative; v1 polling retained for debug only.
- Position of EXPIRED outcome — only 1/102 expired at 72h. Window may be mis-sized vs the mechanism's actual time-to-outcome distribution.
- Dedup window — pre-reg says 24h; recheck for noise around re-fires.
