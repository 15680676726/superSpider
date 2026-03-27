# V7_MAIN_BRAIN_AUTONOMY_PLAN.md

本文件用于定义 `CoPaw` 在 `V6 routine / muscle memory` 之后的下一正式阶段：

> 从“行业实例 + goal/schedule 持续驱动”升级为“单主脑长期自治 + 多职业执行位 + 结构化回流”的长期执行主链。

它不是要推翻当前 `state / kernel / goals / routines / runtime-center` 基线，
而是要在当前已落地骨架上，把“长期身份、长期目标、每日规划、职业派工、汇报回流”对象化、可见化、可测试化。

如果与以下文档冲突，优先级依次为：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. 本文件 `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`

---

## 1. 这次升级解决什么问题

当前系统已经具备：

- 正式 `IndustryInstanceRecord`
- 正式 `IndustryExecutionCoreIdentity`
- 正式 `StrategyMemoryRecord`
- 正式 `Goal / Task / Schedule / Evidence / Decision`
- 正式 `Routine / RoutineRun`
- `dispatch-active-goals`、`learning-strategy` 自动循环

但当前主链仍偏向：

`industry instance -> active goals + schedules -> dispatch -> tasks -> evidence -> reconcile`

这条链已经能跑，但它还不是“一个长期主脑每天知道自己该干什么”的正式模型。

当前最核心的结构性缺口有 5 个：

1. 长期载体语义和阶段执行语义仍混在 `IndustryInstanceRecord.status` 里。
2. “每天/每周/事件触发应该做什么”还没有独立的正式 `cycle` 对象。
3. operator 指令和新机会缺少统一 backlog，很多输入仍会直接变成 active goal。
4. 职业 agent 的执行结果缺少统一、结构化的回流对象。
5. 前端 Runtime Center 还主要围绕 `goal / task / evidence` 展示，没有把“主脑当前周期、责任车道、汇报回流”做成一等对象。

---

## 2. 正式目标

`V7` 的目标不是新增一堆页面或重新实现一套行业系统，而是把系统主链收成：

`Main Brain Carrier`
-> `Main Brain Identity`
-> `Mission / Strategy`
-> `Operating Lanes`
-> `Cycle Plan (daily / weekly / event)`
-> `Assignments`
-> `Career Agent Execution`
-> `Agent Reports + Evidence`
-> `Brain Reconcile`
-> next `Cycle Plan`

这里的关键判断是：

- 长期身份、长期目标、战略优先级只属于主脑。
- 职业 agent 只持有职责、能力、routine、当前任务，不各自持有平行长期战略。
- 主脑通过周期计划决定“现在该做什么”，而不是让 active goals 自己无限蔓延。
- 所有结果先结构化回流，再决定是否改战略、改优先级、改派工。

### 2.1 `2026-03-24` 运行时硬化收口补充

- `chat writeback` 已停止 eager fan-out 未来目标，当前轮只物化可执行 step，后续步骤继续停留在 backlog / cycle / planning state。
- `AssignmentRecord` 已明确回到“执行信封”语义；主脑默认只保留 supervision / planning / delegation / synthesis，不再自动兜底成 leaf executor。
- 写回目标角色裁决已改成 `surface -> capability -> environment` 优先，关键词只作为 fallback；未知桌面/浏览器应用也优先按 surface 路由。
- surface 识别已补词边界约束，避免 `formal -> form` 之类误把规划文本判成 browser 任务。
- `IndustryInstanceDetail.main_chain` 与 `/industry` 前台已显式展示 `writeback -> backlog -> cycle -> assignment -> report -> replan`，监督链不再隐身。

---

## 3. 对象分层

## 3.1 永续对象

这些对象长期存在，不应因为一批 goal 做完就关闭：

- `MainBrainCarrierRecord`
  - 长期载体本体。
  - 当前建议由 `IndustryInstanceRecord` 演进而来。
- `MainBrainIdentityRecord`
  - 主脑是谁、长期扮演什么角色。
  - 当前建议先由 `IndustryExecutionCoreIdentity` 承载。
- `MissionRecord`
  - 唯一长期目标对象。
  - 第一阶段不必单独建表，可先挂到 `StrategyMemoryRecord`。
- `StrategyMemoryRecord`
  - 主脑长期使命、北极星、优先级、委派原则、执行约束的正式真相源。
- `OperatingLaneRecord`
  - 长期责任车道，例如流量、转化、复购、研究、分发、反馈。
- `BacklogItemRecord`
  - operator 新要求、机会、问题、待验证事项的统一入口。
