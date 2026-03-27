# Single-Industry Autonomy Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining runtime gap so the single-industry main brain always routes operator execution requests to an existing seat, auto-creates a low-risk temporary seat when needed, escalates high-risk or long-term seat additions through governance, and exposes staffing and researcher state to both prompts and UI.

**Architecture:** Reuse the existing `IndustryInstance -> Backlog -> OperatingCycle -> Assignment -> AgentReport` chain and the existing seat lifecycle (`add-role / promote-role / retire-role`). Add one focused seat-gap policy module between chat writeback and backlog materialization, normalize its output into an `IndustryInstanceDetail` staffing read surface, then feed that surface into prompt context and the `Industry` / `Runtime Center` / `AgentWorkbench` pages.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite state repositories, React, TypeScript, Vitest, pytest

---

## Scope Guardrails

- Keep `execution-core` as the main brain only. It may plan, chat, assign, review, and supervise; it must not become the fallback leaf executor again.
- Reuse `system:update_industry_team`, `BacklogService`, `OperatingCycleService`, `AssignmentService`, and `AgentReportService`. Do not create a parallel seat-governance or planning path.
- Reuse the existing temporary-seat lifecycle and auto-retirement rules in `IndustryService`; extend them instead of duplicating them.
- Keep `researcher` as a persistent observation seat that reports into the main brain, not a second strategy center.
- Treat this as a closure pass, not a new architecture phase. Existing objects already exist; the missing work is runtime wiring and visibility.

## Existing Baseline To Reuse

- Chat writeback already materializes `strategy / backlog / schedule` into the formal chain.
- `IndustryRoleBlueprint` already supports `employment_mode`, `activation_mode`, and `reports_to`.
- `IndustryService.add_role_to_instance_team()`, `promote_role_in_instance_team()`, and `retire_role_from_instance_team()` already exist.
- `BacklogItemRecord`, `OperatingCycleRecord`, `AssignmentRecord`, and `AgentReportRecord` already exist and already appear in `IndustryInstanceDetail`.
- Workflow-driven `team_role_gap` recommendations and chat approval already exist; use them as the reference behavior for governed seat changes.
- Frontend already shows backlog, assignments, reports, and temporary-seat labels, but it does not yet surface staffing-gap intent or seat-proposal state clearly.

## File Map

### Backend seat-gap closure

- Create: `src/copaw/industry/seat_gap_policy.py`
  - Centralize operator-intake seat resolution so `service_lifecycle.py` stops embedding ad-hoc gap rules.
- Modify: `src/copaw/industry/service_lifecycle.py`
  - Call the seat-gap policy during chat writeback, materialize temporary seats when safe, and submit governed seat proposals when confirmation is required.
- Modify: `src/copaw/industry/service_strategy.py`
  - Build a normalized staffing read surface out of backlog, seats, assignments, reports, and decisions.
- Modify: `src/copaw/industry/service_runtime_views.py`
  - Reflect staffing state in `main_chain` summaries and current loop risk/owner hints.
- Modify: `src/copaw/industry/models.py`
  - Add the new staffing read surface to `IndustryInstanceDetail`.
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Inject staffing context into pure-chat / background-intake prompt context.
- Modify: `src/copaw/kernel/query_execution_prompt.py`
  - Make execution-time prompts explicit about active staffing gaps, temporary seats, and pending staffing approvals.
- Modify: `src/copaw/app/runtime_center/conversations.py`
  - Show the same staffing summary during kickoff/recovery prompts.

### Governance and seat lifecycle references

- Reference: `src/copaw/capabilities/system_team_handlers.py`
  - Existing `add-role / promote-role / retire-role` handling; extend only if the new proposal payload needs extra metadata or no-goal temporary-seat semantics.
- Reference: `src/copaw/predictions/service_recommendations.py`
  - Existing governed seat-gap behavior; use as the pattern for any new confirm-gated seat proposal wording or metadata.

### Frontend visibility

- Create: `console/src/runtime/staffingGapPresentation.ts`
  - Pure helper that converts raw `IndustryInstanceDetail.staffing` data into display labels/badges used across pages.
- Create: `console/src/runtime/staffingGapPresentation.test.ts`
  - Unit coverage for the display helper.
- Modify: `console/src/api/modules/industry.ts`
  - Add typed `staffing` payloads.
- Modify: `console/src/pages/Industry/index.tsx`
  - Add a staffing section that surfaces active gap, pending proposal, temporary seats, and researcher loop status.
