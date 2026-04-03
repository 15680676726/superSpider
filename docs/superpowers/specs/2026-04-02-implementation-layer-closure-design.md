# 2026-04-02 实现层收口设计

## 1. 文档目的

本设计只解决一件事：

把当前已经成型的正式主链，落实为更短、更清晰、更可删旧的实现层结构。

本轮不是继续扩功能，而是收口以下 4 类问题：

1. 拆大文件
2. 统一命名
3. 删除过渡壳
4. 压短 `Runtime Center -> Industry Lifecycle -> Planning Compiler -> Execution Closure` 的实现路径

本设计面向后续独立施工，不允许继续以“以后再优化”作为开放尾巴。

---

## 2. 审计基线

### 2.1 已读基线

本轮审计以以下文档为约束：

- `AGENTS.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

### 2.2 当前热点体量

当前最明显的实现层热点文件：

- `src/copaw/app/routers/runtime_center_shared.py` `930` 行
- `src/copaw/app/runtime_center/state_query.py` `868` 行
- `src/copaw/app/runtime_center/overview_cards.py` `1826` 行
- `src/copaw/industry/service_lifecycle.py` `4409` 行
- `src/copaw/industry/service_runtime_views.py` `3144` 行
- `src/copaw/industry/service_strategy.py` `1815` 行
- `src/copaw/kernel/turn_executor.py` `1139` 行
- `src/copaw/kernel/query_execution_runtime.py` `1916` 行

### 2.3 当前真实问题不是“逻辑没成型”

当前仓库已经有正式主链：

- `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> replan`
- `/runtime-center/chat/run -> KernelTurnExecutor -> MainBrainOrchestrator / MainBrainChatService -> QueryExecutionRuntime -> state/evidence`

所以这轮收口不是“补设计”。

这轮要做的是把已经成型的边界，真正落成代码边界。

---

## 3. 核心诊断

### D1. Runtime Center 的依赖获取、请求模型、序列化、front-door guard、mutation 分发被堆进同一文件

问题位置：

- `src/copaw/app/routers/runtime_center_shared.py:241`
- `src/copaw/app/routers/runtime_center_shared.py:495`
- `src/copaw/app/routers/runtime_center_shared.py:596`
- `src/copaw/app/routers/runtime_center_shared.py:616`
- `src/copaw/app/routers/runtime_center_shared.py:673`
- `src/copaw/app/routers/runtime_center_shared.py:1001`

问题性质：

- 一个“shared”文件同时承担 request schema、app.state service locator、SSE 编码、guard、mutation gateway、actor payload、knowledge payload、capability assignment、schedule surface。
- `shared` 这个名字已经失真，它不是底层共享工具，而是运行中心的隐性总线。

结论：

- `runtime_center_shared.py` 必须拆成显式职责文件，禁止继续扩张。

### D2. Runtime Center overview 仍然是巨型读面装配块

问题位置：

- `src/copaw/app/runtime_center/overview_cards.py:34`
- `src/copaw/app/runtime_center/overview_cards.py:855`
- `src/copaw/app/runtime_center/overview_cards.py:1077`
- `src/copaw/app/runtime_center/overview_cards.py:1501`
- `src/copaw/app/runtime_center/overview_cards.py:1913`

问题性质：

- 同一文件同时承载 overview 卡片装配、entry 映射、main-brain cockpit、automation payload、governance payload、capability summary、evidence summary。
- `RuntimeCenterQueryService` 已经很薄，但 `overview_cards.py` 仍然是第二个 god object。

结论：

- Runtime Center 读面边界已经设计正确，但卡片装配层还没有物理拆开。

### D3. Industry 领域表面是 facade，内部实际仍是 mixin 巨型聚合

问题位置：

- `src/copaw/industry/service.py:1`
- `src/copaw/industry/service_lifecycle.py:41`
- `src/copaw/industry/service_runtime_views.py:14`
- `src/copaw/industry/service_strategy.py:20`

问题性质：

- `IndustryService` 表面只有几十行，但真实复杂度被压进多个 `_Mixin` 文件。
- mixin 方式让“职责分层”看上去存在，实际上文件边界和变更 ownership 仍然混在一起。
- `service_lifecycle.py` 既做 planning sidecar、kickoff、cycle run、report synthesis follow-up、prediction review、bootstrap/update/delete。

结论：

- `IndustryService` 不能继续依赖 mixin 承载核心复杂度，必须转成显式 collaborator/facade 结构。

### D4. Industry runtime view 仍然在大量使用 legacy goal fallback 拼 current focus

问题位置：

- `src/copaw/industry/service_runtime_views.py:1914`
- `src/copaw/industry/service_runtime_views.py:1932`
- `src/copaw/industry/service_runtime_views.py:1979`
- `src/copaw/industry/service_runtime_views.py:2188`
- `src/copaw/industry/service_runtime_views.py:2283`
- `src/copaw/industry/service_runtime_views.py:3168`

问题性质：

- 当前 formal chain 已经是 `backlog / assignment / report / replan`，但 runtime summary 仍然通过 `_resolve_execution_core_goal()` 和 `fallback_goal` 回退来拼焦点。
- 这会继续把 `goal` 留在 operator 心智中心，拉长 read path，也会拖慢后续删除 `current_goal*`。

结论：

- Runtime summary 必须改成“assignment/backlog/cycle truth first”，goal 只保留 leaf backlink，不再参与 focused runtime 主投影。

### D5. Agent 可见模型还保留 `current_goal*` 反向兼容字段，已经形成第二条残留语义链

问题位置：

- `src/copaw/kernel/agent_profile.py:44`
- `src/copaw/kernel/agent_profile.py:62`
- `src/copaw/kernel/agent_profile_service.py:1000`
- `src/copaw/kernel/agent_profile_service.py:1155`
- `src/copaw/state/repositories/sqlite_governance_agents.py:338`
- `console/src/pages/AgentWorkbench/useAgentWorkbench.ts:152`

问题性质：

- model、service、sqlite repository、前端类型都还保留 `current_goal_id/current_goal`。
- 这不是 harmless alias；它会继续逼迫 Industry、AgentWorkbench、ProfileService 去做 focus/goal 双写或回填。

结论：

- 这是本轮最值钱的删除点之一，必须物理移除，而不是继续“只是不展示”。

### D6. TurnExecutor 和 QueryExecutionRuntime 的装配/绑定/执行状态写回混在一起

问题位置：

- `src/copaw/kernel/turn_executor.py:574`
- `src/copaw/kernel/turn_executor.py:732`
- `src/copaw/kernel/turn_executor.py:819`
- `src/copaw/kernel/query_execution_runtime.py:53`
- `src/copaw/kernel/query_execution_runtime.py:114`
- `src/copaw/kernel/query_execution_runtime.py:1035`
- `src/copaw/kernel/query_execution_runtime.py:1070`
- `src/copaw/kernel/query_execution_runtime.py:1911`

问题性质：

- `KernelTurnExecutor` 前半段是 interaction-mode 解析，后半段又塞满 setter/sync/binding。
- `QueryExecutionRuntime` 一边是 collaborator setter，一边是 execute/resume，一边是 runtime persistence/context merge/intake/commit。
- 这导致执行闭环真实路径虽然已经统一，但代码路径仍然很长。

结论：

- 执行闭环下一步不是再补功能，而是把 binding、request context、runtime state persistence、resume flows 分开。

### D7. `bridge` 词汇还残留在 Runtime Center environment/session 运行面，和正式 `Host Companion Session` 心智不一致

问题位置：

- `src/copaw/app/routers/runtime_center_routes_ops.py:737`
- `src/copaw/app/routers/runtime_center_routes_ops.py:764`
- `src/copaw/app/routers/runtime_center_routes_ops.py:801`
- `src/copaw/app/routers/runtime_center_routes_ops.py:827`
- `src/copaw/app/routers/runtime_center_routes_ops.py:887`
- `src/copaw/app/routers/runtime_center_shared.py:98`

问题性质：

- 当前正式文档已经使用 `Seat Runtime / Host Companion Session / SessionMount`。
- router 仍然暴露 `bridge/ack|heartbeat|reconnect|archive|deregister` 这套历史词汇。

结论：

- 这不是简单 rename；这是环境运行面的正式 vocabulary 收口。

### D8. 命名体系还在混用 `service / runtime / shared / bootstrap / lifecycle / facade / manager`

问题位置：

- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/runtime_bootstrap_execution.py`
- `src/copaw/app/runtime_bootstrap_query.py`
- `src/copaw/app/runtime_center/service.py`
- `src/copaw/industry/service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/kernel/query_execution_runtime.py`

