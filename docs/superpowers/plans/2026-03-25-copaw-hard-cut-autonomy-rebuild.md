# CoPaw Hard-Cut Autonomy Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-cut CoPaw from the mixed `goal/task/schedule` + `lane/backlog/cycle/assignment/report` state into a single long-running autonomy kernel where the main brain only plans/assigns/supervises/synthesizes, execution flows strictly through assignments and workers, and the frontend exposes the real runtime chain.

**Architecture:** Introduce a dedicated `MainBrainOrchestrator`, demote `MainBrainChatService` to pure chat/state explanation, route every operator execution turn into `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> Synthesis/Replan`, collapse capability routing around `CapabilityMount + environment + surface`, and hard-cut the frontend/API to the runtime-center object model. Because the system is not yet live, use a short maintenance window, clear legacy runtime data, delete old truth-bearing paths instead of migrating them, and remove legacy UI/API entry points once the new chain is wired.

**Tech Stack:** Python 3, FastAPI, SQLite state repositories, Pydantic, pytest, TypeScript, React, Vitest, Runtime Center

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`
- Baseline status: `TASK_STATUS.md`
- Data model contract: `DATA_MODEL_DRAFT.md`
- API contract ledger: `API_TRANSITION_MAP.md`

---

## Scope Guardrails

- This is a hard cut. Do not preserve the old `goal/task/schedule` planning path once the new orchestrator chain exists.
- Historical runtime data may be deleted. Prefer state reset + baseline rebuild over migration adapters.
- `TaskRecord` may remain as the kernel execution record. `GoalRecord` may not remain as a main-brain planning object.
- `MainBrainChatService` must stop mutating formal runtime state in the background. All durable writes move to the orchestrator path.
- Unknown apps must route by `mounted capability + active environment + surface`, not by hard-coded app names.
- Keep `EnvironmentService` and `EvidenceLedger` as hard runtime dependencies; do not regress to prompt-only environment recovery.
- The repo currently has no initial commit. During execution, replace “commit” checkpoints with `git diff --stat` + saved verification output until a baseline commit exists.

## File Map

### Runtime hard-cut and orchestration

- Create: `src/copaw/kernel/main_brain_orchestrator.py`
- Create: `src/copaw/kernel/test_support/orchestrator_fixtures.py`
- Modify: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/_app.py`

### State-model hard cut

- Create: `scripts/reset_autonomy_runtime.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/industry/chat_writeback.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`

### Assignment / delegation / synthesis

- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/kernel/actor_mailbox.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`

### Capability routing / environment / evidence

- Create: `src/copaw/kernel/surface_routing.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/seat_gap_policy.py`

### Industry decomposition

- Create: `src/copaw/industry/bootstrap_service.py`
- Create: `src/copaw/industry/team_service.py`
- Create: `src/copaw/industry/view_service.py`
- Modify: `src/copaw/industry/service.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`

### Frontend hard cut

- Create: `console/src/runtime/controlChainPresentation.ts`
- Create: `console/src/runtime/controlChainPresentation.test.ts`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/pageHelpers.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`

### Runtime health / docs

