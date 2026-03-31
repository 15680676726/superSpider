# Claude Runtime Contract Hardening P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten CoPaw's lower execution contract without breaking the current live main chain by introducing an internal execution context, unifying file/shell execution behavior, strengthening evidence/result coupling, and tightening request normalization so complete tasks are more likely to run through.

**Architecture:** This plan treats the current main chain as alive. `P0` starts under `src/copaw/capabilities/execution.py`, not at the main-brain front door. `/runtime-center/chat/run` stays as the unified ingress and current SSE relay over `turn_executor.stream_request()`. `task_state_machine.py` and `turn_loop.py` are not `P0` requirements; they should only be extracted later if green implementation work proves they remove real complexity. `P0` standardizes and tightens the contracts that already exist in `CapabilityExecutionFacade`, `KernelToolBridge`, and `query_execution_runtime._resolve_execution_task_context(...)`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, Pytest, existing CoPaw kernel/evidence/runtime services.

---

## Scope Guard

This plan covers only:

- `src/copaw/capabilities/execution.py`
- `src/copaw/capabilities/execution_context.py`
- `src/copaw/kernel/tool_bridge.py`
- file/shell execution through one hardened front-door
- evidence coupling for file/shell execution
- execution result contract hardening
- request normalization hardening

This plan does **not** cover:

- `MainBrainOrchestrator` redesign
- `/runtime-center/chat/run` redesign
- Runtime Center read-surface redesign
- preemptive `task_state_machine.py` extraction
- preemptive `turn_loop.py` extraction
- MCP runtime hardening
- worker/subagent shell hardening
- skill/package formalization

## Ingress Constraint

`/runtime-center/chat/run` stays in place during `P0`.

In this plan it is only:

- unified ingress
- request relay
- live route used to validate the hardened lower contract

It is not:

- a standalone chat system
- a second semantic center
- a redesign target

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
- `tests/capabilities/test_execution_context.py`
  - Unit tests for execution context shape and helpers.

### Existing files to modify

- `src/copaw/capabilities/execution.py`
  - First landing point for the typed execution context and existing unified file/shell contract.
- `src/copaw/kernel/tool_bridge.py`
  - Align tool-bridge-mediated file/shell evidence with the hardened execution contract.
- `src/copaw/kernel/query_execution_runtime.py`
  - Tighten execution-side request normalization by clarifying the existing `_resolve_execution_task_context(...)` path.
- `src/copaw/kernel/runtime_outcome.py`
  - Normalize the lower execution result envelope only if existing execution return fields need a shared helper.
- `tests/app/test_capabilities_execution.py`
  - Lock file/shell execution to the unified contract.
- `tests/agents/test_file_tool_evidence.py`
  - Lock file-tool evidence coupling.
- `tests/agents/test_shell_tool_evidence.py`
  - Lock shell-tool evidence coupling.
- `tests/kernel/test_query_execution_runtime.py`
  - Verify normalized runtime payloads.
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

## Task 2: Tighten the File/Shell Front-Door and Evidence Coupling

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

## Task 3: Tighten Evidence and Execution Result Contract

**Files:**
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_execution_result_contract_exposes_normalized_success_payload():
    ...
    assert result["success"] is True
    assert result["capability_id"] == "tool:read_file"
    assert "summary" in result


def test_chat_run_e2e_returns_runtime_result_without_route_redesign():
    ...
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k normalized_success_payload -v
python -m pytest tests/app/test_operator_runtime_e2e.py -k runtime_result -v
```

Expected: FAIL because the lower result contract is not yet explicit enough or is inconsistent across capability paths.

- [ ] **Step 3: Write minimal implementation**

```python
# execution.py
return {
    "success": success,
    "capability_id": capability_id,
    "environment_ref": task.environment_ref,
    "summary": summary,
    "evidence_id": evidence_id,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k normalized_success_payload -v
python -m pytest tests/app/test_operator_runtime_e2e.py -k runtime_result -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/capabilities/execution.py src/copaw/kernel/runtime_outcome.py tests/app/test_capabilities_execution.py tests/app/test_operator_runtime_e2e.py
git commit -m "feat: normalize execution result contract"
```

## Task 4: Tighten Request Normalization Without Rewriting the Front Door

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_execution_runtime_normalizes_file_shell_request_payloads():
    ...
    assert normalized["execution_context"]["capability_ref"] in {
        "tool:read_file",
        "tool:execute_shell_command",
    }


def test_live_route_still_runs_through_existing_sse_main_chain():
    ...
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_query_execution_runtime.py -k normalize -v
python -m pytest tests/app/test_operator_runtime_e2e.py -k existing_main_chain -v
```

Expected: FAIL because request normalization is still too implicit or inconsistent with the current execution-context merge path.

- [ ] **Step 3: Write minimal implementation**

```python
# query_execution_runtime.py
execution_context = self._resolve_execution_task_context(
    request=request,
    agent_id=owner_agent_id,
    kernel_task_id=kernel_task_id,
    conversation_thread_id=session_id,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_query_execution_runtime.py -k normalize -v
python -m pytest tests/app/test_operator_runtime_e2e.py -k sse_main_chain -v
```

Expected: PASS while the current live route still works.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/kernel/query_execution_runtime.py src/copaw/kernel/turn_executor.py tests/kernel/test_query_execution_runtime.py tests/app/test_operator_runtime_e2e.py
git commit -m "feat: tighten request normalization for execution runtime"
```

## Task 5: Run Regression and Update Live Docs

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/capabilities/test_execution_context.py tests/kernel/test_query_execution_runtime.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py tests/app/test_operator_runtime_e2e.py -v
```

Expected: PASS

- [ ] **Step 2: Update the live docs**

```markdown
- `P0` now hardens the lower execution contract instead of rebuilding the main chain.
- file/shell execution is standardized around the existing capability front-door.
- evidence/result shaping and execution-context normalization are tighter without changing the live vocabulary or route model.
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
- the existing execution result contract is more uniform
- the existing execution-context normalization path is more uniform
- the current live route still works
- the regression suite in Task 5 is green

## Follow-Up Planning Gate

Do not start `P1` from this branch until this plan is green.

Write separate follow-up plans for:

1. MCP runtime hardening
2. task interpretation and assignment hardening
3. worker/subagent shell hardening
4. skill/package formalization
5. conditional extraction of `task_state_machine.py` and/or `turn_loop.py` only if the green `P0` implementation proves they remove real complexity
