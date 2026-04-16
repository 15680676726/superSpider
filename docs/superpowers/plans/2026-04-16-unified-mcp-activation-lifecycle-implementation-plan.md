# Unified MCP Activation Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize MCP activation/self-heal into one shared lifecycle for `stateless`, `auth-bound`, `host-attached`, and `workspace-bound` capabilities without introducing a second truth source.

**Architecture:** Introduce one shared capability activation plane over existing `CapabilityMount / EnvironmentMount / SessionMount / MCPClientRuntimeRecord` truth. Keep `doctor` read-only, add an explicit `activate` write surface, move template-local lifecycle logic behind shared activation models, a shared orchestrator, and class-specific activation strategies, then route the unified capability execution front-door through the same activation plane before execution.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite-backed state services, EnvironmentService, MCPClientManager runtime contract, pytest

---

### File Map

**Create**
- `src/copaw/capabilities/activation_models.py`
  - Shared activation status/reason/result models and helper normalization.
- `src/copaw/capabilities/activation_runtime.py`
  - Shared activation orchestrator and retry/self-heal budget logic.
- `src/copaw/capabilities/activation_strategies.py`
  - Class-specific activation strategy entry points.
- `tests/capabilities/test_activation_runtime.py`
  - Unit tests for shared lifecycle contract and reason mapping.

**Modify**
- `src/copaw/capabilities/install_templates.py`
  - Replace template-local activation heuristics with shared activation calls.
- `src/copaw/app/routers/capability_market.py`
  - Keep `doctor` read-only, add the explicit `activate` surface, and return shared activation truth through product surfaces.
- `src/copaw/capabilities/service.py`
  - Route the unified capability execution front-door through the shared activation plane.
- `src/copaw/app/mcp/runtime_contract.py`
  - Add mapping helpers from MCP runtime state to activation taxonomy.
- `src/copaw/app/mcp/manager.py`
  - Expose the runtime state needed by activation without absorbing product logic.
- `src/copaw/environments/service.py`
  - Support shared host-attached/workspace-bound remediation entry points where needed.
- `tests/app/test_capability_market_api.py`
  - Lock install-template `doctor / activate / example-run` behavior for each class.
- `tests/app/test_capabilities_execution.py`
  - Lock execution front-door auto-activation behavior.
- `tests/environments/test_cooperative_browser_companion.py`
  - Keep host-attached browser continuity/regression coverage green.
- `tests/app/test_mcp_runtime_contract.py`
  - Lock activation mapping over MCP runtime diagnostics.
- `TASK_STATUS.md`
  - Record the full-lifecycle rollout once each phase lands.

---

### Task 1: Lock the shared activation contract

**Files:**
- Create: `src/copaw/capabilities/activation_models.py`
- Create: `tests/capabilities/test_activation_runtime.py`

- [ ] Write a failing test for the shared activation status set: `installed / activating / ready / healing / waiting_human / blocked`.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k status` and verify it fails because the shared models do not exist yet.
- [ ] Write a failing test for the shared failure taxonomy mapping, covering:
  - `dependency_missing`
  - `adapter_offline`
  - `session_unbound`
  - `host_unavailable`
  - `token_expired`
  - `scope_unbound`
  - `human_auth_required`
  - `captcha_required`
  - `two_factor_required`
  - `policy_blocked`
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k taxonomy` and verify it fails for the expected missing-model reason.
- [ ] Implement the minimal shared models in `src/copaw/capabilities/activation_models.py`.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k "status or taxonomy"` and verify they pass.

### Task 2: Land the shared activation orchestrator

**Files:**
- Create: `src/copaw/capabilities/activation_runtime.py`
- Create: `src/copaw/capabilities/activation_strategies.py`
- Modify: `tests/capabilities/test_activation_runtime.py`

- [ ] Write a failing test proving the orchestrator always performs:
  - resolve canonical context
  - read readiness
  - optional remediation
  - canonical re-read
  - final status mapping
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k orchestrator` and verify it fails because the runtime does not exist yet.
- [ ] Write a failing test proving recoverable failures end in `healing -> ready` only after a fresh re-read, not by assumption.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k reheal` and verify it fails correctly.
- [ ] Implement the minimal orchestrator and strategy interface in `activation_runtime.py` and `activation_strategies.py`.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q` and verify the shared contract is green.

### Task 3: Add the explicit activate product surface

**Files:**
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `tests/app/test_capability_market_api.py`

- [ ] Write a failing regression test proving install-template `doctor` stays read-only while `activate` is allowed to perform bounded remediation and return the shared activation proof.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q -k activation_surface` and verify it fails.
- [ ] Add the explicit `activate` route/surface and wire it to the shared activation orchestrator without moving mutation semantics into `doctor`.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q -k "doctor or activate"` and verify the contract is green.

### Task 4: Migrate the existing host-attached browser slice behind the shared orchestrator

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `tests/app/test_capability_market_api.py`