- Create: `src/copaw/app/runtime_health_service.py`
- Modify: `src/copaw/app/routers/system.py`
- Modify: `src/copaw/agents/memory/memory_manager.py`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DEPRECATION_LEDGER.md`

### Tests

- Create: `tests/kernel/test_main_brain_orchestrator.py`
- Create: `tests/state/test_main_brain_hard_cut.py`
- Create: `tests/kernel/test_assignment_envelope.py`
- Create: `tests/kernel/test_surface_routing.py`
- Create: `tests/app/test_runtime_reset.py`
- Create: `tests/app/test_runtime_health_service.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/industry/test_report_synthesis.py`
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Modify: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Modify: `tests/app/test_runtime_center_api.py`
- Modify: `tests/app/test_system_api.py`
- Modify: `tests/agents/test_memory_manager_config.py`

### Task 1: Add a Hard-Cut Reset and Deprecation Baseline

**Files:**
- Create: `scripts/reset_autonomy_runtime.py`
- Create: `tests/app/test_runtime_reset.py`
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Write the failing reset/health test**

```python
def test_reset_autonomy_runtime_removes_legacy_phase1_state(tmp_path: Path) -> None:
    state_db = tmp_path / "state" / "phase1.sqlite3"
    evidence_db = tmp_path / "evidence" / "phase1.sqlite3"
    state_db.parent.mkdir(parents=True)
    evidence_db.parent.mkdir(parents=True)
    state_db.write_text("x", encoding="utf-8")
    evidence_db.write_text("y", encoding="utf-8")

    result = reset_autonomy_runtime(root=tmp_path, dry_run=False)

    assert result["removed_paths"] == [str(state_db), str(evidence_db)]
    assert not state_db.exists()
    assert not evidence_db.exists()
```

- [ ] **Step 2: Run the targeted test to confirm it fails**

Run: `python -m pytest tests/app/test_runtime_reset.py -q -k reset_autonomy_runtime`
Expected: FAIL because `reset_autonomy_runtime()` does not exist yet.

- [ ] **Step 3: Implement the reset script and deprecation ledger updates**

```python
def reset_autonomy_runtime(*, root: Path, dry_run: bool = False) -> dict[str, object]:
    removable = [
        root / "state" / "phase1.sqlite3",
        root / "evidence" / "phase1.sqlite3",
        root / "learning" / "phase1.sqlite3",
        root / "memory" / "qmd",
    ]
    ...
```

- [ ] **Step 4: Re-run the targeted test**

Run: `python -m pytest tests/app/test_runtime_reset.py -q -k reset_autonomy_runtime`
Expected: PASS.

- [ ] **Step 5: Dry-run the reset script against the workspace**

Run: `python scripts/reset_autonomy_runtime.py --root . --dry-run`
Expected: lists removable runtime artifacts without deleting them.

### Task 2: Hard-Split Pure Chat from Formal Orchestration

**Files:**
- Create: `src/copaw/kernel/main_brain_orchestrator.py`
- Create: `tests/kernel/test_main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/kernel/test_main_brain_orchestrator.py`

- [ ] **Step 1: Write the failing split-behavior tests**

```python
async def test_main_brain_chat_service_never_applies_writeback_directly() -> None:
    result = await collect_chat_turn(...)
    assert result.applied_writeback is False
    assert result.kickoff_started is False


async def test_turn_executor_routes_execute_turns_to_orchestrator() -> None:
    mode = _resolve_auto_chat_mode(query="帮主脑规划本周运营并安排执行", request=req, msgs=msgs)
    assert mode == "orchestrate"
```

- [ ] **Step 2: Run the targeted kernel tests to confirm they fail**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_orchestrator.py -q`
Expected: FAIL because the chat path still performs background writeback/kickoff and the orchestrator service does not exist yet.

- [ ] **Step 3: Introduce `MainBrainOrchestrator` and demote `MainBrainChatService`**

```python
class MainBrainOrchestrator:
    async def ingest_operator_turn(self, *, msgs: list[Any], request: Any) -> OrchestratorResult:
        ...
```

Rules to implement:
- `MainBrainChatService` becomes pure chat/state explanation only
- `MainBrainIntakeContract` only classifies/hands off
- `KernelTurnExecutor` calls orchestrator for formal runtime turns
- `runtime_service_graph.py` wires a single orchestrator instance

- [ ] **Step 4: Re-run the targeted kernel tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_orchestrator.py -q`
Expected: PASS.

- [ ] **Step 5: Record a local checkpoint**

Run: `git diff --stat`
Expected: shows only the orchestration split files above.

### Task 3: Hard-Cut the State Chain to `strategy/lane/backlog/cycle/assignment/report`

**Files:**
- Create: `tests/state/test_main_brain_hard_cut.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/industry/chat_writeback.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/state/test_main_brain_hard_cut.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`

- [ ] **Step 1: Write the failing hard-cut state tests**

```python
def test_operator_turn_materializes_backlog_without_goal_record(...) -> None:
    result = service.ingest_operator_target(...)
    assert result.goal_id is None
    assert result.backlog_item_id is not None


