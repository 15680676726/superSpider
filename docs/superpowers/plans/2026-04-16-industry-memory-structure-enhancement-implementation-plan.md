# Industry Memory Structure Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 truth-first memory + knowledge graph + B+ sleep layer 之上，完成行业记忆结构增强、关键细节强写入、proposal 真执行，以及 `Runtime Center + Knowledge` 的简化正式读面。

**Architecture:** 保持“正式事实是唯一真相源”不变，不新造第二套 memory store。实现上以现有 `related-scope recall / relation views / activation service / knowledge graph service / sleep service` 为底座，新增行业结构增强与强写入服务，并把 `proposal apply` 升级成真正 materialize active overlay/profile 的执行动作。

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, React + TypeScript + Ant Design + Vitest

---

## File Map

**Backend truth / persistence**

- Modify: `src/copaw/state/models_memory.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_memory_sleep.py`
- Test: `tests/state/test_state_store_migration.py`
- Test: `tests/state/test_memory_sleep_repository.py`
- Create: `tests/state/test_memory_structure_enhancement_repository.py`

**Backend services**

- Create: `src/copaw/memory/structure_enhancement_service.py`
- Create: `src/copaw/memory/continuity_detail_service.py`
- Create: `src/copaw/memory/structure_proposal_executor.py`
- Modify: `src/copaw/memory/sleep_service.py`
- Modify: `src/copaw/memory/sleep_inference_service.py`
- Modify: `src/copaw/memory/recall_service.py`
- Modify: `src/copaw/memory/profile_service.py`
- Modify: `src/copaw/memory/surface_service.py`
- Modify: `src/copaw/memory/knowledge_graph_service.py`
- Modify: `src/copaw/memory/activation_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`

**Backend API / runtime wiring**

- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/routers/runtime_center_request_models.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`

**Frontend**

- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

**Validation / docs**

- Create: `tests/memory/test_structure_enhancement_service.py`
- Create: `tests/memory/test_continuity_detail_service.py`
- Create: `tests/app/test_memory_structure_enhancement_smoke.py`
- Modify: `tests/memory/test_surface_service.py`
- Modify: `tests/app/test_cron_manager.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

---

### Task 1: Persist Industry Structure Preferences And Continuity Details

**Files:**
- Modify: `src/copaw/state/models_memory.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_memory_sleep.py`
- Test: `tests/state/test_state_store_migration.py`
- Test: `tests/state/test_memory_sleep_repository.py`
- Create: `tests/state/test_memory_structure_enhancement_repository.py`

- [ ] **Step 1: Write the failing repository tests**

```python
def test_slot_preference_repository_round_trip(tmp_path):
    record = IndustryMemorySlotPreferenceRecord(
        preference_id="pref:novel:characters",
        industry_instance_id="industry-1",
        slot_key="character_state",
        status="active",
        promotion_count=3,
    )
    saved = repo.upsert_slot_preference(record)
    assert saved.slot_key == "character_state"
```

```python
def test_continuity_detail_repository_round_trip(tmp_path):
    record = MemoryContinuityDetailRecord(
        detail_id="detail:ctx-1:hero-rule",
        scope_type="work_context",
        scope_id="ctx-1",
        detail_key="hero_rule",
        source_kind="model",
        pinned_until_phase="chapter-10",
    )
    saved = repo.upsert_continuity_detail(record)
    assert saved.pinned_until_phase == "chapter-10"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_memory_structure_enhancement_repository.py -q`
Expected: FAIL with missing models / repository methods / schema

- [ ] **Step 3: Add the new truth objects and schema**

```python
class IndustryMemorySlotPreferenceRecord(UpdatedRecord):
    industry_instance_id: str
    slot_key: str
    status: Literal["active", "inactive", "superseded"] = "active"
    promotion_count: int = 0
    demotion_count: int = 0
```

