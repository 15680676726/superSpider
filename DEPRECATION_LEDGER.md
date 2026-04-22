# DEPRECATION_LEDGER.md

本文件用于记录 `CoPaw` 在“理想载体升级”过程中所有需要逐步退役、兼容、迁移、删除的旧模块与历史结构。

本文件的目标不是记录“未来可能会删什么”，而是明确：

- 哪些旧模块已经进入退役阶段
- 它们为什么需要退役
- 由谁替代
- 在哪个阶段删除
- 删除前提和验收标准是什么

> 原则：
>
> - 不允许没有删除条件的兼容代码长期存在
> - 不允许旧模块和新模块长期双真相源
> - 删除旧代码是正式交付物，不是附带动作

---

## 1. 状态定义

每个条目使用以下状态之一：

- `active`
  - 仍是现网主实现，尚未进入退役流程
- `frozen`
  - 不再承接新设计，仅允许必要 bugfix
- `bridged`
  - 已通过兼容层接到新系统，但旧实现仍在
- `dual-write`
  - 新旧系统短期双写，仅允许极短期存在
- `read-only-compat`
  - 旧模块只读兼容，不再写入真相源
- `ready-to-delete`
  - 满足删除条件，可删
- `deleted`
  - 已删除

---

## 2. 删除判定铁律

满足以下任一条件的旧模块，应优先进入删除名单：

- 继续持有核心运行真相
- 继续直接驱动主运行链
- 继续扩散 `skill / MCP / tool` 多语义分裂
- 与新内核产生长期双写
- 已经被新架构完全替代但尚未清理

---

## 3. 当前遗留台账

## 3.0 `2026-03-25` 硬切自治重构基线

- 当前仓库已进入一次性 `hard-cut autonomy rebuild` 维护窗口。
- 本窗口内的原则不是“继续桥接更多兼容层”，而是：
  - 清掉旧 runtime artifacts
  - 停掉旧主脑规划真相
  - 删除旧聊天后台写回旁路
  - 删除 app-name / keyword first 的写死路由心智
- 当前 hard-cut reset 入口：
  - `scripts/reset_autonomy_runtime.py`

### 3.0.1 `state/phase1.sqlite3 / evidence/phase1.sqlite3 / learning/phase1.sqlite3 / memory/qmd`

- 当前状态：`ready-to-delete`
- 问题：这些 runtime artifacts 来自旧混合主链，会把 Phase 1 历史状态、旧 evidence、旧 learning 与旧 memory residue 带入新的自治内核
- 目标替代：硬切后的 clean boot runtime
- 删除阶段：`hard-cut Task 1`
- 删除前提：
  - operator 已接受本系统未正式上线，历史数据允许直接删除
  - reset 脚本与 dry-run 检查已存在
- 删除方式：
  - 使用 `scripts/reset_autonomy_runtime.py`
  - 默认 dry-run 列出可清理对象，确认后再执行真实删除

### 3.0.2 旧主脑规划真相：`GoalRecord / active goals / schedules`

- 当前状态：`bridged`
- 问题：旧 `goal/task/schedule` 路径仍承载一部分主脑规划语义，导致与 `lane/backlog/cycle/assignment/report` 长期双主线
- 目标替代：
  - `StrategyMemoryRecord`
  - `OperatingLaneRecord`
  - `BacklogItemRecord`
  - `OperatingCycleRecord`
  - `AssignmentRecord`
  - `AgentReportRecord`
- 删除阶段：`hard-cut Task 3`
- 删除前提：
  - operator turn 已不再把长期目标直接 materialize 成 active goal
  - `/industry`、Runtime Center、Chat、AgentWorkbench 已统一消费新的控制链读面
- 删除方式：
  - 先切主脑正式写链
  - 再把 `GoalRecord` 降级为 phase/leaf object 或直接删除
  - 最后删除旧 goal-first planning materialization 逻辑
- `2026-03-25` 补充：
  - operator 主入口、chat writeback、`/industry`、Runtime Center、AgentWorkbench 已全部改为消费 `strategy / lane / backlog / cycle / assignment / report`
  - 当前 repo 内残留的 `GoalRecord` / `/goals` / `dispatch_active_goals` 仅保留执行层 phase/leaf object 语义，不再承担主脑规划真相
  - execution-core baseline capability、runtime query system tool registry、Runtime Center actor capability surface、automation scheduler 已全部停止暴露 `dispatch_active_goals`
  - execution-core baseline capability、runtime query tool registry、prompt capability projection 与 Runtime Center actor capability surface 也已停止暴露 `dispatch_goal`；该能力只允许留在 goal service / workflow / prediction 等执行层内部叶子边界
  - `POST /goals/{goal_id}/dispatch`、`POST /goals/automation/dispatch-active`、`POST /runtime-center/goals/{goal_id}/dispatch` 已物理删除，不再保留 retired shell
  - `POST /capabilities/{id}/execute`、`POST /routines/{routine_id}/replay`、`POST /predictions/{case_id}/recommendations/{recommendation_id}/execute`、`POST /workflow-templates/{template_id}/launch`、`POST /workflow-runs/{run_id}/resume`、`POST /runtime-center/replays/{replay_id}/execute`、`POST /runtime-center/chat/orchestrate` 已物理删除；`_main_brain_boundary.py` 兼容壳已清空并删除

### 3.0.5 runtime-center 旧直接委派入口：`POST /runtime-center/tasks/{task_id}/delegate`

- 当前状态：`deleted`
- 问题：该入口来自旧“人类直打执行位”心智，即使退役成 `410` 壳，也会继续让产品层保留错误心智
- 目标替代：
  - `MainBrainOrchestrator`
  - `AssignmentRecord`
  - `DelegationService`
- 删除阶段：`hard-cut Task 9`
- 删除前提：
  - runtime-center、Chat、`/industry` 已统一走主脑编排入口
  - child task / delegation 继续只允许在 kernel / system capability 内部触发
- 删除方式：
  - `2026-03-25` 已从 `runtime_center_routes_core.py` 物理删除该 HTTP 路由
  - 前台 direct delegate 心智正式下线

### 3.0.6 legacy runtime 焦点键：`goal_id / goal_title / current_goal*`

- 当前状态：`read-only-compat`
- 问题：旧 `goal_*` 焦点键如果继续作为 live runtime writer contract，会让 `current_focus_*` 与 legacy goal 文本长期双语义并存
- 目标替代：
  - `current_focus_kind`
  - `current_focus_id`
  - `current_focus`
- 删除阶段：`execution-discipline closure`
- 删除前提：
  - runtime metadata writer 不再持久化 `goal_id / goal_title`
  - Runtime Center / Agent Workbench / conversations / industry detail 正式只消费 `current_focus_*`
  - mailbox / checkpoint 的历史兼容读被专项迁移或自然淘汰
- 删除方式：
  - `2026-04-03` 已切掉 `industry/service_team_runtime.py` 对 `goal_id / goal_title` 的 runtime metadata 双写
  - 当前仅保留 `AgentProfileService` 的兼容读，用于历史 mailbox/checkpoint payload；待历史数据迁完后物理删除 compatibility fallback

