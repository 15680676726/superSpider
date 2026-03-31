# Claude Code Runtime Donor Adoption P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first stable canonical run path for CoPaw by introducing a formal turn loop, a unified execution context, and a single execution state machine, then prove the path through `POST /api/runtime-center/chat/run` with file/shell execution and evidence visibility.

**Architecture:** This plan implements only `P0` from the approved design spec. It keeps CoPaw's formal truth, orchestration, Runtime Center, and truth-first memory intact while hardening the lower runtime path. The first slice is intentionally narrow: add the new runtime skeleton, wire it into the existing orchestrator/executor path, and validate the path end-to-end with file/shell actions plus evidence readback. `P1` and `P2` require separate follow-up plans after this plan is green.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, Pytest, existing CoPaw kernel/state/evidence services.

---

## Scope Guard

This plan covers only `P0`:

- `turn_loop.py`
- `execution_context.py`
- `task_state_machine.py`
- file/shell capability path through the new execution front-door
- evidence writeback and Runtime Center visibility

Out of scope for this plan:

- MCP runtime hardening
- subagent/worker runtime donor adoption
- skill metadata formalization
- package/plugin binding
- sidecar file memory

## Execution Environment

Run this plan in a dedicated worktree. Do not implement from a dirty shared workspace.

Suggested commands:

```powershell
git worktree add .worktrees\claude-runtime-p0 -b feat/claude-runtime-p0
cd .worktrees\claude-runtime-p0
pip install -e .
```

## File Map

### New files

- `src/copaw/capabilities/execution_context.py`
  - Canonical execution context object for one runtime turn.
- `src/copaw/kernel/task_state_machine.py`
  - Single transition API for execution-state changes.
- `src/copaw/kernel/turn_loop.py`
  - Canonical single-turn execution loop.
- `tests/capabilities/test_execution_context.py`
  - Unit tests for execution context normalization and helpers.
- `tests/kernel/test_task_state_machine.py`
  - Unit tests for legal/illegal state transitions.
- `tests/kernel/test_turn_loop.py`
  - Unit tests for turn-loop stage ordering and failure handling.

### Existing files to modify

- `src/copaw/kernel/main_brain_orchestrator.py`
  - Attach canonical turn-loop inputs and stop duplicating runtime-stage decisions.
- `src/copaw/kernel/turn_executor.py`
  - Route formal execution turns through the new `turn_loop`.
- `src/copaw/kernel/query_execution_runtime.py`
  - Use the new execution context and state machine for heavy execution turns.
- `src/copaw/capabilities/execution.py`
  - Consume `CapabilityExecutionContext V2` and emit normalized outcomes.
- `src/copaw/kernel/tool_bridge.py`
  - Ensure file/shell execution goes through the unified contract.
- `src/copaw/kernel/runtime_outcome.py`
  - Extend outcome payloads if the new loop needs stable stage/result fields.
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - Keep `/runtime-center/chat/run` on the canonical path and surface turn-loop failures cleanly.
- `src/copaw/app/runtime_center/state_query.py`
  - Surface last result/evidence for the new path if existing query output is insufficient.
- `tests/kernel/test_turn_executor.py`
  - Add wiring tests for the new turn loop.
- `tests/kernel/test_query_execution_runtime.py`
  - Add runtime-path tests for the new execution context/state machine.
- `tests/app/test_capabilities_execution.py`
  - Lock file/shell execution against the new unified contract.
- `tests/app/test_operator_runtime_e2e.py`
  - Cover `chat/run -> file/shell -> evidence`.
- `tests/app/test_runtime_query_services.py`
  - Verify Runtime Center sees last result/evidence from the new path.
- `TASK_STATUS.md`
  - Record the new canonical path once implementation is complete.
- `API_TRANSITION_MAP.md`
  - Record the execution-path change if the runtime front-door contract changes.

## Task 1: Add Failing Tests for `CapabilityExecutionContext V2`

