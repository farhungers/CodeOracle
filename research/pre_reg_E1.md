---
edge_code: E1
edge_name: Early holder-concentration anomaly (Solana)
version: 1
status: shadow
created: 2026-07-10
project: CodeOracle
plan_ref: STARTUP_PACKAGE.md §4 E1 + ADDENDUM v1.1 ADD-7
frozen_sha256: 4c796c9ad2788b9444bffdadce826473326488272edf4e288117534ef5ee7651
---

# Pre-registration — Edge E1 (holder concentration)

Per UNIVERSAL_DISCIPLINE §I.3: this document is frozen at commit time. Its SHA-256 is stored in `edges.prereg_sha256` and matched at signal emission. **Mid-experiment mutation is a scientific integrity violation, not a "small fix."** Failed pre-reg -> PARK + retrospective, not a threshold adjustment.

## Hypothesis

Solana tokens passing GATE ZERO plus the E1-specific criteria below yield a median 72h R-multiple return > 0 when entered LONG at signal-emission time and exited at either TP1 (+40% from entry, 1.5R after fees) or SL (-18% from entry) with a forced EXPIRED resolution at the 72h thesis window.

## Mechanism

Recently-launched tokens with organic holder distribution (top-10 concentration below 40%), an active buying velocity relative to chain median, and structural anti-rug preconditions survive the first-week meme mortality curve at higher rates than the discovery-feed baseline, and are more likely to re-rate on second-wave interest.

## Trigger (per token, per scanner cycle)

A token fires an E1 SHADOW signal at cycle time t if and only if ALL of the following are true at time t:

1. `chain == 'solana'`
2. Token passes GATE ZERO (per ADDENDUM v1.1 semantics: liq_usd >= 100000, age 6h..30d, holder_count >= 100, top10_pct <= 0.60, vol_liq_ratio >= 1.0)
3. `top10_pct < 0.40` (E1's tighter concentration threshold — GATE ZERO uses 60%)
4. `trade_count_h24 > median trade_count_h24 across all Solana universe entries in the current cycle` where `trade_count_h24 = txns.h24.buys + txns.h24.sells` from DexScreener (ADD-7 authenticity proxy)
5. Token has not already produced an E1 signal (SHADOW or LIVE) in the prior 24h (dedup)

## E1-specific fields NOT gated in v1 (waived vs body §4 E1 text)

These are body-text criteria that are unavailable in v1 due to data-source limitations. Their absence is documented here so promotion analysis correctly interprets the coverage gap:

- **Dev wallet balance < 5%**: identification of dev wallet requires transaction-history reconstruction not available on Helius free tier. Skipped in v1. Follow-up: add when Helius Enhanced access is procured or a heuristic (creator wallet from Metaplex metadata) is implemented.
- **LP lock duration > 30 days remaining**: LP-lock services (Team Finance, PinkSale, UNCX) are not integrated in v1. Skipped.
- **Holder velocity via unique-buyer-address counting**: substituted with trade-count velocity per ADD-7.

Effect: E1 v1 is a LOOSER filter than the body's aspirational E1. Promotion decision must be interpreted against v1's actual criteria, not the body's.

## Direction, entry, exit

- **Direction:** LONG only.
- **Entry:** current price at signal-emission time (`entry_price = price_usd_at_t`).
- **Stop:** `stop_price = entry_price * (1 - EDGE_E1_STOP_PCT)` where env default `EDGE_E1_STOP_PCT=0.18`.
- **TP1:** `tp1_price = entry_price * (1 + EDGE_E1_TP1_PCT)` where env default `EDGE_E1_TP1_PCT=0.40`.
- **Thesis window:** `EDGE_E1_WINDOW_HOURS=72`. At t+72h, if neither TP1 nor SL hit, resolve as EXPIRED at mid-price.

R-multiple: `R = (exit_price / entry_price - 1) / EDGE_E1_STOP_PCT`. TP1 = +40%/18% = +2.22R gross, ~+2.0R after 2× swap fee (~25 bps each side) + MEV allowance (~30 bps).

## Sample size for promotion decision

n = 30 resolved SHADOW signals. "Resolved" = TP1, SL, or EXPIRED (not chased, not invalid).

## Test statistic

- Bootstrap 95% confidence interval of median R-multiple (10,000 resamples with replacement).
- Ship-rate = fraction of resolved signals reaching TP1 before SL or expiry.
- Median time-to-TP1 (minutes) for tokens that reached TP1.

## Decision threshold (Bonferroni-corrected)

E1 promotes SHADOW -> LIVE if and only if ALL of the following hold at n=30:

1. Bootstrap 95% CI lower bound of median R > 0.
2. Median R >= +0.20.
3. Ship-rate (TP1 fraction) >= 0.30.
4. Bonferroni-adjusted p < 0.0167 for the null hypothesis (median R == 0) against a two-sided alternative — with the family being all concurrently-SHADOW edges (v1: E1, E4, E9 -> alpha_family = 0.05, per-edge alpha = 0.05/3 = 0.0167).
5. Drawdown envelope (cumulative sum of R across resolved SHADOW signals ordered by resolution time) never fell below -5R at any point during accumulation.

**Failure of ANY condition -> PARK.** Do not relax any threshold. A parked edge may be re-eval'd only via a fresh pre-registration document at v=2, with any changes explicitly documented against v=1.

## Resolution rule

- **TP1:** first tick at or above `tp1_price` observed within [t, t+72h].
- **SL:** first tick at or below `stop_price` observed within [t, t+72h].
- **EXPIRED:** neither hit by t+72h. Exit at the closest observed mid-price at or after t+72h. R computed from that.
- **CHASED:** operator note appended manually; the R is still recorded from the mechanical rule above, but the outcome carries a flag.
- **INVALID:** signal was emitted against a token that later turned out to be scam-flagged by RugCheck between emission and resolution -> drop from statistics.

## Exclusions (pre-registered, NOT post-hoc)

- Tokens with `contract_badge != 'normal'` OR any RugCheck scam-flag at emission time.
- Tokens with symbol matching known scam-tag list at emission time (empty list at v=1 commit — additions require fresh pre-reg).
- Tokens where symbol contains characters that a human would find unreadable at a glance (unicode-outside-BMP heuristic — TBD implementation). Not enforced at v=1.

## Failure mode + PARK plan

If E1 SHADOW fails to accumulate n=30 within 60 days from first-SHADOW-fire, revisit: is the trigger too tight (universe too small), or is the discovery feed the limiter (need broader ingest)? Documented in `research/retro_E1_shadow.md` at 60-day mark regardless of n reached.

If E1 hits n=30 and fails promotion, PARK. `edges.status = 'parked'`, `parked_at = now()`, `kill_reason = 'prereg_v1_promotion_failed'`. Re-eval trigger: net 30 additional resolved SHADOW signals from a v=2 pre-reg with documented changes.

## Kill switch

`EDGE_E1_DISABLED=true` -> signal path skipped in scanner loop. Existing open SHADOW signals resolve normally.

## Version log

- v1 — 2026-07-10 — CodeOracle founding session
