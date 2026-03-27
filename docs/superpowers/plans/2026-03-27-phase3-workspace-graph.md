# Phase 3 Workspace Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Symbiotic Host Runtime Phase 3 (`Workspace Graph`) as a richer derived task-workspace projection over the existing seat/session/runtime facts.

**Architecture:** Keep `Workspace Graph` as a projection only, assembled inside the existing environment health/query path from `EnvironmentMount + SessionMount + TaskRuntime-facing workspace facts + Artifact/Evidence + host event summaries + live handle descriptors`. Add structured `locks`, `surfaces`, collision/ownership facts, and checkpoint visibility without creating a second truth source or separate event/object store.

**Tech Stack:** Python, FastAPI, SQLite state repositories, RuntimeEventBus, pytest

---

## File Map

- Create: `docs/superpowers/plans/2026-03-27-phase3-workspace-graph.md`
- Modify: `src/copaw/environments/health_service.py`
- Modify: `tests/environments/test_environment_registry.py`
- Modify: `tests/app/runtime_center_api_parts/shared.py`
- Modify: `tests/app/runtime_center_api_parts/detail_environment.py`
- Modify: `tests/app/test_runtime_projection_contracts.py`
- Modify: `tests/app/test_runtime_query_services.py`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

## Task 1: Define the richer Phase 3 workspace projection contract

**Files:**
- Modify: `docs/superpowers/plans/2026-03-27-phase3-workspace-graph.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] Record the Phase 3 target fields and hard boundaries: `locks`, `surfaces`, collision/ownership facts, checkpoint visibility, and projection-only semantics.
- [ ] Verify every new field maps back to existing truth sources (`EnvironmentMount / SessionMount / host events / artifacts / observations`) rather than inventing a new store.
- [ ] Re-read the approved spec and ensure the plan still follows `projection-only` and `mechanism-not-truth-store` boundaries.

## Task 2: Add richer `Workspace Graph` assembly in `EnvironmentHealthService`

**Files:**
- Modify: `src/copaw/environments/health_service.py`

- [ ] Write failing environment tests for structured `locks`, `surfaces`, and ownership/collision facts.
- [ ] Run: `pytest tests/environments/test_environment_registry.py -q`
- [ ] Extend `build_workspace_graph_projection(...)` to emit richer structures while keeping existing summary/ref fields stable.
- [ ] Build structured `locks` from existing writer-lock/lease metadata and active lock summary.
- [ ] Build structured `surfaces` for browser, desktop, documents/files, clipboard, and downloads using existing site/app/runtime descriptors.
- [ ] Add explicit operational summaries for handoff, download state, active surface ownership, and latest host-event anchor without creating new persistence.
- [ ] Re-run: `pytest tests/environments/test_environment_registry.py -q`

## Task 3: Align Runtime Center fake payloads and API/read-model expectations

**Files:**
- Modify: `tests/app/runtime_center_api_parts/shared.py`
- Modify: `tests/app/runtime_center_api_parts/detail_environment.py`
- Modify: `tests/app/test_runtime_projection_contracts.py`
- Modify: `tests/app/test_runtime_query_services.py`

- [ ] Update fake environment payloads so API tests reflect the new Phase 3 contract instead of stub-only partial shapes.
- [ ] Tighten detail/query/projection tests to assert the structured workspace payload now surfaced from the real contract.
- [ ] Run: `pytest tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q`

## Task 4: Phase 3 acceptance and status/doc sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] Update the status board to record the real Phase 3 boundary landed in code.
- [ ] Sync data-model/API-transition docs only for the fields and boundaries actually implemented.
- [ ] Run focused Phase 3 acceptance:

```bash
python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q
```

- [ ] Run wider regression touching the environment/runtime host chain:

```bash
python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py -q
```
