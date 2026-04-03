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
- external bridge producers can now drive the same lifecycle end to end through the canonical Runtime Center bridge surface
- browser-attach transport facts now ride that same session/environment truth instead of a side channel

### 5.2 Accepted persistence boundary and truthful commit tail

Landed shape:

- pre-stream accepted persistence checkpoint
- bound execution-core chat turns now force a durable snapshot save before model execution starts
- bound execution-core chat turns now force a second snapshot save after the reply is materialized and before commit handling
- accepted persistence recorded into runtime context
- `commit_failed` emitted explicitly
- optimistic `committed` suppressed when runtime context already knows writeback failed
- downstream writeback failure returned from `MainBrainResultCommitter` no longer gets flattened into optimistic `committed`

Status:

- landed on the current runtime chat and session-backed main-brain chat front doors
- session-backed pure chat turns now use the same accepted-first durability discipline
- attached-intake writeback and kickoff outcomes now normalize onto the same `accepted_persistence / commit_outcome` contract
- future chat producers must stay on this contract instead of inventing parallel commit semantics

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
- the current runtime chat surfaces now expose the durable lifecycle on the same thread/control-thread contract
- future chat surfaces must continue to emit the same lifecycle contract instead of a parallel tail protocol

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
- shared operator-abort truth is covered separately in `5.7`; Windows actions stay on that same canonical guardrail chain

### 5.6 Execution-time browser/document guardrails

Landed shape:

- `surface_control_service.execute_document_action(...)` now enforces:
  - operator abort
  - host exclusion
  - frontmost verification
  - clipboard round-trip verification
- `surface_control_service.execute_browser_action(...)` now enforces the same guardrail set on the current live browser companion execution boundary
- runtime-level guardrails now flow from canonical adapter metadata:
  - `document_bridge.execution_guardrails`
  - `browser_companion.execution_guardrails`
- per-call `contract.guardrails` can still override or extend runtime guardrails
- guardrail blocks publish surface-specific runtime events:
  - `document.guardrail-blocked`
  - `browser.guardrail-blocked`

Status:

- landed for the current document/browser live execution boundaries
- future browser/document executor variants must stay on this same guardrail contract instead of inventing parallel checks

### 5.7 Canonical global operator abort truth and live execution enforcement

Landed shape:

- shared operator-abort state now lives on the canonical session/environment truth
- formal write/clear surfaces exist on the same Runtime Center lifecycle plane
- `WindowsDesktopHost.poll_operator_abort_signal(...)` can now act as a host-side producer and publish into that same canonical truth through `EnvironmentService / EnvironmentLeaseService`
- desktop environment execution now passes a hook-capable host executor into `EnvironmentService`, so host-side abort polling and restore hooks are no longer test-only surfaces
- read models expose the same operator-abort truth through:
  - `cooperative_adapter_availability.operator_abort_state`
  - `desktop_app_contract.operator_abort_state`
  - downstream execution guardrails on browser/document/windows surfaces
- browser/document/windows live execution boundaries all merge the shared operator-abort truth before action dispatch
- blocked actions emit surface-specific guardrail events and browser tool execution respects the same operator-abort truth
- bridge stop / archive and lease release paths now deterministically clear stale browser-attach continuity instead of leaving reconnect tokens and attach transport facts behind
- live execution cleanup now captures and restores foreground state through the current desktop host helpers instead of leaving restore discipline implicit

Status:

- landed for the current canonical runtime and live execution surfaces
- donor-style OS-specific ESC capture is no longer only a future adapter concern on Windows; the current desktop host now has a formal producer path onto the canonical operator-abort truth

### 5.8 Stable host-scoped memory continuity

Landed shape:

- `work_context_id` now flows through canonical host/session/workspace projections
- browser companion and other cooperative session truth can carry the same `work_context_id`
- truth-first memory recall already prefers `work_context` scope over broader fallbacks when present
- runtime chat media retain/adopt and main-brain scope snapshots now share the same `work_context / industry / agent` dirty-marking chain
- scope snapshot refresh is incremental on that formal chain instead of donor-style file-backed memory heuristics

Status:

- landed on the formal `work_context_id` truth chain
- no donor-style file memory, repo/worktree heuristics, or second memory truth has been introduced

### 5.9 Current-host acceptance evidence

Fresh evidence on the current host:

- focused regression:
  - `PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py tests/app/runtime_center_api_parts/detail_environment.py -q`
  - result: `107 passed`
- expanded execution-harness regression:
  - `PYTHONPATH=src python -m pytest tests/adapters/test_windows_host.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/routines/test_routine_service.py tests/routines/test_live_routine_smoke.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_main_brain_commit_service.py -q`
  - result: `224 passed, 9 skipped`
- live browser/desktop smoke:
  - `COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 PYTHONPATH=src python -m pytest tests/routines/test_live_routine_smoke.py -q -k "authenticated_continuation_cross_tab_save_reopen_smoke or live_desktop_routine_replay_round_trip"`
  - result: `2 passed`
- expanded live harness smoke:
  - `COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 PYTHONPATH=src python -m pytest tests/routines/test_live_routine_smoke.py -q -k "reconnect_cleanup_smoke or cross_surface_contention_smoke or live_desktop_routine_replay_round_trip"`
  - result: `2 passed, 1 skipped`

Interpretation:

- the browser smoke passed on the real browser routine chain and proved authenticated continuation, cross-tab reuse, save-and-reopen, download initiation, and screenshot evidence on one canonical runtime path
- the expanded desktop smoke now also covers cross-surface contention on the current host and proves the desktop side releases its session lease cleanly when a browser-style page-tab lock already owns the surface
- the expanded browser reconnect/cleanup smoke is now part of the live harness and skips explicitly when the current host cannot start the browser runtime, instead of pretending a host prerequisite failure is a product regression
- donor parity for the currently exercised CoPaw execution harness now includes host-side abort production, deterministic attach cleanup, and thicker cleanup/restore discipline on the canonical truth chain; the only remaining future follow-up stays the conditional remote-session transport reliability work in section `6`

## 6. Conditional Future Follow-ups

1. Harden remote-session transport reliability where that transport shape exists
   - stall-timer clearing on inbound activity
   - reconnect behavior for stalled remote sessions
   - only needed if CoPaw grows the same remote-session transport shape as the donor
   - this is not a reason to introduce a parallel remote-session subsystem preemptively

## 7. Acceptance Criteria

This donor alignment is real only if:

1. reattach does not silently fork a second host/session truth
2. lease/heartbeat/cleanup semantics run on that same truth
3. chat distinguishes accepted input, reply completion, and commit completion
4. `committed` is not emitted as an optimistic synonym for "tail finished"
5. Runtime Center and other read surfaces consume the same host continuity truth
6. execution-time guardrails are enforced on live execution paths, not only projected on read models
7. no second `cowork` store, config namespace, plugin namespace, or file-backed memory truth is introduced
8. shared operator-abort truth blocks live browser/document/windows execution on the same canonical session/environment chain
9. host/session continuity and truth-first memory continuity both resolve through `work_context_id` instead of repo/worktree/file heuristics

## 8. Testing Direction

Targeted verification should continue to cover:

- `tests/environments/test_cooperative_browser_companion.py`
- `tests/environments/test_cooperative_document_bridge.py`
- `tests/environments/test_environment_registry.py`
- `tests/environments/test_cooperative_windows_apps.py`
- `tests/app/runtime_center_api_parts/detail_environment.py`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/kernel/test_main_brain_chat_service.py`
- `console/src/pages/Chat/runtimeTransport.test.ts`
- `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`