**Files:**
- Create: `tests/capabilities/test_execution_context.py`
- Test: `tests/capabilities/test_execution_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.capabilities.execution_context import CapabilityExecutionContext


def test_execution_context_carries_governance_environment_and_evidence_refs():
    context = CapabilityExecutionContext(
        task_id="task-1",
        goal_id="goal-1",
        owner_agent_id="execution-core",
        capability_id="tool:read_file",
        risk_level="guarded",
        environment_ref="session:console:test",
        work_context_id="wc-1",
    )
    assert context.task_id == "task-1"
    assert context.environment_ref == "session:console:test"
    assert context.risk_level == "guarded"


def test_execution_context_read_only_flag_is_derived_from_capability_kind():
    context = CapabilityExecutionContext(
        task_id="task-1",
        goal_id="goal-1",
        owner_agent_id="execution-core",
        capability_id="tool:read_file",
        capability_kind="local-tool",
        action_mode="read",
    )
    assert context.is_read_only is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `CapabilityExecutionContext`.

- [ ] **Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CapabilityExecutionContext:
    task_id: str
    goal_id: str | None = None
    owner_agent_id: str | None = None
    capability_id: str | None = None
    capability_kind: str | None = None
    risk_level: str = "auto"
    environment_ref: str | None = None
    work_context_id: str | None = None
    action_mode: str | None = None

    @property
    def is_read_only(self) -> bool:
        return self.action_mode == "read"
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/capabilities/test_execution_context.py src/copaw/capabilities/execution_context.py
git commit -m "test: add execution context contract"
```

## Task 2: Add Failing Tests for the Formal Execution State Machine

**Files:**
- Create: `tests/kernel/test_task_state_machine.py`
- Test: `tests/kernel/test_task_state_machine.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.kernel.task_state_machine import transition_execution_state


def test_transition_execution_state_allows_created_to_executing():
    next_state = transition_execution_state("created", "executing")
    assert next_state == "executing"


def test_transition_execution_state_rejects_executing_to_created():
    try:
        transition_execution_state("executing", "created")
    except ValueError as exc:
        assert "illegal transition" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/kernel/test_task_state_machine.py -v
```

Expected: FAIL with missing module/function.

- [ ] **Step 3: Write the minimal implementation**

```python
_ALLOWED_TRANSITIONS = {
    "created": {"queued", "executing", "cancelled"},
    "queued": {"executing", "blocked", "cancelled"},
    "executing": {"completed", "failed", "blocked", "waiting-confirm"},
    "waiting-confirm": {"executing", "cancelled"},
    "blocked": {"queued", "executing", "cancelled", "failed"},
}


def transition_execution_state(current: str, target: str) -> str:
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"illegal transition: {current} -> {target}")
    return target
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/kernel/test_task_state_machine.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/kernel/test_task_state_machine.py src/copaw/kernel/task_state_machine.py
git commit -m "test: add execution state machine contract"
```

## Task 3: Add Failing Tests for the Canonical Turn Loop

**Files:**
- Create: `tests/kernel/test_turn_loop.py`
- Test: `tests/kernel/test_turn_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.kernel.turn_loop import run_turn_loop


def test_turn_loop_runs_stages_in_canonical_order():
    calls = []

    def stage(name):
        def _inner(payload):
            calls.append(name)
            return payload
        return _inner

    run_turn_loop(
        payload={"task_id": "task-1"},
        intake_stage=stage("intake"),
        intent_stage=stage("intent"),
        bind_stage=stage("bind"),
        governance_stage=stage("governance"),
        execute_stage=stage("execute"),
        writeback_stage=stage("writeback"),
        evidence_stage=stage("evidence"),
        outcome_stage=stage("outcome"),
    )

    assert calls == [
        "intake",
        "intent",
        "bind",
        "governance",
        "execute",
        "writeback",
        "evidence",
        "outcome",
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/kernel/test_turn_loop.py -v
```

Expected: FAIL with missing module/function.

- [ ] **Step 3: Write the minimal implementation**

