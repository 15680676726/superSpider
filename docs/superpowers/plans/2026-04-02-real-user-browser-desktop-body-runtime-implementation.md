# Real User Browser Desktop Body Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CoPaw feel like a product-grade child-agent runtime that can continue real user browser and Windows desktop work, while staying on CoPaw's formal `EnvironmentMount / SessionMount / EvidenceRecord` truth.

**Architecture:** Do not copy `cowork` as a parallel subsystem. Borrow donor runtime discipline from `cc/cowork` and land it on CoPaw's existing chat durability chain, `work_context_id` continuity chain, `lease_service`, and environment/session metadata. Any new helper must be a thin adapter over the current environment stack, not a second lifecycle center.

**Tech Stack:** Python, FastAPI, SQLite state store, Playwright, Windows desktop MCP adapter, Runtime Event Bus, SSE chat runtime, CoPaw environment/runtime services, `cc` donor bridge and computer-use runtime patterns.

---

## File Map

**Existing files to extend**

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/app/runtime_chat_stream_events.py`
- `src/copaw/app/routers/runtime_center_shared.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/lease_service.py`
- `src/copaw/environments/health_service.py`
- `src/copaw/environments/surface_control_service.py`
- `src/copaw/environments/cooperative/browser_companion.py`
- `src/copaw/environments/cooperative/windows_apps.py`
- `src/copaw/capabilities/browser_runtime.py`
- `src/copaw/agents/tools/browser_control.py`
- `console/src/pages/Chat/runtimeTransport.ts`
- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/environments/test_environment_registry.py`
- `tests/environments/test_cooperative_windows_apps.py`
- `tests/agents/test_browser_tool_evidence.py`
- `tests/app/runtime_center_api_parts/detail_environment.py`
- `console/src/pages/Chat/runtimeTransport.test.ts`
- `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`

**New files to create**

- `src/copaw/environments/cooperative/browser_attach_runtime.py`
- `tests/environments/test_cooperative_browser_attach_runtime.py`

**Grounded donor references**

- `cc/src/bridge/bridgeApi.ts`
- `cc/src/bridge/replBridge.ts`
- `cc/src/bridge/bridgeMain.ts`
- `cc/src/bridge/types.ts`
- `cc/src/QueryEngine.ts`
- `cc/src/hooks/useRemoteSession.ts`
- `cc/src/utils/computerUse/executor.ts`
- `cc/src/utils/computerUse/escHotkey.ts`
- `cc/src/utils/computerUse/appNames.ts`

**Explicit non-goals**

- do not introduce `cowork_settings.json`
- do not introduce `cowork_plugins`
- do not introduce `memdir` or file-backed continuity truth
- do not introduce a second chat or planner runtime

---

### Task 1: Tighten Accepted Reply Commit Durability

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_chat_stream_events.py`
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`
- Test: `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`

- [x] **Step 1: Write the failing backend durability test**

```python
def test_runtime_records_accepted_before_long_execution_and_never_emits_false_committed():
    ...
```

- [x] **Step 2: Run the targeted backend test and verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py -k "accepted or committed" -q`
Expected: FAIL because the runtime still allows optimistic completion gaps on some paths.

- [x] **Step 3: Write the failing frontend lifecycle test**

```ts
it('keeps accepted reply_done and commit_failed as separate phases', () => {
  ...
})
```

- [x] **Step 4: Run the targeted frontend tests and verify failure**

Run: `npm --prefix console test -- runtimeTransport.test.ts ChatRuntimeSidebar.test.tsx`
Expected: FAIL because frontend lifecycle handling does not yet fully match the stricter donor-grade durability contract.

- [x] **Step 5: Implement minimal backend durability fixes**

Implementation:
- persist accepted boundary before long execution
- make `committed` mean durable writeback success only
- keep `reply_done` distinct from commit completion

- [x] **Step 6: Implement minimal frontend lifecycle fixes**

Implementation:
- render accepted/reply/commit as separate runtime phases
- never collapse `commit_failed` into a generic tail-finished state

- [x] **Step 7: Re-run targeted backend and frontend tests**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py -k "accepted or committed" -q`
Run: `npm --prefix console test -- runtimeTransport.test.ts ChatRuntimeSidebar.test.tsx`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/copaw/kernel/query_execution_runtime.py src/copaw/app/runtime_chat_stream_events.py console/src/pages/Chat/runtimeTransport.ts console/src/pages/Chat/useChatRuntimeState.ts console/src/pages/Chat/ChatRuntimeSidebar.tsx tests/kernel/test_query_execution_runtime.py console/src/pages/Chat/runtimeTransport.test.ts console/src/pages/Chat/ChatRuntimeSidebar.test.tsx
git commit -m "feat: harden chat durability lifecycle"
```

### Task 2: Formalize Host Scoped Continuity Without Donor File Truth

**Files:**
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/capabilities/browser_runtime.py`
- Modify: `tests/environments/test_environment_registry.py`
- Modify: `tests/agents/test_browser_tool_evidence.py`

