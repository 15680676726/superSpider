# Claude Runtime Contract Hardening P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten CoPaw's lower execution contract without breaking the current live main chain by introducing an internal execution context, a phase-aware state-machine wrapper over existing kernel vocabulary, a unified file/shell front-door with evidence coupling, and finally a thin turn loop attached to `KernelTurnExecutor`.

**Architecture:** This plan assumes the current main chain is alive and should not be rebuilt in `P0`. The work starts under `capabilities/execution.py`, not in the main-brain front door. `P0` is contract hardening: first normalize the lower execution contract, then add a thin `turn_loop.py` over existing components. `/runtime-center/chat/run` remains the unified ingress, not a second chat system. No `P0` step should invent a second execution vocabulary or rewrite `MainBrainOrchestrator` and `/runtime-center/chat/run`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, Pytest, existing CoPaw kernel/evidence/runtime services.

---

## Scope Guard

This plan covers only:

- `src/copaw/capabilities/execution.py`
- `src/copaw/capabilities/execution_context.py`
- `src/copaw/kernel/task_state_machine.py`
- file/shell execution through a unified front-door
- evidence coupling for file/shell execution
- a thin `src/copaw/kernel/turn_loop.py`
- minimal `src/copaw/kernel/turn_executor.py` integration

This plan does **not** cover:

- MCP runtime hardening
- subagent/worker hardening
- skill/package formalization
- sidecar memory
- `MainBrainOrchestrator` redesign
- router/front-door redesign
- Runtime Center read-surface redesign

## Ingress Constraint

`/runtime-center/chat/run` stays in place during `P0`.

In this plan it is treated only as:

- unified ingress
- request relay
- live route to validate that the hardened lower contract still completes

It is not treated as:

- a standalone chat system
- a second semantic center
- a redesign target in `P0`

## Execution Environment

Run this plan in a dedicated worktree.

Suggested commands:

```powershell
git worktree add .worktrees\claude-contract-p0 -b feat/claude-contract-p0
cd .worktrees\claude-contract-p0
pip install -e .
```

## File Map

### New files

- `src/copaw/capabilities/execution_context.py`
  - Internal standard execution context for one capability invocation.
- `src/copaw/kernel/task_state_machine.py`
  - Wrapper around existing `KernelTask.phase` and phase/status projection.
- `src/copaw/kernel/turn_loop.py`
  - Thin orchestration layer over existing components.
- `tests/capabilities/test_execution_context.py`
  - Unit tests for execution context shape and helpers.
- `tests/kernel/test_task_state_machine.py`
  - Unit tests for current phase transitions and projections.
- `tests/kernel/test_turn_loop.py`
  - Unit tests for thin turn-loop ordering and failure reporting.

### Existing files to modify

- `src/copaw/capabilities/execution.py`
  - First landing point for the new execution context and unified file/shell contract.
- `src/copaw/kernel/tool_bridge.py`
  - Route file/shell execution through the hardened execution contract.
- `src/copaw/kernel/persistence.py`
  - Export or safely reuse existing phase/status projection helpers if needed.
- `src/copaw/kernel/lifecycle.py`
  - Reuse existing legal phase progression where helpful; do not replace it.
- `src/copaw/kernel/turn_executor.py`
  - Attach the thin `turn_loop.py` with minimal intrusion.
- `tests/app/test_capabilities_execution.py`
  - Lock file/shell execution to the unified contract.
- `tests/agents/test_file_tool_evidence.py`
  - Lock file-tool evidence coupling.
- `tests/agents/test_shell_tool_evidence.py`
  - Lock shell-tool evidence coupling.
- `tests/kernel/test_kernel.py`
  - Keep current lifecycle behavior aligned with the new wrapper.
- `tests/kernel/test_turn_executor.py`
  - Verify thin turn-loop integration.
- `tests/app/test_operator_runtime_e2e.py`
  - Verify the live route still completes through the hardened path.
- `TASK_STATUS.md`
  - Record the hardened lower contract once green.
- `API_TRANSITION_MAP.md`
  - Record the execution-contract change if external expectations change.