### 3.0.3 `MainBrainChatService` 后台 `writeback / kickoff`

- 当前状态：`frozen`
- 问题：聊天链仍可在后台触发 durable runtime mutation，导致“纯聊天”与“正式编排”边界不清
- 目标替代：`MainBrainOrchestrator`
- 删除阶段：`hard-cut Task 2`
- 删除前提：
  - `KernelTurnExecutor` 已把 formal execute turn 统一交给 orchestrator
  - `MainBrainChatService` 只保留聊天、澄清、状态解释与建议输出
- 删除方式：
  - 删除 chat 内的后台 writeback / kickoff
  - 所有 durable write 统一经 orchestrator

### 3.0.4 app-name / keyword first 路由 token 表

- 当前状态：`frozen`
- 问题：`service_context.py` 中的桌面/浏览器/app 名关键词表会把未知应用错误绑定到写死语义，无法支撑真正的 surface-first 路由
- 目标替代：`CapabilityMount + active environment + surface` 优先的 formal routing
- 删除阶段：`hard-cut Task 5`
- 删除前提：
  - desktop/browser/file 等 surface 已能根据挂载能力、环境与 surface 直接路由
  - 关键词表只剩 fallback 兜底而不再承担主判断
- 删除方式：
  - 先引入新的 surface router
  - 再把 token 表从 primary routing 降级为 fallback heuristics

---

## 3.1 核心运行链

### 3.1.1 `src/copaw/app/runner/runner.py`

- 当前状态：`deleted`
- 问题：该旧宿主壳曾承载 query lifecycle、命令分流、session/memory 生命周期等历史职责；在 `V3-B4` 中已完成真实退役
- 删除完成情况：
  - `2026-03-12` 已删除 `src/copaw/app/runner/runner.py`
  - `2026-03-14` 已删除 `src/copaw/app/runner/` 剩余 utility compat（`command_dispatch / daemon_commands / session / utils / query_error_dump`）并移除整个旧目录
  - `_app.py` 现直接装配 `RuntimeHost + KernelQueryExecutionService + KernelTurnExecutor`
  - `app.state.runner` 已删除，direct `/api/agent/process` 继续由 `src/copaw/app/agent_runtime.py` 与本地 `_local_tasks` 承接
  - 环境 lease/recovery/replay 主语义已迁入 `RuntimeHost + EnvironmentService`
- 目标替代：`RuntimeHost + KernelTurnExecutor + KernelQueryExecutionService + SRK`
- 删除阶段：`V3-B4`
- 验收口径：
  - 代码树中不再存在 `src/copaw/app/runner/runner.py`
  - `AgentRunner`、`app.state.runner` 与 runtime-center bridge fallback 在 `src/copaw/app`、`console/src`、`tests` 中均无残留引用

### 3.1.2 `src/copaw/app/_app.py`

- 当前状态：`active`
- 问题：承担大量系统装配与状态挂载职责，容易成为历史总线
- 目标替代：边缘接入壳 + `SRK` 生命周期装配器
- 计划阶段：
  - `Phase 4` 之后逐步降级为壳层
- 删除前提：
  - 核心运行状态不再在 `app.state` 中散落托管
- 删除方式：
  - 不一定整体删除
- 但必须移除“内核事实源”地位

### 3.1.3 本地多 agent 执行脑：`actor_worker / actor_supervisor / actor_mailbox / models_agents_runtime`

- 当前状态：`frozen`
- 问题：
  - 这套对象和服务正在承载本地多执行位正式真相
  - 与新方向“外部执行体替代本地多 agent 执行层”直接冲突
- 目标替代：
  - `ExecutorProvider`
  - `ExecutorRuntimeInstance`
  - `ExecutorThreadBinding`
  - `ExecutorTurnRecord`
  - `ExecutorEventRecord`
- 删除阶段：`external-executor hard-cut`
- 删除前提：
  - `ExecutorRuntime` 主链已跑通
  - Runtime Center 已改读 executor runtime truth
  - 新写链已不再写入 actor runtime 真相
- 删除方式：
  - 先停新写
  - 再把 actor runtime 降为 `read-only-compat`
  - 最后物理删除
- `2026-04-20` 落点补充：
  - 第一条正式替代接缝已经落地，但还没有完成 cutover：
    - `3c2327c`：`models_executor_runtime.py` + `executor_runtime_service.py`
    - `d772861`：generic executor protocol taxonomy baseline
    - `155c6b6`：`executor_runtime_port.py` + `Codex App Server` first adapter
    - `a73cace`：`executor_event_ingest_service.py` + focused ingest tests
  - 当前工作树继续把 Task 5 推到 focused mainline：
    - `executor_event_writeback_service.py`
    - `runtime_coordination.py` 的 background event drain
    - `AgentReportService.record_structured_report(...)`
    - `runtime_service_graph.py` / `runtime_bootstrap_execution.py` 的 writeback wiring
  - 当前工作树继续把 Task 6 推到 focused projection：
    - Runtime Center external runtime list/detail 优先读 executor runtime truth
    - query bootstrap 已显式挂接 `executor_runtime_service`
  - 但因为 actor runtime 仍存在于启动图、`delegation_service.py` 仍承担正式派单链、Runtime Center overview/control 仍保留旧 actor 读面，所以这组本地 actor runtime 仍不能写成 `ready-to-delete`
- `2026-04-21` actor runtime compatibility 补充：
  - `runtime_center_routes_actor.py` 已删除 actor pause/resume/retry/cancel 与 actor capability mutation 路由
  - actor payload 已显式标记 `compatibility_mode = read-only-compat`
  - RuntimeExecutionStrip / AgentWorkbench 已删除 actor control affordance，capability governance 统一切到 agent formal surface
  - 当前条目可正式表述为：actor runtime 在 Runtime Center / Agent Workbench 链路上已降到 `read-only-compat`
  - 当前剩余边界不变：启动图仍保留 actor runtime，`delegation_service.py` 仍未退役，因此本条目继续保持 `frozen`，不得提前标记为 `ready-to-delete`