- [x] **Step 1: Write the failing continuity tests**

```python
def test_browser_continuity_prefers_work_context_and_mount_truth_over_transcript_style_fallback():
    ...


def test_environment_detail_projects_host_scoped_continuity_from_mount_session_truth():
    ...
```

- [x] **Step 2: Run targeted continuity tests and verify failure**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_environment_registry.py tests/agents/test_browser_tool_evidence.py -k "continuity or work_context" -q`
Expected: FAIL because the stricter continuity contract has not been fully enforced.

- [x] **Step 3: Tighten continuity resolution**

Implementation:
- root continuity in `work_context_id`
- preserve mount/session continuity refs needed for resume
- do not add transcript-grep or file-memory fallback truth

- [x] **Step 4: Project continuity to runtime read models**

Implementation:
- surface continuity through existing environment/session projections
- keep `host_twin_summary` and browser continuity aligned

- [x] **Step 5: Re-run targeted continuity tests**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_environment_registry.py tests/agents/test_browser_tool_evidence.py -k "continuity or work_context" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/environments/service.py src/copaw/environments/lease_service.py src/copaw/environments/health_service.py src/copaw/capabilities/browser_runtime.py tests/environments/test_environment_registry.py tests/agents/test_browser_tool_evidence.py
git commit -m "feat: formalize host scoped continuity"
```

### Task 3: Add Thin Browser Attach Runtime Over Existing Environment Truth

**Files:**
- Create: `src/copaw/environments/cooperative/browser_attach_runtime.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/cooperative/browser_companion.py`
- Test: `tests/environments/test_cooperative_browser_attach_runtime.py`
- Modify: `tests/environments/test_environment_registry.py`

- [x] **Step 1: Write the failing attach-runtime tests**

```python
def test_register_browser_attach_transport_persists_transport_on_mount_session_metadata():
    ...


def test_attach_runtime_does_not_create_second_browser_truth_object():
    ...
```

- [x] **Step 2: Run attach-runtime tests and verify failure**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_cooperative_browser_attach_runtime.py -q`
Expected: FAIL because the attach runtime adapter does not exist yet.

- [x] **Step 3: Implement the thin attach adapter**

Implementation:
- record attach transport/session/scope refs on existing environment/session metadata
- mirror active transport into current browser companion fields where needed
- do not add a second persistence model

- [x] **Step 4: Bind the adapter into `EnvironmentService`**

Implementation:
- add facade methods for register/clear/snapshot
- keep them as wrappers over existing repositories and metadata

- [x] **Step 5: Project attach facts through current browser companion flow**

Implementation:
- make current browser companion and read-model consumers see attach transport
- keep preferred path/fallback logic on the existing execution path chain

- [x] **Step 6: Re-run attach-runtime and environment tests**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/environments/cooperative/browser_attach_runtime.py src/copaw/environments/service.py src/copaw/environments/cooperative/browser_companion.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py
git commit -m "feat: add thin browser attach runtime"
```

### Task 4: Wire External Bridge Producer Lifecycle End To End

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/health_service.py`
- Modify: `tests/app/runtime_center_api_parts/detail_environment.py`
- Modify: `tests/environments/test_environment_registry.py`

- [x] **Step 1: Write the failing bridge lifecycle tests**

```python
def test_bridge_worker_can_drive_ack_heartbeat_reconnect_and_stop_on_existing_mount_truth():
    ...
