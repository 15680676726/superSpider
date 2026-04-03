# 2026-04-03 实现层收口实施计划

## 1. 计划目的

本计划用于执行 [2026-04-02-implementation-layer-closure-design.md](/D:/word/copaw/docs/superpowers/specs/2026-04-02-implementation-layer-closure-design.md) 中已经确认的收口设计，目标不是继续加新功能，而是对当前实现层做一次完整收尾：

1. 拆掉已经确定为热点的大文件。
2. 统一命名与目录边界。
3. 删除已经明确应退役的过渡壳、兼容壳、历史 front-door。
4. 压短 `Runtime Center -> Industry -> Planning Compiler -> Kernel Execution` 的实现路径。
5. 在不污染当前脏根工作区的前提下，于隔离 worktree 中完成施工、验证、提交。

## 2. 执行原则

### 2.1 单一施工基线

- 以最新主线为真相，不在当前根工作区直接做重构。
- 先创建隔离 worktree，再开始写代码。
- 根工作区中其他 agent 的并行修改不纳入本轮施工。

### 2.2 删除优先

- 本轮不是“只加新文件”的重构。
- 每个阶段都必须包含明确删除项。
- 发现只是把旧逻辑转存到新文件、但旧壳还保留的实现，视为未完成。

### 2.3 边界优先于抽象

- 优先切断错误耦合与兼容链。
- 不做纯形式主义“为了模式而模式”的抽象。
- 新模块必须直接对应正式职责，不增加第三层中间 facade。

### 2.4 分拆验证

- 禁止再把大矩阵一次性捆绑到一个长测试命令里。
- 每阶段使用分块验证矩阵，先跑最小闭环，再跑相邻集成。
- 任何阶段如出现超时，先拆矩阵定位，不继续盲跑。

## 3. 范围与完成定义

## 3.1 本轮范围

- `Runtime Center` 共享路由壳、读投影壳、overview 装配壳收口
- `Formal Planning` typed contract 收口
- `Industry` mixin/视图/策略协作者收口
- `Kernel` 执行闭环收口
- `current_goal* / workflow-* / bridge` 历史心智清理
- 目录与命名统一

## 3.2 明确不在本轮范围

- 新业务能力
- 新 UI 大改版
- 新渠道接入
- 与本轮无关的编码治理专项

## 3.3 完成定义

同时满足以下条件才算本轮完成：

1. 设计文档中列出的立即删除项已经物理删除。
2. 热点文件已经按计划拆开，旧壳仅保留必要薄入口，且有明确删除条件；如无必要则直接删除。
3. `current_goal_id/current_goal` 不再出现在正式模型、仓储、服务、前端类型、主路径读面中。
4. `workflow-templates` 和 `workflow-runs` 不再作为正式 root front-door 存在。
5. `Formal Planning` 不再通过 dict 展平/回灌来维持 typed contract。
6. 分阶段验证矩阵全部通过。
7. 文档、状态记录、删除说明同步更新。

## 4. 施工前提

### 4.1 环境与工作树

- 使用新的 git worktree 执行本轮改动。
- 建议分支名：`codex/implementation-layer-closure`
- worktree 建议目录：`.worktrees/implementation-layer-closure`

### 4.2 基线校验

进入 worktree 后先执行：

```powershell
git status --short --branch
python -m pytest tests/app/test_runtime_query_services.py -q
python -m pytest tests/compiler/test_report_replan_engine.py -q
```

目的：

- 确认 worktree 干净。
- 确认 Python 测试环境可跑。
- 确认关键链路基线可用。

## 5. 分阶段实施

## 5.1 阶段 1：删除最危险的语义残留

### 目标

- 先切掉 `current_goal*` 这条残留语义链。
- 先退役 workflow root front-door，避免后续继续绕过正式路径。

### 修改面

- `src/copaw/kernel/agent_profile.py`
- `src/copaw/kernel/agent_profile_service.py`
- `src/copaw/state/repositories/sqlite_governance_agents.py`
- `src/copaw/industry/service_cleanup.py`
- `src/copaw/industry/service_runtime_views.py`
- `console/src/**/AgentWorkbench*`
- root router 中 workflow 入口所在文件
- 直接依赖 `current_goal*` 的测试

### 输出

- 模型、仓储、服务、前端类型里的 `current_goal_id/current_goal` 物理删除
- workflow root front-door 删除或迁移到正式 runtime automation front-door
- 删除 ledger 写入状态文档