- Modify: `console/src/pages/Industry/pageHelpers.tsx`
  - Add localized labels for the new staffing section.
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
  - Show seat origin/proposal status and better temporary-seat context for the currently selected execution seat.
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
  - Render staffing status in the detail drawer alongside the existing main-chain section.

### Tests and docs

- Create: `tests/industry/test_seat_gap_policy.py`
  - Unit tests for seat-gap resolution kinds and payload generation.
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
  - Integration tests for operator intake -> seat resolution -> backlog/cycle/assignment behavior.
- Modify: `tests/kernel/test_main_brain_chat_service.py`
  - Prompt/context regression coverage for staffing and researcher visibility.
- Modify: `TASK_STATUS.md`
  - Register the closure pass and its execution order after implementation.

### Task 1: Centralize Seat-Gap Resolution Rules

**Files:**
- Create: `src/copaw/industry/seat_gap_policy.py`
- Create: `tests/industry/test_seat_gap_policy.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/industry/test_seat_gap_policy.py`

- [ ] **Step 1: Write failing unit tests for seat-gap resolution kinds**

```python
def test_resolve_gap_prefers_existing_specialist() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="整理桌面文件并归档到工作目录",
        requested_surfaces=["file", "desktop"],
        matched_role=existing_role,
        team=team,
    )
    assert resolution.kind == "existing-role"
    assert resolution.target_role_id == existing_role.role_id


def test_resolve_gap_builds_auto_temporary_seat_for_low_risk_local_work() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="整理桌面下载区并分类到项目文件夹",
        requested_surfaces=["file", "desktop"],
        matched_role=None,
        team=team,
    )
    assert resolution.kind == "temporary-seat-auto"
    assert resolution.role is not None
    assert resolution.role.employment_mode == "temporary"


def test_resolve_gap_requires_governance_for_high_risk_or_long_term_addition() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="以后长期负责平台投放并直接下单执行",
        requested_surfaces=["browser"],
        matched_role=None,
        team=team,
    )
    assert resolution.kind in {"temporary-seat-proposal", "career-seat-proposal"}
    assert resolution.requires_confirmation is True
```

- [ ] **Step 2: Run the new unit tests to confirm they fail**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py -q`
Expected: FAIL because `seat_gap_policy.py` and `resolve_chat_writeback_seat_gap()` do not exist yet.

- [ ] **Step 3: Implement a focused seat-gap policy module**

```python
@dataclass(slots=True)
class SeatGapResolution:
    kind: Literal[
        "existing-role",
        "temporary-seat-auto",
        "temporary-seat-proposal",
        "career-seat-proposal",
        "routing-pending",
    ]
    role: IndustryRoleBlueprint | None = None
    requires_confirmation: bool = False
    reason: str = ""
    requested_surfaces: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Wire `apply_execution_chat_writeback()` to use the new resolution object**

```python
resolution = resolve_chat_writeback_seat_gap(
    message_text=plan.normalized_text,
    requested_surfaces=requested_surfaces,
    matched_role=target_role,
    team=team,
)
```

Implementation rules:

- Existing specialist match wins immediately.
- No specialist + low-risk local leaf work becomes `temporary-seat-auto`.
- No specialist + high-risk or long-term ask becomes a governed proposal.
- No specialist + no concrete surface stays `routing-pending`.
- Persist normalized metadata like `seat_resolution_kind`, `seat_resolution_reason`, and `seat_requested_surfaces` instead of only opaque strings.

- [ ] **Step 5: Re-run the unit tests**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py -q`
Expected: PASS

- [ ] **Step 6: Commit the isolated policy layer**

```bash
git add src/copaw/industry/seat_gap_policy.py src/copaw/industry/service_lifecycle.py tests/industry/test_seat_gap_policy.py
git commit -m "feat: centralize industry seat gap resolution"
```

### Task 2: Materialize Auto Temporary Seats And Governed Seat Proposals

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/capabilities/system_team_handlers.py`
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Add failing integration tests for operator intake closure**

