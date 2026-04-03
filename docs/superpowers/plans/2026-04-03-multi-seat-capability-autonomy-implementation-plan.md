# Multi-Seat Capability Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the backend-only multi-seat capability autonomy chain so CoPaw can automatically reuse, mount, install, trial, replace, and roll back `skill / MCP` capability surfaces without introducing a second truth source.

**Architecture:** Keep all capability governance on the canonical `CapabilityMount / IndustryRoleBlueprint / AgentRuntimeRecord / EnvironmentMount / SessionMount` chain. Extend existing role capability assignment, seat runtime metadata, query runtime resolution, MCP scope overlays, and remote-skill trial/rollout contracts instead of creating a parallel capability manager or recommendation truth.

**Tech Stack:** Python, Pydantic, existing CoPaw industry/kernel/capability services, MCP manager, pytest.

## Execution Status

- [x] Tasks 1-6 are implemented on feature branch `multi-seat-capability-autonomy`.
- [x] Focused backend verification completed on `2026-04-03`.
- [x] Final verification Step 1 completed:
  `PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q`
  -> `240 passed`
- [x] Final verification Step 2 completed:
  `PYTHONPATH=src python -m pytest tests/app/test_capabilities_execution.py tests/agents/test_skills_hub.py tests/app/test_capabilities_api.py tests/app/test_capability_catalog.py -q`
  -> `54 passed`
- [x] Additional focused regressions completed during integration:
  - `tests/app/test_industry_api.py -q` -> `108 passed`
  - `tests/app/test_capability_skill_service.py tests/industry/test_runtime_views_split.py -q` -> `15 passed`
  - `tests/app/test_startup_recovery.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/agents/test_react_agent_tool_compat.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/test_skill_service.py -q` -> `69 passed`
- [ ] Commit / merge / push intentionally deferred until operator instruction.

---

### Task 1: Formalize Role Prototype And Seat Instance Capability Layers

**Files:**
- Modify: `src/copaw/industry/models.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Test: `tests/app/test_industry_service_wiring.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] **Step 1: Write the failing tests**
  Add coverage proving industry runtime surfaces can distinguish:
  - role prototype capability pack
  - seat instance capability pack
  - cycle/lane delta pack placeholder
  - session overlay placeholder

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py -q
  ```
  Expected: new layered-capability assertions fail because seat/runtime payloads do not expose the typed separation yet.

- [ ] **Step 3: Write minimal implementation**
  Extend the role/seat runtime payload shape so the backend can carry a typed capability-layer snapshot without creating a second store. Reuse the existing role blueprint and agent runtime metadata chain.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/industry/models.py src/copaw/industry/service_team_runtime.py tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py
  git commit -m "feat: add multi-seat capability layer snapshot"
  ```

### Task 2: Build The Fast-Loop Effective Capability Resolver

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/agents/react_agent.py`
- Modify: `src/copaw/capabilities/capability_discovery.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/agents/test_react_agent_tool_compat.py`

- [ ] **Step 1: Write the failing tests**
  Add tests proving query execution resolves a seat's effective capability surface in this order:
  - role prototype
  - seat instance
  - cycle/lane delta
  - session overlay

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py -q
  ```
  Expected: new resolver assertions fail because the runtime still only uses coarse allowlists.

- [ ] **Step 3: Write minimal implementation**
  Add one canonical resolver path that computes the effective capability surface for the selected seat and passes the resolved `skills / tool capability ids / mcp clients` into `ReactAgent` without creating a new side channel.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/kernel/query_execution_runtime.py src/copaw/agents/react_agent.py src/copaw/capabilities/capability_discovery.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py
  git commit -m "feat: add seat effective capability resolver"
  ```

### Task 3: Close Automatic Gap Handling On The Existing Install And Assignment Chain

**Files:**
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/system_team_handlers.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/test_industry_api.py`

- [ ] **Step 1: Write the failing tests**
  Add coverage for these cases:
  - installed-but-unassigned capability gets auto-assigned
  - allowlisted capability gets auto-installed then assigned
  - guarded/confirm cases do not silently install
  - auto path reuses the same mutation/front-door semantics as manual `merge / replace`

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py -q
  ```
  Expected: new auto-gap-closure cases fail because install/assign still behaves like bootstrap-only or operator-only flow.

- [ ] **Step 3: Write minimal implementation**
  Reuse the current install and assignment services so the fast loop can choose:
  - reuse
  - assign
  - install + enable + assign
  while keeping risk routing on the existing governed front door.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/industry/service_activation.py src/copaw/app/routers/capability_market.py src/copaw/capabilities/system_team_handlers.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py
  git commit -m "feat: add automatic capability gap closure"
  ```

