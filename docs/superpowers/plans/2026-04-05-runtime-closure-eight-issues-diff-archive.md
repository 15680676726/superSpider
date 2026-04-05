# Runtime Closure Eight Issues Diff Archive

日期：`2026-04-05`

## 1. 本轮实际改了什么

### 1.1 Buddy 建档到聊天入口正式绑定

- `console/src/pages/BuddyOnboarding/index.tsx`
- `console/src/pages/BuddyOnboarding/index.test.tsx`
- `console/src/api/modules/buddy.ts`
- `console/src/utils/runtimeChat.ts`
- `src/copaw/kernel/buddy_onboarding_service.py`
- `tests/app/test_buddy_cutover.py`

本轮把 Buddy 建档确认后的 `execution_carrier` 正式接进聊天入口，补齐前后端 `chat_binding` 契约，不再只靠松散 query 参数进聊天。

### 1.2 Buddy profile 前端真相源收口

- `console/src/runtime/buddyProfileBinding.ts`
- `console/src/pages/Chat/runtimeTransportRequest.ts`
- `console/src/pages/Industry/useIndustryPageState.ts`
- `console/src/pages/Industry/useIndustryPageState.test.tsx`
- `console/src/pages/Chat/runtimeTransport.test.ts`

本轮把 `buddy_profile_id` 的前端读取收口到统一来源，`localStorage` 不再承担 runtime truth，只保留软缓存语义。

### 1.3 `/agents` 第二入口退场

- `console/src/routes/index.tsx`
- `console/src/pages/Agent/Workspace/index.tsx`
- `console/src/pages/Chat/useRuntimeBinding.ts`
- `console/src/pages/Chat/useRuntimeBinding.test.ts`
- `console/src/pages/RuntimeCenter/index.tsx`
- `console/src/pages/RuntimeCenter/index.test.tsx`

本轮把 `/agents` 从正式主入口降为细节视图路径，Runtime Center 继续作为正式 owning surface。

### 1.4 Industry runtime-first 收口

- `console/src/pages/Industry/index.tsx`
- `console/src/pages/Industry/index.test.tsx`
- `console/src/pages/RuntimeCenter/actorPulse.ts`

本轮做了两件事：

- Industry 页面保留运行驾驶舱为主面，旧草案编辑器改为显式动作后再展开。
- 前端当前焦点展示不再从 `goal_title / goal_id` 回退伪造 `currentGoal`。

### 1.5 Buddy 深层逻辑收口

- `src/copaw/kernel/buddy_projection_service.py`
- `src/copaw/kernel/buddy_onboarding_service.py`
- `tests/kernel/test_buddy_onboarding_service.py`
- `tests/kernel/test_buddy_projection_service.py`

本轮收紧了两类逻辑：

- 没有 canonical runtime focus 时，Buddy 不再伪造 `current_task_summary / why_now_summary / single_next_action_summary`。
- `record_chat_interaction(...)` 不再把普通聊天直接计入成长推进，只保留必要关系信号。

### 1.6 闭环证明口径纠偏

- `TASK_STATUS.md`
- `tests/app/test_runtime_canonical_flow_e2e.py`
- `tests/app/test_phase_next_autonomy_smoke.py`
- `tests/app/test_operator_runtime_e2e.py`
- `tests/providers/test_live_provider_smoke.py`
- `tests/routines/test_live_routine_smoke.py`
- `tests/test_p0_runtime_terminal_gate.py`

本轮把“测试名字、skip reason、文档口径”统一改成说真话：

- harness / contract / focused slice 不再被写成默认整链闭环。
- live smoke 明确标记为 opt-in。
- gate 测试禁止把 `--collect-only` / `-k` 切片当默认回归命令。

### 1.7 过程文档

- `docs/superpowers/plans/2026-04-05-runtime-closure-eight-issues-implementation-plan.md`
- `docs/superpowers/plans/2026-04-05-runtime-closure-eight-issues-diff-archive.md`

---

## 2. 本轮明确没改什么

下面这些文件在早期计划里被提过，但本轮最终没有动：

- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/query_execution_prompt.py`
- `src/copaw/app/routers/runtime_center_routes_core.py`
- `tests/kernel/test_main_brain_chat_service.py`
- `tests/kernel/test_main_brain_runtime_context_buddy_prompt.py`
- `tests/app/test_mcp_runtime_contract.py`
- `tests/app/test_cron_executor.py`
- `tests/app/test_runtime_lifecycle.py`
- `console/src/layouts/Sidebar.tsx`
- `console/src/layouts/Sidebar.test.tsx`
- `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- `console/src/pages/RuntimeCenter/text.ts`
- `console/src/pages/Chat/chatRuntimePresentation.ts`
- `console/src/pages/Chat/pagePresentation.tsx`

原因不是遗漏，而是本轮真实问题在更小的接线面上已经能闭环，不需要把范围继续扩大。

---

## 3. 本轮验证覆盖但未改的文件

以下测试文件本轮有实际复跑，但最终不需要改：

- `tests/app/test_mcp_runtime_contract.py`
- `tests/app/test_cron_executor.py`
- `tests/app/test_runtime_lifecycle.py`

---

## 4. 本轮无关脏文件，不进入本次提交

- `src/copaw/memory/activation_models.py`
- `src/copaw/state/models_memory.py`
- `src/copaw/memory/knowledge_graph_models.py`
- `tests/memory/test_knowledge_graph_models.py`

这些文件不属于本轮 8 个问题收口范围，提交时应显式排除。

---

## 5. 验证快照

本轮最终人工复跑结果：

- `python -m pytest tests/app/test_buddy_cutover.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py tests/app/test_operator_runtime_e2e.py tests/app/test_mcp_runtime_contract.py tests/app/test_cron_executor.py tests/app/test_runtime_lifecycle.py tests/test_p0_runtime_terminal_gate.py tests/providers/test_live_provider_smoke.py tests/routines/test_live_routine_smoke.py -q`
  - 结果：`131 passed, 10 skipped`
- `npm --prefix console run test -- src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/runtimeTransport.test.ts src/pages/Industry/useIndustryPageState.test.tsx src/pages/Chat/useRuntimeBinding.test.ts src/pages/RuntimeCenter/index.test.tsx src/routes/resolveSelectedKey.test.ts src/layouts/Sidebar.test.tsx src/pages/Industry/index.test.tsx`
  - 结果：`54 passed`
- `npm --prefix console run build`
  - 结果：通过

---

## 6. 提交边界

本次提交只应包含：

- 第 1 节列出的实际改动
- 本文档与本轮 implementation plan

本次提交不应包含：

- 第 4 节列出的 memory / knowledge graph 脏文件