- `ExecutionRoutineRecord`
  - 职业 agent 的肌肉记忆，不是一次性 run。

## 3.2 周期对象

这些对象按天、按周或按事件生成，用来承载“当前这轮该怎么推进”：

- `OperatingCycleRecord`
  - `daily / weekly / event`
- `CyclePlanRecord`
  - 当前周期的 focus、优先级、预算、review 规则。
- `GoalRecord`
  - 阶段性目标，不再承载长期使命。
- `AssignmentRecord`
  - 主脑给职业 agent 的正式派工单。

## 3.3 完成即关闭对象

- `TaskRecord / TaskRuntimeRecord`
- `RoutineRunRecord`
- `WorkflowRunRecord`
- `DecisionRequestRecord`
- `PredictionCaseRecord`
- 阶段性 `GoalRecord`
- `AgentReportRecord`

---

## 4. 后端一一对应改造表

## 4.1 新增哪些 `state.models`

主落点：`src/copaw/state/models.py`

必须新增：

- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`

建议第二阶段新增：

- `BrainDecisionRecord`
- `BrainInboxRecord`

现有对象必须补字段：

- `IndustryInstanceRecord`
  - 新增 `lifecycle_status`
  - 新增 `autonomy_status`
  - 新增 `current_cycle_id`
  - 新增 `next_cycle_due_at`
  - 新增 `last_cycle_started_at`
- `GoalRecord`
  - 新增 `industry_instance_id`
  - 新增 `lane_id`
  - 新增 `cycle_id`
  - 新增 `goal_class`
- `TaskRecord`
  - 新增 `industry_instance_id`
  - 新增 `assignment_id`
  - 新增 `lane_id`
  - 新增 `cycle_id`
  - 新增 `report_back_mode`
- `ScheduleRecord`
  - 新增 `schedule_kind`
  - 新增 `trigger_target`
  - 新增 `lane_id`
- `StrategyMemoryRecord`
  - 新增 `lane_weights`
  - 新增 `planning_policy`
  - 新增 `current_focuses`
  - 新增 `paused_lane_ids`
  - 新增 `review_rules`

## 4.2 新增哪些 repository

主落点：

- `src/copaw/state/repositories/base.py`
- `src/copaw/state/repositories/sqlite.py`
- `src/copaw/state/store.py`

必须新增：

- `BaseOperatingLaneRepository` / `SqliteOperatingLaneRepository`
- `BaseBacklogItemRepository` / `SqliteBacklogItemRepository`
- `BaseOperatingCycleRepository` / `SqliteOperatingCycleRepository`
- `BaseAssignmentRepository` / `SqliteAssignmentRepository`
- `BaseAgentReportRepository` / `SqliteAgentReportRepository`

建议第二阶段新增：

- `BaseBrainDecisionRepository` / `SqliteBrainDecisionRepository`
- `BaseBrainInboxRepository` / `SqliteBrainInboxRepository`

装配同步点：

- `src/copaw/app/runtime_bootstrap_models.py`
- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/runtime_state_bindings.py`

## 4.3 新增哪些 service

不建议继续把长期自治 planner 逻辑堆进 `src/copaw/industry/service.py`。

必须新增：

- `OperatingLaneService`
- `BacklogService`
- `OperatingCycleService`
- `AssignmentService`
- `AgentReportService`

职责边界：

- `OperatingCycleService`
  - 读取 carrier、identity、strategy、lanes、backlog、evidence、reports。
  - 决定这一轮是否需要新 cycle。
  - 生成 `CyclePlan`。
  - 只把需要执行的 focus 物化成 `GoalRecord`。
- `AssignmentService`
  - 把 cycle plan 转成 agent assignment。
  - 复用现有 `GoalService / TaskDelegationService / KernelDispatcher`，不另造执行器。
- `AgentReportService`
  - 接收职业 agent 的回报。
  - 写结构化 report。
  - 把关键结果回流给 strategy / backlog / next cycle。
- `BacklogService`
  - 吸纳 operator 指令、机会、问题、未决事项。
- `OperatingLaneService`
  - 管理长期责任车道与健康度。

## 4.4 `runtime_lifecycle` 怎么改

主落点：`src/copaw/app/runtime_lifecycle.py`

当前自动循环：

- `dispatch-active-goals`
- `learning-strategy`

`V7` 之后应变成：

1. `operating-cycle`
2. `dispatch-active-goals`
3. `learning-strategy`

具体改法：

