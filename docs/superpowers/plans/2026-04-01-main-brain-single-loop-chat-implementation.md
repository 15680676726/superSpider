# Main Brain Single-Loop Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild CoPaw chat into a cc-like single-loop main-brain experience with one chat window, one primary model turn for ordinary chat, cached prompt/snapshot context, and kernel-owned two-phase commit for formal side effects.

**Architecture:** Keep `POST /api/runtime-center/chat/run` as the only front door, shrink `turn_executor` to lightweight routing, move ordinary chat directly into `MainBrainChatService`, and express formal work as `reply + action_envelope` followed by kernel/governance two-phase commit. Frontend and backend must both adopt the same stream contract: reply tokens first, sidecar commit events second, all inside the same control thread with no second chat product.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, TypeScript, React, Vitest, existing runtime-center streaming/SSE transport

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-04-01-main-brain-single-loop-chat-design.md`
- Status: `TASK_STATUS.md`
- Architecture: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Data model: `DATA_MODEL_DRAFT.md`
- API map: `API_TRANSITION_MAP.md`

---

## Baseline

Backend baseline already verified in the isolated worktree:

- `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_chat_writeback.py -q`
- Result: `76 passed`

Frontend baseline still needs console dependency install inside the worktree before running Vitest.

## Parallel Ownership

These ownership boundaries are mandatory for the 6-agent rollout. One file gets one owner.

### Workstream 1: Frontend transport owner

- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/runtimeTransportRequest.ts`
- Modify: `console/src/pages/Chat/runtimeTransport.test.ts`

### Workstream 2: Runtime chat route and stream contract owner

- Create: `src/copaw/app/runtime_chat_stream_events.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`

### Workstream 3: Kernel routing and intake retirement owner

- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/query_execution_writeback.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/kernel/test_chat_writeback.py`

### Workstream 4: Main-brain turn-result, commit pipeline, and snapshot owner

- Create: `src/copaw/kernel/main_brain_turn_result.py`
- Create: `src/copaw/kernel/main_brain_commit_service.py`
- Create: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Create: `tests/kernel/test_main_brain_commit_service.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`

### Workstream 5: Single-window chat sidecar UI owner

- Create: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Create: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`
- Create: `console/src/pages/Chat/ChatCommitConfirmationCard.tsx`
- Create: `console/src/pages/Chat/ChatCommitConfirmationCard.test.tsx`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/index.tsx`

### Workstream 6: Snapshot invalidation, docs/status, and focused regression owner

- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/industry/chat_writeback.py`
- Modify: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/media/service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `tests/kernel/test_main_brain_orchestrator.py`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `tests/app/test_runtime_conversations_api.py`
- Modify: `tests/app/test_runtime_chat_media.py`
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`

---

### Task 1: Remove Frontend Pre-Send Model Blocking

**Files:**
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/runtimeTransportRequest.ts`
- Modify: `console/src/pages/Chat/runtimeTransport.test.ts`

- [ ] **Step 1: Write the failing frontend transport tests**

```ts
it("still posts chat/run when getActiveModels rejects", async () => {
  vi.spyOn(providerApi, "getActiveModels").mockRejectedValue(new Error("boom"));
  const transport = createRuntimeTransport(...);
  const response = await transport.fetch(runtimeFetchData);
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/runtime-center/chat/run"),
    expect.objectContaining({ method: "POST" }),
  );
  expect(response).toBeInstanceOf(Response);
});

it("does not inject blocking interaction-mode side logic into request building", () => {
  const request = buildRuntimeChatRequest(...);
  expect(request.interaction_mode).toBe("auto");
  expect(request.requested_actions).toBeUndefined();
});
```

- [ ] **Step 2: Run the targeted frontend tests**

Run: `cmd /c npm --prefix console test -- runtimeTransport.test.ts`
Expected: FAIL because transport still returns local model-error responses before the request starts.

- [ ] **Step 3: Implement the minimal transport change**

Rules:
- remove the blocking `providerApi.getActiveModels()` requirement from the send path
- keep runtime wait UI, but make it derive from request lifecycle / streamed server chunks instead of a pre-send gate
- keep request building canonical; `interaction_mode="auto"` remains the default payload unless an explicit action requests otherwise

- [ ] **Step 4: Re-run the targeted frontend tests**

Run: `cmd /c npm --prefix console test -- runtimeTransport.test.ts`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- console/src/pages/Chat/runtimeTransport.ts console/src/pages/Chat/runtimeTransportRequest.ts console/src/pages/Chat/runtimeTransport.test.ts`
Expected: only Workstream 1 files changed.

### Task 2: Lock the Runtime Chat Stream Contract

**Files:**
- Create: `src/copaw/app/runtime_chat_stream_events.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] **Step 1: Write the failing stream-contract tests**