```

- [x] **Step 2: Run targeted bridge tests and verify failure**

Run: `PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/detail_environment.py tests/environments/test_environment_registry.py -k "bridge or heartbeat or reconnect" -q`
Expected: FAIL because the current surface is not yet driven end-to-end by a producer-like flow.

- [x] **Step 3: Add missing bridge lifecycle wiring**

Implementation:
- keep bridge lifecycle on existing environment/session metadata
- prove `ack / heartbeat / stop / reconnect / archive / deregister` can be driven end-to-end

- [x] **Step 4: Update read surfaces**

Implementation:
- expose producer-driven lifecycle states on Runtime Center detail
- keep `seat_runtime` and `host_companion_session.bridge_registration` in sync

- [x] **Step 5: Re-run targeted bridge tests**

Run: `PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/detail_environment.py tests/environments/test_environment_registry.py -k "bridge or heartbeat or reconnect" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/routers/runtime_center_shared.py src/copaw/app/routers/runtime_center_routes_ops.py src/copaw/environments/service.py src/copaw/environments/health_service.py tests/app/runtime_center_api_parts/detail_environment.py tests/environments/test_environment_registry.py
git commit -m "feat: wire bridge lifecycle end to end"
```

### Task 5: Add End To End ESC Operator Abort Plumbing

**Files:**
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/surface_control_service.py`
- Modify: `src/copaw/environments/cooperative/windows_apps.py`
- Modify: `src/copaw/agents/tools/browser_control.py`
- Modify: `tests/environments/test_cooperative_windows_apps.py`
- Modify: `tests/agents/test_browser_tool_evidence.py`

- [x] **Step 1: Write the failing abort-plumbing tests**

```python
def test_global_operator_abort_propagates_into_windows_and_browser_execution_paths():
    ...
```

- [x] **Step 2: Run targeted abort tests and verify failure**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py -k "abort" -q`
Expected: FAIL because abort discipline is not yet end-to-end and cross-surface.

- [x] **Step 3: Add abort state propagation on existing lease/session truth**

Implementation:
- carry operator-abort state through existing lease/session metadata and runtime events
- do not create a separate desktop runtime truth object

- [x] **Step 4: Enforce abort on live execution paths**

Implementation:
- Windows app path must block consistently
- browser path must reach equivalent execution-time abort handling

- [x] **Step 5: Re-run targeted abort tests**

Run: `PYTHONPATH=src python -m pytest tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py -k "abort" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/environments/lease_service.py src/copaw/environments/surface_control_service.py src/copaw/environments/cooperative/windows_apps.py src/copaw/agents/tools/browser_control.py tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py
git commit -m "feat: add end to end operator abort plumbing"
```

### Task 6: Prove Real User Browser Desktop Runtime With Live Smoke

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-02-cc-cowork-donor-mapping-and-copaw-alignment.md`

- [x] **Step 1: Add explicit acceptance checklist**

Checklist must prove:
- accepted input durability
- real browser attach continuity
- no second browser/session truth
- producer-driven bridge lifecycle
- Windows and browser abort behavior
- cleanup and resume visibility

Acceptance evidence on the current host:
- `PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py tests/app/runtime_center_api_parts/detail_environment.py -q` -> `107 passed`
- `COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 PYTHONPATH=src python -m pytest tests/routines/test_live_routine_smoke.py -q -k "authenticated_continuation_cross_tab_save_reopen_smoke or live_desktop_routine_replay_round_trip"` -> `2 passed`
- browser live smoke passed on the real browser routine chain with authenticated continuation, cross-tab reuse, save-and-reopen, download initiation, and screenshot evidence
- desktop live smoke now also passes on the current host; the final blocker was a compatibility gap in `WindowsDesktopHost.get_foreground_window()` where live callers expected a top-level `handle` while the host only exposed the nested `window.handle`

- [x] **Step 2: Run focused regression**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py tests/app/runtime_center_api_parts/detail_environment.py -q`
Expected: PASS

- [x] **Step 3: Run live smoke**

Prove on a real machine:
- a child agent can continue a real user browser scope
- browser continuity survives reconnect/rebind
- a Windows app action respects exclusive ownership and abort
- Runtime Center shows the same lifecycle truth

- [x] **Step 4: Update status and donor spec**

Document:
- what is landed
- what remains
- what is intentionally still not copied from `cc/cowork`

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md docs/superpowers/specs/2026-04-02-cc-cowork-donor-mapping-and-copaw-alignment.md
git commit -m "docs: update real-user runtime acceptance status"
```
