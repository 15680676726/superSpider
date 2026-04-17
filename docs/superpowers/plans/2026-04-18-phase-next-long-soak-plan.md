# Phase-Next Long Soak Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:verification-before-completion` before claiming this soak is complete. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that the current `phase-next` runtime chain keeps formal truth, governance copy, and Runtime Center read surfaces stable across repeated automated rounds after the AI daily report and unified model call rollout.

**Architecture:** Use one fixed soak matrix made of `phase-next autonomy smoke`, `runtime canonical flow e2e`, and `operator runtime e2e`. Run the same matrix sequentially for multiple rounds, record per-round duration and result, and treat any failure as state drift, stale fallback, governance copy mismatch, or cached read contamination until proven otherwise.

**Tech Stack:** `pytest`, Runtime Center, `/runtime-center/chat/run`, main-brain autonomy smoke, operator runtime e2e.

---

## Scope

- In scope:
  - `tests/app/test_phase_next_autonomy_smoke.py`
  - `tests/app/test_runtime_canonical_flow_e2e.py`
  - `tests/app/test_operator_runtime_e2e.py`
- Coverage intent:
  - `phase-next` long-run continuity, handoff, replan, and multi-surface runtime-chain truth
  - canonical `/runtime-center/chat/run` execution and Runtime Center read-side continuity
  - operator/runtime e2e integrity after repeated rounds
- Out of scope:
  - full-repo soak
  - live external-provider soak
  - browser/manual screenshot evidence

## Fixed Soak Matrix

- [x] Baseline broad smoke:

```powershell
python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q
```

- [x] Adjacent full matrix:

```powershell
python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q
```

- [x] Repeated soak rounds:

```powershell
1..3 | ForEach-Object {
  python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q
}
```

## Pass / Fail Rules

- Pass:
  - all baseline commands pass
  - all 3 soak rounds pass with no intermittent failures
  - no reintroduced English governance assertions
  - no drift in long-run handoff / replan / Runtime Center continuity paths
- Fail:
  - any round fails
  - a later round fails after an earlier round passed
  - governance/admission reasons fall back to stale strings
  - Runtime Center or chat/runtime read surfaces diverge across rounds

## Evidence To Record

- command lines
- per-round pass/fail
- per-round runtime duration
- whether failures were execution failures or harness/timeout failures
- current acceptance boundary:
  - whether this reaches `L3`
  - whether this reaches `L4`
  - what still remains outside this soak

## Initial Execution Snapshot

- `2026-04-18` initial baseline:
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q` -> `11 passed`
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q` -> `27 passed`
- `2026-04-18` initial repeated soak:
  - round 1 -> `27 passed` in `209.93s` wall time
  - round 2 -> `27 passed` in `224.32s` wall time
  - round 3 -> `27 passed` in `196.10s` wall time
- Formal run record:
  - acceptance ledger `accept-016` for the broader `L3` sweep
  - acceptance ledger `accept-017` for the selected-slice automated `L4` soak

## Current Boundary

- This plan now has one completed automated soak execution for the selected `phase-next/runtime-center` slice.
- It does not yet prove:
  - full-repository `L4`
  - live external-provider soak
  - manual/live UI continuity sign-off
