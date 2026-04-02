# CC Cowork Donor Mapping And CoPaw Alignment

## 1. Core Decision

CoPaw should borrow `cc/cowork` runtime discipline, not copy `cowork` as a parallel product subsystem.

Everything donor-aligned must still land on CoPaw's formal object chain:

- `EnvironmentMount`
- `SessionMount`
- `CapabilityMount`
- `EvidenceRecord`

It must not introduce:

- a second chat front door
- a second session truth
- a second config/plugin namespace
- a file-backed memory truth
- hidden env-var or settings-bit runtime truth

## 2. Real Donor Inventory

This donor baseline is grounded in the actual `cc` code paths, not only in prior CoPaw docs.

Primary donor areas:

- `cc/src/bridge/bridgeApi.ts`
- `cc/src/bridge/replBridge.ts`
- `cc/src/bridge/bridgeMain.ts`
- `cc/src/bridge/types.ts`
- `cc/src/QueryEngine.ts`
- `cc/src/hooks/useRemoteSession.ts`
- `cc/src/utils/computerUse/executor.ts`
- `cc/src/utils/computerUse/escHotkey.ts`
- `cc/src/utils/computerUse/appNames.ts`
- `cc/src/utils/plugins/pluginDirectories.ts`
- `cc/src/utils/settings/settings.ts`
- `cc/src/memdir/paths.ts`
- `cc/src/memdir/memdir.ts`

## 3. Best Donor Points

### 3.1 Bridge registration, lease lifecycle, and reattach semantics

Borrow:

- typed worker origin
- session capacity
- environment/session reuse
- lease lifecycle semantics
- reconnect/archive/deregister boundaries

Land in CoPaw:

- `EnvironmentService`
- `lease_service`
- `health_service`
- Runtime Center ops routes

### 3.2 Chat acceptance, reply completion, and commit separation

Borrow:

- accepted input is not the same phase as reply completion
- reply completion is not the same phase as durable commit
- lifecycle tails must stay visible after the visible reply ends

Land in CoPaw:

- `QueryExecutionRuntime`
- `runtime_chat_stream_events`
- `runtimeTransport`
- `useChatRuntimeState`
- `ChatRuntimeSidebar`

### 3.3 Execution-time computer-use guardrails

Borrow:

- operator abort
- host/window exclusion
- frontmost verification
- clipboard round-trip verification
- prompt-safe app/window label exposure

Land in CoPaw:

- `surface_control_service`
- `windows_apps`
- `health_service`
- runtime event bus / host-event recovery chain

### 3.4 Stable continuity scope

Borrow only the problem statement:

- embedded or reattached host sessions need a stable continuity key

Do not borrow:

- file-backed memory truth
- repo/worktree/cwd heuristics as formal continuity truth
- env-var or settings-based memory path truth

Land in CoPaw:

- `work_context_id`
- `EnvironmentMount / SessionMount` continuity
- truth-first memory read chain

## 4. Explicit Non-Goals

Do not copy:

- `cowork_settings.json`
- `cowork_plugins`
- hidden settings/plugins mode coupling
- `CLAUDE_COWORK_*` runtime truth
- `MEMORY.md` + daily-log memory truth
- transcript-grep recovery as canonical continuity
- a second `cowork` chat/planner/runtime chain

## 5. Already Landed Alignment

### 5.1 Bridge registration plus canonical Runtime Center lifecycle surface

Landed shape:

- `worker_type`
- `max_sessions`
- `spawn_mode`
- `reuse_environment_id`
- `bridge_work_id`
- `bridge_work_status`
- `bridge_heartbeat_at`
- `bridge_session_id`
- `bridge_stopped_at`
- `bridge_stop_mode`
- `workspace_trusted`
- `elevated_auth_state`

Canonical operations now exist on one formal chain:

- `ack`
- `heartbeat`
- `stop`
- `reconnect`
- `archive`
- `deregister`