问题性质：

- 一部分文件名表达的是启动阶段，一部分表达运行态，一部分表达领域职责，一部分只是历史习惯。
- 当前“名字看不出边界”本身已经构成维护成本。

结论：

- 必须给出明确的词汇边界，不再允许继续泛化 `shared`、泛化 `runtime`、泛化 `lifecycle`。

### D9. Formal planning 仍存在“typed truth -> dict 展平 -> 再组回 typed model”的重复整形链

问题位置：

- `src/copaw/goals/service_compiler.py:502`
- `src/copaw/goals/service_compiler.py:552`
- `src/copaw/goals/service_compiler.py:624`
- `src/copaw/compiler/planning/assignment_planner.py:193`
- `src/copaw/compiler/planning/report_replan_engine.py:98`
- `src/copaw/compiler/planning/cycle_planner.py:106`

问题性质：

- `PlanningStrategyConstraints` 已经存在，但 `service_compiler.py` 仍先拆成多个 `strategy_*` dict，再在不同位置组回 typed planning 输入。
- `AssignmentPlanningCompiler.plan_from_context()` 继续从裸 context 伪造 typed 输入。
- `ReportReplanEngine` 仍依赖 dump-time 额外字段注入，而不是完整 typed contract。
- `CyclePlanningCompiler` 虽然不如 `industry` 那样巨大，但已经在一个文件里混 admission、budget policy、ranking、projection。

