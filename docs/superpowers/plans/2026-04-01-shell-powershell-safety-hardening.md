# Shell And PowerShell Safety Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden CoPaw's shell execution path so obviously destructive or policy-violating shell / PowerShell commands are blocked before execution, classified as `blocked` instead of generic failure, and still stay on the current unified execution + evidence chain.

**Architecture:** Keep `tool:execute_shell_command` on the existing `CapabilityExecutionFacade -> execute_shell_command -> KernelToolBridge -> EvidenceLedger` path. Introduce one pure shell-safety policy module in front of `subprocess` execution, have `shell.py` emit a structured blocked result when policy denies execution, and align `execution.py`, `runtime_outcome.py`, and `tool_bridge.py` so blocked shell outcomes are first-class runtime outcomes rather than free-form stderr strings. This plan is intentionally separate from the `/chat` terminal-state plan and does not redesign main-brain ingress.

**Tech Stack:** Python 3.11, existing CoPaw shell tool stack, pytest, SQLite-backed evidence/runtime contract tests.

---

## Scope Guard

This plan covers only lower shell safety and its unified execution contract:

- `tool:execute_shell_command`
- pre-execution shell / PowerShell safety validation
- blocked outcome taxonomy
- evidence / task summary coupling for blocked shell calls
- targeted tests for safety and evidence

This plan does **not** cover:

- `/runtime-center/chat/run` redesign
- Runtime Center UI redesign
- browser / file tool redesign
- full Claude Code style shell parser parity
- unrelated actor / worker / MCP refactors

## Root Gap Summary

Current shell execution is still a raw command runner:

- [shell.py](D:/word/copaw/src/copaw/agents/tools/shell.py)
  - executes arbitrary command strings with `shell=True`
  - classifies only `success / timeout / error`
  - has no pre-execution destructive-command gate
- [execution.py](D:/word/copaw/src/copaw/capabilities/execution.py)
  - can already carry `blocked` as a runtime outcome, but shell never emits that shape
- [runtime_outcome.py](D:/word/copaw/src/copaw/kernel/runtime_outcome.py)
  - already understands `blocked`, but current shell path does not use it
- [tool_bridge.py](D:/word/copaw/src/copaw/kernel/tool_bridge.py)
  - records shell evidence, but today a policy-denied shell command would only look like a generic error

That leaves a real gap relative to the validated `cc` borrowing point:

- no parse-aware or policy-aware shell guard
- no first-class `blocked` shell outcome
- no evidence record that clearly says "denied before execution"

## File Map

### New files

- `src/copaw/agents/tools/shell_safety.py`
  - Pure validation module for shell / PowerShell command safety decisions.
- `tests/agents/test_shell_tool_safety.py`
  - Unit tests for the new safety policy.

### Existing files to modify

- `src/copaw/agents/tools/shell.py`
  - Call the safety validator before execution and emit blocked results without spawning a subprocess.
- `src/copaw/capabilities/execution.py`
  - Ensure blocked shell outputs are normalized to `error_kind="blocked"`.
- `src/copaw/kernel/runtime_outcome.py`
  - Tighten blocked classification markers for policy-denied shell output.
- `src/copaw/kernel/tool_bridge.py`
  - Preserve blocked shell outcomes in task summaries and evidence metadata.
- `tests/agents/test_shell_tool_evidence.py`
  - Lock blocked evidence payload semantics.
- `tests/app/test_capabilities_execution.py`
  - Lock unified execution result semantics for blocked shell commands.
- `tests/test_truncate.py`
  - Preserve current non-blocked shell behavior while adding blocked behavior checks.
- `TASK_STATUS.md`
  - Record the hardening after tests are green.

## Safety Contract To Introduce

The first slice should stay pragmatic and explicit:

- allow known-safe read / inspect commands to continue
- block obviously destructive commands before execution
- block repository-damaging git commands in normal runtime mode
- classify policy-denied calls as:
  - shell payload status: `blocked`
  - capability result `error_kind`: `blocked`
  - evidence status: blocked-path failure, with clear denial reason

The validator should produce a structured decision:

```python
@dataclass(frozen=True, slots=True)
class ShellSafetyDecision:
    allowed: bool
    reason: str | None = None
    rule_id: str | None = None
```