- `2026-04-22` 状态补充：
  - `runtime_bootstrap_execution.py` / `runtime_service_graph.py` 现已把 actor runtime 收进显式 compatibility wiring；default formal bootstrap 不再默认装配 `actor_mailbox_service / actor_worker / actor_supervisor`
  - `_app.py` 现只会在 actor supervisor 被显式装配时启动 actor runtime lifecycle
  - 因此 actor runtime 已退出 default formal startup graph；旧 `/runtime-center/actors*` 显式读面现也已被物理删除，但 compatibility codepath 与 actor kernel 文件仍在；本条目继续保持 `frozen`，不得误写成 `deleted`
  - `2026-04-22` 验收补充：
    - formal external-provider intake 现已通过真实 `Codex App Server` live smoke，且 `python scripts/run_p0_runtime_terminal_gate.py` 已 fresh 通过
    - 因此 actor runtime compatibility surface 已不再阻塞 external-executor hard-cut 的终态完成声明；但物理删除仍是后续退役事项，本条目继续保持 `frozen`
  - `2026-04-22` 晚间退役补充：
    - `src/copaw/app/routers/runtime_center_routes_actor.py` 与 `src/copaw/app/routers/runtime_center_shared_actor.py` 已物理删除
    - formal `kernel task / decision / agent capability` 路由已拆分到 `runtime_center_routes_governance.py` 与 `runtime_center_routes_agents.py`
    - `runtime_center_payloads.py`、`agent_profile_service.py`、`capabilities/install_templates.py`、`capabilities/system_actor_handlers.py` 已停止生成 `/api/runtime-center/actors/*` dead routes
    - 但 `actor_mailbox.py` / `actor_worker.py` / `actor_supervisor.py` 及 overview/startup compatibility wiring 仍在，因此本条目状态不变，继续保持 `frozen`
  - `2026-04-22` gate-repair 补充：
    - `RuntimeBootstrap` / `RuntimeDomainServices` 已删除 formal `actor_mailbox_service / actor_worker / actor_supervisor / delegation_service` 暴露位
    - `src/copaw/app/_app.py` 与 `src/copaw/app/runtime_lifecycle.py` 默认生命周期已停止通过 startup recovery 传递 actor mailbox / exception absorption，也不再在 default app lifecycle 中启动或停止 actor supervisor
    - Runtime Center formal `agents` 与 `learning governance` 路由已恢复到 `runtime_center_routes_agents.py` / `runtime_center_routes_governance.py`，default gate 已重新通过
    - 但 actor kernel 文件本体仍在，且 browser / desktop / document-file-shell product surface 仍未替换，因此本条目继续保持 `frozen`
  - `2026-04-23` runtime-center fallback 补充：
    - `RuntimeCenterAppStateView` 已删除 `actor_worker_runtime_contract / actor_supervisor_runtime_contract`
    - `overview_cards.py` main-brain governance 已停止在 query entropy 缺失时回退读取 actor runtime-contract sidecar memory
    - 因此 Runtime Center formal governance 读面已不再把 actor runtime contract 当 sidecar-memory 真相；但 actor supervisor snapshot / exception_absorption 读面与 actor kernel 文件仍在，本条目继续保持 `frozen`
  - `2026-04-23` main-brain card 补充：
    - `overview_main_brain.py` 已停止读取 `actor_supervisor_snapshot / actor_supervisor.snapshot()` 来生成 `exception_absorption`
    - Runtime Center main-brain card summary / meta / control-chain 已不再输出 actor supervisor exception-absorption 摘要
    - 因此 Runtime Center formal main-brain 读面已不再把 actor supervisor snapshot 当正式治理真相；但 actor kernel 文件、actor capability compatibility surface 与 mailbox continuity 兼容链仍在，本条目继续保持 `frozen`
  - `2026-04-23` capability surface 补充：
    - `src/copaw/capabilities/system_actor_handlers.py` 已物理删除
    - `CapabilityService` / `SystemCapabilityHandler` 已删除 formal actor setter 与 actor-capability dispatch 残口
    - `predictions/service_recommendations.py` 已停止输出 `system:pause_actor`，高负载执行位只会提示 `manual:coordinate-main-brain`
    - 因此 formal actor capability surface 已不再处在 capability execution 主链；但 actor kernel 文件、`main_brain_chat_service.py` / `query_execution_runtime.py` 的 compatibility 接线与 mailbox continuity 链仍在，本条目继续保持 `frozen`
  - `2026-04-23` automation read-surface 补充：
    - `runtime_center/models.py` 已删除 `actor_supervisor_overview` 与 `actor_supervisor_snapshot()` 读桥
    - `overview_cards.py` 已停止输出 `main_brain.automation.supervisor`
    - Runtime Center / self-check 共用 automation 摘要现在只看 `loops + schedules + heartbeat`，不再把 actor supervisor health 当正式 automation 真相
    - 因此 actor supervisor automation 读面已退出 Runtime Center formal surface；但 `main_brain_chat_service.py`、`query_execution_runtime.py` 与 actor kernel 文件本体仍在，本条目继续保持 `frozen`
  - `2026-04-23` prompt/checkpoint 补充：
    - `main_brain_chat_service.py` 已停止把 `actor_supervisor.snapshot()` / exception-absorption summary 注入 pure-chat prompt 与 prompt-context signature
    - `query_execution_runtime.py` / `query_execution_context_runtime.py` 已改用 `agent_checkpoint_repository` 作为 formal checkpoint read/write truth，并删除 `KernelQueryExecutionService.set_actor_mailbox_service(...)`
    - 因此主脑纯聊天与 query checkpoint 主链已不再依赖 actor supervisor / actor mailbox compatibility；但 `actor_mailbox.py / actor_worker.py / actor_supervisor.py` 文件本体及若干 compatibility path 仍在，本条目继续保持 `frozen`
  - `2026-04-23` runtime-center dependency 补充：
    - `runtime_center_dependencies.py` 已删除 `_get_actor_mailbox_service(...)` 与 `_get_actor_supervisor(...)`
    - Runtime Center dependency module 不再为 actor compatibility service 保留专门 getter；formal DI surface 现在只保留 state-query / repository / governance getter
    - 但 Runtime Center actor compatibility API、startup recovery 与 delegation compatibility path 仍直接使用 actor kernel 文件，本条目继续保持 `frozen`
  - `2026-04-23` runtime-center payload 补充：
    - `runtime_center_payloads.py` 已删除 `_actor_mailbox_payload(...)` dead helper
    - Runtime Center payload module 不再保留 actor mailbox compatibility serializer，只剩 actor runtime compatibility payload 与 formal payload serializer
    - 但 actor mailbox / supervisor compatibility 仍在其他产品面和 kernel 文件中使用，本条目继续保持 `frozen`
  - `2026-04-23` formal capability helper 补充：
    - `runtime_center_actor_capabilities.py` 已删除 `_assign_agent_capabilities(...)` / `_submit_governed_capabilities(...)` 的 `require_actor` dead flag
    - `runtime_center_routes_agents.py` 也已停止向 formal agent capability helper 透传 `require_actor=False`
    - Runtime Center formal agent capability surface 不再保留已无调用方的 actor-only 分支；但 actor kernel 文件与 compatibility path 仍在，本条目继续保持 `frozen`
  - `2026-04-23` bootstrap domain parameter 补充：
    - `runtime_bootstrap_domains.py` 已删除 `actor_supervisor` 形参，`runtime_service_graph.py` 也不再透传该值
    - default bootstrap domain build path 不再保留 actor supervisor dead parameter；但 actor mailbox / supervisor compatibility path 与 kernel 文件本体仍在，本条目继续保持 `frozen`

### 3.1.4 `src/copaw/kernel/delegation_service.py`

- 当前状态：`frozen`
- 问题：
  - 它不是普通工具层，而是 child-task / mailbox / run-once 的正式派单链
  - 如不先补 `Assignment -> ExecutorRuntime -> Event -> Evidence/Report` 主链，直接删除会断派工
