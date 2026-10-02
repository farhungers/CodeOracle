---
edge_code: E1
edge_name: Early holder-concentration anomaly (Solana) — age-filtered, v2 resolver
version: 2
status: shadow
created: 2026-10-02
project: CodeOracle
predecessor: pre_reg_E1.md (v1, PARKED 2026-10-02 — see retro_E1_shadow.md)
plan_ref: STARTUP_PACKAGE.md §4 E1 + ADDENDUM v1.1 ADD-7 + addendum v1.3 (liq floor) + addendum v1.2 (resolver v2)
frozen_sha256: 956c280d12963460ee3fc0e7447df3e02e8297a3c804bbbba65777837ede3c82
sha256_recipe: sha256 of this file with the frozen_sha256 line replaced by '956c280d12963460ee3fc0e7447df3e02e8297a3c804bbbba65777837ede3c82'; verify by substitution + sha256sum.
---

# Pre-registration — Edge E1 v=2

**FROZEN at commit time.** Signed off by operator 2026-10-02.

Per UNIVERSAL_DISCIPLINE §I.3: once frozen, mid-experiment mutation is a scientific integrity violation. Failed pre-reg → PARK + retrospective, not a threshold adjustment.

## Changes from v=1 (explicit audit against predecessor)

| Area | v=1 | v=2 | Rationale |
|------|-----|-----|-----------|
| Resolver authority | v1 (polling) | v2 (OHLC, GeckoTerminal 5-min candles) | v1 had TP1→SL measurement bias (38 flips of 103 common keys). v2 honors pre-reg's TP1-first tie-break. See addendum v1.2. |
| Trigger (new) | top10<0.40 + trade-count-median + GATE ZERO | +age_hours ≥ 24 | Retrospective lift from v=1 data showed age ≥ 24 cohort had ship 0.333 vs 0.307 baseline. See §Data-informed trigger disclosure. |
| Promotion criteria statistic | Median R (degenerate for binary payouts) | Mean R + ship-rate | v=1 criterion 2 (median R ≥ 0.20) was mathematically equivalent to ship-rate ≥ 0.50 for a +2.22R/−1R binary outcome, which contradicted v=1 criterion 3 (ship-rate ≥ 0.30). v=2 uses mean R (true expected value). |
| Drawdown envelope | −5R | −8R | Variance analysis: a true-positive edge with mean R=+0.15 can run drawdowns of −6R or deeper over 30 trades purely from streaks. The v=1 −5R envelope would false-positive-reject profitable edges. |
| Bonferroni family | {E1, E1d, E1e} v1 | {E1 v2, E1e v1} + any future concurrent shadow | E1d is PARKED. E1e remains in shadow at v=1. Per-edge alpha = 0.05/2 = 0.025 until additional shadows join the family. |
| GATE ZERO liq floor | 100k (v1 default) | 50k (addendum v1.3) | Addendum v1.3 is now part of v=2 pre-reg explicitly, not a workflow override. |
| Prior v=1 signals | — | Do NOT count toward v=2 n=30 | v=2 criteria + trigger differ. v=1's 102 signals are historical context, not evidence for v=2. First v=2 shadow signal starts n=1. |

## Data-informed trigger disclosure (honesty required)

The age ≥ 24 filter was selected from v=1 shadow data in which the filter's retrospective ship-rate was 0.333 (vs 0.307 baseline). This is a classic post-hoc overfitting hazard. The pre-reg explicitly acknowledges:

- The age filter is NOT a fresh prior hypothesis; it was chosen because it looked best on the sample we're now using to design v=2.
- Retrospective lift (+2.6pp) was modest and the CI straddles zero; it is noise-compatible.
- Prospective lift may be smaller, zero, or negative.
- Promotion decision must therefore be made against FRESH v=2 signals only (n=30 starting from first v=2 emission). This is the operative honesty guardrail.