- 新增 system capability：`system:run_operating_cycle`
- 新增 `_should_run_operating_cycle()`
- 判定依据：
  - `next_cycle_due_at`
  - 是否存在未处理 `AgentReport`
  - 是否有 operator writeback 待消化
  - 是否有 task terminal / blocker / risk / opportunity 事件要求即时重规划
- 保留 `dispatch-active-goals`，但降级为 cycle 下游执行器
- `learning-strategy` 保持侧链地位，不再承担“今天该做什么”的顶层职责

## 4.5 `industry/service.py` 哪些函数要重构

主落点：`src/copaw/industry/service.py`

必须重构：

- `bootstrap_v1()`
  - 从“创建 instance + goals + schedules”
  - 调整为“创建长期载体 + identity + strategy + lanes + backlog + initial cycle”
- `_activate_plan()`
  - 拆成：
    - `_provision_carrier`
    - `_seed_operating_lanes`
    - `_seed_backlog`
    - `_seed_initial_cycle`
    - `_materialize_initial_goals_if_needed`
- `kickoff_execution_from_chat()`
  - 从“激活 paused goals + 恢复 schedule”
  - 调整为“恢复自治并触发首轮/下一轮 cycle”
- `apply_execution_chat_writeback()`
  - 默认不再直接把 operator 指令炸成 active goal
  - 改成四类分流：
    - `strategy_update`
    - `lane_update`
    - `backlog_item`
    - `immediate_goal`
- `_build_instance_record()`
  - 只负责长期载体字段
  - 不再混执行期状态语义
- `_sync_strategy_memory_for_instance()`
  - 让出一部分职责给 `OperatingCycleService`
- `_build_instance_main_chain()`
  - Runtime Center 主链应从：
    - `carrier -> writeback -> strategy -> lane -> backlog -> cycle -> assignment -> task -> child task -> evidence -> report -> replan -> instance reconcile`
  - 扩成：
    - `carrier -> writeback -> strategy -> lane -> backlog -> cycle -> assignment -> task -> child task -> evidence -> report -> replan -> instance reconcile`
- `delete_instance()`
  - 级联删除 lanes / backlog / cycles / assignments / reports

还必须补改：

- `_derive_instance_status()`
- `_instance_has_live_operation_surface()`
- `src/copaw/industry/compiler.py` 默认 schedule 生成逻辑

明确要求：

- execution-core 的默认 schedule 应优先触发 planner
- 不应直接等于叶子执行 prompt

---

## 5. 前端同步改造表

后端如果切到主脑长期自治模型，前端必须同步改，不允许继续停留在旧的 `industry -> goals -> tasks` 观看模式。

## 5.1 Runtime Center 必须新增的一等对象

Runtime Center 主导航与 detail drawer 必须增加：

- `Main Brain Carrier`
- `Mission / Strategy`
- `Operating Lanes`
- `Current Cycle`
- `Assignments`
- `Agent Reports`

Runtime Center 首屏必须回答：

1. 主脑当前是谁，长期使命是什么。
2. 当前周期是什么，什么时候到期。
3. 这轮 focus 是什么，为什么排这些。
4. 哪些职业 agent 被派了什么活。
5. 哪些汇报已回流，哪些问题待主脑决策。

## 5.2 `/industry` 页面必须升级为长期载体工作台

`/industry` 不应再只是一页“团队初始化 + 团队详情”。

需要同步展示：

- 当前 carrier 状态
- 主脑 identity / mission / strategy 摘要
- 当前 active lanes
- 当前周期计划
- backlog 摘要
- 最近 report / evidence / blocker

## 5.3 `Chat` 必须继续保持“单主脑控制线程”

`/chat` 行业前台继续只暴露 `Spider Mesh 执行中枢`。

但控制线程里必须可见：

- 当前周期 focus
- 待主脑处理的 report / blocker / opportunity
- 这句话是写入 strategy、lane、backlog 还是 immediate goal

不允许：

- 前端继续把新指令默认理解为“立刻新建 goal”
- 前端继续只显示通用聊天记录，不显示正式回流对象

## 5.4 Agent Workbench 必须升级为“职业执行位工作台”

职业 agent 的工作台不能继续假装它们各自是小主脑。

每个职业 agent 至少需要展示：

- `role contract`
- 当前 assignment
- 当前 task / routine
- 最新 report
- escalations
- 需要回主脑确认的事项

## 5.5 前后端一致性硬规则

前端不允许本地推导以下真相：

- 当前 cycle
- 当前 focus
- 当前 assignment owner
- 主脑是否已消费某条 report
- 某条 operator 指令最终写进了 strategy、lane、backlog 还是 goal