```python
def test_runtime_chat_run_streams_reply_then_sidecar_commit_events(client, app) -> None:
    response = client.post("/api/runtime-center/chat/run", json=_payload(), stream=True)
    body = "".join(chunk.decode("utf-8") for chunk in response.iter_raw())
    assert "turn_reply_done" in body
    assert "commit_started" in body

def test_runtime_chat_run_keeps_commit_events_in_same_control_thread(client, app) -> None:
    response = client.post("/api/runtime-center/chat/run", json=_payload(), stream=True)
    assert response.headers["content-type"].startswith("text/event-stream")
```

- [ ] **Step 2: Run the targeted backend API tests**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q -k "chat_run_streams_reply_then_sidecar_commit_events or keeps_commit_events_in_same_control_thread"`
Expected: FAIL because no canonical sidecar events exist yet.

- [ ] **Step 3: Implement the router-side event contract**

Rules:
- add one canonical stream-event encoder/normalizer module
- keep `chat/run` as the only route
- express sidecar events as the same SSE response stream after reply completion
- do not introduce a second transport, second polling route, or second chat thread

- [ ] **Step 4: Re-run the targeted backend API tests**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q -k "chat_run_streams_reply_then_sidecar_commit_events or keeps_commit_events_in_same_control_thread"`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- src/copaw/app/runtime_chat_stream_events.py src/copaw/app/routers/runtime_center_routes_core.py tests/app/runtime_center_api_parts/overview_governance.py`
Expected: only Workstream 2 files changed.

### Task 3: Retire Ordinary-Chat Intake Model Decisions

**Files:**
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/query_execution_writeback.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/kernel/test_chat_writeback.py`

- [ ] **Step 1: Write the failing kernel routing tests**

```python
@pytest.mark.asyncio
async def test_auto_mode_routes_plain_chat_without_writeback_model_decision() -> None:
    ...
    assert resolved_mode == "chat"
    assert writeback_model_decision_calls == []

@pytest.mark.asyncio
async def test_auto_mode_routes_to_orchestrate_only_for_explicit_actions() -> None:
    ...
    assert resolved_mode == "orchestrate"
```

- [ ] **Step 2: Run the targeted kernel tests**

Run: `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_chat_writeback.py -q`
Expected: FAIL because ordinary chat still consults intake/writeback model logic.

- [ ] **Step 3: Implement the routing simplification**

Rules:
- ordinary chat must not call `resolve_chat_writeback_model_decision(...)`
- `turn_executor` may still route `orchestrate` for explicit `requested_actions`, forced execution entry, active confirmation, or resume/human-assist continuity
- if ordinary text is ambiguous, stay in chat and let the main brain ask clarifying follow-up instead of pre-routing to execution

- [ ] **Step 4: Re-run the targeted kernel tests**

Run: `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_chat_writeback.py -q`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- src/copaw/kernel/turn_executor.py src/copaw/kernel/main_brain_intake.py src/copaw/kernel/query_execution_writeback.py tests/kernel/test_turn_executor.py tests/kernel/test_chat_writeback.py`
Expected: only Workstream 3 files changed.

### Task 4: Add Main-Brain Turn Result, Commit Pipeline, and Scope Snapshot

**Files:**
- Create: `src/copaw/kernel/main_brain_turn_result.py`
- Create: `src/copaw/kernel/main_brain_commit_service.py`
- Create: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Create: `tests/kernel/test_main_brain_commit_service.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write the failing turn-result, commit, and snapshot tests**

```python
def test_main_brain_chat_service_returns_reply_and_action_envelope() -> None:
    result = service._build_turn_result_for_test(...)
    assert result.action_envelope.kind in {"reply_only", "suggest_action", "commit_action"}

def test_main_brain_commit_service_rejects_invalid_commit_payload_without_mutating_state() -> None:
    result = service.commit(result_with_missing_payload)
    assert result.outcome == "payload_invalid"

def test_main_brain_commit_service_persists_control_thread_commit_state_for_reload() -> None:
    result = service.commit(result_requiring_confirm)
    snapshot = session_backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-ops:execution-core",
        user_id="ops-user",
        allow_not_exist=False,
    )
    assert snapshot["main_brain_commit"]["status"] == "confirm_required"

def test_main_brain_commit_service_deduplicates_same_commit_key() -> None:
    first = service.commit(valid_result)
    second = service.commit(valid_result)
    assert first.outcome == "committed"
    assert second.outcome == "idempotent_replay"

def test_main_brain_chat_service_reuses_scope_snapshot_for_same_work_context() -> None:
    ...
    assert snapshot_service.calls == ["work-context-1"]

def test_runtime_bootstrap_registers_main_brain_scope_snapshot_service(app_state) -> None:
    assert app_state.main_brain_scope_snapshot_service is not None
```