- 目标替代：
  - `MainBrainOrchestrator`
  - `ExecutorRuntimePort`
  - `ExecutorEventIngestService`
- 删除阶段：`external-executor hard-cut`
- 删除前提：
  - assignment 已能直接派发到 executor runtime
  - evidence/report 回流主链已稳定
- 删除方式：
  - 先把正式派单链切到 executor runtime
  - 再删除旧 delegation 执行分支
- `2026-04-20` 落点补充：
  - `Codex` first adapter 与 event-ingest slice 已经落地，但 `delegation_service.py` 仍是正式派单链的一部分。
  - 当前工作树里的 executor coordination / event writeback 主链已经能在 focused regression 下回写 evidence/report，但这仍不等于 `delegation_service.py` 已退役。
  - 在 `Assignment -> ExecutorRuntime -> Event -> Evidence/Report` 主链落地前，本条目继续维持 `frozen`，不得提前标记为已退役。
- `2026-04-21` 状态补充：
  - actor runtime 前端/路由侧虽然已降到 `read-only-compat`，但 `delegation_service.py` 的正式派单地位并未在本轮变化
  - 因此 delegation 仍是 external-executor hard-cut 的后续删除项，而不是本轮已完成删除项
  - execution-core baseline capability、industry compiler baseline、query runtime 默认 system capability allowlist、prompt capability projection 与 delegation-first prompt 文案，现已全部停止把 `system:delegate_task` 当 execution-core 默认正式能力暴露
  - `capabilities/sources/system.py` 已把 `system:delegate_task` 明确标记为 local child-task delegation compatibility alias
  - focused compatibility regression 仍证明显式 `system:delegate_task` / `TaskDelegationService` 链可以工作；因此本条目当前状态继续保持 `frozen`，不能误写成 `read-only-compat` 或 `ready-to-delete`
  - 删除前提不变：必须先让 assignment formal execution backend 完整收口到 executor runtime，再删除本地 delegation 执行分支
- `2026-04-21` 最终收口补充：
  - `src/copaw/kernel/main_brain_orchestrator.py` 现在会在 formal assignment + executor runtime coordination 成功时直接返回 executor-runtime ack stream，不再继续把同一条 assignment 落回本地 `query_execution_service.execute_stream(...)`
  - 因此 `delegation_service.py` 已不再是 primary assignment execution backend；formal assignment write path 现在锚定到 `Assignment -> ExecutorRuntime -> Event -> Evidence/Report`
  - `delegation_service.py` 仍保留为显式 compatibility child-task backend，且 child-task / mailbox / experience metadata 现统一标记 `execution_source = delegation-compat`
  - 当前状态因此仍保持 `frozen`：formal-backend retirement 已完成，但物理删除与显式 compatibility capability 退役尚未完成
- `2026-04-22` 状态补充：
  - child-task / mailbox / resume payload / Runtime Center child rollup 现统一补齐：
    - `execution_source = delegation-compat`
    - `formal_surface = false`
    - `compatibility_mode = delegation-compat`
  - 因此 delegation compatibility run 不再伪装成 formal assignment child backend；但 `delegation_service.py` 仍会创建 compatibility child task，因此本条目继续保持 `frozen`
  - `2026-04-22` 验收补充：
    - formal assignment -> executor-runtime mainline、formal provider intake live smoke、以及 default regression gate 现都已 fresh 通过
    - 因此 `delegation_service.py` 剩余的 compatibility child-task 能力不再阻塞 external-executor hard-cut 终态收口；但物理删除与 capability 退役仍属于后续删除项
  - `2026-04-22` 晚间退役补充：
    - `query_execution_tools.py` 已物理删除 `delegate_task` formal tool builder
    - `query_execution_prompt.py` 与 `query_execution_runtime.py` 不再把 `system:delegate_task` 当 formal query front-door 条件或提示文案
    - `delegation_service.py` compatibility result 也已停止返回已删除的 actor mailbox route
    - execution-core formal query front-door 现只保留 `dispatch_query / apply_role / discover_capabilities` 等正式 system-op surface；显式 `TaskDelegationService` compatibility chain 仍在
    - 因此本条目继续保持 `frozen`，不得误写成 `deleted`
  - `2026-04-22` gate-repair 补充：
    - `RuntimeBootstrap` 与 `RuntimeDomainServices` 已不再暴露 formal `delegation_service` field；default app lifecycle / startup recovery 也已不再依赖该 compatibility field
    - Runtime Center learning patch write path 已重新挂回 formal governance router，并显式关闭 main-brain auto-approval，恢复 `waiting-confirm` 审批语义
    - 但 `src/copaw/kernel/delegation_service.py` 文件与 compatibility-focused tests 仍在，本条目状态不变，继续保持 `frozen`
  - `2026-04-22` capability-plumbing 补充：
    - `CapabilityService` 已删除 formal `delegation_service` constructor field 与 `set_delegation_service(...)` public setter
    - `SystemCapabilityHandler` / `SystemTeamCapabilityFacade` 已删除 formal `system:delegate_task` dispatch branch 与 `handle_delegate_task(...)` facade
    - `CapabilityExecutionFacade` 也已删除仅为 `system:delegate_task` 保留的环境继承特判
    - 但 `src/copaw/kernel/delegation_service.py` 文件、本地 task-delegation compatibility API、以及 mailbox child-task continuity 兼容链仍在，因此本条目继续保持 `frozen`

### 3.1.5 donor-first 外接项目产品面：`/capability-market/projects/install*`、`project donor` taxonomy、Runtime Center donor 读面

- 当前状态：`frozen`
- 问题：
  - 这套产品面仍保留“任意 GitHub 项目 donor / project-package / adapter / runtime-component”心智
  - 与新方向“只对接受控执行体 runtime provider”冲突
  - Runtime Center 里 donor 候选供给面和 active executor 读面仍未彻底拆开
- 目标替代：
  - `ExecutorProvider`
  - `ExecutorRuntimeInstance`
  - `RoleExecutorBinding`
  - `ModelInvocationPolicy`
- 删除阶段：`external-executor hard-cut`
- 删除前提：
  - executor provider intake 已有正式入口
  - donor/state/runtime center 旧读面已标注 compatibility 或完成拆分
- 删除方式：
  - 先给 donor-first 路由、文档、测试补 `compatibility/acquisition-only` 标记
  - 再把 active execution 语义迁出
  - 最后删除不再需要的 project-donor 产品壳
- `2026-04-20` 落点补充：
  - 当前 generic executor runtime taxonomy 已开始替代 donor-first active runtime taxonomy。
  - 但 `/capability-market/projects/install*`、`project-package / adapter / runtime-component`、donor state/trust/trial/retirement、Runtime Center donor 读面仍是 compatibility/acquisition-only 遗留，尚未完成正式拆分。