```python
class MemoryContinuityDetailRecord(UpdatedRecord):
    scope_type: MemoryScopeType
    scope_id: str
    detail_key: str
    detail_text: str
    source_kind: Literal["model", "rule", "manual"]
    pinned: bool = False
```

- [ ] **Step 4: Run repository tests and migration tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_memory_structure_enhancement_repository.py tests/state/test_state_store_migration.py tests/state/test_memory_sleep_repository.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_memory.py src/copaw/state/store.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_memory_sleep.py tests/state/test_state_store_migration.py tests/state/test_memory_sleep_repository.py tests/state/test_memory_structure_enhancement_repository.py
git commit -m "feat: persist memory structure preferences and continuity details"
```

---

### Task 2: Add Structure Enhancement And Continuity Detail Services

**Files:**
- Create: `src/copaw/memory/structure_enhancement_service.py`
- Create: `src/copaw/memory/continuity_detail_service.py`
- Create: `tests/memory/test_structure_enhancement_service.py`
- Create: `tests/memory/test_continuity_detail_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
def test_structure_enhancement_service_promotes_repeated_dynamic_slots():
    result = service.evaluate_dynamic_slots(
        industry_instance_id="industry-1",
        candidate_slots=["character_state", "character_state", "foreshadow"],
    )
    assert "character_state" in result.promoted_slots
```

```python
def test_structure_enhancement_service_demotes_stale_slots():
    result = service.evaluate_dynamic_slots(
        industry_instance_id="industry-1",
        candidate_slots=[],
        existing_slots=["camera_rhythm"],
    )
    assert "camera_rhythm" in result.demoted_slots
```

```python
def test_continuity_detail_service_marks_user_pinned_details_as_must_keep():
    detail = service.upsert_manual_pin(
        scope_type="work_context",
        scope_id="ctx-1",
        detail_key="risk-boundary",
        detail_text="Do not average down after stop-loss.",
    )
    assert detail.pinned is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/memory/test_structure_enhancement_service.py tests/memory/test_continuity_detail_service.py -q`
Expected: FAIL with missing services

- [ ] **Step 3: Implement the services**

```python
class StructureEnhancementService:
    def build_slot_layout(self, *, industry_instance_id: str | None, scope_type: str, scope_id: str, ...): ...
    def evaluate_dynamic_slots(self, *, industry_instance_id: str | None, candidate_slots: list[str], ...): ...
```

```python
class ContinuityDetailService:
    def select_strong_details(self, *, scope_type: str, scope_id: str, graph_signals: dict[str, Any], ...): ...
    def upsert_manual_pin(self, *, scope_type: str, scope_id: str, detail_key: str, detail_text: str, ...): ...
```

- [ ] **Step 4: Run the new service tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/memory/test_structure_enhancement_service.py tests/memory/test_continuity_detail_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/structure_enhancement_service.py src/copaw/memory/continuity_detail_service.py tests/memory/test_structure_enhancement_service.py tests/memory/test_continuity_detail_service.py
git commit -m "feat: add memory structure enhancement services"
```

---

### Task 3: Feed Graph And Activation Signals Into Sleep

**Files:**
- Modify: `src/copaw/memory/sleep_service.py`
- Modify: `src/copaw/memory/sleep_inference_service.py`
- Modify: `src/copaw/memory/knowledge_graph_service.py`
- Modify: `src/copaw/memory/activation_service.py`
- Test: `tests/state/test_memory_sleep_service.py`
- Test: `tests/memory/test_knowledge_graph_service.py`
- Test: `tests/memory/test_subgraph_activation_service.py`

- [ ] **Step 1: Write failing tests for graph-fed sleep output**

```python
def test_sleep_service_uses_relation_views_and_activation_paths_to_build_continuity_anchors(tmp_path):
    result = sleep.run_sleep_job(scope_type="work_context", scope_id="ctx-1")
    overlay = result["work_context_overlay"]
    assert "continuity_anchors" in overlay.metadata
    assert overlay.metadata["continuity_anchors"]
```