```python
async def test_chat_writeback_auto_creates_temporary_seat_for_low_risk_gap(app) -> None:
    result = await app.state.industry_service.apply_execution_chat_writeback(
        industry_instance_id=instance_id,
        message_text="整理桌面下载文件并归档",
        owner_agent_id=EXECUTION_CORE_AGENT_ID,
        writeback_plan=plan,
    )
    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert any(agent["employment_mode"] == "temporary" for agent in detail.agents)
    assert all(item["owner_agent_id"] != EXECUTION_CORE_AGENT_ID for item in detail.assignments)


async def test_chat_writeback_creates_governed_seat_proposal_for_high_risk_gap(app) -> None:
    result = await app.state.industry_service.apply_execution_chat_writeback(
        industry_instance_id=instance_id,
        message_text="长期负责直接下单投放并执行高风险动作",
        owner_agent_id=EXECUTION_CORE_AGENT_ID,
        writeback_plan=plan,
    )
    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail.staffing["active_gap"]["requires_confirmation"] is True
    assert detail.staffing["active_gap"]["decision_request_id"]
    assert all(item["owner_agent_id"] != EXECUTION_CORE_AGENT_ID for item in detail.assignments)
```

- [ ] **Step 2: Run the integration tests to confirm the current chain still fails**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
Expected: FAIL because unmatched requests still stop at metadata-only gap markers and do not create seats or proposals.

- [ ] **Step 3: Auto-create low-risk temporary seats through the existing team lifecycle**

Implementation rules:

- Use `IndustryService.add_role_to_instance_team()` with `employment_mode="temporary"` and no default long-term goal.
- Refresh the instance/team before backlog writeback so the new seat can own the backlog item and the subsequent cycle.
- Preserve the existing temporary-seat auto-retirement behavior.

```python
if resolution.kind == "temporary-seat-auto":
    await self.add_role_to_instance_team(
        record.instance_id,
        role=resolution.role,
        goal=None,
        schedule=None,
        auto_activate=True,
        auto_dispatch=False,
        execute=False,
    )
```

- [ ] **Step 4: Submit high-risk or long-term seat additions as governed proposals**

Implementation rules:

- Build a `system:update_industry_team` payload from `resolution.role`.
- Use the existing confirm-gated governance path; do not add a second approval system.
- Store the resulting `decision_request_id`, `proposal_kind`, and `proposal_status` back into backlog/staffing metadata.

```python
proposal_payload = {
    "instance_id": record.instance_id,
    "operation": "add-role",
    "role": resolution.role.model_dump(mode="json"),
    "reason": f"chat-writeback:{plan.fingerprint}",
}
```

- [ ] **Step 5: Re-run the integration tests**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS

- [ ] **Step 6: Commit the materialization pass**

```bash
git add src/copaw/industry/service_lifecycle.py src/copaw/capabilities/system_team_handlers.py tests/app/industry_api_parts/runtime_updates.py
git commit -m "feat: close operator seat gap materialization"
```

### Task 3: Build A Staffing Read Surface And Inject It Into Prompts

**Files:**
- Modify: `src/copaw/industry/models.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Add failing prompt/read-model tests**

```python
def test_main_brain_chat_prompt_includes_staffing_gap_and_researcher_state(app) -> None:
    prompt = build_main_brain_prompt(...)
    assert "Staffing" in prompt
    assert "temporary seat" in prompt.lower()
    assert "researcher" in prompt.lower()
```

- [ ] **Step 2: Run the prompt regression test**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because no normalized staffing block is currently emitted.

- [ ] **Step 3: Add a normalized staffing surface to `IndustryInstanceDetail`**

Target shape:

```python
staffing = {
    "active_gap": {...} | None,
    "pending_proposals": [...],
    "temporary_seats": [...],
    "researcher": {...} | None,
}
```

Minimum contents:

- `active_gap`: resolution kind, requested surfaces, target role/proposal label, decision id, reason.
- `pending_proposals`: outstanding governed seat additions or promotions.
- `temporary_seats`: current temporary seats, origin backlog/proposal, auto-retire hint.
- `researcher`: current assignment, latest report, pending signals, and status.

- [ ] **Step 4: Reflect staffing state in `main_chain` and runtime summaries**

Implementation rules:

- Add a staffing-aware summary to `IndustryMainChainGraph` without creating a new truth source.
- If an active staffing gap exists, surface it in current owner/risk hints instead of burying it only in backlog metadata.
- If the researcher is the main observation loop, expose its latest report status in the read surface and kickoff summary.

- [ ] **Step 5: Inject staffing lines into main-brain and execution prompts**

Implementation rules:

- Pure chat prompt must know whether a gap is already covered by a temporary seat, still waiting for approval, or still unresolved.
- Execution prompt must keep telling the main brain not to personally execute when a gap exists.
- Kickoff/recovery prompt should mention pending staffing proposals and latest researcher state next to goal/backlog/assignment counts.

- [ ] **Step 6: Re-run the prompt regression test**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS

- [ ] **Step 7: Commit the read-surface and prompt pass**

```bash
git add src/copaw/industry/models.py src/copaw/industry/service_strategy.py src/copaw/industry/service_runtime_views.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/query_execution_prompt.py src/copaw/app/runtime_center/conversations.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: expose staffing state to industry prompts"
```

### Task 4: Surface Staffing State In Operator UI

**Files:**
- Create: `console/src/runtime/staffingGapPresentation.ts`
- Create: `console/src/runtime/staffingGapPresentation.test.ts`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/pageHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Test: `console/src/runtime/staffingGapPresentation.test.ts`

- [ ] **Step 1: Write a failing Vitest suite for the display helper**

```ts
it("formats an active governed staffing gap", () => {
  expect(presentStaffingGap(activeGap).badge).toContain("待确认");
});

