---
title: CodeOracle bootstrap — entry point for the founding Claude session
audience: fresh Claude Code session invoked at C:\CodeOracle (or launched into it)
date: 2026-07-10
---

# CodeOracle — bootstrap entry point

You are the founding Claude Code session for a new project called **CodeOracle**.

Everything you need to design this project's startup package is in this folder. You do **NOT** need to reach out to any other directory on this machine. All required inputs are local. All outputs go into `C:\CodeOracle\`.

## Read order — before you do anything else

Read these three files fully, in order:

1. `C:\CodeOracle\_bootstrap\UNIVERSAL_DISCIPLINE.md` — your operating discipline. Apply every rule in here to your work below.
2. `C:\CodeOracle\_bootstrap\MISSION.md` — what CodeOracle is, what universe it trades, what output it produces.
3. `C:\CodeOracle\_bootstrap\ONCHAIN_EDGE_GUIDE.md` — curated domain knowledge on how to be a successful on-chain signal caller (data sources, edge classes, risk management, cadence, statistical discipline).

## Your task

Produce ONE markdown document: `C:\CodeOracle\STARTUP_PACKAGE.md`.

This is the complete startup package that CodeOracle's future Claude sessions will read as their launch context. It is a **plan document**, not code. Do **NOT** write project code. Do **NOT** create any files under `C:\CodeOracle\` other than `STARTUP_PACKAGE.md` (and optionally supporting sub-notes if a single file gets unwieldy — keep them in `C:\CodeOracle\_startup_notes\`).

## Required sections in STARTUP_PACKAGE.md

Cover all of the following. Depth over breadth per section is fine — this document is dense reference material, not marketing.

1. **Identity & Mission** — one paragraph naming what CodeOracle is, one paragraph on what it explicitly is NOT (scope discipline)
2. **Universe Definition** — precise chain list, listing-status rules, tokenized-stock inclusion criteria, exclusion filters (rug heuristics, sub-$X liquidity cutoffs, sub-N holder cutoffs, etc.)
3. **Data-Source Inventory** — every ingest surface with: purpose, endpoint / library, rate limit, cost (free / paid tier), reliability grade, fallback if it dies
4. **Edge Hypothesis Catalog** — 5-8 candidate signals to test FIRST. Each with: mechanism (why this should work on-chain), pre-registration criteria (sample size, decision threshold, resolution window, Bonferroni family), SHADOW-to-LIVE promotion gate
5. **Pipeline Architecture** — modules, data flow, storage (Postgres schema sketch — tables + key columns), scheduler pattern (Windows Task Scheduler, not cron), env-var conventions, kill-switch env names for every module
6. **Risk & Safety Layer** — contract-risk gate, liquidity-depth-vs-position-size rule, honeypot detection, slippage estimation, MEV awareness, tokenized-stock-hours awareness, universe survivorship filter
7. **Telegram Output Schema** — full card schema for signals (blocks, ordering, medal system, resolution lifecycle) + full daily-digest template. Match the quality bar described in MISSION.md.
8. **Universal Discipline Application** — map each principle from UNIVERSAL_DISCIPLINE.md to how CodeOracle enforces it (pre-reg gates, SHADOW-then-LIVE, escape functions in Telegram formatters, calendar gates, self-audit checkpoints, etc.)
9. **First-Week Milestones** — day-by-day ordered ship list from empty repo to first pre-registered SHADOW signal fired to Telegram
10. **First-Month Milestones** — from first signal to first pre-registered promotion decision (SHADOW → LIVE or PARK)
11. **Open Questions for Operator** — ONLY items that are trading philosophy, capital allocation, or calendar. Do NOT bounce technical constants back to the operator; pick them inline with your reasoning.

## Style

- Terse, senior-collaborator tone.
- Windows environment. Native paths (`C:\...`). NEVER OneDrive paths for code, venvs, logs, or runtime data.
- Additive-only mindset from day one.
- Every candidate edge through SHADOW → LIVE with a pre-registered gate.
- Assume operator is capital-constrained (starts small, likely $50-$200 initial), human-in-loop initially, with possible progression to a small auto-trader once edge is proven and Bitget Onchain API access is validated.

## After you write STARTUP_PACKAGE.md

At the end of your response, print the FULL contents of STARTUP_PACKAGE.md so the operator can review + copy it without opening the file separately.

Then stop. Do not scaffold code. Do not touch any file outside `C:\CodeOracle\`. Your job is the plan.
