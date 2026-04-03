# Execution Harness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining worthwhile `cc`-inspired execution-harness hardening work without introducing a parallel runtime truth.

**Architecture:** Keep all new behavior on the canonical `EnvironmentMount / SessionMount / EvidenceRecord / work_context_id` chain. Land host-side abort producers, stronger cleanup/restore discipline, thicker lease/attach recovery, and broader live acceptance coverage by extending existing `environment_service`, `surface_control_service`, `browser_attach_runtime`, and live smoke tests instead of creating a new subsystem.

**Tech Stack:** Python, pytest, existing CoPaw environment/kernel services, Windows desktop adapter, live routine smoke harness.

---

### Task 1: Host Abort Producer

**Files:**
- Modify: `src/copaw/adapters/desktop/windows_host.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Test: `tests/adapters/test_windows_host.py`
- Test: `tests/environments/test_environment_registry.py`

- [ ] **Step 1: Write the failing tests**
  Add unit coverage proving the desktop host can emit a canonical abort signal and integration coverage proving the environment service writes that signal onto the shared operator-abort truth for a runtime session.

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/adapters/test_windows_host.py -q
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_environment_registry.py -q
  ```
  Expected: new abort-producer tests fail because the producer path does not exist yet.

- [ ] **Step 3: Write minimal implementation**
  Add a host-side abort producer path that can publish an abort request through `EnvironmentService.set_shared_operator_abort_state(...)` without creating a new truth source or UI-only signal.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run the same targeted pytest commands and confirm the new producer tests are green.

### Task 2: Cleanup And Restore Discipline

**Files:**
- Modify: `src/copaw/environments/surface_control_service.py`
- Modify: `src/copaw/adapters/desktop/windows_host.py`
- Test: `tests/environments/test_cooperative_windows_apps.py`
- Test: `tests/environments/test_cooperative_browser_companion.py`
- Test: `tests/environments/test_cooperative_document_bridge.py`
- Test: `tests/adapters/test_windows_host.py`

- [ ] **Step 1: Write the failing tests**
  Add focused tests for interruption/failure cleanup, foreground restore behavior, and clipboard restore verification so browser/document/windows actions prove they cleanly unwind after blocked or failed execution.

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_cooperative_windows_apps.py -q
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_cooperative_browser_companion.py -q
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_cooperative_document_bridge.py -q
  .\.venv\Scripts\python.exe -m pytest tests/adapters/test_windows_host.py -q
  ```
  Expected: new cleanup/restore assertions fail before implementation.

- [ ] **Step 3: Write minimal implementation**
  Extend the live execution path so pre/post action cleanup and restore are explicit, deterministic, and evidenced through the existing canonical surfaces and guardrail truth.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run the targeted pytest commands and confirm the new cleanup/restore tests are green.

### Task 3: Lease And Attach Hardening

**Files:**
- Modify: `src/copaw/environments/cooperative/browser_attach_runtime.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/service.py`
- Test: `tests/environments/test_cooperative_browser_attach_runtime.py`
- Test: `tests/environments/test_environment_registry.py`

- [ ] **Step 1: Write the failing tests**
  Add tests for stale attach cleanup, reconnect cleanup, orphan/stale lease repair, and deterministic clearing of attach continuity after stop/release/archive flows.

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_cooperative_browser_attach_runtime.py -q
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_environment_registry.py -q
  ```
  Expected: the new stale/orphan hardening tests fail because the stricter cleanup discipline does not exist yet.

- [ ] **Step 3: Write minimal implementation**
  Harden canonical attach and lease cleanup without adding a second continuity store. Keep browser attach truth patch-safe and deterministic across reconnect, stop, archive, and orphan recovery flows.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run the targeted pytest commands and confirm the new hardening tests are green.

### Task 4: Live Acceptance Harness Expansion

**Files:**
- Modify: `tests/routines/test_live_routine_smoke.py`
- Modify: `tests/routines/test_routine_service.py`

- [ ] **Step 1: Write the failing tests**
  Add smoke coverage for abort, reconnect, cleanup, and mixed browser/desktop contention paths using the existing live routine harness, guarded behind the existing environment flag.

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/routines/test_routine_service.py -q
  .\.venv\Scripts\python.exe -m pytest tests/routines/test_live_routine_smoke.py -q
  ```
  Expected: the new smoke specs fail or skip until the harness paths are implemented and wired.

- [ ] **Step 3: Write minimal implementation**
  Extend the current smoke harness and its helper assertions so live acceptance covers the newly hardened execution behaviors instead of only basic happy paths.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run the targeted pytest commands and confirm the non-flagged coverage passes; flagged live smoke should remain gated by `COPAW_RUN_V6_LIVE_ROUTINE_SMOKE`.

### Final Verification

**Files:**
- Verify only; no new files

- [ ] **Step 1: Run targeted environment/kernel/routine regressions**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/adapters/test_windows_host.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/routines/test_routine_service.py tests/routines/test_live_routine_smoke.py -q
  ```

- [ ] **Step 2: Run adjacent regressions that prove the canonical runtime chain still holds**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/runtime_center_api_parts/detail_environment.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_main_brain_commit_service.py -q
  ```

- [ ] **Step 3: Commit only this task's files**
  Do not add unrelated dirty files or `cc/`.
