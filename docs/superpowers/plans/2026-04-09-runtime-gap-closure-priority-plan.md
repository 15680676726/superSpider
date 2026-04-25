# Runtime Gap Closure Priority Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the confirmed runtime-chain gaps that make CoPaw feel like chat-plus-recording while preserving the real architecture boundary: main brain handles intake, planning, delegation, governance, and return flow; execution remains on `assignment -> specialist -> task -> report`.

**Architecture:** Do not turn the main brain into a leaf executor. Fix the front-door rule, durable state progression, and cross-surface visibility so concrete operator instructions either become same-turn delegated work or are clearly shown as deferred/pending/guarded. Keep long-term autonomy, backlog, cycle, and specialist execution intact.

**Tech Stack:** FastAPI, Python domain services, Runtime Center read models, React/TypeScript console, pytest, vitest

---

## Scope Lock

This plan only targets the audited runtime-gap set currently recorded in:

- [2026-04-09-p0-runtime-gap-audit-ledger.md](/D:/word/copaw/docs/superpowers/specs/2026-04-09-p0-runtime-gap-audit-ledger.md)
- [2026-04-09-execution-chat-front-door-dispatch-gap-spec.md](/D:/word/copaw/docs/superpowers/specs/2026-04-09-execution-chat-front-door-dispatch-gap-spec.md)

Hard rules for every task below:

- Main brain remains:
  - chat intake
  - task understanding / planning
  - delegation / orchestration
  - risk governance
  - return-flow summarization
- Execution remains on:
  - `assignment`
  - `specialist / execution seat`
  - `task`
  - `environment / capability`
  - `report / evidence`
- Do not collapse long-term autonomy into a naive round-based “you say one line, it directly does one tool action” loop.
- Do not introduce a new parallel truth source.

## Priority Order

### Must-fix first

- `P0-001`
- `P0-002`
- `P0-003`
- `P0-005`
- `P0-009`
- `P0-011`
- `P0-012`

### Fix after front-door closure

- `P0-004`
- `P0-010`
- `P0-013`
- `P0-014`
- `P0-015`
- `P0-017`
- `P0-018`
- `P0-019`
- `P0-020`
- `P0-021`

### Reproduce before modifying

- `P0-006`
- `P0-007`
- `P0-008`
- `P0-016`

---

### Task 1: Lock the front-door delegation contract

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_chat_stream_events.py`
- Test: `tests/app/test_runtime_canonical_flow_e2e.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/industry/test_service_lifecycle*.py`

- [ ] **Step 1: Write failing tests for immediate-execution front-door behavior**

Cover:
- concrete execution-core instruction with no existing pending assignment
- expected result: same-turn durable state distinguishes:
  - recorded only
  - materialized
  - dispatched
  - blocked / waiting-confirm

- [ ] **Step 2: Run the targeted tests to capture current failure**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/industry -k "execution_chat or kickoff_execution_from_chat or operating_cycle" -q`

- [ ] **Step 3: Implement the smallest possible rule change**

Rules:
- if instruction is concrete and execution-ready, front door must materialize assignment truth in the same turn
- dispatch in the same turn only when risk and environment rules allow
- if same-turn dispatch cannot happen, durable state must explicitly show deferred/pending instead of relying on prompt wording

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/industry -k "execution_chat or kickoff_execution_from_chat or operating_cycle" -q`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: close execution front-door delegation gap"`

### Task 2: Add dedicated writeback/materialization evidence

**Files:**
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `src/copaw/kernel/dispatcher.py`
- Test: `tests/state/test_main_brain_service.py`
- Test: `tests/evidence/test_ledger*.py`

- [ ] **Step 1: Write failing evidence-chain tests**

Cover:
- chat writeback acceptance
- assignment materialization
- dispatch start

- [ ] **Step 2: Run the failing tests**

Run: `python -m pytest tests/state tests/evidence -k "chat_writeback or materialization or dispatch" -q`

- [ ] **Step 3: Implement dedicated evidence types**

Rules:
- keep outer kernel completion evidence
- add purpose-built evidence for formal object creation / materialization transitions
- do not invent a second evidence store

- [ ] **Step 4: Re-run evidence tests**

Run: `python -m pytest tests/state tests/evidence -k "chat_writeback or materialization or dispatch" -q`

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat: add dedicated front-door and materialization evidence"`

### Task 3: Fix deferred / pending state visibility across Chat, Runtime Center, and Industry