结论：

- formal planning 子域下一步不是再扩能力，而是先把 typed contract 走直，不再反复 dict 化。

### D10. 旧 `workflow/current_goal/goal-dispatch` 仍在仓内维持第二条历史执行心智

问题位置：

- `src/copaw/industry/service_cleanup.py:1784`
- `src/copaw/industry/service_cleanup.py:1869`
- `src/copaw/goals/service_dispatch.py:8`
- `src/copaw/industry/service_activation.py:275`
- `src/copaw/industry/service_lifecycle.py:2048`
- `src/copaw/app/routers/workflow_templates.py:36`
- `src/copaw/workflows/service_runs.py:143`
- `src/copaw/app/startup_recovery.py:98`

问题性质：

- 行业 bootstrap/cleanup 仍主动写 `current_goal*`
- `GoalService` 仍承载多套 dispatch 变体
- root router 还挂着 `workflow-templates / workflow-runs`
- workflow service 内部仍耦合 `goal-dispatch`
- startup recovery 还带着 legacy execution-core chat-writeback 修复器

结论：

- 这些不是边角垃圾，而是会持续把旧主链拖回来的复活点，必须纳入本轮删旧计划。

---

## 4. 收口目标

本轮结束时，要同时满足以下条件：

1. `Runtime Center` 不再有单个 800+ 行的共享总线文件承载多类职责。
2. `Industry` 不再把核心复杂度藏在 mixin 巨文件里。
3. `KernelTurnExecutor` 和 `QueryExecutionRuntime` 的 binding/context/persistence/resume 职责分开。
4. `current_goal*` 从正式 agent visible model、持久层、前端类型中物理删除。
5. `bridge` 旧词汇从正式 environment/session front-door 退役，统一改成 host/session vocabulary。
6. 新命名规则写入文档并体现在落地文件名上。
7. 每个拆分动作都伴随旧壳删除，不允许“只新增文件、旧文件继续保留原逻辑”。

---

## 5. 设计方案

### 5.1 Runtime Center 收口

#### 5.1.1 `runtime_center_shared.py` 拆分目标

目标拆分：

- `src/copaw/app/routers/runtime_center_request_models.py`
  - 只放 request payload schema
- `src/copaw/app/routers/runtime_center_dependencies.py`
  - 只放 `app.state` service/repository accessor
- `src/copaw/app/routers/runtime_center_mutation_gateway.py`
  - 只放 governed mutation dispatch、reentry guard
- `src/copaw/app/routers/runtime_center_payloads.py`
  - 只放 agent/task/knowledge/session public payload assembly
- `src/copaw/app/routers/runtime_center_sse.py`
  - 只放 `_encode_sse_event()` 与 event publish helpers

删除规则：

- 原 `runtime_center_shared.py` 最终只能保留 re-export 过渡一轮，随后物理删除。
- 本轮不允许把新 helper 再塞回 `shared.py`。

#### 5.1.2 `overview_cards.py` 拆分目标

目标拆分：

- `src/copaw/app/runtime_center/overview_card_support.py`
  - 通用 call/mapping/count helper
