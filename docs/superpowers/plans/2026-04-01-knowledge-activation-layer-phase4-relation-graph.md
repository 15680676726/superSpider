# Knowledge Activation Layer Phase 4 Relation Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the optional persisted relation graph as a derived SQLite-backed relation-view layer over existing memory truth so activation relationships can be queried and inspected through Runtime Center without introducing a second truth source or a graph database.

**Architecture:** This phase implements the optional graph-persistence slice in the smallest possible way. It introduces a persisted `memory_relation_views` table, repository interfaces/implementations, derived-index generation of relation views from existing fact/entity/opinion records, and a Runtime Center read surface for relations. The graph remains derived and rebuildable from canonical truth.

**Tech Stack:** Python 3.11, SQLite state store, Pydantic, existing memory repositories/derived index services, FastAPI, Pytest.

---

## 2026-04-01 Reality Check

This plan's core Phase 4 primitives are now landed in the current codebase:

- `MemoryRelationViewRecord` exists in `src/copaw/state/models_memory.py`
- `memory_relation_views` exists as a SQLite-backed table/read model in `src/copaw/state/store.py`
- `SqliteMemoryRelationViewRepository` exists and is wired through runtime bootstrap
- `DerivedMemoryIndexService` exposes explicit `list_relation_views(...)` and `rebuild_relation_views(...)`
- Runtime Center now exposes `GET /runtime-center/memory/relations`

Current hard boundary in code:

- persisted relation views are derived-only read models over existing fact/entity/opinion views
- persisted relation views are not a second truth source and are not graph-native write targets
- the generic memory rebuild route does not yet invoke relation rebuild automatically; relation rebuild currently remains an explicit derived-index operation

## Scope Check

This is the final remaining activation-layer subsystem:

1. persisted relation views
2. relation graph rebuild/export
3. Runtime Center relation read route

This plan does **not** add:

- a separate graph database
- a second memory truth source
- graph-native writes from execution paths

## Execution Environment

Continue in the same feature worktree:

```powershell
cd D:\word\copaw\.worktrees\knowledge-activation-phase1
```

## File Map

### Existing files to modify

- `src/copaw/state/models_memory.py`
  - Add `MemoryRelationViewRecord` and any supporting enum/type definitions.
- `src/copaw/state/repositories/base.py`
  - Add `BaseMemoryRelationViewRepository`.
- `src/copaw/state/repositories/sqlite_memory.py`
  - Add `SqliteMemoryRelationViewRepository`.
- `src/copaw/state/repositories/__init__.py`
  - Export the new base/sqlite repository types.
- `src/copaw/state/store.py`
  - Add `memory_relation_views` schema and indexes; bump schema version if required.
- `src/copaw/app/runtime_bootstrap_models.py`
  - Add `memory_relation_view_repository` to runtime repository/bootstrap types.
- `src/copaw/app/runtime_bootstrap_repositories.py`
  - Instantiate the new repository.
- `src/copaw/memory/derived_index_service.py`
  - Build and persist relation views from existing fact/entity/opinion data.
- `src/copaw/app/routers/runtime_center_routes_memory.py`
  - Add `/runtime-center/memory/relations` route.
- `tests/app/test_runtime_center_memory_api.py`
  - Add relation-route tests.
- `tests/memory/test_activation_service.py`
  - Add relation generation tests if that remains the right unit surface.
- `tests/app/test_runtime_bootstrap_helpers.py`
  - Verify new repository wiring if needed.
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
  - Record the landed relation graph boundary.
- `TASK_STATUS.md`
  - Record the final activation-layer completion boundary.
- `DATA_MODEL_DRAFT.md`
  - Record `MemoryRelationViewRecord` as a landed derived object.

## Task 1: Add Failing Tests for `MemoryRelationViewRecord`

**Files:**
- Modify: `src/copaw/state/models_memory.py`
- Create or Modify: `tests/memory/test_activation_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.state.models_memory import MemoryRelationViewRecord


def test_memory_relation_view_record_accepts_relation_metadata():
    record = MemoryRelationViewRecord(
        relation_id="rel:ctx-1:approval->finance",
        source_node_id="fact:approval",
        target_node_id="entity:finance-queue",
        relation_kind="supports",
        scope_type="work_context",
        scope_id="ctx-1",
    )
    assert record.relation_kind == "supports"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k relation_view_record -v
```

Expected: FAIL with missing model/type.

- [ ] **Step 3: Write minimal implementation**

```python
class MemoryRelationViewRecord(UpdatedRecord):
    relation_id: str
    source_node_id: str
    target_node_id: str
    relation_kind: str
    scope_type: MemoryScopeType = "global"
    scope_id: str = "runtime"
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    summary: str = ""
    confidence: float = 0.0
    source_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k relation_view_record -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/state/models_memory.py tests/memory/test_activation_service.py
git commit -m "feat: add memory relation view model"
```

## Task 2: Add Failing Tests for SQLite Relation View Repository and Schema

**Files:**
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_memory.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_repositories_include_memory_relation_view_repository(...):
    ...
    assert bootstrap.repositories.memory_relation_view_repository is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_bootstrap_helpers.py -k relation_view_repository -v
```

Expected: FAIL because repository wiring/schema does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
CREATE TABLE IF NOT EXISTS memory_relation_views (...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_bootstrap_helpers.py -k relation_view_repository -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_memory.py src/copaw/state/repositories/__init__.py src/copaw/state/store.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_bootstrap_repositories.py tests/app/test_runtime_bootstrap_helpers.py
git commit -m "feat: add relation view repository and schema"
```

## Task 3: Add Failing Tests for Derived Relation View Generation

**Files:**
- Modify: `src/copaw/memory/derived_index_service.py`
- Modify: `tests/memory/test_activation_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_derived_index_service_persists_relation_views_from_fact_entity_links():
    ...
    assert relation_views
    assert relation_views[0].relation_kind in {"mentions", "supports", "contradicts"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k relation_views -v
```

Expected: FAIL because derived relation views are not generated yet.

- [ ] **Step 3: Write minimal implementation**

```python
def rebuild_relation_views(...):
    # derive relation rows from fact/entity/opinion intersections
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k relation_views -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/memory/derived_index_service.py tests/memory/test_activation_service.py
git commit -m "feat: persist derived memory relation views"
```

## Task 4: Add Failing Tests for Runtime Center Relation Graph Route

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `tests/app/test_runtime_center_memory_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_center_memory_relations_route_lists_relation_views(...):
    response = client.get("/runtime-center/memory/relations", params={"scope_type": "work_context", "scope_id": "ctx-1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["relation_kind"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k memory_relations_route -v
```

Expected: FAIL because the route does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@router.get("/memory/relations")
async def list_memory_relations(...):
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_memory_api.py -k memory_relations_route -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/routers/runtime_center_routes_memory.py tests/app/test_runtime_center_memory_api.py
git commit -m "feat: add runtime center relation graph route"
```

## Task 5: Run Phase 4 Regression and Update Docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_center_memory_api.py -v
```

Expected: PASS

- [ ] **Step 2: Update the docs**

```markdown
- persisted relation views now exist as a derived SQLite-backed layer
- Runtime Center can list relation views
- activation graph remains derived and rebuildable from canonical truth
```

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "docs: record knowledge activation phase4"
```

## Done Definition

Phase 4 is complete only when all of the following are true:

- relation-view model exists
- SQLite schema/repository exists
- derived index can persist relation views
- Runtime Center can list relation views
- the regression suite in Task 5 is green

## Completion Gate

After this plan is green, the knowledge activation layer upgrade is complete for the currently approved roadmap.