### 阶段验证

```powershell
python -m pytest tests/kernel/test_agent_profile_service.py -q
python -m pytest tests/app/test_runtime_center_actor_api.py -q
python -m pytest tests/app/test_goals_api.py -q
cmd /c npm --prefix console run test -- src/pages/AgentWorkbench
```

## 5.2 阶段 2：Runtime Center 路由共享壳拆分

### 目标

- 把 `runtime_center_shared.py` 从总线文件拆成明确职责模块。
- 把 mutation guard、序列化、依赖获取、SSE 编码、front-door helper 分开。

### 修改面

- `src/copaw/app/routers/runtime_center_shared.py`
- 新增 `src/copaw/app/routers/runtime_center_*.py` 支持模块
- 依赖它的 runtime center routes 文件

### 输出

- `runtime_center_shared.py` 仅保留薄入口或被删除
- 请求模型解析、SSE 编码、序列化兜底、front-door 守卫、依赖获取各自独立

### 阶段验证

```powershell
python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q
python -m pytest tests/app/test_runtime_center_actor_api.py -q
python -m pytest tests/app/test_runtime_query_services.py -q
```

## 5.3 阶段 3：Runtime Center 读投影与 overview 装配拆分

### 目标

- 对 `state_query.py` 做第二波拆分。
- 拆开 `overview_cards.py` 的主脑、概览卡、运营卡、支持卡装配。

### 修改面

- `src/copaw/app/runtime_center/state_query.py`
- `src/copaw/app/runtime_center/overview_cards.py`
- 新增：
  - `state_query_tasks.py`
  - `state_query_human_assist.py`
  - `state_query_work_contexts.py`
  - `state_query_governance.py`
  - `state_query_automation.py`
  - `overview_main_brain.py`
  - `overview_operator_cards.py`
  - `overview_support_cards.py`

### 输出

- `RuntimeCenterStateQueryService` 只做编排与组合
- `overview_cards.py` 不再承载 1000+ 行装配逻辑
- Runtime Center 前端不再自己重复拼主脑卡片语义

### 阶段验证

```powershell
python -m pytest tests/app/test_runtime_query_services.py -q
python -m pytest tests/kernel/test_runtime_events.py -q
python -m pytest tests/app/test_runtime_center_actor_api.py -q
cmd /c npm --prefix console run test -- src/pages/Chat/runtimeTransport.test.ts
```

## 5.4 阶段 4：Formal Planning typed contract 收口

### 目标

- 切断 `typed -> dict -> typed` 展平回灌链。
- 拆开 `cycle_planner.py` 与 `report_replan_engine.py` 的职责。
- 删除 monkey-patch 风格字段注入。

### 修改面

- `src/copaw/goals/service_compiler.py`
- `src/copaw/compiler/planning/service_compiler.py`
- `src/copaw/compiler/planning/assignment_planner.py`
- `src/copaw/compiler/planning/cycle_planner.py`
- `src/copaw/compiler/planning/report_replan_engine.py`
- 新增：
  - `strategy_projection.py`
  - `assignment_input.py`
  - `cycle_admission.py`
  - `cycle_budget_policy.py`
  - `cycle_scoring.py`
  - `cycle_projection.py`
  - `report_replan_classifier.py`
  - `report_replan_projection.py`

### 输出

- typed planning 输入输出链保持 typed，不再依赖 dict 临时拼装
- `decision_kind` / `strategy_change_decision` 统一到单一正式字段
- `_set_extra_fields()` 和等价注入壳删除

### 阶段验证

```powershell
python -m pytest tests/compiler/test_planning_models.py -q
python -m pytest tests/compiler/test_strategy_compiler.py -q
python -m pytest tests/compiler/test_cycle_planner.py -q
python -m pytest tests/compiler/test_report_replan_engine.py -q
python -m pytest tests/state/test_strategy_memory_service.py -q
python -m pytest tests/app/test_predictions_api.py -q
```

## 5.5 阶段 5：Industry 领域显式协作者收口

### 目标

- 把 `IndustryService` 从 mixin 聚合改成显式协作者装配。
- 拆分 lifecycle/runtime views/strategy 三个热点。

### 修改面