Status:

- landed as formal CoPaw read/write contract
- still not proof that an external bridge producer is emitting the full lifecycle end to end

### 5.2 Accepted persistence boundary and truthful commit tail

Landed shape:

- pre-stream accepted persistence checkpoint
- accepted persistence recorded into runtime context
- `commit_failed` emitted explicitly
- optimistic `committed` suppressed when runtime context already knows writeback failed

Status:

- materially better than the old CoPaw behavior
- still weaker than the donor's stricter flush discipline before long execution and before final handoff

### 5.3 Hidden tail split and first-class reply lifecycle visibility

Landed shape:

- visible reply stream ends when the real reply ends
- hidden tail sidecars continue in the background
- frontend models these lifecycle phases:
  - `accepted`
  - `reply_done` from backend `turn_reply_done`
  - `commit_started`
  - `confirm_required`
  - `committed`
  - `commit_failed`

Status:

- reply/commit separation is now visible on the chat page
- strict donor-grade durability semantics are still not complete

### 5.4 Prompt-safe app/window labels on the read model

Landed shape:

- raw adapter metadata keeps original host-provided strings
- prompt-facing projections sanitize:
  - `desktop_app_contract.app_identity`
  - `desktop_app_contract.window_anchor_summary`
  - downstream `cooperative_adapter_availability.windows_app_adapters.app_identity`

Status:

- landed
- this is read-model hardening, not the full execution-time guardrail story

### 5.5 Execution-time Windows app guardrails

Landed shape:

- `surface_control_service.execute_windows_app_action(...)` now enforces:
  - operator abort
  - host exclusion
  - frontmost verification
  - clipboard round-trip verification
- runtime-level guardrails can come from canonical adapter metadata
- per-call guardrails can still override or extend them
- verifier hooks are supported through:
  - `guardrail_snapshot`
  - `verify_frontmost`
  - `verify_clipboard_roundtrip`
- guardrail blocks publish `desktop.guardrail-blocked` runtime events

Status:

- landed for the Windows app execution boundary
- still not the same as donor-complete global ESC hotkey plumbing
- browser/document execution paths do not yet have equivalent execution-time guardrails

## 6. Remaining Alignment Work

1. Complete donor-grade chat durability
   - persist and flush accepted input before long execution
   - make `committed` a strict proof of durable writeback success across the whole chat pipeline

2. Complete external bridge producer/runtime wiring
   - the formal lifecycle surface exists
   - external bridge workers still need to drive it end to end

3. Harden remote-session transport reliability where that transport shape exists
   - stall-timer clearing on inbound activity
   - reconnect behavior for stalled remote sessions
   - only needed if CoPaw grows the same remote-session shape

4. Extend execution-time guardrails beyond the Windows app boundary
   - browser/document parity
   - end-to-end global operator abort plumbing

5. Formalize stable host-scoped memory continuity
   - do it through `work_context_id` and formal mount/session truth
   - do not add donor-style file memory or repo/worktree heuristics

## 7. Acceptance Criteria

This donor alignment is real only if:

1. reattach does not silently fork a second host/session truth
2. lease/heartbeat/cleanup semantics run on that same truth
3. chat distinguishes accepted input, reply completion, and commit completion
4. `committed` is not emitted as an optimistic synonym for "tail finished"
5. Runtime Center and other read surfaces consume the same host continuity truth
6. execution-time guardrails are enforced on live execution paths, not only projected on read models
7. no second `cowork` store, config namespace, plugin namespace, or file-backed memory truth is introduced

## 8. Testing Direction

Targeted verification should continue to cover:

- `tests/environments/test_environment_registry.py`
- `tests/environments/test_cooperative_windows_apps.py`
- `tests/app/runtime_center_api_parts/detail_environment.py`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/kernel/test_main_brain_chat_service.py`
- `console/src/pages/Chat/runtimeTransport.test.ts`
- `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`