- [ ] **Step 2: Run the failing tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_memory_sleep_service.py -k "continuity_anchors or top_relations" -q`
Expected: FAIL because anchors/slots not yet produced

- [ ] **Step 3: Upgrade the sleep inference input**

```python
inferred = self._inference_service.infer(
    ...,
    relation_views=relation_views,
    graph_focus=knowledge_graph_service.extract_compact_graph_summary(...),
    activation_summary=activation_service.activate_for_query(...).metadata,
)
```

- [ ] **Step 4: Write upgraded overlay/profile payloads**

```python
overlay_metadata = {
    "continuity_anchors": anchors,
    "slot_layout": slot_layout,
    "dynamic_slots": dynamic_slots,
}
```

- [ ] **Step 5: Run the graph/sleep test matrix**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_memory_sleep_service.py tests/memory/test_knowledge_graph_service.py tests/memory/test_subgraph_activation_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/memory/sleep_service.py src/copaw/memory/sleep_inference_service.py src/copaw/memory/knowledge_graph_service.py src/copaw/memory/activation_service.py tests/state/test_memory_sleep_service.py tests/memory/test_knowledge_graph_service.py tests/memory/test_subgraph_activation_service.py
git commit -m "feat: feed graph signals into memory sleep outputs"
```

---

### Task 4: Add Strong Detail Write-In To Daytime And Sleep Chains

**Files:**
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/memory/continuity_detail_service.py`
- Test: `tests/memory/test_knowledge_writeback_service.py`
- Test: `tests/kernel/test_memory_recall_integration.py`
- Test: `tests/state/test_memory_services.py`

- [ ] **Step 1: Write failing tests for strong detail retention**

```python
def test_high_value_detail_enters_overlay_priority_surface(tmp_path):
    writeback.record_fact(..., text="Do not average down after stop-loss.")
    snapshot = recall_service.recall(query="risk boundary", work_context_id="ctx-1")
    assert snapshot.profile.overlay_id is not None
    assert "Do not average down" in snapshot.profile.summary
```

- [ ] **Step 2: Run the failing tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/memory/test_knowledge_writeback_service.py tests/kernel/test_memory_recall_integration.py -k "strong_detail or risk boundary" -q`
Expected: FAIL

- [ ] **Step 3: Implement model-first plus rule-backstop selection**

```python
selected = continuity_detail_service.select_strong_details(
    scope_type=scope_type,
    scope_id=scope_id,
    graph_signals=graph_signals,
    candidate_facts=fact_entries,
)
```

- [ ] **Step 4: Refresh overlay/profile after new strong details land**

Run the daytime refresh path through:
- `retain_service`
- `knowledge_writeback_service`
- `industry/service_lifecycle.py`
- `query_execution_runtime.py`

- [ ] **Step 5: Run the strong-detail regression suite**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/memory/test_knowledge_writeback_service.py tests/kernel/test_memory_recall_integration.py tests/state/test_memory_services.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/memory/retain_service.py src/copaw/memory/knowledge_writeback_service.py src/copaw/industry/service_lifecycle.py src/copaw/kernel/query_execution_runtime.py src/copaw/memory/continuity_detail_service.py tests/memory/test_knowledge_writeback_service.py tests/kernel/test_memory_recall_integration.py tests/state/test_memory_services.py
git commit -m "feat: add strong detail write-in for memory continuity"
```

---

### Task 5: Make Structure Proposal Apply Materialize Active Truth

**Files:**
- Create: `src/copaw/memory/structure_proposal_executor.py`
- Modify: `src/copaw/memory/sleep_service.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/state/test_memory_sleep_service.py`

- [ ] **Step 1: Write failing tests for real apply side effects**

```python
def test_apply_structure_proposal_rewrites_active_overlay_and_switches_read_layer(tmp_path):
    applied = client.post(f"/runtime-center/memory/sleep/structure-proposals/{proposal_id}/apply", json={"actor": "tester"})
    payload = client.get("/runtime-center/memory/surface?work_context_id=ctx-1").json()
    assert payload["sleep"]["work_context_overlay"]["overlay_id"] == "overlay:ctx-1:v2"