- [ ] Write a failing regression test proving `browser-companion` example-run now reports the shared activation status/result shape instead of template-local ad hoc semantics.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q -k browser_companion_activation_contract` and verify it fails.
- [ ] Refactor the current `browser-companion` auto-heal path to call the shared orchestrator rather than embedding lifecycle logic directly in `_browser_companion_example_run(...)`.
- [ ] Make `browser-companion` example-run consume the explicit `activate` surface/contract instead of remaining the only place that knows how to heal browser companion state.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q -k "browser_companion or browser_local_session_start"` and verify the browser cooperative path still passes.

### Task 5: Complete the host-attached class

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `tests/app/test_capability_market_api.py`

- [ ] Write a failing test for `document-office-bridge` proving an unbound session maps to the shared `session_unbound`/activation contract instead of a template-local raw error.
- [ ] Write a failing test for `host-watchers` proving unavailable watcher state maps to the shared host-attached activation contract.
- [ ] Write a failing test for `windows-app-adapters` proving adapter availability and host/session binding use the shared activation result shape.
- [ ] Run the focused host-attached pytest matrix and verify these fail before implementation.
- [ ] Move all four host-attached templates onto the shared orchestrator with a shared host-attached strategy.
- [ ] Run:
  - `python -m pytest tests/app/test_capability_market_api.py -q -k "browser_companion or document_office_bridge or host_watchers or windows_app_adapters"`
  - `python -m pytest tests/environments/test_cooperative_browser_companion.py -q`
  and verify they pass.

### Task 6: Add the workspace-bound class

**Files:**
- Modify: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/capabilities/activation_strategies.py`
- Modify: `tests/app/test_mcp_runtime_contract.py`

- [ ] Write a failing test proving scope-local MCP overlays map `overlay_scope / overlay_mode / pending_reload / dirty` into the shared activation result, with `scope_unbound` and workspace/session remediation semantics.
- [ ] Run `python -m pytest tests/app/test_mcp_runtime_contract.py -q -k workspace_bound_activation` and verify it fails.
- [ ] Implement the workspace-bound activation strategy and runtime-contract mapping helpers.
- [ ] Run `python -m pytest tests/app/test_mcp_runtime_contract.py -q` and verify it passes.

### Task 7: Add the auth-bound class

**Files:**
- Modify: `src/copaw/capabilities/activation_strategies.py`
- Modify: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `tests/capabilities/test_activation_runtime.py`

- [ ] Write a failing unit test proving token-expired cases attempt refresh/retry first and only land in `waiting_human` for:
  - first auth
  - captcha
  - 2FA
  - explicit human confirm
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k auth_bound` and verify it fails.
- [ ] Implement the auth-bound strategy and human-boundary mapping.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k auth_bound` and verify it passes.

### Task 8: Add the stateless class

**Files:**
- Modify: `src/copaw/capabilities/activation_strategies.py`
- Modify: `tests/capabilities/test_activation_runtime.py`

- [ ] Write a failing test proving stateless MCP-style capabilities map runtime reconnect/rebuild into the same activation result contract without requiring environment/session truth.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k stateless` and verify it fails.
- [ ] Implement the stateless strategy.
- [ ] Run `python -m pytest tests/capabilities/test_activation_runtime.py -q -k stateless` and verify it passes.

### Task 9: Route the real execution front-door through activation

**Files:**
- Modify: `src/copaw/capabilities/service.py`
- Modify: `tests/app/test_capabilities_execution.py`

- [ ] Write a failing regression test proving real capability execution auto-invokes the shared activation plane when the capability class is not currently `ready`.
- [ ] Run `python -m pytest tests/app/test_capabilities_execution.py -q -k auto_activation` and verify it fails.
- [ ] Wire the unified capability execution front-door through the shared activation plane so execution no longer requires humans to manually run `doctor` or `example-run` first.
- [ ] Run `python -m pytest tests/app/test_capabilities_execution.py -q -k auto_activation` and verify it passes.

### Task 10: Converge product surfaces on the shared contract

**Files:**
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `tests/app/test_capability_market_api.py`

- [ ] Write a failing test proving capability-market install-template `doctor`, `activate`, and `example-run` responses expose the shared activation status/reason contract consistently across classes.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q -k activation_contract_surface` and verify it fails.
- [ ] Update the router and template surfaces to emit the shared activation contract.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py -q` and verify it passes.

### Task 11: Record rollout status and verify end-to-end coverage

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] Update `TASK_STATUS.md` with:
  - shared activation plane landed
  - host-attached/workspace-bound/auth-bound/stateless phase status
  - remaining non-goals or open follow-ups
- [ ] Run the focused final matrix:
  - `python -m pytest tests/capabilities/test_activation_runtime.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/environments/test_cooperative_browser_companion.py tests/app/test_runtime_bootstrap_split.py -q`
- [ ] Verify all commands are green before calling the lifecycle generalization landed.

---

## Review Note

This plan was written in-session without dispatching a review subagent, because the current turn did not include fresh user authorization for delegation. If delegation is re-enabled later, run the normal plan review loop before large-scale execution.
