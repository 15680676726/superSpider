# cc/cowork Donor Mapping and CoPaw Alignment

**Context.** CoPaw already has formal execution-side architecture documents for `Symbiotic Host Runtime`, `Host Companion Session`, `Cooperative Adapter`, `Host Continuity`, and `Full Host Digital Twin`. What is still missing is a donor-specific alignment document that answers a narrower question:

> when we inspect the real `cc/cowork` code, which parts are worth borrowing into CoPaw, where should they land in the existing object model, what has already been landed, and what must not be copied?

This document exists to make that mapping explicit and auditable.

It does **not** replace:

- `2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`
- `2026-03-30-host-continuity-contract-design.md`
- `2026-03-30-canonical-host-continuity-plan.md`
- `2026-03-30-full-host-digital-twin-terminal-closure.md`

It should be read as a donor-alignment layer on top of those existing formal documents.

## 1. Core Decision

`cc/cowork` should **not** be imported into CoPaw as a parallel subsystem.

The correct stance is:

1. borrow `cowork` as a runtime-discipline donor
2. land each donor point into CoPaw's existing formal objects
3. refuse any donor pattern that would introduce:
   - a second truth source
   - a second host/session state tree
   - a second settings/plugins namespace
   - env-var-driven core runtime semantics

In CoPaw, the product word `coworker` may exist as a UI or presentation label, but the backend truth must remain:

- `EnvironmentMount`
- `SessionMount`
- `CapabilityMount`
- `EvidenceRecord`
- derived `host_twin / host_twin_summary / workspace_graph`

## 2. Donor Audit Scope

This alignment is based on direct code inspection of the real `cc` donor files, not on secondary summaries.

Primary donor files inspected:

- `cc/src/bridge/bridgeApi.ts`
- `cc/src/bridge/replBridge.ts`
- `cc/src/bridge/bridgeMain.ts`
- `cc/src/bridge/types.ts`
- `cc/src/QueryEngine.ts`
- `cc/src/hooks/useRemoteSession.ts`
- `cc/src/utils/computerUse/executor.ts`
- `cc/src/utils/computerUse/escHotkey.ts`
- `cc/src/utils/computerUse/appNames.ts`
- `cc/src/memdir/paths.ts`
- `cc/src/memdir/memdir.ts`
- `cc/src/utils/plugins/pluginDirectories.ts`
- `cc/src/utils/settings/settings.ts`

## 3. Formal Mapping Rule

Every accepted donor point must map back to one of the following CoPaw formal targets:

| Donor concern | CoPaw formal target |
| --- | --- |
| bridge registration / leased work lifecycle / worker origin / capacity / reattach / workspace trust | `Seat Runtime` and `Host Companion Session` projections over `EnvironmentMount + SessionMount` |
| browser / desktop / watcher execution | `Cooperative Adapter` family under `CapabilityMount` |
| host continuity / handoff / resume / verification | `Host Companion Session` + `host_twin_summary` |
| host event / recovery trigger / return-to-human | `Host Event` backed by `EvidenceRecord + ObservationCache + runtime projections` |
| chat acceptance / pre-loop durability / reply-complete / commit lifecycle / resume durability | unified chat runtime chain, not a parallel chat system |
| memory scope continuity | formal `work_context_id`-anchored runtime scope, not repo/worktree/cwd/env-var heuristics |

If a donor point cannot be mapped cleanly to one of those targets, it should not enter the main line.

## 4. Best Donor Points

### 4.1 Bridge registration, lease, and reattach contract

The strongest donor point in `cc/cowork` is not only registration. It is the whole bridge-side leased work contract:

- `worker_type`
- `max_sessions`
- `reuseEnvironmentId`
- spawn/isolation semantics
- work ack / heartbeat / stop / archive / deregister
- pointer-based resume and fresh-session fallback
- workspace-trust / elevated-auth gating before the bridge is considered usable

Why it matters:

- it gives the runtime a stable idea of what kind of execution seat it is talking to
- it allows reattach instead of silently creating a second environment/session
- it makes concurrency and capacity explicit
- it turns seat/session continuity into an explicit lease state machine instead of a bag of metadata
- it makes "bridge ready for real work" stricter than "bridge registered once"

CoPaw landing zone:

- `Seat Runtime`
- `Host Companion Session`
- `host_twin_summary`
- `lease_service`
- host recovery/read models

CoPaw files:

- `src/copaw/environments/models.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/health_service.py`

Status:

- partially landed at the projection level
- `bridge_registration` is already projected into `seat_runtime` and `host_companion_session`
- the donor-equivalent lease lifecycle (`ack / heartbeat / stop / archive / deregister / reconnect`) is not yet landed as a demonstrated CoPaw producer/runtime contract in the current cooperative slice
- pointer-based continuity and workspace-trust/elevated-auth semantics are not yet explicitly mapped in this donor wave

### 4.2 Durable accept and truthful commit lifecycle

`cc` persists and flushes user acceptance before entering a long-running query loop, then flushes again before yielding the result. This is one of the most important donor disciplines for CoPaw chat reliability.

Why it matters:

- the UI can distinguish accepted work from completed writeback
- resume/recovery works even if the long-running phase dies mid-flight
- the user does not see "reply already finished but send state still hangs forever"
- the runtime can treat `committed` as a truth-bearing phase instead of a best-effort optimistic signal

CoPaw landing zone:

- unified `/runtime-center/chat/run` chain
- runtime stream sidecar lifecycle
- control-thread continuity

CoPaw files:

- `src/copaw/app/runtime_chat_stream_events.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/main_brain_chat_service.py`
- `console/src/pages/Chat/runtimeTransport.ts`

Status:

- partially landed at the lifecycle-visibility level
- `accepted` is emitted before long execution
- hidden sidecar tail is now split from the visible chat stream
- frontend now shows tail lifecycle states after reply completion
- not yet donor-equivalent on pre-loop durability: CoPaw still does not persist-and-flush accepted input before the long-running execution path in the same way `cc` does
- not yet donor-equivalent on commit truth: current `committed` should still be treated as an optimistic lifecycle signal, not proof that durable writeback truly succeeded

### 4.3 Computer-use host safety contract

`cc/cowork` has a strong host-control discipline around desktop execution:

- host exclusion
- frontmost/window gating
- operator abort
- clipboard restore verification
- prompt hardening around app names and titles

Why it matters:

- these are the real contracts that make a long-lived host seat safe
- they fit CoPaw's `Windows Seat Runtime Baseline` direction
- they strengthen the execution layer without creating new truth objects

CoPaw landing zone:

- `windows_apps`
- `browser_companion`
- `watchers`
- `host_event_recovery_service`
- `health_service`

Status:

- conceptually aligned
- CoPaw is currently stronger on host truth, recovery planning, and read-model projection than on execution-time guardrails
- the donor-equivalent execution-time guardrails are still largely unlanded:
  - global ESC abort
  - host/screenshot exclusion
  - frontmost safety gate
  - clipboard round-trip protection
- prompt-facing app/window identity sanitization is also not yet donor-equivalent and remains a specific unlanded safety gap

### 4.4 Stable continuity scope, not file-based memory donor

`cc/cowork` uses memory-path override patterns, git-root heuristics, and a file-based memory pipeline to keep embedded sessions on a stable continuity scope. The implementation surface is not acceptable for CoPaw, but the continuity problem it solves is real.

Why it matters:

- embedded or reattached host sessions need stable continuity
- per-turn cwd or transient transport state is not enough
- repo/worktree churn can silently fork continuity if the formal key is weak

CoPaw landing zone:

- `work_context_id`
- `EnvironmentMount / SessionMount` continuity
- truth-first memory read chain

Status:

- concept accepted
- implementation must remain formal and explicit
- only the stable continuity problem is borrowable
- the donor's file-based memory system is not borrowable:
  - `MEMORY.md`
  - daily logs
  - topic-file distillation
  - transcript-grep recovery
  - mkdir/write carve-out behavior
  - settings-based or env-based memory path overrides
  - repo/worktree/cwd identity as a formal continuity key

## 5. Limited-Use Donor Points

### 5.1 Remote session transport reliability

`cc`'s `useRemoteSession` donor is not only echo dedup. It also carries:

- remote echo dedup
- stall timer clearing on any inbound activity
- compaction-aware timeout handling
- reconnect behavior when a remote session stalls

Landing zone:

- transport hygiene only

Status:

- conditional donor
- medium value only if CoPaw grows the same remote session / daemon / resubscribe transport shape
- not currently core architecture, but richer than "dedup only"

### 5.2 Spawn/isolation mode semantics

`cc` distinguishes single-session/worktree/same-dir style spawn modes, but the donor value is broader than a mode enum. It also expresses:

- a persistent multi-session seat server
- pre-created cwd session + on-demand isolated worktrees
- capacity-aware polling / at-capacity behavior
- worktree-aware resume and timeout/watchdog semantics

This is directionally useful, but CoPaw should represent it as:

- seat lease policy
- writer reservation
- workspace contention semantics
- seat/workspace projections

It should not be copied as a donor UI mode enum.

## 6. Explicit Non-Goals

The following `cc/cowork` patterns must **not** be copied into CoPaw mainline.

### 6.1 Separate settings namespace

Do not copy:

- `cowork_settings.json`
- `cowork_plugins`

Reason:

- this would create a second config/capability truth
- it conflicts with CoPaw's single formal object chain
- the real donor risk is broader than filenames: one hidden mode bit changes both plugin resolution and effective settings base
- plugin seed/cache layering is an operational storage detail, not a product-architecture donor target

### 6.2 File-backed memory and hidden runtime truth

Do not copy:

- `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE`
- `CLAUDE_COWORK_MEMORY_EXTRA_GUIDELINES`
- settings-backed `autoMemoryDirectory` override as formal continuity truth
- `MEMORY.md`
- `memory/YYYY-MM-DD.md`
- daily-log distillation and transcript-grep recovery as the formal continuity model
- any hidden env-var that directly changes formal runtime semantics

Reason:

- adapter/bootstrap toggles are acceptable
- formal memory scope, host continuity, and runtime behavior must not depend on hidden shell state
- CoPaw explicitly rejects file-backed memory as the canonical source
- repo root, worktree root, cwd, and thread aliases are not acceptable formal continuity keys

### 6.3 Hidden settings/plugins mode coupling

Do not copy any donor pattern where one hidden mode bit silently changes:

- plugin directory choice
- settings file choice
- effective settings merge base
- memory/runtime semantics

Reason:

- this recreates a second runtime truth without naming it as one
- it would let the same donor anti-pattern reappear under new filenames

### 6.4 Parallel chat or planner semantics

Do not copy any pattern that would make `cowork` become:

- a second chat system
- a second planner
- a second execution front door

CoPaw must continue to use one main chat/runtime chain.

## 7. Already Landed Alignment

The following donor-aligned items are already in motion in CoPaw.

### 7.1 Bridge registration plus formal runtime-center lifecycle surface

Landed into:

- `src/copaw/environments/health_service.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/lease_service.py`
- `src/copaw/app/routers/runtime_center_routes_ops.py`

Visible fields:

- `worker_type`
- `max_sessions`
- `spawn_mode`
- `reuse_environment_id`
- `bridge_work_id`
- `bridge_work_status`
- `bridge_heartbeat_at`
- `bridge_session_id`
- `workspace_trusted`
- `elevated_auth_state`

Visible operations:

- `ack`
- `heartbeat`
- `stop`
- `reconnect`
- `archive`
- `deregister`

This is the correct shape:

- donor semantics are visible
- no new store was created
- projection lands on `seat_runtime` and `host_companion_session`
- the formal CoPaw contract now exists on `EnvironmentService / SessionMount / EnvironmentMount`
- Runtime Center can now drive the lifecycle through one canonical surface instead of only reading projection metadata
- this is still not proof that an external bridge worker is emitting the full lifecycle end to end
- `stopWork` is now modeled as a distinct stopped-work state on the same session truth rather than being folded into archive/deregister

### 7.2 Accepted persistence boundary and truthful failure tail, not donor-grade durability yet

Landed into:

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/app/runtime_chat_stream_events.py`

Visible behavior:

- a formal pre-stream accepted checkpoint is recorded before the long-running stream body
- accepted persistence is written back into the runtime context
- `commit_failed` now emits explicit lifecycle tail state instead of silently dying
- `committed` is now suppressed when runtime context already knows writeback failed
- this is useful, but it is still weaker than the donor
- not yet landed:
  - donor-equivalent flush semantics before long execution and before final result handoff
  - `committed` as a strict proof of durable writeback completion across the whole chat pipeline

### 7.3 Hidden tail split and lifecycle visibility

Landed into:

- `console/src/pages/Chat/runtimeTransport.ts`
- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/index.tsx`
- `console/src/pages/Chat/ChatRuntimeSidebar.tsx`

Visible behavior:

- the visible chat stream ends when the actual reply ends
- hidden tail sidecar events continue in the background
- the page can still show:
  - `accepted`
  - `commit_started`
  - `confirm_required`
  - `committed`
  - `commit_failed`
- backend also emits `turn_reply_done`, but frontend does not yet model it as a first-class lifecycle state
- current alignment here is UI-tail visibility, not yet full donor-equivalent reply/commit truth

This is directly aligned with the donor idea that transcript acceptance and result commit are not the same phase.

### 7.4 Prompt-safe app/window labels on the read model

Landed into:

- `src/copaw/environments/health_service.py`

Visible behavior:

- raw adapter metadata can still keep original host-provided app/window strings
- prompt-facing runtime projections now sanitize app/window labels before they surface in:
  - `desktop_app_contract`
  - `cooperative_adapter_availability`
  - downstream host-twin/app-family projections that consume those fields

This is only a partial computer-use donor landing:

- read-model hardening is now present
- execution-time guardrails are still not yet present

## 8. Remaining Alignment Work

The next donor-aligned implementation steps should be:

1. complete the chat runtime contract
   - persist and flush accepted input before the long-running execution path
   - ensure the full commit lifecycle is canonical across backend and frontend
   - make `committed` mean durable writeback success rather than optimistic tail completion
   - expose `reply_done` as an explicit first-class phase
   - keep control-thread and work-context continuity explicit
2. strengthen host companion registration and reattach
   - expand typed session/seat registration semantics
   - complete external producer/runtime wiring for the landed `ack / heartbeat / stop / archive / deregister / reconnect` contract
   - make reuse/reattach legality explicit in the environment read model
   - map pointer-based continuity, workspace trust, and elevated-auth gating into the formal contract
3. harden transport reliability where remote session shape exists
   - echo dedup
   - stall-timer clearing on inbound activity
   - reconnect behavior for stalled remote sessions
4. harden computer-use contracts
   - operator abort
   - host exclusion
   - frontmost verification
   - clipboard round-trip verification
   - extend prompt-safe app/window exposure from read-model hardening into execution-time guardrails
5. formalize stable host-scoped memory continuity
   - do it through `work_context_id` and session/environment truth
   - explicitly reject file-backed memory donors and repo/worktree/cwd continuity heuristics
   - do not add donor-style hidden overrides or hidden settings/plugins mode coupling

## 9. Acceptance Criteria

This donor alignment is considered real only if the following are true:

1. the runtime can reattach to the same host/session truth without silently forking a second one
2. the runtime can carry lease/heartbeat/cleanup semantics on that same truth instead of only projecting registration metadata
3. chat durably records accepted input before long execution and does not claim `committed` until durable writeback really succeeds
4. chat can distinguish accepted work from reply completion from commit completion
5. Runtime Center and Agent Workbench consume the same host continuity truth
6. browser/desktop/document/watcher execution all remain first-class cooperative adapters on one formal chain, and execution-time guardrails are not left only as read models
7. no new `cowork` object store, config namespace, hidden runtime truth, file-backed memory truth, or repo/worktree heuristic continuity key has been introduced

## 10. Testing Direction

Targeted verification should continue to cover three areas.

### Environment and host projections

- `tests/environments/test_environment_registry.py`
- `tests/app/runtime_center_api_parts/detail_environment.py`

### Chat lifecycle and runtime stream behavior

- `tests/app/runtime_center_api_parts/overview_governance.py`
- `console/src/pages/Chat/runtimeTransport.test.ts`
- `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`

### Full host continuity and consumer alignment

- `tests/app/test_workflow_templates_api.py`
- `tests/fixed_sops/test_service.py`
- `tests/app/test_fixed_sop_kernel_api.py`
- `tests/app/test_cron_executor.py`
- `tests/app/test_phase_next_autonomy_smoke.py`

## 11. Final Stance

The right question is not:

> should CoPaw copy `cowork`?

The right question is:

> which `cc/cowork` runtime disciplines should be absorbed into CoPaw's existing single truth chain?

The answer is:

- yes to bridge/lease/reattach/workspace-trust semantics
- yes to durable accept/reply/commit lifecycle discipline
- yes to host-aware safety contracts
- yes to the stable continuity problem
- no to file-backed memory donor mechanics
- no to hidden settings/plugins mode coupling
- no to separate settings/plugins/runtime truth

That keeps CoPaw aligned with its own formal architecture while still learning from the strongest parts of the donor.