```

- [ ] **Step 2: Run the failing tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_memory_api.py tests/state/test_memory_sleep_service.py -k "apply_structure_proposal" -q`
Expected: FAIL because apply only changes status

- [ ] **Step 3: Implement the executor**

```python
class StructureProposalExecutor:
    def apply(self, *, proposal_id: str, actor: str | None, note: str | None) -> MemoryStructureProposalRecord: ...
```

- [ ] **Step 4: Wire the router to the executor**

```python
record = service.apply_structure_proposal(
    proposal_id=proposal_id,
    decided_by=payload.actor,
    note=payload.note,
)
```

- [ ] **Step 5: Run the apply regression suite**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_memory_api.py tests/state/test_memory_sleep_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/memory/structure_proposal_executor.py src/copaw/memory/sleep_service.py src/copaw/app/routers/runtime_center_routes_memory.py tests/app/test_runtime_center_memory_api.py tests/state/test_memory_sleep_service.py
git commit -m "feat: materialize active memory truth on proposal apply"
```

---

### Task 6: Reprioritize Formal Read Chain Around Overlay, Anchors, And Strong Details

**Files:**
- Modify: `src/copaw/memory/recall_service.py`
- Modify: `src/copaw/memory/profile_service.py`
- Modify: `src/copaw/memory/surface_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Test: `tests/kernel/test_memory_recall_integration.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/memory/test_surface_service.py`

- [ ] **Step 1: Write failing tests for read-order truth**

```python
def test_recall_prefers_overlay_anchors_and_strong_details_before_related_scope_fallback(tmp_path):
    result = recall_service.recall(query="what must not be forgotten", work_context_id="ctx-1")
    assert result.profile.read_layer == "work_context_overlay"
    assert "continuity_anchors" in result.profile.metadata
```

- [ ] **Step 2: Run the failing tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py -k "overlay or continuity_anchors or truth_first" -q`
Expected: FAIL

- [ ] **Step 3: Reorder the read chain**

Target order:
1. `work_context_overlay / industry_profile`
2. continuity anchors and strong details
3. graph relation summary
4. related-scope fact fallback
5. lexical fallback

- [ ] **Step 4: Expose explicit read metadata**

```python
profile.metadata["continuity_anchors"] = anchors
profile.metadata["strong_details"] = details
profile.metadata["slot_layout"] = slot_layout
```

- [ ] **Step 5: Run the read-chain regression suite**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_memory_api.py tests/memory/test_surface_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/memory/recall_service.py src/copaw/memory/profile_service.py src/copaw/memory/surface_service.py src/copaw/kernel/query_execution_prompt.py src/copaw/kernel/main_brain_chat_service.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_memory_api.py tests/memory/test_surface_service.py
git commit -m "feat: prioritize overlay anchors in truth-first memory reads"
```

---

### Task 7: Add Manual Pin API And Simplified Runtime Center / Knowledge Read Surfaces

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/routers/runtime_center_request_models.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Write failing frontend/backend contract tests**

```tsx
it("shows continuity anchors and pending memory proposals in Runtime Center", async () => {
  render(<RuntimeCenterPage />);
  expect(await screen.findByText("当前最该记住")).toBeInTheDocument();
});
```

```tsx
it("shows dynamic slots, long-term preferences, and pinned details in Knowledge", async () => {
  render(<KnowledgePage />);
  expect(await screen.findByText("行业长期偏好")).toBeInTheDocument();
});
```

```python
def test_pin_continuity_detail_enters_formal_memory_truth(client):
    response = client.post(
        "/runtime-center/memory/continuity-details/pin",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "detail_key": "risk-boundary",
            "detail_text": "Do not average down after stop-loss.",
        },
    )
    assert response.status_code == 200
```

- [ ] **Step 2: Run the failing tests**

