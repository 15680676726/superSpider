# Closure Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-confidence truth gaps confirmed in `docs/archive/root-legacy/46问题文档.md` without adding new parallel truth sources.

**Architecture:** Fix the closure gaps from the write path inward: first harden `HumanAssistTask` verification semantics, then remove active legacy `goal/schedule` writebacks from industry runtime, then eliminate read-side truth fabrication and governance bypasses, and finally align API/frontend/doc surfaces to the corrected contracts. Each task owns a disjoint write set.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state repositories, Vitest, pytest

## `2026-04-06` Status Snapshot

- `Task 1`: complete
  - `HumanAssistTask` 验收模式、`verification_evidence_refs` 持久化、以及 evidence-ledger 失败回退已落地并重新通过状态/API 回归。
- `Task 2`: partial
  - public bootstrap 不再把 `auto_activate` 扩成 legacy goal dispatch，chat writeback 也不再扩张 `schedule_ids` truth；但 kickoff / auto-resume 与 `goal_ids / schedule_ids / active_goal_ids` 长期收口仍未完成。
- `Task 3`: complete
  - runtime focus writeback 已收成 assignment focus；read-side 不再因为 selected assignment/backlog 伪造 `execution.current_focus_*`。
- `Task 4`: partial
  - acquisition approve/reject route regressions 已修；runtime-center 与 learning review-gate 现在都已 dispatcher-first，runtime-center actor route fallback 已删除；但 producer/kernel-task 一体化仍未完成，learning runtime 内部 compatibility fallback 仍存在。
- `Task 5`: partial
  - backend query boundary 已收成只接受 canonical `assignment/backlog` focus；前端本轮补齐了 Runtime Center surface-only contract 的陈旧测试；另外 `/runtime-center/external-runtimes/actions` 已切回 `kernel dispatcher submit -> execute_task` 并继承 mount risk，但更大范围的本地 truth derivation 与 capability front-door 绕路清理尚未完成。
- `Task 6`: complete for this remediation round
  - `docs/archive/root-legacy/46问题文档.md`、`TASK_STATUS.md`、本计划文档已按本轮真实验证结果纠偏；更大范围的历史文档真实性治理仍需后续持续处理。
- `Final Verification`: complete for the current remediation scope
  - backend 回归矩阵已重新执行，`bootstrap_lifecycle.py` 本轮全量 `38 passed`，industry kickoff focused slice `7 passed`，external runtime route focused regression `4 passed`；前端 targeted Vitest `19 passed`，`console build` 通过。

---

### Task 1: Harden HumanAssist Verification Semantics

**Files:**
- Modify: `src/copaw/state/human_assist_task_service.py`
- Modify: `src/copaw/state/models_core.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`

- [ ] Add failing tests for `evidence_verified` and `state_change_verified` so plain text cannot pass without the required evidence/state contract.
- [ ] Add a failing test that `verification_evidence_refs` persists accepted verification evidence.
- [ ] Implement acceptance-mode branching in `HumanAssistTaskService.verify_task(...)`.
- [ ] Implement persistence of `verification_evidence_refs` and mode-specific verification payload.
- [ ] Decide and encode evidence-ledger failure semantics explicitly; do not silently downgrade without state evidence.
- [ ] Run focused tests for state and API human-assist coverage.

### Task 2: Remove Legacy Goal Dispatch From Industry Bootstrap/Kickoff

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/state/models_industry.py`
- Modify: `src/copaw/state/models_reporting.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] Add failing tests that bootstrap/kickoff do not require `goal/schedule` dispatch to activate an instance.
- [ ] Add failing tests that no new `goal_ids/schedule_ids` truth is written during bootstrap/kickoff.
- [ ] Refactor public activation flags so `auto_activate` no longer implies legacy goal dispatch.
- [ ] Route kickoff/auto-resume through backlog/cycle/assignment-native execution.
- [ ] Remove or neutralize persistent `goal_ids/schedule_ids` / `active_goal_ids` write paths that act as live truth.
- [ ] Run focused industry bootstrap/lifecycle smoke tests.

### Task 3: Remove Goal-Based Runtime Focus Writeback And Read-Side Fabrication

**Files:**
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] Add failing tests that runtime focus is not written as `goal` when assignment/task truth exists.
- [ ] Add failing tests that read models do not fabricate `current_focus_*` from selected assignment/backlog when execution truth is empty.
- [x] Remove `goal_id/goal_title -> current_focus_kind="goal"` runtime sync behavior.
- [ ] Remove read-side fallback that invents `execution.current_focus_*`.
- [x] Run focused runtime-view and industry runtime tests.

### Task 4: Unify DecisionRequest / Acquisition Governance Paths

**Files:**
- Modify: `src/copaw/kernel/persistence.py`
- Modify: `src/copaw/learning/runtime_core.py`
- Modify: `src/copaw/learning/acquisition_runtime.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] Add failing tests that acquisition approval/reject flows use the canonical decision path rather than learning-specific special cases.
- [ ] Refactor learning/acquisition producers to stop constructing free-form `DecisionRequestRecord` bypasses where the kernel seam should own them.
- [ ] Remove Runtime Center actor-route special handling that bypasses canonical review flow for acquisition approvals.
- [ ] Run focused decision/governance API tests.

### Task 5: Remove API/Frontend Focus Truth Patching And Local Runtime Truth Derivation

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_industry.py`
- Modify: `src/copaw/industry/view_service.py`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/industryPagePresentation.ts`
- Modify: `console/src/pages/AgentWorkbench/useAgentWorkbench.ts`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Modify: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/Chat/sessionApi/index.test.ts`