it("formats temporary seats with auto-retire hints", () => {
  expect(presentTemporarySeat(tempSeat).description).toContain("自动退出");
});
```

- [ ] **Step 2: Run the Vitest suite and confirm failure**

Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: FAIL because the helper does not exist yet.

- [ ] **Step 3: Add typed staffing payloads and the shared presentation helper**

Implementation rules:

- Keep UI logic in the helper, not inline in three separate pages.
- Prefer consuming normalized `staffing` fields over reaching into raw backlog metadata everywhere.

- [ ] **Step 4: Add a staffing section to `/industry`**

UI requirements:

- Show the current active staffing gap or confirm there is none.
- Show pending seat proposals and their decision status.
- Show temporary seats and their lifecycle hint.
- Show researcher status: current assignment, latest report time, and whether signals are waiting for the main brain.

- [ ] **Step 5: Reuse the same helper in `AgentWorkbench` and `Runtime Center`**

UI requirements:

- `AgentWorkbench` should explain whether the current seat is permanent, temporary, pending promotion, or pending approval.
- `Runtime Center` detail drawer should show staffing state near the main-chain section instead of hiding it inside raw JSON.

- [ ] **Step 6: Re-run frontend verification**

Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: PASS

Run: `npm --prefix console run build`
Expected: build completes with exit code 0

- [ ] **Step 7: Commit the UI visibility pass**

```bash
git add console/src/runtime/staffingGapPresentation.ts console/src/runtime/staffingGapPresentation.test.ts console/src/api/modules/industry.ts console/src/pages/Industry/index.tsx console/src/pages/Industry/pageHelpers.tsx console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx console/src/pages/RuntimeCenter/viewHelpers.tsx
git commit -m "feat: surface staffing closure state in runtime ui"
```

### Task 5: Full Regression Pass And Documentation Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-03-23-single-industry-autonomy-carrier-design.md` (only if the final implementation changes the approved design wording)
- Test: `tests/industry/test_seat_gap_policy.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `console/src/runtime/staffingGapPresentation.test.ts`

- [ ] **Step 1: Re-read the accepted design and this plan**

Checklist:

- Main brain never personally executes leaf work.
- Low-risk temporary seat can be auto-created.
- High-risk temporary seat or long-term seat addition requires confirmation.
- Researcher remains a persistent observation seat.
- Runtime UI makes staffing state visible.

- [ ] **Step 2: Run the backend regression bundle**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: all tests pass

- [ ] **Step 3: Run the frontend regression bundle**

Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: all tests pass

Run: `npm --prefix console run build`
Expected: build completes with exit code 0

- [ ] **Step 4: Update `TASK_STATUS.md`**

Document:

- the new autonomy-closure pass,
- the new seat-gap policy,
- auto temporary-seat creation behavior,
- governed seat proposals,
- staffing/researcher visibility surfaces,
- and any follow-up deletion or hardening work left after this pass.

- [ ] **Step 5: Manual runtime smoke on the live industry instance**

Manual checks:

1. Send a low-risk local-work request such as “整理桌面下载文件并归档”.
2. Confirm a temporary seat appears and the assignment owner is not `execution-core`.
3. Send a high-risk or long-term execution request.
4. Confirm a governed seat proposal/decision appears and the main brain does not claim the work is already executing.
5. Confirm `/industry`, `Runtime Center`, and `AgentWorkbench` all show the same staffing state.

- [ ] **Step 6: Commit the final closure pass**

```bash
git add TASK_STATUS.md docs/superpowers/specs/2026-03-23-single-industry-autonomy-carrier-design.md
git commit -m "docs: register single-industry autonomy closure status"
```