- [ ] **Step 2: Run the targeted snapshot tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_commit_service.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: FAIL because no turn-result/commit service or dedicated snapshot service is wired yet.

- [ ] **Step 3: Implement the turn-result, commit, snapshot, and cache path**

Rules:
- create one formal `MainBrainTurnResult` / `action_envelope` contract
- create one kernel-owned commit service for phase-2 validation, risk/environment checks, failure semantics, and idempotency
- create one dedicated service to materialize the derived scope snapshot
- `MainBrainChatService` should consume the service, not rebuild profile/latest/history/lexical sections ad hoc on every turn
- stable prompt prefix caching must key off session/user/stable signature
- snapshot refresh API must support explicit dirty marking from writer-side flows, not rebuild every turn
- phase-2 commit must persist normalized same-thread status into the current control-thread/session snapshot so reconnect, refresh, and background completion can reload `confirm_required / committed / commit_failed / governance_denied / commit_deferred` without the SSE still being open
- the persisted commit state is canonical reload state for the same conversation record; the stream sidecar is only the live transport for that same state

- [ ] **Step 4: Re-run the targeted turn-result and snapshot tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_commit_service.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- src/copaw/kernel/main_brain_turn_result.py src/copaw/kernel/main_brain_commit_service.py src/copaw/kernel/main_brain_scope_snapshot_service.py src/copaw/kernel/main_brain_chat_service.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_service_graph.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_commit_service.py tests/app/test_runtime_bootstrap_split.py`
Expected: only Workstream 4 files changed.

### Task 5: Render Sidecar Commit Events and Confirm Flow in the Single Chat Window

**Files:**
- Create: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Create: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`
- Create: `console/src/pages/Chat/ChatCommitConfirmationCard.tsx`
- Create: `console/src/pages/Chat/ChatCommitConfirmationCard.test.tsx`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/index.tsx`

- [ ] **Step 1: Write the failing sidecar UI tests**

```ts
it("reduces commit_started and commit_failed into current-thread status cards", () => {
  const state = reduceRuntimeSidecarEvent(initialState, {
    event: "commit_failed",
    payload: { reason: "payload_invalid" },
  });
  expect(state.currentCommitStatus?.kind).toBe("failed");
});

it("never navigates to a second chat thread for commit events", async () => {
  ...
  expect(navigateMock).not.toHaveBeenCalledWith(
    expect.stringContaining("task-chat:")
  );
});

it("renders confirm_required in the same chat window and exposes approve/reject actions", () => {
  ...
  expect(screen.getByText("待确认")).toBeTruthy();
  expect(screen.getByRole("button", { name: "批准" })).toBeTruthy();
});
```

- [ ] **Step 2: Run the targeted frontend UI tests**

Run: `cmd /c npm --prefix console test -- runtimeSidecarEvents.test.ts ChatCommitConfirmationCard.test.tsx`
Expected: FAIL because no sidecar reducer/render path exists yet.

- [ ] **Step 3: Implement the single-window sidecar handling**

Rules:
- parse sidecar events from the existing response parser path
- store them in current-thread state
- render status cards / timelines inside the same chat screen
- render `confirm_required`, `committed`, `governance_denied`, and `environment_unavailable` as same-window states
- provide a real same-window confirmation path, not just a passive badge
- never navigate to or materialize a second chat product

- [ ] **Step 4: Re-run the targeted frontend UI tests**

Run: `cmd /c npm --prefix console test -- runtimeSidecarEvents.test.ts ChatCommitConfirmationCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- console/src/pages/Chat/runtimeSidecarEvents.ts console/src/pages/Chat/runtimeSidecarEvents.test.ts console/src/pages/Chat/ChatCommitConfirmationCard.tsx console/src/pages/Chat/ChatCommitConfirmationCard.test.tsx console/src/pages/Chat/useChatRuntimeState.ts console/src/pages/Chat/index.tsx`
Expected: only Workstream 5 files changed.

### Task 6: Wire Snapshot Dirty Marking, Sync Canonical Docs, and Lock Focused Regressions

**Files:**
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/industry/chat_writeback.py`
- Modify: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/media/service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `tests/kernel/test_main_brain_orchestrator.py`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `tests/app/test_runtime_conversations_api.py`
- Modify: `tests/app/test_runtime_chat_media.py`
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`

- [ ] **Step 1: Write the failing invalidation and regression assertions**

```python
def test_main_brain_orchestrator_result_committer_marks_scope_snapshot_dirty_for_recovery_context(...) -> None:
    ...
    assert snapshot_dirty_calls == ["work-context-1"]