- [ ] Add failing tests that `/runtime-center/industry/{id}` does not inject nonexistent `focus_selection`.
- [ ] Move any supported focus-selection truth into canonical view building or reject unsupported focus inputs.
- [ ] Remove frontend local derivations that select current focus/environment/owner when canonical payload already defines them.
- [ ] Keep frontend as a consumer of canonical projections, not a second truth producer.
- [ ] Run focused backend and frontend tests plus console build.

### Task 6: Reconcile Docs And Verification Claims

**Files:**
- Modify: `docs/archive/root-legacy/46问题文档.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

- [ ] Update docs so “已验证/已闭环” statements distinguish live e2e, focused harness contract, and code-baseline completion.
- [ ] Remove stale canonical-vocabulary conflicts where current truth and target-state terms are mixed.
- [ ] Document deletion criteria for any remaining compatibility seams left after Tasks 1-5.
- [ ] Re-run the verification matrix referenced by the updated claims and record actual results.

### Final Verification

**Files:**
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/industry/test_runtime_views_split.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`
- Test: `tests/app/test_operator_runtime_e2e.py`
- Test: `tests/app/test_runtime_canonical_flow_e2e.py`
- Test: `tests/app/test_runtime_center_api.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_learning_api.py`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `console/src/pages/Settings/System/index.test.tsx`

- [ ] Run all focused backend tests touched by Tasks 1-5.
- [ ] Run focused frontend tests touched by Task 5.
- [ ] Run `npm --prefix console run build`.
- [ ] Update `docs/archive/root-legacy/46问题文档.md` with final resolved/unresolved status.

### 2026-04-06 Follow-up Closure Update

本节原本记录当日 follow-up 中途核查结果。此前批量文档清理时该段发生错误转码，现收敛为可公开摘要。

核查重点如下：

- Task 2
  - 重点确认 kickoff / auto-resume 是否已经切到 assignment-native truth，以及 legacy goal/schedule 是否还在影响 execution-stage admission / result contract
  - 重点确认 goal_ids / schedule_ids / active_goal_ids 一类历史字段是否还会通过 earlier partial 路径重新渗回 kickoff seam
- Task 4
  - 重点确认 acquisition producer 是否已经进入 kernel dispatcher-backed task store，而不是继续依赖 free-form DecisionRequestRecord / TaskRecord producer fallback
  - 重点确认 review-gate / runtime-center / producer 是否已经统一使用 kernel task identity
- Task 5
  - 重点确认 query-time builtin tool delegate、eact_agent builtin fallback、system_dispatch 是否都进入正式 capability front-door
  - 重点确认 kernel admission、turn failure 与 frontend/local runtime truth derivation 是否仍存在 partial seam

focused verification additions:

- python -m pytest tests/app/test_learning_api.py tests/app/test_runtime_center_api.py -q -> 122 passed
- python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/dispatch.py tests/kernel/query_execution_environment_parts/lifecycle.py -q -> 58 passed
- python -m pytest tests/app/test_capabilities_execution.py -k "system_dispatch_query or external_runtime or runtime_center" -q -> 3 passed, 48 deselected

### 2026-04-06 Final Closure Update

- `Task 2`: complete
  - kickoff / auto-resume 已切到 assignment/backlog/cycle-native truth。
  - `IndustryInstanceRecord.goal_ids / schedule_ids`、`StrategyMemoryRecord.active_goal_ids / active_goal_titles`、`OperatingCycleRecord.goal_ids`、`WorkflowRunRecord.goal_ids / schedule_ids` 已从正式 state contract 删除。
- `Task 4`: complete
  - acquisition producer / review-gate / prediction recommendation execution 已统一走 kernel-backed identity 与 governed mutation front-door。
- `Task 5`: complete for this closure scope
  - query-time builtin delegate、`react_agent` builtin fallback、capability-market install-template assignment、prediction capability retirement recommendation 已统一接回 capability front-door。
- `Task 6`: complete
  - 问题文档、状态板与本计划文档已按最终代码基线和验证结果同步纠偏。
- final focused verification:
  - `python -m pytest tests/app/test_predictions_api.py tests/app/test_workflow_templates_api.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/runtime_center_api_parts/overview_governance.py tests/industry/test_runtime_views_split.py tests/state/test_strategy_memory_service.py tests/state/test_sqlite_repositories.py tests/app/test_industry_service_wiring.py tests/state/test_main_brain_hard_cut.py tests/app/test_goals_api.py tests/app/test_runtime_chat_media.py tests/app/test_startup_recovery.py tests/app/industry_api_parts/bootstrap_lifecycle.py::test_public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_chat_writeback_schedule_creation_does_not_expand_instance_schedule_truth tests/app/industry_api_parts/runtime_updates.py::test_industry_list_instances_hides_empty_placeholder_records tests/app/industry_api_parts/runtime_updates.py::test_industry_list_instances_uses_lightweight_summary_without_detail_build tests/app/industry_api_parts/runtime_updates.py::test_industry_instance_status_reconciles_from_goal_states tests/app/industry_api_parts/runtime_updates.py::test_industry_instance_status_completes_with_static_team_membership_only tests/app/industry_api_parts/runtime_updates.py::test_industry_detail_backfills_execution_core_identity_with_delegation_first_defaults -q` -> `242 passed`
- residual note:
  - 仍可搜索到的旧字段字面量只剩 migration reset fixture 和无关 governance 控制字段，不再属于运行时平行真相源。