If v=2's 30 fresh signals produce ship-rate materially below v=1's 0.307 baseline AND the pre-reg criteria fail, the overfitting hypothesis is confirmed and E1 lineage is PARKED permanently (not re-eval'd via v=3).

## Hypothesis

Solana tokens passing GATE ZERO plus the E1-v2-specific criteria below (including age ≥ 24 hours since pool-creation) yield positive expected R-multiple per signal when entered LONG at signal-emission time and exited at either TP1 (+40% from entry) or SL (−18% from entry) with a forced EXPIRED resolution at the 72h thesis window. Measurement is by resolver v2 OHLC.

## Mechanism

Same as v=1 §Mechanism, plus: tokens past the first-24-hour post-launch window have cleared the acute discovery-driven volatility phase and are more likely to resolve on fundamental holder-distribution dynamics rather than first-hour fomo spikes.

## Trigger (per token, per scanner cycle)

A token fires an E1 v=2 SHADOW signal at cycle time t if and only if ALL are true at t:

1. `chain == 'solana'`
2. Passes GATE ZERO (liq_usd ≥ 50000, age 6h..30d, holder_count ≥ 100, top10_pct ≤ 0.60, vol_liq_ratio ≥ 1.0 — per addendum v1.3)
3. `top10_pct < 0.40`
4. `trade_count_h24 > median trade_count_h24 across Solana universe in current cycle` (buys_h24 + sells_h24 from DexScreener)
5. **NEW:** `age_hours >= 24`
6. Token has not already produced an E1 v=2 signal in the prior 24h (dedup)

v=1-only signals do not count toward v=2 dedup — dedup is per-version.

## E1-specific fields NOT gated in v=2 (same waivers as v=1)

- Dev wallet balance < 5% — not implemented (Helius free tier)
- LP lock duration > 30 days — not integrated
- Holder velocity via unique-buyer-address — substituted with trade-count velocity (ADD-7)

Documented so promotion analysis correctly interprets coverage.

## Direction, entry, exit

- **Direction:** LONG only.
- **Entry:** `entry_price = price_usd_at_t` at emission time.
- **Stop:** `stop_price = entry_price * (1 − EDGE_E1V2_STOP_PCT)`, default `EDGE_E1V2_STOP_PCT=0.18`.
- **TP1:** `tp1_price = entry_price * (1 + EDGE_E1V2_TP1_PCT)`, default `EDGE_E1V2_TP1_PCT=0.40`.
- **Thesis window:** `EDGE_E1V2_WINDOW_HOURS=72`.
- R-multiple: `R = (exit_price / entry_price − 1) / EDGE_E1V2_STOP_PCT`. TP1 ≈ +2.22R gross, ~+2.0R after fees + MEV. SL = −1R. EXPIRED = computed from exit tick.

## Resolution — resolver v2 OHLC (authoritative)

Resolver v2 (`src/resolver/open_scanner_v2.py`, addendum v1.2) fetches 5-min OHLCV candles from GeckoTerminal across the hold window and walks them chronologically. Within a candle:

- If `high >= tp1_price` → TP1 (first-crossing tie-break, honors v=1 intent)
- Else if `low <= stop_price` → SL
- Else advance

First crossing across candles wins. Outcomes: `TP1`, `SL`, `EXPIRED`, `INVALID` (same semantics as v=1).

**V2 is authoritative.** V1 polling resolver continues to run for debug/comparison and writes to `resolutions.jsonl`, but no v=2 promotion decision references it.

## Sample size for promotion decision

**n = 30 FRESH resolved SHADOW signals under v=2 trigger.** "Resolved" = TP1, SL, or EXPIRED. INVALID drops from stats. v=1 signals do not count. Clock starts at first v=2 shadow emission.

## Test statistics

- **Mean R** across n=30 resolved signals.
- **Bootstrap 95% confidence interval of mean R** (10,000 resamples with replacement).
- **Ship-rate** = TP1 fraction.
- **Drawdown envelope** = cumulative sum of R across resolved signals ordered by resolution time; the minimum of this cumulative series.
- Median R and median time-to-TP1 reported for context but NOT used in promotion criteria.

## Decision threshold (Bonferroni-corrected, family = concurrent shadows at commit time)

E1 v=2 promotes SHADOW → LIVE if and only if ALL hold at n=30:

1. **Bootstrap 95% CI lower bound of mean R > 0.** (Rules out noise around breakeven.)
2. **Mean R ≥ +0.15.** (Covers fees ~25bps × 2 + MEV ~30bps + a small positive edge.)
3. **Ship-rate ≥ 0.30.** (Minimum TP1 frequency floor independent of magnitude.)
4. **Drawdown envelope ≥ −8R at every step during n=30 accumulation.**
5. **Bonferroni-adjusted p < 0.025 for the null hypothesis (mean R == 0) against a two-sided alternative.** Family at commit time: {E1 v=2, E1e v=1}. Alpha_family = 0.05, per-edge alpha = 0.025. If a new shadow edge joins the family during the n=30 accumulation window, alpha is re-divided and criteria 1 and 5 recomputed at the new alpha. Family changes documented in an addendum.

**Failure of ANY condition → PARK.** Thresholds do not relax. Re-eval only via v=3 pre-reg.

## Exclusions (pre-registered)

- Tokens with `contract_badge != 'normal'` OR any RugCheck scam-flag at emission time.
- Tokens with symbol matching known scam-tag list at emission (empty list at v=2 commit — additions require fresh pre-reg).
- Tokens where symbol contains characters outside printable ASCII — not enforced at v=2 (TBD).

## Failure mode + PARK plan

- If v=2 fails to accumulate n=30 within **90 days** of first-v=2-shadow emission, revisit discovery feed; document in `research/retro_E1_v2_shadow.md` regardless. v=1 took ~55 days to reach n=30 under $50k floor; 90-day budget gives safety margin.
- If v=2 hits n=30 and fails ≥1 promotion criterion → **PARK PERMANENTLY**. `edges.status = 'parked_terminal'`. No v=3. The hypothesis (holder-concentration + trade-velocity + age filter yields positive R on Solana memes) is considered rejected at the end of v=2 if criteria fail. Rationale: v=1 already failed; v=2 is the second attempt with the strongest honest refinements available; a third failure would be hypothesis-rejection by any defensible standard.
- If v=2 hits n=30 and passes → promote to LIVE per existing LIVE arc (STARTUP_PACKAGE §6).

## Kill switch

`EDGE_E1V2_DISABLED=true` → signal path skipped in scanner loop. Existing open v=2 SHADOW signals resolve normally.

v=1's kill `EDGE_E1_DISABLED=true` remains in `.github/workflows/cycle.yml` indefinitely.

## Implementation plan (post-sign-off)

1. New file `src/edges/e1_v2_holder_concentration_age.py` with `class E1V2HolderAge(Edge)` — code "E1V2", version = 2. Mirrors v=1 class + adds `age_hours >= 24` check. Reads `EDGE_E1V2_*` env vars with v=1 defaults.
2. Wire into scanner `scripts/run_scan_solana.py` alongside existing E1e.
3. Add `EDGE_E1V2_DISABLED` kill-switch env default to NOT set (enabled).
4. Freeze this file (compute SHA-256, record in `edges.prereg_sha256`), commit as `pre_reg_E1_v2.md` (drop `_draft` suffix).
5. First v=2 signal expected within one scanner cycle (4h).

## Version log

- v=2 — 2026-10-02 — successor to v=1 after v=1 PARK. See `research/retro_E1_shadow.md`.