这些都必须直接读后端正式对象。

---

## 6. 汇报对象定义

正式新增：`AgentReportRecord`

建议字段：

- `report_id`
- `industry_instance_id`
- `agent_id`
- `assignment_id`
- `goal_id`
- `task_id`
- `lane_id`
- `report_type`
- `severity`
- `summary`
- `structured_result`
- `evidence_ids`
- `blockers`
- `risks`
- `opportunities`
- `proposed_next_actions`
- `requires_brain_decision`
- `reported_at`

`report_type` 建议固定为：

- `heartbeat`
- `daily_summary`
- `weekly_review`
- `task_completed`
- `task_failed`
- `blocked`
- `risk_alert`
- `opportunity_found`
- `handoff_request`
- `strategy_suggestion`

主脑消费的不是一段自由文本，而是：

- 结果
- 证据
- 阻塞
- 风险
- 建议

---

## 7. 实施顺序

推荐按以下顺序施工：

1. 改 `state.models + state.store + repositories`
2. 改 `runtime_service_graph + runtime_bootstrap_models + runtime_state_bindings`
3. 新增 `OperatingCycleService / AssignmentService / AgentReportService`
4. 重构 `industry/service.py`
5. 再改 `runtime_lifecycle`
6. 最后补 Runtime Center / `/industry` / `Chat` / `AgentWorkbench`
7. 端到端测试补齐

这样做的原因：

- 先把真相源立住
- 再改运行环
- 最后改前端读面

---

## 8. 测试要求

除了现有 goal/task/evidence 闭环测试，还必须新增：

- 载体创建后，在没有 active goals 的情况下，下一轮 cycle 仍会生成新的 goal/assignment
- operator 指令默认进入 backlog，而不是直接变 active goal
- 周期 review 能根据 report 和 evidence 调整 strategy / lane priority
- 职业 agent 完成 task 后会自动生成 `AgentReportRecord`
- Runtime Center 能看到 `carrier -> strategy -> lane -> cycle -> assignment -> report` 正式链路
- `/industry` 与 Runtime Center 对同一 carrier 的 cycle / assignment / report 读面一致
- 前端不依赖本地派生 cycle/focus/assignment 状态

---

## 9. 改动规模评估

只做后端主链与文档，不改前端：

- 规模：`中到大`
- 预计触达：`18-26` 个文件
- 预计改动：`2500-4000` 行

后端主链 + Runtime Center / `/industry` / `Chat` / `AgentWorkbench` 一并改：

- 规模：`大`
- 预计触达：`30-45` 个文件
- 预计改动：`5000-8000` 行

如果再顺手把 `industry` 全语义重命名为 `carrier`：

- 不建议本轮做
- 这是额外的大规模命名迁移
- 收益不如先把主脑长期自治闭环做实

---

## 10. 本轮文档同步要求

凡是涉及 `V7` 主脑长期自治规划的后续改动，至少同步：

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `implementation_plan.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `FRONTEND_UPGRADE_PLAN.md`
- `RUNTIME_CENTER_UI_SPEC.md`
- `AGENT_VISIBLE_MODEL.md`

否则会再次出现：

- 后端按主脑/周期/汇报链改
- 前端还按 goal/task/schedule 老链展示
- 文档里两套心智并存

---

## 11. 2026-03-20 Realized Constraints

- `/chat` is now formally constrained to a single main-brain control thread in the user-facing product. Task threads may still exist as backend execution artifacts, but they are no longer exposed as a second chat product, sidebar thread type, or review drawer on the frontend.
- The main brain is now treated as a planner / dispatcher / supervisor by default. Frontend chat no longer encourages the user to open execution task threads; execution work is expected to flow into assignments, tasks, reports, and evidence surfaces instead.
- `heartbeat` is now a supervision pulse, not a chat surrogate. The runtime cron submits `system:run_operating_cycle` for `copaw-main-brain`, which matches the V7 rule that daily supervision belongs to the main brain instead of a fake standalone heartbeat persona.
- Prediction is now the formal morning/evening review mechanism. `PredictionCase` metadata carries `meeting_window`, `review_date_local`, `participant_inputs`, `assignment_summaries`, and `lane_summaries`, and `/predictions` is treated as the visible review center rather than a separate optimization sidecar.
- `researcher` remains a durable support role in the default industry bootstrap. If a draft omits it, the compiler reinjects it together with the default morning review / evening review / researcher-loop schedules so the main brain keeps a stable research input.