- `src/copaw/industry/service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/industry/service_runtime_views.py`
- `src/copaw/industry/service_strategy.py`
- 新增：
  - `service_instance_reconcile.py`
  - `service_operating_cycle.py`
  - `service_prediction_cycle.py`
  - `service_report_closure_adapter.py`
  - `service_runtime_focus.py`
  - `service_runtime_planning_views.py`
  - `service_runtime_main_chain.py`
  - `service_runtime_detail.py`
  - `service_runtime_execution_summary.py`
  - `service_strategy_memory.py`
  - `service_chat_writeback_routing.py`
  - `service_instance_summary.py`

### 输出

- `IndustryService` 只保留装配与外部 front-door
- runtime views 不再走 legacy goal fallback
- strategy sync 不再依赖 runtime view helper

### 阶段验证

```powershell
python -m pytest tests/industry/test_report_synthesis.py -q
python -m pytest tests/industry/test_runtime_views_split.py -q
python -m pytest tests/app/industry_api_parts/runtime_updates.py -q
python -m pytest tests/app/test_industry_service_wiring.py -q
```

## 5.6 阶段 6：Kernel 执行闭环压路径

### 目标

- 把 `turn_executor.py`、`query_execution_runtime.py`、`main_brain_chat_service.py` 按正式职责压短。
- 统一 child-run 命名和 cleanup 壳。

### 修改面

- `src/copaw/kernel/turn_executor.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/main_brain_orchestrator.py`
- `src/copaw/kernel/query_execution_confirmation.py`
- `src/copaw/kernel/child_run_shell.py`
- 新增：
  - `turn_interaction_router.py`
  - `turn_kernel_admission.py`
  - `turn_stream_gateway.py`
  - `main_brain_cognitive_surface.py`
  - `main_brain_execution_envelope.py`
  - `main_brain_chat_session_store.py`
  - `main_brain_chat_prompt_builder.py`
  - `main_brain_chat_stream_runner.py`
  - `main_brain_chat_commit_bridge.py`
  - `query_execution_runner.py`
  - `query_execution_resume_service.py`
  - `query_execution_actor_runtime.py`
  - `query_execution_main_brain_bridge.py`
  - `query_execution_runtime_state.py`
  - `query_execution_resume_request.py`

### 输出

- `KernelTurnExecutor` 只保留 turn 入口级编排
- `QueryExecutionRuntime` 不再承担 runner、resume、checkpoint、prune、persistence 全部职责
- `child_run_shell` 词汇与正式 child-run / cleanup 语义对齐

### 阶段验证

```powershell
python -m pytest tests/kernel/test_turn_executor.py -q
python -m pytest tests/kernel/test_main_brain_chat_service.py -q
python -m pytest tests/kernel/test_query_execution_runtime.py -q
python -m pytest tests/kernel/test_main_brain_commit_service.py -q
python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q
```

## 5.7 阶段 7：目录收拢、命名统一、过渡壳清扫

### 目标

- 在不引入新一层 compat 的前提下完成目录归位。
- 删除阶段性 re-export、历史 alias、bridge 残留命名。

### 修改面

- `src/copaw/state/`
- `src/copaw/kernel/`
- `src/copaw/industry/`
- `src/copaw/app/runtime_center/`
- `src/copaw/environments/`
- 相关导入路径、测试、文档

### 输出

- `main_brain_service.py` 之类污染 truth-layer 的命名被重命名或下沉到正确目录
- `bridge` 词汇退出正式环境主链
- 过渡 re-export 和 alias 清空

### 阶段验证

```powershell
python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_center_actor_api.py -q
python -m pytest tests/kernel/test_runtime_events.py tests/kernel/test_query_execution_runtime.py -q
python -m pytest tests/industry/test_runtime_views_split.py tests/app/industry_api_parts/runtime_updates.py -q
python -m pytest tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py -q
git diff --check
```

## 6. 多 agent 实施拆分

## 6.1 施工方式

- 使用 6 个 worker agent。
- 每个 agent 只拿互斥写集合。
- 任何共享文件只能由主 agent 或唯一 owner 修改。

## 6.2 Ownership

### Agent 1：Agent Visible Model / current_goal 删除链

负责：

- `kernel/agent_profile*`
- `state/repositories/sqlite_governance_agents.py`
- `industry/service_cleanup.py`
- `console` 中 `AgentWorkbench` 相关类型与适配

### Agent 2：Runtime Center 路由共享壳拆分

负责：

- `app/routers/runtime_center_shared.py`
- runtime center routes 依赖的共享 helper 支撑文件

### Agent 3：Formal Planning 合同拆分

负责：

