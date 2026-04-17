# Runtime Center AI Daily Report And Unified Model Call Implementation Plan

> **For agentic workers:** use `executing-plans` or `subagent-driven-development` to execute this plan task by task. Keep verification output fresh and explicit.

**Goal:** 把 `Runtime Center` 的 `日报` 从系统字段列表改成 AI 生成的固定结构中文 `早报 / 晚报`，并把 runtime 侧模型调用的超时、重试、中文校验、结构化校验、错误分级和观测统一收进全局模型调用层。

**Architecture:** 后端新增统一 runtime model call 层作为全局模型纪律入口；Buddy onboarding、chat writeback、industry draft 和 `Runtime Center` 日报全部接入该层。`Runtime Center` cockpit 合同从弱约束 `items[]` 切到固定 `sections[] + status + error + model_status`，前端删除本地日报 fallback，只消费正式后端结果。

## File Map

- Create: `src/copaw/providers/runtime_model_call.py`
- Modify: `src/copaw/providers/runtime_provider_facade.py`
- Modify: `src/copaw/kernel/buddy_onboarding_reasoner.py`
- Modify: `src/copaw/kernel/query_execution_writeback.py`
- Modify: `src/copaw/industry/draft_generator.py`
- Create: `src/copaw/app/runtime_center/daily_report_generation.py`
- Modify: `src/copaw/app/runtime_center/models.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `tests/providers/test_runtime_provider_facade.py`
- Modify: `tests/kernel/test_buddy_onboarding_reasoner.py`
- Modify: `tests/kernel/test_chat_writeback.py`
- Modify: `tests/app/test_industry_draft_generator.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Modify: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.test.tsx`
- Modify: `TASK_STATUS.md`

## Task 1: Build Unified Runtime Model Call Layer

**Files:**

- Create: `src/copaw/providers/runtime_model_call.py`
- Modify: `src/copaw/providers/runtime_provider_facade.py`
- Test: `tests/providers/test_runtime_provider_facade.py`

- [ ] 定义统一 policy：`120s`、`3` 次重试、中文/结构化校验、失败观测。
- [ ] 新增健康追踪与系统级错误升级逻辑。
- [ ] 让 runtime provider 默认返回带统一纪律的 active chat model。
- [ ] 补充 provider 层 focused tests。

Run:

`python -m pytest tests/providers/test_runtime_provider_facade.py -q`

## Task 2: Migrate Structured Runtime Callers

**Files:**

- Modify: `src/copaw/kernel/buddy_onboarding_reasoner.py`
- Modify: `src/copaw/kernel/query_execution_writeback.py`
- Modify: `src/copaw/industry/draft_generator.py`
- Test: `tests/kernel/test_buddy_onboarding_reasoner.py`
- Test: `tests/kernel/test_chat_writeback.py`
- Test: `tests/app/test_industry_draft_generator.py`

- [ ] Buddy onboarding contract compile 改走统一模型调用层。
- [ ] chat writeback decision 改走统一模型调用层。
- [ ] industry draft generation 改走统一模型调用层。
- [ ] 把旧的局部 timeout / validation 逻辑收口成统一错误映射。

Run:

`python -m pytest tests/kernel/test_buddy_onboarding_reasoner.py tests/kernel/test_chat_writeback.py tests/app/test_industry_draft_generator.py -q`

## Task 3: Rebuild Runtime Center Daily Report Backend Contract

**Files:**

- Create: `src/copaw/app/runtime_center/daily_report_generation.py`
- Modify: `src/copaw/app/runtime_center/models.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] 新增日报生成服务，固定输出 `早报 / 晚报` 6 槽位。
- [ ] `RuntimeHumanCockpitReportBlock` 改为 `sections/status/error` 合同。
- [ ] `RuntimeHumanCockpitPayload` 新增 `model_status`。
- [ ] cockpit 后端不再本地拼日报 fallback。
- [ ] 模型失败时返回模块错误块，系统级故障由全局健康状态反映。

Run:

`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`

## Task 4: Update Frontend To Consume Fixed Daily Report Slots

**Files:**

- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Modify: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
- Test: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] 前端类型切到 `sections/status/error/model_status`。
- [ ] `日报` 卡只渲染固定 section 行，不再渲染匿名 bullet。
- [ ] 删除本地合成日报逻辑。
- [ ] 增加模块级错误块和系统级模型状态提醒。

Run:

`cmd /c npm --prefix console test -- src/pages/RuntimeCenter/AgentWorkPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx`

## Task 5: Sync Docs And Verification

**Files:**

- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-17-runtime-center-ai-daily-report-and-unified-model-call-design.md`
- Modify: `docs/superpowers/plans/2026-04-17-runtime-center-ai-daily-report-and-unified-model-call-implementation-plan.md`

- [ ] 把本轮正式落点写回 `TASK_STATUS.md`。
- [ ] 记录 focused verification 命令与结果。
- [ ] 确认实现和 spec/plan 口径一致。

## Final Focused Regression

Backend:

`python -m pytest tests/providers/test_runtime_provider_facade.py tests/kernel/test_buddy_onboarding_reasoner.py tests/kernel/test_chat_writeback.py tests/app/test_industry_draft_generator.py -q`

`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`

Frontend:

`cmd /c npm --prefix console test -- src/pages/RuntimeCenter/AgentWorkPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx`
