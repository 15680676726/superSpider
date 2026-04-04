# TASK_STATUS.md

本文件是 `CoPaw` 仓库的实时施工状态板。

它不替代总方案，也不替代专项执行计划；它的用途只有一个：
让下一位接手的 agent / 开发者在几分钟内知道“现在做到哪、主链是什么、下一步先干什么”。

---

## 1. 阅读顺序

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. 本文档 `TASK_STATUS.md`
4. `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`（如任务涉及上位 carrier 目标 / symbiotic host runtime / seat runtime / workspace / host event）
5. `implementation_plan.md`
6. `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
7. `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
8. `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`（如任务涉及短中长期 formal planner 缺口、Claude Code planning shell donor 边界、assignment/cycle/strategy planning 能力建设）
9. `docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md`（如任务涉及 formal planner 施工顺序、P-2/P-3/P-4/P-5 分阶段实现、planner file/test map）
10. `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md`
11. `CHAT_RUNTIME_ALIGNMENT_PLAN.md`
12. `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`（如任务涉及 runtime-first / computer-control / orchestrator / environment plane 视角）
13. `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`（如任务涉及 execution agent computer bodies / browser-desktop-document runtime / contention / recovery）
14. `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`（如任务涉及 fixed SOP / automation / `n8n` 退役 / runtime automation IA）
15. `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`（如任务涉及 fixed SOP kernel 施工顺序）
16. `docs/superpowers/specs/2026-04-03-multi-seat-capability-autonomy-design.md`（如任务涉及 skill/MCP 自动安装、角色原型能力包、执行位实例能力快照、多执行位能力治理、升级替换与回滚）
17. `docs/superpowers/plans/2026-04-03-multi-seat-capability-autonomy-implementation-plan.md`（如任务涉及多执行位能力自治的后端施工顺序、快/慢循环接线、seat 作用域 MCP 挂载与技能生命周期落地）
18. 与当前任务直接相关的源码和测试

---

## 1.1 `2026-03-25` 硬切维护窗口说明

- 当前仓库已进入一次性 `hard-cut autonomy rebuild` 维护窗口，允许短期停机与阶段性功能不完整。
- 本窗口的最高约束不再是兼容历史数据，而是切掉旧主链、旧真相源与无边界兼容逻辑。
- 当前唯一目标链以
  `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`
  为准。
- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md` 只作为 runtime-first 补充视角，不替代上述正式主链。
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md` 只作为 execution-side computer runtime 补充视角；它规定“执行 agent 持有 computer body”，但不替代正式主链与正式 state object vocabulary。
- 旧 `goal/task/schedule` 规划主线不再视为未来兼容目标；如无硬依赖，允许直接删除而不是迁移。
- 已新增运行时清库脚本：
  - `scripts/reset_autonomy_runtime.py`
  - 当前批准可直接清理的残留 runtime artifacts：
    - 说明：以下均为本地运行时在工作目录内生成的 side-effects（默认不入库，可能尚未生成）；如存在，可直接删除而不做历史迁移。
    - `state/phase1.sqlite3`
    - `evidence/phase1.sqlite3`
    - `learning/phase1.sqlite3`
- 本窗口内如本文与以下文档冲突，以硬切文档为准：
  - `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`
  - `docs/superpowers/plans/2026-03-25-copaw-hard-cut-autonomy-rebuild.md`
- `docs/superpowers/plans/2026-03-23-seat-gap-closure.md` 现只保留为 seat-gap/staffing 子计划历史切片；其核心规则仍有效，但如与硬切文档冲突，必须以后者为准。

---

## 2. 当前总判断

- 截至 `2026-03-25`，仓库正式从“V7 软收口 / 增量硬化”切换到“一次性硬切重建”阶段；`2026-03-24` 的收口描述现在只代表旧基线，不再代表目标终态。
- 截至 `2026-03-24`，旧规划口径下的 `Phase A / Phase B / V1~V5` 已完成到“可运行代码基线”的里程碑；这不代表 post-`V6` hard-cut 阶段与 phase-next（`Full Host Digital Twin`、single-industry 真实世界扩面、主脑 cockpit 扩面、回归与 live smoke 扩面、重模块拆分）已交付终态。
- post-`V5` 的 `V6 routine / muscle memory` 主体已经落地；`n8n SOP Adapter / Workflow Hub` 现仅代表旧基线，`2026-03-26` 起已转入退役迁移，目标由系统内建 `Native Fixed SOP Kernel` 接替。
- 当前正式主线已经进入 post-`V6` 的 `V7 main brain autonomy` 阶段。
- `2026-03-27` 补充：正式目标框架已升级为 `Intent-Native Universal Carrier`。execution-side 不再只按“更强 computer control”理解，而是以 `Symbiotic Host Runtime` 作为正式执行框架：Windows 宿主、浏览器、文档、应用都是 carrier 的本地执行环境。
- `2026-03-27` 补充：这次 `Symbiotic Host Runtime V1` 的状态回写，表示 execution-side 的正式方向、对象映射与当前阶段边界已经收敛，不表示相关文档、后续 phase 能力或 `Full Host Digital Twin` 成熟态已经一次性全部落地。
- 这轮最重要的工程方向，不再是继续堆新模块，而是把“主脑长期自治 + 单行业闭环 + 执行位回流 + staffing 可见化 + 主脑综合闭环”硬切成唯一运行事实，并删除旧 `goal/task/schedule` 主脑规划路径。

一句话概括当前项目状态：

> `CoPaw` 现在不是继续做增量修补，而是在维护窗口内被硬切为“主脑只规划/派工/监督/综合，执行位只负责动作，能力/环境/证据成为统一底座”的本地自治执行载体。

---

## 3. 当前代码基线

### 3.1 已完成的大阶段（截至 `2026-03-24` 旧基线里程碑）

- `Phase A`：载体硬化收口、运行主链收拢、旧入口退役与基础状态统一（完成到旧基线）。
- `Phase B`：行业初始化 MVP、行业对象、团队初始化与运行时接线（完成到旧基线）。
- `V1`：行业团队正式化（完成到旧基线）。
- `V2`：长期自治运营基础、知识/报告/节奏/环境宿主深化（完成到旧基线）。
- `V3`：能力市场、治理中心、恢复与规模化收口（完成到旧基线）。
- `V4`：预测对象、recommendation、governed prediction-to-execution 闭环（完成到旧基线）。
- `V5`：执行 surface 升级与主链收口（完成到旧基线）。
- `V6`：`routine / replay / diagnosis / fallback` 已形成正式产品边界；`n8n SOP Adapter / Workflow Hub` 已转入退役删除与内核替换（完成到旧基线）。

补充说明：

- 以上标签用于标记旧计划的里程碑完成点，便于定位历史变更，不代表当前 hard-cut 维护窗口与 phase-next 的成熟态已一次性全部交付。

### 3.2 当前聊天与执行主链

- 聊天页正式写入口是 `POST /api/runtime-center/chat/run`。
- `POST /api/runtime-center/chat/orchestrate` 已物理删除；显式执行编排不再保留第二条 HTTP 前门。
- `MainBrainChatService` 已作为主脑纯聊天前台存在，不再后台触发正式 `writeback/kickoff`。
- `MainBrainOrchestrator` 已作为正式主脑执行入口接到 `KernelTurnExecutor` 后面，durable operator turn 统一落到编排链。
- `2026-03-25` 补充：`MainBrainOrchestrator` 现已先产出 `execution intent / execution mode / environment binding / recovery mode`，再把 request runtime context 提交给 `KernelQueryExecutionService`；query runtime 也开始优先复用 orchestrator 挂载的 intake contract，而不是再次独立判定。
- `2026-03-25` 补充：`build_runtime_bootstrap(...)` 现已正式拆成 `repositories / observability / query / execution / domains` 多模块装配，`runtime_service_graph.py` 保留公共入口，但不再内联 domain service 组装。
- `2026-03-24` 补充：`MainBrainChatService` 现已恢复“流式优先”的输出方式。主脑纯聊天链会优先消费流式模型响应，并以同一条消息逐段更新；拿不到有效文本时，才退回非流式兜底，不再默认整段完成后一次性吐出。
- `KernelTurnExecutor` 负责 `interaction_mode=auto / chat / orchestrate` 裁决与转发。
- `KernelQueryExecutionService / QueryExecutionRuntime` 继续承载重执行编排链。
- `2026-03-24` 补充：`execution-core` 与行业执行位的本地 `file/shell` 能力已重新放开，不再被 `direct-tool` 规则一刀切封死；直接阻断现在应只保留给真实高风险外部动作。
- `2026-03-24` 补充：运行时状态口径已细化为
  `assigned / queued / claimed / executing / blocked`，
  其中“已分配但未认领邮箱”的执行位不再被前端误显示为正在干活。
- `2026-03-24` 补充：`browser/desktop` 的高风险确认规则已收成“默认底线”：绝大多数动作默认放行；当前只把 `transfer / remit / wire / withdraw / 转账 / 汇款 / 打款 / 提现 / 出金` 这类资金转移动作升格到确认门，且用户明确批准后应继续执行，不是永久阻断。
- `2026-03-28` 已补上 chat-first `HumanAssistTask / 共生协作任务` 正式主链基线：
  - 状态层已有正式 `HumanAssistTaskRecord / repository / service`
  - Runtime Center 已提供 `current / list / detail` 读面
  - `POST /api/runtime-center/chat/run` 已可在当前控制线程拦截宿主提交，自动走 `submit -> verify -> accepted|need_more_evidence -> resume_queued`
  - 聊天页已补任务条、任务记录弹层与详情读面，宿主可直接在聊天窗口提交并查看历史
- `2026-03-29` 补充：`HumanAssistTask` 已补上第一条真实 producer 主链。runtime governance 在发现 `host_twin` 要求人接管/人返回时，会正式物化 `task_type=host-handoff-return` 的协作任务，不再只在 governance summary 或 host-twin blocker 文案里提示。
- `2026-03-29` 补充：聊天前门对活动 `HumanAssistTask` 的宿主回执不再只认显式 `submit_human_assist` 或纯 `media_analysis_ids`；当消息文本命中验收锚点或明确完成话术时，也会正式进入 `submitted -> verifying -> accepted|need_more_evidence` 链，再决定是否恢复执行。
- `2026-03-28` 补充：`need_more_evidence` 现已是正式持久化状态，不再和 `rejected` 混写；`accepted` 之后的恢复链也已接回真实消费者，前门会先自动重试一次恢复，再决定是否阻塞。立即恢复成功会收尾到 `closed`，恢复失败才会落到 `handoff_blocked`，异步恢复则短暂进入 `resume_queued` 后再按结果收尾。
- `2026-03-28` 补充：`KernelTurnExecutor auto` 的聊天/执行分流已继续收紧为“显式 `requested_actions` + 主脑 intake contract”双来源；`生成一下 / 开始吧 / 好的` 这类自然话术不再由 `turn_executor` 自己关键词猜执行。`query_execution_runtime / query_execution_team` 的 writeback/kickoff 侧效现在也只认已挂到 request 的 intake contract，不再在内部偷偷补跑一份 sync intake heuristics。
- `2026-03-28` 补充：`main_brain_intake.py` 里的 `resolve_main_brain_intake_contract_sync / resolve_request_main_brain_intake_contract_sync` 已从代码基线移除；当前主链只保留异步 intake 解析 + 已挂载 contract 读取，不再保留 sync 兼容后门。
- `2026-04-02` 补充：`/runtime-center/chat/run` 的单环主脑聊天口径已正式收口。普通聊天前台不再阻塞等待 frontend model precheck，`KernelTurnExecutor auto` 也不再为普通文本额外触发 intake 模型判定；只有显式 `requested_actions`、已挂载 intake contract、确认/恢复连续性这几类正式信号才会转入 orchestrate。
- `2026-04-02` 补充：聊天流 contract 已锁成“同一控制线程、同一 SSE、先回复后 sidecar”。`/runtime-center/chat/run` 会先流出 reply tokens，再在同一条 `industry-chat:*` / `agent-chat:*` 控制线程里追加 main-brain commit sidecar events；前台不再引入第二聊天窗口、第二轮询路由，也不恢复 `task-chat:*`。
- `2026-04-02` 补充：主脑 phase-2 commit 状态现已正式持久化进 session snapshot 的 `main_brain.phase2_commit`。`RuntimeConversationFacade` 会在同一控制线程重载时把它回填到 conversation `meta.main_brain_commit`，因此确认中/已提交状态不会因为刷新聊天页而丢失。
- `2026-04-04` 补充：六缺口收口在当前隔离 worktree 内继续完成第二轮真收口，不再只停在“typed facade 包一层”。`Runtime Center` 后端正式前门现只剩 `/runtime-center/surface`；旧 `/overview`、`/main-brain` 只在断层测试里保留 `404` 断言。前端 `Runtime Center` 事件刷新已按 `cards / main_brain` section 增量刷新，未知 topic 不再回退成整页 full reload；侧边栏里的 `agents` 顶层入口已物理删除，`/agents` 只作为 runtime-center drill-down route 保留。provider/runtime bootstrap 现显式装配 `runtime_provider + provider_admin_service`，formal runtime/kernel 链已不再调用无参 `get_runtime_provider_facade()`；`ProviderManager.get_instance()` 只剩 CLI/live-smoke compatibility 路径。与此同时，`Runtime Center` 自动化/恢复读面已改用正式 snapshot contract：`ActorSupervisor.snapshot()`、`AutomationTaskGroup.overview_snapshot()`、`RuntimeCenterAppStateView.resolve_recovery_summary()` 已成为 canonical read seam，`overview_cards.py` 不再读取 `_loop_task / _agent_tasks` 这类私有字段。`System` overview 也已去掉 recovery 事实对象重复展示，只保留维护路由与 `recovery_source`。本轮验证：`python -m pytest tests/providers/test_runtime_provider_facade.py tests/agents/test_model_factory.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_actor_supervisor.py tests/app/test_local_models_api.py tests/app/test_models_api.py tests/app/test_ollama_models_api.py tests/app/test_phase2_read_surface_unification.py tests/app/test_runtime_center_api.py tests/app/test_system_api.py -q` -> `252 passed`；`python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q -k "surface or host_twin_summary or runtime_center or overview or main_brain or provider or bootstrap or recovery"` -> `26 passed`；`npm --prefix console run build` -> 通过；`npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/routes/resolveSelectedKey.test.ts src/layouts/Sidebar.test.tsx src/pages/Settings/System/index.test.tsx` -> `16 passed`。
- 当前产品口径已经固定为：
  - 人类默认先和主脑说话
  - 主脑决定本轮是继续聊天还是进入执行编排
  - 高风险动作仍回到正式治理链

### 3.3 当前 V7 主脑自治基线

- `OperatingLane / BacklogItem / OperatingCycle / Assignment / AgentReport` 已经作为正式对象进入主链。
- 行业实例 detail 读面已能返回：
  - `lanes`
  - `backlog`
  - `current_cycle`
  - `cycles`
  - `assignments`
  - `agent_reports`
  - `strategy_memory`
  - `execution_core_identity`
- 主脑正式写链现已收口为
  `chat writeback -> backlog -> cycle -> assignment -> task -> report -> strategy sync / replan`。
- 前端 shared control-chain 的显式监督链保持为
  `writeback -> backlog -> cycle -> assignment -> report -> replan`；
  `task` 仍是真实执行叶子，但不再作为共享 UI 控制链节点单独展示。
