# External Executor Runtime Hard-Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CoPaw 收口成“上层主脑框架 + 可插拔外部执行 runtime”架构，先接通 `Codex App Server`，再退役本地多 agent 执行脑。

**Architecture:** 保留 `MainBrain / Memory / Knowledge / Assignment / Evidence / Report / Runtime Center` 这条正式真相链，不再让 CoPaw 自己维护浏览器/桌面/文档执行脑。复用现有 `external_runtime / external_adapter / donor` 资产，统一改造成 `ExecutorRuntime` 接入层；第一适配器是 `Codex App Server`，后续可扩展到其他开源智能体 runtime。

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Codex App Server protocol, Runtime Center frontend

---

## Reality Sync (2026-04-20)

- 当前主脑骨架已经存在，正式真相链位于：
  - `src/copaw/kernel/turn_executor.py`
  - `src/copaw/kernel/main_brain_chat_service.py`
  - `src/copaw/kernel/main_brain_orchestrator.py`
  - `src/copaw/state/main_brain_service.py`
  - `src/copaw/state/models_goals_tasks.py`
- 当前本地多执行位执行脑仍然存在，主要位于：
  - `src/copaw/kernel/actor_worker.py`
  - `src/copaw/kernel/actor_supervisor.py`
  - `src/copaw/kernel/actor_mailbox.py`
  - `src/copaw/kernel/delegation_service.py`
  - `src/copaw/state/models_agents_runtime.py`
- 当前仓库已经有一套可复用的外部 runtime / adapter / donor 契约，不应重写：
  - `src/copaw/state/models_external_runtime.py`
  - `src/copaw/state/external_runtime_service.py`
  - `src/copaw/capabilities/external_adapter_contracts.py`
  - `src/copaw/capabilities/external_adapter_execution.py`
  - `src/copaw/capabilities/external_runtime_execution.py`
  - `src/copaw/capabilities/project_donor_contracts.py`
- 当前文档刚新增了一个偏 `Codex-only` 的硬切 spec：
  - `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
- 当前最终方向已经收口成：
  - `CoPaw = 主脑框架`
  - `ExecutorRuntime = 可插拔外部执行层`
  - `Codex = 第一适配器，不是唯一适配器`
- 第一阶段不删除浏览器/桌面/文档底座代码，只把它们从正式执行脑降级为待退役遗留层。

---

## File Map

**Docs and architecture sync**

- Modify: `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DEPRECATION_LEDGER.md`

**New executor runtime formal layer**

- Create: `src/copaw/state/models_executor_runtime.py`
- Create: `src/copaw/state/executor_runtime_service.py`
- Create: `src/copaw/kernel/executor_runtime_port.py`
- Create: `src/copaw/kernel/executor_event_ingest_service.py`
- Create: `tests/state/test_executor_runtime_service.py`
- Create: `tests/kernel/test_executor_event_ingest_service.py`

**Refactor reusable external runtime assets**

- Modify: `src/copaw/state/models_external_runtime.py`
- Modify: `src/copaw/state/external_runtime_service.py`
- Modify: `src/copaw/capabilities/external_adapter_contracts.py`
- Modify: `src/copaw/capabilities/external_adapter_execution.py`
- Modify: `src/copaw/capabilities/external_runtime_execution.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Create: `tests/capabilities/test_executor_runtime_contracts.py`
- Create: `tests/capabilities/test_executor_runtime_execution.py`

**Codex first adapter**

- Create: `src/copaw/adapters/executors/__init__.py`
- Create: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Create: `src/copaw/adapters/executors/codex_protocol.py`
- Create: `tests/adapters/test_codex_app_server_adapter.py`

**Main brain integration**

- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Create: `tests/kernel/test_main_brain_executor_runtime_integration.py`

**Runtime Center read model**

- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/execution_runtime_projection.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.ts`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.test.tsx`
- Create: `tests/app/test_runtime_center_executor_runtime_projection.py`

**Retirement candidates**