- `src/copaw/app/runtime_center/overview_entry_builders.py`
  - task/agent/evidence/decision/patch/growth entry builder
- `src/copaw/app/runtime_center/overview_main_brain.py`
  - main-brain cockpit、industry strategy、report cognition、automation payload
- `src/copaw/app/runtime_center/overview_capability_governance.py`
  - capability/prediction/governance/evidence summary

保留：

- `RuntimeCenterOverviewBuilder`
  - 只做 orchestration，不做细节 mapping

#### 5.1.3 `state_query.py` 第二波拆分目标

现状：

- task/human-assist/work-context/schedule/goal/decision/projection 全塞一个类

目标拆分：

- `task_projection.py`
- `human_assist_projection.py`
- `work_context_projection.py`
- `goal_projection.py`
- `decision_projection.py`

保留：

- `RuntimeCenterStateQueryService`
  - 只做 facade 和 dependency injection

### 5.2 Formal Planning 收口

#### 5.2.1 `service_compiler.py` 改成 typed planning orchestration

目标：

- `service_compiler.py` 不再平铺 `strategy_mission / strategy_lane_budgets / strategy_review_rules`
- 统一只传单一 `PlanningStrategyConstraints`
- assignment 输入收成 typed `AssignmentPlanningInput`

目标拆分：

- `src/copaw/compiler/planning/strategy_projection.py`
  - 只负责 strategy 读取与 typed constraints 编译
- `src/copaw/compiler/planning/assignment_input.py`
  - 只负责 assignment planner 的 typed input

删除动作：

- 删除 `AssignmentPlanningCompiler.plan_from_context()`
- 删除 `_build_assignment_strategy_sidecar_context()`
- 删除平铺 `strategy_*` alias

#### 5.2.2 `cycle_planner.py` 从单文件策略机拆成明确子模块

目标拆分：

- `cycle_admission.py`
- `cycle_budget_policy.py`
- `cycle_scoring.py`
- `cycle_projection.py`

保留：

- `CyclePlanner` 或 `CyclePlanningCompiler`
  - 只做 façade

#### 5.2.3 `report_replan` 改成完整 typed contract

目标：

- `ReportReplanDecision` 直接拥有正式 `trigger_context / strategy_change`
- 不再 monkey-patch `model_dump()`

目标拆分：

- `report_replan_classifier.py`
- `report_replan_projection.py`

删除动作：

- 删除 `_set_extra_fields()`
- 删除 `strategy_change_decision`
- 删除 `decision_hint` 这类双名残留

### 5.3 Industry 收口

#### 5.2.1 `IndustryService` 从 mixin 聚合改为显式协作者

目标结构：

- `industry/service.py`
  - 只做 façade + collaborator 装配
- `industry/bootstrap_service.py`
- `industry/team_service.py`
- `industry/view_service.py`
- `industry/planning_service.py`
- `industry/execution_kickoff_service.py`
- `industry/report_cycle_service.py`

原则：

- mixin 只允许保留在短过渡期，不能继续成为正式复杂度承载方式。

#### 5.2.2 `service_lifecycle.py` 拆分目标

目标拆分：

- `industry/planning_materialization.py`
  - strategy constraints、activation、cycle planner、assignment materialization
- `industry/execution_kickoff.py`
  - chat kickoff、schedule kickoff、resume gating、goal leaf dispatch 封装
- `industry/report_processing.py`
  - synthesis、follow-up backlog、report back
- `industry/cycle_runner.py`
  - run_operating_cycle、prediction review window、cycle dispatch
- `industry/bootstrap_preview.py`
  - preview/bootstrap/team update/delete 入口

删除动作：

- `_compat_cycle_reason()` 物理删除，调用方直接消费正式 reason vocabulary。
- 分散的 `dispatch_goal_execute_now / dispatch_goal_deferred_background` 不再散落在 lifecycle 文件深处，统一收口到 `execution_kickoff` 侧的 leaf dispatch façade。

#### 5.2.3 `service_runtime_views.py` 拆分目标

目标拆分：

- `industry/planning_surface_views.py`
  - uncertainty/lane_budget/replan/planning surface
- `industry/execution_summary_views.py`
  - current focus、execution summary、child task chain
- `industry/instance_detail_projection.py`
  - detail payload assembly
- `industry/focus_selection.py`
  - focused assignment/backlog selection rules

删除动作：