- `2026-04-21` 状态补充：
  - 本轮 actor runtime compatibility 收口未继续推进 donor/project intake 边界
  - 因此本条目状态保持不变：仍是 `compatibility/acquisition-only` 遗留，不得写成 formal executor provider 主链已闭环
  - 当前工作树已继续补上 donor/project intake 的 surface demotion：
    - `project_donor_contracts.py` 的 donor contract metadata / projected package metadata 现显式带 `compatibility_mode = compatibility/acquisition-only` 与 `formal_surface = false`
    - `/capability-market/projects/search`、`/projects/install*` 与 Runtime Center donor/package projection 现都会返回同一 compatibility 标记，避免再被误读成 canonical executor-provider surface
    - Runtime Center donor/package projection 也已兼容 dict-backed service payload，避免 donor 读面只因 projection 形态不同就静默掉数据
  - 但这仍只是 compatibility 标记收口，不是 formal executor provider intake 完整替代；本条目状态因此继续保持 `frozen`
- `2026-04-21` 最终收口补充：
  - `src/copaw/app/routers/capability_market.py` 已新增：
    - `GET /capability-market/executor-providers/search`
    - `POST /capability-market/executor-providers/install`
  - `src/copaw/app/runtime_center/state_query.py` / `src/copaw/state/executor_runtime_service.py` / executor runtime repository 现已支持 formal provider inventory read path
  - 因此 formal `ExecutorProvider / control_surface_kind / default_protocol_kind` intake 已落地，donor/project install 不再是唯一也不再是假装 canonical 的 executor intake 前门
  - 但 donor/project product shell、donor state/trust/trial/retirement taxonomy 与 compatibility/acquisition-only 路由仍在；本条目因此继续保持 `frozen`，不得误写成“donor-first 产品面已删除”
- `2026-04-22` 状态补充：
  - `project_donor_contracts.py` 现把 nested `execution_shell` 也统一标记为 `compatibility/acquisition-only`
  - Capability Market project install result 的 `runtime_contract` 与 Runtime Center donor projection 的 nested `runtime_contract` 现都会显式带：
    - `compatibility_mode = compatibility/acquisition-only`
    - `formal_surface = false`
  - donor/project shell 因此不再返回“裸 runtime_contract”误导前台把 acquisition-only surface 当 active execution shell；但 donor-first taxonomy 与路由仍在，本条目继续保持 `frozen`
  - `2026-04-22` 验收补充：
    - `/capability-market/executor-providers/search` 与 `/executor-providers/install` 现已通过真实 external-provider smoke，formal provider intake 已不再依赖 donor/project 产品壳做真实性证明
    - 因此 donor/project compatibility/acquisition-only surface 已不再阻塞 external-executor hard-cut 终态完成；但 donor-first taxonomy、旧产品壳与路由删除仍是单独 follow-up

### 3.1.6 本地 browser 执行层：`src/copaw/agents/tools/browser_control.py`、`src/copaw/capabilities/browser_runtime.py`、`src/copaw/environments/surface_execution/browser/service.py`

- 当前状态：`frozen`
- 问题：
  - 这条链仍把本地 browser actuation 当成 CoPaw 自带执行脑的一部分
  - 与“外部执行体负责执行、CoPaw 保留主脑真相”的 hard-cut 方向冲突
- 目标替代：
  - `ExecutorRuntimePort`
  - 外部 executor browser-facing tool surface
  - executor event -> `EvidenceRecord / AgentReport`
- 删除阶段：`external-executor hard-cut follow-up`
- 删除前提：
  - executor runtime 主链已接管 browser 相关 assignment 执行
  - Runtime Center 已能显示 executor truth，而不是本地 browser runtime truth
- 删除方式：
  - 先停掉新的本地 browser-first 正式写链
  - 再把本地 browser actuation 降成 compatibility/fallback
  - 最后物理删除
- `2026-04-20` 落点补充：
  - `Codex App Server` first adapter 已落地，但 browser local execution 还没有被 executor runtime 正式接管。
  - 因此本条目继续是 retirement target，不得误记为已替代或已删除。
- `2026-04-22` 状态补充：
  - `query_execution_runtime.py` 现已把 execution-core formal front-door 上的本地 browser/file/shell/document tool capability ids 默认移除
  - 因此 browser local chain 不再作为 execution-core default formal surface 暴露；但 specialist/compatibility/internal path 仍在，本条目继续保持 `frozen`

### 3.1.7 本地 desktop 执行层：`src/copaw/agents/tools/desktop_actuation.py`、`src/copaw/adapters/desktop/windows_host.py`、`src/copaw/adapters/desktop/windows_mcp_server.py`、`src/copaw/environments/surface_execution/desktop/service.py`

- 当前状态：`frozen`
- 问题：
  - 这条链仍把 Windows/desktop 控制维持为本地主执行层
  - 一旦继续扩张，会与外部 executor runtime 形成第二套执行主链
- 目标替代：
  - `ExecutorRuntimePort`
  - 外部 executor desktop-facing control surface
  - executor event -> `EvidenceRecord / AgentReport`
- 删除阶段：`external-executor hard-cut follow-up`
- 删除前提：
  - 外部 executor 能承接 desktop 相关 assignment
  - 当前 desktop local runtime 不再承担正式主链写入
- 删除方式：
  - 先冻结新设计
  - 再把本地 desktop path 降成 compatibility/fallback
  - 最后物理删除
- `2026-04-20` 落点补充：
  - `Codex App Server` first adapter 已落地，但 desktop local execution 仍未切到 executor runtime 主链。
  - 因此本条目继续是 retirement target，不得误记为已替代或已删除。
- `2026-04-22` 状态补充：
  - execution-core formal front-door 现已不再默认暴露本地 desktop/document/browser/file tool capability ids
  - 因此 desktop local chain 不再作为 execution-core default formal surface 暴露；但本地 desktop compatibility path 仍在，本条目继续保持 `frozen`

### 3.1.8 本地 document 执行层：`src/copaw/agents/tools/document_surface.py`、`src/copaw/environments/surface_execution/document/service.py`

- 当前状态：`frozen`
- 问题：
  - 这条链仍把 document/file actuation 保留在本地主执行层
  - 与统一 `ExecutorRuntime` 接缝下的执行边界不一致
- 目标替代：
  - `ExecutorRuntimePort`
  - 外部 executor document/file-facing tool surface
  - executor event -> `EvidenceRecord / AgentReport`
- 删除阶段：`external-executor hard-cut follow-up`
- 删除前提：
  - executor runtime 已能承接 document/file assignment 执行
  - Runtime Center 与主脑读面不再依赖本地 document runtime
- 删除方式：
  - 先冻结新增设计
  - 再降级为 compatibility/fallback
  - 最后物理删除
- `2026-04-20` 落点补充：
  - `Codex App Server` first adapter 已落地，但 document/file local execution 仍未切到 executor runtime 主链。
  - 因此本条目继续是 retirement target，不得误记为已替代或已删除。