- Modify then delete later:
  - `src/copaw/kernel/actor_worker.py`
  - `src/copaw/kernel/actor_supervisor.py`
  - `src/copaw/kernel/actor_mailbox.py`
  - `src/copaw/kernel/delegation_service.py`
  - `src/copaw/state/models_agents_runtime.py`
- Deferred delete after executor chain proves stable:
  - `src/copaw/agents/tools/browser_control.py`
  - `src/copaw/agents/tools/desktop_actuation.py`
  - `src/copaw/agents/tools/document_surface.py`
  - `src/copaw/capabilities/browser_runtime.py`
  - `src/copaw/adapters/desktop/windows_host.py`
  - `src/copaw/adapters/desktop/windows_mcp_server.py`
  - `src/copaw/environments/surface_execution/browser/service.py`
  - `src/copaw/environments/surface_execution/desktop/service.py`
  - `src/copaw/environments/surface_execution/document/service.py`

---

## Task 1: Sync The Architecture Docs To The New Generic Runtime Direction

**Files:**
- Modify: `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DEPRECATION_LEDGER.md`

- [ ] **Step 1: Write a failing architecture contract test note in the plan**

Add a checklist note to the modified spec stating that the previous `Codex-only` wording is obsolete if it still implies `browser/desktop/document` are deleted before a generic executor layer exists.

- [ ] **Step 2: Review the current spec and mark the exact sections to revise**

Run: `rg -n "Codex-only|Codex App Server|browser|desktop|document|actor_worker|delegation" docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md DEPRECATION_LEDGER.md`

Expected: existing `Codex-first` and old executor/runtime wording is located for replacement.

- [ ] **Step 3: Update the design doc to state the new core architecture**

Required outcome:

```text
CoPaw = main-brain framework
ExecutorRuntime = pluggable external executor runtime seam
Codex = first adapter
Hermes/others = future adapters
Old local actor runtime = retirement target
```

- [ ] **Step 4: Update transition and deprecation docs**

Required content:

- old local actor runtime marked as retired target
- old browser/desktop/document execution surfaces marked as deferred retirement
- `external_runtime / external_adapter / donor` assets marked as rename-and-reuse assets

- [ ] **Step 5: Commit docs sync**

```bash
git add docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md DEPRECATION_LEDGER.md
git commit -m "docs: retarget hard-cut plan to generic executor runtimes"
```

---

## Task 2: Introduce Formal Executor Runtime Records And Service

**Files:**
- Create: `src/copaw/state/models_executor_runtime.py`
- Create: `src/copaw/state/executor_runtime_service.py`
- Create: `tests/state/test_executor_runtime_service.py`
- Modify: `src/copaw/state/models_external_runtime.py`
- Modify: `src/copaw/state/external_runtime_service.py`

- [ ] **Step 1: Write the failing tests for executor runtime truth**

```python
def test_executor_runtime_instance_records_executor_kind_and_scope():
    record = ExecutorRuntimeInstanceRecord(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
    )
    assert record.executor_id == "codex"
    assert record.protocol_kind == "app_server"
```

```python
def test_executor_runtime_service_reuses_active_runtime_for_same_scope():
    service = ExecutorRuntimeService(repository=repo)
    first = service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
    )
    second = service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
    )
    assert second.runtime_id == first.runtime_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/state/test_executor_runtime_service.py -q`

Expected: FAIL with missing module or missing `ExecutorRuntimeInstanceRecord`.

- [ ] **Step 3: Implement the minimal executor runtime model**

```python
class ExecutorRuntimeInstanceRecord(UpdatedRecord):
    runtime_id: str
    executor_id: str
    protocol_kind: str
    scope_kind: str
    assignment_id: str | None = None
    role_id: str | None = None
    thread_id: str | None = None
    runtime_status: str = "starting"
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Implement minimal service reuse and lifecycle helpers**

Required methods:

- `get_runtime(...)`
- `list_runtimes(...)`
- `create_or_reuse_runtime(...)`
- `mark_runtime_ready(...)`
- `mark_runtime_stopped(...)`

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/state/test_executor_runtime_service.py -q`