- 删除 `_resolve_execution_core_goal()`
- 删除 execution summary 中对 `fallback_goal/current_goal` 的主路径依赖
- focused runtime 改为：
  - `assignment truth`
  - `backlog follow-up truth`
  - `cycle truth`
  - `goal backlink only`

### 5.4 Kernel 执行闭环收口

#### 5.3.1 `KernelTurnExecutor` 拆分目标

目标拆分：

- `kernel/turn_interaction_mode.py`
  - auto/chat/orchestrate 解析
- `kernel/turn_service_bindings.py`
  - collaborator wiring / sync helpers
- `kernel/turn_request_context.py`
  - request runtime cache / payload helpers

保留：

- `KernelTurnExecutor`
  - 只负责 admission、dispatch、stream orchestration

删除动作：

- setter/sync/binding 大段逻辑从 `turn_executor.py` 移出。

#### 5.3.2 `QueryExecutionRuntime` 拆分目标

目标拆分：

- `kernel/query_execution_bindings.py`
  - collaborator bundle 和 setter
- `kernel/query_execution_resume.py`
  - tool confirmation / human assist resume
- `kernel/query_execution_context.py`
  - main-brain runtime context merge、execution task context、degradation context
- `kernel/query_execution_state.py`
  - actor query start/finish、runtime state persistence、snapshot save
- `kernel/query_execution_capability_context.py`
  - capability context / delegation-first / profile resolution
- `kernel/query_execution_intake.py`
  - intake contract / writeback / commit outcome

保留：

- `query_execution_runtime.py`
  - 只做 `execute_stream()` 总控与 imports 过渡，最终继续瘦身

#### 5.3.3 `child_run_shell.py`

判断：

- 这个文件不大，职责也相对纯。

处理方式：

- 不拆
- 但它的 `ChildRunWriterContract` 要作为统一 child-run writer shell 保留给 delegation/query execution 共用
- 后续禁止在别处重新发明第二套 writer lease envelope

### 5.5 命名统一规则

#### 5.4.1 保留词

- `Service`
  - 领域 owner，允许读写 state / 触发领域流程
- `QueryService`
  - 只读 façade，不写 state
- `Facade`
  - 边缘组合壳，不拥有真相
- `Builder` / `Projection`
  - 纯装配、纯派生
- `Bootstrap`
  - 只用于启动接线，不承载领域逻辑
- `Runtime`
  - 只用于 live session / lease / execution / heartbeat / runtime-state 语义

#### 5.4.2 禁止继续泛化的词

- `shared`
  - 除非真的是零领域语义的底层 helper，否则禁用
- `manager`
  - 新核心路径禁用，只保留旧外部 adapter
- `lifecycle`
  - 只用于真实生命周期转换；不能再承载 planning、view、bootstrap、cleanup 全部逻辑
- `bridge`
  - 只保留给外部协议桥；环境会话正式词汇统一用 `host/session/companion`
- `main_brain`
  - 只允许出现在 `kernel/` 和 operator/chat 前台；禁止继续进入 `state/` 正式服务文件名

### 5.6 目录收拢方案

#### 5.6.1 `state`

目标：

- 新增 `src/copaw/state/services/`
- 拆 `main_brain_service.py`

目标文件：

- `operating_lane_service.py`
- `backlog_service.py`
- `operating_cycle_service.py`
- `assignment_service.py`
- `agent_report_service.py`

#### 5.6.2 `kernel`

目标：

- 新增 `src/copaw/kernel/main_brain/`
- 新增 `src/copaw/kernel/execution/query/`

说明：

- `main_brain_*` 文件进入 `kernel/main_brain/`
- `query_execution_*` 文件进入 `kernel/execution/query/`

#### 5.6.3 `industry`

目标：

- `service.py` 保留唯一公开入口
- 复杂内部实现收进 `industry/internal/`

#### 5.6.4 `app/runtime_center`

目标：

- 新增 `query/`
- 新增 `projections/`

#### 5.6.5 `environments`

目标：

- 新增 `environments/browser/`
- 把 `capabilities/browser_runtime.py` 迁到环境域

### 5.7 历史遗留删除清单

#### 5.7.1 立即纳入本轮删除