def test_runtime_center_delegate_endpoint_is_removed_after_hard_cut(client) -> None:
    response = client.post("/api/runtime-center/tasks/task-1/delegate", json={})
    assert response.status_code in {404, 410}
```

- [ ] **Step 2: Run the targeted backend tests to confirm they fail**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
Expected: FAIL because the old goal/materialization path is still active.

- [ ] **Step 3: Remove the old planning truth path**

Implement the hard cut so that:
- operator execution turns no longer create `GoalRecord`
- backlog is written directly from orchestrator intake
- `goal -> backlog` and `schedule -> planning` materialization is deleted
- retired delegate/API paths are fully removed or converted to explicit `410 Gone`

- [ ] **Step 4: Re-run the targeted backend tests**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
Expected: PASS.

- [ ] **Step 5: Execute the state reset script for a clean runtime baseline**

Run: `python scripts/reset_autonomy_runtime.py --root .`
Expected: legacy runtime state is cleared so the new chain can boot from a clean baseline.

### Task 4: Tighten Assignment as the Only Execution Envelope

**Files:**
- Create: `tests/kernel/test_assignment_envelope.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/kernel/actor_mailbox.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Test: `tests/kernel/test_assignment_envelope.py`
- Test: `tests/industry/test_report_synthesis.py`

- [ ] **Step 1: Write the failing assignment/report-loop tests**

```python
def test_assignment_is_the_only_leaf_execution_envelope(...) -> None:
    assignment = build_assignment(...)
    assert assignment.task_id is not None
    assert assignment.owner_agent_id is not None
    assert assignment.metadata["execution_source"] == "assignment"


def test_synthesis_requests_replan_on_conflicting_reports(...) -> None:
    payload = synthesize_reports([success_report, failed_report])
    assert payload["needs_replan"] is True
```

- [ ] **Step 2: Run the targeted envelope/synthesis tests to confirm they fail**

Run: `python -m pytest tests/kernel/test_assignment_envelope.py tests/industry/test_report_synthesis.py -q`
Expected: FAIL because assignment ownership and synthesis/replan are not yet strict enough.

- [ ] **Step 3: Tighten assignment ownership and report-driven supervision**

Implement:
- assignment metadata as the sole leaf execution envelope
- mailbox/worker state tied back to assignment IDs
- report synthesis feeding explicit follow-up actions and replan signals
- prompt guidance updated so the control core synthesizes before delegating again

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest tests/kernel/test_assignment_envelope.py tests/industry/test_report_synthesis.py -q`
Expected: PASS.

- [ ] **Step 5: Smoke-check the supervision chain payloads**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q -k "assignment or report or synthesis"`
Expected: PASS with the supervision chain rooted in assignment/report objects.

### Task 5: Replace Keyword-Led Routing with `mount + environment + surface`

**Files:**
- Create: `src/copaw/kernel/surface_routing.py`
- Create: `tests/kernel/test_surface_routing.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/seat_gap_policy.py`
- Test: `tests/kernel/test_surface_routing.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Write the failing surface-routing tests**

```python
def test_unknown_app_name_routes_to_desktop_when_only_desktop_surface_is_mounted() -> None:
    decision = resolve_execution_surface(
        text="去文末天机里整理本机资料",
        mounted_surfaces={"desktop"},
        environment_hints={"desktop_session": True},
    )
    assert decision.surface == "desktop"


def test_unknown_site_routes_to_browser_when_browser_session_is_available() -> None:
    decision = resolve_execution_surface(
        text="去那个后台网页上发布草稿",
        mounted_surfaces={"browser"},
        environment_hints={"browser_session": True},
    )
    assert decision.surface == "browser"
