---
title: E1 SHADOW — pre-scheduler retro + signal invalidations
edge_code: E1
edge_version: 1
created: 2026-08-03
project: CodeOracle
pre_reg_ref: research/pre_reg_E1.md
---

# E1 SHADOW — pre-scheduler retro

## Purpose

Document the fate of E1 SHADOW signals emitted BEFORE the Windows Task
Scheduler was registered, and formally declare the n=0 restart point
for the pre-registered promotion decision (pre_reg_E1.md §Sample size).

This document does **not** modify the pre-registration. It applies the
pre-reg's own `INVALID` resolution class to a manually-fired test signal
that could not be resolved because no resolver process was running.

## Invalidated signal — tolywifhat (2026-07-10)

Signal payload (verbatim from `research/shadow_log.jsonl` prior to
gitignore):

```
cycle_ts_utc:   2026-07-10T01:09:52+00:00
emitted_ts_utc: 2026-07-10T01:10:16+00:00
edge_code:      E1
edge_version:   1
mode:           shadow
chain:          solana
token_addr:     E2ueKQ3EDTTmCkUA17j3KeTb2u6VT91xiyECdKRzpump
symbol:         tolywifhat
direction:      long
entry_price:    0.002855
stop_price:     0.0023411
tp1_price:      0.003997
thesis_window:  4320 min (72h)
reasons:
  - top10=21.9% (<40% threshold)
  - holders=1000
  - h24 trade count 50114 > cycle median 31720
  - liq=$171,571  vol24h=$4,588,756
```

## Resolution: INVALID

Per pre_reg_E1.md §Resolution rule, valid outcomes require price
observations within [t, t+72h]. The 72h window for this signal expired
at **2026-07-13T01:10:16+00:00**. No resolver process ran during that
window (the resolver module was not built; Task Scheduler was not
registered). Therefore no TP1 / SL / EXPIRED determination is possible
from mechanical rules, and the signal cannot be scored against any
alternate reconstructed price series without violating the
pre-registration (post-hoc price fetching is not the mechanism
specified for resolution).

Resolution class: **INVALID** (per pre-reg §Exclusions treatment — the
signal is dropped from statistics).

Rationale for INVALID rather than EXPIRED at reconstructed mid: the
pre-reg specifies "first tick at or above / below" — a tick-level
observation the resolver was supposed to record in real time. Post-hoc
DexScreener OHLC fetch is not tick data and cannot be substituted
without amending the pre-reg, which is a §I.3 discipline violation.

## n restart

Effective n for the E1 SHADOW promotion decision resets to **0** at
the first signal emitted from a scheduled scan cycle (i.e., first
signal fired by a `CodeOracle_ScanSolana` task run, not a manual
`run_scan_solana.py` invocation).

The 60-day accumulation clock (pre-reg §Failure mode) starts at that
same first-scheduled-fire moment.

## Discipline note

This invalidation is a one-time cleanup of pre-scheduler debris. Any
future INVALIDs — after Task Scheduler is live — must have a mechanical
justification (scam-flag emerged between emission and resolution, or
resolver failed to poll for a documented outage). Silently invalidating
signals to improve headline statistics is a discipline violation of the
same class as mid-experiment threshold adjustment.

## Version log

- 2026-08-03 — initial invalidation of tolywifhat manual-test signal