- `AgentProfile.current_goal_id/current_goal`
- `AgentProfileService` 中 `goal_id/goal_title -> current_goal*` 回填逻辑
- `sqlite_governance_agents.py` 中 `current_goal*` 列写入逻辑
- `industry/service_cleanup.py` 中 `current_goal*` 写入
- `Industry runtime views` 中 `fallback_goal/current_goal` 主路径
- `_compat_cycle_reason()`
- `AgentWorkbench` 的 tab alias 与 `current_goal*` 前端类型
- root router 上的 `/workflow-templates` 与 `/workflow-runs`

#### 5.7.2 前置条件后删除

- `runtime_center_routes_ops.py` 中 `bridge/*` vocabulary
  - 前提：host/session 新 front-door 和前端调用位完成切换
- `runtime_center_shared.py` 原文件
  - 前提：request model / deps / mutation / payload / sse 全部拆出
- `query_execution_runtime.py` 中 setter soup
  - 前提：bindings 模块落位
- `GoalService` 的 `dispatch_goal_*` 多变体
  - 前提：行业激活/启动直接物化正式 planning 链，不再经过 goal-dispatch
- `workflows/service_runs.py` 中 `launch_template/resume_run` 与 `goal-dispatch` 耦合
  - 前提：剩余 workflow 调用方迁到 Native Fixed SOP Kernel / runtime automation
- `startup_recovery.py` 中 `_recover_legacy_execution_core_chat_writebacks`
  - 前提：清库或迁移完成，确认旧残留不会再出现

#### 5.7.3 暂不动

- `child_run_shell.py`
- `runtime_service_graph.py`
  - 允许后续再压缩，但本轮先只保证 bootstrap 不再承载领域逻辑扩散

---

## 6. 实施顺序

### 阶段 0. 施工前提

1. 不在当前多人并行写的根工作区直接开拆。
2. 必须切到干净隔离 worktree。
3. 所有 writer agent 以“互斥写集合”分工。

### 阶段 1. 先删最值钱的语义残留

目标：

- 彻底移除 `current_goal*`
- 让 `current_focus*` 成为唯一正式可见焦点

涉及：

- `kernel/agent_profile.py`
- `kernel/agent_profile_service.py`
- `state/repositories/sqlite_governance_agents.py`
- `industry/service_runtime_views.py`
- `console/src/pages/AgentWorkbench/**`

### 阶段 2. Runtime Center 读写拆边界

目标：

- 拆 `runtime_center_shared.py`
- 拆 `state_query.py`
- 拆 `overview_cards.py`

### 阶段 3. Formal Planning 合同收口

目标：

- `service_compiler.py` 只传 typed constraints / typed assignment input
- `cycle_planner.py` 和 `report_replan_engine.py` 按边界拆开

### 阶段 4. Industry 领域拆显式协作者

目标：

- lifecycle / runtime-views / strategy 不再靠 mixin 巨文件承载主复杂度

### 阶段 5. Kernel 执行闭环压路径

目标：

- TurnExecutor 只做 turn orchestration
- QueryExecutionRuntime 只保留总控和组合

### 阶段 6. 环境 bridge 词汇退役 + workflow 前门退役

目标：

- 正式切到 host/session/companion vocabulary
- 删除旧 route/request model 名称
- 删除 `workflow-templates/workflow-runs` root front-door

### 阶段 7. 删除最后的过渡 re-export 和 compat 包装

目标：

- 删除旧 exports
- 删除旧 helper forwarding
- 删除不再被引用的测试兼容数据

---

## 7. 6 Agent 实施拆分

后续真正施工时，按以下互斥写集合拆：

### Agent 1. Agent Focus / Schema Cleanup

写集合：

- `src/copaw/kernel/agent_profile.py`
- `src/copaw/kernel/agent_profile_service.py`
- `src/copaw/state/repositories/sqlite_governance_agents.py`
- `console/src/pages/AgentWorkbench/**`

### Agent 2. Runtime Center Shared Split

写集合：

- `src/copaw/app/routers/runtime_center_shared.py`
- 新增 `runtime_center_request_models.py`
- 新增 `runtime_center_dependencies.py`
- 新增 `runtime_center_mutation_gateway.py`
- 新增 `runtime_center_payloads.py`
- 新增 `runtime_center_sse.py`

### Agent 3. Formal Planning Contract Split

写集合：

- `src/copaw/goals/service_compiler.py`
- `src/copaw/compiler/planning/strategy_compiler.py`
- `src/copaw/compiler/planning/cycle_planner.py`
- `src/copaw/compiler/planning/assignment_planner.py`
- `src/copaw/compiler/planning/report_replan_engine.py`
- `src/copaw/compiler/planning/models.py`
- 必要时 `tests/compiler/**`
- `tests/app/test_goals_api.py`
- `tests/app/test_predictions_api.py`