Expected: PASS

- [ ] **Step 6: Bridge the old external runtime service instead of deleting it immediately**

Implementation note:

- keep `ExternalCapabilityRuntimeInstanceRecord` readable during transition
- add translation helpers or aliases so new executor runtime logic can reuse the same repository patterns

- [ ] **Step 7: Commit the formal executor runtime layer**

```bash
git add src/copaw/state/models_executor_runtime.py src/copaw/state/executor_runtime_service.py src/copaw/state/models_external_runtime.py src/copaw/state/external_runtime_service.py tests/state/test_executor_runtime_service.py
git commit -m "feat: add formal executor runtime state layer"
```

---

## Task 3: Refactor Donor And External Runtime Assets Into Generic Executor Contracts

**Files:**
- Modify: `src/copaw/capabilities/external_adapter_contracts.py`
- Modify: `src/copaw/capabilities/external_adapter_execution.py`
- Modify: `src/copaw/capabilities/external_runtime_execution.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Create: `tests/capabilities/test_executor_runtime_contracts.py`
- Create: `tests/capabilities/test_executor_runtime_execution.py`

- [ ] **Step 1: Write failing tests for generic executor protocol surfaces**

```python
def test_executor_protocol_surface_supports_app_server():
    surface = ExecutorProtocolSurface(
        protocol_surface_kind="app_server",
        transport_kind="sdk",
        call_surface_ref="codex-app-server",
        formal_adapter_eligible=True,
    )
    assert surface.protocol_surface_kind == "app_server"
```

```python
def test_cli_runtime_without_event_contract_is_not_formal_executor():
    payload = derive_executor_surface({"execute_command": "python -m tool"})
    assert payload.protocol_surface_kind == "cli_runtime"
    assert payload.formal_adapter_eligible is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_executor_runtime_contracts.py tests/capabilities/test_executor_runtime_execution.py -q`

Expected: FAIL because `app_server` protocol kind is not supported yet.

- [ ] **Step 3: Extend protocol taxonomy**

Required additions:

- `app_server`
- `event_stream`
- `thread_turn_control`

Required rule:

- a runtime is only formal if it exposes controllable lifecycle plus event return path

- [ ] **Step 4: Rename donor-oriented helpers in code and docstrings**

Examples:

- “donor” -> “executor runtime provider” where the code is now about runtime intake
- keep migration aliases only if tests require them

- [ ] **Step 5: Keep MCP/API/SDK/CLI-runtime support**

Required outcome:

- `Codex` can land as `app_server`
- future `Hermes` can land as `api / sdk / cli_runtime` depending on its real protocol surface

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_executor_runtime_contracts.py tests/capabilities/test_executor_runtime_execution.py -q`

Expected: PASS

- [ ] **Step 7: Commit the contract refactor**

```bash
git add src/copaw/capabilities/external_adapter_contracts.py src/copaw/capabilities/external_adapter_execution.py src/copaw/capabilities/external_runtime_execution.py src/copaw/capabilities/project_donor_contracts.py tests/capabilities/test_executor_runtime_contracts.py tests/capabilities/test_executor_runtime_execution.py
git commit -m "refactor: retarget external runtime contracts to executor runtimes"
```

---

## Task 4: Add The Codex App Server Adapter As The First Concrete Executor Runtime

**Files:**
- Create: `src/copaw/kernel/executor_runtime_port.py`
- Create: `src/copaw/adapters/executors/__init__.py`
- Create: `src/copaw/adapters/executors/codex_protocol.py`
- Create: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Create: `tests/adapters/test_codex_app_server_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

```python
def test_codex_adapter_starts_thread_and_turn_for_assignment():
    adapter = CodexAppServerAdapter(transport=fake_transport)
    result = adapter.start_assignment_turn(
        assignment_id="assign-1",
        project_root="D:/agents/codex-project",
        prompt="Implement the task",
    )
    assert result.thread_id == "thread-1"
    assert result.turn_id == "turn-1"