**Files:**
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Modify: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Modify: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/actorPulse.ts`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Test: `console/src/pages/Chat/*.test.ts*`
- Test: `console/src/pages/Industry/*.test.ts*`
- Test: `console/src/pages/RuntimeCenter/*.test.ts*`

- [ ] **Step 1: Write failing UI/read-model tests for deferred states**

Cover:
- `commit_deferred`
- `dispatch_deferred`
- “recorded but pending staffing/routing”
- refresh after thread switch

- [ ] **Step 2: Run the failing tests**

Run: `cd console; npm exec vitest run src/pages/Chat src/pages/Industry src/pages/RuntimeCenter --pool threads`

- [ ] **Step 3: Implement one canonical visible state vocabulary**

Required states:
- 已记录
- 已生成任务
- 已派发
- 执行中
- 待确认
- 待调度 / 待补位 / deferred

- [ ] **Step 4: Re-run frontend tests and build**

Run:
- `cd console; npm exec vitest run src/pages/Chat src/pages/Industry src/pages/RuntimeCenter --pool threads`
- `cd console; npm run build`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: unify deferred runtime states across surfaces"`

### Task 4: Keep human-assist continuity visible after acceptance

**Files:**
- Modify: `src/copaw/state/human_assist_task_service.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `console/src/pages/Chat/ChatHumanAssistPanel.tsx`
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`
- Test: `console/src/pages/Chat/*.test.ts*`

- [ ] **Step 1: Write failing continuity tests**

Cover:
- accepted -> `resume_queued`
- current-task surface still shows “恢复中” instead of disappearing

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/state/test_human_assist_task_service.py tests/app/test_runtime_human_assist_tasks_api.py -q`

- [ ] **Step 3: Implement a durable visible resume state**

Rules:
- do not break the existing resume machinery
- only fix the visibility contract

- [ ] **Step 4: Re-run backend and frontend tests**

Run:
- `python -m pytest tests/state/test_human_assist_task_service.py tests/app/test_runtime_human_assist_tasks_api.py -q`
- `cd console; npm exec vitest run src/pages/Chat --pool threads`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: preserve human-assist continuity during resume"`

### Task 5: Correct false-empty and false-active Runtime Center read models

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/app/runtime_center/task_detail_projection.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeEnvironmentSections.tsx`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/app/test_runtime_center_api.py`
- Test: `console/src/pages/Industry/*.test.ts*`
- Test: `console/src/pages/RuntimeCenter/*.test.ts*`

- [ ] **Step 1: Write failing tests for false-empty and false-active cases**

Cover:
- unwired service returns explicit unavailable/degraded signal, not empty idle surface
- paused schedules do not imply active automation
- empty assignment/backlog/report subchains do not inherit healthy top-level active
- environment without backing truth does not default to “已就绪”

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`

- [ ] **Step 3: Implement tighter read-model semantics**

Rules:
- missing wire != empty truth
- top-level healthy carrier != active subchain
- no environment proof != ready

- [ ] **Step 4: Re-run backend + frontend verification**

Run:
- `python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`
- `cd console; npm exec vitest run src/pages/Industry src/pages/RuntimeCenter --pool threads`
- `cd console; npm run build`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: tighten runtime read-model truth semantics"`

### Task 6: Make capability install truth explicit: inventory vs seat attachment vs external-job result

**Files:**
- Modify: `console/src/api/modules/capabilityMarket.ts`
- Modify: `console/src/pages/CapabilityMarket/index.tsx`
- Modify: `console/src/pages/CapabilityMarket/useCapabilityMarketState.ts`
- Modify: `src/copaw/app/routers/capability_market.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `console/src/pages/CapabilityMarket/*.test.ts*`

- [ ] **Step 1: Write failing tests for install truth**

Cover:
- inventory-only install
- install with target attachment
- project-package async accepted vs completed

- [ ] **Step 2: Run targeted tests**

Run:
- `python -m pytest tests/app/test_capability_market_api.py -q`
- `cd console; npm exec vitest run src/pages/CapabilityMarket --pool threads`

- [ ] **Step 3: Implement explicit market outcomes**

Required distinctions:
- 已加入库存
- 已挂到执行位
- 项目包安装中
- 项目包安装失败
- 项目包已完成并通过正式 probe/trial

- [ ] **Step 4: Re-run tests and build**

Run:
- `python -m pytest tests/app/test_capability_market_api.py -q`
- `cd console; npm exec vitest run src/pages/CapabilityMarket --pool threads`
- `cd console; npm run build`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: distinguish inventory, attachment, and external job results"`

### Task 7: Harden learning truth: real trials, patch evidence attachment, scoped workbench feeds

**Files:**
- Modify: `src/copaw/learning/acquisition_runtime.py`
- Modify: `src/copaw/learning/runtime_core.py`
- Modify: `src/copaw/learning/patch_runtime.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Modify: `console/src/pages/AgentWorkbench/AgentReports.tsx`
- Modify: `console/src/pages/AgentWorkbench/index.tsx`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`
- Test: `console/src/pages/AgentWorkbench/*.test.ts*`

- [ ] **Step 1: Write failing tests for learning truth mismatches**

Cover:
- skill trial cannot pass on `describe` alone when real execution proof is required
- patch approval/apply/rollback evidence is visible from patch detail
- selected agent workbench does not show global growth feed

- [ ] **Step 2: Run targeted tests**

Run:
- `python -m pytest tests/app/test_learning_api.py tests/app/runtime_center_api_parts/detail_environment.py -q`
- `cd console; npm exec vitest run src/pages/AgentWorkbench --pool threads`

- [ ] **Step 3: Implement the minimal learning/read-model fixes**

Rules:
- do not fake trial success from metadata-only responses
- attach emitted patch lifecycle evidence back to patch truth
- scope agent workbench learning feeds by selected agent when the page is in agent-specific mode

- [ ] **Step 4: Re-run tests and build**

Run:
- `python -m pytest tests/app/test_learning_api.py tests/app/runtime_center_api_parts/detail_environment.py -q`
- `cd console; npm exec vitest run src/pages/AgentWorkbench --pool threads`
- `cd console; npm run build`

- [ ] **Step 5: Commit**

Commit: `git commit -m "fix: harden learning trial and patch truth surfaces"`

### Task 8: Reproduce seam issues before deciding whether to patch them

**Files:**
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `tests/kernel/test_buddy_execution_carrier.py`
- Modify: `tests/app/test_startup_recovery.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Optional modify after proof: relevant source files for `P0-006/P0-007/P0-008/P0-016`

- [ ] **Step 1: Write explicit reproduction tests for each probable issue**

Cover:
- split durable commit path user-visible divergence
- canonical thread continuity collapse
- symbolic `environment_ref` raised as continuity proof
- startup recovery deriving live capability intent from legacy allowlists

- [ ] **Step 2: Run only the reproduction tests**

Run: `python -m pytest tests/kernel tests/app -k "commit_path or execution_carrier or environment_ref or startup_recovery" -q`

- [ ] **Step 3: Decide which seams graduate to confirmed**

Rules:
- if reproduced: move to confirmed and create a dedicated fix task
- if not reproduced: keep as seam, do not patch speculatively

- [ ] **Step 4: Commit reproduction coverage**

Commit: `git commit -m "test: reproduce remaining runtime seam issues"`

**Current outcome note (`2026-04-10`):**
- `P0-006` reproduced and fixed in the conversation reload path
- `P0-008` reproduced and fixed in continuity gating
- `P0-016` reproduced and fixed in startup-recovery capability projection
- `P0-007` reproduced and fixed in the buddy carrier handoff path
  - legacy binding backfill could preserve an explicit historical
    `control_thread_id` while the carrier handoff re-derived a canonical thread
    from `instance_id`
  - fix: preserve explicit continuity ids and only derive canonical thread ids
    when `control_thread_id` is missing

---

## Recommended Execution Order

1. Task 1
2. Task 3
3. Task 4
4. Task 2
5. Task 5
6. Task 6
7. Task 7
8. Task 8

This order preserves the main architecture:

- front door first
- visible state second
- evidence third
- read-model cleanup fourth
- market/learning truth after the main runtime path is stable
- seam reproduction last, before any speculative refactor

## Safety Checklist

Before changing any file in Tasks 1-7, explicitly verify:

- the main brain is still not the leaf executor
- assignment creation still feeds specialist/task/report, not direct main-brain tool execution
- backlog/cycle remains the long-run planning plane
- no new parallel truth source was introduced
- every new state is visible on at least one formal surface and traceable in tests

## Verification Gate

Do not claim closure until all of these pass:

- backend targeted pytest for modified chains
- frontend targeted vitest for modified surfaces
- `cd console; npm run build`
- one canonical operator flow replay:
  - operator gives concrete execution instruction
  - main brain accepts
  - assignment is either materialized and dispatched in-turn, or visibly deferred with durable state
  - execution seat/report/evidence surfaces agree on the same truth

---

Subagent review was intentionally skipped here because this session did not have fresh user authorization for new delegation; use the required review loop before execution if delegation is re-enabled.
