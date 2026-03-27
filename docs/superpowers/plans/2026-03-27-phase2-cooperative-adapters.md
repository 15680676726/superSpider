# Phase 2 Cooperative Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Symbiotic Host Runtime Phase 2 (`Cooperative Adapters`) as first-class runtime/capability/install surfaces on top of the existing Phase 1 seat/runtime baseline.

**Architecture:** Add cooperative adapter runtimes as execution-side services that write only to `EnvironmentMount / SessionMount` metadata and emit runtime events, then project them back through existing environment health/read models. Surface the families as first-class `CapabilityMount`s and install-template/runtime-selection products without introducing a second truth source.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state repositories, RuntimeEventBus, pytest

---

## File Map

- Create: `src/copaw/environments/cooperative/__init__.py`
- Create: `src/copaw/environments/cooperative/browser_companion.py`
- Create: `src/copaw/environments/cooperative/document_bridge.py`
- Create: `src/copaw/environments/cooperative/watchers.py`
- Create: `src/copaw/environments/cooperative/windows_apps.py`
- Create: `src/copaw/environments/cooperative/execution_path.py`
- Create: `tests/environments/test_cooperative_browser_companion.py`
- Create: `tests/environments/test_cooperative_document_bridge.py`
- Create: `tests/environments/test_cooperative_watchers.py`
- Create: `tests/environments/test_cooperative_windows_apps.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`
- Modify: `src/copaw/capabilities/browser_runtime.py`
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `src/copaw/capabilities/registry.py`
- Create: `src/copaw/capabilities/sources/cooperative.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `tests/app/test_capability_market_api.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`
- Modify: `TASK_STATUS.md`

## Task 1: Cooperative browser companion runtime

**Files:**
- Create: `src/copaw/environments/cooperative/browser_companion.py`
- Create: `tests/environments/test_cooperative_browser_companion.py`
- Modify: `src/copaw/capabilities/browser_runtime.py`

- [ ] Write failing tests for attach/register/update projection metadata and execution-path preference.
- [ ] Run: `pytest tests/environments/test_cooperative_browser_companion.py -q`
- [ ] Implement the browser companion runtime service with session metadata writes, host event emission, and snapshot helpers.
- [ ] Extend `BrowserRuntimeService` to expose companion-aware runtime snapshots/registration helpers without bypassing existing browser continuity contracts.
- [ ] Re-run: `pytest tests/environments/test_cooperative_browser_companion.py tests/agents/test_browser_tool_evidence.py -q`

## Task 2: Document bridge runtime

**Files:**
- Create: `src/copaw/environments/cooperative/document_bridge.py`
- Create: `tests/environments/test_cooperative_document_bridge.py`

- [ ] Write failing tests for Office/document bridge registration, supported-family projection, and runtime selection semantics.
- [ ] Run: `pytest tests/environments/test_cooperative_document_bridge.py -q`
- [ ] Implement document bridge registration/update helpers that persist bridge identity/status/family support into the canonical session/environment metadata path.
- [ ] Re-run: `pytest tests/environments/test_cooperative_document_bridge.py -q`

## Task 3: Filesystem/download/notification watchers

**Files:**
- Create: `src/copaw/environments/cooperative/watchers.py`
- Create: `tests/environments/test_cooperative_watchers.py`

- [ ] Write failing tests for watcher registration, download-completed/runtime event emission, and host-event projection compatibility.
- [ ] Run: `pytest tests/environments/test_cooperative_watchers.py -q`
- [ ] Implement watcher service methods that update watcher metadata, publish runtime events, and preserve the “Host Event Bus is a mechanism, not a truth store” boundary.
- [ ] Re-run: `pytest tests/environments/test_cooperative_watchers.py tests/environments/test_environment_registry.py -q`

## Task 4: Windows app adapters and execution path policy

**Files:**
- Create: `src/copaw/environments/cooperative/windows_apps.py`
- Create: `src/copaw/environments/cooperative/execution_path.py`
- Create: `tests/environments/test_cooperative_windows_apps.py`

- [ ] Write failing tests for Windows app adapter registration, app-identity/control-channel projection, and `native/cooperative -> semantic -> ui-fallback` path resolution.
- [ ] Run: `pytest tests/environments/test_cooperative_windows_apps.py -q`
- [ ] Implement Windows app adapter service plus shared execution-path resolver for browser/document/app workloads.
- [ ] Re-run: `pytest tests/environments/test_cooperative_windows_apps.py -q`

## Task 5: EnvironmentService integration and capability graph surfacing

**Files:**
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`
- Create: `src/copaw/capabilities/sources/cooperative.py`
- Modify: `src/copaw/capabilities/registry.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`

- [ ] Write failing tests for EnvironmentService cooperative facade exposure and bootstrap wiring.
- [ ] Run: `pytest tests/app/test_runtime_bootstrap_split.py -q`
- [ ] Integrate the new cooperative services into `EnvironmentService` without changing the truth model boundary.
- [ ] Add first-class `CapabilityMount` families for browser companion, document bridge, host watchers, and Windows app adapters.
- [ ] Re-run: `pytest tests/app/test_runtime_bootstrap_split.py tests/environments/test_environment_registry.py -q`

## Task 6: Install-template and API surfaces

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `tests/app/test_capability_market_api.py`

- [ ] Write failing tests for new install templates / detail / doctor / example-run surfaces.
- [ ] Run: `pytest tests/app/test_capability_market_api.py -q`
- [ ] Add install-template/runtime surfaces for cooperative browser companion, document bridge, host watchers, and Windows app adapters.
- [ ] Ensure example runs/doctor payloads route through the same runtime/capability vocabulary and reflect mode-aware execution selection.
- [ ] Re-run: `pytest tests/app/test_capability_market_api.py -q`

## Task 7: Status board and acceptance closeout

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] Update the status board to record Phase 2 code baseline and remaining next-phase boundaries.
- [ ] Run the focused Phase 2 acceptance slice:

```bash
pytest tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_capability_market_api.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q
```

- [ ] Run broader regression once focused acceptance is green:

```bash
pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q
```