```

```python
def test_codex_adapter_normalizes_plan_and_file_events():
    adapter = CodexAppServerAdapter(transport=fake_transport)
    event = adapter.normalize_event({"method": "turn/plan/updated", "params": {"plan": []}})
    assert event.event_type == "plan_submitted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/adapters/test_codex_app_server_adapter.py -q`

Expected: FAIL with missing adapter module.

- [ ] **Step 3: Implement the executor runtime port**

Required interface:

- `ensure_runtime(...)`
- `start_assignment_turn(...)`
- `steer_turn(...)`
- `stop_turn(...)`
- `subscribe_events(...)`

- [ ] **Step 4: Implement the Codex protocol shim**

Required outputs:

- typed request builders for thread/turn lifecycle
- event normalizer for plan, diff, command, file, mcp, complete, failed

- [ ] **Step 5: Implement the concrete adapter**

Minimum support:

- create or resume thread
- start turn
- consume event stream
- normalize into CoPaw event types

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/adapters/test_codex_app_server_adapter.py -q`

Expected: PASS

- [ ] **Step 7: Commit the first executor adapter**

```bash
git add src/copaw/kernel/executor_runtime_port.py src/copaw/adapters/executors src/copaw/adapters/executors/codex_protocol.py src/copaw/adapters/executors/codex_app_server_adapter.py tests/adapters/test_codex_app_server_adapter.py
git commit -m "feat: add codex app server executor adapter"
```

---

## Task 5: Integrate Assignment -> Executor Runtime -> Event -> Evidence/Report

**Files:**
- Create: `src/copaw/kernel/executor_event_ingest_service.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Create: `tests/kernel/test_executor_event_ingest_service.py`
- Create: `tests/kernel/test_main_brain_executor_runtime_integration.py`

- [ ] **Step 1: Write failing event-ingest tests**

```python
def test_plan_event_becomes_executor_event_record():
    service = ExecutorEventIngestService(...)
    record = service.ingest_event(
        assignment_id="assign-1",
        event_type="plan_submitted",
        payload={"plan": [{"step": "Implement"}]},
    )
    assert record.event_type == "plan_submitted"
```

```python
def test_completed_turn_generates_agent_report():
    result = service.ingest_event(
        assignment_id="assign-1",
        event_type="task_completed",
        payload={"summary": "done"},
    )
    assert result.generated_report is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_executor_event_ingest_service.py tests/kernel/test_main_brain_executor_runtime_integration.py -q`

Expected: FAIL with missing ingest service and integration hooks.

- [ ] **Step 3: Implement event ingest service**

Required mappings:

- plan -> executor event record
- command/file/mcp -> evidence
- completed/failed -> agent report

- [ ] **Step 4: Wire the main brain orchestrator to the executor port**

Required flow:

- create assignment
- select executor runtime
- ensure runtime binding
- start assignment turn
- subscribe/ingest events

- [ ] **Step 5: Keep existing assignment truth intact**

Required rule:

- no second task truth source
- no free-floating “Codex said X” chat text as runtime truth

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_executor_event_ingest_service.py tests/kernel/test_main_brain_executor_runtime_integration.py -q`

Expected: PASS

- [ ] **Step 7: Commit main-brain integration**

```bash
git add src/copaw/kernel/executor_event_ingest_service.py src/copaw/kernel/main_brain_orchestrator.py src/copaw/kernel/turn_executor.py src/copaw/kernel/runtime_coordination.py src/copaw/app/runtime_service_graph.py src/copaw/app/runtime_bootstrap_execution.py src/copaw/app/runtime_bootstrap_models.py tests/kernel/test_executor_event_ingest_service.py tests/kernel/test_main_brain_executor_runtime_integration.py
git commit -m "feat: wire main brain to executor runtime events"
```

---

## Task 6: Project Runtime Center On The New Executor Runtime And Retire The Old Actor Brain

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/execution_runtime_projection.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.ts`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.test.tsx`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/actor_mailbox.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/state/models_agents_runtime.py`
- Create: `tests/app/test_runtime_center_executor_runtime_projection.py`

- [ ] **Step 1: Write failing Runtime Center projection tests**