- `2026-04-22` 状态补充：
  - `query_execution_runtime.py` 现已停止在 execution-core formal front-door 默认暴露 `tool:read_file / tool:write_file / tool:execute_shell_command / tool:document_surface`
  - 因此 document/file local chain 已退出 execution-core default formal surface；但兼容执行链与底层 executor 仍在，本条目继续保持 `frozen`

---

## 3.2 状态与真相源

### 3.2.1 `config.json` 作为运行真相承载体

- 当前状态：`active`
- 问题：声明式配置与运行真相耦合
- 目标替代：
  - `config.*` 只保留声明式配置
  - `state.db` 承载运行真相
- 计划阶段：`Phase 1`
- 删除前提：
  - 新 store 已承载任务、运行态、证据索引
  - `config.*` 不再保存核心运行事实
- 删除方式：
  - 不是删除文件
  - 而是删除其作为“运行真相源”的职责

### 3.2.2 `jobs.json`

- 当前状态：`deleted`
- 问题：`jobs.json` 的主链 bootstrap/read fallback 已删除；运行主链不再读取该文件，残留文件需人工清理
- 目标替代：`state` 仓储中的 `Task / Schedule / TaskRuntime`
- 计划阶段：`Phase 1` -> `Phase 4`
- 删除前提：
  - 新调度模型可覆盖列表、暂停、恢复、触发、状态读取
  - `ScheduleRecord.spec_payload` 已能完整承载 cron 规格快照
  - 主链已经不再保留任何 `jobs.json` bootstrap/read path
- 删除方式：
  - 当前 runtime 读写已不再回流 `jobs.json`
  - repo 内 legacy delete-gate API/daemon/cleanup-only 已移除
  - 如有残留文件需人工删除

### 3.2.3 `chats.json`

- 当前状态：`deleted`
- 问题：`chats.json` 的主链 bootstrap/read fallback 已删除；`/chats/{id}` 已改走统一 snapshot/history path，不再依赖旧 JSON，残留文件需人工清理
- 目标替代：基于 `Task / TaskRuntime` 的统一 chat registry
- 计划阶段：`Phase 1`
- 删除前提：
  - `StateBackedChatRepository` 已稳定覆盖 list/get/create/update/delete
  - `/chats/{id}` 详情读取持续通过统一 history reader，而不是回退到手写 legacy 文件读取
  - 主链已经不再保留任何 `chats.json` bootstrap/read path
- 删除方式：
  - 当前 runtime 读写已不再回流 `chats.json`
  - repo 内 legacy delete-gate API/daemon/cleanup-only 已移除
  - 如有残留文件需人工删除

### 3.2.4 `sessions/`

- 当前状态：`deleted`
- 问题：steady-state 已完全收口到 Phase 1 SQLite session snapshot；legacy `sessions/*.json` 已退出主链，兼容壳也已删除，剩余风险仅是外部残留文件可能误导人工判断
- 目标替代：`session_state_snapshots / EnvironmentMount / replay storage / evidence replay`
- 计划阶段：`Phase 1` -> `Phase 3`
- 删除前提：
  - `load_session_snapshot` 已稳定覆盖会话恢复与 `/chats/{id}` 历史读取
  - 会话恢复不再依赖 JSON 落盘
  - legacy JSON 不再被 steady-state 路径命中
  - `_app.py` 不再给 session 注入 legacy write mode
  - `SafeJSONSession` 不再暴露 legacy write_mode/save_dir 兼容参数
  - replay 入口迁入统一环境/证据层
- 删除方式：
  - 2026-03-11 已删除 `src/copaw/app/legacy/` compatibility shell，并让 `SafeJSONSession` 收缩为纯 SQLite snapshot 存取实现
  - 如有残留文件需人工删除

### 3.2.5 `src/copaw/state/goal_repository.py`

- 当前状态：`deleted`
- 问题：该模块曾以独立 SQLite 与独立状态枚举承载 `Goal`，形成潜在双真相源
- 目标替代：`src/copaw/state/repositories/base.py` 中的 `BaseGoalRepository` 与 `src/copaw/state/repositories/sqlite.py` 中的 `SqliteGoalRepository`
- 计划阶段：`Phase 1`
- 删除前提：
  - `GoalRecord` 已通过统一 `state` repository 读写
  - 后续 Goal service / router 只允许接入 `state` 层
- 删除方式：
  - 2026-03-10 已删除独立文件 `src/copaw/state/goal_repository.py`
  - Goal 读写统一进入 `state` repository 集合
  - 后续若新增 Goal API/Service，只能继续接 `state` 层，不得再建平行存储

### 3.2.6 `src/copaw/app/bridges/phase1_runtime_bridge.py`

- 当前状态：`deleted`
- 问题：这是故意引入的 Phase 1 兼容桥，不应长期存在；该文件已于 2026-03-11 删除，chat/cron manager 写入现已直接落到 state-backed repository，query/tool evidence 由 `KernelToolBridge + EvidenceLedger` 承接
- 目标替代：`StateQueryService / EvidenceQueryService / SRK / KernelToolBridge`
- 原计划阶段：
  - `Phase 1~2` 作为过渡桥接层存在
  - `Phase 3~4` 随新服务稳定逐步收缩
- 删除完成条件：
  - `runner/chats/cron` 不再需要桥接才能写入新 state/evidence/schedule
  - `shell / file / browser` 证据接入统一走 `KernelToolBridge -> EvidenceLedger`
  - `state_query_service` 与 `evidence_query_service` 已可直接读取正式 service
- 删除方式：
  - 2026-03-11 已删除 bridge 文件与 `ChatManager / CronManager` 中的 shadow-sync hook
  - 相关验收由 `tests/app/test_chat_manager.py`、`tests/app/test_cron_manager.py`、`tests/app/test_runtime_query_services.py` 覆盖
  - 后续剩余债务转入 `AgentRunner` 宿主职责与 runtime-center 只读兼容元数据收缩

### 3.2.7 `src/copaw/app/legacy/write_policy.py`

- 当前状态：`deleted`
- 问题：该模块原本用于阻断 legacy 写路径扩散；随着 jobs/chats/sessions delete-gate 与 session compatibility shell 退役，它已不再需要
- 目标替代：新 state / evidence / environment 成为唯一真相后，不再需要 legacy write mode
- 计划阶段：`Phase 1` -> `Phase 3`
- 删除前提：
  - `jobs.json / chats.json` 的 repo 内 delete-gate 与 bootstrap/read fallback 已删除
  - `sessions/` 的 compatibility shell（`SafeJSONSession.write_mode/save_dir`）已删除
  - `src/copaw/app/_app.py` 不再调用 `build_phase1_legacy_write_policy()` 或给 session 注入 legacy mode
  - 新主链不再依赖 legacy repo 的写入开关
- 删除方式：
  - 2026-03-11 已删除 policy 模块、session compatibility 参数与 `_app.py` 中的注入点

### 3.2.8 `GoalOverrideRecord.compiler_context` 临时承载行业实例上下文