### Task 4: Scope MCP Exposure And Session Overlay Per Seat

**Files:**
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/kernel/child_run_shell.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/test_mcp_resilience.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write the failing tests**
  Add coverage proving MCP lifecycle is separated into:
  - substrate install
  - role/seat visibility
  - session mount
  and that one seat's overlay does not leak into another seat.

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/kernel/test_query_execution_runtime.py -q
  ```
  Expected: new scope-isolation assertions fail before mount semantics are tightened.

- [ ] **Step 3: Write minimal implementation**
  Harden the existing MCP overlay chain so it mounts only the selected seat/session surface, reuses the same scope lifecycle, and cleans up deterministically at the end of the run.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/kernel/test_query_execution_runtime.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/app/mcp/manager.py src/copaw/kernel/child_run_shell.py src/copaw/kernel/query_execution_runtime.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/kernel/test_query_execution_runtime.py
  git commit -m "feat: scope mcp overlays per seat session"
  ```

### Task 5: Implement Skill Replacement, Budgets, And Upgrade Lifecycle

**Files:**
- Modify: `src/copaw/capabilities/remote_skill_contract.py`
- Modify: `src/copaw/capabilities/skill_service.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Modify: `src/copaw/predictions/service_context.py`
- Test: `tests/capabilities/test_remote_skill_presentation.py`
- Test: `tests/app/test_capability_skill_service.py`
- Test: `tests/test_skill_service.py`

- [ ] **Step 1: Write the failing tests**
  Add coverage for:
  - role-specific skill budget enforcement
  - overlapping skill replacement instead of endless merge
  - single-seat trial before wider rollout
  - rollback when the candidate underperforms

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q
  ```
  Expected: lifecycle and budget assertions fail because current contracts do not fully encode the new discipline.

- [ ] **Step 3: Write minimal implementation**
  Extend the existing remote-skill trial and rollout contract so it can express:
  - candidate stage
  - trial stage
  - rollout stage
  - deprecated / retired / blocked
  - replacement target ids
  - role/seat budget checks

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/capabilities/remote_skill_contract.py src/copaw/capabilities/skill_service.py src/copaw/predictions/service_recommendations.py src/copaw/predictions/service_context.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py
  git commit -m "feat: add governed skill upgrade lifecycle"
  ```

### Task 6: Project Capability Governance Into The Runtime Read Model

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/industry/test_runtime_views_split.py`
- Test: `tests/app/test_industry_api.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write the failing tests**
  Add backend read-model coverage proving operators can inspect:
  - role prototype capability boundary
  - seat instance differences
  - current session overlay
  - candidate/trial/rollout/deprecated lifecycle state

- [ ] **Step 2: Run tests to verify they fail**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py -q
  ```
  Expected: new read-model assertions fail because runtime views do not project the typed autonomy state yet.

- [ ] **Step 3: Write minimal implementation**
  Extend the existing runtime read-model services so capability governance stays visible on the canonical backend projection instead of hiding only in install logs or raw metadata.

- [ ] **Step 4: Run tests to verify they pass**
  Re-run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py -q
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/overview_cards.py src/copaw/industry/service_runtime_views.py tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py
  git commit -m "feat: expose capability autonomy runtime projection"
  ```

### Final Verification

**Files:**
- Verify only; no new files

- [ ] **Step 1: Run focused backend regressions**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q
  ```

- [ ] **Step 2: Run adjacent regressions for existing capability/runtime chains**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_capabilities_execution.py tests/agents/test_skills_hub.py tests/app/test_capabilities_api.py tests/app/test_capability_catalog.py -q
  ```

- [ ] **Step 3: Update status docs**
  Update:
  - `TASK_STATUS.md`
  - any dated follow-up spec/plan references that changed during implementation

- [ ] **Step 4: Commit only this task's files**
  Do not add unrelated dirty files or `cc/`.