```

- [ ] **Step 2: Run the targeted routing tests to confirm they fail**

Run: `python -m pytest tests/kernel/test_surface_routing.py -q`
Expected: FAIL because no centralized surface router exists yet.

- [ ] **Step 3: Implement the new router and shrink token tables to fallback-only**

```python
@dataclass(slots=True)
class SurfaceRouteDecision:
    surface: str | None
    source: str
    confidence: float
```

Rules to implement:
- primary routing from mounted capabilities
- secondary routing from active environment/session
- tertiary routing from explicit surface language
- token tables only as isolated fallback logic

- [ ] **Step 4: Re-run the targeted routing tests**

Run: `python -m pytest tests/kernel/test_surface_routing.py -q`
Expected: PASS.

- [ ] **Step 5: Run the integration routing tests**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q -k "surface or desktop or browser"`
Expected: PASS with no requirement to hard-code unknown app names.

### Task 6: Decompose `IndustryService` into Bootstrap / Team / View Responsibilities

**Files:**
- Create: `src/copaw/industry/bootstrap_service.py`
- Create: `src/copaw/industry/team_service.py`
- Create: `src/copaw/industry/view_service.py`
- Modify: `src/copaw/industry/service.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Write the failing composition tests**

```python
def test_industry_service_facade_delegates_bootstrap_to_bootstrap_service(...) -> None:
    result = industry_service.bootstrap_instance(...)
    assert result.instance_id is not None
    assert result.team is not None


def test_industry_service_facade_reads_runtime_detail_from_view_service(...) -> None:
    detail = industry_service.get_instance_detail(...)
    assert detail.current_cycle is not None or detail.backlog is not None
```

- [ ] **Step 2: Run the targeted industry API tests to confirm they fail**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: FAIL because the new composition services do not exist yet.

- [ ] **Step 3: Extract explicit services and thin the facade**

Implement:
- `BootstrapService` for industry compilation/bootstrap
- `TeamService` for staffing/team mutations
- `ViewService` for runtime detail aggregation
- `IndustryService` as a thin composition facade instead of a growing mixin shell

- [ ] **Step 4: Re-run the targeted industry API tests**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS.

- [ ] **Step 5: Check the facade surface area**

Run: `rg -n "class IndustryService|pass$|_Industry.*Mixin" src/copaw/industry`
Expected: `IndustryService` is a thin coordinator and mixin growth is reduced rather than expanded.

### Task 7: Hard-Cut the Frontend to the Runtime-Center Object Model

**Files:**
- Create: `console/src/runtime/controlChainPresentation.ts`
- Create: `console/src/runtime/controlChainPresentation.test.ts`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/pageHelpers.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Test: `console/src/runtime/controlChainPresentation.test.ts`
- Test: `console/src/pages/AgentWorkbench/executionSeatPresentation.test.ts`

- [ ] **Step 1: Write the failing presentation test for the control chain**

```ts
it("renders the supervision chain from writeback to replan", () => {
  const model = presentControlChain(detail);
  expect(model.nodes.map((n) => n.id)).toEqual([
    "writeback",
    "backlog",
    "cycle",
    "assignment",
    "report",
    "replan",
  ]);
});
```

- [ ] **Step 2: Run the targeted frontend tests to confirm they fail**

Run: `npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts src/pages/AgentWorkbench/executionSeatPresentation.test.ts`
Expected: FAIL because the shared presentation helper and new hard-cut runtime view do not exist yet.

- [ ] **Step 3: Implement the hard-cut runtime presentation**

Implement:
- shared presentation helper for control-chain / synthesis / environment / evidence cards
- `Industry` page focused on strategy/lane/backlog/cycle/assignment/report
- `RuntimeCenter` detail views focused on runtime truth, not legacy goal/task semantics
- `AgentWorkbench` execution seat panel aligned to assignment/report/environment/evidence

- [ ] **Step 4: Re-run the targeted frontend tests**

Run: `npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts src/pages/AgentWorkbench/executionSeatPresentation.test.ts`
Expected: PASS.

- [ ] **Step 5: Run the frontend build**

Run: `npm --prefix console run build`
Expected: PASS.

### Task 8: Expose Runtime Health and Memory Degradation Explicitly

**Files:**
- Create: `src/copaw/app/runtime_health_service.py`
- Modify: `src/copaw/app/routers/system.py`
- Modify: `src/copaw/agents/memory/memory_manager.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Test: `tests/app/test_system_api.py`
- Test: `tests/agents/test_memory_manager_config.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write the failing runtime-health tests**

```python
def test_system_self_check_surfaces_embedding_model_gap(client) -> None:
    payload = client.get("/api/system/self-check").json()
    names = {item["name"] for item in payload["checks"]}
    assert "memory_embedding_config" in names