## Task 1: Add Failing Tests for `CapabilityExecutionContext`

**Files:**
- Create: `tests/capabilities/test_execution_context.py`
- Test: `tests/capabilities/test_execution_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.capabilities.execution_context import CapabilityExecutionContext


def test_execution_context_keeps_existing_kernel_identity_fields():
    context = CapabilityExecutionContext(
        task_id="ktask:test",
        goal_id="goal:test",
        owner_agent_id="execution-core",
        capability_ref="tool:read_file",
        environment_ref="session:console:test",
        risk_level="guarded",
    )
    assert context.task_id == "ktask:test"
    assert context.capability_ref == "tool:read_file"
    assert context.environment_ref == "session:console:test"


def test_execution_context_marks_read_actions_as_read_only():
    context = CapabilityExecutionContext(
        task_id="ktask:test",
        capability_ref="tool:read_file",
        action_mode="read",
    )
    assert context.is_read_only is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py -v
```

Expected: FAIL with missing module or missing class.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CapabilityExecutionContext:
    task_id: str
    goal_id: str | None = None
    owner_agent_id: str | None = None
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str = "auto"
    action_mode: str | None = None

    @property
    def is_read_only(self) -> bool:
        return self.action_mode == "read"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/capabilities/test_execution_context.py src/copaw/capabilities/execution_context.py
git commit -m "test: add internal execution context contract"
```

## Task 2: Add Failing Tests for `task_state_machine` Using Existing Kernel Vocabulary

**Files:**
- Create: `tests/kernel/test_task_state_machine.py`
- Test: `tests/kernel/test_task_state_machine.py`
- Test: `tests/kernel/test_kernel.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.kernel.task_state_machine import (
    ensure_legal_phase_transition,
    project_runtime_status,
    project_task_status,
)


def test_phase_projection_reuses_existing_persistence_contract():
    assert project_task_status("executing") == "running"
    assert project_runtime_status("executing") == "active"


def test_illegal_transition_is_checked_against_existing_task_phase_contract():
    assert ensure_legal_phase_transition("pending", "risk-check") == "risk-check"
    try:
        ensure_legal_phase_transition("completed", "executing")
    except ValueError as exc:
        assert "illegal transition" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/kernel/test_task_state_machine.py -v
```

Expected: FAIL with missing module/function.

- [ ] **Step 3: Write minimal implementation**

```python
from .persistence import _runtime_status_for_phase, _task_status_for_phase

_ALLOWED_PHASE_TRANSITIONS = {
    "pending": {"risk-check", "cancelled"},
    "risk-check": {"executing", "waiting-confirm", "cancelled"},
    "waiting-confirm": {"executing", "cancelled"},
    "executing": {"completed", "failed", "cancelled"},
}


def ensure_legal_phase_transition(current: str, target: str) -> str:
    if target not in _ALLOWED_PHASE_TRANSITIONS.get(current, set()):
        raise ValueError(f"illegal transition: {current} -> {target}")
    return target


def project_task_status(phase: str) -> str:
    return _task_status_for_phase(phase)


def project_runtime_status(phase: str) -> str:
    return _runtime_status_for_phase(phase)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/kernel/test_task_state_machine.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/kernel/test_task_state_machine.py src/copaw/kernel/task_state_machine.py
git commit -m "test: wrap existing kernel phase contract"
```

## Task 3: Tighten the File/Shell Execution Front-Door and Evidence Coupling

**Files:**
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/kernel/tool_bridge.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/agents/test_file_tool_evidence.py`
- Test: `tests/agents/test_shell_tool_evidence.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_file_execution_builds_internal_execution_context():
    ...
    assert result["capability_id"] == "tool:read_file"
    assert result["environment_ref"] == "session:console:test"


def test_shell_execution_writes_evidence_via_unified_contract():
    ...
    records = evidence_ledger.list_by_task(task.id)
    assert records[-1].capability_ref == "tool:execute_shell_command"
    assert records[-1].status == "succeeded"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "file or shell" -v
python -m pytest tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py -v
```