First-slice deny rules should at minimum cover:

- recursive delete patterns like `Remove-Item -Recurse`, `del /s`, `rmdir /s`
- destructive git commands like `git reset --hard`, `git checkout --`, `git clean -fd`
- direct `.git`, `hooks`, `refs` destructive path writes/deletes

This is not full shell parsing parity with `cc`; it is the first formal CoPaw safety gate.

### Task 1: Lock The Shell Safety Gap In Failing Tests

**Files:**
- Create: `tests/agents/test_shell_tool_safety.py`
- Modify: `tests/agents/test_shell_tool_evidence.py`
- Modify: `tests/app/test_capabilities_execution.py`
- Modify: `tests/test_truncate.py`

- [ ] **Step 1: Write the failing pure-policy tests**

```python
from copaw.agents.tools.shell_safety import validate_shell_command


def test_validate_shell_command_allows_read_only_git_status() -> None:
    decision = validate_shell_command("git status")
    assert decision.allowed is True


def test_validate_shell_command_blocks_git_reset_hard() -> None:
    decision = validate_shell_command("git reset --hard HEAD")
    assert decision.allowed is False
    assert decision.rule_id == "destructive-git"


def test_validate_shell_command_blocks_recursive_powershell_delete() -> None:
    decision = validate_shell_command('Remove-Item -LiteralPath "." -Recurse -Force')
    assert decision.allowed is False
    assert decision.rule_id == "recursive-delete"
```

- [ ] **Step 2: Write the failing shell evidence test**

```python
def test_execute_shell_command_emits_blocked_payload_without_running_subprocess(...):
    ...
    assert payloads[0]["status"] == "blocked"
    assert payloads[0]["rule_id"] == "destructive-git"
```

- [ ] **Step 3: Write the failing capability contract test**

```python
def test_execution_failure_contract_classifies_blocked_shell_separately(...):
    ...
    assert result["success"] is False
    assert result["error_kind"] == "blocked"
```

- [ ] **Step 4: Write the failing behavioral shell test**

```python
def test_shell_blocked_command_returns_policy_message(shell_test_dir):
    ...
    assert "blocked" in text.lower()
    assert "git reset --hard" in text.lower()
```

- [ ] **Step 5: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/agents/test_shell_tool_safety.py tests/agents/test_shell_tool_evidence.py tests/app/test_capabilities_execution.py tests/test_truncate.py -k "shell and (blocked or safety)" -q
```

Expected: FAIL because there is no dedicated shell safety validator and blocked shell outcomes are not yet formalized.

### Task 2: Introduce A Pure Shell Safety Policy Module

**Files:**
- Create: `src/copaw/agents/tools/shell_safety.py`
- Test: `tests/agents/test_shell_tool_safety.py`

- [ ] **Step 1: Write the minimal policy object**

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShellSafetyDecision:
    allowed: bool
    reason: str | None = None
    rule_id: str | None = None
```

- [ ] **Step 2: Implement the first-slice validator**

```python
def validate_shell_command(command: str) -> ShellSafetyDecision:
    normalized = (command or "").strip().casefold()
    if "git reset --hard" in normalized or "git checkout --" in normalized or "git clean -fd" in normalized:
        return ShellSafetyDecision(False, "Blocked destructive git command.", "destructive-git")
    if "remove-item" in normalized and "-recurse" in normalized:
        return ShellSafetyDecision(False, "Blocked recursive delete command.", "recursive-delete")
    if normalized.startswith("del ") and "/s" in normalized:
        return ShellSafetyDecision(False, "Blocked recursive delete command.", "recursive-delete")
    return ShellSafetyDecision(True)
```

- [ ] **Step 3: Keep the validator pure**

No subprocess calls, no filesystem mutation, no evidence writes. This file should only decide `allowed / denied / why`.

- [ ] **Step 4: Run pure-policy tests**

Run:

```powershell
python -m pytest tests/agents/test_shell_tool_safety.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/agents/tools/shell_safety.py tests/agents/test_shell_tool_safety.py
git commit -m "feat: add shell safety policy validator"
```