def test_memory_manager_reports_vector_degraded_without_embedding_model_name() -> None:
    cfg = load_memory_config(...)
    assert cfg["vector_enabled"] is False
    assert "EMBEDDING_MODEL_NAME" in cfg["vector_disable_reason"]
```

- [ ] **Step 2: Run the targeted system/memory tests to confirm they fail**

Run: `python -m pytest tests/app/test_system_api.py tests/agents/test_memory_manager_config.py tests/app/test_runtime_center_api.py -q`
Expected: FAIL because the runtime health service and explicit embedding-gap surface do not exist yet.

- [ ] **Step 3: Implement explicit runtime-health surfaces**

Rules to implement:
- distinguish `core_runtime_ready`, `memory_vector_ready`, `browser_surface_ready`, and `desktop_surface_ready`
- expose degradation reasons as structured runtime health, not only logs
- surface the health blocks on the Runtime Center

- [ ] **Step 4: Re-run the targeted system/memory tests**

Run: `python -m pytest tests/app/test_system_api.py tests/agents/test_memory_manager_config.py tests/app/test_runtime_center_api.py -q`
Expected: PASS.

- [ ] **Step 5: Rebuild runtime state after health-service wiring**

Run: `python scripts/reset_autonomy_runtime.py --root .`
Expected: runtime databases and caches are reset so the new health surfaces reflect a clean baseline.

### Task 9: Final Legacy Deletion, Verification, and Status Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Remove any remaining goal-centric or retired runtime references**

Run:
```bash
rg -n "goal -> backlog|dispatch_active_goals|has_active_writeback_plan|/tasks/.*/delegate|GoalRecord" src/copaw console/src
```
Expected: only valid kernel-task or documentation references remain; no main-brain planning path still depends on them.

- [ ] **Step 2: Run the backend verification bundle**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_orchestrator.py tests/state/test_main_brain_hard_cut.py tests/kernel/test_assignment_envelope.py tests/kernel/test_surface_routing.py tests/industry/test_report_synthesis.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_runtime_center_api.py tests/app/test_system_api.py tests/agents/test_memory_manager_config.py -q`
Expected: PASS.

- [ ] **Step 3: Run the frontend verification bundle**

Run: `npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts src/pages/AgentWorkbench/executionSeatPresentation.test.ts`
Expected: PASS.

Run: `npm --prefix console run build`
Expected: PASS.

- [ ] **Step 4: Run the post-cut reset and boot smoke check**

Run:
```bash
python scripts/reset_autonomy_runtime.py --root .
python -m pytest tests/app/test_runtime_center_api.py -q -k "overview or detail or control"
```
Expected: PASS against a clean runtime baseline.

- [ ] **Step 5: Update the status/docs to reflect the completed hard cut**

Record in:
- `TASK_STATUS.md`: hard cut completed, old planning path removed
- `DEPRECATION_LEDGER.md`: old goal/planning chain deleted
- `DATA_MODEL_DRAFT.md`: new single planning truth
- `API_TRANSITION_MAP.md`: old UI/API paths removed, not migrated