def test_chat_writeback_marks_scope_snapshot_dirty_after_operating_truth_write(...) -> None:
    ...
    assert snapshot_dirty_calls == ["industry-1"]

def test_runtime_chat_media_adopt_marks_scope_snapshot_dirty_for_work_context(...) -> None:
    ...
    assert snapshot_dirty_calls == [("work_context", "ctx-media-ops")]

def test_runtime_chat_media_retain_marks_scope_snapshot_dirty_for_work_context(...) -> None:
    ...
    assert snapshot_dirty_calls == [("work_context", "ctx-media-ops")]

def test_runtime_chat_media_keeps_single_window_chat_run_path(...) -> None:
    ...
    assert "/api/runtime-center/chat/run" in observed_path
    assert "task-chat:" not in observed_thread_type

def test_runtime_conversation_contract_marks_commit_status_on_same_thread(...) -> None:
    ...
    assert payload["thread_kind"] == "control"
    assert payload["meta"]["main_brain_commit"]["status"] == "confirm_required"

def test_runtime_chat_confirm_flow_stays_on_same_control_thread_after_approve_or_reject(...) -> None:
    ...
    assert confirm_payload["meta"]["main_brain_commit"]["status"] == "confirm_required"
    assert approved_payload["meta"]["main_brain_commit"]["status"] in {"committed", "governance_denied"}
    assert approved_payload["id"] == "industry-chat:industry-v1-ops:execution-core"
```

- [ ] **Step 2: Run the focused regression tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_media.py tests/app/test_runtime_canonical_flow_e2e.py -q`
Expected: FAIL until dirty marking, single-window behavior, and docs are aligned.

- [ ] **Step 3: Implement dirty marking hooks and update docs/regressions**

Rules:
- chat writeback, report-closure, media adopt, and media retain paths must mark the same resolved chat scope dirty, preferring `work_context_id`, otherwise falling back to `industry_instance_id`, consistent with `MainBrainChatService` scope resolution
- runtime conversation detail must merge persisted `main_brain_commit` status from the current control-thread/session snapshot so refresh/reconnect keeps the same-window sidecar state after the SSE has ended
- `TASK_STATUS.md` must describe `chat/run` as the only chat front door
- `API_TRANSITION_MAP.md` must describe commit results as same-thread sidecar flow
- `DATA_MODEL_DRAFT.md` must not imply a second chat object for task threads

- [ ] **Step 4: Re-run the focused regression tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_media.py tests/app/test_runtime_canonical_flow_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat -- src/copaw/app/runtime_center/conversations.py src/copaw/industry/chat_writeback.py src/copaw/industry/service_report_closure.py src/copaw/industry/service_lifecycle.py src/copaw/media/service.py src/copaw/memory/retain_service.py tests/kernel/test_main_brain_orchestrator.py TASK_STATUS.md API_TRANSITION_MAP.md DATA_MODEL_DRAFT.md tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_media.py tests/app/test_runtime_canonical_flow_e2e.py`
Expected: only Workstream 6 files changed.

## Final Integration Sequence

After the six workstreams land:

1. install console dependencies in the worktree if missing
   - `cmd /c npm --prefix console install`
2. run targeted frontend tests:
   - `cmd /c npm --prefix console test -- runtimeTransport.test.ts runtimeSidecarEvents.test.ts ChatCommitConfirmationCard.test.tsx`
3. run targeted backend tests:
   - `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_commit_service.py tests/kernel/test_chat_writeback.py tests/kernel/test_main_brain_orchestrator.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_media.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_runtime_bootstrap_split.py -q`
4. run one focused console build:
   - `cmd /c npm --prefix console run build`
5. run one focused app import / bootstrap smoke if needed:
   - `python -c "import main; print('import_main_ok')"`

## Execution Mode Chosen

The user already selected subagent-heavy execution and explicitly requested 6 agents for this upgrade.

Use:

- 6 agent dispatches with the ownership boundaries above
- no shared write files between agents
- controller integration and verification after all six slices return