### Task 3: Wire `shell.py` To Block Before Execution And Emit Structured Evidence

**Files:**
- Modify: `src/copaw/agents/tools/shell.py`
- Modify: `tests/agents/test_shell_tool_evidence.py`
- Modify: `tests/test_truncate.py`

- [ ] **Step 1: Validate before starting a subprocess**

At the top of `execute_shell_command(...)`:

```python
decision = validate_shell_command(cmd)
if not decision.allowed:
    ...
```

- [ ] **Step 2: Emit a blocked shell result without executing**

The blocked path should:

- skip subprocess execution entirely
- emit shell evidence with:
  - `status="blocked"`
  - `rule_id`
  - denial reason in `stderr` or dedicated payload field
- return a user-facing ToolResponse that clearly says the command was blocked by policy

- [ ] **Step 3: Preserve existing success / timeout / error behavior**

Do not regress:

- truncation behavior
- timeout handling
- evidence sink behavior for successful and timed-out commands

- [ ] **Step 4: Run shell tool tests**

Run:

```powershell
python -m pytest tests/agents/test_shell_tool_evidence.py tests/test_truncate.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/agents/tools/shell.py tests/agents/test_shell_tool_evidence.py tests/test_truncate.py
git commit -m "fix: block unsafe shell commands before execution"
```

### Task 4: Align Unified Execution And Tool-Bridge Outcome Semantics

**Files:**
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/kernel/tool_bridge.py`
- Modify: `tests/app/test_capabilities_execution.py`

- [ ] **Step 1: Make capability execution classify blocked shell outputs correctly**

Blocked shell responses should produce:

- `success=False`
- `error_kind="blocked"`
- `summary` equal to the policy denial summary

- [ ] **Step 2: Tighten runtime outcome classification**

Add or normalize blocked markers so policy-denied shell output is not treated as generic `failed`.

- [ ] **Step 3: Preserve blocked shell evidence in tool bridge**

`KernelToolBridge.record_shell_event(...)` should keep blocked context visible in:

- evidence metadata
- task summary
- task last error summary

- [ ] **Step 4: Run execution contract tests**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "shell and (blocked or timeout or unified_contract)" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/capabilities/execution.py src/copaw/kernel/runtime_outcome.py src/copaw/kernel/tool_bridge.py tests/app/test_capabilities_execution.py
git commit -m "fix: classify blocked shell execution as first-class runtime outcome"
```

### Task 5: Run The Focused Shell Hardening Regression Gate

**Files:**
- Verify: `src/copaw/agents/tools/shell_safety.py`
- Verify: `src/copaw/agents/tools/shell.py`
- Verify: `src/copaw/capabilities/execution.py`
- Verify: `src/copaw/kernel/runtime_outcome.py`
- Verify: `src/copaw/kernel/tool_bridge.py`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the focused shell safety regression set**

Run:

```powershell
python -m pytest tests/agents/test_shell_tool_safety.py tests/agents/test_shell_tool_evidence.py tests/app/test_capabilities_execution.py tests/test_truncate.py -q
```

Expected: PASS

- [ ] **Step 2: Review diff scope**

Confirm the implementation only changes:

- shell safety policy
- blocked shell outcome classification
- evidence/task coupling

and does not redesign unrelated runtime ingress.

- [ ] **Step 3: Update task status**

Record in `TASK_STATUS.md` that shell execution now has a first-slice policy blocker and first-class blocked outcome semantics.

- [ ] **Step 4: Re-run the focused regression after docs update**

Run:

```powershell
python -m pytest tests/agents/test_shell_tool_safety.py tests/agents/test_shell_tool_evidence.py tests/app/test_capabilities_execution.py tests/test_truncate.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add TASK_STATUS.md docs/superpowers/plans/2026-04-01-shell-powershell-safety-hardening.md
git commit -m "docs: add shell and powershell safety hardening plan"
```

## Next Constraint

After this first slice is green, a later follow-up plan may deepen shell safety with:

- stronger PowerShell token parsing
- path-aware git internal path protection
- read-only deception checks
- permission / governance integration instead of a local preflight-only blocker

That deeper slice should only start after this first blocked-outcome contract is stable.