```python
def run_turn_loop(
    *,
    payload,
    intake_stage,
    intent_stage,
    bind_stage,
    governance_stage,
    execute_stage,
    writeback_stage,
    evidence_stage,
    outcome_stage,
):
    current = intake_stage(payload)
    current = intent_stage(current)
    current = bind_stage(current)
    current = governance_stage(current)
    current = execute_stage(current)
    current = writeback_stage(current)
    current = evidence_stage(current)
    return outcome_stage(current)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/kernel/test_turn_loop.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/kernel/test_turn_loop.py src/copaw/kernel/turn_loop.py
git commit -m "test: add canonical turn loop skeleton"
```

## Task 4: Wire `KernelTurnExecutor` and `MainBrainOrchestrator` Through the New Turn Loop

**Files:**
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Add the failing wiring tests**

```python
def test_turn_executor_uses_turn_loop_for_orchestrated_execution(monkeypatch):
    calls = []

    async def fake_turn_loop(**kwargs):
        calls.append(kwargs["stage_label"])
        return {"status": "completed"}

    monkeypatch.setattr("copaw.kernel.turn_executor.run_turn_loop_async", fake_turn_loop)
    ...
    assert calls == ["orchestrated-execution"]


def test_query_execution_runtime_builds_execution_context_before_running_tools():
    ...
    assert runtime_payload["execution_context"].task_id == kernel_task.id
```

- [ ] **Step 2: Run the target tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_turn_executor.py -k turn_loop -v
python -m pytest tests/kernel/test_query_execution_runtime.py -k execution_context -v
```

Expected: FAIL because the new wiring does not exist yet.

- [ ] **Step 3: Implement the minimal wiring**

```python
# turn_executor.py
result = await run_turn_loop_async(
    stage_label="orchestrated-execution",
    payload=runtime_payload,
    ...
)

# query_execution_runtime.py
context = CapabilityExecutionContext(
    task_id=kernel_task.id,
    goal_id=kernel_task.goal_id,
    owner_agent_id=kernel_task.owner_agent_id,
    capability_id=kernel_task.capability_ref,
    environment_ref=kernel_task.environment_ref,
)
```

- [ ] **Step 4: Run the target tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_turn_executor.py -k turn_loop -v
python -m pytest tests/kernel/test_query_execution_runtime.py -k execution_context -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/kernel/main_brain_orchestrator.py src/copaw/kernel/turn_executor.py src/copaw/kernel/query_execution_runtime.py src/copaw/kernel/runtime_outcome.py tests/kernel/test_turn_executor.py tests/kernel/test_query_execution_runtime.py
git commit -m "feat: route execution turns through canonical turn loop"
```

## Task 5: Put File and Shell Capability Calls Behind the Unified Execution Contract

**Files:**
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/kernel/tool_bridge.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/agents/test_file_tool_evidence.py`
- Test: `tests/agents/test_shell_tool_evidence.py`

- [ ] **Step 1: Add the failing tests**

```python
def test_capability_execution_uses_context_for_file_tool():
    ...
    assert result["capability_id"] == "tool:read_file"
    assert result["environment_ref"] == "session:console:test"


def test_capability_execution_writes_evidence_for_shell_tool():
    ...
    records = evidence_ledger.list_by_task(task.id)
    assert records[-1].capability_ref == "tool:execute_shell_command"
    assert records[-1].status == "succeeded"
```

- [ ] **Step 2: Run the target tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "file_tool or shell_tool" -v
python -m pytest tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py -v
```

Expected: FAIL because file/shell execution is not fully normalized by the new contract.

- [ ] **Step 3: Implement the minimal execution-orchestrator wiring**

```python
# execution.py
context = context or CapabilityExecutionContext.from_task(task, mount)
response = await orchestrate_capability_call(context=context, executor=executor, payload=payload)

# tool_bridge.py
return await capability_service.execute_task(task)
```

- [ ] **Step 4: Run the target tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "file_tool or shell_tool" -v
python -m pytest tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/capabilities/execution.py src/copaw/kernel/tool_bridge.py src/copaw/kernel/query_execution_tools.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py
git commit -m "feat: normalize file and shell execution contract"
```

## Task 6: Prove the Canonical Path Through `/runtime-center/chat/run`

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/app/test_operator_runtime_e2e.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`

- [ ] **Step 1: Add the failing API tests**

