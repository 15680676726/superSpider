# MCP Activation Self-Heal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the first truthful MCP activation/self-heal slice by making `browser-companion` example-run auto-activate a canonical managed browser companion seat when recovery is possible.

**Architecture:** Keep all truth in the current `CapabilityMount / EnvironmentMount / SessionMount` chain. Extend the install-template example-run path with one bounded remediation helper that creates or reuses a canonical browser lease, starts the managed browser runtime, writes companion/attach facts through `EnvironmentService`, then retries the same canonical read path.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed state services, EnvironmentService, BrowserRuntimeService, pytest

---

### Task 1: Lock the browser-companion recovery contract

**Files:**
- Modify: `tests/app/test_capability_market_api.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] Add a failing test proving `browser-companion` example-run auto-activates a canonical managed browser seat when no session is mounted.
- [ ] Run the focused pytest node and verify it fails for the expected reason.
- [ ] Add a failing test proving an unhealthy mounted browser-companion session is retried through the same canonical path instead of returning the old raw blocker immediately.
- [ ] Run the focused pytest node and verify it fails for the expected reason.

### Task 2: Implement bounded auto-activation on the install-template surface

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`

- [ ] Add a small helper that decides whether `browser-companion` can be auto-recovered with the currently available canonical services.
- [ ] Add a small helper that ensures a canonical browser session lease exists or reuses the mounted one.
- [ ] Add a small helper that starts the managed browser runtime, writes browser companion / attach metadata through canonical services, and returns the remediated mount ids.
- [ ] Wire `_browser_companion_example_run(...)` to retry its canonical read after successful remediation.
- [ ] Keep doctor diagnostic-only for this slice.

### Task 3: Expose the new contract in the install-template spec

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`

- [ ] Update the `browser-companion` template notes/config summary so the product surface no longer claims the example-run is always read-only.
- [ ] If needed, add one optional config field that lets the example-run name the managed session it auto-creates.

### Task 4: Verify the slice and record rollout status

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] Run the focused browser companion capability-market regression matrix.
- [ ] Run adjacent cooperative browser regressions to ensure no routing/continuity behavior regressed.
- [ ] Record the landed slice and its remaining boundaries in `TASK_STATUS.md`.
