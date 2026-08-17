# Addendum v1.2 — Resolver measurement-bias fix (OHLC-based order-of-crossing)

**Effective:** 2026-08-17
**Applies to:** all edges (currently E1 only)
**Author:** operator + assistant
**Rationale:** measurement integrity — the pre-registered "TP1 wins ties" rule was not actually implemented by the v1 resolver; v2 implements it as originally intended.

## The bug in v1

`src/resolver/open_scanner.py` reads *current* price at each poll. Its docstring (lines 13–18) says "TP1 wins over SL in that ambiguous case", but that tie-break can never fire because a single price tick is never both `>= TP1` and `<= SL` simultaneously (TP1 > SL by construction). In practice:

- Poll fires with price at or below SL → recorded SL (even if TP1 was wicked earlier)
- Poll fires with price at or above TP1 → recorded TP1

For meme tokens with 18% SL / 40% TP1 targets and 4-hour poll cadence, this asymmetrically favors SL: a token that briefly touches +40%, reverses, and closes below -18% by the next poll is recorded as SL. The v1 resolver systematically under-counts TP1 outcomes.

## The fix in v2

`src/resolver/open_scanner_v2.py` fetches 5-minute OHLCV candles from GeckoTerminal for the hold window and walks them chronologically. Within a single candle:

- If `high >= tp1`, resolve to TP1 (tie-break: TP1 first — honors pre-reg)
- Else if `low <= stop`, resolve to SL
- Else advance to next candle

Across candles, the first crossing wins. Outcome semantics (`TP1` / `SL` / `EXPIRED` / `INVALID`) are unchanged; only the resolution *method* is stricter.

## What we preserve

- `research/resolutions.jsonl` (v1) remains unchanged — no historical mutation
- `research/resolutions_v2.jsonl` (v2) is a parallel append-only log
- Both resolvers run every CI cycle; v1 is authoritative for the pre-reg record, v2 is the corrected measurement
- Pre-registration integrity: this addendum documents the change without editing `research/pre_reg_E1.md`

## Retroactive re-resolution of the first 4 SHADOW signals

Ran `scripts/rerun_resolver_v2.py` on 2026-08-17 with the OHLC method:

| symbol | v1 outcome | v2 outcome | v1 r-mult | v2 r-mult | flip |
|--------|-----------|-----------|-----------|-----------|------|
| TikTok | SL | INVALID | -1.00 | n/a | pool not on GeckoTerminal |
| RAMEN | SL | SL | -1.00 | -1.00 | confirmed |
| Doom | SL | INVALID | -1.00 | n/a | pool not on GeckoTerminal |
| TOAD | SL | SL | -1.00 | -1.00 | confirmed |

**Zero SL→TP1 flips.** The v1 measurement bias did not produce any of the four losses. The 4/4 SL rate is real for the two pools where OHLC is available; for the other two, we lack independent OHLC to verify.

## Data-coverage caveat

GeckoTerminal doesn't index every DEX pool. Pump.fun pre-graduation pools frequently lack coverage. When candles are unavailable and the thesis window has closed, v2 records `INVALID` rather than guess. Over time this may bias the v2 series toward pools with liquidity/volume above GT's indexing threshold — a separate honesty concern to monitor if v2 ever becomes authoritative.

## Rate-limit budget

GeckoTerminal public API is 30 req/min unauthenticated. One call per open signal per cycle. At current signal density (~4 signals per 14 days), utilization is negligible. Even at 100 open signals/cycle (upper bound), a single cycle stays well inside the budget.

## Files added

- `src/ingest/geckoterminal.py`
- `src/resolver/open_scanner_v2.py`
- `scripts/run_resolver_v2.py`
- `scripts/rerun_resolver_v2.py`
- `tests/test_resolver_v2.py`

## Files modified

- `.github/workflows/cycle.yml` — added `Resolver v2` step + `resolutions_v2.jsonl` to commit-state list