- `2026-03-24` 补充：运行时硬化链已补齐，`ContextVar` 跨上下文错误与控制台编码异常已修复到正式执行链，不再只停留在离线补丁。
- `2026-03-24` 补充：chat writeback 已停止 eager goal fan-out；goal 现在只物化当前可执行 step，未来步骤继续留在正式 backlog / cycle / planning state 中。
- `2026-03-24` 补充：`Assignment` 已重新收紧为执行信封；当没有真实执行位承接时，只保留主脑监督 owner，不再把 `execution-core` 默认伪装成叶子执行者。
- `2026-03-24` 补充：写回路由已改成 `surface -> capability -> environment` 优先，app 名关键词只做 fallback；同时补了英文词边界匹配，避免 `formal -> form` 这类伪 browser 命中。
- `2026-03-24` 补充：`/industry` 与实例 detail 的主脑监督链已显式展示 `writeback -> backlog -> cycle -> assignment -> report -> replan`，不再只返回一句“已分配”。
- `2026-03-25` 补充：`/system/self-check` 仍保留正式 runtime health 读面，但 memory 的 canonical health contract 已不再包含 `memory_vector_ready / memory_embedding_config` 这类向量就绪字段；formal memory 不再依赖 embedding/vector readiness。
- `2026-03-30` 补充：memory 正式架构已锁定并落地为 `truth-first` 与 `no-vector formal memory`：主脑与执行位共享同一套 truth-derived memory，私有 conversation compaction 与共享正式记忆显式分离，QMD / embedding / vector health 只可被视为 physically removed residuals，不再属于正式 runtime/operator contract。
- `2026-04-01` 补充：knowledge activation layer 的第一批代码基线已落地。runtime query bootstrap 现在会实例化 `memory_activation_service`，并把它绑定到 `app.state`；`KernelQueryExecutionService` 的 prompt retrieval 与 `GoalService` compiler context 现已可消费 activation-derived memory items/refs。当前落地边界仍然是派生激活层，不是新的 memory truth，也未引入 graph persistence。
- `2026-04-01` 补充：knowledge activation layer 的第二批代码基线也已落地。industry report synthesis 现在可消费 activation-derived constraints/contradictions，follow-up backlog materialization 会把 activation metadata 沿 `synthesis -> backlog -> assignment` 链继续带下去，current-cycle runtime view 也已能暴露 `synthesis.activation`。当前仍未引入 graph persistence。
- `2026-04-01` 补充：knowledge activation layer 的第三批 Runtime Center 可见化读面已落地。`/runtime-center/memory/activation` 现在会直接返回 activation result；memory profile / episode 读面在显式传入 `include_activation=true + query` 时也可附带 activation payload；`RuntimeCenterStateQueryService` 已开始为 task list/detail 派生保守型 `activation` 摘要（如 `activated_count / contradiction_count / top_entities / top_constraints / top_next_actions / support_refs`）。当前边界仍然是派生读面，不包含 graph persistence，也不是独立的 activation truth/UI 系统。
- `2026-04-02` 补充：formal planning capability gap 的 compiler/runtime 收口现已完成到 `FP-6 / FP-7 / FP-8`。当前正式读法已收敛为 `strategy compiler -> cycle planner -> assignment planner -> report-to-replan engine`：`src/copaw/compiler/planning/` 已成为独立 formal planning slice；`IndustryService` 会在 cycle / assignment 物化时持久化 `formal_planning` sidecar；prediction cycle review 已复用真实 operating-cycle 的 formal planning overlap，而不是再开 planning-blind review 壳；goal compiler context、`Runtime Center / industry detail`、`main brain cognitive surface` 与 prediction snapshot 也都已能暴露 typed `strategic_uncertainties / lane_budgets / report_replan(decision_kind + trigger context)`。当前 focused formal-planning 回归：`$env:PYTHONPATH='src'; python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_goals_api.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py tests/app/test_runtime_bootstrap_split.py -q` -> `77 passed`。该记录表示本轮 formal planning capability gap 已对 `FP-6 / FP-7 / FP-8` 闭环，后续如需扩展 long-horizon planning，只允许进入新的 dated spec，不再把这条 gap 文档重新打开成含糊 follow-up。
- `2026-04-03` 补充：经营级 formal planning 的下游消费者又收紧了一刀。`PredictionService` 不再只读取 `north_star / priority_order / execution_constraints` 这类薄战略摘要；`src/copaw/predictions/service_recommendations.py` 现在也会把 `strategy_trigger_rules / strategic_uncertainties / lane_budgets` 编译成正式 prediction signals，并在需要时给出带 `strategy_change_decision / trigger_rule_ids / affected_lane_ids / affected_uncertainty_ids` 的 `manual:coordinate-main-brain` 计划建议。与此同时，workflow preview 侧已验证继续透传同一份 `StrategyMemory` 正式字段，新增测试锁定 `strategy_trigger_rules / strategic_uncertainties / lane_budgets` 不得从 `WorkflowTemplatePreview.strategy_memory` 回退丢失。focused 回归：`$env:PYTHONPATH='src'; python -m pytest tests/state/test_strategy_memory_service.py tests/compiler/test_strategy_compiler.py tests/app/test_goals_api.py -q` -> `30 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_predictions_api.py -q` -> `16 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q` -> `11 passed`；workflow preview 针对性锁定：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_workflow_templates_api.py -k "workflow_templates_list_and_preview or workflow_preview_keeps_strategy_trigger_rules_and_uncertainty_budget_context" -q` -> `2 passed`。
- `2026-04-03` 补充：formal planning 第二波又补了两条真实闭环。`CyclePlanningCompiler` 现在会把 `completed_cycles / consumed_cycles / missed_target_cycles / consecutive_missed_cycles` 这类 durable lane debt 编进 `multi_cycle_gap`，并把 `target_cycle_count / underinvested_cycles / multi_cycle_gap` 正式写进 `lane_budget_outcomes`，不再只靠单测里手工塞 `budget_window` 才能触发 `multi-cycle-underinvestment`。与此同时，`report_replan` 现在会把 derived `uncertainty_register` 先持久化进 formal planning sidecar，Runtime Center/industry detail 读面优先消费该 sidecar，缺省再回落到 strategy-memory 派生，而 uncertainty 自带 `escalate_when` 也会在 register 内补成 effective trigger surface，不再因为旧 trigger-rule 集合没同步就退化成空壳。focused 回归：`$env:PYTHONPATH='src'; python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_cycle_planner.py tests/industry/test_runtime_views_split.py -q` -> `25 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_same_thread_cognitive_closure_smoke_updates_visible_judgment_after_later_resolution tests/app/industry_api_parts/runtime_updates.py -k "test_phase_next_same_thread_cognitive_closure_smoke_updates_visible_judgment_after_later_resolution or test_runtime_detail_exposes_stable_main_brain_planning_surface_from_formal_sidecars" -q` -> `2 passed`。
- `2026-04-02` 补充：knowledge activation layer 已开始真正进入 planning 主链，而不再只停留在 query/read surface。`MemoryActivationService.activate_for_query(...)` 现在会在 scoped fact recall 之外继续拉取 `entity/opinion` derived views；`IndustryService.run_operating_cycle(...)` 会把同一份 activation result 前移复用到 prediction cycle review、report synthesis 与 cycle planner，而不是各自重算或只在后半段消费；`PlanningStrategyConstraints` 与 `CyclePlanningDecision.metadata` 现已保留 `graph_focus_entities / graph_focus_opinions`；follow-up backlog 与 materialized assignment continuity 也会继续携带 `activation_top_entities / activation_top_opinions`。当前 focused graph-backed planning 回归：`$env:PYTHONPATH='src'; python -m pytest tests/memory/test_activation_service.py tests/industry/test_report_synthesis.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/industry_api_parts/bootstrap_lifecycle.py::test_activation_followup_backlog_carries_activation_metadata tests/app/industry_api_parts/bootstrap_lifecycle.py::test_activation_followup_materialized_assignment_keeps_activation_metadata tests/app/industry_api_parts/bootstrap_lifecycle.py::test_run_operating_cycle_persists_graph_focus_into_formal_planning_sidecar tests/app/test_predictions_api.py::test_prediction_cycle_case_exposes_light_formal_planning_context_in_detail tests/app/industry_api_parts/runtime_updates.py::test_runtime_updates_expose_activation_summary_on_current_cycle_surface tests/app/industry_api_parts/runtime_updates.py::test_runtime_updates_keep_replan_focus_and_activation_summary_together -q` -> `41 passed`。当前边界仍然是不引入 graph persistence、不新增第二真相源，只把 graph signal 作为 planner/replan sidecar 输入。
- `2026-04-02` 补充：长期无人值守成熟度 follow-up 的第一刀已从 `ActorSupervisor` 扩到 automation coordinator/read-model。resident supervisor 现在对单个 agent run failure 做异常隔离，不再因为单个 worker 异常把整次 poll 或整条常驻 loop 一起打死；失败会正式写回 `AgentRuntime.last_error_summary`、`metadata.supervisor_last_failure_*`，并通过 runtime event bus 发布 `actor-supervisor.agent-failed / actor-supervisor.poll-failed`。与此同时，`start_automation_tasks()` 已升级成带 `loop_snapshots()` 的 `AutomationTaskGroup`，每条 loop 现都会暴露稳定 `automation_task_id / coordinator_contract / loop_phase / health_status / last_gate_reason / submit_count`，并把同一套 coordinator 元数据写进真正提交到 kernel 的 payload；`/runtime-center/main-brain` 的 automation section 也已开始持续显示 automation loops 和 actor-supervisor health，而不再只剩 schedule/heartbeat 薄摘要。focused durable-runtime 验证：`$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_actor_supervisor.py tests/app/test_runtime_lifecycle.py tests/app/runtime_center_api_parts/overview_governance.py -k "test_actor_supervisor or test_start_automation_tasks or main_brain_route_exposes_unified_operator_sections or automation_loop_and_supervisor_health" -q` -> `22 passed`。该记录表示 durable runtime baseline 已继续从“能恢复/能发车”推进到“有 coordinator snapshot 与 health read-model”，不表示 external bridge/browser/document producer 已全部纳入同一 durable producer runtime。
- `2026-04-02` 补充：durable runtime 的 operator self-check/overview 也已补到同源 runtime summary。`RuntimeHealthService` 现在会复用 Runtime Center 的正式 automation/supervisor/startup recovery 投影，直接从同一条 `app.state` runtime truth 生成 `/system/self-check.runtime_summary`，不再只回“服务是否存在”；`/runtime-center/main-brain` 的 automation loops 读面也已开始合并 `loop_snapshots()` 的 coordinator 字段，不再只能看见 task name + running/completed。focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_system_api.py tests/app/runtime_center_api_parts/overview_governance.py -k "runtime_summary or automation_loop_and_supervisor_health or automation_loop_snapshots" -q` -> `10 passed`。这条记录表示 durable runtime 的 operator summary 已从 service-presence 升级为 execution-grade read-model，不表示 automation heartbeat/schedule 已完全切成 persisted-only projection。
- `2026-04-02` 补充：durable runtime 的 operator mutation front-door 这一轮也已继续硬化。`Runtime Center` 现在对 `POST /runtime-center/heartbeat/run` 与 `POST /runtime-center/schedules/{id}/run|pause|resume` 增加了同类动作重入保护：相同 operator control 在未完成时会直接返回 `409`，不再允许双击/重复提交在同一前门上并行发车。与此同时，`dispatch_governed_mutation(...)` 已开始按 `capability_ref + owner_agent_id + stable payload signature` 复用现有 `risk-check / waiting-confirm / executing` kernel task；相同 governed mutation 在 `waiting-confirm` 时会复用已有 `decision_request_id`，而不是继续物化第二个 pending decision。`pause/resume` 对已命中目标状态的 schedule 也会直接返回 typed no-op，不再制造无意义 task/evidence；同一合同面的 `404 / dispatch failure / heartbeat failed result` 分支也已补上专项回归，不再只锁 happy-path。最后，`CronManager._run_heartbeat(...)` 已升级成 heartbeat single-flight：手动 `run` 与 scheduler callback 在同一时刻只会真正执行一次底层 supervision pulse，后续并发调用复用同一结果，不再重复提交 operating-cycle heartbeat。focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_cron_manager.py tests/app/test_runtime_lifecycle.py tests/app/test_system_api.py -q` -> `88 passed`，以及 `$env:PYTHONPATH='src'; python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/industry/test_runtime_views_split.py tests/industry/test_report_synthesis.py -q` -> `45 passed`。这条记录表示 runtime mutation contract 已从“只有 happy-path governed shell”推进到“front-door reentry guard + pending reuse + typed no-op + heartbeat single-flight”，不表示 durable runtime 的 external producer / persisted-only projection 已全部终态完成。
- `2026-03-25` 补充：前端 shared `control chain` presenter 已落地，`/industry`、`Runtime Center`、`AgentWorkbench` 统一消费同一条 `writeback -> backlog -> cycle -> assignment -> report -> replan` 呈现链，不再各自维护排序和标签逻辑。
- `2026-03-25` 补充：`Runtime Center` 路由已继续按域拆出 `overview / memory / knowledge / reports / industry` 模块，`runtime_center_routes_core.py` 不再继续承载这些域；同时已删除 retired `TaskDelegationRequest` 与死掉的 delegation shared helper。
- `2026-03-25` 补充：`state/models.py` 已收成兼容 re-export 面，`goals_tasks / agents_runtime / governance / workflows / prediction / reporting / industry / core` 分层模块已经落位，旧导入链继续可用但真正定义不再堆在单文件里。
- `2026-03-25` 补充：`EnvironmentService` 已降为稳定 façade；环境包已拆出 `session_service / lease_service / replay_service / artifact_service / health_service`，session/resource/actor lease、runtime recovery、environment detail 与 replay/artifact 读面不再继续堆在单个 1400+ 行服务里。
- `2026-03-25` 补充：`ProviderManager` 已降为 compat façade；`providers` 包已拆出 `provider_registry / provider_storage / provider_resolution_service / provider_chat_model_factory / provider_fallback_service`，runtime/query/industry 等可注入调用点优先改走显式实例，残余 `get_instance()` 已收口到 bootstrapping、router/CLI、`memory_manager` 兼容链与 façade 静态入口。
- `2026-03-25` 补充：`POST /api/runtime-center/tasks/{task_id}/delegate` 已从 runtime-center router 物理删除；人类前台不再保留 direct delegate API，assignment/delegation 只留在内核与 system capability 内部。
- `2026-03-25` 补充：`dispatch_active_goals` 与旧 goal-dispatch 文案已从前台 capability / insights surface 删除；残留 `GoalRecord` 与 goal service 只作为执行层 phase/leaf object 保留，不再代表主脑规划真相。
- `2026-03-25` 补充：execution-core 的正式能力基线、runtime query system tools、prompt capability projection、Runtime Center actor capability surface 与 automation loop 已全部摘掉 `dispatch_active_goals`；主脑/Runtime Center 不再把它当成正式派工入口，后续残留边界也只允许继续向 history-only 的 recommendation 识别/归一化收口。
- `2026-03-25` 补充：execution-core 的正式能力基线、runtime query tool registry、prompt capability card 与 Runtime Center capability assignment surface 也已同步摘掉 `dispatch_goal`；该能力仅保留给 goal service / workflow / prediction 等执行层内部叶子边界，不再作为主脑或 execution-core 的正式可见能力。
- `2026-03-28` 补充：`system:dispatch_active_goals` 与 `system:dispatch_goal` 已从 system capability registry 物理退役；prediction service 启动时会直接清除残留旧 recommendation，不再把 retired goal-dispatch recommendation 改写后继续展示，运行期读面也不再长期背这条 compat 分支。governance 默认阻断集合也不再把 `dispatch_goal` 当作现役 system capability。当前旧 goal-dispatch runtime compat 已收口到 `/goals` 叶子显式 dispatch family 与 prediction 启动期旧 recommendation 清理边界；`GoalService.dispatch_active_goals()` 已从服务层物理删除。现役 `manual:coordinate-main-brain` recommendation 也不再泄露 `goal_id / owner_agent_id / execute / activate / context` 这类旧 dispatch payload，前后端正式只靠 `target_goal_id / target_agent_id + routes.coordinate` 进入主脑协调。
- `2026-03-28` 补充：goal leaf dispatch 的返回面也已继续瘦身，不再把 `compiled_specs` 和顶层 `trigger` 当作 dispatch 结果镜像直接抛给调用方；正式结果只保留 `goal / compiled_tasks / dispatch_results`，而 trigger 事实继续通过 goal compiler context 与 runtime event 留证。
- `2026-03-28` 补充：goal leaf dispatch 的执行 API 也已继续收口；compile-only 入口现已正式改名为 `compile_goal_dispatch(...)`，旧公共 `dispatch_goal(...)` 名称已退役，不再保留为现役 service surface。前台同步执行统一改走 `dispatch_goal_execute_now(...)`，即时后台执行统一改走 `dispatch_goal_background(...)`，延迟 release 统一改走 `dispatch_goal_deferred_background(...) + release_deferred_goal_dispatch(...)`；industry / workflow 等调用方不再自行拼接旧 dispatch 开关组合，也不再继续依赖旧公共名。
- `2026-03-28` 补充：CLI `goals dispatch` 也已从命令面物理删除，不再保留 retired shell；CLI 只剩 `goals list / compile` 这类只读/编译辅助面。
- `2026-03-26` 补充：`Runtime Center` 的行业 kickoff 提示、overview meta 与 execution focus 卡片已停止把 `goal / active goal` 当作 operator 主口径；当前正式摘要统一改成 `backlog / cycle / assignment / report`，详情卡文案也改成 `Current Focus / No active focus`。
- `2026-03-29` 补充：`Runtime Center / /industry / 行业 kickoff prompt` 现在已把 `strategy + lanes + current cycle + assignments + agent reports` 提成正式 planning surface，而不是只把这些对象留在后端 read-model。`Runtime Center` 的行业 focus section 已新增 `Main-Brain Planning` 卡；`/industry` 已新增 `工作泳道` 正式展示；kickoff prompt 也会显式带出 `lane/backlog/cycle/assignment/report` 计数与 lane 摘要。
- `2026-03-29` 补充：hard-cut 回归面继续扩大到根路由/OpenAPI 层；`/runtime-center/chat/intake`、`/runtime-center/chat/orchestrate`、`/runtime-center/tasks/{task_id}/delegate`、`/runtime-center/goals/{goal_id}`、`/runtime-center/goals/{goal_id}/dispatch`、`/goals/{goal_id}/dispatch` 与 `/goals/automation/dispatch-active` 现已在 assembled root-router 合同里明确锁成“未注册 + 404”，不再只靠局部 app/feature 测试兜底。
- `2026-03-29` 补充：assembled root app 上的公开 `goals` frontdoor 也已继续收口为 detail-only。根路由/OpenAPI 现在只保留 `GET /goals/{goal_id}/detail` 作为 leaf detail 读面；`GET/POST /goals`、`GET/PATCH/DELETE /goals/{goal_id}` 与 `POST /goals/{goal_id}/compile` 已从 root-router 退役，专项测试 app 如需完整 `/goals` router 仍需手工显式挂载。
- `2026-03-29` 补充：`goals` 公开 router 里的 `GET /goals/{goal_id}` 也已一起退役，public leaf read 现只保留 `GET /goals/{goal_id}/detail`。这意味着 assembled root app 与专项测试 app 都不再把旧 `GoalRecord` 裸读面继续当正式 operator surface。
- `2026-03-29` 补充：`Runtime Center` 的行业 `Current Focus` 卡片也已继续从 legacy goal 视角退场；前端正式优先打开 live `assignment / backlog` route，并通过 `focus_selection + selected assignment/backlog` 呈现 focused subview，不再因为旧 `current_goal_id` 残留而把 operator 带回 goal detail。
- `2026-03-29` 补充：`/industry` 前端也已开始对齐同一条 focused runtime 心智。行业页现在支持按 `assignment_id / backlog_item_id` 重新加载 focused subview，并把 `agent_report.work_context_id` 继续带回 report drill-down chat；staffing closure surface 也不再只留最薄摘要。
- `2026-03-29` 补充：`/runtime-center/industry/{instance_id}` 的后端 detail 投影也已同步切到 live `assignment / backlog`。正式 schema 已从 `execution.current_goal / main_chain.current_goal` 收敛到 `execution.current_focus / main_chain.current_focus`，并在存在 live assignment/backlog 时优先反映执行焦点；`assignment / backlog` 节点 route 统一锚定到 `industry detail + assignment_id/backlog_item_id`，不再回跳 legacy goal surface。
- `2026-03-29` 补充：`AgentProfile / governance override / chat meta / prompt appendix` 这条 legacy `current_goal` 心智已完成正式收口；`AgentProfile` 与 `AgentProfileOverrideRecord` 现已统一只认 `current_focus_kind / current_focus_id / current_focus`，`Runtime Center conversations`、overview agent meta、主脑聊天 roster、`AgentWorkbench / Knowledge` 前台与 query execution prompt 已全部消费 focus 字段。`current_goal / current_goal_id` 已从正式模型、仓储、服务与前台读面移除，仓库内仅保留负向回归测试断言，防止旧字段回流。
- `2026-03-29` 补充：execution-side 的 `host_twin` 也已开始按正式前台对象被看见，而不是继续只靠 raw detail 递归字典。`Runtime Center` detail drawer 现在会把 `host_twin` 提成结构化 `Host Twin` section，显式展示 continuity、legal recovery、coordination、active app-family twins 与 blocked surfaces；`projection_kind / is_projection / is_truth_store` 这类投影元信息不再挤占主要读面。
- `2026-03-29` 补充：`host_twin` 的后端消费面也已继续收口为正式摘要对象。`RuntimeCenterStateQueryService` 现在会回填 `host_twin_summary`；task review payload 与 overview governance card 都会优先消费 `seat_owner_ref / recommended_scheduler_action / active_app_family_keys / blocked_surface_count / legal_recovery_mode` 这类派生摘要，而不是继续把 raw `host_twin` JSON 整块透传给首屏 summary。
- `2026-03-29` 补充：`/goals/{goal_id}/detail` 也已收掉一个隐蔽 compat 副作用。goal detail 读面不再在读取时偷偷调用 `reconcile_goal_status()` 推进状态，正式边界恢复为“读面只读、状态推进走显式 reconcile/write 链”，避免 leaf goal detail 再次变相承接规划/执行 mutation。
- `2026-03-26` 补充：`/industry` summary/detail/runtime main-chain、agent detail stats、industry team update result、state reporting snapshot 已继续摘掉 `goal_count / active_goal_count` 这类 operator/runtime 兼容统计；行业实例列表也不再按“是否有 goal”决定可见性，而是按真实 team/runtime surface 判定。当前仓库里保留的 `goal_count` 只剩 `/goals` 叶子 dispatch 内部结果，不再属于主脑或运行中心主口径。
- `2026-03-26` 补充：`LearningService` 已切成正式 façade，公开入口保留在 `src/copaw/learning/service.py`，内部运行逻辑下沉到 `runtime_core + proposal_service + patch_service + growth_service + acquisition_service`；runtime bootstrap 已开始通过 `LearningRuntimeBindings.configure_bindings(...)` 一次性接线，不再继续在 live 装配层堆 learning setter。
- `2026-03-26` 补充：`RuntimeCenterQueryService` 已切成 thin façade，overview 主装配改为 `service.py -> overview_cards.py -> overview_helpers.py`；`/runtime-center/overview` 已正式退休 `goals / schedules` 卡片，只保留 runtime-first operator 读面。
- `2026-03-26` 补充：computer-control 的下一正式方向已锁定为 `Agent Body Grid`。浏览器、桌面应用、文件/文档操作不再被视为主脑直接调用的零散工具，而是 execution agent 持有的 `computer body` surfaces；后续实现必须围绕 `observe -> interpret -> act -> verify -> recover` 循环、body lease / resource contention、以及真实任务验收集推进。
- `2026-03-26` 补充：`Agent Body Grid` 必须与现有 `workflow / routine / SOP` 一起升级，而不是替代它们。正式边界应收成 `Assignment -> Role Workflow -> Body Scheduler -> Body Lease -> Routine/Operator -> Evidence/Report`：workflow 继续负责角色连贯执行逻辑，body scheduler 只负责机器资源/会话/写锁调度；workflow preview/launch 后续也必须把 body/session/resource 可用性纳入 launch blocker，而不再只检查 capability / assignment gap。
- `2026-03-27` 补充：`Agent Body Grid` 下的 browser runtime contract 已收紧为 3 类正式 mode：`managed-isolated / attach-existing-session / remote-provider`。`attach-existing-session` 不再被视为临时调试技巧，而是正式浏览器会话模式；但首次接管真实用户浏览器、以及该模式下的能力边界，必须继续显式纳入治理与恢复语义。
- `2026-03-27` 补充：browser readiness 不应再只看单一 `browser_surface_ready`。后续实现、Runtime Center 与 acceptance 必须按 mode 显式暴露 `multi_tab / uploads / downloads / pdf_export / storage_access / locale_timezone_override / resume_kind` 等 capability contract；已登录后台续作、跨 tab、上传下载、恢复重连要进入正式验收，不再只测表单提交。
- `2026-03-27` 补充：browser writer work 不能继续按“通用网页动作”理解。对已知后台/站点，execution-side 后续必须在 browser mode 之外再解析 `site contract`：至少说明认证/写入/下载/提交/人工登录边界、验证锚点与风险契约。没有 site contract 时，默认只能走 read-only、launch blocker 或 governed handoff。
- `2026-03-27` 补充：human login / CAPTCHA / MFA / drift rescue 也已被收口为正式 browser continuity contract。人接管浏览器不等于主脑亲自执行；它只是 execution body 的 handoff 状态。后续实现必须显式记录 handoff owner/reason/checkpoint/return condition，并在 agent 续跑前重新 observe/verify，而不是根据聊天文本盲续。
- `2026-03-27` 补充：desktop/app runtime 后续也不再只按“鼠标键盘能不能点”理解。当前仓库应按 Windows-first 口径补 `desktop host + app contract`：至少显式区分 `host_mode / lease_class / access_mode / session_scope / account_scope_ref / handoff_state / resume_kind / verification_channel` 等共享 host 字段，以及 `app_identity / window_scope / app_contract_status / writer_lock_scope / active_window_ref` 等 Windows app 字段。
- `2026-03-27` 补充：Windows 桌面应用的 writer work 后续必须解析 `app contract`，并优先走 `accessibility/window/process` 控制通道；未知模态框、登录、UAC/系统提示、焦点丢失与窗口争用都要进入正式 handoff / contention / recovery 语义，不允许继续只靠 Win32 API 返回值或宿主日志判断“操作成功”。
- `2026-03-27` 补充：execution-side browser/desktop contract 已回写到总方案、API 迁移图、数据模型与执行计划。当前正式口径应统一理解为：`EnvironmentMount / SessionMount` 承载 live surface，shared `Surface Host Contract` 统一 `host_mode / lease_class / access_mode / handoff / resume / verification`，browser 追加 `Site Contract`，Windows desktop 追加 `Desktop App Contract`；主脑继续只负责派工/监督，不直接成为 surface driver。
- `2026-03-27` 补充：当前上位正式目标已继续上抬为 `Intent-Native Universal Carrier`，execution-side 正式框架改为 `Symbiotic Host Runtime`。`Agent Body Grid` 现在应被理解为 execution substrate，而不是单独的传统 computer-control 产品面。
- `2026-03-27` 补充：execution-side 当前下一正式阶段已收敛为 `Windows Seat Runtime Baseline`，而不是一次性交付 `Full Host Digital Twin`。当前应优先把 `Seat Runtime / Host Companion Session` 做成正式运行边界，把 `Workspace Graph` 收敛为正式 projection，把 `Host Event Bus` 收敛为正式运行机制。
- `2026-03-26` 补充：`n8n / Workflow Hub` 已从目标架构退役。后续必须删除 `/sop-adapters`、前端 `社区工作流（n8n）`、社区模板同步与 callback 相关代码，并以系统内建 `Native Fixed SOP Kernel` 取代；该内核只覆盖 webhook、schedule、API 串联、低判断条件路由，真实 UI 动作仍通过 CoPaw 的 body runtime / routine 主链完成。
- `2026-03-27` 补充：`src/copaw/sop_adapters/*`、旧 `/sop-adapters` router、state `SopAdapter*` record/repository/export 与 fresh schema `sop_adapter_*` 表已物理删除；仓库内正式 SOP 自动化面现只保留 native `fixed-sops` 路线。
- `2026-03-27` 补充：console 侧旧 `workflow-hub` / `Capability Market -> 工作流` 假入口与 `console/src/api/modules/sopAdapters.ts` 也已删除；`WorkflowTemplates` 独立页现已退役为 `Runtime Center -> 自动化` 的历史残留，不再把已退役的 n8n hub 当正式前台入口。
- `2026-03-27` 补充：capability-market 安装模板返回的 `workflow_resume.return_path` 已改指向 `Runtime Center -> Automation`，不再回跳到已退休的 `/workflow-templates/*` 前台路由。
- `2026-03-27` 补充：prediction / Insights 的 operator 文案也已同步收口，不再建议把周期性工作沉淀为“工作流模板”；当前正式口径统一改为 `Runtime Center -> Automation` 下的固定 SOP / 运行计划。
- `2026-03-26` 补充：固定 SOP 的正式替代方案以 `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md` 及对应 implementation plan 为准，不再沿用 `n8n` 相关产品口径。
- `2026-03-26` 补充：`src/copaw/app/routers/learning.py` 已改成依赖注入式 façade 解析，不再在每个 endpoint 内重复手动解析 app-state learning service。
- `2026-03-26` 补充：capability/runtime 尾巴已继续硬切收口。旧 `/skills`、`/mcp` 与 `legacy_capability_aliases.py` 已物理删除；router 写操作现统一落到 `app/routers/governed_mutations.py`；runtime decision/patch 链接现统一落到 `utils/runtime_action_links.py`；chat / AgentWorkbench / RuntimeCapabilitySurfaceCard / RuntimeExecutionStrip 的风险与状态标签颜色已统一改走 `console/src/runtime/tagSemantics.ts`，不再各自维护分叉语义。
- `2026-03-26` 补充：`Chat` 页已正式按 chat-first 收口，只保留 `消息流 + 输入框 + 最小状态条 + 必要附件能力 + 最小治理审批入口`；`capability drawer`、重 runtime sidebar、`V7ControlThreadPanel` 与 actor detail 驱动的聊天页附属面已从主页面摘除，不再把 `Chat` 做成第二个运行中心。`AgentWorkbench` 的 `ActorRuntimePanel` 已独立落到 `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`，`pageSections.tsx` 回退为兼容导出面。
- `2026-03-26` 补充：Industry 主链已继续朝“单一状态入口”硬化。`build_industry_service_runtime_bindings(...)` 不再基于 `state_store` 临时补造 repo/service，运行时绑定只接受显式注入协作者；`reconcile_instance_status_for_goal()` 也已改成按 `goal_id` 定向读取实例，不再每次 goal 变化都全表扫行业实例。
- `2026-03-26` 补充：query runtime 的前门意图判定与 durable writeback 策略已统一改走共享 `query_execution_intent_policy.py`，不再在 `shared/runtime/writeback` 三处各自复制“目标委托 / 假设性提问 / 是否写回”的启发式；`LearningRuntimeCore` 公开 patch/growth/trial 入口也已继续瘦身为 thin delegate，proposal/patch/growth/acquisition 责任边界开始稳定落位。
- `2026-03-26` 补充：前端 page-god 收口继续推进。`Chat` 输入区已移除对第三方聊天框的 DOM 手术式解锁；`/industry` 与 `CapabilityMarket` 的页面级加载、刷新、选择与动作编排已分别下沉到 `useIndustryPageState` / `useCapabilityMarketState`，页面组件本身不再继续兼当 application service。
- `2026-03-29` 补充：`IndustryService._build_instance_detail(...)` 的 runtime detail/read-model 组装已继续从 `service_strategy.py` 下沉到 `service_runtime_views.py`，`IndustryViewService` 也保持了“无 focused 参数时按旧签名调用”的兼容边界；当前拆分已经开始把行业 detail/read-model 责任从策略服务里剥离出来。
- `2026-03-26` 补充：`Chat` 运行时 transport 也已开始从页面状态 hook 中下沉。`useChatRuntimeState` 不再内联模型可用性检查、runtime request 组装、附件合并与流式 response 健康/结束判定；上述逻辑已抽到 `console/src/pages/Chat/runtimeTransport.ts`，并新增前端测试锁住 canonical request body 与 streamed completion 行为。
- `2026-03-26` 补充：`RuntimeCenter` 的治理/恢复/application orchestration 也已开始从页面层下沉。governance status、capability optimization、recovery/self-check、batch decision/patch actions 与 emergency stop/resume 相关状态机已抽到 `console/src/pages/RuntimeCenter/useRuntimeCenterAdminState.ts`；`RuntimeCenter/index.tsx` 继续回退为 tab 路由与视图组合壳，并新增 hook 测试锁住 governance tab 加载与 batch approve 刷新语义。
- `2026-03-26` 补充：`Chat` 绑定恢复状态机也已从 `useChatRuntimeState` 抽离。默认 execution-core 自动绑定、失败控制线程重绑、缺 owner reset-chat 等恢复判定现统一收口到 `console/src/pages/Chat/chatBindingRecovery.ts`，页面状态 hook 不再散着维护 3 段 rebind/reset `useEffect`。
- `2026-03-26` 补充：`RuntimeCenter` 详情抽屉与行业专属 detail section 已正式从 `viewHelpers.tsx` 拆出。共享 detail primitive 已落到 `console/src/pages/RuntimeCenter/runtimeDetailPrimitives.ts`，行业 focus/main-chain/review section 已落到 `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`，detail drawer/record renderer 已落到 `console/src/pages/RuntimeCenter/runtimeDetailDrawer.tsx`；`viewHelpers.tsx` 现只保留 entry/card helper 与兼容导出壳，不再继续承载 detail-drawer god block。
- `2026-03-26` 补充：主脑 environment/recovery 语义已继续收紧。`MainBrainEnvironmentCoordinator` 现已显式区分 `environment_lease_token / continuity_source / resume_ready`，`MainBrainRecoveryCoordinator` 也不再把“本轮刚 admission 出来的 current kernel task id”误判成恢复依据；当前正式恢复口径已拆成 `resume-environment / rebind-environment / attach-environment / resume-runtime / resume-task / fresh`，只有带连续性证明（如 lease token / explicit continuity token）的 live body 才会被标记为真正可续现场。
- `2026-03-26` 补充：主脑 environment recovery 已进一步从“请求自证”切到“持久态实证”。`MainBrainOrchestrator` 现已显式注入 `EnvironmentService`，恢复判断会回查真实 `SessionMount` 的 `lease_status / lease_token / live_handle_ref`，不再信任 request 携带的 `environment_lease_token`；同时 request 上重复平铺的 `_copaw_main_brain_*` 兼容字段已删除，主脑正式运行上下文统一收口到 `_copaw_main_brain_runtime_context`（`_copaw_main_brain_intake_contract` 与 `_copaw_kernel_task_id` 继续保留给现有真实消费者）。
- `2026-03-25` 补充：`POST /goals/{goal_id}/dispatch`、`POST /goals/automation/dispatch-active`、`POST /runtime-center/goals/{goal_id}/dispatch` 已全部物理删除；旧 goal-dispatch HTTP 入口不再保留 `410` 兼容壳。
- `2026-03-25` 补充：`POST /capabilities/{id}/execute`、`POST /routines/{routine_id}/replay`、`POST /predictions/{case_id}/recommendations/{recommendation_id}/execute`、`POST /workflow-templates/{template_id}/launch`、`POST /workflow-runs/{run_id}/resume`、`POST /runtime-center/replays/{replay_id}/execute`、`POST /runtime-center/chat/orchestrate` 已全部物理删除；direct-execution retired shell 已从 router 层清空。
- `2026-03-25` 补充：execution-core 默认身份文案、行业 detail fallback 身份与 Runtime Center 战略样例数据已统一改成“主脑不亲自执行叶子动作；缺岗位时补位 / 改派 / 提案”，不再残留“没有合适执行位时主脑亲自执行”的旧口径。
- `2026-03-25` 补充：surface routing 的 hard-hint 逻辑已进一步收紧；未知应用在仅凭 mount/env 推断时优先落到 `desktop/browser` 交互面，不再因为挂了通用 `write_file` 就额外伪命中 `file` 面，app 名关键词继续只做兜底而不是主判据。
- `2026-03-25` 补充：runtime chat media 前门已补齐正式写回；行业 control thread 上的新附件与既有 `media_analysis_ids` 现在都会在进入 turn executor 前完成 `analysis -> prompt context -> backlog/strategy writeback`，不再只停留在“回答时参考附件”的半闭环。
- `2026-03-29` 补充：记忆 recall 对 `work_context_id` 的正式优先级也已补上。`KernelQueryExecutionService` / prompt recall 现在在存在 `work_context_id` 时会优先按共享工作上下文读取媒体/记忆命中，而不是只按 `task_id` 兜底；这使得同一 work context 下的素材分析与长期记忆在后续 follow-up turn 里不再容易漏召回。
- `2026-03-29` 补充：runtime chat media 这条链也已继续补厚成正式 `work_context` 闭环。行业 control thread 的 `media analyze / adopt existing analysis / memory retain / memory recall` 现在都会显式透传 `work_context_id`，媒体 writeback 会进入 `memory:work_context:*` scope，recall consumer 也会优先回显原始 `source_ref`，不再只看到 retain chunk 的内部 id。
- `2026-03-31` 补充：媒体闭环最后一段也已收口。`/media/analyses` 与 console chat 现在都会显式消费 `work_context_id`，恢复/换线程后的同一连续工作上下文仍能重新拉回既有 media analyses；主脑聊天侧在同时存在 `industry_instance_id + work_context_id` 时也会优先按 `work_context` 做 truth-first recall，不再把更细的媒体连续记忆让位给行业级粗粒度召回。
- `2026-03-31` 补充：media-backed memory trace 与 operator surface 也已补齐。truth-first recall 命中的 `media-analysis:*` 来源现在会直接回路由到原始 `/api/media/analyses/{analysis_id}`，`Runtime Center` 行业 detail 也已新增正式 `Media Analyses` section，不再只把媒体分析记录当 generic array 混在 detail drawer 里。
- `2026-04-02` 补充：truth-first memory 的主脑 scope snapshot 现已正式转向“scope snapshot + 增量刷新”。runtime chat media 的 retain/adopt 写回会通过同一条 `work_context / industry / agent` scope 解析链标记 snapshot dirty，下一轮只刷新相关 scope，不再为附件写回把整份主脑记忆上下文全量重建。
- `2026-04-02` 补充：`cc/cowork` donor 对齐这一轮已经从“文档映射”推进到当前主链的正式基线。`QueryExecutionRuntime` 现已在进入长执行前记录正式 `accepted` persistence boundary，并把 `accepted_persistence / commit_outcome` 写回 runtime context；runtime chat sidecar 现已显式区分 `accepted / reply_done / commit_started / confirm_required / committed / commit_failed`，不会再在已知 writeback 失败时继续乐观发 `committed`；`MainBrainChatService` 现已把 donor 风格的双 checkpoint flush 扩到当前 runtime chat / session-backed main-brain chat front door，`MainBrainResultCommitter` 也已尊重下游 writeback/kickoff 的真实返回。`Runtime Center` 现已具备正式 bridge lifecycle ops：`ack / heartbeat / stop / reconnect / archive / deregister`，external bridge producer 还能通过同一条 canonical surface 驱动 `browser_attach` transport/session/scope/reconnect truth；`health_service` 会把 `bridge_work_id / bridge_work_status / bridge_heartbeat_at / bridge_session_id / bridge_stopped_at / bridge_stop_mode / workspace_trusted / elevated_auth_state` 统一投影进 `seat_runtime / host_companion_session.bridge_registration`。另外，desktop app projection 现已对 prompt-facing `app_identity / window_anchor_summary` 做 sanitization；`surface_control_service.execute_windows_app_action()`、`execute_document_action()` 与 `execute_browser_action()` 现已都具备 execution-time `operator abort / host exclusion / frontmost verification / clipboard roundtrip verification` guardrail，并通过 runtime event bus 发布 `desktop.guardrail-blocked`、`document.guardrail-blocked`、`browser.guardrail-blocked`；共享 `operator_abort_state` 也已成为同一条 session/environment truth，可通过 Runtime Center 正式写入/清除并在 live execution boundary 生效。与此同时，stable host-scoped memory continuity 已正式落在 `work_context_id + truth-first memory + scope snapshot incremental refresh` 主链上，不再需要 donor 风格 file memory / repo-worktree heuristics。当前 donor 文档仅保留一个条件性 future follow-up：如果 CoPaw 将来真的长出与 donor 相同的 remote-session transport 形态，再补同型 stall/reconnect reliability，而不是现在预先造第二套子系统。
- `2026-04-03` 补充：`cc` donor 纪律下剩余的两条 verified partial gap 现已正式收口。`CapabilityExecutionFacade` 的 direct write path 不再只靠 capability-id fallback 判断写语义；mount-declared `execution_policy` 现在会把 direct capability write 统一包进 shared writer lease 前门，`writer_scope_source=file_path` 的 built-in file mutator 也已正式采用这条写链。与此同时，`surface_control_service` 的 browser / document / windows-app live action 现已统一走 `guardrail -> acquire_shared_writer_lease -> execute -> release_shared_writer_lease`，writer scope 优先取显式 contract/session detail，缺省再回落到 `session_mount_id`，冲突会在 executor 前以 `reserved` 语义阻断。`QueryExecutionRuntime` 也已把 compaction/sidecar 状态正式对象化为 canonical `runtime_entropy` contract，并保留 `query_runtime_entropy` 作为同一 truth 的兼容投影；`runtime_bootstrap_execution` 与 `Runtime Center governance overview` 现已消费同一套 typed entropy payload，`sidecar_memory` 只作为 convenience projection，不再单独发明 read-model 状态。focused aggregate verification：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capabilities_execution.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_windows_apps.py tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_bootstrap_split.py tests/app/test_operator_runtime_e2e.py -q` -> `107 passed`。
- `2026-04-02` 补充：`real-user browser/desktop body runtime` 这一轮 acceptance 已补齐到“代码闭环 + focused regression + live smoke 记录”三层。focused regression：`python -m pytest tests/kernel/test_query_execution_runtime.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/environments/test_cooperative_windows_apps.py tests/agents/test_browser_tool_evidence.py tests/app/runtime_center_api_parts/detail_environment.py -q` -> `107 passed`。live smoke：`COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 python -m pytest tests/routines/test_live_routine_smoke.py -q -k "authenticated_continuation_cross_tab_save_reopen_smoke or live_desktop_routine_replay_round_trip"` -> `2 passed`。其中 browser smoke 已在真实浏览器 routine 链上跑通 authenticated continuation / cross-tab reuse / save-and-reopen / download-initiation / screenshot evidence；desktop smoke 也已打通，最后的阻塞是 `WindowsDesktopHost.get_foreground_window()` 对 live caller 只返回嵌套 `window.handle`、没有顶层 `handle` 的兼容缺口，现已修复。
- `2026-04-03` 补充：execution harness 这轮“值得继续补”的 4 项已收口到当前主线。`WindowsDesktopHost.poll_operator_abort_signal(...)` 已能把宿主侧 ESC 中止信号写入 canonical shared `operator_abort_state`，`EnvironmentService / EnvironmentLeaseService` 没有引入第二真相源；desktop routine 的 environment path 现在也会显式传入带 host hooks 的 executor adapter，host-side abort polling / foreground restore / clipboard restore verification 不再只是测试面接口。`surface_control_service` 的 cleanup / restore discipline 已显式化，live browser/document/windows 边界会统一走 foreground capture/restore，并在 host-side clipboard restore verification 失败时 fail closed；lease / attach hardening 现在会在 `release / stop / archive` 后清掉 stale `browser_attach` continuity，并同步更新 lease/runtime descriptor，不再让 reconnect 继承脏 attach truth；routine acceptance 也已继续扩面，`tests/routines/test_routine_service.py` 现覆盖 operator-abort retry / auth-expired reconnect cleanup / browser+desktop page-tab contention，live smoke helper 则会回传 per-run cleanup 与最终 `stop_payload`，并新增 gated 的 browser reconnect cleanup / desktop cross-surface contention smoke。当前 focused regression：`PYTHONPATH=src python -m pytest tests/adapters/test_windows_host.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py tests/routines/test_routine_service.py tests/routines/test_routine_execution_paths.py tests/routines/test_live_routine_smoke.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_main_brain_commit_service.py -q` -> `231 passed, 9 skipped`；expanded gated live smoke：`COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 PYTHONPATH=src python -m pytest tests/routines/test_live_routine_smoke.py -q -k "reconnect_cleanup_smoke or cross_surface_contention_smoke or live_desktop_routine_replay_round_trip"` -> `2 passed, 1 skipped`。其中 browser reconnect cleanup smoke 在宿主无法启动 browser runtime 时会显式 skip，而不是把前置条件失败误报成产品回归。
- `2026-04-03` 补充：多执行位能力自治这轮已在特性分支 `multi-seat-capability-autonomy` 完成后端实现并合并回 `main` 的当前集成态。当前正式能力治理口径已落成 `全局能力底座 / 角色原型能力包 / 执行位实例能力包 / 周期增量包 / session overlay` 五层，并已接到 query fast-loop、seat/session MCP overlay、governed remote skill lifecycle、prediction rollout/rollback、Runtime Center / industry detail read-model。合并收口时额外补掉了几个真实尾巴：1）hub-skill mock/install 在缺少本地 `SKILL.md` 持久化目标时改为 fail-soft，不再把 bootstrap/trial 整条链误判为失败；2）Runtime Center 在无 live task 时会优先回显最近 operator writeback 链，而不是被新的 queued assignment 抢走 `routine/report` 主链真相；3）显式 assignment/backlog 选中与 report-followup backlog 现在会稳定进入 runtime focus，但在存在 live task 时仍不会凭 task title 伪造 focus。merged-main fresh verification：`PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q` -> `259 passed`；adjacent regressions：`PYTHONPATH=src python -m pytest tests/app/test_capabilities_execution.py tests/agents/test_skills_hub.py tests/app/test_capabilities_api.py tests/app/test_capability_catalog.py -q` -> `61 passed`；focused integration slice：`PYTHONPATH=src python -m pytest tests/app/test_industry_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_capability_market_api.py tests/app/test_capability_skill_service.py tests/industry/test_runtime_views_split.py -q` -> `190 passed`。
- `2026-03-25` 补充：`run_operating_cycle()` 已切掉 `goal` 物化中转；backlog 现在直接生成 `Assignment` 并编译成 assignment-backed `TaskRecord`，`AgentReport` 也优先按 `assignment_id` 回收，不再走旧 goal-phase 假链。
- `2026-03-25` 补充：`main_chain.routine` 在没有 live task 时，会回锚到最新 `AgentReport` 对应的 assignment/task 元数据；已完成的固定 SOP / routine 执行不会再在主链上丢失执行面信息。

### 3.3.1 `Symbiotic Host Runtime V1` 当前落地边界

- 这次回写的含义，是把 execution-side 的正式口径、对象映射与当前阶段施工边界写成统一状态事实；它不是在声明所有配套文档、后续 phase 能力或成熟态宿主投影已经全部交付。
- 当前已完成到“正式口径 + 正式映射 + Phase 1 基线边界锁定”这一层：`Intent-Native Universal Carrier` / `Symbiotic Host Runtime` / `Windows Seat Runtime Baseline` 已成为状态板、总方案、数据模型与 API 迁移图一致的正式主线。
- 当前已有基线主要仍落在统一底座：`SRK` 已拥有 admit/risk/decision/evidence 闭环，`EnvironmentMount / SessionMount` 已持久化 `lease_status / lease_owner / lease_token / lease_acquired_at / lease_expires_at / live_handle_ref` 并具备 `acquire / heartbeat / release / reap` 生命周期；这次版本是在该基线上，把 `Seat Runtime / Host Companion Session`、shared `Surface Host Contract`、browser `Site Contract`、Windows `Desktop App Contract` 明确收口为 execution-side 当前正式施工面。
- `Workspace Graph V2` 在这次版本中的正式推进程度，只到 `Windows Seat Runtime Baseline` 所需的最小正式 projection：它已被正式收敛为 `TaskRuntime + EnvironmentMount + SessionMount + Artifact/Evidence` 的派生投影，并进入当前阶段正式范围；它还不是 Phase 3 那种跨 browser / app / file-doc / clipboard / downloads / artifacts / locks / handoffs 的完整工作区视图。
- `Host Event Bus V1` 在这次版本中的正式推进程度，只到 `Windows Seat Runtime Baseline` 所需的最小正式 mechanism：它已被正式收敛为基于 `EvidenceRecord + ObservationCache + environment/runtime detail` 的运行机制与恢复入口，并进入当前阶段正式范围；它还不是 Phase 4 那种完整的 active-window / modal / UAC / login rescue / download-completion 宿主事件总线。
- `2026-03-27` 补充：`Phase 1 final acceptance closeout` 已在代码侧关账。当前正式结果包括：
  - `Runtime Center / task-review` 已对 acceptance closeout evidence 做正规 normalization，不再强依赖顶层 `step_id / step_title / verification_status`；`verification / step / checkpoint / closeout` payload 现在可稳定投影到 `continuity`、`evidence_status` 与最近 replayable evidence 读面。
  - `routine replay` 已新增正式 `verification_summary` 聚合，并进入 `RoutineDiagnosis`；browser/desktop replay 不再只看动作是否执行，而会汇总 `chain_status / verified_steps / observed_steps / evidence_anchors`。
  - live browser smoke 已扩展到本地 HTML acceptance chain 的完整收口，当前可在真实浏览器会话上跑通 `open / multi-tab / authenticated continuation / save-and-reopen / upload / download-initiation / screenshot`，并留下 replayable evidence anchors。
  - browser acceptance closeout 已补齐关键底层语义修正：`wait_for_function` 文本参数关键字传递、`tabs.switch -> select` 兼容、logical page handle rebind、重复 page handle 去重、`click.wait` 的 post-click settle、download listener 的 `suggested_filename` property 兼容、HTTP root URL canonicalization（如 `https://example.com` 与 `https://example.com/`）。
  - Windows desktop/document closeout 已收紧为正式失败/验证语义：ambiguous window selector 不再假成功，focused-window / modal interruption / post-write reread / save-reopen evidence 已进入正式 contract 与 replay verification。
  - environment/runtime visibility closeout 已补齐 `host_contract / browser_site_contract / desktop_app_contract / workspace_graph / host_event_summary` 的 Phase 1 acceptance projection，不新增第二真相源。
  - 当前一轮完整 Phase 1 验收组合已验证通过：`139 passed, 1 skipped`。唯一 skip 是 live desktop smoke 对“可解析前台 Windows 窗口”的宿主前提检查；它代表当前座席条件未满足，不再视为代码欠账。
- 仍属于后续阶段的内容包括：更完整的 shared host/site/app contract 实装、`Seat Runtime / Host Companion Session` 的恢复与交接策略、`Cooperative Adapters`、完整 `Workspace Graph`、完整 `Host Event Bus`，以及 `Execution-Grade Host Twin -> Full Host Digital Twin` 的成熟态投影。

### 3.3.2 `Phase 2 Cooperative Adapters` 当前真实进度

- cooperative runtime slice 已有独立环境测试基线：`tests/environments/test_cooperative_browser_companion.py`、`tests/environments/test_cooperative_document_bridge.py`、`tests/environments/test_cooperative_watchers.py`、`tests/environments/test_cooperative_windows_apps.py` 已落仓。
- Phase 2 主链已正式接通：`EnvironmentService` 现已暴露 cooperative facade，并通过现有 `EnvironmentMount / SessionMount` metadata、`RuntimeEventBus` 与 `cooperative_adapter_availability` projection 统一承载 browser companion、document bridge、host watchers、Windows app adapters，不新增第二真相源。
- capability graph / install-template / product API 侧已进入可验收状态：`CapabilityRegistry` 已收进 cooperative system capabilities，`capability_market` router 已把 `environment_service` 正式透传到 install-template surface，`install_templates.py` 已补齐 `browser-companion`、`document-office-bridge`、`host-watchers`、`windows-app-adapters` 四类模板的 builder、doctor、example-run 与 install 路径。
- `2026-03-27` focused acceptance 已验证通过：`python -m pytest tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_capability_market_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q` -> `79 passed`。
- Phase 2 期间暴露的独立 routine replay 回归现已实修完成：`RoutineService` 的 browser URL verification 已与 browser tool 契约对齐，优先消费工具返回的导航锚点而不是无条件追加 `evaluate window.location.href`；成功路径测试中的 browser screenshot mock 也已补成真实落文件语义，不再用不完整响应伪装成功。
- `2026-03-27` 宽回归复跑已验证通过：`python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py -q` -> `106 passed`。
- 下一步边界应转入 Phase 3/4：继续深化 `Workspace Graph`、`Host Event Bus` 家族与更完整的 runtime center 可见化；当前不再保留已知的 Phase 2 独立 routine replay 回归阻塞。

### 3.3.3 `Phase 3 Workspace Graph` 当前真实进度

- `Workspace Graph` 的正式实现已从“只给 refs 和 count”推进到结构化工作区投影：`EnvironmentHealthService.build_workspace_graph_projection(...)` 现在在不新增第二真相源的前提下，继续基于既有 `EnvironmentMount / SessionMount / Artifact / Evidence / host_event_summary / live handle` 派生 `locks`、`surfaces`、`ownership`、`collision_facts`、`collision_summary` 与 richer `download_status / surface_contracts / handoff_checkpoint`。
- 当前 `locks` 已显式给出 writer-lock 的 `resource_ref / summary / surface_ref / account_scope_ref / status / scope / owner_agent_id / lease_class / access_mode / handoff`，不再只剩一句 `active_lock_summary`；但这些字段仍全部来自既有 session/environment/contract/runtime facts，而不是新建锁对象库。
- 当前 `surfaces` 已把 browser / desktop / file-docs / clipboard / downloads / host-blocker 收成同一工作区视图：浏览器会显式暴露 `context_refs + active_tab`，桌面会显式暴露 `window_refs + active_window`，file/doc、clipboard、downloads 也都有 active ref 与 workspace scope；这样 execution-side 已能在一个投影里回答“现在开着什么、写着什么、卡在哪、下载落哪、下一步谁该接”。
- 当前工作区 ownership/collision 读面也已正式化：`owner_agent_id / account_scope_ref / workspace_scope / handoff_owner_ref / ownership_summary / collision_facts / collision_summary` 已进入 runtime/environment detail 投影，用于表达共享账号、writer 冲突、handoff 人工返回与 active surface owner，而不是把这些冲突事实继续埋在私有 metadata 或宿主日志里。
- Runtime Center API/read-model 契约现已和真实工作区投影对齐：`tests/app/runtime_center_api_parts/shared.py` 的 fake environment payload 已同步成与真实 `health_service` 同形的 workspace graph；`detail_environment`、`runtime_projection_contracts`、`runtime_query_services` 也已锁住 richer `locks / surfaces / ownership / collision` 读面，不再保留“真实实现一套、stub 一套”的分叉。
- `2026-03-27` focused Phase 3 acceptance 已验证通过：`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q` -> `40 passed`。
- `2026-03-27` Phase 3 合并后宽回归已验证通过：`python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py -q` -> `106 passed`。
- 下一步边界继续转入 Phase 4/5：`Host Event Bus` 家族还需要从当前 summary/alert/pending-recovery 机制继续深化到更完整的 event-driven runtime loop，前台 Runtime Center 也还需要把 workspace/seat/handoff/recovery 的可见化继续做厚；但当前 `Workspace Graph` 已不再停留在“最小 V2 refs-only projection”阶段。

### 3.3.4 `Phase 4 Host Event Bus` + `Phase 5 Execution-Grade Host Twin` 当前真实进度

- `Host Event Bus` 已从“只有 summary/alert/pending-recovery 的读面”推进到正式 runtime mechanism 输入：`EnvironmentHealthService.build_host_events_projection(...)` 现在除 `family_counts / latest_event_by_family / active_alert_families` 外，还会显式派生 `blocking_event_families / recovery_event_families / latest_blocking_event / latest_recovery_event / latest_handoff_event / human_handoff_active / scheduler_inputs`，并保持 `is_truth_store=False`，不新增第二事件库。
- 人接管/人返回不再只是宿主日志或聊天暗示：`host.human-takeover`、`host.human-return-ready` 已进入同一 host-event 机制，正式归一为 `human-handoff-return` 家族，并可在 `pending_recovery_events[*].legal_recovery_path` 上给出 `decision / resume_kind / checkpoint_ref / verification_channel / return_condition`，从而把 `handoff / recover / retry` 变成正式 runtime 输入。
- `Execution-Grade Host Twin` 已正式落地到 environment/session detail：`host_twin` 明确标注 `projection_kind=host_twin_projection`、`is_projection=True`、`is_truth_store=False`，并派生 `ownership / seat / surface_mutability / blocked_surfaces / continuity / trusted_anchors / legal_recovery_path / active_blocker_families / latest_blocking_event / execution_mutation_ready / scheduler_inputs / recovery_inputs`，不新建第二真相源。
- `host_twin` 当前已能回答 Phase 5 要求的 5 个关键问题：谁持有 seat、哪些 surface 现在可写、continuity 是否仍有效、哪些 anchor 可信、当前合法恢复路径是什么；并且会把这些答案回投到 `Runtime Center / task review / workflow preview`，不再让每个消费面自己猜 host 状态。
- Runtime Center 读面已对齐真实 host twin 契约：`runtime_center_routes_ops.py` 已把 `host_twin` 纳入 formal runtime surface keys；`tests/app/runtime_center_api_parts/shared.py` 的 fake environment payload 也已补齐同形 `host_twin`，避免“真实 payload 一套、stub 一套”的再次分叉。
- `RuntimeCenterStateQueryService` 与 task-review projection 已正式接 `host_twin`：environment feedback 会带回 `host_twin`，`build_task_review_payload(...)` 也会显式回传 `execution_runtime.host_twin`，并优先使用 twin 的 blocker/recovery/anchor/writable-surface 事实生成 continuity、风险和 next-step 提示。
- workflow preview 现在已经把 host twin 作为真实 preflight consumer，而不是只看 capability/assignment 缺口：`WorkflowTemplateService` 会读取 environment detail 的 `host_twin`，对 mutating desktop/browser work 正式发出 `host-twin-continuity-invalid / host-twin-writable-surface-unavailable / host-twin-recovery-handoff-only / host-twin-active-host-blockers` 这类 launch blocker；runtime bootstrap 也已把 `environment_service` 接入 workflow service，避免只在测试 app 生效。
- `2026-03-27` Phase 4/5 focused acceptance 已验证通过：`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_workflow_templates_api.py -q` -> `95 passed`。
- `2026-03-27` Phase 4/5 宽回归已验证通过：`python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_workflow_templates_api.py -q` -> `126 passed`。
- 当前 repo 定义内的 `Full Host Digital Twin` 已完成收口；本文件对它的判断统一收口到 `6.1` 的“当前已闭环 / 终态标准”，不再在历史记录里混写“下一步扩展”。
- `2026-03-27` 补充：`Phase 6 Full Host Digital Twin` 的实施顺序与设计约束已用于本轮收口：先补 `host_twin.app_family_twins + coordination` 派生投影，再补 Runtime Center/task-review 读面，再补 workflow preview/run/resume 与 fixed-SOP doctor/run 对同一 host truth 的消费；并保持 `Workspace Graph` 为 projection、`Host Event Bus` 为 runtime mechanism、`host twin` 为 derived projection，不新增第二真相源。
- `2026-03-27` ~ `2026-03-30` 的正式收口包括：
  - `host_twin` 已正式补齐 `app_family_twins` 与 `coordination` 派生投影，`seat_runtime` 也已带上 `status / occupancy_state / candidate_seat_refs / selected_seat_ref / seat_selection_policy / expected_release_at`。
  - `Runtime Center / task review` 不再只透传 `coordination` 原始字段，而会显式把 `recommended_scheduler_action / contention_forecast / seat_selection_policy` 进入 summary、next action 与 risk 读面。
  - workflow preview / launch / run detail / resume / cron 已统一消费 canonical host truth：`host_requirements`、`host_snapshot`、schedule `environment_ref / environment_id / session_mount_id / host_requirement` 与 cron dispatch host meta 已全部落到正式链路，不再回退成仅靠 `session:{channel}:{session_id}` 猜环境。
  - fixed SOP doctor / run / run detail 已统一消费 canonical host preflight，正式暴露并落证 `environment_id / session_mount_id / host_requirement / host_preflight`；非法 writable path 会被 doctor 阻断，并在 run 入口返回显式错误，而不是盲跑。
  - `tests/app/test_cron_executor.py` 已补入 Phase 6 验收面，用于锁住 cron 对 stored host refs / scheduler inputs 的消费契约。
- `2026-03-29` 补充：execution-side 的 canonical host truth 已继续补齐到正式读链。`host_twin` 对 stale blocker / stale handoff history 的抑制现在只会在“当前 host/session 事实已恢复 clean + latest handoff event 明确进入 return-ready/return-complete”时生效，不再因为残留 recovery metadata 就把 live blocker 错误吞掉；`Runtime Center` overview/task-review 也已优先消费同一条 canonical `host_twin_summary`，不会再把 `recommended_scheduler_action=proceed` 误当阻断。
- `2026-03-29` 补充：workflow resume / cron / fixed SOP 这条 host-aware 执行链也已继续补厚。workflow run detail、resume 与 schedule meta 现在会从 live `host_twin` 回填 `host_snapshot / environment_ref / environment_id / session_mount_id / host_requirement`，fixed SOP doctor/run 也会正式阻断 `requires_human_return`、`legal_recovery.path=handoff` 及需要 `handoff/recover/retry` 的 blocker event，不再让“handoff-only 恢复路径”假装可执行。
- `2026-03-29` 补充：workflow preview / fixed SOP doctor 对 canonical host summary 的优先级也已补齐。当 top-level 或 nested `host_twin_summary` 已明确给出 `recommended_scheduler_action=proceed|continue`、`blocked_surface_count=0` 与非 handoff 的 `legal_recovery_mode` 时，消费面会优先信任这条 canonical summary，而不是继续被 stale handoff metadata 反向卡死；workflow run/schedule 持有的 host snapshot 也会同步沿用同一条 summary 口径。
- `2026-03-30` 补充：`Full Host Digital Twin` 在当前仓库定义内已完成最终收口。`host_twin` 现在会基于同一宿主/账号/workspace scope 派生真实 multi-seat candidate 集，统一给出 canonical `candidate_seats / selected_seat_ref / selected_session_mount_id`，并把跨 seat 的 writer contention 正式体现在 coordination / handoff 语义里；当当前 seat 已阻断但同 scope 的 alternate ready seat 可用时，canonical selected seat 会切到可继续执行的 seat，而不是继续抱着 stale seat/session 不放。
- `2026-03-30` 补充：workflow preview / run-resume / cron / fixed-SOP 现已全部优先消费同一条 canonical selected seat/session truth。下游在 scheduler meta、run detail、host preflight 缺位或陈旧时，会统一回退到 live `host_twin_summary` 与 `multi_seat_coordination.selected_*`，不再出现 workflow、cron、fixed-SOP 各自拿不同 seat/session 的分叉。
- `2026-03-30` 补充：phase-next smoke 已补入宿主切换闭环。`tests/app/test_phase_next_autonomy_smoke.py` 现会覆盖 host switch + reentry + replay continuity，验证 canonical host truth 切换后，workflow 与 fixed-SOP 仍沿用同一 selected seat/session，且 evidence/replay continuity 不断裂。
- `2026-03-30` 补充：`document` 已成为一等 host-aware execution surface，而不再只是 `office_document` app-family 的隐式别名。workflow preview 现在会保留显式 `surface_kind=document` 的 host requirement；workflow run detail 会正式回传 `host_requirement / host_requirements`；fixed-SOP doctor/run 也会把 `document` 正确映射到 canonical `desktop_app` 写面，而不是误落到 browser 分支。对应 `tests/app/test_workflow_templates_api.py`、`tests/fixed_sops/test_service.py`、`tests/app/test_fixed_sop_kernel_api.py` 与 `tests/app/test_phase_next_autonomy_smoke.py` 的 document-aware 回归已通过。
- `2026-03-29` 补充：`Runtime Center / /industry` 的 execution-side 可见化也已对齐长跑读面。`Host Twin` section 现会显式展示 `handoff owner / recovery checkpoint / verification channel / blocking-event state / mutation readiness / active app-family surfaces / trusted anchors`；`/industry` focused runtime 与 planning surface 也会带出 supervisor follow-up pressure、recommended actions、control-contract items 与 staffing pressure，不再只剩最薄摘要。
- `2026-03-27` 补充：当前仓库在 worktree 模式下做 Phase 6 验收时，必须显式把 `PYTHONPATH` 指到 `D:\\word\\copaw\\.worktrees\\codex-phase6-host-twin\\src`；否则 `pytest` 会从主仓 `D:\\word\\copaw\\src` 导入，存在假完成/假失败风险。当前已用该导入路径复核 `copaw.__file__` 与 `FixedSopRunRequest` 字段面，确认验收到的是本 worktree 代码。


### 3.4 当前 single-industry autonomy 基线

- `IndustryService.apply_execution_chat_writeback()` 已不再只是文本写回。
- seat gap 现已按正式 `seat_gap_policy` 走三岔路：
  - 现有岗位承接
  - 低风险临时位自动补位
  - 高风险或长期岗位走治理提案
- `IndustryInstanceDetail` 已有 canonical `staffing` 读面，包含：
  - `active_gap`
  - `pending_proposals`
  - `temporary_seats`
  - `researcher`
- `MainBrainChatService`、`Runtime Center`、`/industry`、`AgentWorkbench` 已开始消费这块共享 staffing 读面。

### 3.5 当前主脑综合闭环基线

- `AgentReportRecord` 已扩展 richer report 字段：
  - `findings`
  - `uncertainties`
  - `recommendation`
  - `needs_followup`
  - `followup_reason`
- 主脑侧已存在 explicit report synthesis 读面，可看到：
  - `latest_findings`
  - `conflicts`
  - `holes`
  - `needs_replan`
  - `control_core_contract`
- `/industry`、`Runtime Center`、`AgentWorkbench` 已能看到综合状态、冲突/缺口与 replan 标记。

### 3.6 当前 capability / discovery / acquisition 基线

- `CapabilityDiscoveryService` 已进入正式链路。
- capability discovery 已打通：
  - discovery
  - acquisition proposal
  - install / upgrade
  - binding
  - onboarding validate
- 官方 `MCP Registry` 已接入共享 discovery/acquisition 主链。
- `LearningService` 的 `mcp:*` onboarding validate 已升级为真实活体握手与安全零参数工具试运行，不再只是“配置存在性检查”。

### 3.7 当前已退役或不应恢复的旧形态

- `/runtime-center/chat/intake` 已退役。
- `task-chat:*` / `actor-chat:*` 前台聊天心智已退役。
- `query_confirmation_policy` 已删除。
- 人类直连底层执行入口已退役：
  - capability direct execute
  - replay direct execute
  - prediction recommendation direct execute
- 默认产品链路必须保持：
  `人类 -> 主脑 -> agent 执行`

---

## 4. 当前收口判断

截至 `2026-04-01`，本仓库应按“核心闭环是否已经完成、哪些只是仓库门槛、哪些仍是真未完成项”来判断状态，不应再把所有 guardrail / 接线 / 展示加厚都写成开放式长期任务。

### 4.0 已完成：hard-cut autonomy rebuild

目标：

- 把当前混合主链直接切成唯一自治主链
- 停止把 `GoalRecord / active goal / schedule` 当成主脑规划真相
- 让 `MainBrainChatService` 彻底退出 durable runtime mutation
- 让旧数据通过 reset 明确退出，而不是继续背历史包袱

当前状态：

- 硬切 spec 与 implementation plan 已落地
- 用户已明确接受停机窗口、旧数据直接删除、旧前后端入口一起下线
- `scripts/reset_autonomy_runtime.py` 与 `tests/app/test_runtime_reset.py` 已落地并通过首轮验证
- Task 7/8 已完成：runtime health、shared control-chain presenter、Runtime Center / Industry / AgentWorkbench 新读面全部上线
- Task 9 已完成产品面删旧：runtime-center direct delegate route 已物理删除，console 侧旧 goal-dispatch 文案已下线
- `2026-03-25` 补充：Task 10/11 已完成收口，formal operating-cycle 已完全切成 `assignment -> task -> report`，历史 retirement 回归已更新到 live contract，不再拿 `waiting-confirm` / `goal` 节点当当前主链。

结论：

- 本项已完成，不再作为开放任务继续挂起。
- 后续若发现主链回退、旧入口复活或 reset 失效，按回归缺陷单独登记。

### 4.1 已完成：single-industry autonomy closure

目标：

- 主脑收到 operator 指令后，优先把工作路由给现有执行位
- 没有合适执行位时，低风险任务自动补临时位
- 高风险或长期岗位需求进入治理提案
- researcher 作为长期观察位持续回流
- 上述状态必须同时在 prompt、state、API、UI 四层一致可见

当前状态：
- 已有正式 staffing 读面
- 已有 seat gap policy
- 已有 UI surface
- `2026-03-24` 补充：surface-first 路由、seat gap 回填、supervisor-only backlog/schedule 元数据、监督链可见化与对应回归已完成一轮正式收口。
- `2026-03-26` 补充：更大回归面已再次通过，`tests/app/industry_api_parts/bootstrap_lifecycle.py`、`tests/app/industry_api_parts/runtime_updates.py`、`tests/app/industry_api_parts/retirement_chain.py`、`tests/state/test_main_brain_hard_cut.py` 与 `console/src/runtime/staffingGapPresentation.test.ts` 均通过；`single-industry autonomy closure` 的 seat-gap、temporary seat、staffing read surface 与 UI helper 现阶段已形成稳定代码基线。
- `2026-03-28` 补充：seat proposal 在批准并完成 `system:update_industry_team` 后，`IndustryInstanceDetail.staffing.active_gap / pending_proposals` 现会随 live team 实际闭合而消失，不再被 backlog 上残留的 `waiting-confirm` 元数据长期卡住；同一轮里，失败/阻塞 assignment 的 follow-up backlog 已改成“新 follow-up 接棒、原 materialized backlog 收尾 completed”，避免旧 backlog 永远悬在已物化态。
- `2026-03-29` 补充：long-horizon governance 写链已继续收口到统一 kernel 壳。`/runtime-center/schedules*` 与 `/cron/jobs*` 的 create/update/delete/run/pause/resume 现全部通过 `system:create_schedule / update_schedule / delete_schedule / run_schedule / pause_schedule / resume_schedule` 进入 governed mutation，不再让 HTTP frontdoor 直接调用 `CronManager`；`/runtime-center/learning/patches/{id}/approve|reject|apply|rollback` 也已统一走 kernel-governed system mounts，旧 `/learning/patches/{id}/*` 单条写入口已物理退役。
- `2026-03-29` 补充：`GovernanceStatus` 已扩成正式 runtime blocker 读面，新增 `host_twin / handoff / staffing / human_assist` 摘要；`GovernanceService.admission_block_reason(...)` 现会在 `system:dispatch_query / system:dispatch_command` 前正式检查 handoff、人协作阻塞与 staffing confirmation，而不再只看 emergency stop。
- `2026-03-29` 补充：新的治理主链回归已补齐 `submit -> waiting-confirm -> approve/reject -> evidence/writeback`。当前已通过 `tests/app/test_learning_api.py`、`tests/app/runtime_center_api_parts/overview_governance.py`、`tests/app/runtime_center_api_parts/detail_environment.py`、`tests/kernel/test_governance.py`、`tests/app/test_operator_runtime_e2e.py` 与 `tests/app/test_capabilities_execution.py` 的相关套件。
- `2026-03-29` 补充：single-industry 的真实长跑闭环已继续从“主链存在”推进到“监督/补位/重排链成套回归”。当前已锁住 `staffing approval -> materialization -> failed assignment report -> follow-up backlog -> synthesis/replan` 这条链；follow-up backlog 会继承原 supervisor/staffing/writeback metadata，并在默认 focused runtime 里优先于无关 active assignment 进入当前执行焦点，而不再被旧 assignment 或旧 backlog 抢焦点。
- `2026-03-29` 补充：治理层对 long-run staffing truth 的拦截也已继续补严。即使最新 `active_gap` 已转成 `routing-pending`，只要仍有 pending staffing proposal 未决，dispatch admission 仍会被正式阻断；这保证了 single-industry 的“岗位补位确认”不会因为 backlog/route 重排而被静默绕过。
- `2026-03-29` 补充：更宽的 industry 长跑回归已再次通过，当前已重新跑过 `tests/app/industry_api_parts/runtime_updates.py`、`tests/app/industry_api_parts/bootstrap_lifecycle.py`、`tests/app/industry_api_parts/retirement_chain.py` 与 `tests/industry/test_report_synthesis.py` / `tests/industry/test_seat_gap_policy.py` 的关键套件；seat staffing、report synthesis、follow-up replan 与 focused runtime 读面现阶段已形成稳定代码基线。
- `2026-03-29` 补充：report follow-up 的 control contract 也已继续补齐。由 failed report / synthesis 生成的新 follow-up backlog 现在会保留 `control_thread_id / session_id / environment_ref / chat_writeback_channel / requested_surfaces` 等跨周期执行线索；后续即使只剩 session/control-thread 线索，governance、human-assist 与 runtime focus 仍能把 browser/desktop/document follow-up 压力接回同一条 canonical runtime chain。
- `2026-03-30` 补充：single-industry 的 `handoff -> human_assist -> resume` 控制线程闭环已正式补齐。治理层创建的 host-handoff `HumanAssistTask` 现在会预写 `work_context_id / environment_ref / control_thread_id / requested_surfaces / recommended_scheduler_action / recovery checkpoint` 等 continuity 上下文；Runtime Center `chat/run` 提交宿主回执时会 merge 新证据而不覆盖这批隐藏上下文，resume path 也会把同一组 `work_context + environment + recovery` 继续写回 `request_context / KernelTask`，不再把恢复动作降级成脱离原链的“重新聊一次”。
- `2026-03-30` 补充：对应真实长跑 smoke 已补齐并再次通过。当前已新跑 `tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_industry_long_run_smoke_keeps_handoff_human_assist_and_replan_on_one_control_thread`，并复跑 `tests/state/test_human_assist_task_service.py tests/kernel/query_execution_environment_parts/confirmations.py tests/kernel/test_main_brain_runtime_context_consumption.py tests/kernel/test_governance.py tests/app/test_runtime_human_assist_tasks_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_phase_next_autonomy_smoke.py -q` -> `111 passed`。
- `2026-03-26` 补充：learning/runtime-center P1-P3 硬切已完成一轮正式验证，已通过
  `tests/app/test_learning_api.py`、
  `tests/app/test_runtime_center_api.py`、
  `tests/app/runtime_center_api_parts/overview_governance.py`、
  `tests/app/test_runtime_center_actor_api.py`、
  `tests/app/industry_api_parts/bootstrap_lifecycle.py`、
  `tests/app/industry_api_parts/runtime_updates.py`、
  `tests/app/industry_api_parts/retirement_chain.py`、
  `tests/state/test_reporting_service.py`、
  `tests/kernel/test_agent_profile_service.py`、
  `tests/app/test_capabilities_execution.py`、
  `tests/app/test_industry_service_wiring.py`。
- `2026-03-26` 补充：第二轮 deep-cut 已落地到 live 代码路径：
  `LearningPatchService` 与 `LearningAcquisitionService` 已切到
  `patch_runtime.py` / `acquisition_runtime.py`，
  `RuntimeCenterOverviewBuilder` 已降为分组编排壳并由
  `overview_groups.py` 承接 operations/control/learning 三组卡片；
  新增验证 `tests/kernel/test_learning_runtime_domains.py` 与
  `tests/app/test_runtime_center_overview_group_builders.py` 已通过。
- `2026-03-31` 补充：真实世界覆盖/长期自治回归的当前口径已与 `6.1` 对齐，不再把这项写成开放式尾巴。`tests/app/test_phase_next_autonomy_smoke.py` 的长跑 smoke 现在除 `handoff -> human-assist -> resume -> replan` 外，也显式锁住同一条 phase-next 连续链中的 `multi-seat candidate/selected seat` 与 `multi-agent shared-writer contention`，当前 repo 定义范围内已收口；后续只保留 `6.1` 里的终态标准，不再在历史记录里重复写“仍需继续补更大范围覆盖”。

结论：

- 本项已完成，不再作为开放任务继续挂起。
- 后续如新增行业执行位、真实世界新场景或新治理对象，按新增功能单独立项。


### 4.1.1 `2026-03-30` 仓库门槛与护栏（`P0-P4`）

正式执行顺序文档：

- `docs/superpowers/plans/2026-03-30-main-brain-hardening-priority-sequence.md`

说明：

- `P0-P4` 在当前仓库应被视为仓库级 gate / regression guardrails，不应再被理解为开放式长期 backlog。
- 新任务如果触碰这些边界，必须通过相应护栏；未触碰则不应反向把它们重新解释成“系统仍未完成”。

当前护栏分层如下：

- `P0 truth-chain / write-boundary guardrails`
  - 先锁唯一写链、retired frontdoor、detail-only 读面与“读面无副作用”
- `P1 chat/orchestrate mode isolation`
  - 再锁纯聊天链和执行编排链的物理边界，避免默认聊天回潮成重执行 runtime
- `P2 canonical continuity contract`
  - 再统一 `work_context / environment / control_thread / recovery / host summary` 的连续性合同
- `P3 projection discipline`
  - 再清理 synthesis / cockpit / presenter 等派生层，确保 projection 不反向变成 truth
- `P4 long-run smoke maturity gate`
  - 最后把多周期、handoff、human-assist、resume、host switch 收成正式长跑验收门槛

当前已开始执行：

- `P0` 的第一刀优先落在 hard-cut regression 上：
  - assembled root app 的 `/goals` frontdoor 必须继续保持 `detail-only`
  - retired write frontdoors 必须继续 `404`
  - goal detail / runtime detail 这类读面不得重新承担隐式 reconcile 或 mutation
- `2026-03-30` 补充：已先补一条公开 `goals` frontdoor 的 root-router 回归。
  `tests/app/test_phase2_read_surface_unification.py`
  现已显式锁住：
  - `/goals/{goal_id}/detail` 在公开 frontdoor 上只允许 `GET`
  - `POST/PATCH/DELETE /goals/{goal_id}/detail` 必须保持 `405`
  - 现已执行 `python -m pytest tests/app/test_phase2_read_surface_unification.py -q` -> `5 passed`
- `2026-03-30` 补充：`P0` focused suite 已复跑通过。
  - `tests/app/test_goals_api.py` 已新增 leaf `goal detail` 读面只读回归：
    - `POST/PATCH/DELETE /goals/{goal_id}/detail` 在专用 `goals` router 上必须保持 `405`
  - 已执行
    `python -m pytest tests/app/test_goals_api.py -q -k "goal_detail"` -> `5 passed`
  - 已执行
    `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/test_goals_api.py -q` -> `24 passed`
- `2026-03-30` 补充：`P1` 的 mode-isolation 护栏已开始补回归。
  - `tests/kernel/test_main_brain_chat_service.py`
    已新增纯聊天 prompt 不得泄露
    `dispatch_query / delegate_task / dispatch_goal / dispatch_active_goals / memory_search`
    的回归
  - `tests/kernel/test_turn_executor.py`
    已新增“显式 `interaction_mode=chat` 必须压过 intake contract 的 orchestrate hint”
    的回归
  - 已执行
    `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
    -> `60 passed`
- `2026-03-30` 补充：`P1` 已补到显式 mode 覆盖旧缓存这层。
  - `tests/kernel/test_turn_executor.py`
    已新增：
    - 显式 `chat` 必须忽略旧 `_copaw_requested/_copaw_resolved_interaction_mode`
    - 显式 `orchestrate` 必须忽略旧 `_copaw_requested/_copaw_resolved_interaction_mode`
  - `src/copaw/kernel/turn_executor.py`
    已做最小修复：只有当当前请求的 requested mode 与缓存 requested mode 一致时，才允许复用 interaction-mode 缓存
  - 已执行
    `python -m pytest tests/kernel/test_turn_executor.py -q` -> `46 passed`
  - 已执行
    `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
    -> `61 passed`
- `2026-03-30` 补充：`P2` 已先补一条 continuity merge 护栏。
  - `tests/app/test_runtime_human_assist_tasks_api.py`
    已新增：
    - 当 `chat/run` 提交落到 `need_more_evidence` 时，
      已存在的隐藏 continuity 上下文
      `work_context_id / control_thread_id / environment_ref / recommended_scheduler_action`
      以及嵌套 `main_brain_runtime.*`
      不得被本轮半截 payload 覆盖或丢失
  - 已执行
    `python -m pytest tests/app/test_runtime_human_assist_tasks_api.py -q`
    -> `12 passed`
- `2026-03-30` 补充：`P3` 已先补一条 presenter 只读护栏。
  - `console/src/runtime/controlChainPresentation.test.ts`
    已新增：
    - `presentControlChain()` 不得就地改写输入 `main_chain.nodes`
  - 已执行
    `cmd /c npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts`
    -> `5 passed`

结论：

- `P0-P4` 保留为门槛，不再登记为开放任务。
- 后续只有在护栏失效、回归失守或新增功能跨越边界时，才重新立单。

### 4.2 已完成：主脑 cognitive closure

目标：

- 主脑不是只会派工，还要会收结果、看冲突、补缺口、决定是否 replan
- 子执行位必须输出主脑可消费的正式报告，不是只有 status/summary
- 综合状态必须进入正式读面与测试
当前状态：

- report schema 已增强
- synthesis 读面已出现
- UI 可见化已补出第一轮
- `2026-03-24` 补充：主脑监督链节点已进入正式 detail/UI 读面，writeback/backlog/cycle/assignment/report/replan 的可见链路与回归测试已补齐。
- `2026-03-26` 补充：`tests/kernel/test_main_brain_chat_service.py`、`tests/kernel/test_turn_executor.py`、`tests/kernel/test_query_execution_runtime.py`、`tests/app/test_runtime_center_api.py`、`tests/app/test_runtime_conversations_api.py`、`tests/app/test_agent_runtime_ingress.py`、`tests/app/runtime_center_api_parts/overview_governance.py`、`tests/app/test_system_api.py` 与 `console/src/runtime/controlChainPresentation.test.ts` 已通过更大回归，`report_synthesis`、`main_brain_intake`、control-chain presenter 与 runtime/system 读面当前已形成可验证基线。
- `2026-03-31` 补充：主脑作为唯一认知中心的当前定义范围已收口，不再把这项写成开放式尾巴。`Runtime Center / Industry cockpit / control-chain presenter` 与 `main_brain_chat_service / turn_executor / runtime center overview` 当前已共享同一条主脑认知链，并通过 `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_api.py tests/app/test_runtime_conversations_api.py tests/app/test_agent_runtime_ingress.py tests/app/test_system_api.py -q` -> `176 passed`，以及 `npm --prefix console test -- MainBrainCockpitPanel.test.tsx index.test.tsx runtimePresentation.test.tsx text.test.ts controlChainPresentation.test.ts` -> `23 passed` 验证。后续不再把这项单独登记为未闭环任务。

结论：

- 本项已完成，不再作为开放任务继续挂起。

### 4.3 已完成：主脑聊天链瘦身与性能硬化

目标：

- 纯聊天态保持轻量、低负载、少工具
- 需要执行时再进入编排态
- 聊天前台仍保持思考流 / 工具流可见，但不把执行噪声长期混进控制线程
- 首字延迟、一次性整段返回、过重 prompt/持久化负担要持续收敛

当前状态：

- `MainBrainChatService` 已存在
- `/chat` 默认已收口为主脑 auto 裁决
- prompt 已做过一轮瘦身
- `2026-03-26` 补充：runtime surface decomposition 已完成一轮正式收口：
  `state_query.py` 的 task-review / route contract 已切到
  `task_review_projection.py` 与 `utils/runtime_routes.py`；
  `query_execution_shared.py` 的 chat-writeback / confirmation seam
  已切到 `query_execution_writeback.py` / `query_execution_confirmation.py`；
  `AgentWorkbench/pageSections.tsx` 已稳定消费
  `sections/taskPanels.tsx` / `sections/detailPanels.tsx`；
  `Chat` 已补 `useRuntimeBinding.ts` 统一 runtime binding 入口。
  已通过
  `tests/app/test_runtime_projection_contracts.py`、
  `tests/kernel/test_query_execution_shared_split.py`、
  `tests/app/test_runtime_center_api.py`、
  `tests/kernel/test_main_brain_chat_service.py`、
  `tests/kernel/test_turn_executor.py`、
  `console/src/pages/AgentWorkbench/pageSections.test.ts`、
  `console/src/pages/Chat/useRuntimeBinding.test.ts`、
  `console/src/runtime/controlChainPresentation.test.ts`、
  `console/src/runtime/staffingGapPresentation.test.ts`
  与 `console tsc --noEmit` 验证。
- 高阶遗留已明显下降；`Chat/index.tsx` 的 runtime derivation、human-assist presentation 与 transport request 组装已继续下沉。当前若再压缩，优先应继续拆 sidebar / media shell，而不是回头堆平行 surface。
- `2026-03-31` 补充：轻量聊天链回归护栏已锁定（runtime conversations / bootstrap wiring），会持续阻断 runtime conversations 回流超重/重复 chat state，并要求 bootstrap wiring 保持 chat/orchestrate 轻量分链。
- `2026-03-31` 补充：主脑聊天性能/交互这项在当前仓库定义范围内已收口，不再保留开放式尾巴。`turn_executor` 现在对短 inspection 聊天请求也会直接走 chat fast-path，不再无脑触发 main-brain intake classifier；同时 `main_brain_chat_service / turn_executor / runtime conversations / runtime bootstrap split` 与 chat 前台 `runtimeTransport / useRuntimeBinding / ChatRuntimeSidebar / ChatComposerAdapter` 已通过 `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_split.py -q` -> `95 passed`、`npm --prefix console test -- runtimeTransport.test.ts useRuntimeBinding.test.ts ChatRuntimeSidebar.test.tsx ChatComposerAdapter.test.tsx` -> `14 passed` 与 `npm --prefix console run build` 验证。后续如再做聊天层变更，视为新一轮增强，而不是本项未闭环。

结论：

- 本项已完成，不再作为开放任务继续挂起。
- 后续如再做聊天层变更，视为新增增强，不回写成本项未闭环。

### 4.4 已完成：媒体与记忆闭环首轮收口

目标：

- `Memory VNext`
- `MediaAnalysisRecord`
- `chat media -> analysis -> answer/writeback/strategy`

当前状态：

- 聊天前门、media analyze、industry writeback、truth-first memory retain/recall 已全部接到同一正式链
- `/media/analyses`、console chat、主脑 recall 与 Runtime Center detail 现已共享 `work_context` continuity contract
- media-backed memory hit 现已可直接追回原始 `MediaAnalysisRecord`
- `Runtime Center` 已有正式 `Media Analyses` operator section
- `2026-04-01` 补充：`/runtime-center/main-brain` 正式 payload 已补上顶层 `cycles` 与顶层 `report_cognition`；前台驾驶舱也已把 `周期序列` 收进正式规划面，不再只靠 `meta.report_cognition` 和单个 `current_cycle` 临时拼装。
- `2026-04-01` 补充：`researcher` 的 schedule-originated continuity 已继续补厚到“follow-up backlog 物化 assignment 后仍保住 execution-core continuity 合同”。`service_lifecycle` 现会把 `control_thread_id / session_id / environment_ref / work_context_id / supervisor_* / requested_surfaces / recommended_scheduler_action` 从 follow-up backlog 正式持久化进 assignment metadata；`service_report_closure` 也会优先使用最新 report 的 `work_context_id`，不再让旧 assignment metadata 把新工作上下文盖掉。
- `2026-04-01` 补充：`AgentWorkbench` 前台已停止展示 `GoalSelector / GoalDetailPanel`，也不再主动请求 `/goals/{goal_id}/detail`；执行条文案已把 `目标` 收成 `焦点`，`Predictions` 里的 `目标状态面 / 目标 delta` 也已改成 `焦点` 口径，避免继续把 operator 拉回旧 `goal-era` 心智。
- `2026-04-01` 补充：`P0-4` 已新增正式 gate 入口 `scripts/run_p0_runtime_terminal_gate.py`，把后端主链回归、长跑与删旧回归、控制台定向回归和控制台构建收口成一个仓库级可执行门槛；`scripts/README.md` 已同步写明用法。
- `2026-04-01` 补充：`Knowledge Activation Layer Phase 4` 已补上最小 persisted relation-view 边界。`MemoryRelationViewRecord`、SQLite-backed `memory_relation_views`、`SqliteMemoryRelationViewRepository` 与 runtime bootstrap wiring 已落地；`DerivedMemoryIndexService` 已具备显式 `list_relation_views(...) / rebuild_relation_views(...)`；`Runtime Center` 也已新增 `GET /runtime-center/memory/relations` 读面，并支持按 `scope / relation_kind / source_node_id / target_node_id` 过滤。
- 硬边界：persisted relation view 仍然只是 derived-only read model，来源仍是 `MemoryFactIndexRecord + MemoryEntityViewRecord + MemoryOpinionViewRecord` 的派生组合，不是第二真相源，也不是 graph-native 写入主链。当前通用 `POST /runtime-center/memory/rebuild` 仍只负责 fact-index rebuild；relation rebuild 目前仍是显式 `DerivedMemoryIndexService.rebuild_relation_views(...)` 能力，而不是自动接入所有 memory rebuild 路径。

结论：

- 当前首轮闭环已成，不再用“继续接线”口径长期挂起。
- 只有在新增正式 `Memory VNext` 功能、知识激活层新对象或新的 operator 能力时，才单独立项。

### 4.5 `2026-04-01` `n8n / sop-adapters` 退役收口：`[已完成]`

本轮只做硬删除旧残留，不重做 fixed SOP 内核。当前收口结果：

- `tests/app/test_fixed_sop_kernel_api.py` 已删除 `/sop-adapters/templates` 与旧 router module removal 断言；fixed SOP API 回归现在只保留 native fixed SOP kernel 正式合同。
- `src/copaw/routines/service.py` 已删除 `RETIRED_SOP_ENGINE_KIND = "n8n-sop"`、对应 migration message 与专门 compatibility 分支；`n8n-sop` 现在只会被当成普通非法 `engine/environment kind` 输入，而不是 runtime 内建兼容语义。
- `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md` 继续保留为历史实施计划，但不再代表当前状态板上的活跃未完成项。

当前结论：

- 状态板不再保留“唯一未完成硬项”；
- 后续如再动 automation / fixed SOP，只按新增增强任务登记，不再以 `n8n / sop-adapters` 退役名义继续挂账。

---

## 5. 当前最重要的风险

1. 不要重新引入平行聊天前门、平行任务线程前台或旧 compat shell。
2. 不要为了“看起来更聪明”继续堆 role / capability / router，先补主脑闭环。
3. 不要让 `execution-core` 再次退化成默认叶子执行者。
4. 不要让 capability / MCP / install-template 的复杂度继续吞掉主脑清晰度。
5. 不要在中文 Markdown 上继续做补丁式乱码修复；如文件已坏，优先整份重写。

---

## 6. 当前闭环与终态标准

### 6.1 四项终态硬清单（`2026-03-30`）

1. `Full Host Digital Twin`
   - 当前已闭环：`Seat Runtime / Workspace Graph / Host Event Bus / host_twin` 已成为正式运行边界；`runtime query / workflow preview-run-resume / cron / fixed-SOP / Runtime Center` 已统一优先消费 canonical `host_twin_summary`；`host_twin` 也已正式派生 multi-seat `candidate_seats / selected_seat_ref / selected_session_mount_id`，并在同 scope alternate ready seat 可用时切换 canonical host truth。`browser / desktop / document` 三类执行位现都已进入同一条 host-aware 消费链，workflow run detail 与 fixed-SOP run detail 也会显式带出 `host_requirement`。
   - 终态标准：所有执行入口都只认一套 canonical `host_twin` 真相；`workflow / cron / fixed-SOP / Runtime Center / industry runtime` 对 `selected_seat_ref / selected_session_mount_id / host_requirement / legal_recovery` 使用同一宿主口径；多 seat / 多 agent 并发时系统能稳定判定 writer ownership、handoff、recovery、resume 与 host switch；browser / desktop / document / app-family twins 都纳入同一宿主真相；并有长时间 live smoke 证明切换、重入、回放和证据连续性不会断。
2. `single-industry` 真实世界覆盖
   - 当前已闭环：`strategy -> lane -> backlog -> cycle -> assignment -> report -> synthesis/replan` 已成正式主链；failed-report follow-up 已能继承 `source_report_ids / supervisor continuity / control_thread / session / environment / recommended_scheduler_action`，并在 focused runtime 中优先回到当前执行焦点，`replan` 也不会在 cycle rollover 后静默丢失。治理层创建的 host-handoff `HumanAssistTask` 现在也会继承同一条 `work_context / environment / recovery / requested_surfaces` continuity，上游宿主回执与下游 resume 会继续沿着同一控制线程和同一恢复上下文闭环，而不再掉出原行业主链。
   - 终态标准：单个行业实例能稳定连续跑多个周期；`staffing + handoff + human assist + report + synthesis + replan` 能形成长期闭环；supervisor / manager / researcher / operator 的职责切换和协作关系在长跑里不掉线；browser / desktop / document 执行位能接入同一行业闭环；报告、证据、决策和重规划都能回流到同一主链，并有真实世界长跑 smoke 证明其稳定性。
3. 主脑 cockpit / `Unified Runtime Chain`
   - 当前已闭环：`/runtime-center/main-brain` 已成为 dedicated main-brain cockpit contract，`Runtime Center` main-brain panel 现在会把 `carrier / strategy / lanes / backlog / cycle / assignment / report / environment / governance / recovery / automation / evidence / decision / patch` 放进同一驾驶舱，并形成 `Execution Envelope / Operator Closure / Trace Closure` 三段闭环；`/runtime-center/industry/{instance_id}` 已支持 `focus_kind + focus_id` drill-down，`/runtime-center/reports` 也已支持按 `industry / assignment / lane / cycle / needs_followup / processed` 过滤。
   - 终态标准：前台不是 detail 堆叠页，而是统一运行中心；上述核心对象都能在一个驾驶舱里被看见、被关联、被追踪；驾驶舱不只展示结果，还能承载治理、调度、恢复、证据追踪与 patch/decision 闭环；主脑对象、执行对象、证据对象之间的关系前台可直接看清；重要运行真相不再藏在日志、内部状态或零散 detail 里，也不再出现第二套平行执行器。
4. 宽回归与 `live smoke`
   - 当前已闭环：关键 `industry / runtime / workflow / fixed-SOP / host-aware` 主链已进入聚合回归；`tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_long_run_live_smoke_closes_unified_runtime_chain_and_multi_surface_continuity` 已把 `multi-cycle industry`、`handoff -> human-assist -> resume`、`schedule pause-resume`、`host switch + reentry + replay continuity`、以及 `browser / desktop / document + cockpit contract + evidence / decision / patch continuity` 锁进同一条长跑 smoke，`tests/app/test_runtime_human_assist_tasks_api.py`、`tests/app/runtime_center_api_parts/overview_governance.py` 与 `tests/app/runtime_center_api_parts/detail_environment.py` 也继续作为正式聚合回归护栏；同时仓库已新增单入口 gate `python scripts/run_p0_runtime_terminal_gate.py` 作为正式门槛入口。
   - 终态标准：关键主链都有稳定宽回归，而不是只靠局部单测；存在长时间连续 smoke，覆盖恢复点、重入、宿主切换、handoff、调度恢复、证据回放；多 agent / 多 cycle / 多 host / 多执行位组合场景能稳定通过；回归能锁住关键合同漂移；smoke 本身成为成熟度门槛，而不是开发时顺手跑一遍的附属检查。

### 6.2 其他已收口 / 持续工程项

1. Goal 叶子兼容边界：`[已清零到显式 leaf dispatch family]`
   - 当前已闭环：公开 `/goals` frontdoor、公开 `GET /goals/{goal_id}`、retired dispatch alias 与旧公共 `dispatch_goal(...)` 名称都已退役；当前只剩显式 `compile_goal_dispatch / dispatch_goal_execute_now / dispatch_goal_background / dispatch_goal_deferred_background` 这组 leaf dispatch family，prediction 侧只保留启动期 retired recommendation 清理，已不再构成运行期 compat 分支。
2. hard-cut 全量收口：`[合同硬切已锁住基线]`
   - 当前已闭环：retired frontdoor、legacy goal alias、runtime-center 写面与治理壳的关键合同已锁住，并已补到更宽的 `industry / runtime / workflow / fixed-SOP` 聚合回归。
3. Claude-derived runtime contract hardening `P0-P2`：`[当前已闭环，后续新增执行面再单独登记]`
   - 当前已闭环：`CapabilityExecutionContext` 已成为 `CapabilityExecutionFacade` 的内部标准执行上下文，`error_kind / action_mode / work_context_id / evidence_id` 已进入统一 capability result contract，早返回 / 异常 / tool-response 三类路径不再各自漂移；`runtime_outcome.py` 现统一 lower execution outcome taxonomy，并提供共享 `cleanup disposition`、`failure_source / blocked_next_step / remediation_summary` 给 `ActorWorker / TaskDelegationService / Runtime Center`；MCP runtime 已补成 typed runtime/rebuild contract，`MCPClientManager` 不再手拼多套 raw-dict 诊断；task interpretation 现在围绕统一 request family 收口，system dispatch 优先消费 `dispatch_request`，delegated child-run 统一为 `dispatch_request + request + request_context` 正式 envelope，`execute=True` 已交回 `ActorSupervisor -> ActorWorker` 统一 worker shell，不再保留 delegation-service 的旧 terminal cleanup 支路；worker interruption / supervisor stop / submit-time terminal closeout 也已统一到同一 terminal path；capability mount 已正式带 `package_ref / package_kind / package_version`，skill frontmatter 与 MCP registry provenance 现都绑定到同一 formal package contract；sidecar-memory 与 degraded-runtime 也已成为显式 degradation contract，并统一锚定到 `conversation_compaction_service` / runtime metadata / Runtime Center overview，而不是隐藏 fallback。
   - 删旧结论：`query_execution_runtime.py` 的 legacy `set_memory_manager(...)` alias 已删除；`turn_executor.py / runtime_host.py / runtime_service_graph.py / runtime_state_bindings.py` 的 runtime-side `memory_manager` 兼容入口也已删除，正式主链现统一只认 `conversation_compaction_service`；provider usage path 不再实例化隐式 `ProviderManager()` fallback；delegation-service 内联 child-run cleanup 已删除；`main_brain_intake.py` 中无调用的 runtime-context attached helper 已删除；本轮没有新增 `task_state_machine.py` 或 `turn_loop.py`，因为条件式 extraction audit 证明它们当前还不能实质删掉足够多的重复逻辑。
   - `2026-04-01` 补充：`tool:execute_shell_command` 已补上第一批 shell / PowerShell 安全硬化。当前会在启动子进程前先跑纯策略 validator，显式阻断 `git reset --hard / git checkout -- / git clean -fd`、`Remove-Item -Recurse`、`del /s`、`rmdir /s` 与直指 `.git/hooks/refs` 的破坏性命令；被策略拒绝的 shell 调用会沿现有 `CapabilityExecutionFacade -> execute_shell_command -> KernelToolBridge -> EvidenceLedger` 主链以正式 `blocked` 结果写回，不再伪装成 generic shell failure。
   - `2026-04-01` 补充：`docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md` 现已把 Claude-derived borrowing 收口成统一的 `10` 项优先级，并补齐与 `P0 / P1 / P2` 的正式对照口径：`P0` 读作统一 execution/tool front-door 基座，`P1` 读作 MCP / concurrency / planning-shell / Runtime Center projection 壳硬化，`P2` 读作 context entropy / skill metadata / additive child-run shell 的长任务纪律；该口径只用于后续新增执行面归类，不表示重开当前已闭环的 `P0-P2` 任务，也不表示 `planning-shell / Runtime Center projection / long-turn entropy` 这些 forward borrowing item 已被历史 `2026-04-01` landed wave 一次性全部做完。
   - `2026-04-02` 补充：同一 hardening 设计文档已新增 `Current Repo Construction Matrix`，把当前仓库的 `execution / entropy / concurrency / MCP / planning shell / Runtime Center / skill metadata / additive child-run shell / hotspot cooling` 逐项映射到具体模块与 `present / partial / follow-up` 状态；这张矩阵用于后续施工分类、补洞和借鉴对照，不表示重开历史 `P0-P2`，也不表示把 planning-program follow-up 静默并入已闭环波次。
   - `2026-04-02` 施工补充：`RuntimeCenterStateQueryService` 已继续按 projection-only 边界收口。decision 列表/详情读取不再在 query 面偷偷执行 `reviewing / expired / runtime event publish` 这类写操作；旧 `/runtime-center/decisions/{decision_id}/review` compatibility shim 已物理删除，正式 review 写入口现只剩 `/runtime-center/governed/decisions/{decision_id}/review`；`/runtime-center/kernel/tasks` 现也改走 `state_query.list_kernel_tasks()` 读取 persisted `KernelTaskStore` 视图，不再依赖 live `dispatcher.lifecycle.list_tasks()`；同时 task list / kernel task read projection 已下沉到 `app/runtime_center/task_list_projection.py`，从 `state_query.py` 拆出第一块稳定 projector。该变化用于把 Runtime Center query surface 从“半读半写”继续拉回正式只读投影视图，并锁住 `waiting-confirm` 等 kernel phase 的原样返回语义。
   - `2026-04-02` 施工补充：四阶段 `runtime complete tail closure` 程序的 `Stage 1` 已达 exit criteria。`app/runtime_center/work_context_projection.py` 现已承接 `list/count/detail work_context*` 与共享 `serialize_work_context(...)` 读投影，`state_query.py` 对这块只保留 delegate；同时已补齐真实 state-backed 回归，直接锁住 `count_work_contexts()`、runtime-owner detail rollup，以及 `GET /runtime-center/work-contexts` / `GET /runtime-center/work-contexts/{context_id}` 的正式 API 契约。该记录只表示 Stage 1 收口，不表示整个四阶段程序完成；后续 `Stage 2 / Stage 3` 与 formal planning 的收口见下方同日记录。
   - `2026-04-02` 施工补充：同一四阶段程序的 `Stage 2: MCP Lifecycle Hardening` 现已完成本阶段代码与测试收口。`app/mcp/runtime_contract.py` 已继续承接唯一正式 lifecycle contract，并新增 typed `reload_state`，显式覆盖 `dirty / pending_reload / pending_spec / overlay_scope / overlay_mode / last_outcome`；`MCPClientManager` 现会把 `replace` 的 connect failure 收口成“保留 steady client + 标记 dirty/pending”的正式状态，而不是把 steady snapshot 直接毒化成含混失败态；old-client close failure 也会回写到同一 runtime record，不再只打日志；`MCPConfigWatcher` 在 reload task 忙碌时会显式调用 pending 标记而不是静默跳过；同时 manager 已具备 scope-local `additive / replace` overlay、overlay clear，以及 failed overlay mount 保留旧 scope clients 的边界，base registry 与 scoped overlay 不再混成单一进程级壳。该记录只表示 Stage 2 收口，不表示整个四阶段程序完成；`Stage 3 / Stage 4` 仍保持 open。
   - `2026-04-02` 施工补充：同一四阶段程序的 `Stage 3: Concurrency Discipline + Child-Run Shell` 现已完成本阶段代码与测试收口。`EnvironmentService / EnvironmentLeaseService` 现已正式暴露 `shared-writer` lease front-door，writer serialization 不再只靠任务表扫冲突；`kernel/child_run_shell.py` 已作为共享 writer cleanup shell 落地，`ActorWorker` 与 direct delegation execute path 会通过同一 lease acquire / heartbeat / release 壳执行 writer child-run，不再各自维护一条隐藏 cleanup 分支；`TaskDelegationService.preview_delegation(...)` 也会在 writer task 上显式检查 `writer_lock_scope` 是否已被其他 owner 持有，而不是只看 `environment_ref`。该记录只表示 Stage 3 收口，不表示整个四阶段程序完成；`Stage 4` 仍保持 open。
   - `2026-04-02` Stage 3 定向验证：`$env:PYTHONPATH='src'; python -m pytest tests/environments/test_environment_registry.py tests/environments/test_host_event_recovery_service.py tests/kernel/test_actor_worker.py tests/kernel/test_actor_supervisor.py tests/app/test_runtime_center_task_delegation_api.py -q` -> `64 passed`
   - `2026-04-02` Stage 3 长跑验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_phase_next_autonomy_smoke.py -k "long_run_live_smoke" -q` -> `1 passed`
   - `2026-04-02` Stage 3 关联验证：`$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_assignment_envelope.py tests/kernel/test_query_execution_shared_split.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_capabilities_execution.py -q` -> `66 passed`
   - `2026-04-02` 施工补充：同一四阶段程序的 `Stage 4: Planning Shell Plus Formal Planning Gap` 现已完成本阶段代码与测试收口。`src/copaw/compiler/planning/` 现已成为正式 typed planning slice，`StrategyPlanningCompiler / CyclePlanningCompiler / AssignmentPlanningCompiler / ReportReplanEngine` 已接入 `runtime_bootstrap_domains / GoalService / IndustryService / PredictionService / Runtime detail`；assignment plan envelope、cycle `formal_planning` sidecar、prediction planning overlap 与 `main_brain_planning` surface 已落到同一 truth-preserving sidecar 链，不再由 lifecycle/prediction 各自维护 shallow local planning 壳。与此同时，`CapabilityService` 现支持显式注入 config I/O front-door，同时保留默认 `load_config/save_config` patchable contract，prediction/install-plan 测试与隔离 runtime shell 都可在独立 config 下运行；`run_operating_cycle(force=True, backlog_item_ids=...)` 也已改为绕过 active-cycle gate 并开启 dedicated formal-planned cycle，而不是把 scoped backlog 偷塞回当前 cycle，report / cognitive continuity 因而保持干净。至此四阶段 `runtime complete tail closure` 程序已整体闭环，不再保留 Stage 4 open 尾巴。
   - `2026-04-02` Stage 4 compiler/runtime 验证：`$env:PYTHONPATH='src'; python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_runtime_bootstrap_split.py tests/app/test_goals_api.py tests/app/test_predictions_api.py -q` -> `54 passed`
   - `2026-04-02` Stage 4 lifecycle/smoke 验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -q` -> `27 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/industry_api_parts/runtime_updates.py -q` -> `37 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py -q` -> `12 passed`
   - `2026-04-02` Stage 4 front-door 回归：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capabilities_execution.py tests/app/test_capability_skill_service.py tests/app/test_runtime_center_actor_api.py -q` -> `42 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capabilities_write_api.py -q` -> `16 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capability_market_api.py -q` -> `22 passed`
   - 当前验证：`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_execution_context.py tests/app/test_capabilities_execution.py tests/agents/test_file_tool_evidence.py tests/agents/test_shell_tool_evidence.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_query_usage_accounting.py tests/kernel/test_actor_worker.py tests/kernel/test_actor_supervisor.py tests/kernel/test_turn_executor.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_operator_runtime_e2e.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_phase_next_autonomy_smoke.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_capability_catalog.py tests/app/test_capability_skill_service.py tests/app/test_capability_market_api.py -q` -> `231 passed`
   - `2026-04-03` donor gap 收口补充：`cc` 审计后的第一批真实 execution/runtime 缺口已继续落地到主线。`CapabilityExecutionFacade` 现已具备最小可用的 `parallel-read -> serial-write` batch orchestration；`tool:execute_shell_command` 不再被内置 mount 永久硬编码成 `write`，而是改由 typed tool contract 根据实际命令解析 `action_mode / concurrency_class`；tool-bridge shell evidence 也已保留正式 `blocked` 状态，并把 `action_mode / read_only / concurrency_class / preflight_policy / tool_contract` 一起写进 evidence metadata。与此同时，dispatcher/lifecycle 的 terminal closeout 已对重复 `fail_task(...) / cancel_task(...)` 变成 idempotent，不再重复追加 evidence 或重复触发 terminal side effect；`/runtime-center/recovery/latest` 与 main-brain recovery card 也已切到 canonical `latest_recovery_report` first、`startup_recovery_summary` fallback 的读取口径，并继续暴露统一 `source + detail(leases/mailbox/decisions/automation)` recovery drilldown，不再把“最近恢复报告”错误等同于“启动恢复快照”。
   - `2026-04-03` donor gap 定向验证：`python -m pytest tests/capabilities/test_execution_context.py::test_execution_context_carries_contract_fields tests/app/test_capabilities_execution.py::test_execute_task_batch_runs_parallel_reads_before_serial_write tests/app/test_capabilities_execution.py::test_shell_execution_writes_evidence_via_unified_contract tests/app/test_capabilities_execution.py::test_shell_execution_blocked_status_propagates_to_tool_bridge_evidence tests/app/test_capabilities_execution.py::test_shell_execution_tool_bridge_evidence_carries_execution_contract_metadata tests/kernel/test_kernel.py::TestKernelDispatcher::test_fail_task_is_idempotent_for_terminal_task tests/kernel/test_kernel.py::TestKernelDispatcher::test_cancel_task_is_idempotent_for_terminal_task tests/app/test_runtime_center_events_api.py::test_runtime_center_recovery_latest_endpoint_returns_summary tests/app/test_runtime_center_events_api.py::test_runtime_center_recovery_latest_endpoint_prefers_canonical_latest_report tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_main_brain_route_exposes_unified_operator_sections tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_main_brain_route_prefers_canonical_latest_recovery_report -q` -> `11 passed`
   - `2026-04-03` donor gap 审计细化：此前收敛出的 3 条真实残项已在本轮继续收口到当前主线，不再作为 blocker 保留：1) `query/chat` capability front-door 现在除了统一 delegate + `ToolExecutionContract` 外，也已补上 delegate-builder -> wrapped builtin tool -> capability execution 的 boundary coverage，并明确验证 preflight 优先级与 delegate failure fallback；2) `skill metadata / package discipline` 除了 filesystem `package_ref` re-anchor 回真实 skill root 外，`skill / MCP / package-bound / delta` 也已正式投进 Runtime Center 主读面；3) Runtime Center 现在除了 `governance explain` 与 recovery `source + detail` 外，也已补上 capability-gap 级别的 `degraded_components` drilldown。若后续还要继续加 full query-stream smoke、seat/session typed capability overlays 或更广义 runtime diagnostics，应视为下一轮增强，而不是本轮 donor-gap 仍未闭环。
   - `2026-04-03` donor gap 修复补充：blocked shell 现在不会再为策略拒绝命令写 replay pointer；当 tool-bridge 已经写入 canonical blocked/failure evidence 时，dispatcher 也不会再重复追加一条 `kernel.failed` evidence。与此同时，relation-aware planning 已继续进入正式 cycle planner 排序：`graph_focus_relations + graph_relation_evidence` 现在会参与 near-tie backlog 选择，并把 `affected_relation_ids / affected_relation_kinds` 写回 typed `CyclePlanningDecision`。`MemoryActivationService` 的共享战略 resolver 也已对齐当前 `resolve_strategy_payload(...)` 合同，不再走过期的 `fallback_payload` 调用口径。
   - `2026-04-03` donor gap 收口续补：`query/chat` 的 built-in `tool:*` 前门现已继续向统一 capability front-door 靠拢。`react_agent.py` 现在除了共享 typed `ToolExecutionContract` 校验外，还支持在 query runtime 里绑定 capability delegate；`KernelQueryExecutionService` 会为当前 query turn 构建同源 `tool:* -> CapabilityService.execute_task(...)` delegate，因此 query/chat 本地工具不再只能直接命中 raw local tool 函数。与此同时，`IndustryService._apply_activation_to_strategy_constraints(...)` 已正式把 `top_relations / top_relation_evidence` 写进 `PlanningStrategyConstraints.graph_focus_relations / graph_relation_evidence`，`report_synthesis` 也会把 relation activation 带进 synthesis payload，follow-up backlog / materialized assignment 现已保留 `activation_top_relations / activation_top_relation_kinds / activation_top_relation_ids / activation_relation_source_refs`；Runtime Center `main-brain governance` surface 已新增 `explain` 对象，task list projector 也已改用共享 `resolve_visible_execution_phase(...)`，不再把 raw runtime-only `active` 暴露给 operator。
   - `2026-04-03` donor gap package/recovery 补充：`CapabilitySkillService` 现已在 read/bind skill package metadata 时把 filesystem-backed `package_ref` 重新锚定到真实 skill root，避免 frontmatter 里逃逸路径继续充当 package identity；`/runtime-center/recovery/latest` 与 main-brain recovery payload 现在也都会返回统一 `source` 与 `detail.leases / detail.mailbox / detail.decisions / detail.automation`，让 startup/latest recovery summary 进入同一条 operator drilldown 口径。
   - `2026-04-03` donor gap 最后一轮收口：`react_agent.py` 里的 wrapped builtin tool 现在在 delegate 失败时会回退到 builtin tool 路径，不再因为 capability delegate 短时异常直接撕裂 query turn；query runtime boundary tests 也已把 delegate-builder -> wrapper -> `CapabilityService.execute_task(...)` 的整条链锁住。与此同时，Runtime Center `capabilities` card 与 `main-brain governance` 现已补上 capability governance projection：`skill_count / mcp_count / package_bound_* / delta / degraded_components` 会基于既有 capability/prediction 真相源进入 operator 主读面，不再只停在独立 capability 卡或 recommendation 端点。
   - `2026-04-03` donor gap HTTP/governance 续补：`/runtime-center/chat/run` 现已补上 app-level e2e boundary coverage，真实 `KernelTurnExecutor` admission 后会把 wrapped builtin `tool:get_current_time` 送进统一 capability front-door，不再只有 runtime-internal seam 测试；与此同时，`/runtime-center/governance/status` 也已开始直接返回 canonical `capability_governance` 投影，把原先只存在于 `overview/main-brain` projection 的 `skill_count / mcp_count / package_bound_* / delta / degraded_components` 提升成 Runtime Center 正式治理读面 contract。
   - `2026-04-03` donor gap HTTP/governance 定向验证：`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/query_execution_environment_parts/dispatch.py tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -k "governance or frontdoor or preflight or fallback or query_turn or runtime_center_chat_run" -q` -> `73 passed`
   - `2026-04-03` diagnostics 续补：`capability_governance` 的 delta diagnostics 现已从“半套 summary”收紧到同一共享投影里。`overview/main-brain/governance/status` 现在都会共用同一条 capability diagnostics producer，正式返回 `total_items / history_count / case_count / waiting_confirm_count / manual_only_count / executed_count`，并把 `underperforming / waiting_confirm / manual_only` 提升成 canonical `degraded_components`，不再只有 `capability-coverage` 一种简化降级解释。
   - `2026-04-03` diagnostics 定向验证：`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_events_api.py -k "governance or main_brain or overview or capability_optimizations" -q` -> `66 passed`
   - `2026-04-03` donor gap 聚合验证：`python -m pytest tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_mcp_runtime_contract.py tests/app/test_capability_catalog.py tests/app/test_capability_skill_service.py tests/memory/test_activation_service.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_capabilities_execution.py tests/kernel/test_tool_bridge.py tests/capabilities/test_execution_context.py -q` -> `166 passed`
   - `2026-04-03` 状态映射补充验证：`python -m pytest tests/kernel/test_task_execution_projection.py tests/kernel/test_actor_mailbox.py -q` -> `5 passed`
   - `2026-04-03` donor gap 续补验证：`python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -k "frontdoor or unified_tool_contract_validation or evidence_sinks_attach_tool_contract_metadata" -q` -> `4 passed`；`python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "graph_focus_into_formal_planning_sidecar or activation_followup" -q` -> `3 passed`；`python -m pytest tests/industry/test_report_synthesis.py tests/compiler/test_report_replan_engine.py -k "relation" -q` -> `2 passed`；`python -m pytest tests/kernel/test_task_execution_projection.py tests/app/test_runtime_query_services.py -k "projector or visible_execution_phase" -q` -> `6 passed`
   - `2026-04-03` donor gap 收口复验：`python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -k "frontdoor or preflight or fallback or end_to_end or entropy_budget" -q` -> `6 passed`；`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_query_services.py -q` -> `75 passed`；`python -m pytest tests/app/test_capability_skill_service.py tests/app/test_capabilities_execution.py tests/kernel/test_tool_bridge.py tests/capabilities/test_execution_context.py tests/industry/test_report_synthesis.py -k "relation_activation or relation or tool_bridge or execution_context or capability_skill_service or capabilities_execution" -q` -> `54 passed`
   - `2026-04-02` Stage 2 定向验证：`$env:PYTHONPATH='src'; python -m pytest tests/test_mcp_resilience.py tests/app/test_mcp_runtime_contract.py tests/app/test_runtime_bootstrap_helpers.py -q` -> `41 passed`
   - `2026-04-01` 定向验证：`$env:PYTHONPATH='src'; python -m pytest tests/agents/test_shell_tool_safety.py tests/agents/test_shell_tool_evidence.py tests/app/test_capabilities_execution.py tests/test_truncate.py -q` -> `61 passed`
   - `2026-04-03` 施工补充：实现层收口波次已在隔离 worktree 内完成本轮代码与删除收口。`runtime_center_shared.py` 现只保留极薄聚合入口，请求模型/SSE/dependencies/mutation helpers/actor focus/schedule surface 已拆到独立模块；`RuntimeCenterStateQueryService` 已继续 delegate 到 `task_detail_projection / environment_feedback_projection / goal_decision_projection`，`overview_cards.py` 也已再拆出 `overview_entry_builders.py`，不再继续承载 entry builder 与底层取值工具；`query_execution_runtime.py` 已把 execution-context seam 抽到 `query_execution_context_runtime.py`，`main_brain_chat_service.py` 已把 turn session state / inbound persistence / assistant snapshot / commit cache 落成局部 helper；`Industry runtime views` 已去掉 idle 场景对 legacy goal 的假回退；`workflow-templates/workflow-runs` 旧 HTTP root front-door 不再挂入 assembled root router，只保留 workflow service 内部读面与专项测试入口。该波次同时清掉了正式主链上的 `current_goal / current_goal_id` 历史残留，focus 口径现已统一到 `current_focus_*`。
   - `2026-04-03` execution-discipline 收口补充：`industry/service_team_runtime.py` 已切掉 runtime metadata 对 `goal_id / goal_title` 的最后双写点；bootstrap、lifecycle refresh 与 cleanup backfill 虽仍沿用 legacy 参数名进入 shared runtime sync，但最终持久化到 `AgentRuntimeRecord.metadata` 的焦点 contract 现只剩 `current_focus_kind / current_focus_id / current_focus`。`tests/app/industry_api_parts/runtime_updates.py` 与 `tests/kernel/test_agent_profile_service.py` 已补齐对应回归，锁住“live runtime metadata 不再回灌 legacy goal 字段、兼容读只停在历史 mailbox/checkpoint”的边界。
   - `2026-04-03` execution-discipline 收口补充：`/runtime-center/main-brain` 现已把 `main_brain_planning` 提升为 dedicated read contract；`Runtime Center` 主脑 cockpit 也已新增结构化 `正式规划壳` 读面，直接显示 `strategy_constraints / latest_cycle_decision / focused_assignment_plan / replan` 以及各自的 `resume_key / fork_key / verify_reminder`，不再只通过 `report_cognition.replan` 或 `current_cycle.main_brain_planning` 的隐含字段间接暴露 planning shell。
   - `2026-04-03` 六缺口收口补充：你点名的 6 条实现层残项已在隔离 worktree 收口完成。provider 的正式写前门现在统一是 `/providers/admin/*`，`/models` 只保留读接口，`local_models` 的 catalog 刷新也已改走 `ProviderAdminService`；runtime/bootstrap 正式 contract 只保留 `runtime_provider`，`provider_manager` 只在 `runtime_state_bindings.py` 留 compatibility mirror，不再作为主链字段。`industry/service_runtime_views.py` 的 live focus 读面已停止从 assignment/backlog/task 读时发明 `current_focus_*`；`Runtime Center` 页面正式改走 canonical `/runtime-center/surface` 单一 fetch，main-brain dedicated payload 不再用 overview entry 伪造 `strategy/carrier` truth，cockpit 也不再回退读取 overview 的 `surface/generated_at/error`。`System` 页进一步退回“系统维护”定位，不再承载 runtime factual summary。聚合验证见本轮 fresh 结果：`python -m pytest tests/app/test_models_api.py tests/app/test_local_models_api.py tests/app/test_phase2_read_surface_unification.py tests/providers/test_provider_manager_facade.py tests/providers/test_llm_routing_provider_manager.py tests/providers/test_runtime_provider_facade.py tests/agents/test_model_factory.py tests/app/test_industry_draft_generator.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_system_api.py tests/app/test_industry_service_wiring.py -q` -> `80 passed`；`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_center_api.py -q` -> `206 passed`；`python -m pytest tests/industry/test_runtime_views_split.py tests/kernel/test_agent_profile_service.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_query_execution_shared_split.py tests/kernel/test_query_execution_intent_policy.py -q` -> `82 passed`；`npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx src/layouts/Sidebar.test.tsx src/pages/Settings/System/index.test.tsx` -> `23 passed`；`npm --prefix console run build` -> 通过。
   - `2026-04-03` 分块验证：`$env:PYTHONPATH='D:/word/copaw/.worktrees/implementation-layer-closure/src'; python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_query_services.py tests/app/test_phase2_read_surface_unification.py -q -p no:cacheprovider` -> `86 passed`；`python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_assignment_planner.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_predictions_api.py -q -p no:cacheprovider` -> `45 passed`；`python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_bootstrap_split.py tests/kernel/test_main_brain_chat_service.py -q -p no:cacheprovider` -> `54 passed`；`python -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_service_wiring.py tests/app/test_workflow_templates_api.py tests/app/test_phase_next_autonomy_smoke.py -q -p no:cacheprovider` -> `52 passed`；`python -m pytest tests/app/industry_api_parts/runtime_updates.py -q -p no:cacheprovider` -> `37 passed`；`python -m pytest tests/kernel/test_agent_profile_service.py tests/state/test_sqlite_repositories.py tests/kernel/test_compiler_learning.py tests/app/test_runtime_conversations_api.py tests/app/runtime_center_api_parts/shared.py tests/kernel/query_execution_environment_parts/confirmations.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/query_execution_environment_parts/shared.py -q -p no:cacheprovider` -> `98 passed`。前端定向 Vitest 在当前环境缺少本地 `vitest` 可执行文件且网络受限，未能在本轮命令行内重跑；后端分块矩阵与 `git diff --check` 已通过。
4. 重模块继续拆分：`[当前已闭环，后续如再拆视为新一轮增强]`
   - 当前已闭环：本轮超重前台模块已完成正式 split wave。`IndustryRuntimeCockpitPanel.tsx` 已继续把环境可见化、focus/work-context 与媒体/推荐展示收回共享 `industryPagePresentation / runtimePresentation`；`MainBrainCockpitPanel.tsx` 已把 compact-record / operator / trace / cognition 渲染块抽到 `mainBrainCockpitSections.tsx`；`runtimeIndustrySections.tsx` 已把 operator/media sections 抽到 `runtimeIndustryOperatorSections.tsx`；`controlChainPresentation.ts` 已把 graph/synthesis/metrics 归一化 helper 下沉到 `controlChainPresentationHelpers.ts`。本轮已执行 `npm --prefix console run build` -> 通过，`npm --prefix console test -- runtimePresentation.test.tsx MainBrainCockpitPanel.test.tsx runtimeDetailDrawer.test.tsx controlChainPresentation.test.ts index.test.tsx` -> `18 passed`。后续若继续拆 `FixedSopPanel`、Automation surface 或更深 backend 模块，按新增增强任务单独登记，不再把当前项保留为未闭环。

---

- `2026-03-24`
  - `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/test_agent_runtime_ingress.py tests/app/runtime_center_api_parts/overview_governance.py -q`
  - 结果：`66 passed`
- `2026-03-24`
  - `python -m pytest tests/industry/test_seat_gap_policy.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_conversations_api.py -q`
  - 结果：`42 passed`
- `2026-03-24`
  - `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
  - 结果：`2 passed`
- `2026-03-24`
  - `npm --prefix console run build`
  - 结果：通过
- `2026-03-24`
  - `python -m pytest tests/app/industry_api_parts/runtime_updates.py tests/industry/test_seat_gap_policy.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`
  - 结果：`67 passed`
- `2026-03-25`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py -q`
  - 结果：`12 passed`
- `2026-03-25`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
  - 结果：`20 passed`
- `2026-03-25`
  - `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
  - 结果：`23 passed`
- `2026-03-26`
  - `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
  - 结果：`23 passed`
- `2026-03-26`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
  - 结果：`20 passed`
- `2026-03-26`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py tests/state/test_main_brain_hard_cut.py -q`
  - 结果：`14 passed`
- `2026-03-26`
  - `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/kernel/test_query_execution_runtime.py -q`
  - 结果：`44 passed`
- `2026-03-26`
  - `python -m pytest tests/app/test_runtime_center_api.py tests/app/test_runtime_conversations_api.py tests/app/test_agent_runtime_ingress.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_system_api.py -q`
  - 结果：`75 passed`
- `2026-03-26`
  - `npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts src/runtime/staffingGapPresentation.test.ts`
  - 结果：`4 passed`
- `2026-03-25`
  - `python -m pytest tests/state/test_main_brain_hard_cut.py -q`
  - 结果：`2 passed`
- `2026-03-27`
  - `python -m pytest tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_capability_market_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q`
  - 结果：`79 passed`
- `2026-03-27`
  - `python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py -q`
  - 结果：`106 passed`
- `2026-03-27`
  - `$env:PYTHONPATH='D:\\word\\copaw\\.worktrees\\codex-phase6-host-twin\\src'; @' import copaw; from copaw.sop_kernel.models import FixedSopRunRequest; print(copaw.__file__); print(sorted(FixedSopRunRequest.model_fields.keys())) '@ | python -`
  - 结果：`copaw` 已确认从 `D:\word\copaw\.worktrees\codex-phase6-host-twin\src\copaw\__init__.py` 导入；`FixedSopRunRequest` 已包含 `environment_id / session_mount_id`
- `2026-03-27`
  - `$env:PYTHONPATH='D:\\word\\copaw\\.worktrees\\codex-phase6-host-twin\\src'; python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`
  - 结果：`135 passed`
- `2026-03-27`
  - `$env:PYTHONPATH='D:\\word\\copaw\\.worktrees\\codex-phase6-host-twin\\src'; python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`
  - 结果：`166 passed`
- `2026-03-27`
  - `python -m pytest tests/routines/test_routine_service.py tests/agents/test_browser_tool_evidence.py -q`
  - 结果：`25 passed`
- `2026-03-25`
  - `npx vitest run src/runtime/controlChainPresentation.test.ts`
  - 结果：`2 passed`
- `2026-03-24`
  - `python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_console_channel.py tests/app/test_goals_api.py -q`
  - 结果：`23 passed`

历史验收请直接看：
- `2026-03-24`
  - `npm --prefix console run build`
  - 结果：通过

历史验收请直接看：

- `V1_RELEASE_ACCEPTANCE.md`
- `V2_RELEASE_ACCEPTANCE.md`
- `V3_RELEASE_ACCEPTANCE.md`
- `V6_RELEASE_ACCEPTANCE.md`

---

## 8. 当前推荐关注源码

如果任务涉及主脑 / 聊天 / 编排 / 闭环，优先看：

- `src/copaw/kernel/turn_executor.py`
- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/query_execution_prompt.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/kernel/query_execution_tools.py`

如果任务涉及行业自治 / staffing / report / synthesis，优先看：

- `src/copaw/industry/service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/industry/service_strategy.py`
- `src/copaw/industry/service_runtime_views.py`
- `src/copaw/industry/seat_gap_policy.py`
- `src/copaw/industry/report_synthesis.py`

如果任务涉及聊天页与前端结果面，优先看：

- `console/src/pages/Chat/*`
- `console/src/pages/Industry/*`
- `console/src/pages/RuntimeCenter/*`
- `console/src/pages/AgentWorkbench/*`
- `console/src/runtime/staffingGapPresentation.ts`

---

## 9. 给下一位 agent 的一句话提醒

先确认你现在做的是哪条收口线：

- single-industry autonomy
- main-brain cognitive closure
- main-brain chat performance / split-chain hardening
- media / memory 闭环

如果答不出来，就不要下手改代码。