- 当前状态：`bridged`
- 问题：Phase B 当前通过 `GoalOverrideRecord.compiler_context` 暂存 `industry_profile / team_blueprint / role_blueprint / goal_kind` 等行业初始化上下文；`2026-03-11` 虽已正式落地 `IndustryProfile / IndustryTeamBlueprint / IndustryRoleBlueprint / IndustryGoalSeed`、industry instances/detail、默认 schedule 与 evidence-driven reports，但持久化投影仍借这条 carrier 接入现有 goal/compiler/runtime-center 主链，不应长期替代一等行业对象模型
- 目标替代：正式的 `IndustryProfile / TeamBlueprint / RoleBlueprint` repository + read model
- 计划阶段：
  - `Phase B` 允许作为极短期承载位存在
  - `Phase B~C` 应开始迁出到正式行业对象
- 删除前提：
  - 行业画像与团队蓝图已经成为一等对象
  - Runtime Center 不再通过 goal override 读取行业实例上下文
  - 行业 detail/query 有正式 read model
- 删除方式：
  - 先补正式对象与 query service
  - 再移除 `compiler_context` 中的行业特定字段写入
  - 最后清理相关兼容读逻辑

### 3.2.9 `AgentProfileOverrideRecord` 临时承载生成型行业 agents

- 当前状态：`bridged`
- 问题：Phase B 当前通过 `AgentProfileOverrideRecord` 注入 `industry-manager-* / industry-researcher-*` 这类生成型 agent，使其进入 Runtime Center 与 `/industry` 可见面；`2026-03-11` 虽已存在正式角色蓝图对象，并让显式 capability allowlist 成为角色授权权威边界，但读面仍依赖 profile override 这个过渡承载位，不应长期代替正式团队/角色注册表
- 目标替代：正式的团队蓝图/角色蓝图 registry 与 agent projection service
- 计划阶段：
  - `Phase B` 允许作为行业初始化 MVP 的过渡手段
  - `Phase C` 前应开始迁移
- 删除前提：
  - `TeamBlueprint / RoleBlueprint` 已进入正式 repository/service
  - agent list/detail 不再依赖 profile override 注入生成型角色
- 删除方式：
  - 先引入正式团队/角色读模型
  - 再改造 Runtime Center agent list/detail 的投影来源
  - 最后清理 Phase B 的 override 注入逻辑

---

## 3.3 能力系统

### 3.3.1 `src/copaw/agents/skills_manager.py`

- 当前状态：`deleted`
- 问题：该 shim 曾继续承担技能发现、同步、启用逻辑；虽然 skill execute 已进入统一 capability contract，但旧 manager 与后续 `src/copaw/compatibility/skills.py` compat seam 仍保留主语义入口职责，无法成为最终能力图谱形态
- 目标替代：`src/copaw/skill_service.py + src/copaw/capabilities/skill_service.py`
- 计划阶段：`Phase 2`
- 删除前提：
  - skill 已被编译成 `CapabilityMount`
  - skill 的执行、授权、风险与证据都能经 `CapabilityService + Kernel + DecisionRequest` 落地
  - 新系统不再直接把 skill 当主能力语义
- 删除方式：
  - 当前已桥接成 `CapabilityRegistry` 的 `skill-bundle` source，并由 `/capabilities` 暴露统一读面
  - 当前 `GET /skills` 与 `GET /skills/available` 的只读返回已经经 `CapabilityService` 统一读面后再映射回旧 schema
  - 当前 skill mounts 仍由统一 capability execute contract 承接，但人类前台 `/api/capabilities/{id}/execute` 已物理删除，不再保留直打入口
  - `2026-03-15` 起旧 `/api/skills*` 已从普通 router include 收口为显式 legacy capability alias，并统一返回 `Deprecation + X-CoPaw-Compatibility-*` 头
  - `2026-03-19` 起旧 `/api/skills*` 已进一步收口为“兼容但不再进入产品文档”：legacy router 现已 `include_in_schema=False`，并统一返回 `Cache-Control: no-store`
  - `2026-03-19` 已将 capability 主链全部切到 canonical `src/copaw/capabilities/skill_service.py`，物理删除 `src/copaw/compatibility/` 与 `src/copaw/agents/skills_manager.py`
  - 当前旧 `/skills` 路由只剩 legacy alias/admin 入口，不再存在 active runtime import 指向 `copaw.agents.skills_manager`

### 3.3.2 `tool / MCP / skill` 三套平行主语义

- 当前状态：`bridged`
- 问题：语义分裂，影响调度、授权、风险和证据统一
- 目标替代：`CapabilityMount`
- 计划阶段：`Phase 2`
- 删除前提：
  - 所有主能力入口都能统一映射到 capability registry
  - 所有执行入口都能统一经过 `CapabilityService + Kernel + DecisionRequest + Evidence`
- 删除方式：
  - 当前已新增 `src/copaw/capabilities/` 与 `/capabilities` 统一读面，把 tool / MCP / skill 先桥接成统一 capability model
  - 当前 `GET /mcp` 与 `GET /mcp/{client_key}` 已开始复用 `CapabilityService` 的统一读面，再映射为兼容返回
  - 当前 `tool / skill / MCP / system` mounts 都已可通过 `CapabilityService.execute_task()` 与 kernel confirm/execute 路径真正执行
  - `2026-03-15` 起旧 `/api/mcp*` 已从普通 router include 收口为显式 legacy capability alias，并统一返回 `Deprecation + X-CoPaw-Compatibility-*` 头
  - `2026-03-19` 起旧 `/api/mcp*` 已进一步收口为“兼容但不再进入产品文档”：legacy router 现已 `include_in_schema=False`，并统一返回 `Cache-Control: no-store`
  - 当前剩余缺口是旧路由/旧 manager 的语义地位尚未删除，以及非 tool capability 的验收覆盖不足
  - 允许底层执行实现保留
  - 删除“作为主系统语义入口”的分裂地位

---

## 3.4 调度与入口

### 3.4.1 `src/copaw/app/crons/*` 作为平行主链

- 当前状态：`bridged`
- 问题：cron ingress 已能进入 kernel，且 `executor/manager/heartbeat` 中无效的 runner/channel 依赖已删除；chat/schedule 写入也已直达 state-backed repository。剩余债务是旧 cron manager 仍持有调度编排与 heartbeat 宿主职责，尚未彻底退化为 schedule adapter
- 目标替代：SRK 下的 `schedule ingress`
- 计划阶段：`Phase 4`
- 删除前提：
  - cron 所有动作都能以 intent / scheduled task 形式接入 SRK
  - 调度编排、heartbeat 管理与状态维护不再依赖旧 manager 宿主
- 删除方式：
  - 2026-03-11 已删除 cron executor/manager/heartbeat 中未使用的 runner/channel 依赖，并移除 shadow-sync bridge 写入
  - 保留触发 adapter
  - 删除平行主链职责

### 3.4.2 Channels 直接驱动旧 runner

- 当前状态：`deleted`
- 问题：该遗留路径已由 kernel-backed ingress 替代；当前剩余债务不再是 channel 直驱 runner，而是旧 runner 作为整体宿主的持续收缩
- 目标替代：channels -> SRK intent ingress
- 计划阶段：`Phase 4`
- 删除前提：
  - 所有主要 channel 都通过 SRK 接入
  - channel 处理路径不再回调 runner 执行 turn