Run: `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: FAIL

- [ ] **Step 3: Extend the backend payloads**

Add:
- continuity anchor summary
- strong detail summary
- dynamic slot summary
- long-term preference summary
- pending structure proposal summary
- manual pin write action and readback payload

- [ ] **Step 4: Render the simplified Runtime Center and structured Knowledge sections**

Runtime Center:
- current continuity anchors
- key constraints
- key conflicts
- pending proposals

Knowledge:
- industry baseline
- work-context memory
- key objects / relations
- strong details
- dynamic slots / long-term preferences
- proposal / diff / rollback / manual pin

- [ ] **Step 5: Run frontend tests and build**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_memory_api.py -k "pin_continuity_detail or memory_surface" -q`
Expected: PASS

Run: `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

Run: `cmd /c npm --prefix console run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/routers/runtime_center_routes_memory.py src/copaw/app/routers/runtime_center_request_models.py src/copaw/app/routers/runtime_center_payloads.py console/src/pages/Knowledge/index.tsx console/src/pages/Knowledge/index.test.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/index.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: surface industry memory structure in runtime center and knowledge"
```

---

### Task 8: Run Long-Chain Regression And Real Smoke

**Files:**
- Create: `tests/app/test_memory_structure_enhancement_smoke.py`
- Modify: `tests/app/test_cron_manager.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Write the long-chain smoke**

```python
def test_memory_structure_enhancement_long_chain_smoke(tmp_path):
    # same work_context, repeated rounds, conflict insertion, restart, scheduled sleep, proposal apply
    ...
```

- [ ] **Step 2: Run focused backend regressions**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_memory_structure_enhancement_repository.py tests/memory/test_structure_enhancement_service.py tests/memory/test_continuity_detail_service.py tests/state/test_memory_sleep_service.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_memory_api.py tests/memory/test_knowledge_writeback_service.py tests/memory/test_knowledge_graph_service.py tests/app/test_cron_manager.py::test_cron_manager_runs_memory_sleep_jobs_after_heartbeat tests/app/test_runtime_bootstrap_helpers.py::test_warm_runtime_memory_services_runs_idle_sleep_catchup_when_available tests/app/test_memory_structure_enhancement_smoke.py -q`
Expected: PASS

- [ ] **Step 2a: Verify diff/rollback still preserves new structure fields**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_memory_api.py -k "diff or rollback" -q`
Expected: PASS with `continuity_anchors / strong_details / slot_layout / long_term_preferences` visible in diffed or rolled-back active payloads

- [ ] **Step 3: Run frontend tests and build again**

Run: `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

Run: `cmd /c npm --prefix console run build`
Expected: PASS

- [ ] **Step 4: Run a real live smoke**

Suggested command:

```bash
PYTHONPATH=src C:\Python312\python.exe tests/app/test_memory_structure_enhancement_smoke.py
```

Expected:
- same work_context survives multiple rounds
- graph-fed sleep output remains stable
- strong details survive restart
- applied proposal changes active read layer
- Runtime Center / Knowledge payloads stay aligned

- [ ] **Step 5: Sync docs**

Update:
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

- [ ] **Step 6: Commit**

```bash
git add tests/app/test_memory_structure_enhancement_smoke.py TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md
git commit -m "test: verify industry memory structure enhancement end to end"
```

---

## Execution Notes

- Do not create any second durable memory truth source.
- Reuse the existing four底座 explicitly:
  - `related-scope recall`
  - `MemoryRelationViewRecord`
  - `MemoryActivationService`
  - `KnowledgeGraphService`
- `related-scope recall` must be demoted to fallback, not deleted.
- `proposal apply` is not complete until active overlay/profile versions really change.
- `Runtime Center` must stay simplified; heavy detail belongs in `Knowledge`.
- Any new manual pin action must remain inside formal memory truth and not create page-local-only state.
- Promotion is not enough; stale or unhelpful industry slots must also be demotable and test-covered.
- Scheduled sleep and restart catch-up must stay green while this enhancement lands.