### Agent 4. Runtime Center Read Projection Split

写集合：

- `src/copaw/app/runtime_center/state_query.py`
- 新增 `task_projection.py`
- 新增 `human_assist_projection.py`
- 新增 `work_context_projection.py`
- 新增 `goal_projection.py`
- 新增 `decision_projection.py`

### Agent 5. Runtime Center Overview Split

写集合：

- `src/copaw/app/runtime_center/overview_cards.py`
- 新增 `overview_card_support.py`
- 新增 `overview_entry_builders.py`
- 新增 `overview_main_brain.py`
- 新增 `overview_capability_governance.py`
- 必要前端 Runtime Center 只读适配

### Agent 6. Industry + Kernel + Workflow Retirement

写集合：

- `src/copaw/industry/service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/industry/service_runtime_views.py`
- `src/copaw/industry/service_cleanup.py`
- 新增 `planning_materialization.py`
- 新增 `execution_kickoff.py`
- 新增 `report_processing.py`
- 新增 `cycle_runner.py`
- 新增 `planning_surface_views.py`
- 新增 `execution_summary_views.py`
- 新增 `instance_detail_projection.py`
- `src/copaw/kernel/turn_executor.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/main_brain_orchestrator.py`
- 新增 `turn_interaction_mode.py`
- 新增 `turn_service_bindings.py`
- 新增 `query_execution_bindings.py`
- 新增 `query_execution_resume.py`
- 新增 `query_execution_context.py`
- 新增 `query_execution_state.py`
- `src/copaw/app/routers/runtime_center_routes_ops.py`
- `src/copaw/app/routers/workflow_templates.py`
- `src/copaw/workflows/service_runs.py`
- `src/copaw/app/startup_recovery.py`
- `src/copaw/app/routers/runtime_center_shared.py` 中 bridge request model 改动需和 Agent 2 串行交接

必须串行的文件：

- `src/copaw/app/routers/runtime_center_shared.py`
- `src/copaw/industry/service.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/goals/service_compiler.py`
- `src/copaw/compiler/planning/models.py`

---

## 8. 验收标准

### 8.1 代码结构验收

必须满足：

- `service_lifecycle.py` 不再超过当前体量的一半级别
- `service_runtime_views.py` 不再同时承担 planning surface + execution summary + detail projection
- `overview_cards.py` 不再同时承担 cockpit + entry builder + summary builder
- `runtime_center_shared.py` 被拆空或删除
- `turn_executor.py` 和 `query_execution_runtime.py` 的 setter/binding 逻辑已抽离
- `service_compiler.py` 不再平铺 `strategy_*` alias 再回组 typed contract
- `cycle_planner.py` 与 `report_replan_engine.py` 的边界已拆开

### 8.2 语义收口验收

必须满足：

- `current_goal_id/current_goal` 不再出现在正式 product/model/repository/front-end 类型中
- runtime focused summary 不再依赖 `fallback_goal`
- host/session front-door 不再暴露 `bridge/*` 旧词汇
- `/workflow-templates` 与 `/workflow-runs` 不再是正式 root front-door
- `report_replan` 只保留正式 typed 字段，不再靠 dump-time 注入

### 8.3 测试验收

至少补和回归以下面：

- agent visible model / runtime profile projection
- industry instance detail / current focus / focused runtime view
- runtime center query/detail/overview
- kernel turn executor chat-vs-orchestrate split
- query execution resume / runtime persistence
- host/session environment ops route contract
- formal planning compiler / goal compiler / prediction planning contract

### 8.4 删除验收

本轮必须同时交付：

- 新模块
- 旧壳删除
- 删除说明写入 `TASK_STATUS.md`

如果只新增不删除，则本轮视为未完成。

---

## 9. 非目标

本轮不做：

- 新 planning 能力扩展
- 新 front-end 大功能
- 新 memory truth
- 新 environment truth

只做实现层收口。

---

## 10. 结论

当前系统“看起来乱”，不是因为主链没定，而是因为实现层还残留：

- mixin 巨文件
- shared 总线
- goal 旧语义回填
- bridge 旧词汇
- runtime/bindings/persistence 混装

所以本轮的正确做法不是再补新功能，而是按本设计完成一次真正的实现层硬收口。