```python
def test_runtime_center_shows_executor_thread_status_for_assignment():
    payload = build_runtime_center_payload(...)
    assert payload["executors"][0]["executor_id"] == "codex"
```

```tsx
it("prefers executor runtime state over retired actor runtime state", () => {
  const view = buildActorRuntimeCard({ executorRuntime: { executorId: "codex" } });
  expect(view.primaryLabel).toContain("codex");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_executor_runtime_projection.py -q`

Run: `npm test -- --runInBand console/src/pages/RuntimeCenter/viewHelpers.test.tsx`

Expected: FAIL because Runtime Center still reads actor runtime first.

- [ ] **Step 3: Repoint Runtime Center to executor runtime truth**

Required outcome:

- show executor runtime status
- show thread/turn binding
- keep assignment/evidence/report views intact

- [ ] **Step 4: Deactivate old actor runtime code paths**

Required approach:

- stop new writes to actor runtime truth
- mark legacy modules as retired or unreachable
- only delete physically once all tests pass on the new path

- [ ] **Step 5: Run focused regression**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_executor_runtime_projection.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/state/test_executor_runtime_service.py -q`

Expected: PASS

- [ ] **Step 6: Commit runtime-center cutover and actor retirement**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/execution_runtime_projection.py src/copaw/app/routers/runtime_center_routes_core.py console/src/pages/RuntimeCenter/viewHelpers.ts console/src/pages/RuntimeCenter/viewHelpers.test.tsx src/copaw/kernel/actor_worker.py src/copaw/kernel/actor_supervisor.py src/copaw/kernel/actor_mailbox.py src/copaw/kernel/delegation_service.py src/copaw/state/models_agents_runtime.py tests/app/test_runtime_center_executor_runtime_projection.py
git commit -m "refactor: cut runtime center over to executor runtimes"
```

---

## Task 7: Verification, Cleanup, And Deferred-Retirement Ledger

**Files:**
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run backend focused regression**

Run: `PYTHONPATH=src python -m pytest tests/state/test_executor_runtime_service.py tests/capabilities/test_executor_runtime_contracts.py tests/capabilities/test_executor_runtime_execution.py tests/adapters/test_codex_app_server_adapter.py tests/kernel/test_executor_event_ingest_service.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_runtime_center_executor_runtime_projection.py -q`

Expected: PASS

- [ ] **Step 2: Run frontend focused regression**

Run: `npm test -- --runInBand console/src/pages/RuntimeCenter/viewHelpers.test.tsx`

Expected: PASS

- [ ] **Step 3: Update deprecation ledger for deferred removals**

Required entries:

- browser runtime local execution layer
- desktop host local execution layer
- document surface local execution layer

- [ ] **Step 4: Update task status**

Required note:

- old actor runtime retired or retirement-started
- executor runtime seam landed
- Codex first adapter landed
- browser/desktop/document local execution layer still pending final delete

- [ ] **Step 5: Commit verification and cleanup**

```bash
git add DEPRECATION_LEDGER.md TASK_STATUS.md
git commit -m "docs: record executor runtime cutover verification"
```

---

## Non-Goals For This Plan

- Do not delete browser/desktop/document local execution files in the first commit set.
- Do not build Hermes integration in the same phase.
- Do not invent a second memory or runtime truth chain inside external executors.
- Do not keep local actor runtime and executor runtime as long-lived peers after cutover.

---

## Exit Criteria

This plan is complete only when all of the following are true:

- `Assignment -> ExecutorRuntime -> Event -> Evidence/Report` mainline works
- `Codex App Server` is the first working executor adapter
- Runtime Center reads executor runtime truth instead of retired actor runtime truth
- old local actor runtime stops being the active execution path
- deferred local browser/desktop/document execution layers are explicitly recorded for later deletion

---

## Execution Notes

- Prefer small commits per task.
- Keep aliases and bridges only where they reduce migration risk in the current phase.
- Any compatibility shim added during cutover must include an explicit delete condition in `DEPRECATION_LEDGER.md`.