- 删除方式：
  - 适配器保留
  - 2026-03-11 已删除 channels 直接耦合旧 runner 的执行路径

---

## 3.5 控制台与 API

### 3.5.1 旧控制台信息架构

- 当前状态：`active`
- 问题：以页面功能分类为主，而不是以运行事实为主
- 目标替代：围绕任务、环境、risk、evidence 的运行中心
- 计划阶段：`Phase 6`
- 删除前提：
  - 新运行中心页面与 API 已可用
- 删除方式：
  - 逐步替换旧页面
  - 最后删除旧数据绑定逻辑

### 3.5.2 各 router 直接面向旧 manager 模型

- 当前状态：`active`
- 问题：API 与旧 manager 强耦合
- `2026-03-12` 更新：`V3-B4` 已完成核心 runtime 壳删尾；旧 router/legacy alias 如仍存在，只能以显式 redirect/compat surface 形式保留，不得再承载核心主链
- 目标替代：router -> SRK/state/evidence service
- 计划阶段：`Phase 4 ~ 6`
- 删除前提：
  - 新服务层接口稳定
- 删除方式：
  - 先桥接
  - 再逐个替换

### 3.5.3 `RuntimeOverviewResponse.bridge` / `X-CoPaw-Bridge-*` 兼容元数据

- 当前状态：`deleted`
- 问题：这些旧命名曾作为 runtime-center discovery 兼容窗；在 `V3-B4` 中已完成真实收口
- 删除完成情况：
  - `RuntimeOverviewResponse.bridge` 已删除
  - `X-CoPaw-Bridge-*` headers 已删除
  - console 与测试侧的 `data?.bridge`、bridge-fallback、旧 header helper 已全部移除
  - canonical contract 现统一为 `RuntimeCenterSurfaceInfo` + `X-CoPaw-Runtime-*` / `X-CoPaw-Runtime-Surface-*`
- 目标替代：`RuntimeCenterSurfaceInfo` + `X-CoPaw-Runtime-Surface-*`
- 删除阶段：`V3-B4`
- 验收口径：
  - `src/copaw/app`、`console/src`、`tests` 中不再存在 `X-CoPaw-Bridge`、`bridge-fallback`、`data?.bridge`、`apply_runtime_center_bridge_headers` 引用

### 3.5.4 `/api/routines/{routine_id}/replay` 直连 `RoutineService.replay_routine()`

- 当前状态：`deleted`
- 问题：该路由曾直接调用 `RoutineService.replay_routine()`，虽然会写 routine evidence，但会绕过 `KernelDispatcher` 的统一 admission / risk / capability evidence 主链，形成 V6/V7 之外的一条旧旁路；即使后续改成 kernel-governed public route，仍会继续给人类前台保留第二条 replay HTTP 入口
- 目标替代：`system:replay_routine -> KernelDispatcher -> CapabilityService -> RoutineService`
- 删除阶段：`V6 / V7 post-hardening`
- 删除完成情况：
  - `2026-03-18` 先把 `/api/routines/{routine_id}/replay` 收口到统一 kernel 主链
  - `2026-03-25` 已从 router 物理删除该公开 replay 入口；human/operator 只能通过主脑或正式 system capability 触发 replay
- 验收口径：
  - 生产 router 中不再存在 `/api/routines/{routine_id}/replay` 入口
  - replay 只剩 `system:replay_routine` 这条内核/能力边界
  - `tests/app/runtime_center_api_parts/detail_environment.py` 与 opt-in `tests/routines/test_live_routine_smoke.py` 均保持通过

### 3.5.5 `RoutineService.engine_kind="n8n-sop"`

- 当前状态：`deleted`
- 问题：
  - 该实现曾把 `n8n` 收缩成 webhook/SOP bridge，但它仍被建模在 `RoutineService` 的 engine 分支内
  - 这会模糊“固定 SOP 编排层”与“browser/desktop routine 叶子执行层”的边界
  - 继续沿这个口子扩张，容易把 `n8n` 误长成第二 workflow/routine truth source
- 目标替代：
  - `FixedSopService`
  - `FixedSopTemplateRecord`
  - `FixedSopBindingRecord`
  - `POST /api/fixed-sops/bindings/{binding_id}/run`
- 计划阶段：`V6 / V7 post-hardening`
- 删除完成情况：
  - `2026-03-21` 已删除 `src/copaw/routines/n8n_service.py`
  - `RoutineService` 不再允许新建 `engine_kind="n8n-sop"`；legacy persisted `n8n-sop` routine replay 会返回显式迁移错误
  - `2026-03-27` 已删除 `src/copaw/sop_adapters/*`、旧 `/sop-adapters` router、旧 state `SopAdapter*` record/repository/export 与 fresh schema `sop_adapter_*` 表
  - 主脑 / 行业固定 SOP 已统一改走 `sop_binding_id -> system:trigger_sop_binding -> FixedSopService`
  - discovery / recommendation 不再推荐 `engine_kind="n8n-sop"`，而是返回 fixed SOP template / binding
  - 固定 SOP 回流闭环的正式 surface 现收口到 `/fixed-sops`

---

## 4. 兼容层使用规则

所有新增兼容逻辑必须遵守：

- 只允许放进 `compatibility/` 或同等专门目录
- 必须写明删除条件
- 必须在本台账中登记
- 不允许进入 `kernel / state / capabilities / environments / evidence` 核心层

---

## 5. 阶段性删除策略

### Phase 1 结束前

- 已删除 repo 内 `jobs/chats/sessions` 的 delete-gate surfaces；残留文件按需人工清理
- 完成 Goal 双真相源退役
- 明确 `config` 与 `state` 的职责边界

### Phase 2 结束前

- 停止继续扩张 `tool / MCP / skill` 平行主语义
- 统一 capability registry 成为唯一能力入口
- 把旧 `/skills` / `/mcp` 路由降级为管理面或兼容面，而不是执行主入口

### Phase 4 结束前

- 旧 runner 不再是系统唯一主链
- `Phase1RuntimeBridge` 已删除；`AgentRunner` 也已在 `V3-B4` 删除，`RuntimeHost + KernelTurnExecutor + KernelQueryExecutionService` 成为正式公开宿主组合
- cron 与 channels 只保留 adapter / ingress 角色，不再形成平行执行事实源

### Phase 6 结束前

- 控制台和 API 基本完成到新模型的迁移
- 旧 manager 驱动页面的数据绑定进入删除阶段

---

## 6. 维护要求

每次大规模迁移后，本文件必须更新：

- 新增了哪些兼容代码
- 哪些旧模块进入 `frozen`
- 哪些旧模块进入 `bridged`
- 哪些旧模块已经 `ready-to-delete`
- 哪些旧模块已经 `deleted`

如果不更新本文件，就等于默认容许历史遗留继续堆积。