```python
def test_chat_run_executes_file_tool_through_canonical_turn_loop(client, app):
    response = client.post(
        "/api/runtime-center/chat/run",
        json={"message": "read README.md", "interaction_mode": "auto"},
    )
    assert response.status_code == 200
    assert response.json()["runtime"]["path"] == "canonical-turn-loop"


def test_chat_run_returns_stage_aware_failure_payload_when_execution_breaks(client, app):
    ...
    assert response.json()["runtime"]["failed_stage"] == "execute"
```

- [ ] **Step 2: Run the target tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_operator_runtime_e2e.py -k canonical_turn_loop -v
python -m pytest tests/app/test_runtime_human_assist_tasks_api.py -k failed_stage -v
```

Expected: FAIL because the route is not yet exposing the canonical path or stage-aware failures.

- [ ] **Step 3: Implement the minimal route integration**

```python
runtime_meta = {
    "path": "canonical-turn-loop",
    "failed_stage": result.failed_stage,
}
```

- [ ] **Step 4: Run the target tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_operator_runtime_e2e.py -k canonical_turn_loop -v
python -m pytest tests/app/test_runtime_human_assist_tasks_api.py -k failed_stage -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/routers/runtime_center_routes_core.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_human_assist_tasks_api.py
git commit -m "feat: expose canonical turn loop on chat run route"
```

## Task 7: Make Runtime Center Read Back the Last Result and Evidence

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/evidence_query.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Add the failing read-surface tests**

```python
def test_runtime_query_services_surface_last_execution_result_and_evidence(tmp_path):
    ...
    overview = await service.get_overview(app_state)
    assert any(card.kind == "evidence" for card in overview.cards)


def test_runtime_center_api_includes_last_evidence_id_for_runtime_task(client, app):
    ...
    assert payload["runtime"]["last_evidence_id"] == evidence_id
```

- [ ] **Step 2: Run the target tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_query_services.py -k last_execution_result -v
python -m pytest tests/app/test_runtime_center_api.py -k last_evidence_id -v
```

Expected: FAIL because the new path is not yet fully projected to the read surfaces.

- [ ] **Step 3: Implement the minimal projection changes**

```python
runtime_payload["last_result_summary"] = task_runtime.last_result_summary
runtime_payload["last_evidence_id"] = task_runtime.last_evidence_id
```

- [ ] **Step 4: Run the target tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_query_services.py -k last_execution_result -v
python -m pytest tests/app/test_runtime_center_api.py -k last_evidence_id -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/evidence_query.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py
git commit -m "feat: surface canonical execution evidence in runtime center"
```

## Task 8: Run the P0 Regression Set and Update Architecture Docs

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/superpowers/specs/2026-04-01-claude-code-runtime-donor-adoption-design.md`

- [ ] **Step 1: Run the P0 regression suite**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py tests/kernel/test_task_state_machine.py tests/kernel/test_turn_loop.py tests/kernel/test_turn_executor.py tests/kernel/test_query_execution_runtime.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -v
```

Expected: PASS

- [ ] **Step 2: Update the live status docs**

```markdown
- `P0` canonical run path now flows through `kernel.turn_loop`
- file/shell execution now uses `CapabilityExecutionContext V2`
- Runtime Center now surfaces the last result/evidence from the canonical path
```

- [ ] **Step 3: Commit**

```powershell
git add TASK_STATUS.md API_TRANSITION_MAP.md docs/superpowers/specs/2026-04-01-claude-code-runtime-donor-adoption-design.md
git commit -m "docs: record p0 canonical runtime adoption"
```

## Done Definition

P0 is complete only when all of the following are true:

- `POST /api/runtime-center/chat/run` reaches a single canonical execution path.
- file and shell capabilities run through the unified execution contract.
- execution-state changes go through the formal state machine.
- each successful or failed execution writes formal evidence.
- Runtime Center can read back the last result and evidence for the task/runtime.
- the regression suite in Task 8 is green.

## Follow-Up Planning Gate

Do not start `P1` from this branch until this plan is green and reviewed.

When this plan is complete, write separate follow-up plans for:

1. MCP runtime hardening
2. subagent/worker donor adoption
3. skill metadata + package binding
