# Knowledge Activation Layer Phase 3 Runtime Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the landed Knowledge Activation Layer through Runtime Center memory/read surfaces so operators can inspect activation summaries, activated neurons, contradictions, and support references without introducing a second truth source.

**Architecture:** This phase stays entirely in read models and Runtime Center routes. It does not add new truth storage. It reuses `MemoryActivationService` and the existing Runtime Center memory routes to present activation-layer outputs in a way that is operator-visible and consistent with the current truth-first memory surfaces.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, existing Runtime Center memory routes and query services, Pytest.

---

## Scope Check

The remaining activation-layer roadmap still has two downstream areas:

- Runtime Center activation visualization
- optional persisted relation graph

This plan covers only **Phase 3**:

1. activation recall route
2. activation-aware memory profile/detail surfaces
3. Runtime Center overview/read-model exposure for activation

Future planning is still required for:

- optional persisted relation graph

## Execution Environment

Continue in the existing feature worktree:

```powershell
cd D:\word\copaw\.worktrees\knowledge-activation-phase1
```

## File Map

### Existing files to modify

- `src/copaw/app/routers/runtime_center_routes_memory.py`
  - Add activation-specific routes and/or activation-aware projections alongside current memory endpoints.
- `src/copaw/app/routers/runtime_center_shared.py`
  - Add `memory_activation_service` retrieval helper if needed.
- `src/copaw/app/runtime_center/state_query.py`
  - Surface activation-derived summaries in existing runtime detail/overview payloads where appropriate.
- `src/copaw/app/runtime_center/models.py`
  - Add read-model fields only if existing response models need explicit activation payloads.
- `tests/app/test_runtime_center_memory_api.py`
  - Add Runtime Center memory-route tests for activation outputs.
- `tests/app/test_runtime_center_api.py`
  - Add broader Runtime Center read-surface tests if overview/detail payloads gain activation summaries.
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
  - Update landed boundary after Phase 3.

## Task 1: Add Failing Tests for Runtime Center Activation Recall Route

**Files:**
- Modify: `tests/app/test_runtime_center_memory_api.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_center_memory_activation_route_returns_activation_result(...):
    response = client.get(
        "/runtime-center/memory/activation",
        params={"query": "outbound approval blocked", "work_context_id": "ctx-1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["activated_neurons"]
    assert payload["top_constraints"]


def test_runtime_center_memory_activation_route_preserves_scope_priority(...):
    ...
    assert payload["scope_type"] == "work_context"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k activation_route -v
```

Expected: FAIL because the activation route does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@router.get("/memory/activation", response_model=dict[str, object])
async def activate_memory(...):
    service = _get_memory_activation_service(request)
    result = service.activate_for_query(...)
    return result.model_dump(mode="json")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k activation_route -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/app/test_runtime_center_memory_api.py src/copaw/app/routers/runtime_center_routes_memory.py src/copaw/app/routers/runtime_center_shared.py
git commit -m "feat: add runtime center activation recall route"
```

## Task 2: Add Failing Tests for Activation-Aware Memory Read Surfaces

**Files:**
- Modify: `tests/app/test_runtime_center_memory_api.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_center_memory_profile_includes_activation_summary_when_requested(...):
    response = client.get(
        "/runtime-center/memory/profiles/industry/industry-1",
        params={"include_activation": True, "query": "outbound approval blocked"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["activation"]["activated_neurons"]


def test_runtime_center_memory_episodes_can_include_activation_refs(...):
    ...
    assert payload[0]["activation"]["support_refs"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k include_activation -v
```

Expected: FAIL because memory profile/episode routes do not yet include activation payloads.

- [ ] **Step 3: Write minimal implementation**

```python
if include_activation and query:
    activation = service.activate_for_query(...)
    payload["activation"] = activation.model_dump(mode="json")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k include_activation -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/app/test_runtime_center_memory_api.py src/copaw/app/routers/runtime_center_routes_memory.py
git commit -m "feat: expose activation on memory read surfaces"
```

## Task 3: Add Failing Tests for Runtime Center Core Surfaces Using Activation Summaries

**Files:**
- Modify: `tests/app/test_runtime_center_api.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/models.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_center_task_detail_includes_activation_summary_when_available(...):
    payload = client.get("/runtime-center/tasks/task-1").json()
    assert payload["activation"]["top_entities"]


def test_runtime_center_overview_includes_activation_hint_for_current_focus(...):
    ...
    assert payload["activation"]["top_constraints"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_api.py -k activation_summary -v
```

Expected: FAIL because existing Runtime Center task/overview payloads do not yet surface activation summaries.

- [ ] **Step 3: Write minimal implementation**

```python
detail_payload["activation"] = activation_summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_api.py -k activation_summary -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/app/test_runtime_center_api.py src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/models.py
git commit -m "feat: surface activation summaries in runtime center"
```

## Task 4: Run Phase 3 Regression and Update Docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_api.py -v
```

Expected: PASS

- [ ] **Step 2: Update the docs**

```markdown
- Runtime Center now exposes activation recall and activation-aware memory/read surfaces.
- Activation summaries are operator-visible but remain derived from canonical truth.
```

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "docs: record knowledge activation phase3"
```

## Done Definition

Phase 3 is complete only when all of the following are true:

- Runtime Center has an activation recall route
- memory read surfaces can expose activation summaries when requested
- core Runtime Center read surfaces can show activation summaries where appropriate
- the regression suite in Task 4 is green

## Follow-Up Planning Gate

Do not start the next activation phase from this branch until this plan is green.

Write a follow-up plan for:

1. optional persisted relation graph