Expected: FAIL because file/shell do not consistently flow through one internal contract.

- [ ] **Step 3: Write minimal implementation**

```python
# execution.py
context = CapabilityExecutionContext(
    task_id=task.id,
    goal_id=task.goal_id,
    owner_agent_id=task.owner_agent_id,
    capability_ref=task.capability_ref,
    environment_ref=task.environment_ref,
    risk_level=task.risk_level,
    action_mode="read" if task.capability_ref == "tool:read_file" else "write",
)

# tool_bridge.py
return await capability_service.execute_task(task)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "file or shell" -v
python -m pytest tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/capabilities/execution.py src/copaw/kernel/tool_bridge.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py
git commit -m "feat: harden file and shell execution contract"
```

## Task 4: Add a Thin `turn_loop.py` and Attach It Minimally to `KernelTurnExecutor`

**Files:**
- Create: `src/copaw/kernel/turn_loop.py`
- Create: `tests/kernel/test_turn_loop.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.kernel.turn_loop import run_turn_loop


def test_turn_loop_orders_existing_stages_without_redefining_them():
    calls = []

    def stage(name):
        def _inner(payload):
            calls.append(name)
            return payload
        return _inner

    run_turn_loop(
        payload={"task_id": "ktask:test"},
        stages=[
            stage("bind"),
            stage("governance"),
            stage("execute"),
            stage("evidence"),
        ],
    )

    assert calls == ["bind", "governance", "execute", "evidence"]
```

```python
def test_turn_executor_uses_thin_turn_loop_without_rewriting_main_brain(monkeypatch):
    ...
    assert result.success is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_turn_loop.py -v
python -m pytest tests/kernel/test_turn_executor.py -k turn_loop -v
```

Expected: FAIL because `turn_loop.py` does not exist and `KernelTurnExecutor` is not using it.

- [ ] **Step 3: Write minimal implementation**

```python
def run_turn_loop(*, payload, stages):
    current = payload
    for stage in stages:
        current = stage(current)
    return current
```

```python
# turn_executor.py
result = run_turn_loop(
    payload=runtime_payload,
    stages=[bind_stage, governance_stage, execute_stage, evidence_stage],
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_turn_loop.py -v
python -m pytest tests/kernel/test_turn_executor.py -k turn_loop -v
python -m pytest tests/app/test_operator_runtime_e2e.py -k "chat_run" -v
```

Expected: PASS while the existing live route still works.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/kernel/turn_loop.py src/copaw/kernel/turn_executor.py tests/kernel/test_turn_loop.py tests/kernel/test_turn_executor.py tests/app/test_operator_runtime_e2e.py
git commit -m "feat: add thin turn loop over existing execution path"
```

## Task 5: Run Regression and Update Live Docs

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py tests/kernel/test_task_state_machine.py tests/kernel/test_turn_loop.py tests/kernel/test_kernel.py tests/kernel/test_turn_executor.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py tests/app/test_operator_runtime_e2e.py -v
```

Expected: PASS

- [ ] **Step 2: Update the live docs**

```markdown
- `P0` now hardens the lower execution contract instead of rebuilding the main chain.
- file/shell execution now flows through a unified internal execution context.
- thin turn loop has been added without changing the live vocabulary.
```

- [ ] **Step 3: Commit**

```powershell
git add TASK_STATUS.md API_TRANSITION_MAP.md docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md
git commit -m "docs: record p0 runtime contract hardening"
```

## Done Definition

`P0` is complete only when all of the following are true:

- file/shell execution runs through one hardened front-door
- evidence is coupled to that front-door
- `KernelTask.phase` remains the canonical kernel vocabulary
- no second execution vocabulary is introduced
- the current live route still works
- the thin turn loop is attached with minimal intrusion
- the regression suite in Task 5 is green

## Follow-Up Planning Gate

Do not start `P1` from this branch until this plan is green.

Write separate follow-up plans for:

1. MCP runtime hardening
2. task interpretation and assignment hardening
3. worker/subagent shell hardening
4. skill/package formalization