- `goals/service_compiler.py`
- `compiler/planning/*`
- typed planning 相关测试

### Agent 4：Runtime Center 读投影拆分

负责：

- `app/runtime_center/state_query.py`
- `app/runtime_center/task_review_projection.py`
- 相关 query 测试

### Agent 5：Runtime Center overview 装配拆分

负责：

- `app/runtime_center/overview_cards.py`
- `app/runtime_center/*overview*`
- 必要的前端只读适配

### Agent 6：Industry / Kernel / workflow retirement

负责：

- `industry/service*.py`
- `kernel/turn_executor.py`
- `kernel/query_execution_runtime.py`
- `kernel/main_brain_chat_service.py`
- workflow root front-door 删除链

## 7. 主 agent 串行控制点

以下动作必须由主 agent 串行完成，不能并发乱改：

1. 创建 worktree
2. 分派 ownership
3. 合并共享导入路径调整
4. 解决跨 agent 连接处
5. 跑阶段集成验证
6. 更新文档与状态
7. 最终提交与合并

## 8. 测试矩阵策略

## 8.1 原则

- 每阶段只跑与该阶段直接相关的最小矩阵。
- 慢测试独立跑，不再捆成大串。
- 任何超过 3 分钟的用例文件单独列出，避免掩盖失败点。

## 8.2 推荐分组

### A. Runtime Center

```powershell
python -m pytest tests/app/test_runtime_query_services.py -q
python -m pytest tests/app/test_runtime_center_actor_api.py -q
python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q
```

### B. Formal Planning

```powershell
python -m pytest tests/compiler/test_planning_models.py -q
python -m pytest tests/compiler/test_strategy_compiler.py -q
python -m pytest tests/compiler/test_cycle_planner.py -q
python -m pytest tests/compiler/test_report_replan_engine.py -q
```

### C. Industry

```powershell
python -m pytest tests/industry/test_report_synthesis.py -q
python -m pytest tests/industry/test_runtime_views_split.py -q
python -m pytest tests/app/industry_api_parts/runtime_updates.py -q
python -m pytest tests/app/test_industry_service_wiring.py -q
```

### D. Kernel

```powershell
python -m pytest tests/kernel/test_turn_executor.py -q
python -m pytest tests/kernel/test_main_brain_chat_service.py -q
python -m pytest tests/kernel/test_query_execution_runtime.py -q
python -m pytest tests/kernel/test_main_brain_commit_service.py -q
```

### E. 慢测试单独跑

```powershell
python -m pytest tests/app/industry_api_parts/runtime_updates.py -q
python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q
```

### F. 前端

```powershell
cmd /c npm --prefix console run test -- src/pages/Chat/runtimeTransport.test.ts
cmd /c npm --prefix console run test -- src/pages/AgentWorkbench
```

### G. 最终总收口

```powershell
python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_center_actor_api.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_turn_executor.py -q
git diff --check
```

## 9. 文档同步

本轮施工完成后至少同步：

- `TASK_STATUS.md`
- `API_TRANSITION_MAP.md`
- `DATA_MODEL_DRAFT.md`（如果对象模型边界变化）
- `docs/superpowers/specs/2026-04-02-implementation-layer-closure-design.md`
- 删除 ledger 或等价状态记录

## 10. 风险与回退策略

### 风险 1：大规模导入路径变动导致串联失败

应对：

- 每阶段先做窄拆分，再做导入收拢
- 用最小矩阵快速定位断点

### 风险 2：多 agent 交界面冲突

应对：

- 先固定 ownership
- 共享连接点只由主 agent 合并

### 风险 3：删除 `current_goal*` 触发前端/报告隐式依赖

应对：

- 删除前先补 focused regression
- 先切主路径，再清兼容测试

### 风险 4：workflow 入口删除后遗漏隐式调用方

应对：

- 先用 `rg` 穷举 root front-door 与 launch/resume 调用点
- 删除后补 API/路由层回归

## 11. 执行结论

本轮实施按以下顺序推进：

1. 写入本计划并冻结边界。
2. 创建隔离 worktree。
3. 基于本计划启动 6 个 worker agent 按 ownership 并行施工。
4. 主 agent 串行合并交界面并跑阶段验证。
5. 所有删除项物理落地后，再做最终验收、文档同步、提交与合并。

不满足“删除完成 + 边界收紧 + 测试通过”三项同时成立，不得宣称本轮收口完成。
