# TASK_STATUS.md

本文件是 `CoPaw` 仓库的实时施工状态板。

它不替代总方案，也不替代专项执行计划；它的用途只有一个：
让下一位接手的 agent / 开发者在几分钟内知道“现在做到哪、主链是什么、下一步先干什么”。

---

## 1. 阅读顺序

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. 本文档 `TASK_STATUS.md`
4. `UNIFIED_ACCEPTANCE_STANDARD.md`（如任务涉及测试、验收、发布、完成声明、live smoke、long soak、真实运行结论）
5. `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`（如任务涉及上位 carrier 目标 / symbiotic host runtime / seat runtime / workspace / host event）
6. `implementation_plan.md`
7. `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
8. `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
9. `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`（如任务涉及短中长期 formal planner 缺口、Claude Code planning shell donor 边界、assignment/cycle/strategy planning 能力建设）
10. `docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md`（如任务涉及 formal planner 施工顺序、P-2/P-3/P-4/P-5 分阶段实现、planner file/test map）
11. `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md`
12. `CHAT_RUNTIME_ALIGNMENT_PLAN.md`
13. `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`（如任务涉及 runtime-first / computer-control / orchestrator / environment plane 视角）
14. `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`（如任务涉及 execution agent computer bodies / browser-desktop-document runtime / contention / recovery）
15. `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`（如任务涉及 fixed SOP / automation / `n8n` 退役 / runtime automation IA）
16. `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`（如任务涉及 fixed SOP kernel 施工顺序）
17. `docs/superpowers/specs/2026-04-03-multi-seat-capability-autonomy-design.md`（如任务涉及 skill/MCP 自动安装、角色原型能力包、执行位实例能力快照、多执行位能力治理、升级替换与回滚）
18. `docs/superpowers/plans/2026-04-03-multi-seat-capability-autonomy-implementation-plan.md`（如任务涉及多执行位能力自治的后端施工顺序、快/慢循环接线、seat 作用域 MCP 挂载与技能生命周期落地）
19. `docs/superpowers/specs/2026-04-04-external-capability-assimilation-architecture.md`（如任务涉及 donor-first 能力吸纳、外部项目/skill/MCP/adapter/provider 供给面、source chain、opportunity radar、多源去重与能力组合治理）
20. `docs/superpowers/plans/2026-04-04-external-capability-assimilation-implementation-plan.md`（如任务涉及 donor-first 外部能力吸纳的对象落地、discovery source chain、自主 scout、portfolio governance 与 Runtime Center 接线）
21. `docs/superpowers/specs/2026-04-04-next-round-discipline-closure-spec.md`（如任务涉及下一轮 runtime/capability 纪律收口、熵控制、source chain、去重归一、写串行合同、child-run shell、MCP 生命周期、skill/package 元数据与 portfolio compaction）
22. `docs/superpowers/plans/2026-04-04-donor-first-capability-evolution-priority-plan.md`（如任务涉及纠偏后的 capability evolution 下一轮施工顺序、donor-first 复用优先级、baseline import、MCP-native candidate、fallback-only local authored 边界）
23. `docs/superpowers/specs/2026-04-06-universal-donor-execution-contract-design.md`（如任务涉及 donor formal provider injection、universal execution envelope、host compatibility contract、真实 donor “安装后不等于真正可用”的平台收口）
24. `docs/superpowers/specs/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-design.md`（如任务涉及“不要只做页面理解”，而要把 browser/document/desktop 升级成主动探测、状态图、能力孪生、收益排序这一层）
25. `docs/superpowers/plans/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-implementation-plan.md`（如任务涉及这条新方向的正式施工顺序、文件落点、测试和分层验收）
26. 与当前任务直接相关的源码和测试

---

## 1.0 `2026-04-16` 统一验收口径

- 自今日起，`TASK_STATUS.md` 里所有“已完成 / 已通过 / 已闭环 / 可放行”记录，都必须显式标明对应的验收层级：
  - `L1` 单元验证
  - `L2` 集成 / 合同验证
  - `L3` 真实运行 smoke
  - `L4` 长链 soak
- `default regression`、`focused regression`、`live smoke`、`long soak` 必须拆开写，不允许再混成一句“测试通过”。
- 以后凡是只证明了代码基线、局部回归、仓库内默认回归通过，都不能直接写成“真实运行已完成”。
- 如果 live 或 soak 没跑，必须明确写“没跑”和原因；不允许默认省略。
- 统一口径以仓库根目录 `UNIFIED_ACCEPTANCE_STANDARD.md` 为准；本文件里的阶段状态记录以后都按该文档表达完成度。

## 1.0.1 `2026-04-20` 外部执行体 hard-cut 方向补充

- 当前新方向已经收口为：
  - `CoPaw = 主脑框架`
  - `External Executor Runtime = 可插拔执行层`
  - 被替换的是本地多 agent 执行层，不是主脑
- 旧 GitHub/open-source donor 接入面不再以“任意项目接入”为正式目标，后续要收口成“只接执行体 runtime provider”
- 第一适配器是 `Codex App Server`
- 后续允许接入 `Hermes` 与其他具备正式控制面的开源智能体 runtime
- 系统必须同时支持：
  - `single-runtime`
    - 所有执行位统一用一个执行体
  - `role-routed`
    - 不同职业绑定不同执行体
- 模型调用必须进入统一治理，不能完全散落在各执行体私有配置中
- 当前正式边界还需要写死：
  - `External Executor Runtime` 不是 `MCP`
  - `External Executor Runtime` 也不是 `skill`
  - `MCP/skill` 只能作为执行体内部工具层或 workflow 增强层存在
- 当前已明确的实现级缺口包括：
  - `models_external_runtime.py` 仍不足以表达 executor thread/turn truth
  - `external_adapter_contracts.py` / `external_adapter_execution.py` 仍不足以表达 app-server/event-stream 控制面
  - bootstrap/runtime service graph 仍把 actor runtime 硬接为正式执行底座
  - Runtime Center 与主脑上下文仍是 actor-first 读面
  - `query_execution_runtime.py` 仍把本地工具和旧 agent runtime 硬写进执行前门
  - `delegation_service.py` 仍承担正式派单链
  - `models_agents_runtime.py` 仍是完整 persisted truth，而新 executor truth 还没补齐
- 当前还没彻底收口的 donor-first 遗留包括：
  - `/capability-market/projects/install*`
  - `project-package / adapter / runtime-component`
  - donor trust/trial/portfolio state
  - Runtime Center donor/external-runtime 双读面
  - donor-first 旧 specs / tests / TASK_STATUS 口径

## 1.0.2 `2026-04-20` 外部执行体 hard-cut 当前落点（Task 1-5 已进入主链，Task 6/7 部分完成）

- 当前阶段边界：
  - `Task 1`：已完成。设计/模型/迁移/状态/退役文档现已按 executor-runtime 方向同步，`ExecutorRuntime != MCP != skill` 的边界文本保持不变。
  - `Task 2`：部分完成。提交 `3c2327c`（`feat: start formal executor runtime state layer`）已落地正式 executor runtime state layer：
    - `src/copaw/state/models_executor_runtime.py`
    - `src/copaw/state/executor_runtime_service.py`
    - `tests/state/test_executor_runtime_service.py`
    - 当前仍未完成原计划里的 `models_external_runtime.py` / `external_runtime_service.py` bridge 收口。
  - `Task 3`：部分完成。提交 `d772861`（`refactor: add generic executor protocol taxonomy`）已落地首批 generic executor protocol taxonomy 与 focused tests：
    - `src/copaw/capabilities/external_adapter_contracts.py`
    - `tests/capabilities/test_executor_runtime_contracts.py`
    - `tests/capabilities/test_executor_runtime_execution.py`
    - 当前仍未完成原计划里的 `external_adapter_execution.py` / `external_runtime_execution.py` / `project_donor_contracts.py` 全量重构。
  - `Task 4`：已完成。提交 `155c6b6`（`feat: add codex app server executor adapter`）已落地 Codex first adapter：
    - `src/copaw/kernel/executor_runtime_port.py`
    - `src/copaw/adapters/executors/codex_protocol.py`
    - `src/copaw/adapters/executors/codex_app_server_adapter.py`
    - `tests/adapters/test_codex_app_server_adapter.py`
  - `Task 5`：当前工作树已完成到 `L1 + L2`。以 `a73cace` 的 ingest slice 为起点，本轮继续补上：
    - `src/copaw/kernel/executor_event_ingest_service.py`
    - `src/copaw/kernel/executor_event_writeback_service.py`
    - `src/copaw/kernel/runtime_coordination.py`
    - `src/copaw/state/main_brain_service.py` 中 `AgentReportService.record_structured_report(...)`
    - `tests/kernel/test_executor_event_ingest_service.py`
    - `tests/kernel/test_executor_event_writeback_service.py`
    - `tests/state/test_agent_report_service_structured_write.py`
    - 当前已经证明 `Assignment -> ExecutorRuntime -> Event -> Evidence/Report` focused mainline 可跑；剩余边界是没有 `L3/L4`，也还没有 formal persisted `ExecutorEventRecord` 真相对象。
  - `Task 6`：部分完成。当前工作树已补：
    - `src/copaw/app/runtime_center/execution_runtime_projection.py`
    - `src/copaw/app/runtime_center/state_query.py`
    - `src/copaw/app/runtime_bootstrap_query.py`
    - `console/src/pages/RuntimeCenter/viewHelpers.tsx`
    - `tests/app/test_runtime_center_executor_runtime_projection.py`
    - `tests/app/test_runtime_center_executor_runtime_bootstrap.py`
    - Runtime Center 外部 runtime list/detail 现在优先读 executor runtime truth，并保留 legacy fallback；但 actor runtime 仍未进入 `read-only-compat`，overview/control 读面也还没完全退役。
  - `Task 7`：部分完成。focused verification、`MCP/skill` guardrail regression、widened `default regression`、以及 selected `L3/L4` 证据现在都已基于真实代码状态补齐；但这仍不等于整套 cutover 已完成，因为 `Task 2/3/5` 的 formal truth / retirement 边界仍未全部收口。
- 当前阶段边界补充：
  - 旧本地 actor runtime 仍然在应用启动图里存在，`delegation_service.py` 也还没有退役，所以这轮不能写成“旧执行脑已完全删除”。
  - 当前能硬说的是：executor 主链接缝、focused writeback 主链、Runtime Center 外部 runtime executor projection，以及 selected runtime smoke/soak 证据都已入树；但整套 cutover 仍未完全收口，更不能写成 formal executor-provider / persisted executor-event truth 已全部终态化。
- 当前 focused regression 证据：
  - Executor focused regression：
    - 命令：`PYTHONPATH=src python -m pytest tests/adapters/test_codex_app_server_adapter.py tests/capabilities/test_executor_runtime_contracts.py tests/capabilities/test_executor_runtime_execution.py tests/state/test_executor_runtime_service.py tests/state/test_agent_report_service_structured_write.py tests/kernel/test_executor_event_ingest_service.py tests/kernel/test_executor_event_writeback_service.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_runtime_center_executor_runtime_projection.py tests/app/test_runtime_center_executor_runtime_bootstrap.py tests/app/test_executor_event_writeback_bootstrap.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_center_external_runtime_api.py -q`
    - 结果：`89 passed in 32.96s`
    - 验收层级：`L1 + L2`
  - Main-brain orchestrator sanity：
    - 命令：`PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_orchestrator.py -q`
    - 结果：`6 passed in 7.11s`
    - 验收层级：`L1 + L2`
  - Frontend focused regression：
    - 命令：`npm --prefix console test -- src/pages/RuntimeCenter/viewHelpers.test.tsx`
    - 结果：`12 passed`
    - 验收层级：`L1 + L2`
  - `MCP/skill` guardrail regression：
    - 命令：`PYTHONPATH=src python -m pytest tests/capabilities/test_capability_discovery.py tests/capabilities/test_install_templates.py tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/test_skills_cmd.py tests/capabilities/test_mcp_registry_cache.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/predictions/test_skill_trial_service.py tests/predictions/test_skill_candidate_service.py -q`
    - 结果：`103 passed in 48.21s`
    - 验收层级：`L1 + L2`
  - `default regression`：
    - 命令：`python scripts/run_p0_runtime_terminal_gate.py`
    - 结果：后端主链回归 `361 passed in 238.94s`；长跑与删旧回归 `84 passed in 387.04s`；前台定向回归 `21 passed`；控制台构建通过
    - 验收层级：`L2`
  - `L3` live smoke：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
    - 结果：`16 passed in 94.23s`
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "runtime_center or runtime_center_overview or canonical_flow or operator or chat_run or long_run_smoke"`
    - 结果：`4 passed, 7 deselected in 36.45s`
    - 验收层级：`L3`
  - `L4` long soak：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
    - 结果：连续 `3` 轮分别为 `27 passed in 178.60s`、`27 passed in 176.46s`、`27 passed in 177.24s`
    - 验收层级：`selected L4`
- 当前仍需优先盯住的缺口：
  - `delegation_service.py` 仍承担正式派单链
  - Runtime Center actor overview/control 读面仍未完全切到 executor-runtime-first
  - actor runtime 仍未降到 `read-only-compat`
  - browser / desktop / document 本地执行层仍是后续退役目标，而不是本轮已删除项

## 1.0.3 `2026-04-21` 外部执行体 hard-cut actor-runtime `read-only-compat` 收口

- 当前工作树新增收口：
  - `src/copaw/app/routers/runtime_center_routes_actor.py` 已删除 actor mutation / actor capability mutation 路由：
    - `/runtime-center/actors/{agent_id}/pause`
    - `/runtime-center/actors/{agent_id}/resume`
    - `/runtime-center/actors/{agent_id}/retry/{mailbox_id}`
    - `/runtime-center/actors/{agent_id}/cancel`
    - `/runtime-center/actors/{agent_id}/capabilities`
    - `/runtime-center/actors/{agent_id}/capabilities/governed`
  - `src/copaw/app/routers/runtime_center_payloads.py` 现把 actor runtime payload 显式标记为：
    - `compatibility_mode = read-only-compat`
    - `formal_surface = false`
    - `agent_capabilities_route = /api/runtime-center/agents/{agent_id}/capabilities`
  - `src/copaw/kernel/agent_profile_service.py` 的 capability surface 已删除 `actor_governed_assign` / `actor_direct_assign`，只保留 agent formal 写路由。
  - `console/src/components/RuntimeExecutionStrip.tsx`、`console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`、`console/src/pages/AgentWorkbench/useAgentWorkbench.ts`、`console/src/api/modules/runtimeCenter.ts` 已删除 actor pause/resume/cancel/retry 控制 affordance 与前端 mutation helper；Agent Workbench capability governance 统一只走 `/runtime-center/agents/{agent_id}/capabilities*`。
- 当前能诚实表述的结论：
  - actor runtime 在 Runtime Center / Agent Workbench 这条前端-后端链上已降为 `read-only-compat`
  - 这证明 Task 6 的 actor compatibility demotion slice 已到 `L1 + L2`
  - 这不等于整个 external-executor hard-cut 已完成，更不等于 `delegation_service.py` / donor-provider 边界已全部删除
- 当前 fresh focused regression 证据：
  - Actor compatibility backend：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_runtime_center_actor_api.py -q`
    - 结果：`8 passed in 37.69s`
    - 验收层级：`L1 + L2`
  - Runtime Center executor/actor focused regression：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_executor_runtime_projection.py tests/app/test_runtime_center_executor_runtime_bootstrap.py -q`
    - 结果：`17 passed in 56.78s`
    - 验收层级：`L1 + L2`
  - Frontend actor compatibility focused regression：
    - 命令：`npm --prefix console test -- src/components/RuntimeExecutionStrip.test.tsx src/components/RuntimeExecutionLauncher.test.tsx src/pages/AgentWorkbench/runtimePanels.test.tsx src/pages/AgentWorkbench/useAgentWorkbench.test.tsx src/pages/AgentWorkbench/index.test.tsx`
    - 结果：`13 passed`
    - 验收层级：`L1 + L2`
  - Frontend build regression：
    - 命令：`npm --prefix console run build`
    - 结果：`tsc -b && vite build` 通过
    - 验收层级：`L1 + L2`
- 当前仍然明确未完成：
  - 共享 `default regression` / selected `L3` / selected `L4` 证据现已补齐，详见 `1.0.6`
  - `delegation_service.py` 仍未退役
  - `/capability-market/projects/install*` / donor-provider compatibility 边界未在本轮继续推进
  - 因此 actor-runtime compatibility demotion 这条 slice 现在只能诚实写成 `L1 + L2 + default regression + selected L3 + selected L4`，不能写成整套 external-executor hard-cut 已闭环

## 1.0.4 `2026-04-21` delegation default-surface compatibility demotion

- 当前工作树继续把 `Task 2 / Step 4` 往前推了一个默认暴露面收口切片，但这次没有物理删除 `delegation_service.py`：
  - `src/copaw/kernel/agent_profile_service.py`
    - execution-core baseline capability 已移除 `system:delegate_task`
    - prompt capability projection 不再把 `delegate_task` 计入默认 dispatch bucket
  - `src/copaw/industry/compiler.py`
    - execution-core 行业 baseline capability 已移除 `system:delegate_task`
  - `src/copaw/kernel/query_execution_runtime.py`
    - execution-core query runtime 的默认 system capability allowlist 已移除 `system:delegate_task`
  - `src/copaw/kernel/query_execution_prompt.py`
    - delegation-first prompt 不再把 `dispatch_query / delegate_task` 并列成默认动作
    - 若显式挂载 `delegate_task`，prompt 现在会把它描述为 legacy compatibility path，而不是正式首选执行链
  - `src/copaw/kernel/query_execution_tools.py`
    - `delegate_task` tool docstring 已同步成 compatibility 口径
  - `src/copaw/capabilities/sources/system.py`
    - `system:delegate_task` 已明确标记为 local child-task delegation compatibility alias
- 当前能诚实表述的结论：
  - execution-core 默认不再把 `delegate_task` 当正式一等能力暴露给 query runtime / prompt / capability projection
  - `TaskDelegationService` 仍然存在，且显式 `system:delegate_task` / runtime-center focused compatibility tests 继续可用
  - 这证明 delegation default-surface demotion slice 到了 `L1 + L2`
  - 这不等于 `delegation_service.py` 已退役，更不等于 assignment formal execution backend 已完全切离本地 actor compatibility chain
- 当前 fresh focused regression 证据：
  - Delegation default-surface + compatibility focused regression：
    - 命令：`python -m pytest tests/kernel/test_agent_profile_service.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/query_execution_environment_parts/dispatch.py tests/kernel/test_assignment_envelope.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_task_delegation_api.py -q`
    - 结果：`130 passed in 88.04s`
    - 验收层级：`L1 + L2`
- 当前仍然明确未完成：
  - `delegation_service.py` 仍承担显式 compatibility delegation 写链，尚未物理退役
  - 共享 `default regression` / selected `L3` / selected `L4` 证据现已补齐，详见 `1.0.6`
  - 因此 delegation default-surface demotion 这条 slice 现在只能诚实写成 `L1 + L2 + default regression + selected L3 + selected L4`

## 1.0.5 `2026-04-21` donor/project intake compatibility-acquisition-only 标记收口

- 当前工作树继续把 `Task 4` 往前推了一个正式表面降级切片，但这次仍没有把 donor/project intake 替换成 formal executor provider：
  - `src/copaw/capabilities/project_donor_contracts.py`
    - 已给 project donor contract metadata 与 projected package metadata 统一补上：
      - `compatibility_mode = compatibility/acquisition-only`
      - `formal_surface = false`
  - `src/copaw/app/routers/capability_market.py`
    - `/capability-market/projects/search`
    - `/capability-market/projects/install`
    - `/capability-market/projects/install-jobs/{task_id}`
    - `/capability-market/projects/install-jobs/{task_id}/result`
    - 上述 donor/project surface 现都会显式返回 compatibility/acquisition-only 标记，不再裸露成像 formal executor-provider intake 的产品面
    - project candidate materialization / install contract metadata / persisted external package metadata 也会继承同一标记
  - `src/copaw/app/runtime_center/state_query.py`
    - Runtime Center donor/package projection 现统一补上 compatibility/acquisition-only 标记
    - donor/package 读面同时兼容 dict-backed service payload，不再只接受 `model_dump()` 结果
- 当前能诚实表述的结论：
  - donor/project intake 这条产品与状态读面现在已明确标为 `compatibility/acquisition-only`
  - 这证明 `Task 4` 的“先标记 compatibility，再阻止误读为 canonical executor surface”切片已到 `L1 + L2`
  - 这不等于 formal `ExecutorProvider` intake 已落地，更不等于 donor/project runtime taxonomy 已从所有 state/trial/read 面彻底拆除
- 当前 fresh focused regression 证据：
  - donor/project compatibility surface focused regression：
    - 命令：`PYTHONPATH=src python -m pytest tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_center_external_runtime_api.py -q`
    - 结果：`96 passed in 77.54s`
    - 验收层级：`L1 + L2`
- 当前仍然明确未完成：
  - formal `ExecutorProvider / control_surface_kind / protocol_surface_kind` intake 仍未完全替换 donor/project install 前门
  - donor state/trust/trial/retirement 全量 taxonomy 仍未完成正式拆分
  - 共享 `default regression` / selected `L3` / selected `L4` 证据现已补齐，详见 `1.0.6`
  - 因此 donor/project compatibility demotion 这条 slice 现在只能诚实写成 `L1 + L2 + default regression + selected L3 + selected L4`

## 1.0.6 `2026-04-21` external-executor hard-cut 验收补录（default regression + selected `L3/L4`）

- 这轮 hard-cut 收口在补跑 widened `default regression` 时，先暴露出 `industry` 默认 gate 里的 3 个真实断点：
  - `IndustryDraftGenerator` 缺模型配置时被错误归到 `MODEL_STRUCTURED_VALIDATION_FAILED / 502`
  - `tests/app/industry_api_parts/runtime_updates.py` 中 2 条 governance block-reason 断言仍停在旧英文 copy，而正式实现已切到中文治理文案
- 当前工作树已同步修正：
  - `src/copaw/providers/runtime_model_call.py`
    - `_resolve_model()` 现在把模型工厂抛出的解析/配置异常统一视为 `MODEL_UPSTREAM_ERROR`
    - 因此 `industry` preview 缺少 active/fallback chat model 时重新回到 `503 service unavailable` 合同，而不是误报 `502 structured validation failed`
  - `tests/app/test_industry_draft_generator.py`
    - 新增 focused regression，锁定“缺模型配置 -> upstream unavailable / 503”合同
  - `tests/app/industry_api_parts/runtime_updates.py`
    - 默认 gate 内的 staffing / runtime-handoff governance 断言已对齐当前中文正式 copy
- 当前 fresh verification 证据：
  - focused regression：
    - 命令：`python -m pytest tests/app/test_industry_draft_generator.py -q -k "missing_chat_model_as_upstream_unavailable"`
    - 结果：`1 passed, 5 deselected in 4.21s`
    - 验收层级：`L1 + L2`
    - 命令：`python -m pytest tests/app/industry_api_parts/runtime_updates.py -q -k "test_industry_preview_returns_service_unavailable_when_chat_model_missing or test_governance_blocks_dispatch_when_pending_staffing_proposal_is_not_top_active_gap or test_report_followup_backlog_wins_next_cycle_over_unrelated_open_backlog_when_handoff_and_staffing_are_live"`
    - 结果：`3 passed, 45 deselected in 28.56s`
    - 验收层级：`L1 + L2`
  - `default regression`：
    - 命令：`python scripts/run_p0_runtime_terminal_gate.py`
    - 结果：后端主链回归 `361 passed in 238.94s`；长跑与删旧回归 `84 passed in 387.04s`；前台定向回归 `21 passed`；控制台构建通过
    - 验收层级：`L2`
  - `L3` live smoke：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
    - 结果：`16 passed in 94.23s`
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "runtime_center or runtime_center_overview or canonical_flow or operator or chat_run or long_run_smoke"`
    - 结果：`4 passed, 7 deselected in 36.45s`
    - 验收层级：`L3`
  - `L4` long soak：
    - 命令：`PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
    - 结果：连续 `3` 轮分别为 `27 passed in 178.60s`、`27 passed in 176.46s`、`27 passed in 177.24s`
    - 验收层级：`selected L4`
- 当前能诚实表述的结论：
  - actor-runtime `read-only-compat`、delegation default-surface demotion、以及 donor/project compatibility demotion 这三个 `2026-04-21` 收口 slice 现在都已具备 `L1 + L2 + default regression + selected L3 + selected L4`
  - 这不等于整套 external-executor hard-cut 已终态完成，更不等于 formal `ExecutorProvider` intake / persisted `ExecutorEventRecord` / `delegation_service.py` retirement 已全部收口
  - `live external-provider smoke` 与 full-repo soak 仍未在这轮执行，不得混写成“所有真实外部执行链都已验证”

## 1.1.1 `2026-04-07` Buddy 领域能力阶段收口补充

- Buddy 当前成长阶段的正式真相已从关系经验切到 active `BuddyDomainCapabilityRecord`
- `CompanionRelationship.companion_experience` 继续保留，但只作为关系层信号，不再决定 stage
- Buddy execution carrier 的正式真相已从 profile-global `buddy:{profile_id}` 收口为“每个 `BuddyDomainCapabilityRecord` 各自绑定自己的 carrier continuity”
- 新增正式后端链路：
  - `POST /buddy/onboarding/direction-transition-preview`
  - `POST /buddy/onboarding/confirm-direction` with `capability_action`
  - `GET /buddy/surface` / Runtime Center buddy summary 统一读取 active domain capability
- 新增正式状态对象：
  - `BuddyDomainCapabilityRecord`
    - `domain_key / domain_label / capability_score / evolution_stage / strategy_score / execution_score / evidence_score / stability_score`
    - `industry_instance_id / control_thread_id / domain_scope_summary / domain_scope_tags`
- 前端已同步把 stage 文案收口为：
  - `幼年期 / 成长期 / 成熟期 / 完全体 / 究极体`
- Buddy 领域能力分现在会从当前 execution carrier 的正式规划/执行事实自动刷新：
  - `industry_instance / lanes / backlog / cycles / assignments / agent_reports / evidence_ids`
  - 不再停留在“record 结构已存在，但能力分不会自己增长”的半成品状态
- BuddyOnboarding 的换目标确认现在是显式人工确认 UI：
  - 先 preview，再由用户明确选择 `keep-active / restore-archived / start-new`
  - 前端不再自动接受系统推荐动作
- Buddy carrier 切换规则现已正式化：
  - `keep-active`：沿用当前 domain 绑定 carrier
  - `restore-archived`：恢复历史 domain 绑定的旧 carrier / 旧 control thread continuity
  - `start-new`：冻结旧 domain carrier，并为新 domain 创建 fresh carrier，不再继承旧 runtime 事实
- Buddy 页面与聊天的职责边界已收口：
  - 页面只负责主领域硬切换
  - 聊天只负责当前领域扩展，不自动切换 domain carrier
- 当前 fresh verification：
  - backend：
    - `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
    - 结果：`38 passed`
  - console：
    - `npm --prefix console test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/runtime/buddyFlow.test.ts`
    - 结果：`35 passed`
  - console build：
    - `npm --prefix console run build`
    - 结果：通过

## 1.1.2 `2026-04-08` Buddy stage points/gates cutover

- Buddy 当前成长阶段的正式规则已从 `capability_score -> stage` 切到 `capability_points + promotion gates -> stage`
- `capability_score / strategy_score / execution_score / evidence_score / stability_score` 继续保留，但只作为兼容读面和附属指标，不再决定正式 stage
- Buddy 当前领域成长积分的正式口径已固定为：
  - `1` 次真实闭环 = `2` 积分
  - 真实闭环必须同时满足：正式 `Assignment` 已结算完成、存在对应 completed `AgentReport`、且有非空 evidence
- Buddy 正式晋级门槛已固定为：
  - `bonded`：`capability_points >= 20`
  - `capable`：`capability_points >= 40` 且 `settled_closure_count >= 1`
  - `seasoned`：`capability_points >= 100` 且 `distinct_settled_cycle_count >= 3`
  - `signature`：`capability_points >= 200`，且 `independent_outcome_count >= 10`、`recent_completion_rate >= 0.92`、`recent_execution_error_rate <= 0.03`
- Buddy 正式降级规则已固定为：
  - 每次 growth refresh 最多只允许降 `1` 级
  - 不允许一次刷新跨多级下跌
- Chat / BuddyPanel / BuddyOnboarding preview / Runtime Center buddy summary 现已统一投影积分制字段：
  - `capability_points`
  - `settled_closure_count`
  - `independent_outcome_count`
  - `recent_completion_rate`
  - `recent_execution_error_rate`
  - `distinct_settled_cycle_count`
- 当前 fresh verification：
  - backend：
    - `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_domain_capability.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
    - 结果：`52 passed`
  - console：
    - `npm --prefix console test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/runtime/buddyFlow.test.ts`
    - 结果：`36 passed`
  - console build：
    - `npm --prefix console run build`
    - 结果：通过

## 1.1.3 `2026-04-11` Buddy onboarding collaboration contract hard-cut

- Buddy onboarding 前门已从“澄清问答回合”正式切到“协作合同直填 + compile”。
- 当前正式主链固定为：
  - `POST /buddy/onboarding/identity`
  - `POST /buddy/onboarding/contract`
  - `GET /buddy/onboarding/{session_id}/candidates`
  - `POST /buddy/onboarding/direction-transition-preview`
  - `POST /buddy/onboarding/confirm-direction`
  - `POST /buddy/name`
  - `GET /buddy/surface`
- 如需异步 UI，不再走 `clarify`，而是走：
  - `POST /buddy/onboarding/identity/start`
  - `POST /buddy/onboarding/contract/start`
  - `POST /buddy/onboarding/confirm-direction/start`
- `Buddy surface.onboarding` 的正式合同已收口为：
  - `service_intent`
  - `collaboration_role`
  - `autonomy_level`
  - `confirm_boundaries`
  - `report_style`
  - `collaboration_notes`
  - `candidate_directions`
  - `recommended_direction`
  - `selected_direction`
  - `requires_direction_confirmation`
  - `requires_naming`
  - `completed`
- 旧澄清问答字段已从活代码前后端合同退役，不应再被当成正式 onboarding 真相：
  - `question_count`
  - `tightened`
  - `next_question`
  - `existing_question_count`
- `2026-04-05` 那条“最多 9 问澄清对话”的历史设计口径已被本条 supersede；当前正式方向是“身份建档 -> 协作合同 compile -> 方向确认 -> 首次命名/进入聊天”，不是继续维护问答机。
- `2026-04-11` 本轮收尾补充：
  - Buddy persona block 与 execution-core identity 里的协作合同标签已收口为中文提示，不再继续混入 `Buddy name / Service intent / Collaboration role` 这类英文标签。
  - `docs/superpowers/plans/2026-04-05-main-brain-buddy-companion-implementation-plan.md` 已补强 supersede 说明；文中残留 `clarification / question_count / next_question` 等旧措辞只代表历史施工痕迹，不再代表当前正式合同。
- 当前 fresh verification：
  - backend：
    - `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_persona_prompt.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_main_brain_chat_service.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/test_buddy_onboarding_activation.py tests/kernel/test_buddy_onboarding_latency.py tests/kernel/test_buddy_projection_capability.py -q`
    - 结果：`83 passed`
  - console：
    - `npm --prefix console run test -- src/api/modules/buddy.test.ts src/runtime/buddyFlow.test.ts src/pages/BuddyOnboarding/index.test.tsx src/routes/entryRedirect.test.tsx`
    - 结果：`14 passed`
  - console build：
    - `npm --prefix console run build`
    - 结果：通过

## 1.2 `2026-04-05` donor-first 开源项目能力落位补充

- GitHub open-source donor 不再只以 `SKILL.md` bundle 形式落地。
- 正式新增的一等 capability landing：
  - `project-package`
  - `adapter`
  - `runtime-component`
- `/capability-market/projects/install` 已改为真实开源项目 materialization 前门，不再先降成 `skill:*` 再冒充 project donor。
- config-backed external capability mounts 已接入统一 `capability graph / catalog / execution`，可以被正式列出、切换、删除、执行。
- 当前默认 project donor materialization 已改成 bounded HTTP transport first：优先 `codeload tar.gz -> GitHub archive zip`，`git clone` 只作为最后兜底，避免真实网络环境下先卡死在长时间 `git clone`。
- `2026-04-05` fresh regression：
  - `129 passed`
- `2026-04-05` live smoke 已真实验证：
  - GitHub donor search：
    - `psf/black`
    - `HKUDS/OpenSpace`
  - real install + unified execution：
    - `project:black`
      - `discover -> install -> run` 已真实通过，统一执行面返回真实 `black --version`
    - `runtime:openspace`
      - `discover -> install -> start -> ready -> stop` 已通过正式前门真实跑通
      - install contract 会正式落成 `startup_entry_ref=script:openspace-dashboard`、`predicted_default_port=7788`、`health_url=http://127.0.0.1:7788/health`
      - `start` 会进入 bounded readiness wait，而不是一轮立即 probe 失败就误判 `degraded`
  - real API front-door：
    - `/capability-market/projects/install` 对 `https://github.com/psf/black` 返回真实 `candidate_id`，并安装 `project:black`
    - `/capability-market/projects/install` 对 `https://github.com/HKUDS/OpenSpace` 返回真实 `runtime_contract`
    - `/runtime-center/external-runtimes/actions` 对 `runtime:openspace` 的 `start/stop` 已按动作类型透传 typed payload，不再把 `runtime_id=null` 或 `args=[]` 之类无关字段塞给错误动作模型

- 当前 donor Python runtime 的真实边界：
  - CLI donor 闭环已被真实验证
  - service donor 的 formal install/start/healthcheck/stop/state chain 已被真实验证
  - 至少 1 个真实 Python service donor（`HKUDS/OpenSpace`）已完成 `search -> install -> ready -> stop`
  - 当前边界仍是“符合 Python/GitHub/isolated-venv/runtime-contract 合同的项目”，不等于任何语言、任何构建系统的任意仓库都已自动适配

## 1.2.3 `2026-04-06` donor install async job front-door 补充

- `/capability-market/projects/install` 已从“长阻塞 HTTP 安装请求”收口为“正式异步 install job 创建前门”。
- 当前正式前门合同改为：
  - `POST /capability-market/projects/install`
    - 立即返回 `202 Accepted`
    - 返回 `task_id / status / phase / routes`
  - `GET /capability-market/projects/install-jobs/{task_id}`
    - 返回 install job 当前 `status / stage / progress_summary / error / result`
  - `GET /capability-market/projects/install-jobs/{task_id}/result`
    - 仅在 job `completed` 后返回最终 donor install 结果
- 这轮没有新造一套内存 install-job 真相：
  - install job 状态复用现有 `KernelTaskStore -> TaskRecord / TaskRuntimeRecord`
  - job 进度与最终结果挂在同一条 kernel task payload/runtime truth 上
  - `Runtime Center` 已可通过既有 kernel task detail/review 路由读取同一任务，不需要第二套 task 系统
- 这样重 donor（例如此前会把前端长请求顶超时的 service donor）不再依赖单个 HTTP 请求硬撑到安装完成。
- install job 现在不再只暴露一个粗粒度 `installing`：
  - `_install_external_project_capability(...)` 已正式回写细粒度阶段
  - 当前已落位的阶段包括：
    - `resolve_ref`
    - `bootstrap_env`
    - `download_transport`
    - `pip_install`
    - `inspect_distribution`
    - `compile_contract`
    - `persist_mount`
  - `GET /capability-market/projects/install-jobs/{task_id}` 会把这些阶段直接投影到 `stage / progress_summary`
- 失败收口也已补齐：
  - install job 失败时，`/install-jobs/{task_id}` 会返回 terminal `failed`
  - `/install-jobs/{task_id}/result` 会对 failed job 返回 `409` + 真实错误摘要，而不是继续伪装成“还在跑”
  - install job 若被 runtime cancel / shutdown 打断，也会正式收口到 terminal `cancelled`，不再遗留 `running`
- 当前 fresh regression：
  - `python -m pytest tests/app/test_capability_market_api.py tests/app/test_runtime_center_donor_api.py tests/capabilities/test_project_donor_contracts.py -q`
  - 结果：`55 passed`
- `2026-04-06` fresh verification 补充：
  - 直接 donor install 内核 smoke：
    - 真实仓库：`https://github.com/psf/black`
    - 结果：在独立临时 `COPAW_WORKING_DIR` 下完成 `resolve_ref -> bootstrap_env -> download_transport -> pip_install -> inspect_distribution -> compile_contract -> persist_mount`
    - 终态：成功落成 `project:black`
  - 真实 HTTP front-door smoke：
    - 启动本地 HTTP server 后，真实调用：
      - `POST /capability-market/projects/install`
      - `GET /capability-market/projects/install-jobs/{task_id}`
      - `GET /capability-market/projects/install-jobs/{task_id}/result`
    - 真实仓库：`https://github.com/psf/black`
    - 结果：job 从 `pip_install` 进入 `completed`，最终可读到 `project:black` 安装结果
- 当前诚实边界：
  - 这轮已证明“正式异步 install job 前门 + 细粒度阶段可见 + terminal result 可取”成立
  - 但真实大型 donor 的单阶段耗时仍可能主要集中在 `pip_install`
  - 因此这轮解决的是“别再假卡死、别再靠长 HTTP 顶住、别再没有 terminal truth”，不是“所有 donor 安装都会很快”

## 1.2.1 `2026-04-06` donor adapter common-base assimilation 补充

- 已新增并落地的公共吸纳主链：
  - `protocol surface classify`
  - `compiled adapter contract`
  - `typed adapter execution`
  - `trial / lifecycle / evidence attribution`
  - `Runtime Center candidate adapter read-model`
- 当前正式对象口径已收口为：
  - 外部 intake/transport 事实：
    - `native_mcp`
    - `api`
    - `sdk`
    - `cli_runtime`
  - CoPaw 内部正式能力对象：
    - `project-package`
    - `runtime-component`
    - `adapter`
- 当前 fresh regression：
  - `PYTHONPATH=src python -m pytest tests/capabilities/test_external_adapter_contracts.py tests/capabilities/test_external_adapter_compiler.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_center_donor_api.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/predictions/test_donor_recommendations.py tests/kernel/test_query_execution_runtime.py -q`
  - 结果：`148 passed`
- 当前已验证事实：
  - runtime-only donor 现在会被正式阻断，不能再冒充 business adapter
  - compiled adapter action 可通过统一 `external-adapter` 执行面走 `mcp/http/sdk`
  - candidate/trial/lifecycle/evidence/read-model 现在会保留：
    - `protocol_surface_kind`
    - `transport_kind`
    - `compiled_adapter_id`
    - `compiled_action_ids`
    - `selected_adapter_action_id`（在 evidence/runtime attribution 面）
- 当前诚实边界：
  - 这一轮完成的是“公共 formal assimilation seam”
  - 不是“任意开源项目安装后都自动抽出 typed callable actions”
  - 现在真正 live-verified 的自动 install/start/health/stop 仍主要在 `project-package / runtime-component` 层
  - 对 `adapter` 而言，公共执行/治理主链已完成；但“从任意真实 donor 自动抽取 `mcp_tools / api_actions / sdk_actions`”仍未作为通用 live-verified discovery 合同落地

## 1.2.2 `2026-04-06` universal donor execution contract 设计补充

- 已新增正式设计文档：
  - `docs/superpowers/specs/2026-04-06-universal-donor-execution-contract-design.md`
- 该设计不是 `OpenSpace` 单项目修补，而是把真实 live probe 暴露出来的 3 个平台缺口上升成通用 donor 合同：
  - `donor provider injection`
  - `donor execution envelope / fail-fast`
  - `donor host compatibility contract`
- 该设计的核心口径是：
  - donor 可以有不同 transport / packaging / startup 方式
  - 但 provider 注入、执行超时/取消/心跳、host 兼容归一不能项目各搞一套
  - `installed`、`runtime_operable`、`adapter_probe_passed`、`primary_action_verified` 必须被区分，不得把“装上了”夸成“完全可用”
- `2026-04-06` 当前实现状态补正：
  - `src/copaw/capabilities/donor_probe_service.py` 已补齐最小 probe 正式服务：
    - `runtime-component` 走 `start -> readiness -> stop`，成功后提升到 `runtime_operable`
    - `adapter` 走最小 action probe，成功后提升到 `adapter_probe_passed`
    - 单 action adapter 可提升到 `primary_action_verified`
    - 无 formal probe 路径的 donor 保持在 `installed`，不会被夸大
  - `/capability-market/projects/install` 已在 install + trial attach 后接入 probe，并把 probe truth 回写到：
    - candidate `verified_stage / provider_resolution_status / compatibility_status`
    - scoped trial `verdict / summary / evidence_refs / probe_result`
    - lifecycle decision `reason / evidence_refs / probe_result`
  - Runtime Center donor 读面已把 `metadata.probe_result` 显式投影成 top-level：
    - `selected_adapter_action_id`
    - `probe_outcome`
    - `probe_error_type`
    - `probe_evidence_refs`
  - `query_execution_runtime` 已把 donor probe attribution 正式带入 evidence metadata：
    - `verified_stage`
    - `provider_resolution_status`
    - `compatibility_status`
    - `probe_outcome`
    - `probe_error_type`
    - `probe_evidence_refs`
  - 当前 fresh donor verification：
    - `python -m pytest tests/capabilities/test_donor_provider_injection.py tests/capabilities/test_donor_execution_envelope.py tests/capabilities/test_donor_host_compatibility.py tests/capabilities/test_donor_probe_service.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_runtime_execution.py tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py -q`
    - 结果：`113 passed`
- 当前诚实边界：
  - 这轮完成的是 universal donor execution contract 的 Task 5/6 落地和读面/evidence 收口
  - 不等于“任意 donor 都能自动发现 typed business action 并完整业务可用”
  - `project-package / runtime-component / adapter` 的 formal execution/probe/promotion 主链已接通，但更强的 donor action discovery 与更大范围 live donor 适配仍是后续增强项

---

## 1.3 `2026-04-05` 内部统一知识图谱设计补充

- 已新增正式设计文档：
  - `docs/superpowers/specs/2026-04-05-internal-unified-knowledge-graph-design.md`
- 该设计的核心口径是：
  - CoPaw 内部只能有一套正式知识图谱
  - 图谱主语是世界、目标、行动、结果，不是聊天记录或人类本身
  - 主脑运行时只读“当前任务子图”，不直接扫总图
  - 人类只作为最高指令源、治理边界与必要时的讨论伙伴进入图谱
  - activation / strategy / planning / execution / report 继续复用现有正式主链，不另造第二条 memory 或 planning truth
- 这份文档当前是知识图谱总设计，不替代：
  - `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
  - `MEMORY_VNEXT_PLAN.md`
  - `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
- 后续如进入实现，第一优先级不是扩外部知识源，而是：
  - 统一对象与关系模型
  - 统一任务子图激活入口
  - 统一 report / execution 回写总图

---

## 1.3.1 `2026-04-15` 记忆睡眠整理层 `B+` 设计补充

- 已新增正式设计文档：
  - `docs/superpowers/specs/2026-04-15-memory-sleep-layer-b-plus-design.md`
- 当前口径已收死为：
  - 共享正式记忆继续坚持 `truth-first` 与 `no-vector formal memory`
  - 下一步不是重写 memory truth，而是在 canonical `state / evidence / graph projection / strategy / formal memory` 之上新增 `B+` 睡眠整理层
  - 私有 `ConversationCompactionService` 明确排除在这轮之外，只保留线程内私有压缩
- `B+` 这轮已确定的正式对象：
  - `MemorySleepJob`
  - `MemoryScopeDigest`
  - `MemoryAliasMap`
  - `MemoryMergeResult`
  - `MemorySoftRule`
  - `MemoryConflictProposal`
  - `IndustryMemoryProfileRecord`
  - `WorkContextMemoryOverlayRecord`
  - `MemoryStructureProposalRecord`
- 第二天正式主读链目标已定为：
  - `canonical object / graph truth`
  - `sleep digest / alias / merge / soft-rule`
  - `raw text memory`
  - `lexical fallback`
- 模型权限边界已定为：
  - `digest / alias / merge / 次日展示口径` 可由模型直接决定
  - 低风险 `soft-rule` 可自动生效，但必须可回滚
  - 高风险冲突结论、长期规则变更、审批/资金/外部动作类约束只允许生成提案
- 状态说明：
  - 当前已完成“正式设计收口 + 首轮代码落地”，不是只停留在设计稿
  - 当前仓库已落地 `industry / work_context` 两类 scope 的 `B+` sleep layer 与对应测试；`C` 仍只保留路线规划，不在本轮实现
  - Runtime Center 已新增：
    - `GET /runtime-center/memory/sleep/industry-profiles`
    - `GET /runtime-center/memory/sleep/work-context-overlays`
    - `GET /runtime-center/memory/sleep/structure-proposals`
  - `MemoryProfileService` 已把 sleep-derived `industry_profile / work_context_overlay` 接入 profile 主读层
  - `MemoryRecallService` 与 `/runtime-center/memory/profiles*` 现都会显式暴露：
    - `read_layer`
    - `overlay_id`
    - `industry_profile_id`

### 1.3.1a `2026-04-16` 记忆 `B+` 真实性校正与剩余尾巴

- 当前 `industry / work_context` 两类 `B+` 记忆主链应按“已闭环”理解，不再写成 `implementation pending`：
  - 知识图谱 relation view / rebuild / recall 引用已纳入正式读链
  - 睡眠层 `industry_profile / work_context_overlay / structure_proposal` 已纳入正式派生链
  - `Runtime Center / profile / recall / surface` 已统一消费 overlay/profile 元数据
- 本轮 fresh verification 已补到：
  - `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/state/test_memory_sleep_service.py tests/state/test_memory_services.py tests/kernel/test_memory_recall_integration.py tests/memory/test_knowledge_writeback_service.py tests/app/test_runtime_center_memory_api.py tests/app/test_cron_manager.py::test_cron_manager_runs_memory_sleep_jobs_after_heartbeat tests/app/test_runtime_bootstrap_helpers.py::test_warm_runtime_memory_services_runs_idle_sleep_catchup_when_available tests/kernel/test_main_brain_chat_service.py::test_main_brain_chat_service_prompt_prefers_truth_first_profile_before_lexical_recall tests/kernel/test_main_brain_chat_service.py::test_main_brain_chat_service_scope_snapshot_prefers_overlay_profile_surface -q` -> `72 passed`
  - `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx` -> `11 passed`
  - `cmd /c npm --prefix console run build` -> 通过
  - live HTTP smoke 结果：`tmp/live_memory_bplus_smoke/result.json`
- 本轮真实修正：
  - sleep 并发写入时，pending `MemoryStructureProposal` 现会自动对齐当前 active overlay/profile，避免提案挂到旧版本
  - `/runtime-center/memory/surface` 在 `work_context_overlay` 已持有 `industry_instance_id` 时，现可自动解析并返回对应 `sleep.industry_profile`，不再依赖人工 scope 绑定
- 当前剩余只保留 2 项，不再泛化成“整套 `B+` 没做完”：
  - formal memory 当前仍以 selective ingestion 为正式写边界；高价值长期细节的更强稳定写入仍是下一轮功能重点
  - 更长时长的 mixed long-run soak 仍未完成；当前虽已通过 live / restart / parallel / scheduled smoke，但还未达到发布级连续混跑门槛

### 1.3.1c `2026-04-16` 记忆读面尾巴实收口

- 这轮按代码真相补平了 3 条此前还没完全接上的尾巴：
  - `POST /runtime-center/memory/continuity-details/pin` 已进入正式后端 API，不再是 service-only 暗能力；手动钉住会写入正式 continuity detail，并立即刷新对应 `industry / work_context` projection
  - `Knowledge` 页已新增正式“手动钉住”入口，用户可以直接提交 `detail_key + detail_text`，不再只能靠后端脚本或内部调用
  - `Runtime Center` 主脑驾驶舱已把记忆简化读面正式接回 `main_brain.cockpit.summary_fields`，当前至少包括：
    - `最该记住`
    - `关键约束`
    - `待处理整理`
    - `最近记忆整理`
- 同轮顺手补平了一条驾驶舱旧合同断点：
  - `main_brain.cockpit.trace` 与 `agents[].trace` 已重新进入正式 payload，不再出现“模型里没字段”的断点
  - 但当前只收到了后端 payload 层；驾驶舱 `追溯` tab 前端读面仍未正式落地，已转入 `docs/superpowers/specs/2026-04-16-runtime-center-trace-tab-design.md` 与 `docs/superpowers/plans/2026-04-16-runtime-center-trace-tab.md` 继续施工
- 本轮 fresh verification：
  - backend：
    - `C:\Python312\python.exe -m pytest tests/app/test_runtime_center_memory_api.py -q`
    - 结果：`24 passed`
    - `C:\Python312\python.exe -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`
    - 结果：`97 passed`
  - console：
    - `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/index.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
    - 结果：`23 passed`

### 1.3.1b `2026-04-16` 行业记忆结构增强设计已批准

- 已新增正式设计文档：
  - `docs/superpowers/specs/2026-04-16-industry-memory-structure-enhancement-design.md`
- 这轮口径已收死为“与当前 `B+` 同轮完整增强”，不是另开平行章节：
  - 不新造第二套记忆系统
  - 不重做知识图谱
  - 不引入向量库主链
  - 不把聊天压缩重新升级为共享正式记忆
- 本轮新增正式目标：
  - 让知识图谱成为睡眠层正式输入，而不是只停留在 relation read surface
  - 在固定通用主槽位之上，引入按行业/阶段动态增强的槽位体系
  - 允许多轮稳定有效的增强槽位升格为行业长期偏好，并支持失效降权
  - 为高价值长期细节补齐“模型主判 + 规则兜底 + 人工钉住”的强写入链
  - 把 `structure proposal apply` 从“改状态”升级为真正 materialize active profile/overlay 的执行动作
  - 前台只收口 `Runtime Center + Knowledge` 两个正式读面；聊天页不承担这轮行业记忆结构展示
- 这轮完成标准不按“多几个接口 / 多几个卡片”判断，而按闭环判断：
  - 图谱真的喂给睡眠层
  - 行业结构增强真的影响主读链
  - 强写入真的进入正式主读面
  - proposal apply 真执行
  - `Runtime Center / Knowledge` 真能看见
  - 长链验收跑通

---

## 1.3.2 `2026-04-15` Chat 结果可见化正式生产链补充

- Chat `turn_reply_done` 的 `tool_use_summary.result_items` 不再只依赖 compaction / 前端保守派生。
- 当前正式主链已补到真实 tool evidence 生产点：
  - `KernelToolBridge` 在产出 file artifact / shell replay evidence 后，会直接生成正式 `result_items`
  - `query_execution_runtime` 的 evidence sink 会把这份结果写入 `query_runtime_state.tool_use_summary`
  - session snapshot 会同步持久化同一份 `query_runtime_state`
- 当前正式 `result_items` 字段已支持：
  - `ref`
  - `kind`
  - `label`
  - `summary`
  - `route`
- 当前已真实直出的结果类型：
  - file artifact -> `文件`
  - shell replay -> `回放`
  - browser screenshot artifact -> `截图`
  - browser verified download artifact -> `文件`
- `ConversationCompactionService` 仍保留保守派生兜底，但它已退回 fallback 角色；正式优先级改为“真实 evidence 生产侧直出 > compaction fallback > 前端 fallback”。
- 相关读面 serializer 也已开始统一到 canonical evidence projection，避免不同页面再次把正式 evidence 缩回 count/ref：
  - Runtime Center task detail / schedule detail
  - goal detail
  - routine evidence hydration
  - workflow preview / workflow run detail
  - industry runtime evidence aggregation
- 当前 fresh verification：
  - backend：
    - `python -m pytest tests/app/test_learning_api.py tests/app/test_runtime_reset.py tests/app/test_system_api.py tests/app/test_industry_draft_generator.py tests/app/test_goals_api.py tests/app/test_runtime_query_services.py -q`
    - `python -m pytest tests/kernel/test_learning_workflow_patch.py tests/kernel/test_tool_bridge.py -q`
    - `python -m pytest tests/app/test_runtime_center_api.py tests/app/test_runtime_center_events_api.py tests/app/test_workflow_industry_optimization_scenario.py tests/app/test_workflow_templates_api.py -q`
    - `python -m pytest tests/routines/test_routine_service.py tests/app/runtime_center_api_parts/detail_environment.py -q`
    - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_predictions_api.py tests/app/test_cron_executor.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_self_evolution_engine_e2e.py tests/industry/test_optimization_closure_projection.py -q`
    - 结果：`351 passed`
  - live：
    - `COPAW_RUN_LIVE_AGENT_ACTION_SMOKE=1 python -m pytest tests/app/test_live_agent_action_smoke.py -q -rs`
    - `COPAW_RUN_LIVE_OPTIMIZATION_SMOKE=1 python -m pytest tests/app/test_live_optimization_smoke.py -q -rs`
    - 结果：`2 passed`
  - console：
    - `npm --prefix console test -- src/pages/Chat/runtimeSidecarEvents.test.ts src/pages/Chat/index.results.test.tsx src/pages/RuntimeCenter/index.test.tsx src/pages/RuntimeCenter/viewHelpers.test.tsx src/pages/AgentWorkbench/WorkspaceTab.test.tsx src/pages/AgentWorkbench/sections/detailPanels.test.tsx`
    - 结果：`37 passed`
    - `npm --prefix console run build`
    - 结果：通过

---

## 1.3.3 `2026-04-15` live 烟雾前置诊断补充

- `tests/app` 分块回归已跑通；本轮新增暴露出的失败均为 bootstrap / execution wiring 测试桩合同漂移，已对齐当前正式合同。
- 默认被 skip 的两条 opt-in live smoke 已补“前置条件真相分流”：
  - `test_live_agent_action_smoke.py` 会先检查 chat writeback decision model 是否真的可用
  - `test_live_optimization_smoke.py` 会先检查 curated remote skill discovery 是否真的可用
- 当前 live 阻塞已明确归因为环境前提，而不是主链代码断裂：
  - 浏览器动作 live smoke：缺可用 chat decision model / fallback model slot
  - 远程技能优化 live smoke：SkillHub curated discovery 当前不可达
- `/system/self-check` 已新增两类正式诊断：
  - `provider_resolution`
  - `chat_decision_model`
  - `remote_skill_discovery`
- 目标是把“缺模型 / 缺远程发现”这类外部前提提前暴露在正式读面，而不是运行到中途才以业务失败形式爆出。

---

## 1.3.4 `2026-04-15` live chat writeback 抖动收口

- operator 指出“模型连接本身是通的”后，已补做沙箱外直连与原始 decision probe：
  - 结论不是 provider 不通，而是 chat writeback decision model 在真实上游链路里存在显著流式抖动；
  - 同一条浏览器截图指令的原始 decision 调用，实测既可能在 `25s` 左右成功，也可能在 `100s+` 成功，且偶发在 `300s` 内仍超时。
- 因此，本轮没有继续把问题误归因为“模型不可用”，而是对正式前门做了窄托底：
  - `query_execution_writeback` 默认 decision timeout 提高到 `300s`
  - 对“明确浏览器/桌面执行指令”新增 heuristic `direct-execution-request` 判定
  - 当 model timeout / unavailable，或把这类明确执行指令保守误判成 `chat` 时，正式退回 heuristic execute-task 判定，而不是整条主链中断
- 该托底当前只覆盖明确执行面，不放宽泛化写回：
  - 典型命中：`Use the mounted browser capability right now. Open ... and save a screenshot ...`
  - 非浏览器/桌面明确执行请求仍保留原有 timeout / unavailable 传播语义
- 当前已完成 fresh verification：
  - `python -m pytest tests/kernel/test_chat_writeback.py -q` -> `11 passed`
  - `python -m pytest tests/app/test_system_api.py -q` -> `14 passed`
  - `python -m pytest tests/kernel/test_turn_executor.py -q -k timeout` -> `1 passed`
  - `python -m pytest tests/kernel/test_main_brain_orchestrator.py -q -k timeout` -> `1 passed`
  - `COPAW_RUN_LIVE_AGENT_ACTION_SMOKE=1 python -m pytest tests/app/test_live_agent_action_smoke.py -q -rs` -> `1 passed`
  - `COPAW_RUN_LIVE_OPTIMIZATION_SMOKE=1 python -m pytest tests/app/test_live_optimization_smoke.py -q -rs` -> `1 passed`

---

## 1.3.5 `2026-04-15` learning patch 前门治理补充

- `LearningService.create_patch(...)` 与 `POST /learning/patches` 现在会对 patch 创建合同 fail closed：
  - 只有 `workflow_patch` 允许声明 `patch_payload.target_surface`
  - 且当前唯一合法值是 `workflow_template`
  - `file_path / repo_path` 这类源码或文件系统目标字段不再允许进入正式 learning patch 写链
- 这次收口的目标不是新增“源码 patch”能力，而是明确学习层正式边界：
  - 学习层只能产标准 patch 对象
  - 当前真实副作用边界仍是 profile / role / capability / plan / workflow-template
  - 任何试图借 `/learning/patches` 塞入源码/文件系统意图的 payload 都应在前门直接 `400`
- 当前 fresh verification：
  - `python -m pytest tests/app/test_learning_api.py -q` -> `21 passed`
  - `python -m pytest tests/kernel/test_learning_workflow_patch.py -q` -> `2 passed`
  - `python -m pytest tests/app/test_workflow_industry_optimization_scenario.py -q` -> `1 passed`
  - `python -m pytest tests/industry/test_optimization_closure_projection.py -q` -> `1 passed`

---

## 1.4 `2026-04-05` Group F 闭环证明口径纠偏（必读）

- `collect-only` 只证明“被收集到哪些测试”，**不证明行为通过**、不证明“默认回归闭环”。
- 当前已确认的收集边界示例（历史命令口径）：
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py --collect-only -q`
  - 输出：`61 tests collected`。
  - 其中任何 `-k` 过滤切片（例如 `26 passed`）都只能算 focused slice，不可写成“整链默认闭环”。
- `tests/providers/test_live_provider_smoke.py` 与 `tests/routines/test_live_routine_smoke.py` 属于 **opt-in live smoke**：
  - 默认环境下可被 skip。
  - `skipped` 只代表前置条件未开启，不代表默认 CI 已证明 live 可靠性。
- 本文档后续所有“已闭环/已验证”叙述必须同时注明：
  - 是否为默认回归（默认命令直接执行）
  - 是否为 gated live smoke（需显式环境变量）
  - 是否仅为 collect-only / focused slice

---

## 1.1 `2026-03-25` 硬切维护窗口说明

- 当前仓库已进入一次性 `hard-cut autonomy rebuild` 维护窗口，允许短期停机与阶段性功能不完整。
- 本窗口的最高约束不再是兼容历史数据，而是切掉旧主链、旧真相源与无边界兼容逻辑。
- 当前唯一目标链以
  `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`
  为准。
- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md` 只作为 runtime-first 补充视角，不替代上述正式主链。
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md` 只作为 execution-side computer runtime 补充视角；它规定“执行 agent 持有 computer body”，但不替代正式主链与正式 state object vocabulary。
- 旧“把 `goal/task/schedule` 当主脑规划主线”的路径不再视为未来兼容目标；但当前活代码里的 `GoalRecord / ScheduleRecord` 仍承担执行阶段与自动化节奏职责，不能按“整组无脑删除”理解。
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
- 这轮最重要的工程方向，不再是继续堆新模块，而是把“主脑长期自治 + 单行业闭环 + 执行位回流 + staffing 可见化 + 主脑综合闭环”硬切成唯一运行事实，并删除旧“以 `goal/task/schedule` 充当主脑规划入口”的路径。

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
- `2026-04-02` 补充：聊天流 contract 已锁成“同一控制线程、同一 SSE、先回复后 sidecar”。`/runtime-center/chat/run` 会先流出 reply tokens，再把 main-brain commit sidecar 挂回同一条正式主脑控制线程；前台不再引入第二聊天窗口、第二轮询路由，也不恢复 `task-chat:*`。`agent-chat:*` 如仍出现在后台绑定/执行 artifact 中，也不再属于前台可直接打开的正式聊天会话。
- `2026-04-02` 补充：主脑 phase-2 commit 状态现已正式持久化进 session snapshot 的 `main_brain.phase2_commit`。`RuntimeConversationFacade` 会在同一控制线程重载时把它回填到 conversation `meta.main_brain_commit`，因此确认中/已提交状态不会因为刷新聊天页而丢失。
- `2026-04-12` 补充：`Runtime Center` 主脑驾驶舱已新增正式 `main_brain.cockpit` 合同，并开始作为普通用户主读面优先来源。当前正式字段至少包括 `card / summary_fields / morning_report / evening_report / trend / trace / approvals / stage_summary / agents[]`；前端在存在 `main_brain.cockpit` 时优先直读这些正式字段，缺失时才回退旧派生。与此同时，`KernelTurnExecutor auto` 与 `MainBrainOrchestrator` 对显式 `requested_actions` 已统一优先物化 request-scoped intake contract，不再因为测试桩或注入 resolver 返回 `None` 而意外跌回 chat writeback decision model。当前验证已更新为：`C:\Python312\python.exe -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q` -> `97 passed`；`python -m pytest tests/kernel/test_main_brain_intake.py tests/kernel/test_main_brain_orchestrator.py tests/kernel/test_turn_executor.py -q` -> `71 passed`；cockpit 前端定向测试与 `console` build 已在本轮主脑驾驶舱收口时通过。
- `2026-04-16` 补充：`Runtime Center` 主脑/职业 agent 驾驶舱已继续扩正式 `trace` 合同，并在前端把 `追溯` 固化为 `统计` 后的固定 tab。当前 `main_brain.cockpit` 与 `agents[]` 均新增 `trace[]`，字段为 `timestamp / level / message / route`；后端 `overview_cards.py` 现在会从 `assignment / report / evidence / patch / growth / approval` 正式对象生成今天的追溯日志流，前端不再硬拼卡片内容。UI 口径已收死为“像后端日志的一行一条，旧日志在上、新日志在下”，主脑和职业 agent 共用同一读面形态。当前验证：`PYTHONPATH=D:\\word\\copaw\\.worktrees\\runtime-center-trace-tab\\src;D:\\word\\copaw\\.worktrees\\runtime-center-trace-tab python -m pytest tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_main_brain_route_exposes_human_cockpit_trace_contract tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_human_cockpit_trace_is_chronological_and_replays_key_events -q -p no:cacheprovider` -> `2 passed`；`npm --prefix console test -- src/pages/RuntimeCenter/AgentWorkPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx` -> `14 passed`。
- `2026-04-17` 补充：`Runtime Center` 的 `日报` 已从系统字段列表正式切到 AI 生成的固定结构中文汇报。当前 `main_brain.cockpit` 与 `agents[]` 的 `morning_report / evening_report` 已统一返回 `kind / title / status / sections[] / generated_at / error`，其中 `早报` 固定为 `今天要做什么 / 重点先做什么 / 风险提醒`，`晚报` 固定为 `今天完成了什么 / 产出了什么结果 / 明天继续什么`；前端 `Runtime Center` 已删除本地日报 fallback，不再自己拼 `items[]`，模型失败时只显示模块错误块。与此同时，runtime provider 已新增统一模型调用层，正式收口 `120s` 等待反馈、最多 `3` 次重试、中文输出校验、结构化返回校验、失败事件记录与全局健康升级；Buddy onboarding contract compile、chat writeback decision、industry draft generation 已接入同一层，`RuntimeHumanCockpitPayload` 也已新增 `model_status` 供前端显示系统级模型故障。对应 design/plan 已补入 `docs/superpowers/specs/2026-04-17-runtime-center-ai-daily-report-and-unified-model-call-design.md` 与 `docs/superpowers/plans/2026-04-17-runtime-center-ai-daily-report-and-unified-model-call-implementation-plan.md`。当前 fresh verification：`python -m pytest tests/providers/test_runtime_provider_facade.py tests/kernel/test_buddy_onboarding_reasoner.py tests/kernel/test_chat_writeback.py tests/app/test_industry_draft_generator.py -q` -> `27 passed`；`python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q` -> `102 passed`；`cmd.exe /c npm --prefix console test -- src/pages/RuntimeCenter/AgentWorkPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx` -> `19 passed`。
- `2026-04-18` 验收补充：按 `UNIFIED_ACCEPTANCE_STANDARD.md` 继续补跑了 `L3` 真实链路 smoke，而不再只停在 focused regression。当前通过的 `L3` 证据包括：`python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q` -> `16 passed`，覆盖 `/runtime-center/chat/run`、canonical runtime e2e、operator/runtime e2e 与 Runtime Center 读面主链；`python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "runtime_center or runtime_center_overview or canonical_flow or operator or chat_run or long_run_smoke"` -> `4 passed, 7 deselected`，补到了 Runtime Center cockpit、overview、chat-run 相邻 smoke 切片。此前这组扩面 smoke 的失败根因不是本轮 `日报 + 统一模型调用` 数据合同断层，而是旧断言仍在匹配已退役的英文文案；现已按当前中文/语义稳定口径收口。当前因此可以诚实声明：本轮 `日报/统一模型调用` 已过 `L1 + L2 + 选定范围的 L3`，但仍未覆盖 `L4` long soak，也不应外推成“整仓所有 runtime smoke 全部通过”。
- `2026-04-18` 验收补充：`phase-next` 扩面 smoke 与选定范围 `L4` 自动 soak 已继续补跑。当前更宽的 `L3` 证据包括：`python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q` -> `11 passed`；长链切片 `python -m pytest tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_industry_long_run_smoke_keeps_followup_focus_and_replan_truth_contract tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_industry_long_run_smoke_keeps_handoff_human_assist_and_replan_on_one_control_thread_contract tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_long_run_harness_smoke_covers_runtime_chain_and_multi_surface_continuity_contract -q` -> `3 passed`；相邻主链组合 `python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q` -> `27 passed`。这轮唯一新发现的断点仍然不是运行主链断层，而是 long-run harness 里残留的旧英文 handoff 断言，现已对齐到当前中文治理原因。与此同时，已按固定矩阵完成选定范围 `L4` 自动 soak：连续 `3` 轮执行 `python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`，结果分别为 `27 passed in 207.05s`、`27 passed in 221.28s`、`27 passed in 193.21s`；壁钟耗时分别为 `209.93s / 224.32s / 196.10s`。对应计划与执行记录已写入 `docs/superpowers/plans/2026-04-18-phase-next-long-soak-plan.md` 以及 acceptance ledger `accept-016 / accept-017`。当前因此可以更准确地声明：本轮 `日报/统一模型调用` 已过 `L1 + L2 + 更宽的 L3 + 选定范围自动 L4`，但这仍不等于整仓 full-repo soak，也不等于 live external-provider soak。
- `2026-04-04` 补充：六缺口收口在当前隔离 worktree 内继续完成第二轮真收口，不再只停在“typed facade 包一层”。`Runtime Center` 后端正式前门现只剩 `/runtime-center/surface`；旧 `/overview`、`/main-brain` 只在断层测试里保留 `404` 断言。前端 `Runtime Center` 事件刷新已按 `cards / main_brain` section 增量刷新，未知 topic 不再回退成整页 full reload；侧边栏里的 `agents` 顶层入口已物理删除，`/agents` 只作为 runtime-center drill-down route 保留。provider/runtime bootstrap 现显式装配 `runtime_provider + provider_admin_service`，formal runtime/kernel 链已不再调用无参 `get_runtime_provider_facade()`；`ProviderManager.get_instance()` 只剩 CLI/live-smoke compatibility 路径。与此同时，`Runtime Center` 自动化/恢复读面已改用正式 snapshot contract：`ActorSupervisor.snapshot()`、`AutomationTaskGroup.overview_snapshot()`、`RuntimeCenterAppStateView.resolve_recovery_summary()` 已成为 canonical read seam，`overview_cards.py` 不再读取 `_loop_task / _agent_tasks` 这类私有字段。`System` overview 也已去掉 recovery 事实对象重复展示，只保留维护路由与 `recovery_source`。本轮验证：`python -m pytest tests/providers/test_runtime_provider_facade.py tests/agents/test_model_factory.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_actor_supervisor.py tests/app/test_local_models_api.py tests/app/test_models_api.py tests/app/test_ollama_models_api.py tests/app/test_phase2_read_surface_unification.py tests/app/test_runtime_center_api.py tests/app/test_system_api.py -q` -> `252 passed`；`python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q -k "surface or host_twin_summary or runtime_center or overview or main_brain or provider or bootstrap or recovery"` -> `26 passed`；`npm --prefix console run build` -> 通过；`npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/routes/resolveSelectedKey.test.ts src/layouts/Sidebar.test.tsx src/pages/Settings/System/index.test.tsx` -> `16 passed`。
- `2026-04-05` runtime 三项收口补充：第一，`/runtime-center/chat/run` 已有真实 canonical e2e，能从聊天前门一路闭到 `writeback -> backlog -> assignment -> real fixed-SOP -> evidence -> terminal report`，并把 `work_context_id` 沿同一控制线程写回；第二，`KernelTurnExecutor.handle_query(...)` 的 command/query 两条分支已收成同一套 admission + terminal closeout helper，`waiting-confirm` 不会误 complete，`asyncio.CancelledError` 与“取消语义 runtime error”现在都会统一写成 `cancelled`，不再出现前端显示取消、内核却记失败的分叉；第三，`cron / automation` 已补上共享 launch contract，新增 `runtime_launch_contract.py` 统一生成 durable coordinator 元数据，cron agent request/request_context 与 automation loop payload 现在都会带上同源 launch fields，workflow 既有 `workflow-run` coordinator 合同继续保留。focused 验证：`python -m pytest tests/kernel/test_turn_executor.py tests/app/test_runtime_lifecycle.py tests/app/test_cron_executor.py tests/kernel/test_main_brain_orchestrator_roles.py -q` -> `87 passed`；相邻主链验证：`python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_workflow_templates_api.py::test_workflow_template_service_launch_materializes_run tests/fixed_sops/test_service.py::test_fixed_sop_service_records_host_snapshot_in_run_and_evidence -q` -> `6 passed`。
- `2026-04-04` 设计补充：外部能力吸纳现已形成 donor-first 正式设计与落地计划，不再默认把“主脑自己写 skill”当成长主路线。新增 `docs/superpowers/specs/2026-04-04-external-capability-assimilation-architecture.md` 与 `docs/superpowers/plans/2026-04-04-external-capability-assimilation-implementation-plan.md`，正式收口了以下口径：1) CoPaw 自身只掌握 truth/runtime/risk/evidence/lifecycle，不再追求自写所有功能；2) 外部项目、skill、MCP、browser/desktop/document adapter、provider/runtime helper 都作为 donor 供给面进入同一 `discover -> evaluate -> candidate -> scoped trial -> evidence -> lifecycle decision` 主链；3) discovery 采取 `gap/performance/periodic/opportunity` 四模，且按 `primary -> mirror -> fallback` 的单次单活 source chain 执行，source 故障只允许降级 discovery，不允许拖垮 runtime；4) 多源发现必须先做 donor/package/lineage 去重再扩 candidate；5) `local_authored` 降级为 fallback-only/gap-closure-only，而不是主增长路线；6) donor 组合、trust memory、retirement 和 portfolio compaction 进入后续正式施工范围。
- `2026-04-04` 设计补充：下一轮纪律收口 spec 已新增 `docs/superpowers/specs/2026-04-04-next-round-discipline-closure-spec.md`。该文档把当前最值得继续借鉴 `cc`、并与 donor-first 架构直接耦合的 8 个 closure package 正式收口为下一轮范围：1) query runtime entropy contract；2) discovery source chain；3) multi-source deduplication and donor normalization；4) read concurrent / write serialized writer contract；5) unified child-run shell；6) MCP lifecycle discipline；7) skill/package metadata discipline；8) portfolio governance and hotspot cooling。该文档同时明确了 `P0/P1/P2` 推荐顺序、验收标准与非目标，避免后续施工再回到“重开聊天前链路”或“继续无限扩功能”的旧路径。
- `2026-04-05` donor 现实边界更正：从今天起，`TASK_STATUS` 里与 donor-first 相关的“已完成”口径必须拆成三层，不允许再混写。`已进主线代码基线` 只代表对象/服务/read-model/测试存在；`市场子链 live 可用` 只代表具体 product surface 已实测通过；`完整外扩闭环` 则必须同时满足真实发现、真实安装、真实使用三条链。此前把第一层写成第三层的记录，现全部按本条纠偏理解。
- `2026-04-05` 设计补充：已新增并补全 `docs/superpowers/specs/2026-04-05-main-brain-buddy-companion-design.md`，正式定义 `Buddy = 主脑唯一对外人格外壳` 的 companion 方向。当前口径已收死为：1) Buddy 不是独立 agent，不是第二主脑，不拥有独立记忆或独立规划链；2) 聊天页是 Buddy 的主场，主脑页只作为长期目标/当前任务/成长状态的 cockpit；3) 默认人类读面只显示 `最终目标 + 当前任务`，复杂计划树和执行位拆解默认隐藏；4) 执行位结果统一回流主脑后再由 Buddy 转述，不再让前台重新退化成多 agent 拼盘；5) Buddy 允许采用 `cc` 的可爱像素/轻伙伴外观 donor，但只能借外观骨架、气泡和互动机制，不能照搬 `/buddy` 命令、`companion_intro` 第二说话者合同或 config-only truth；6) Buddy 必须具备游戏化成长属性和外观/语气/主动性进化，但这些属性只能作为主脑正式记忆、互动历史与执行回流的派生投影，不能成长为第二真相源；7) 首次进入系统时，旧 `industry bootstrap` 不应再作为人的第一入口，正式方向现已被 `2026-04-11` collaboration contract cutover 收死为 `基础身份建档 -> 协作合同直填 / compile -> 2~3 个候选大方向 -> 用户确认唯一主方向 -> 生成初始规划 -> 首次聊天内命名 Buddy`，旧“最多 9 问澄清对话”口径已退役；8) 第二轮补充已把 Buddy 状态与外观成长进一步收死：正式区分 `LifecycleState / PresenceState / MoodState` 三类状态家族，定义 `Seed -> Bonded -> Capable -> Seasoned -> Signature` 五段进化形态，明确亲密度/契合度/知识值/技能值/愉快度等属性的派生规则，并把聊天页展开面板收口为 `Identity / Relationship / Growth / Capability / Current Bond Context` 五个正式块；9) 第三轮补充已把 implementation-facing 细节补到位：新增属性公式分层、外观资源映射策略、`BuddyPresentation / BuddyGrowthProjection` 后端对象/API 接线建议，以及旧 `industry-profile-v1` 首入口向新 Buddy onboarding 的断层迁移表。后续实现应按 `buddy onboarding replacement -> chat-first buddy shell -> buddy growth projection -> evolution -> main-brain cockpit alignment -> state/evolution calibration` 顺序推进。
- `2026-04-05` 计划补充：已新增 `docs/superpowers/plans/2026-04-05-main-brain-buddy-companion-implementation-plan.md`。该计划已把 Buddy 方向正式拆成 9 个可施工任务：`formal buddy truth/projection models -> onboarding backend -> projection service -> buddy-first first entry -> chat-first buddy shell -> first-chat naming -> growth/evolution mapping -> main-brain cockpit alignment -> docs/verification sync`，并显式列出了推荐新文件、现有改动文件、测试文件和逐步验收命令。Buddy 方向后续不应再停留在概念讨论，默认进入计划驱动施工。
- `2026-04-05` 执行边界补充：Buddy 施工应被严格理解为“在现有主脑/runtime/human-assist 基础上的增量升级”，不是从零重做主脑或另起第二套任务系统。当前已有 `HumanAssistTask`、聊天提交 `submit_human_assist`、聊天侧人类协作面板和主脑执行前门都应保留为后台正式真相；本轮真正要收的是前台口径与入口 ownership：人类同伴任务默认通过 Buddy 聊天发起、验收、追问和恢复，旧单独任务模块/页面只允许退成 supporting detail/history/read surface，不再当主交互面。
- `2026-04-05` Buddy implementation 补充：`Task 1-9` 当前已在隔离 worktree `buddy-companion-impl` 全部落地完成。后端已新增正式 `models_buddy / repositories_buddy / buddy_onboarding_service / buddy_projection_service / buddy_routes`，并将 Buddy onboarding、direction confirmation、free-form naming、chat surface、runtime cockpit summary 接入现有 runtime bootstrap；前端已完成 `BuddyOnboarding` 首入口替换、聊天页常驻 Buddy shell + 展开面板、首次真实聊天命名提示、成长/进化映射、`Runtime Center` 主脑 cockpit 的 compact Buddy summary，以及旧 `/industry` 首入口 ownership 的降级。当前验证结果：`PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q` -> `10 passed`；`npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/buddyEvolution.test.ts src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/routes/resolveSelectedKey.test.ts` -> `35 passed`；`npm --prefix console run build` -> 通过。下一步如果无新设计变更，应进入合并、主线验证与后续 live 调优，而不是继续停在 Buddy 方案讨论。
- `2026-04-05` Buddy 断层修复补充：上一轮 Buddy cutover 之后，实际代码仍存在 4 个实质断层：1) `build_chat_surface()` 在多 profile 下默认取最新 profile，前台存在串人风险；2) `BuddyProjectionService` 在生产装配里未接 execution-core `current_focus` resolver，当前任务/why-now 只能退回 human-assist fallback；3) Buddy 成长属性只停留在 onboarding transcript，真实聊天/陪跑不会持续回写关系成长；4) onboarding 确认主方向后未正式生成 `lane/backlog/cycle/assignment` 成长骨架。当前隔离 worktree 已完成对应收口：`BuddyProjectionService` 在多 profile 时必须显式 `profile_id`，聊天页 / onboarding / Runtime Center buddy summary 已统一透传并持久化 `buddy_profile_id`；`HumanAssistTaskRecord` 与 human-assist service 现已带 `profile_id`，Buddy fallback 不再把无 profile 协作任务误配给任意 profile；runtime bootstrap 已新增 `buddy_current_focus_resolver`，生产 `BuddyProjectionService` 正式优先消费 execution-core `current_focus`，再回退到 buddy instance assignment/backlog；`BuddyOnboardingService` 已开始在确认主方向后物化 `buddy:{profile_id}` 行业实例、lane/backlog/cycle/assignment scaffold，并增加 `record_chat_interaction(...)` 把真实聊天频次、愉快度、强陪跑次数和经验值持续回写到 `CompanionRelationship`。本轮 focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py tests/app/test_buddy_runtime_bootstrap.py -q` -> `13 passed`；`npm --prefix console run test -- src/runtime/buddyProfileBinding.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/runtimeTransport.test.ts src/pages/RuntimeCenter/useRuntimeCenter.test.ts` -> `34 passed`；`npm --prefix console run build` -> 通过。当前 Buddy 仍未补 donor 级完整像素资产迁移，但 profile 作用域、current-focus 接线、关系成长回写和成长 scaffold 这四条 blocker 已收死。
- `2026-04-05` Buddy persona / contract / visible-chain 收口补充：在上一轮数据闭环之后，又继续补齐了 5 个和 spec 对齐的正式缺口。1) Buddy 已正式进入主脑 prompt/persona 生成链：`main_brain_chat_service` 现在会在 pure-chat system prompt 之后附加 Buddy persona block，`query_execution_prompt` 也会把 `buddy_name / human identity / primary direction / current task / why now / single next action / companion strategy` 注入 runtime appendix，明确要求前台保持 Buddy 为唯一对外人格，而不是重新暴露多 agent 内部结构；2) `BuddyPresentation` 正式补上 `single_next_action_summary` 与 `companion_strategy_summary`，后端 projection、Runtime Center buddy summary、聊天页 Buddy 面板都已统一消费这两个字段，不再只停在 `current_goal / current_task / why_now` 三件套；3) `CompanionRelationship` 中的 `effective_reminders / ineffective_reminders / avoidance_patterns` 不再只是静态存储，Buddy projection 现已根据这些关系记忆派生陪伴策略 summary，使关系记忆开始真正影响陪伴表达；4) spec 要求的 `console/src/assets/buddy/base|parts|effects|forms/*` 资产命名空间已正式落位，`buddyAvatar / buddySpriteAssets` 已切到新资产目录；5) Buddy 触达链路里的可见英文/混码已在 `BuddyOnboarding`、聊天页 `BuddyCompanion / BuddyPanel / buddyPresentation`、Runtime Center 的 compact buddy summary 上收成正常中文。fresh verification：`PYTHONPATH=src C:\Python312\python.exe -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_onboarding_service.py -q` -> `48 passed`；`cmd /c npm --prefix console run test -- src/assets/buddy/assetNamespace.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/buddyAvatar.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx` -> `35 passed`；`cmd /c npm --prefix console run build` -> 通过。当前 Buddy 的正式边界应理解为：系统继续负责规划、拆解、执行与主链推进，人类只承接系统无法替代的现实动作；`HumanAssistTask` 保留为后台正式真相与 exception path，不再误用为前台主交互任务系统。
- `2026-04-04` 执行口径补充：donor-first 外扩主链与下一轮纪律收口不是“两条互相独立的串行工程”。当前正式口径已写死为：第一波外扩必须与 `P0` 三条纪律一起推进，也就是 `external assimilation spine + query runtime entropy contract + discovery source chain + multi-source dedup/donor normalization` 同波落地；不能先把所有铁律做完再外扩，也不能先把外扩放量再补这三条。后续 `P1/P2` 再按 writer contract / child-run shell / MCP lifecycle / metadata / portfolio cooling 继续收口。
- `2026-04-04` 边界更正：`docs/superpowers/specs/2026-04-03-autonomous-capability-evolution-loop-design.md` 与配套 implementation plan 现已显式改回 donor-first 平台口径，不再允许被理解为“系统内置写 skill 是主增长路线”。当前正式规则写死为：1) CoPaw 是 truth/runtime/risk/evidence/lifecycle 底座，不是 skill 工厂；2) 外部成熟 donor、MCP、adapter、runtime helper 是默认增长路径；3) 复用现有健康 artifact/version 优先于重新生成；4) 本地 self-authored artifact 仅为 fallback-only，用于 donor-first 路径仍无法补洞时的薄胶水或私有行业补丁；5) 即使进入本地 authored 路径，也必须落回同一 `CapabilityCandidateRecord -> trial -> lifecycle decision -> replace/rollback/retire` 主链，不享受本地特权。
- `2026-04-04` 计划补充：为避免后续 capability evolution 施工再次滑回“先写 skill 再说”，现已新增 `docs/superpowers/plans/2026-04-04-donor-first-capability-evolution-priority-plan.md` 作为纠偏后的下一轮施工优先级文档。该计划明确要求下一波实现按 `baseline import + donor-first candidate truth -> donor adoption/reuse resolver -> MCP-native candidate form -> trial verdict/protected lifecycle -> Runtime Center visibility + drift re-entry` 的顺序推进，并把本地 authored artifact 明确限制为 donor-first 失败后的 fallback 路径。
- `2026-04-05` donor 当前状态总括：本节 donor-first 记录必须按“当前总结 > 历史施工账本”读取。`2026-04-04` 到 `2026-04-05 donor 真实缺口清单` 这些条目保留为历史中间态，不再代表当前未完成项；当前权威状态以后续 3 条为准：`donor live gap closure`、`donor GitHub project live closure`、`donor Python project contract`。按当前实测，已 live 打通的范围是：`SkillHub/curated/official MCP registry` 市场子链、GitHub `SKILL.md` 仓库前门，以及符合当前 `Python/GitHub/isolated-venv` 合同的开源项目 donor；当前边界也同步写死为：这不等于“任意语言、任意构建系统、任意仓库都已自动适配”。
- `2026-04-04` 施工补充：donor-first 外部能力吸纳的第一批正式对象和主读面已进主线，但这一批完成度应严格理解为“对象层 / 持久化层 / Runtime Center 读面已落”，而不是“真实外部能力供给已经全量打通”。`CapabilityCandidateRecord` 现已正式携带 `donor_id / package_id / source_profile_id`；state 层新增了 `CapabilityDonorRecord / CapabilityPackageRecord / CapabilitySourceProfileRecord / CapabilityDonorTrustRecord` 以及 `CapabilityDonorService / CapabilityPortfolioService`，candidate 落库时会同步归一 donor/package/source truth。Runtime Center 现已新增 `/runtime-center/capabilities/donors` 与 `/runtime-center/capabilities/source-profiles` 读面，`governance/status` 和 `capability-optimizations` 也开始返回正式 `portfolio` 诊断。当前定向验证已通过：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/predictions/test_skill_trial_service.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_system_api.py tests/app/test_capability_market_api.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`，合计 `172 passed`。这条记录只表示 donor/source/portfolio 的 state truth 与 read-model 已进入正式主链；它不表示 autonomous scout、opportunity radar、通用开源 donor 搜索、真实 source-chain provider 和 live 安装质量已经全部闭环。
- `2026-04-04` 收口补充：donor-first 第二波 `P1/P2` 的代码侧收口主要完成了 lifecycle mutation 统一和 portfolio/discovery read-model 去重，不应再表述为“整体 donor-first 已完成闭环”。`runtime_center_actor_capabilities.py`、`industry/service_team_runtime.py`、`predictions/service_recommendations.py` 现已统一改走 `system:apply_capability_lifecycle`，actor/runtime-center/industry bootstrap 的 capability assignment 不再继续生成新的 `system:apply_role` mutation 任务；`RuntimeCenterStateQueryService` 与 `PredictionService` 自己复制的一套 portfolio/discovery 统计逻辑也已删除，正式统一委托 `CapabilityPortfolioService`。对应 focused verification：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/app/test_runtime_center_actor_api.py tests/predictions/test_skill_candidate_service.py tests/app/test_predictions_api.py tests/app/test_runtime_center_events_api.py -q` -> `45 passed`；相邻主链回归：`tests/app/test_capability_market_api.py` -> `27 passed`、`tests/app/industry_api_parts/runtime_updates.py` -> `40 passed`、`tests/app/industry_api_parts/bootstrap_lifecycle.py` -> `34 passed`、`tests/app/runtime_center_api_parts/overview_governance.py` -> `81 passed`、`tests/kernel/test_query_execution_runtime.py` -> `21 passed`。这条记录仅表示 `P1/P2` 中与 lifecycle/read-model 相关的代码路径已经落地；它不表示 live donor discovery/source chain/自治 scout 已经完成。
- `2026-04-04` 实施补充：第一波 donor-first 外扩 + `P0(A/B/C)` 已把 discovery/source-chain/dedup/entropy contract 的对象与写链落到主线，但 runtime 真实外扩能力仍然存在关键缺口。当前仓库已新增 `src/copaw/discovery/models.py`、`src/copaw/discovery/source_chain.py`、`src/copaw/discovery/deduplication.py` 与 `src/copaw/state/donor_source_service.py`，并让 `CapabilityCandidateService` 能导入 normalized discovery hits，把 `canonical_package_id / source_aliases / equivalence_class / capability_overlap_score / replacement_relation` 落到正式 candidate truth；`SkillTrialService` 与 `SkillLifecycleDecisionService` 也已接上 attribution/retirement 字段。`query_execution_runtime` 与 `conversation_compaction_service` 已补上 donor/trial-heavy turn 的 entropy contract，`Runtime Center` 也已新增 `/runtime-center/capabilities/portfolio` 与 `/runtime-center/capabilities/discovery`。fresh verification：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/state/test_capability_donor_truth.py tests/state/test_donor_source_service.py tests/discovery/test_source_chain.py tests/discovery/test_deduplication.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/app/test_predictions_api.py tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_bootstrap_helpers.py -q` -> `176 passed`；邻接长链回归：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py tests/app/test_system_api.py tests/app/test_capability_market_api.py tests/app/test_predictions_api.py -q` -> `64 passed`。这条记录现在必须配合一个现实边界理解：`_execute_runtime_discovery_action()` 仍为空实现、`OpportunityRadarService` 在 runtime bootstrap 中仍是 `feeds={}`、默认 source profile 里仍含占位镜像地址，因此这部分只能算“source-chain/dedup/entropy contract 代码骨架和对象真相已落”，不能算“真实自治发现已经打通”。
- `2026-04-04` `P1` 续补：MCP / donor 安装后的“正式采用”链又继续收口了一刀，不再让 capability market 与 industry bootstrap 在装完 donor 后直接把采用语义写成 `system:apply_role`。仓库已新增 `src/copaw/capabilities/lifecycle_assignment.py` 作为共享 lifecycle-assignment builder：它会先从 `agent_profile_service` 解析当前 capability surface、role/seat 上下文与 `session_overlay_capability_ids`，再生成正式 `system:apply_capability_lifecycle` payload。`/capability-market/*install*` 的 target-agent assignment 与 `industry/service_activation.py` 的 install-plan assignment 现在都会统一改走这条 lifecycle contract；`replace` 模式下会显式生成 `replacement_target_ids`，但会保留 session overlay，不再把临时 `mcp_scope_overlay`/seat overlay 一起误删。与此同时，`CapabilityDiscoveryService` 的 donor governance path 也已从 `install/create -> apply_role` 收紧为 `install/create -> apply_capability_lifecycle`，避免 MCP/skill donor 继续沿旧直觉走“装上/连上=正式采用”。定向验证：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/app/test_capability_market_api.py -q` -> `27 passed`；`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "auto_gap_closure_installs_desktop_mcp_template_and_assigns_target_role or replace_mode_swaps_seat_delta_capabilities" -q` -> `2 passed`；`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/app/industry_api_parts/runtime_updates.py -q` -> `40 passed`。
- `2026-04-04` donor-first 外扩剩余工作在代码层已经补上 `src/copaw/discovery/opportunity_radar.py`、`src/copaw/discovery/scout_service.py`、`src/copaw/state/donor_package_service.py`、`src/copaw/state/donor_trust_service.py`，runtime bootstrap/query 也已带上相应 wiring，`RuntimeCenterStateQueryService` 与 `/runtime-center/capabilities/*` 也新增了 `packages / trust / scout` 读面。fresh verification：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/state/test_donor_source_service.py tests/state/test_donor_package_service.py tests/state/test_donor_trust_service.py tests/discovery/test_source_chain.py tests/discovery/test_opportunity_radar.py tests/discovery/test_deduplication.py tests/discovery/test_scout_service.py tests/predictions/test_donor_recommendations.py tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py -q` -> `33 passed`；相邻回归：`$env:PYTHONPATH='src'; C:\\Python312\\python.exe -m pytest tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/app/test_capability_market_api.py tests/app/test_predictions_api.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_bootstrap_helpers.py -q` -> `94 passed`。这条记录现在必须更正为：`opportunity radar / autonomous scout / donor package-trust services / runtime-center donor API` 已进入主线代码基线，但 live runtime 仍未证明 radar/scout 已有真实 feed 和真实外部执行器；截至 `2026-04-05` 的实测，自治 scout 默认运行仍会得到 `0` imported candidates，不能再表述为“剩余闭环已收口”。
- `2026-04-04` donor-first capability evolution priority plan 的 `Task 1 ~ Task 4` 已在对象层、resolver 层、read-model 层大部分落到主线，但不能再表述为“整套 donor-first capability evolution 已完成”。当前仓库新增了 `src/copaw/capabilities/skill_evolution_service.py` 与 `src/copaw/learning/skill_gap_detector.py`：前者把 `reuse_existing_candidate / adopt_registered_package / adopt_external_donor / author_local_fallback` 收成单一 resolver，明确 `healthy reuse -> registered package -> external donor -> local fallback` 的决策顺序，并支持 `mcp-bundle` 这类非 skill-only candidate form；后者把 repeated failure / operator takeover / rollback pressure 统一投影成 formal drift re-entry summary。与此同时，`CapabilitySkillService` 已只在 resolver 明确要求时才 materialize fallback local artifact，`SkillTrialService` 已提供 candidate-level verdict aggregation，`query_execution_runtime` 与 `query_execution_context_runtime` 会继续携带 `donor_id / package_id / source_profile_id / candidate_source_kind / resolution_kind` 等 attribution 到 evidence sink/runtime metadata，`industry/service_runtime_views.py` 与 `RuntimeCenterStateQueryService` 也开始稳定暴露 `current_capability_trial / supply_path / provenance / lifecycle_history / drift_reentry`。当前 focused verification：`python -m pytest tests/test_skill_service.py tests/app/test_capability_skill_service.py tests/predictions/test_skill_trial_service.py tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_events_api.py tests/app/test_capability_market_api.py tests/industry/test_runtime_views_split.py -q` -> `98 passed`；相邻回归：`python -m pytest tests/test_mcp_resilience.py tests/app/test_mcp_runtime_contract.py -q` -> `23 passed`，`python -m pytest tests/predictions/test_skill_candidate_service.py -q` -> `6 passed`。但截至 `2026-04-05` 的真实联网验收，这一轮仍缺少三类 live closure：1) 通用开源 donor / GitHub 搜索未形成真实产品链；2) autonomous scout / opportunity radar 未形成真实外部发现链；3) SkillHub/curated 搜索结果存在大量 bundle 404，安装质量治理未闭环。
- `2026-04-06` autonomous capability evolution loop 收口补充：此前被确认为 partial / unfinished 的 `Phase 6 ~ Phase 9` 已在主线代码补齐，不再停在“对象有了、治理细节没收口”的状态。当前正式落地包括：1) `system:apply_capability_lifecycle` 现在显式要求 `governed_mutation=True`，`replace_existing / retire` 已有 protection gating，`rollback` 会恢复 prior seat truth 并保留 session overlay，外部 install / 本地 authored 完成后也不会绕开 lifecycle 直接 role 激活；2) 新增 `src/copaw/industry/service_capability_governance.py`，`service_team_runtime.py` 与 `service_runtime_views.py` 已正式接入 role/seat/MCP/overlap budget、replacement pressure、protected baseline、install discipline 与 lifecycle 后 recomposition，且不新增第二真相源；3) `RuntimeCenterStateQueryService`、`overview_capability_governance.py`、prediction/drift 相关主链已把 candidate provenance、baseline projection、per-seat/session trial、lifecycle history、replacement lineage、drift re-entry、revision/replace/retire pressure 稳定投影到正式读面；4) `CapabilityPortfolioService` 已补齐 `revision_pressure_count` 等漂移治理统计。当前 focused verification：`PYTHONPATH=src python -m pytest tests/app/test_governed_mutations.py -q` -> `5 passed`；`PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/industry/test_runtime_views_split.py -q` -> `35 passed`；`PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py -q` -> `16 passed`；`PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q` -> `84 passed`；`PYTHONPATH=src python -m pytest tests/app/test_runtime_center_events_api.py -q` -> `19 passed`；`PYTHONPATH=src python -m pytest tests/app/test_capability_market_api.py -q` -> `42 passed`；`PYTHONPATH=src python -m pytest tests/app/test_predictions_api.py -k "trial_and_retirement_loop" -q` -> `1 passed`；`PYTHONPATH=src python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "governed_kernel_tasks or replace_mode or protected_replace" -vv` -> `4 passed`。当前诚实边界：这条记录表示 capability evolution 的 governed closure 已完成；它不等于 donor 侧“任意项目任意协议都能自动抽业务动作”这种更大的外扩承诺。
- `2026-04-05` 更正：前述 `2026-04-04` donor-first 相关记录中，凡是把“对象/测试/read-model 落地”表述成“真实外扩能力已全部完成”的口径，现统一收回。当前最准确的现实边界是：1) `capability-market` 的 SkillHub / curated / official MCP registry 三条市场子链已经部分 live 可用，其中 MCP 搜索 -> 安装 -> 真实连接已实测打通；2) SkillHub/curated 的搜索结果集仍混有大量坏 bundle，存在“能搜到但安装 404”的真实断层；3) `DonorScoutService`、`OpportunityRadarService`、`source-chain`、`portfolio/trust` 的对象层和 read-model 已落主线，但 runtime bootstrap 中默认 `discovery_executor` 仍为空，opportunity feeds 仍为空，通用开源 donor / GitHub 搜索也尚未形成真实产品级 discover -> candidate -> trial 主链；4) 因此 donor-first 当前状态只能表述为“代码骨架、state truth、部分市场链已落地”，不能再表述为“完整闭环已全部完成”。
- `2026-04-05` donor 真实缺口清单：当前只保留 4 个仍需补齐的 live gap，不再泛化成“还有一轮增强”。1) runtime discovery executor 仍未接真实 provider，导致 autonomous scout 默认只能跑出空结果；2) source-chain 对 `0 hit` 仍记 success，source health 会假阳性；3) 通用开源 donor / GitHub 搜索还未形成真实 discover -> candidate 主链；4) SkillHub / curated 的 bundle installability 校验与坏包抑制尚未闭环。后续 donor 施工应只围绕这 4 项，补完后再重新做 live 验收，不再按“代码骨架已在”宣告完成。
- `2026-04-05` donor live gap closure：上述 4 个 live gap 已在主线代码补齐，并已按“真实发现 / 真实安装 / 真实使用”三层补完 live 验收。代码面收口包括：1) `source_chain.execute_discovery_action()` 现已把 `0 hit` 收口为 `empty`，会继续尝试下一个 source，且不会把空结果写成 last-known-good success；2) `runtime_service_graph._execute_runtime_discovery_action()` 已从空实现改成真实 provider dispatcher，当前默认支持 `SkillHub / GitHub repo search / official MCP registry`，并会把 `source.endpoint` 透传给 provider search；3) `runtime_service_graph` 的 `OpportunityRadarService` 不再默认 `feeds={}`，而是带 bounded `github-trending / mcp-registry` feeds；4) `src/copaw/discovery/provider_search.py` 已形成通用 GitHub donor search 正式适配层；5) `search_hub_skills()`、`search_curated_skill_catalog()` 现会做 SkillHub bundle installability 校验并抑制坏包；6) `donor_source_service` / `source_chain` 现已支持 cache-backed `offline-private` 与 last-known-good snapshot fallback。focused regression：`PYTHONPATH=src python -m pytest tests/state/test_donor_source_service.py tests/discovery/test_source_chain.py tests/discovery/test_scout_service.py tests/discovery/test_opportunity_radar.py tests/discovery/test_provider_search.py tests/agents/test_skills_hub.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_center_donor_api.py tests/app/test_capability_market_api.py -q` -> `73 passed`；donor read-model 相邻回归：`PYTHONPATH=src python -m pytest tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/predictions/test_donor_recommendations.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py -q` -> `107 passed`。真实联网验收矩阵：1) `/capability-market/hub/search?q=agent browser` 只返回可安装包，`agent-browser` 安装成功，且统一 `/capability-market/capabilities?kind=skill-bundle` 可见；2) `/capability-market/curated-catalog?q=agent browser` 会显式报告已抑制的坏 bundle 数，并成功安装 `agent-browser`；3) `/capability-market/mcp/catalog?q=filesystem` + detail/install 实测成功安装 `io.github.Digital-Defiance/mcp-filesystem`，随后 `MCPClientManager.init_from_config()` 返回 `status=ready`；4) `/capability-market/install-templates/browser-local/install` 后，真实 API start -> attach -> stop 全链通过；5) `/capability-market/install-templates/desktop-windows/install` 后，真实 MCP runtime connect 返回 `status=ready`；6) `DonorScoutService` 现已能在真实 runtime executor 上通过 `browser automation github` 和 `opportunity` 模式导入真实 GitHub donor candidates，不再默认 `0 imported candidates`；7) source-chain 在主源强制失效后会落到 snapshot fallback，并能通过 `offline-private` profile 命中 cache-backed donor results。按这条记录，`2026-04-04` donor-first 外扩实现计划与 donor-first capability evolution priority plan 的 live runtime 边界已满足；当前没有这两份 donor 文档范围内的已知 live 缺口。
- `2026-04-05` donor GitHub project live closure 补充：此前 runtime/path 层虽然已经能发现 GitHub donor，但产品前门仍缺 3 条真链：1) capability-market 没有正式 `/projects/search`；2) raw GitHub fallback 把 repo 名误当 skill 名，真实仓库 `LeoYeAI/teammate-skill` 会在 `SKILL.md name=create-teammate` 时安装失败；3) `/projects/install` 直接读 kernel 顶层结果、没有解包 `result.output`，且 `source_url` 直装不会自动 materialize `candidate -> trial` 真相。现已补齐：`/capability-market/projects/search` 支持 direct repo query（URL 或 `owner/repo`）并返回 installable GitHub donor；raw fallback 会以前台 `SKILL.md` frontmatter 名称作为正式 skill 名；project install 现统一解包 kernel output，并在 `source_url` 直装时自动导入 candidate、同步 `candidate/trial` 正式真相。fresh 回归：`PYTHONPATH=src python -m pytest tests/agents/test_skills_hub.py tests/discovery/test_provider_search.py tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py -q` -> `53 passed`；相邻回归：`PYTHONPATH=src python -m pytest tests/predictions/test_skill_trial_service.py tests/app/test_runtime_center_events_api.py tests/kernel/test_query_execution_runtime.py -q` -> `40 passed`。真实 smoke：`GitHub repo -> /capability-market/projects/search -> /capability-market/projects/install(source_url-only) -> seat trial -> /runtime-center/agents/{agent_id}/capabilities` 已用 `https://github.com/LeoYeAI/teammate-skill` 跑通；结果包括 `candidate_id` 生成、`name=create-teammate`、`installed_capability_ids=['skill:create-teammate']`、seat-scoped `trial_attachment` 成功、agent `effective_capabilities` 出现 `skill:create-teammate`，且 candidate/trial 同步带上正式 `donor_id / package_id / source_profile_id`。需要注意：当前 GitHub donor live closure 的边界仍是“仓库暴露有效 `SKILL.md` bundle 的 SKILL-backed repo”；它不等价于“任意开源仓库都能被 CoPaw 直接 clone/build/materialize 成正式 capability”。
- `2026-04-05` donor Python project contract 补充：GitHub 开源项目 donor 现已不再复用共享 `pip --user` 环境，也不再在安装后搬动 venv 路径。`/capability-market/projects/install` 已切到 source-scoped isolated venv contract：先在 `WORKING_DIR/external_capability_packages/*/.venv` 中创建独立环境，再用该环境自己的 `python -m pip` 走 bounded transport chain（`codeload tar.gz -> GitHub archive zip -> git`），随后通过目标 venv 的 `importlib.metadata` 解析 distribution / console script，并把 `environment_root / python_path / scripts_dir` 写回正式 config truth。与此同时，这一轮又继续补齐了 4 个真实 runtime 断层：1) multi-entrypoint service donor 现会优先选真正的 service entrypoint，而不是盲选 distribution 同名 CLI；`OpenSpace` 现在会正式落到 `openspace-dashboard`；2) service start 现带 bounded readiness wait，不再一轮 probe 失败就过早降成 `degraded`；3) `/runtime-center/external-runtimes/actions` 现已按动作类型裁切 typed payload，`start/stop/healthcheck/restart` 不再互相携带无关字段；4) project donor install front-door 不再优先把用户卡在长时间 `git clone`。fresh focused regression：`PYTHONPATH=src python -m pytest tests/kernel/test_runtime_outcome.py tests/capabilities/test_project_donor_contracts.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py tests/state/test_external_runtime_service.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_center_external_runtime_api.py -q` -> `129 passed`。真实 fresh smoke：1) `https://github.com/psf/black` 已成功安装为 `project:black`，统一执行面真实返回 `black --version`；2) `https://github.com/HKUDS/OpenSpace` 已通过正式前门完成 `projects/search -> projects/install -> runtime-center start -> HTTP 200 /health -> runtime-center stop`，并真实落成 `runtime:openspace` + `script:openspace-dashboard` + `port 7788` 的 service runtime truth。按这条记录，GitHub Python 开源项目 donor 已正式满足当前合同下的 `discover -> install -> use` 与 `service ready -> stop` 真实闭环；当前边界仍是“符合 Python/GitHub/venv install contract 的项目”，不等于任何语言、任何构建系统的任意仓库都已自动适配。
- `2026-04-05` 下一轮纪律收口 `G/H` 真落地补充：`Package G` 与 `Package H` 已在隔离 worktree `gh-discipline-closure` 完成代码级闭环，不再只停在“已有骨架”。`CapabilitySkillService` 现新增 canonical `read_skill_metadata_summary(...)`，把 `package_ref / package_kind / package_version / canonical_skill_root / target_scope / target_role_id / target_seat_ref / activation_scope_key / path_scoped_activation / package_bound` 收口成同一正式 skill metadata read model；`CapabilityCatalogFacade.list_skill_specs()` 与 `list_available_skill_specs()` 也已开始消费这同一 summary，并按 canonical package identity / canonical skill root 做 duplicate suppression，避免相同 donor/package 在正式 skill spec 里并行外溢。与此同时，`CapabilityPortfolioService` 已从 summary-only 统计长出正式 `governance_actions` contract，现会输出 `run_scoped_trial / review_replacement_pressure / review_retirement_pressure / compact_over_budget_scope` 的结构化 action payload（带 `priority / route / donor_ids / scope_key / budget_limit` 等字段），旧 `planning_actions` 退为兼容投影；`Runtime Center` capability governance projection 也已把这些 structured actions 透传进正式读面。为防未来继续把 capability governance 堆回超大 orchestration file，`overview_cards.py` 中的 capability governance projection 已抽到新文件 `src/copaw/app/runtime_center/overview_capability_governance.py`，这次 hotspot cooling 只切 capability governance 这一块正式合同，不做 cosmetic file move。fresh verification：`PYTHONPATH=src C:\Python312\python.exe -m pytest tests/test_skill_service.py tests/app/test_capability_skill_service.py tests/predictions/test_skill_candidate_service.py tests/app/runtime_center_api_parts/overview_governance.py -q` -> `112 passed`。
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
- `2026-04-04` 补充：prediction 的 capability evolution recommendation contract 又收紧了一刀。`underperforming_capability / capability_rollout / capability_rollback / capability_retirement` 现在统一改走 `system:apply_capability_lifecycle`，不再在 rollout/rollback/retirement 分支里混用 `apply_role / set_capability_enabled` 造成 recommendation action contract 分裂；同一轮 recommendation refresh 也开始把 `trial_attachment / lifecycle_result / selected_scope / selected_seat_ref / skill_trial_id` 写回 metadata，保证 single-seat trial 的 seat continuity 能沿 `trial -> follow-up recommendation -> execution refresh` 主链持续可见。与此同时，trial follow-up findings 现在会把 `candidate_id` 沿 `service_context -> service_recommendations` 正式透传，避免 rollout/rollback/retirement recommendation 丢失 capability lifecycle 主语。focused 回归：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_predictions_api.py tests/app/test_capability_skill_service.py -q` -> `28 passed`。
- `2026-04-02` 补充：knowledge activation layer 已开始真正进入 planning 主链，而不再只停留在 query/read surface。`MemoryActivationService.activate_for_query(...)` 现在会在 scoped fact recall 之外继续拉取 `entity/opinion` derived views；`IndustryService.run_operating_cycle(...)` 会把同一份 activation result 前移复用到 prediction cycle review、report synthesis 与 cycle planner，而不是各自重算或只在后半段消费；`PlanningStrategyConstraints` 与 `CyclePlanningDecision.metadata` 现已保留 `graph_focus_entities / graph_focus_opinions`；follow-up backlog 与 materialized assignment continuity 也会继续携带 `activation_top_entities / activation_top_opinions`。当前 focused graph-backed planning 回归：`$env:PYTHONPATH='src'; python -m pytest tests/memory/test_activation_service.py tests/industry/test_report_synthesis.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/industry_api_parts/bootstrap_lifecycle.py::test_activation_followup_backlog_carries_activation_metadata tests/app/industry_api_parts/bootstrap_lifecycle.py::test_activation_followup_materialized_assignment_keeps_activation_metadata tests/app/industry_api_parts/bootstrap_lifecycle.py::test_run_operating_cycle_persists_graph_focus_into_formal_planning_sidecar tests/app/test_predictions_api.py::test_prediction_cycle_case_exposes_light_formal_planning_context_in_detail tests/app/industry_api_parts/runtime_updates.py::test_runtime_updates_expose_activation_summary_on_current_cycle_surface tests/app/industry_api_parts/runtime_updates.py::test_runtime_updates_keep_replan_focus_and_activation_summary_together -q` -> `41 passed`。当前边界仍然是不引入 graph persistence、不新增第二真相源，只把 graph signal 作为 planner/replan sidecar 输入。
- `2026-04-02` 补充：长期无人值守成熟度 follow-up 的第一刀已从 `ActorSupervisor` 扩到 automation coordinator/read-model。resident supervisor 现在对单个 agent run failure 做异常隔离，不再因为单个 worker 异常把整次 poll 或整条常驻 loop 一起打死；失败会正式写回 `AgentRuntime.last_error_summary`、`metadata.supervisor_last_failure_*`，并通过 runtime event bus 发布 `actor-supervisor.agent-failed / actor-supervisor.poll-failed`。与此同时，`start_automation_tasks()` 已升级成带 `loop_snapshots()` 的 `AutomationTaskGroup`，每条 loop 现都会暴露稳定 `automation_task_id / coordinator_contract / loop_phase / health_status / last_gate_reason / submit_count`，并把同一套 coordinator 元数据写进真正提交到 kernel 的 payload；`/runtime-center/main-brain` 的 automation section 也已开始持续显示 automation loops 和 actor-supervisor health，而不再只剩 schedule/heartbeat 薄摘要。focused durable-runtime 验证：`$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_actor_supervisor.py tests/app/test_runtime_lifecycle.py tests/app/runtime_center_api_parts/overview_governance.py -k "test_actor_supervisor or test_start_automation_tasks or main_brain_route_exposes_unified_operator_sections or automation_loop_and_supervisor_health" -q` -> `22 passed`。该记录表示 durable runtime baseline 已继续从“能恢复/能发车”推进到“有 coordinator snapshot 与 health read-model”，不表示 external bridge/browser/document producer 已全部纳入同一 durable producer runtime。
- `2026-04-02` 补充：durable runtime 的 operator self-check/overview 也已补到同源 runtime summary。`RuntimeHealthService` 现在会复用 Runtime Center 的正式 automation/supervisor/startup recovery 投影，直接从同一条 `app.state` runtime truth 生成 `/system/self-check.runtime_summary`，不再只回“服务是否存在”；`/runtime-center/main-brain` 的 automation loops 读面也已开始合并 `loop_snapshots()` 的 coordinator 字段，不再只能看见 task name + running/completed。focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_system_api.py tests/app/runtime_center_api_parts/overview_governance.py -k "runtime_summary or automation_loop_and_supervisor_health or automation_loop_snapshots" -q` -> `10 passed`。这条记录表示 durable runtime 的 operator summary 已从 service-presence 升级为 execution-grade read-model，不表示 automation heartbeat/schedule 已完全切成 persisted-only projection。
- `2026-04-02` 补充：durable runtime 的 operator mutation front-door 这一轮也已继续硬化。`Runtime Center` 现在对 `POST /runtime-center/heartbeat/run` 与 `POST /runtime-center/schedules/{id}/run|pause|resume` 增加了同类动作重入保护：相同 operator control 在未完成时会直接返回 `409`，不再允许双击/重复提交在同一前门上并行发车。与此同时，`dispatch_governed_mutation(...)` 已开始按 `capability_ref + owner_agent_id + stable payload signature` 复用现有 `risk-check / waiting-confirm / executing` kernel task；相同 governed mutation 在 `waiting-confirm` 时会复用已有 `decision_request_id`，而不是继续物化第二个 pending decision。`pause/resume` 对已命中目标状态的 schedule 也会直接返回 typed no-op，不再制造无意义 task/evidence；同一合同面的 `404 / dispatch failure / heartbeat failed result` 分支也已补上专项回归，不再只锁 happy-path。最后，`CronManager._run_heartbeat(...)` 已升级成 heartbeat single-flight：手动 `run` 与 scheduler callback 在同一时刻只会真正执行一次底层 supervision pulse，后续并发调用复用同一结果，不再重复提交 operating-cycle heartbeat。focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_cron_manager.py tests/app/test_runtime_lifecycle.py tests/app/test_system_api.py -q` -> `88 passed`，以及 `$env:PYTHONPATH='src'; python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/industry/test_runtime_views_split.py tests/industry/test_report_synthesis.py -q` -> `45 passed`。这条记录表示 runtime mutation contract 已从“只有 happy-path governed shell”推进到“front-door reentry guard + pending reuse + typed no-op + heartbeat single-flight”，不表示 durable runtime 的 external producer / persisted-only projection 已全部终态完成。
- `2026-03-25` 补充：前端 shared `control chain` presenter 已落地，`/industry`、`Runtime Center`、`AgentWorkbench` 统一消费同一条 `writeback -> backlog -> cycle -> assignment -> report -> replan` 呈现链，不再各自维护排序和标签逻辑。
- `2026-03-25` 补充：`Runtime Center` 路由已继续按域拆出 `overview / memory / knowledge / reports / industry` 模块，`runtime_center_routes_core.py` 不再继续承载这些域；同时已删除 retired `TaskDelegationRequest` 与死掉的 delegation shared helper。
- `2026-03-25` 补充：`state/models.py` 已收成兼容 re-export 面，`goals_tasks / agents_runtime / governance / workflows / prediction / reporting / industry / core` 分层模块已经落位，旧导入链继续可用但真正定义不再堆在单文件里。
- `2026-03-25` 补充：`EnvironmentService` 已降为稳定 façade；环境包已拆出 `session_service / lease_service / replay_service / artifact_service / health_service`，session/resource/actor lease、runtime recovery、environment detail 与 replay/artifact 读面不再继续堆在单个 1400+ 行服务里。
- `2026-03-25` 补充：`ProviderManager` 已降为 compat façade；`providers` 包已拆出 `provider_registry / provider_storage / provider_resolution_service / provider_chat_model_factory / provider_fallback_service`，runtime/query/industry 等可注入调用点优先改走显式实例，残余 `get_instance()` 已收口到 bootstrapping、router/CLI 与 façade 静态入口；旧 `memory_manager` 兼容链已在 `2026-04-14` 物理删除。
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
- `2026-04-08` 补充：computer-control remaining closure 这轮已按正式边界收口完成。当前正式口径是：execution agent 决定何时观察/操作/验证/恢复，adapter/host 负责真实 browser/desktop/document 动作，MCP 负责统一暴露/接线，runtime/kernel/environment 负责 `session / lease / lock / evidence / risk / recovery / anti-contention`。在这条边界下，desktop hardening slice、watcher/readiness/writer contract 与 browser routing truthful closure 已全部进入主线：built-in browser 继续作为默认通道，healthy attached browser continuity 会显式解析到 browser MCP 通道，attach-required 请求会 fail closed 而不是静默降级；Runtime Center environment detail 现已正式投影 browser channel selection/health。fresh verification：`python -m pytest tests/routines/test_routine_service.py tests/app/test_capability_market_api.py tests/environments/test_cooperative_document_bridge.py tests/routines/test_routine_execution_paths.py tests/environments/test_cooperative_windows_apps.py -q` -> `106 passed`；`python -m pytest tests/routines/test_routine_service.py tests/app/test_capability_market_api.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q` -> `179 passed`；`$env:COPAW_RUN_V6_LIVE_ROUTINE_SMOKE='1'; python -m pytest tests/routines/test_live_routine_smoke.py -k "attached_browser_channel_continuation_smoke or authenticated_continuation_cross_tab_save_reopen_smoke" -q` -> `2 passed`；`$env:COPAW_RUN_V6_LIVE_ROUTINE_SMOKE='1'; python -m pytest tests/routines/test_live_routine_smoke.py -k "semantic_dialog_controls_round_trip or live_desktop_routine_launch_edit_save_round_trip or live_desktop_routine_replay_round_trip" -q` -> `3 passed`。这条记录表示当前 computer-control 规划文档对应的 closure/blocker 工作已经完成，不表示未来所有新 app-family 语义能力都已无限扩展到终态。
- `2026-03-26` 补充：`src/copaw/app/routers/learning.py` 已改成依赖注入式 façade 解析，不再在每个 endpoint 内重复手动解析 app-state learning service。
- `2026-03-26` 补充：capability/runtime 尾巴已继续硬切收口。旧 `/skills`、`/mcp` 与 `legacy_capability_aliases.py` 已物理删除；router 写操作现统一落到 `app/routers/governed_mutations.py`；runtime decision/patch 链接现统一落到 `utils/runtime_action_links.py`；chat / AgentWorkbench / RuntimeCapabilitySurfaceCard / RuntimeExecutionStrip 的风险与状态标签颜色已统一改走 `console/src/runtime/tagSemantics.ts`，不再各自维护分叉语义。
- `2026-03-26` 补充：`Chat` 页已正式按 chat-first 收口，只保留 `消息流 + 输入框 + 最小状态条 + 必要附件能力 + 最小治理审批入口`；`capability drawer`、重 runtime sidebar、`V7ControlThreadPanel` 与 actor detail 驱动的聊天页附属面已从主页面摘除，不再把 `Chat` 做成第二个运行中心。`AgentWorkbench` 的 `ActorRuntimePanel` 已独立落到 `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`，`pageSections.tsx` 回退为兼容导出面。
- `2026-03-26` 补充：Industry 主链已继续朝“单一状态入口”硬化。`build_industry_service_runtime_bindings(...)` 不再基于 `state_store` 临时补造 repo/service，运行时绑定只接受显式注入协作者；`reconcile_instance_status_for_goal()` 也已改成按 `goal_id` 定向读取实例，不再每次 goal 变化都全表扫行业实例。
- `2026-03-26` 补充：query runtime 的前门意图判定与 durable writeback 策略已统一改走共享 `query_execution_intent_policy.py`，不再在 `shared/runtime/writeback` 三处各自复制“目标委托 / 假设性提问 / 是否写回”的启发式；`LearningRuntimeCore` 公开 patch/growth/trial 入口也已继续瘦身为 thin delegate，proposal/patch/growth/acquisition 责任边界开始稳定落位。
- `2026-04-04` 缓存治理补充：`cc` donor 的缓存精华已按 CoPaw 正式主链本地化落地，不再停留在“散落 TTL dict”。后端新增 `src/copaw/utils/cache.py` 作为统一 micro-cache helper，提供 `TTLCache / BoundedLRUCache`；`/system` 的 workspace stats cache 与 `capabilities/mcp_registry.py` 的 registry HTTP cache 已迁到 shared helper，分别补上 `clear_workspace_stats_cache()` 与 bounded TTL contract。`kernel/query_execution_writeback.py` 的 chat writeback decision cache 现已收紧为正式 bounded LRU，并新增 `clear_chat_writeback_decision_cache()`；对应回归锁死了“最近命中项不应被错误逐出”。主脑 prompt scope cache 的 dirty contract 也补上了全局 dirty 语义：当没有显式 work-context / industry / agent key 时，会统一标脏所有 scope snapshot，避免 global runtime 变化后沿用旧 prompt snapshot。前端新增 `console/src/runtime/activeModelsCache.ts` 统一托管聊天页 active-model convenience cache；provider/local-model/ollama 的写 API 现都会显式失效该缓存，`runtimeTransport` 不再自带隐藏 singleton。缓存账本已新增 `docs/superpowers/specs/2026-04-04-caching-governance-ledger.md`，正式登记了主脑 scope/session、resident agent、MCP registry、workspace stats、writeback decision、frontend active models 与 execution pulse 这些缓存的 key/TTL/失效条件/风险级别。当前定向验证：`python -m pytest tests/test_cache_utils.py tests/capabilities/test_mcp_registry_cache.py tests/kernel/test_chat_writeback.py tests/kernel/test_main_brain_chat_service.py tests/app/test_system_api.py -q` -> `54 passed`；`npm --prefix console run test -- src/runtime/activeModelsCache.test.ts src/api/modules/modelMutationInvalidation.test.ts src/pages/Chat/runtimeTransport.test.ts` -> `25 passed`。
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
- `2026-04-07` 补充：desktop-control governance 这轮又继续收了一刀。`RoutineService` 在正式 runtime wiring 下已新增 `mcp:desktop_windows` fail-close 校验：当 owner agent capability surface 缺少桌面能力时，desktop replay 会在宿主实例化前直接失败，而不会绕过 capability 装配治理偷跑 Windows host；runtime domain bootstrap 也已把 `capability_service + agent_profile_service` 正式接入 routine front door。与此同时，`desktop-windows` install-template doctor/example-run 不再把“能列窗口”误报成“电脑控制完整可用”：doctor 现显式区分 `pywin32_ready` 与 `semantic_control_ready`，`pywinauto` 缺失时会降级为 `degraded`，example-run 也会额外返回 `semantic-import-check` 结果。`surface_control_service` 的 document writer scope 也已从“缺省 session 级锁”收紧为“优先显式 scope，其次稳定文档路径 scope，最后才回退 session_mount_id”，同一路径跨 session 的桌面文档写入现在会共享同一把 writer lease。fresh verification：`python -m pytest tests/routines/test_routine_service.py tests/routines/test_routine_execution_paths.py -q` -> `18 passed`；`python -m pytest tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_operator_abort_projection.py -q` -> `43 passed`；`python -m pytest tests/app/test_capability_market_api.py -k "desktop_windows or desktop-windows or desktop" -q` -> `2 passed, 43 deselected`；`python -m pytest tests/app/runtime_center_api_parts/detail_environment.py -k "desktop_app_contract or operator_abort" -q tests/app/test_workflow_templates_api.py::test_install_template_assigns_capability_and_unlocks_workflow_launch` -> `1 passed, 10 deselected`；`python -m pytest tests/adapters/test_windows_host.py tests/adapters/test_windows_host_control_layer.py tests/adapters/test_windows_uia.py -q` -> `27 passed`；`python -m pytest tests/app/test_runtime_bootstrap_split.py::test_domain_builder_wires_environment_service_into_fixed_sop_service -q` -> `1 passed`。
- `2026-04-03` 补充：多执行位能力自治这轮已在特性分支 `multi-seat-capability-autonomy` 完成后端实现并合并回 `main` 的当前集成态。当前正式能力治理口径已落成 `全局能力底座 / 角色原型能力包 / 执行位实例能力包 / 周期增量包 / session overlay` 五层，并已接到 query fast-loop、seat/session MCP overlay、governed remote skill lifecycle、prediction rollout/rollback、Runtime Center / industry detail read-model。合并收口时额外补掉了几个真实尾巴：1）hub-skill mock/install 在缺少本地 `SKILL.md` 持久化目标时改为 fail-soft，不再把 bootstrap/trial 整条链误判为失败；2）Runtime Center 在无 live task 时会优先回显最近 operator writeback 链，而不是被新的 queued assignment 抢走 `routine/report` 主链真相；3）显式 assignment/backlog 选中与 report-followup backlog 现在会稳定进入 runtime focus，但在存在 live task 时仍不会凭 task title 伪造 focus。merged-main fresh verification：`PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py -q` -> `259 passed`；adjacent regressions：`PYTHONPATH=src python -m pytest tests/app/test_capabilities_execution.py tests/agents/test_skills_hub.py tests/app/test_capabilities_api.py tests/app/test_capability_catalog.py -q` -> `61 passed`；focused integration slice：`PYTHONPATH=src python -m pytest tests/app/test_industry_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_capability_market_api.py tests/app/test_capability_skill_service.py tests/industry/test_runtime_views_split.py -q` -> `190 passed`。
- `2026-04-03` 补充：长期自治下“主脑治理型完整 capability evolution loop” 的正式设计与施工文档已补齐：`docs/superpowers/specs/2026-04-03-autonomous-capability-evolution-loop-design.md` 与 `docs/superpowers/plans/2026-04-03-autonomous-capability-evolution-loop-implementation-plan.md`。这套文档明确区分了 `candidate truth / artifact synthesis / scoped trial / lifecycle decision / capability recomposition / drift detection` 六段正式闭环，并锁死 donor 边界：可借 `cc` 的 `SKILL.md` artifact discipline、skill surfacing/loading、small-step skill improvement，但 capability lifecycle governance 继续留在 CoPaw 的 `CapabilityMount -> role/seat/session layers -> governed mutation -> evidence` 主链上，不引入第二真相源。
- `2026-03-25` 补充：`run_operating_cycle()` 已切掉 `goal` 物化中转；backlog 现在直接生成 `Assignment` 并编译成 assignment-backed `TaskRecord`，`AgentReport` 也优先按 `assignment_id` 回收，不再走旧 goal-phase 假链。
- `2026-03-25` 补充：`main_chain.routine` 在没有 live task 时，会回锚到最新 `AgentReport` 对应的 assignment/task 元数据；已完成的固定 SOP / routine 执行不会再在主链上丢失执行面信息。

- `2026-04-17` research session 当前真实边界补充：
  - 已落地代码基线：
    - `ResearchSessionRecord / ResearchSessionRoundRecord`
    - `SqliteResearchSessionRepository`
    - `BaiduPageResearchService`
    - runtime bootstrap 注入 `research_session_service`
    - 主脑 `user-direct` -> research session 正式触发前门
    - schedule `monitoring brief` -> research session 正式唤醒链
    - `GET /runtime-center/research`
    - `Runtime Center` 主脑 cockpit research summary surface
    - opt-in `live smoke` 合同测试
    - research session 默认浏览器登录态持久化：`WORKING_DIR/state/research_browser_storage/<owner_agent_id>.json`
    - `search?word=` 正式发问链、页面答案文本提取、登录误判修正、内部导航链接过滤
  - 当前未完成：
    - 当前主线已拿到“已登录状态下返回真实答案”的联网 `PASS`；剩余尾巴主要是答案/链接抽取策略还能继续做得更精细，但不再是主链断点
    - 这条链已具备正式对象、触发、执行、汇报、读面、登录态持久化与真实联网问答；仍不能外推成“所有百度页面变体都零维护”
    - `2026-04-18` continuity 收口补充：此前 heavy 前门仍是“每次 follow-up 都新建 session”，research service 也仍有“默认首问 + 一次 follow-up 就收工”的旧停机语义；现已收正为“跟进问题优先复用同一 matching reusable `ResearchSession`、同一 reusable session 优先复用同一 chat page/thread、停止以当前问题是否问清为主，`MAX_BAIDU_ROUNDS / MAX_DEEP_LINKS / MAX_DOWNLOADS` 只保留为安全上限”；其中 `MAX_BAIDU_ROUNDS` 现已按单次 `run_session(...)` 安全切片收口，不再错误限制整个可复用研究线程的生命周期
  - 当前验收口径：
    - `L1/L2`：
      - `python -m pytest tests/state/test_research_repositories.py tests/state/test_state_store_migration.py tests/state/test_models_module_exports.py tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_deepening_flow.py tests/research/test_research_report_writeback.py tests/research/test_research_knowledge_ingestion.py tests/agents/test_browser_tool_evidence.py tests/app/test_research_schedule_trigger.py tests/app/test_research_session_api.py tests/app/test_runtime_center_router_split.py tests/app/test_cron_executor.py tests/app/test_runtime_manager_stack.py tests/kernel/test_main_brain_research_followup.py tests/app/test_research_session_live_contract.py -q` -> `81 passed, 1 skipped`
      - `python -m pytest tests/app/test_industry_service_wiring.py::test_runtime_domain_builder_injects_research_session_service_into_main_brain_chat tests/app/industry_api_parts/runtime_updates.py -k "bootstrap_researcher_schedule_report_keeps_main_brain_continuity or researcher_followup_assignment_persists_execution_core_continuity_without_backlog_anchor" -q` -> `2 passed, 47 deselected`
      - `npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx` -> `19 passed`
      - `PYTHONPATH=src python -m pytest tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py tests/app/test_research_session_live_contract.py tests/kernel/test_main_brain_research_followup.py -q` -> `15 passed, 1 skipped`
      - `PYTHONPATH=src python -m pytest tests/research/test_source_collection_contracts.py tests/research/test_source_collection_routing.py tests/research/test_source_collection_synthesis.py tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_deepening_flow.py tests/research/test_research_report_writeback.py tests/research/test_research_knowledge_ingestion.py tests/research/test_research_writeback_flow.py tests/kernel/test_main_brain_research_followup.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_research_session_live_contract.py tests/app/test_runtime_center_research_surface.py -q` -> `49 passed, 1 skipped`
      - `npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx` -> `20 passed`
      - `PYTHONPATH=src python -m pytest tests/research/test_baidu_page_research_service.py tests/app/test_source_collection_frontdoor_service.py tests/app/test_research_session_live_contract.py tests/kernel/test_main_brain_research_followup.py tests/research/test_research_report_writeback.py tests/research/test_research_knowledge_ingestion.py -q` -> `30 passed, 1 skipped`
    - `L3`：已跑 opt-in live smoke 合同；`COPAW_RUN_BAIDU_RESEARCH_LIVE_SMOKE=1 PYTHONPATH=src python -m pytest tests/app/test_research_session_live_contract.py -q -rs` -> `2 passed`
      - `2026-04-18` 真实连续追问补充：已在当前机器登录态下真实跑通 `start -> run -> resume -> run -> resume -> run`，结果为同一 `research session`、同一 `browser session`、`baidu_chat_open_count=1`，第三次追问也已收口到 `followup-complete`，不再掉回 `max-rounds`
      - 当前真实结果：浏览器 runtime 已能正常启动并打开百度页；在当前机器登录百度后，真实 research session 已能拿到问答结果
    - `L4`：已跑选定范围 live soak
      - `2026-04-18` 真实 soak：通过 inline python live soak harness 连续跑 `3` 个 cycle；每个 cycle 都走正式 `SourceCollectionFrontdoorService`，并在每一步重新构建 `SqliteResearchSessionRepository / BaiduPageResearchService / SourceCollectionFrontdoorService` 模拟重进
      - 每个 cycle 的真实结果一致：`session_ids` 全程同一条、`stop_reasons = ["followup-complete", "followup-complete", "followup-complete"]`、`round_count = 6`、`chat_open_count = 1`
      - 当前因此可以诚实声明：research continuity / source-collection heavy path 这条链已过 `L1 + L2 + L3 + 选定范围的 live L4`；但这仍不等于“所有百度页面变体”或“整仓 full-repo soak”都已完成
  - 下一步验证顺序应固定为：继续收答案/链接抽取质量，以及更广范围的 external-provider / full-repo soak，而不是再回退到“新 session + 固定轮次”的旧语义
  - `2026-04-17` source collection foundation 已落地：
    - typed contracts：`ResearchBrief / CollectedSource / ResearchFinding / ResearchAdapterResult`
    - routing / synthesis / orchestration：`route_collection_mode(...) / synthesize_collection_results(...) / SourceCollectionService`
    - phase-1 adapters：`search / web_page / github / artifact`
    - 当前 adapter 边界：phase-1 light adapters 已支持 live single-source collection，并补上默认 source inference；真实外部多轮采集默认仍由 heavy `BaiduPageResearchService` 承接，但它已通过 `collect_via_baidu_page(...)` 收进共享 provider adapter seam
    - formal frontdoor：`SourceCollectionFrontdoorService.run_source_collection_frontdoor(...)`
    - 统一入口：主脑 `user-direct`、`main-brain-followup`、cron `monitoring`、职业 agent `collect_sources`
    - persistence/read-model：session-level `brief / conflicts / writeback_truth`、round-level `sources / findings / conflicts / gaps / writeback_truth` 已正式持久化；`/runtime-center/research` 现已优先读取这些 formal projection，而不是继续优先吃 metadata fallback
    - writeback boundary：heavy `summarize_session()` 继续复用 report + knowledge summary writeback；`StateKnowledgeService.ingest_research_session(...)` 与 `KnowledgeWritebackService.build_research_session_writeback(...)` 已作为 heavy/light 共用 builder；light inline collection 现在也会在 live frontdoor 上自动写 dedicated `EvidenceRecord`，并自动把 report / knowledge / graph writeback 真写回
    - Runtime Center：`/runtime-center/research` 与 cockpit research card 已正式暴露 `brief / findings / sources / gaps / conflicts / writeback_truth`
  - `2026-04-20` searching upgrade phase-1 已落地：
    - 正式新增 `retrieval substrate`：`src/copaw/retrieval/` 现已落地 `RetrievalQuery / RetrievalPlan / RetrievalHit / RetrievalRun / RepositoryIndexSnapshot / CodeSymbolRecord`
    - 当前 canonical 接线：`SourceCollectionFrontdoorService -> SourceCollectionService -> RetrievalFacade`；`route_collection_mode(...)` 继续只负责 `light/heavy` 分流，`RetrievalPlanner` 只负责检索策略，不再混成同一层职责
    - 当前 retrieval phase-1 source seam：`local_repo / github / search / web_page`；本地仓库已补 `exact / symbol / semantic` retrieval，GitHub/Web 已补 object/discover/read/credibility/freshness seam
    - retrieval cache/index 当前明确只属于可重建检索层，不属于 formal truth；正式写链仍然是 `ResearchSessionRecord / ResearchSessionRoundRecord / EvidenceRecord / report / knowledge / graph writeback`
    - `/runtime-center/research` 当前已继续暴露 retrieval read surface：`intent / requested_sources / mode_sequence / coverage / selected_hits / dropped_hits / trace`；但 `brief / findings / sources / gaps / conflicts / writeback_truth` 仍保持 top-level formal projection 优先，retrieval trace 只作为解释层
    - `artifact-followup` 与 heavy `BaiduPageResearchService` 当前边界保持不变；searching retrieval substrate 不会把 heavy owner 回退成单一 light collector
    - fresh verification：
      - `L1/L2 backend`：`PYTHONPATH=src python -m pytest tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py tests/retrieval/test_local_repo_retrieval.py tests/retrieval/test_github_retrieval.py tests/retrieval/test_web_retrieval.py tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/app/test_source_collection_frontdoor_service.py tests/app/test_runtime_center_research_surface.py tests/app/test_runtime_center_research_retrieval_surface.py -q` -> `49 passed`
      - `L2 frontend`：`npm --prefix console test -- src/pages/RuntimeCenter/researchHelpers.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.retrieval.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts` -> `23 passed`
      - `L3 live smoke`：`COPAW_RUN_SEARCHING_LIVE_SMOKE=1 PYTHONPATH=src python -m pytest tests/app/test_searching_live_contract.py -q -rs` -> `2 passed`
      - `L4 soak`：`COPAW_RUN_SEARCHING_SOAK=1 PYTHONPATH=src python -m pytest tests/app/test_searching_soak_contract.py -q -rs` -> `2 passed`
  - 当前边界补充：
    - `2026-04-18` 文档纠偏：此前这里把 source collection 的 writeback / adapter 落地口径写得过窄；现已收正为“formal session/round truth 已闭环，heavy + light writeback 已闭环，provider adapter seam 已落到 `collect_via_baidu_page(...)`，phase-1 light adapters 已补成 live collector”
    - 这轮 fresh regression 已证明 typed contracts / routing / synthesis / frontdoor / Runtime Center 读面 / provider fallback 在 `L1/L2` 层收口
    - `2026-04-18` 真实 light-path `L3`：已在正式 `SourceCollectionFrontdoorService + SQLiteStateStore + EvidenceLedger + StateKnowledgeService + KnowledgeWritebackService` 组合上跑通 `search / web_page / github / artifact` 四条 live smoke；四条都真实产出 source / finding / evidence / report / writeback truth
    - `2026-04-18` 真实 light-path `L4`：已跑选定范围 live soak；连续 `3` 个 cycle、每轮重建 repositories/services，并让 `search / web_page / github / artifact` 都通过默认 source inference 走 light frontdoor。每条链都稳定写入 `1` round、`1` evidence、`written` writeback truth，且 source 数量稳定大于等于 `1`
  - `2026-04-18` browser substrate cutover 当前真实边界补充：
    - 已落地代码基线：
      - `src/copaw/environments/surface_execution/browser/contracts.py`
      - `src/copaw/environments/surface_execution/browser/observer.py`
      - `src/copaw/environments/surface_execution/browser/resolver.py`
      - `src/copaw/environments/surface_execution/browser/verifier.py`
      - `src/copaw/environments/surface_execution/browser/service.py`
      - `BaiduPageResearchService` 的 chat input / readback / deep-think toggle 已切到共享 browser substrate
    - 已删除的旧执行真相：
      - `data-copaw-chat-input` 单点回读规则
      - page-wide `button/label/span/div` 深度思考全页扫描
      - `BaiduPageResearchService` 内部重复定义的旧 `_read/_resolve` 硬编码链
    - 当前保留且允许存在的薄页面提示：
      - `#chat-textarea`
      - `data-copaw-deep-think`
      - 这些只用于页面 profile / target hint，不再决定“下一步做什么”
    - `2026-04-19` 进一步收口：
      - `BrowserSurfaceExecutionService` 已补共享 `observe_page / resolve_target / read_target_readback` 入口
      - `BrowserSurfaceExecutionService` 已补共享 `capture_page_context(...)` 入口，provider 不再需要直接调用底层 profile helper
      - `BrowserSurfaceExecutionService` 已新增最小 `run_step_loop(...)`，作为 shared `observe -> decide -> act -> reobserve` loop owner
      - `ResearchChatSurfaceLoopOwner` 已成为第一条 profession-layer submit planner：当前正式负责 `reasoning_toggle -> type -> press` 提交微循环，不再由 `BaiduPageResearchService` 自己手搓逐步动作
      - `BrowserSurfaceExecutionService.execute_step(...)` 已补页面级 `press` 动作，不再只能处理“先 resolve 元素再 click/type”的两类动作
      - shared browser verifier 已补 `toggle_enabled` 正式读回与断言；共享 click 链不再只能靠按钮文本验证
      - `BaiduPageResearchService` 的 `_resolve_chat_input_target / _read_chat_input_readback / _read_baidu_deep_think_state / _ensure_baidu_deep_think_enabled` 已改走 shared browser service
      - `BaiduPageResearchService._build_baidu_surface_context(...)` 已切到 shared `capture_page_context(...)`，不再直接 import profile helper
      - `BaiduPageResearchService` 的 page profile seed input 解析也已切到 shared browser service，不再直接 import 模块级 `observe_browser_page / resolve_browser_target`
      - `BaiduPageResearchService._submit_chat_question(...)` 已改挂 shared `run_step_loop(...)`；当前正式提交链是 `type -> press(Enter)`，不再由 service 自己手搓 `type 后再直接 press_key`
      - Baidu 提交 loop 已收成“轻 page profile”读面，只保留输入框相关 probe，不再把 deep-think toggle probe 混进 submit loop 里污染状态
      - `BaiduPageResearchService._ensure_baidu_deep_think_enabled(...)` 已切到 shared `execute_step(...) + toggle_enabled` 断言，不再自己拼 click payload
      - `BaiduPageResearchService._read_baidu_deep_think_state(...)` 已切到 shared `read_target_readback(...)`，旧私有 `_read_toggle_candidate_state(...)` 已删除
      - 旧 `_select_chat_input_ref(...)` helper 已从 `BaiduPageResearchService` 物理删除，不再保留死尾巴
      - shared browser substrate 现已复用现有 `browser evidence sink` 合同；当 runtime 绑定 sink 时，`BrowserExecutionResult.evidence_ids` 会回填正式 `evidence_id`
      - browser substrate 的 `target-unresolved` 失败早退也已留证据，不再让失败链静默丢失
      - `KernelToolBridge` 的 browser/file tool-use summary 现已显式回传 `evidence_id`，不再只回 `artifact_refs/result_items`
      - `src/copaw/environments/surface_execution/document/*` 与 `src/copaw/environments/surface_execution/desktop/*` 已补第一版 shared substrate 合同：两条新线都已具备正式 `Observation / ExecutionStep / ExecutionResult / ExecutionLoopResult / Service`，不再只有 browser 一条 shared execution 新链
      - `SourceCollectionFrontdoorService._find_reusable_heavy_session(...)` 已补 active-session 强制复用：同一 `owner_agent_id + industry_instance_id + work_context_id` 下，只要存在 `queued / running / waiting-login` 的 heavy research session，前门现在优先复用该会话，而不是继续依赖问题相似度 heuristics 新开一条
      - shared browser substrate 已补“无 profile 通用读面”基线：`capture_live_browser_page_context(...)` 在没有 provider/page profile 的页面上，也会先抓 live `bodyText / href / title`，再组装 shared `BrowserObservation`
      - shared `BrowserObservation` 已新增通用正文/阻塞派生：
        - 没有显式 `readable_sections` 时，会从 live `bodyText` 自动生成 `readable_sections`
        - 没有显式 `login_state` 时，会从页面正文/快照里的通用登录阻塞文案自动推导 `login-required`
        - `blockers` 会同步补上正式 `login-required`
      - shared `BrowserObservation` 现已新增正式 `page_summary`：
        - `page_kind`
        - `headline`
        - `primary_text`
        - `action_hints`
        - `blocker_hints`
      - 这条 `page_summary` 目前属于“共享页面理解基线”，不是最终完整语义模型；它已经能把普通页面先归纳成 `login-wall / upload-flow / form-flow / content-page` 这类粗粒度页面摘要，给上层 agent 提供第一层可消费读面
      - 这意味着像“番茄上传小说页”这类没有 provider 专用 profile 的普通页面，shared browser substrate 现在也能先读正文和阻塞，再把结果交给上层 agent 决策；不再是只能先靠 Baidu 这类特化页面活着
      - `BaiduPageResearchService` 的 `BrowserPageProfile` 现已显式 opt-in shared generic live probe；Baidu 这条 profiled live 链不再只能看输入框和 toggle，也会先带上 shared `bodyText -> readable_sections/login_state/blockers`
      - chat submit 前门现在已补“pre-submit blocker fail-closed”：当 shared observation 在提交前就已标出 `login-required` 时，`_submit_chat_question(...)` 不再先 `type -> press` 再回头发现被挡，而是直接返回 `pre_submit_login_required`
    - `2026-04-19` 继续收口：
      - 已新增共享 `chat_continuation_policy.py`：把 heavy research chat 的 `stop / deepen-link / next-round` 判定从 provider service 内联分支抽成正式纯决策函数
      - 已新增共享 `chat_continuation_owner.py`：在 policy 之上把“读回答 -> 判断是否继续 -> 生成下一步动作”收成 profession-layer owner，正式输出 `stop_reason / next_round_mode / next_question / next_link_url`
      - `BaiduPageResearchService.run_session(...)` 现已改走该 shared continuation owner；原来 service 里那段 `has_structured_answer / should_deepen / coverage-followup / generic-continue / enough-findings / no-new-findings / deepened-link-closed` 的内联 continue/stop 分支，现已由共享 owner 统一裁决
      - `response_readback` 现已补上最小 `page_kind / blocker_hints`，让高层 continuation owner 不再只能吃 provider 私变量，也能吃到本轮读面的页面摘要基线
      - `2026-04-19` 进一步修正：此前“同一话题连续对话”仍有一条真实断点，不在 `run_session(...)` 内部，而在 heavy frontdoor 对 completed session 的复用边界。单次 `run_session(...)` 内部本来就固定走 `chat_page_id={session.id}:chat`；真正会把一个话题拆成多个窗口的是 `main-brain-followup` 在没有明显 follow-up 关键词/强重叠分时，会错误地重新 `start_session`
      - 现已修成：`main-brain-followup` 会优先续上同 scope 下最近的 reusable heavy session；只有存在强匹配的旧线程时才改选该线程，不再因为自然追问文案太泛而新开一个 session/page
      - `2026-04-19` 主脑聊天 waiting-login 恢复链已正式化：
        - `MainBrainChatService` 现在会在 waiting-login 时把 `research_continuation` 正式写进 session snapshot 与 request runtime context，而不是只在当前 turn 内临时记住
        - 主脑回复文案现在会明确告诉用户“先完成百度登录，然后直接在这个聊天线程回复‘继续’或‘我登录好了’，系统会沿同一个研究会话和浏览器窗口继续”
        - 当用户在同一聊天线程回复继续类文案时，主脑会从 snapshot 里恢复 formal brief，并把 `preferred_session_id` 显式传给 heavy frontdoor，不再重新猜一个新 session
      - `2026-04-19` heavy research 的共享登录态路由已正式补上：
        - `BaiduPageResearchService._browser_session_start_kwargs(...)` 现已改成按这条正式优先级选 `storage_state_path`：
          - `session.metadata.browser_session.storage_state_path`
          - `COPAW_BAIDU_RESEARCH_STORAGE_STATE_PATH / COPAW_RESEARCH_BROWSER_STORAGE_STATE_PATH`
          - owner 默认 `state/research_browser_storage/{owner}.json`
        - 这意味着主脑 / cron / 其他 heavy entry 不再只能碰运气吃 owner 默认 storage file；现在可以稳定指向一个明确的共享已登录 storage state
        - `MainBrainChatService._build_research_frontdoor_metadata(...)` 现已会把 `_copaw_research_brief.browser_session` 正式透传给 heavy frontdoor
        - `CronExecutor` 现已会把 `job.meta.browser_session` 正式透传给 heavy frontdoor
        - 这条改动直接收掉了此前 live 环境里“同样代码，有的 storage file completed、有的却 waiting-login”的关键断点：根因不是研究 loop 假跑，而是 storage-state 选路不稳定
      - `2026-04-19` shared surface owner/checkpoint 合同已镜像到三类 surface：
        - `src/copaw/environments/surface_execution/owner.py` 已正式定义 `ProfessionSurfaceOperationOwner / ProfessionSurfaceOperationPlan / ProfessionSurfaceOperationCheckpoint`
        - browser / document / desktop 三套 `run_step_loop(...)` 现在都接受共享 `owner`，并在 loop result 上正式返回 `operation_checkpoint`
        - 这让“职业 agent 负责决策、surface substrate 负责观察/执行/回读”的边界至少在 shared loop 合同层落成同一套接口，不再只有 browser 一条新链
    - 当前验收口径：
      - `L1/L2`：
        - `python -m pytest tests/environments/test_browser_surface_execution.py -k "generic_upload_page_summary or login_wall_page_summary" -q` -> `2 passed`
        - `python -m pytest tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py -q` -> `56 passed`
        - `python -m pytest tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py tests/kernel/test_tool_bridge.py -q` -> `57 passed`
        - `python -m pytest tests/environments/test_document_desktop_surface_execution.py -q` -> `3 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/research/test_baidu_page_research_service.py tests/kernel/test_tool_bridge.py -q` -> `68 passed`
        - `python -m pytest tests/research/test_chat_continuation_policy.py tests/research/test_chat_continuation_owner.py tests/research/test_baidu_page_research_service.py -q` -> `40 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/environments/test_browser_surface_execution.py tests/research/test_chat_continuation_policy.py tests/research/test_chat_continuation_owner.py tests/research/test_baidu_page_research_service.py tests/kernel/test_tool_bridge.py -q` -> `78 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/environments/test_browser_surface_execution.py tests/research/test_chat_continuation_policy.py tests/research/test_chat_continuation_owner.py tests/research/test_baidu_page_research_service.py tests/kernel/test_tool_bridge.py tests/kernel/test_query_execution_runtime.py -q` -> `109 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/research/test_baidu_page_research_service.py tests/kernel/test_main_brain_research_followup.py -q` -> `41 passed`
        - `python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py -q` -> `31 passed`
        - `python -m pytest tests/environments/test_browser_surface_execution.py -k "guided_owner" -q` -> `2 passed`
        - `python -m pytest tests/environments/test_document_desktop_surface_execution.py -k "guided_owner" -q` -> `2 passed`
        - `python -m pytest tests/agents/test_browser_tool_evidence.py -k "guided_surface" -q` -> `2 passed`
        - `python -m pytest tests/kernel/query_execution_environment_parts/confirmations.py -k "guided_browser_submit or contextual_browser_submit_click" -q` -> `2 passed`
        - `python -m pytest tests/kernel/query_execution_environment_parts/confirmations.py -q` -> `17 passed`
        - `python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/research/test_baidu_page_research_service.py -q` -> `67 passed`
        - `python -m pytest tests/agents/test_browser_tool_evidence.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/research/test_baidu_page_research_service.py tests/kernel/query_execution_environment_parts/confirmations.py -q` -> `121 passed`
        - `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_research_followup.py tests/app/test_source_collection_frontdoor_service.py -q` -> `62 passed`
        - `python -m pytest tests/app/test_runtime_center_research_surface.py tests/app/test_research_session_api.py -q` -> `7 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/research/test_chat_continuation_policy.py tests/research/test_chat_continuation_owner.py tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py tests/research/test_research_knowledge_ingestion.py tests/research/test_research_report_writeback.py tests/kernel/test_main_brain_research_followup.py tests/kernel/test_tool_bridge.py -q` -> `108 passed`
        - `python -m pytest tests/app/test_source_collection_frontdoor_service.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/research/test_chat_continuation_policy.py tests/research/test_chat_continuation_owner.py tests/research/test_baidu_page_research_service.py tests/kernel/test_tool_bridge.py tests/kernel/test_query_execution_runtime.py tests/agents/test_browser_tool_evidence.py tests/kernel/query_execution_environment_parts/confirmations.py -q` -> `177 passed`
        - `python -m pytest tests/agents/test_surface_tool_frontdoors.py tests/agents/test_react_agent_tool_compat.py tests/environments/test_document_desktop_surface_execution.py tests/kernel/query_execution_environment_parts/confirmations.py tests/kernel/test_query_execution_runtime.py -q` -> `69 passed`
        - `python -m pytest tests/agents/test_browser_tool_evidence.py tests/agents/test_surface_tool_frontdoors.py tests/agents/test_react_agent_tool_compat.py tests/environments/test_document_desktop_surface_execution.py tests/kernel/query_execution_environment_parts/confirmations.py tests/kernel/test_query_execution_runtime.py -q` -> `106 passed`
        - `python -m pytest tests/app/test_research_session_live_contract.py -q` -> `2 passed, 1 skipped`
        - `python -m pytest tests/research/test_baidu_page_research_service.py tests/kernel/test_main_brain_research_followup.py tests/app/test_research_session_live_contract.py -q` -> `39 passed, 1 skipped`
        - `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/app/test_source_collection_frontdoor_service.py tests/app/test_runtime_center_research_surface.py tests/app/test_research_session_api.py -q` -> `66 passed`
        - 额外 focused regression：`python -m pytest tests/research/test_baidu_page_research_service.py -k "no_longer_exposes_private_input_selector_helper or shared_browser_service_entry or split_action_and_readback or deep_think_state_scopes" -q` -> `5 passed`
        - active-session continuity focused regression：`python -m pytest tests/app/test_source_collection_frontdoor_service.py -k "forces_reuse_of_active_waiting_login_session_in_same_scope" -q` -> `1 passed`
        - query runtime 读面兼容回归：`python -m pytest tests/kernel/test_query_execution_runtime.py -k "artifact_refs or result_items" -q` -> `1 passed, 30 deselected`
      - `L3`：
        - 已重跑登录门槛 live external-information smoke：`python scripts/live_external_information_chain_acceptance.py --output tmp/live_external_information_chain_acceptance_result.json`
        - 真实结果：`main_brain` 与 `cron` 两条 heavy 入口都真实创建/读取正式 research session，并都稳定落到 `waiting-login`；`/runtime-center/research` 读面同步返回 formal `brief` 与 `writeback_truth.status=pending`
        - `2026-04-19` continuation owner cutover 后已再次重跑同一 live smoke；结果保持不变，说明这轮 shared continuation owner 切线没有把 heavy frontdoor / formal session / Runtime Center waiting-login 读面打断
        - `2026-04-19` 主脑 waiting-login continuation formalization 后已再次重跑同一 live smoke；结果仍稳定落到 `waiting-login`，说明“聊天窗口提示用户登录 -> 记录 formal continuation -> Runtime Center 读到同一 formal session”这条 fail-closed 主链没有被打断
        - 这说明当前真实 live 环境下，“主脑/cron -> heavy research frontdoor -> formal session -> Runtime Center 读面” 这条链在未登录 Baidu 时会 fail-closed 到同一类 `waiting-login` 真相，不再误落模型闲聊
        - `2026-04-19` 共享登录态路由补齐后，已用真实已登录 storage file 再跑 logged-in live smoke：
          - 环境：`COPAW_BAIDU_RESEARCH_STORAGE_STATE_PATH=C:\Users\21492\.copaw\state\research_browser_storage\industry-researcher-live-demo.json`
          - 命令：`python scripts/live_external_information_chain_acceptance.py --output tmp/live_external_information_chain_acceptance_logged_in.json`
          - 真实结果：`main_brain.status=completed`、`cron.status=completed`
          - 同轮结果里，`main_brain.runtime.findings_count=1 / sources_count=1`，`cron.runtime.findings_count=1 / sources_count=5`
        - `2026-04-19` 已继续做 3 轮重复 live smoke（同一共享已登录 storage file）：
          - run1：`main=completed / cron=completed`
          - run2：`main=completed / cron=completed`
          - run3：`main=completed / cron=completed`
          - 这说明 logged-in shared-storage 路由已经不再卡死在 `waiting-login`，主脑和 cron 两条 heavy 入口都能真实走到 completed
      - `L4`：这轮仍不能诚实写成 long soak 完成；虽然已补了 `3` 轮重复 logged-in live smoke，但这还不是完整的长链 soak 口径
    - 当前边界：
      - 这轮已把“provider-specific 执行硬编码”收回为“共享底座 + 薄页面提示”
      - 这轮还额外把“无 profile 页面先读正文/识别登录阻塞”补进了 shared browser substrate；因此通用页面理解不再完全依赖 provider 专用 page profile
      - 这轮现在又进一步补到了“共享页面摘要”这一层：上层不再只能拿原始 `readable_sections`，也能拿一份最小 `page_summary`
      - 这轮也已把“登录页先乱打字”这类机械行为收掉一条：至少在 Baidu chat 这条 profiled live 链上，shared observation 一旦先读到 `login-required`，提交前门会直接 fail-closed
      - shared browser substrate 现已具备最小 submit loop owner，而且 research chat 这条线的高层 `读回答 -> 判断是否继续 -> 生成下一步动作` 也已正式抽成 shared continuation owner；当前 Baidu heavy session 已不再只靠 service 内联 if/else 接下一轮
      - `2026-04-19` 又补上了 shared guided owner 第一版：
        - browser 已有基础 guided planner：`type -> login-wall stop`，有明确 submit cue 时再提交
        - document 已有 `replace_text / write_document` 两条 guided planner 分支
        - desktop 已有 `focus_window -> type_text` guided planner，但前提是存在可解析的 `window_target`
        - 三类 surface 现在都不只接受裸 `planner callable`，也有可复用的 guided owner builder，开始形成“职业 agent 提意图，surface 底座执行通用连续动作”的共享高层基线
      - `2026-04-19` 这条 guided 基线已经不再只停在环境测试：
        - `browser_use` 前门现已正式支持 `action="guided_surface"`
        - `document_surface` 前门现已正式支持 `observe / write_document / replace_text / guided_surface`
        - `desktop_actuation` 前门现已正式支持 `observe / launch / focus / click / type / keys / control-dialog action / guided_surface`
        - `CoPawAgent` built-in toolkit、tool capability catalog、tool execution contract、query-runtime tool mapping 现已同时把 browser / document / desktop 三条 frontdoor 接进正式主链
        - browser 当前会先读页面快照和正文，再走 shared guided owner 决策 `type -> submit`
        - document 当前会先读同一 document thread，再在同一路径上决定 `replace_text / write_document`
        - desktop 当前会先看同一窗口 thread，再按 shared guided owner 决策 `focus_window -> type_text`
        - 遇到 `login-required` 会直接停住并回正式 `guardrail`，而不是盲打
        - query prompt 也已明确提示：普通 chat/form 页优先走 guided surface，不要一上来就手写 selector chase；document thread 也优先沿同一路径继续写
      - heavy research 现在不再只有“未登录 fail-closed”这半边 live 真相；已经同时证明了：
        - 未登录时会稳定落到 `waiting-login`
        - 显式共享已登录 storage state 时，主脑 / cron 两条 heavy live 链都能真实 completed
      - 之前“browser 有正式 guided frontdoor，但 document / desktop 还只是 shared substrate + guided owner 基线，没接成同等级主线”这条真缺口，现已收掉：
        - 三类 surface 现在都各自有模型可直接调用的正式 frontdoor
        - 三类 frontdoor 现在都挂在同一套 `ProfessionSurfaceOperationOwner / Checkpoint` 合同上
        - 这意味着“职业 agent 决策、surface frontdoor 执行、底座观察/回读”这条边界已不再只在 browser 成立
      - 但这轮也不能夸成“所有复杂 surface 任务都已终态”：
        - 当前是三类 surface 都有正式主线 frontdoor，不再缺入口
        - 但 shared high-level planner 仍是第一版，复杂多区块页面理解、分页/上传/结果筛选、跨窗口上下文切换，还要继续补强
      - 当前因此只能诚实声明：
        - “document / desktop 没接成正式主线 frontdoor”这条缺口已完成
        - 这条 frontdoor 升级线已过 `L1/L2`
        - document / desktop 这轮没有新增 `L3/L4` live/soak，不能混写成“所有 surface 的真实长链都已验完”
      - `2026-04-19` 新方向补充：
        - `docs/superpowers/specs/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-design.md` 已写入仓库，正式把下一阶段目标从“更强页面理解器”提升为：
          - `Surface State Graph`
          - `Probe Engine`
          - `Transition Miner`
          - `Capability Twin`
          - `Goal-Conditioned Reward Engine`
        - 这份 spec 的目的不是推翻现有 shared browser/document/desktop substrate，而是在现有 `observe / execute / reobserve / guided owner / evidence` 基线之上，再补“状态编译 + 主动探测 + 状态转移学习 + 能力归并 + 收益排序”
        - `docs/superpowers/plans/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-implementation-plan.md` 已补入仓库，正式把这条新方向拆成可执行施工阶段：
          - `Surface Graph Baseline`
          - `Probe Engine`
          - `Transition Miner`
          - `Capability Twin`
          - `Reward Ranking`
          - `Runtime Center / Knowledge` 读面
        - 当前口径必须写死：
          - 这是正式设计 + 正式实施计划，已写文档
          - 还不是代码已实现
          - 当前验收层级只到文档一致性检查，不得混写成 surface runtime 已闭环升级

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
- `2026-04-16` 补充：unified MCP activation lifecycle 已在当前 worktree 落下第一批正式代码，而不再只停在文档。仓库已新增 `src/copaw/capabilities/activation_models.py`、`src/copaw/capabilities/activation_runtime.py` 与 `src/copaw/capabilities/activation_strategies.py`，把 shared activation status/reason contract 与 canonical `resolve -> read -> remediate -> re-read` orchestrator 固定下来；与此同时，`browser-companion` 已成为第一条真实接线的 host-attached slice：`/capability-market/install-templates/browser-companion/doctor` 继续保持 read-only，新增 `/activate` 作为 bounded write surface，`example-run` 也已改为先走同一 activation plane 再返回读面结果，不再把“无 mounted session”直接甩给用户。focused verification：`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_activation_runtime.py -q` -> `4 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capability_market_api.py -q` -> `53 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/environments/test_cooperative_browser_companion.py -q` -> `13 passed`。当前 worktree 仍需显式使用 `PYTHONPATH=src`，否则本机 editable install 会回退导入主仓 `D:\\word\\copaw\\src`，导致隔离实现与验收失真。
- `2026-04-16` 续补：统一 activation plane 已继续接入真实 capability execution front-door，而不再只存在于 capability market。`CapabilityExecutionFacade` 现在会在 `system:browser_companion_runtime` 前门上优先走 install-template activation slice：direct execution 会复用同一 `browser-companion` activation contract、自动创建/修复 canonical browser session mount，并把 activation truth 作为正式 execution output 返回；blocked path 也会返回 formal activation reason，不再把未知 `system:*` 误落到 learning handler。focused verification：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capabilities_execution.py -q -k "system_browser_companion_runtime_frontdoor_auto_activates or system_browser_companion_runtime_frontdoor_returns_activation_blocker"` -> `2 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_activation_runtime.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/environments/test_cooperative_browser_companion.py -q` -> `127 passed`。
- `2026-04-16` 三层验收续补：host-attached activation slice 现已把 `document-office-bridge`、`host-watchers`、`windows-app-adapters` 正式并进同一 activation plane，并补齐 `/activate`、`example-run -> activate -> reread` 与 shared host-attached execution front-door。当前三层验收结果如下：
  - 单测：`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_activation_runtime.py -q` -> `4 passed`
  - 集成测试：`$env:PYTHONPATH='src'; python -m pytest tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/environments/test_cooperative_browser_companion.py -q` -> `127 passed`
  - 真实 live：在隔离 `COPAW_WORKING_DIR` 下真起 `python -m copaw app`，通过真实 `/api` HTTP 跑 `document-office-bridge activate`、`host-watchers example-run`、`windows-app-adapters example-run`、`browser-companion activate`，然后穿插 `/api/runtime-center/surface` 噪音请求、重启服务、再次读取 template detail 与重复 example-run/activate。live 结果：Round 1 全部成功；重启后 detail 仍保留 canonical `session_mount_id`（`session:desktop:live-doc-1`、`session:desktop:live-watch-1`、`session:desktop:live-win-1`、`session:browser:live-browser-1`），Round 2 的 `document/host-watchers/windows-app-adapters` example-run 仍然 `success`，`browser-companion activate` 仍然 `ready` 且 `auto_heal_attempted=false`，表明重启后走的是 persisted canonical truth 而不是再次虚构 fresh state。
  - 默认 live 环境校正：上述隔离验收工作目录里的 warning 不能外推为默认 `C:\Users\21492\.copaw` 现状。`2026-04-16` 对默认 live 服务执行真实 `GET /api/system/self-check`，返回 `overall_status=pass`；其中 `provider_active_model=pass`（`code998/qwen/qwen3.5-397b-a17b`）、`provider_fallback=pass`（`aliyun-codingplan/kimi-k2.5`）、`desktop_surface_ready=pass`（`desktop_windows` 已安装且启用）。因此，“缺 active/fallback model” 与 “desktop-windows 未安装” 只属于此前隔离验收工作目录的中间态，不代表默认 live 环境当前故障。
- `2026-04-16` 收口补充：`2026-04-16-unified-mcp-activation-lifecycle-design.md` 与 `2026-04-16-unified-mcp-activation-lifecycle-implementation-plan.md` 已同步进入当前 worktree；本轮实现不再只停在 `host-attached`，而是已把文档定义的四类 activation class 全部接进同一 shared activation plane：
  - `host-attached`：`browser-companion / document-office-bridge / host-watchers / windows-app-adapters` 全部支持 read-only `doctor`、显式 `/activate`、`example-run -> activate -> reread`，execution front-door 也会自动复用同一 activation contract。
  - `workspace-bound`：`runtime_contract` 已把 `overlay_scope / overlay_mode / pending_reload / dirty` 收口为 shared activation truth，`mcp:*` execution 与 `/runtime-center/external-runtimes/actions` 现在都能透传 `scope_ref / mcp_scope_overlay / tool_name / tool_args` 并走同一 activation plane，而不是各自读写临时 overlay 语义。
  - `auth-bound`：统一 token/runtime 失败现在先走 refresh/retry，再由 shared taxonomy 决定是否进入 `waiting_human`；不再让各类模板或执行前门自己拼接 `token expired / relogin` 文案。
  - `stateless`：不依赖 environment/session truth 的 MCP runtime 也已统一走 `runtime reconnect -> canonical reread -> ready/blocked`，不再保持独立“运行时恢复”旁路。
- `2026-04-16` focused final matrix 已验证通过：`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_activation_runtime.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/environments/test_cooperative_browser_companion.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_center_external_runtime_api.py -q` -> `173 passed`。这批 focused regression 已覆盖 shared contract、capability-market、execution front-door、runtime-contract、runtime-center HTTP passthrough 与 cooperative browser continuity。
- `2026-04-16` unified lifecycle live acceptance 已补成正式脚本：`$env:PYTHONPATH='src'; python scripts/run_unified_mcp_activation_live_acceptance.py`。该脚本会真起 `python -m copaw app`，在隔离 `COPAW_WORKING_DIR` 下通过真实 localhost HTTP 跑多轮 host-attached/template surface、`mcp:desktop_windows_stateless`、`mcp:desktop_windows_auth` 与 `workspace-bound` overlay front-door，期间主动注入 runtime fault、穿插噪音请求、重启服务后再次复验。最新一轮运行返回 `exit 0`，结果文件落在 `%TEMP%\\copaw-mcp-live-*\\unified_mcp_activation_live_acceptance.json`（例如 `C:\\Users\\21492\\AppData\\Local\\Temp\\copaw-mcp-live-en5euxg1\\unified_mcp_activation_live_acceptance.json`）。
- `2026-04-16` shutdown hygiene 已进一步实修，不再保留前一轮 live acceptance 暴露的两类退出告警：
  - `MCPClientManager` 现在会优先走 stateful client 的正式 `close()` 合同，并按 LIFO 关闭 client map，不再拆 `process.aclose / stack.aclose` 这类内部句柄来做 shutdown；对应 focused regression 已收口到 `tests/app/test_mcp_runtime_contract.py`
  - `BrowserRuntimeService` 已进入 `RuntimeManagerStack` 正式 stop 链，并新增 `shutdown()`；local browser stop 现在会等待 idle watchdog cancellation 完成，再关闭 Playwright/browser，不再只靠 `atexit`
  - fresh regression：`$env:PYTHONPATH='src'; python -m pytest tests/capabilities/test_activation_runtime.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/environments/test_cooperative_browser_companion.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_bootstrap_helpers.py -q` -> `212 passed`
  - fresh live：`$env:PYTHONPATH='src'; python scripts/run_unified_mcp_activation_live_acceptance.py` -> `exit 0`，且不再打印此前那两类 `cancel scope` / `_idle_watchdog` / Playwright pending-task 告警
  - 当前 live 输出里剩余的是三方依赖告警（如 `websockets` deprecation、`numexpr` 信息日志），不属于本仓 activation/shutdown 主链未收口
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

### 3.3 `2026-04-06` 闭环真实性回归补充

- `HumanAssistTask` 验收合同已完成本轮正式修复：
  - `verify_task()` 现在会先物化真实 `submitted` 快照，再进入 `verifying`
  - `evidence_verified` 现在必须有正式 `verification_evidence_refs`
  - `state_change_verified` 现在必须满足配置的状态合同路径
  - evidence ledger 写入失败不再静默接受；现在会回退到验证前状态并返回 `verification_record_failed`
- `Runtime Center` 行业详情 focus query 已收紧到 canonical 边界：
  - `/runtime-center/industry/{instance_id}` 现在只接受 `assignment/backlog` focus
  - `report/lane/cycle` 与其他非 canonical focus 不再由 route 层注入伪 truth
  - `industry/service_runtime_views.py` 允许展示选中的 assignment/backlog detail，但不再借此伪造 `execution.current_focus_*`
- industry lifecycle 的 legacy seam 当日 partial 记录已过时：
  - 该段仅保留为施工轨迹；当前 authoritative status 以后文 `3.3.2 2026-04-06 authoritative closure update` 为准
  - 当前真实状态：kickoff / auto-resume 已切离 legacy `goal/schedule`，`goal_ids / schedule_ids / active_goal_ids` 的正式运行期平行真相源已物理删除
- acquisition decision / producer 收口已完成：
  - `Runtime Center` approve/reject、learning review-gate、producer-side identity 现统一走 kernel-backed dispatcher / governed mutation 主链
  - runtime-center actor route 的 acquisition 专属 fallback 已删除；当 kernel task 缺失时会显式返回 `404`
- capability execution 前门本轮新增一条真实收口：
  - `POST /runtime-center/external-runtimes/actions` 现在已改成 `kernel dispatcher submit -> execute_task`
  - 该路由会继承 capability mount 的正式 `risk_level`，`waiting-confirm` 不再偷跑执行
  - focused verification：
    - `python -m pytest tests/app/test_runtime_center_external_runtime_api.py -q` -> `4 passed`
    - `python -m pytest tests/app/test_capabilities_execution.py -k "external_runtime or runtime_center" -q` -> `1 passed, 49 deselected`
  - 当前诚实边界：
    - 这只代表 external runtime action 这条前门已收住
    - query-time delegate / react-agent builtin fallback / system dispatch 仍是下一轮 capability front-door 收口重点
- 本轮重新执行并确认通过的正式验证：
  - `PYTHONPATH=src python -m pytest tests/state/test_human_assist_task_service.py -q` -> `15 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_runtime_human_assist_tasks_api.py -q` -> `14 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_learning_api.py -q` -> `12 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_api.py -q` -> `105 passed`
  - `PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q` -> `83 passed`
  - `PYTHONPATH=src python -m pytest tests/industry/test_runtime_views_split.py -q` -> `12 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q` -> `11 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_operator_runtime_e2e.py -q` -> `9 passed`
  - `PYTHONPATH=src python -m pytest tests/app/test_runtime_canonical_flow_e2e.py -q` -> `4 passed`
  - `PYTHONPATH=src python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -q` -> `38 passed`
  - `python -m pytest tests/app/test_industry_service_wiring.py::test_kickoff_execution_from_chat_records_trigger_message_context_in_assignment_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch tests/app/industry_api_parts/kickoff_fixed_sop.py::test_industry_chat_kickoff_executes_in_background_without_blocking_response tests/app/industry_api_parts/kickoff_fixed_sop.py::test_industry_chat_kickoff_background_reuses_team_projection_instead_of_rematerializing_it_per_goal tests/app/industry_api_parts/retirement_chain.py::test_industry_chat_kickoff_executes_in_background_without_blocking_response tests/app/industry_api_parts/retirement_chain.py::test_industry_bootstrap_auto_activate_enters_live_coordinating_contract tests/app/industry_api_parts/retirement_chain.py::test_industry_runtime_main_chain_exposes_live_assignment_chain_after_auto_activate -q` -> `7 passed`
  - `npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/routes/resolveSelectedKey.test.ts src/layouts/Sidebar.test.tsx src/pages/Settings/System/index.test.tsx` -> `19 passed`
  - `npm --prefix console run build` -> `通过`
- 本轮验证边界说明：
  - `tests/app/test_phase_next_autonomy_smoke.py` 与 `tests/app/test_runtime_canonical_flow_e2e.py` 并行执行时在 `124s` 超时；串行重跑后通过，因此不能把并行超时误写成流程断裂
  - 上述结果证明“当前代码基线 + 正式回归命令”已通过，不自动等于默认外部 live e2e；除非单独标注 live/opt-in，否则都按仓库内回归理解

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
- `2026-04-15` 补充：reset 脚本已加默认安全护栏；默认只清 `memory/qmd`，`state/evidence/learning` 三个主 runtime 库必须显式 `--force` 才允许删除，相关回归 `tests/app/test_runtime_reset.py tests/app/test_runtime_lifecycle.py tests/app/test_startup_recovery.py -q` 已通过 `32 passed`
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
- researcher 作为研究支援位持续回流；没有正式 brief / monitoring task 时不应空跑
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
- `2026-04-01` 补充：researcher follow-up continuity 已继续补厚到“follow-up backlog 物化 assignment 后仍保住 execution-core continuity 合同”。`service_lifecycle` 现会把 `control_thread_id / session_id / environment_ref / work_context_id / supervisor_* / requested_surfaces / recommended_scheduler_action` 从 follow-up backlog 正式持久化进 assignment metadata；`service_report_closure` 也会优先使用最新 report 的 `work_context_id`，不再让旧 assignment metadata 把新工作上下文盖掉。这条 continuity 现在只服务已经被正式创建的研究任务或监控任务，不再依赖默认 researcher loop。
- `2026-04-01` 补充：`AgentWorkbench` 前台已停止展示 `GoalSelector / GoalDetailPanel`，也不再主动请求 `/goals/{goal_id}/detail`；执行条文案已把 `目标` 收成 `焦点`，`Predictions` 里的 `目标状态面 / 目标 delta` 也已改成 `焦点` 口径，避免继续把 operator 拉回旧 `goal-era` 心智。
- `2026-04-01` 补充：`P0-4` 已新增正式 gate 入口 `scripts/run_p0_runtime_terminal_gate.py`，把后端主链回归、长跑与删旧回归、控制台定向回归和控制台构建收口成一个仓库级可执行门槛；`scripts/README.md` 已同步写明用法。
- `2026-04-01` 补充：`Knowledge Activation Layer Phase 4` 已补上最小 persisted relation-view 边界。`MemoryRelationViewRecord`、SQLite-backed `memory_relation_views`、`SqliteMemoryRelationViewRepository` 与 runtime bootstrap wiring 已落地；`DerivedMemoryIndexService` 已具备显式 `list_relation_views(...) / rebuild_relation_views(...)`；`Runtime Center` 也已新增 `GET /runtime-center/memory/relations` 读面，并支持按 `scope / relation_kind / source_node_id / target_node_id` 过滤。
- `2026-04-14` 补充：formal text memory 第二轮收口已真实落地。`MemoryRetainService` 现统一通过 `text_memory_policy` 做 selective ingestion 与 scope routing：低价值 chat noise 不再进入正式记忆，工作连续性文本优先落 `work_context`，共享行业知识优先落 `industry`。
- `2026-04-14` 补充：`recall / activation / Runtime Center memory surface` 现统一走 `retrieval_budget`，按固定 related-scope 顺序 `work_context -> task -> agent -> industry -> global` 读取，并施加显式 fetch budget；formal durable text memory 也已补上 `canonical_compaction`，重复稳定文本 anchor 会合并成 canonical 内容，不再无限 append。
- `2026-04-14` 补充：旧 `src/copaw/agents/memory/memory_manager.py` 兼容壳已物理删除；`agents.memory` 不再导出该别名，runtime/agent/hook 现统一只认 `ConversationCompactionService`。它现在只负责私有会话压缩，不再承担正式记忆写入或召回职责。
- `2026-04-14` 补充：旧 `memory_fact_index` 历史库自动补列/自动升级也已退出正式支持面；当前基线只保证 fresh canonical state schema。若本地还残留旧 memory db，按“删库重建”处理，不再继续扩写这条兼容链。
- `2026-04-14` 补充：memory 正式操作面又收了一刀。`POST /runtime-center/memory/rebuild` 现在会在同一条 operator rebuild 链里自动连带 `relation views` 重建，并把 `relation_view_count` 回给前端；`GET /runtime-center/memory/surface` 也已成为 activation + relation 的正式聚合读面，Knowledge 页不再只能靠零散 payload 拼读。
- 硬边界：persisted relation view 仍然只是 derived-only read model，来源仍是 `MemoryFactIndexRecord + MemoryEntityViewRecord + MemoryOpinionViewRecord` 的派生组合，不是第二真相源，也不是 graph-native 写入主链；本轮新增的是统一 rebuild/read surface，不是第二套 memory truth。

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

`2026-04-06` 真实性校正：

- 本节“当前已闭环”只表示“当前代码基线 + 指定回归已通过”，不自动等于默认真实外部 live e2e。
- 除非测试明确标注为 live/opt-in 并单独核实，否则应按仓库内 default/focused regression 理解。
- 具体回归命令和最新通过结果以 `3.3 2026-04-06 闭环真实性回归补充` 为准。

1. `Full Host Digital Twin`
   - 当前已闭环：`Seat Runtime / Workspace Graph / Host Event Bus / host_twin` 已成为正式运行边界；`runtime query / workflow preview-run-resume / cron / fixed-SOP / Runtime Center` 已统一优先消费 canonical `host_twin_summary`；`host_twin` 也已正式派生 multi-seat `candidate_seats / selected_seat_ref / selected_session_mount_id`，并在同 scope alternate ready seat 可用时切换 canonical host truth。`browser / desktop / document` 三类执行位现都已进入同一条 host-aware 消费链，workflow run detail 与 fixed-SOP run detail 也会显式带出 `host_requirement`。
   - 终态标准：所有执行入口都只认一套 canonical `host_twin` 真相；`workflow / cron / fixed-SOP / Runtime Center / industry runtime` 对 `selected_seat_ref / selected_session_mount_id / host_requirement / legal_recovery` 使用同一宿主口径；多 seat / 多 agent 并发时系统能稳定判定 writer ownership、handoff、recovery、resume 与 host switch；browser / desktop / document / app-family twins 都纳入同一宿主真相；并有长时间 live smoke 证明切换、重入、回放和证据连续性不会断。
2. `single-industry` 真实世界覆盖
   - 当前已闭环：`strategy -> lane -> backlog -> cycle -> assignment -> report -> synthesis/replan` 已成正式主链；failed-report follow-up 已能继承 `source_report_ids / supervisor continuity / control_thread / session / environment / recommended_scheduler_action`，并在 focused runtime 中优先回到当前执行焦点，`replan` 也不会在 cycle rollover 后静默丢失。治理层创建的 host-handoff `HumanAssistTask` 现在也会继承同一条 `work_context / environment / recovery / requested_surfaces` continuity，上游宿主回执与下游 resume 会继续沿着同一控制线程和同一恢复上下文闭环，而不再掉出原行业主链。
   - 终态标准：单个行业实例能稳定连续跑多个周期；`staffing + handoff + human assist + report + synthesis + replan` 能形成长期闭环；supervisor / manager / researcher / operator 的职责切换和协作关系在长跑里不掉线；browser / desktop / document 执行位能接入同一行业闭环；报告、证据、决策和重规划都能回流到同一主链，并有真实世界长跑 smoke 证明其稳定性。
3. 主脑 cockpit / `Unified Runtime Chain`
   - 当前已闭环：`/runtime-center/main-brain` 已成为 dedicated main-brain cockpit contract，`Runtime Center` main-brain panel 现在会把 `carrier / strategy / lanes / backlog / cycle / assignment / report / environment / governance / recovery / automation / evidence / decision / patch` 放进同一驾驶舱，并形成 `Execution Envelope / Operator Closure / Trace Closure` 三段闭环；`/runtime-center/industry/{instance_id}` 当前只支持 `assignment/backlog` canonical focus drill-down，`/runtime-center/reports` 也已支持按 `industry / assignment / lane / cycle / needs_followup / processed` 过滤。
   - 终态标准：前台不是 detail 堆叠页，而是统一运行中心；上述核心对象都能在一个驾驶舱里被看见、被关联、被追踪；驾驶舱不只展示结果，还能承载治理、调度、恢复、证据追踪与 patch/decision 闭环；主脑对象、执行对象、证据对象之间的关系前台可直接看清；重要运行真相不再藏在日志、内部状态或零散 detail 里，也不再出现第二套平行执行器。
4. 宽回归与 `live smoke`
   - 当前已闭环：关键 `industry / runtime / workflow / fixed-SOP / host-aware` 主链已进入聚合回归；`tests/app/test_phase_next_autonomy_smoke.py`、`tests/app/test_runtime_human_assist_tasks_api.py`、`tests/app/runtime_center_api_parts/overview_governance.py` 与 `tests/app/runtime_center_api_parts/detail_environment.py` 继续作为正式聚合回归护栏，`python scripts/run_p0_runtime_terminal_gate.py` 也已成为单入口 gate。这里的“已闭环”应理解为当前仓库内回归矩阵已通过，不应直接写成外部真实世界 live smoke 全量完成。
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
   - `2026-04-03` durable automation/runtime follow-up 又收了一刀：`AutomationLoopRuntimeRecord + automation_loop_runtimes` 已正式进入 state/bootstrap/runtime lifecycle，automation loop heartbeat/blocked/submitting/result/failure/stop 都会写持久化 snapshot，重启后也会先从正式 repo 复水；`/runtime-center/main-brain` 与 `/system/self-check` 现会优先消费 persisted automation loop snapshot，并把 loop degraded/failed 真正上卷到 automation/status 与顶层 surface/status。与此同时，`cron agent` 已补上 shared durable request contract：`CronExecutor` 现在会为 agent cron 归一化 `request / request_context / main_brain_runtime / work_context_id`，workflow 自动生成的 cron spec 也会把 `control_thread_id + entry_source + main_brain_runtime.environment` 一起写进正式 schedule spec，不再只有 host meta。`latest_recovery_report` 也不再只是 startup alias：`EnvironmentService.run_host_recovery_cycle(...)` 已成为运行期 recovery producer 边界，会同步写出 canonical latest recovery report，并通过 app-state sink + runtime read resolver 让 `/runtime-center/recovery/latest`、`Runtime Center` recovery card 与 `/system/self-check` 优先读取运行期最新恢复结果；此前悬空的 capability candidate service contract 也已补成正式 `CapabilityCandidateService`，避免 capability market / prediction 测试再因为候选能力服务缺口中断。Focused 验证：`$env:PYTHONPATH='src'; python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py -q -k "capability_candidates or skill_candidate_service"` -> `4 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_cron_executor.py tests/app/test_runtime_center_events_api.py tests/app/test_workflow_templates_api.py tests/app/test_capabilities_execution.py -q -k "cron_executor or runtime_recovery_latest or workflow_template_service_launch_materializes_run or host_recovery"` -> `9 passed`；`$env:PYTHONPATH='src'; python -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_lifecycle.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_system_api.py -q -k "rehydrates_persisted_loop_state or latest_recovery_report or automation_degraded or runtime_summary or prefers_environment_runtime_recovery_report"` -> `5 passed`。
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
   - `2026-04-14` execution-discipline 纠偏补充：此前文档把这条尾巴写早了；实际代码直到本日才真正切掉 `industry/service_team_runtime.py` 里 `goal_id / goal_title -> current_focus_kind="goal"` 这段 idle runtime 焦点写入。现在 bootstrap、lifecycle refresh 与 cleanup backfill 虽仍沿用 legacy 参数名进入 shared runtime sync，但 live runtime metadata 已不再把空闲职业 agent 持久化成 `goal` 焦点，正式 contract 仍只剩 `current_focus_kind / current_focus_id / current_focus`。同日也一并去掉了默认 system agent profile 上静态 `current_focus_kind="goal"` 的展示占位，`/runtime-center/surface` 与 `/runtime-center/agents` 现在只保留摘要文本，不再把系统 agent 误标成 `goal` 焦点。fresh 验证：`python -m pytest tests/app/industry_api_parts/runtime_updates.py -q` -> `48 passed`；`python -m pytest tests/kernel/test_agent_profile_service.py -q` -> `16 passed`；`python -m pytest tests/app/test_runtime_canonical_flow_e2e.py -q` -> `6 passed`；live bootstrap probe 也确认 idle role 与默认 system agent 的 `current_focus_*` 口径已符合预期。
   - `2026-04-14` execution graph projection 纠偏补充：此前文档把“execution 主链已经闭环”写得过满，真实遗漏点不是 `backlog/cycle/assignment/report/work_context` 没有 canonical truth，而是这些 canonical truth 没有稳定投影进 formal memory graph。也就是说，执行链本身能跑，但 graph 里长期只稳定覆盖了 `report/evidence/finding/recommendation`、`runtime_outcome failure/recovery` 与部分 human-boundary，缺少 `backlog / cycle / assignment / work_context` 节点以及 `backlog->cycle`、`backlog->assignment`、`assignment->cycle`、`assignment->work_context`、`assignment->report`、`report->work_context`、`runtime_outcome->work_context` 这些正式关系。当前修正口径已收死为：1) raw execution graph projection owner 下沉到 `state` canonical services；2) `work_context` 成为一等 graph node；3) link 迁移时显式失效旧关系，不允许 graph 永久残留旧链；4) `report_synthesis` 不再拥有 raw report graph writeback，只保留 synthesis/replan 摘要职责。落地后必须至少重新通过：`python -m pytest tests/memory/test_knowledge_writeback_service.py tests/memory/test_knowledge_graph_service.py tests/state/test_execution_graph_projection_services.py -q`、`python -m pytest tests/industry/test_report_synthesis.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_bootstrap_helpers.py -q`。
   - `2026-04-14` execution graph projection 落地补充：上述纠偏已真实落到当前主线代码，而不是只停在文档。`KnowledgeWritebackService` 现已补齐 `cycle / backlog / assignment / work_context / report / runtime_outcome` 的 formal graph projection 与 stale relation invalidation；`KnowledgeGraphService` 已对外暴露 canonical projection helper；`BacklogService / OperatingCycleService / AssignmentService / AgentReportService / WorkContextService` 已在 canonical mutator 上自动触发 graph projection；runtime bootstrap/domain wiring 也已把同一个 `KnowledgeGraphService` 注入这些 canonical services；`report_synthesis` 已移除 raw report graph writeback owner，只保留 synthesis/replan 读面职责。fresh 验证已通过：`python -m pytest tests/memory/test_knowledge_writeback_service.py tests/memory/test_knowledge_graph_service.py tests/state/test_execution_graph_projection_services.py tests/industry/test_report_synthesis.py -q` -> `28 passed`；`python -m pytest tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_bootstrap_helpers.py tests/state/test_memory_services.py tests/state/test_sqlite_repositories.py tests/industry/test_service_report_closure.py tests/app/test_industry_service_wiring.py -q` -> `81 passed`；`python -m pytest tests/kernel/test_execution_knowledge_writeback.py tests/state/test_reporting_service.py -q` -> `13 passed`；`python -m pytest tests/app/test_startup_recovery.py tests/app/test_runtime_center_memory_api.py -q` -> `20 passed`；`tests/app/industry_api_parts/bootstrap_lifecycle.py` 54 条与 `tests/app/industry_api_parts/runtime_updates.py` 48 条已按分批 nodeid 全量跑通；`python -m pytest tests/app/test_buddy_onboarding_activation.py tests/kernel/test_buddy_onboarding_service.py -q` -> `24 passed`；`python -m pytest tests/kernel/test_execution_knowledge_writeback.py -q` -> `4 passed`；`git diff --check` -> 通过。
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

### 3.3.11 `2026-04-20` active surface state graph / twin / reward chain closure

- 对应文档：
  - `docs/superpowers/specs/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-design.md`
  - `docs/superpowers/plans/2026-04-19-active-surface-state-graph-capability-twin-and-reward-engine-implementation-plan.md`
- 当前这条线已经完成的正式对象与主链：
  - `Task 1-4` 已完成：`surface_graph / probe / discovery / transition` 已接到 browser / document / desktop 正式 execution contract，并通过统一 `EvidenceRecord.kind` 写入 `surface-probe / surface-discovery / surface-transition`
  - `Task 5` 已完成：`SurfaceCapabilityTwinRecord / SurfacePlaybookRecord`、对应 SQLite schema / repository、runtime bootstrap projection 已落地
  - `Task 6` 已完成：`transition/discovery -> twin/playbook -> reward` 正式写链已接入 `LearningService`，并在写入后 `mark_dirty(...)` 对应 scope snapshot
  - `Task 7` 已完成：query prompt、main-brain scope snapshot、Runtime Center memory / knowledge 后端读链已统一读取 active playbook / reward ranking / latest surface evidence
  - `Task 8` 已完成：Knowledge 全量读面、Runtime Center 摘要读面和 stale-response 防护已落到正式前端读面与测试
  - `Task 9` 已完成：新增 gated `tests/app/test_surface_graph_live_smoke.py` 与 `tests/app/test_surface_graph_soak.py`，不再拿不存在的 live 命令冒充验收
- 本轮 fresh verification 口径：
  - `L1/L2` backend：
    - `python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py tests/state/test_state_store_migration.py tests/state/test_sqlite_repositories.py tests/state/test_surface_learning_repository.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_scope_snapshot_service.py tests/app/test_learning_api.py tests/app/test_runtime_center_knowledge_api.py tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_surface_learning_api.py tests/app/test_phase2_read_surface_unification.py tests/app/test_surface_graph_live_smoke.py tests/app/test_surface_graph_soak.py -q -rs`
    - 当前结果：`215 passed, 4 skipped`
  - `L1/L2` console：
    - `cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
    - 当前结果：`34 passed`
  - `L3` live smoke：
    - `$env:COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE='1'; python -m pytest tests/app/test_surface_graph_live_smoke.py -q -rs`
    - 当前结果：`4 passed`
  - `L4` long soak：
    - `$env:COPAW_RUN_SURFACE_GRAPH_SOAK='1'; python -m pytest tests/app/test_surface_graph_soak.py -q -rs`
    - 当前结果：`2 passed`
- 当前诚实边界：
  - 这代表 `2026-04-19 active surface state graph / capability twin / reward engine` 这条 spec，按当前 implementation plan 已闭环到 `L1 + L2 + L3 + L4`
  - 这不等于“任意职业 agent / 任意页面 / 任意窗口 的统一高层 planner 已全部完成”
  - document / desktop 这轮完成的是 shared substrate + graph/probe/transition/twin/reward/read-chain 闭环，不应外推成所有职业场景都已做完

## 9. 给下一位 agent 的一句话提醒

先确认你现在做的是哪条收口线：

- single-industry autonomy
- main-brain cognitive closure
- main-brain chat performance / split-chain hardening
- media / memory 闭环

如果答不出来，就不要下手改代码。

### 3.3.1 `2026-04-06` ????????????? partial ???

- industry kickoff / auto-resume ? legacy seam ????????
  - `kickoff_execution_from_chat(...)` ???? `started_goal_ids / started_goal_titles / resumed_schedule_ids / resumed_schedule_titles`
  - `_should_auto_resume_execution_stage(...)` ? `_reconcile_kickoff_autonomy_status(...)` ??? legacy `goal/schedule` ?? execution-stage admission truth
  - `service_activation.py` ??? bootstrap auto-learning ? kickoff legacy goal dispatch ?????
- acquisition producer / kernel identity ????????
  - `learning/acquisition_runtime.py` ???? free-form `DecisionRequestRecord / TaskRecord` ?? producer fallback
  - acquisition proposal ???? kernel dispatcher-backed task store??? dispatcher ????????????? legacy compatibility path
- capability execution ??????????????
  - query-time builtin tool delegate ???? child kernel task `submit -> execute_task` ??????
  - `react_agent` builtin tool delegate ??????????????? raw builtin ??
  - `system_dispatch` ???? `skip_kernel_admission=True`???? turn executor ? failure status ????? kernel
- ???? focused / file-level verification?
  - `python -m pytest tests/app/test_learning_api.py tests/app/test_runtime_center_api.py -q` -> `122 passed`
  - `python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/dispatch.py tests/kernel/query_execution_environment_parts/lifecycle.py -q` -> `58 passed`
  - `python -m pytest tests/app/test_capabilities_execution.py -k "system_dispatch_query or external_runtime or runtime_center" -q` -> `3 passed, 48 deselected`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py::test_public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_chat_writeback_schedule_creation_does_not_expand_instance_schedule_truth tests/app/industry_api_parts/retirement_chain.py::test_industry_runtime_main_chain_exposes_live_assignment_chain_after_auto_activate -q` -> `3 passed`
- ????????????????
  - `goal_ids / schedule_ids / active_goal_ids` ??????????????????????? kickoff / auto-resume / acquisition / capability front-door ?????????? legacy ??
  - ???????????????????????focused harness??????live smoke???????

### 3.3.2 `2026-04-06` authoritative closure update

- 上面 `3.3.1` 的同日 `partial` 记录已过时；当前权威状态以后续本节为准。
- industry kickoff / auto-resume 主链已切离 legacy `goal/schedule` 依赖；assignment/backlog/cycle 已成为正式前门真相。
- acquisition producer / decision / review-gate 已统一到 kernel-backed identity；prediction 与 runtime-center 的 lifecycle mutation 现在都通过 governed mutation / kernel admission 执行。
- capability execution 前门已继续硬切：query-time builtin tool delegate、`react_agent` builtin fallback、capability-market install-template assignment、prediction capability retirement recommendation 已全部接入统一治理前门。
- 兼容字段物理删除已完成：`IndustryInstanceRecord.goal_ids / schedule_ids`、`StrategyMemoryRecord.active_goal_ids / active_goal_titles`、`OperatingCycleRecord.goal_ids`、`WorkflowRunRecord.goal_ids / schedule_ids`、`ReportRecord.goal_ids` 已从 state model / schema / sqlite repository / runtime consumer 删除。
- 当前仍能搜索到的相关字面量只剩：
  - `tests/state/test_state_store_migration.py` 的旧 schema reset fixture；
  - `paused_schedule_ids` 这类与本轮删旧无关的 governance 控制字段。
- 本轮权威验证矩阵：
  - `python -m pytest tests/app/test_predictions_api.py tests/app/test_workflow_templates_api.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/runtime_center_api_parts/overview_governance.py tests/industry/test_runtime_views_split.py tests/state/test_strategy_memory_service.py tests/state/test_sqlite_repositories.py tests/app/test_industry_service_wiring.py tests/state/test_main_brain_hard_cut.py tests/app/test_goals_api.py tests/app/test_runtime_chat_media.py tests/app/test_startup_recovery.py tests/app/industry_api_parts/bootstrap_lifecycle.py::test_public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch tests/app/industry_api_parts/bootstrap_lifecycle.py::test_chat_writeback_schedule_creation_does_not_expand_instance_schedule_truth tests/app/industry_api_parts/runtime_updates.py::test_industry_list_instances_hides_empty_placeholder_records tests/app/industry_api_parts/runtime_updates.py::test_industry_list_instances_uses_lightweight_summary_without_detail_build tests/app/industry_api_parts/runtime_updates.py::test_industry_instance_status_reconciles_from_goal_states tests/app/industry_api_parts/runtime_updates.py::test_industry_instance_status_completes_with_static_team_membership_only tests/app/industry_api_parts/runtime_updates.py::test_industry_detail_backfills_execution_core_identity_with_delegation_first_defaults -q` -> `242 passed`

### 3.3.3 `2026-04-07` final-purity follow-up

- industry bootstrap `auto_dispatch` 已从 activation write-path 切到 assignment dispatch 前门；bootstrap response 不再把 goal dispatch 当作现役执行语义。
- workflow schedule step 已不再依赖持久化的 `linked_schedule_ids` 才能恢复/展示；run detail 与 resume 现在优先从 deterministic schedule identity 推导 runtime 资源。
- workflow goal step 在存在 `linked_task_ids / linked_decision_ids / linked_evidence_ids` 时，不再为了 resume 强行回填 legacy `linked_goal_ids`；只有在完全没有 runtime context 时才会重建 goal link 兜底。
- 本次追加 focused verification：
  - `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q` -> `43 passed`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch or public_bootstrap_auto_dispatch_materializes_assignment_tasks_without_goal_dispatch or kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch or run_operating_cycle_dispatches_materialized_execution_assignment or run_operating_cycle_auto_dispatch_keeps_assignment_formal_planning_in_compiled_task or run_operating_cycle_auto_dispatch_uses_assignment_checklist_instead_of_generic_steps" -q` -> `6 passed, 38 deselected`
  - `python -m pytest tests/app/test_workflow_templates_api.py -k "launch_materializes_run or run_step_detail_stays_read_only_and_service_resume_rehydrates_missing_links or step_detail_prefers_persisted_task_links_over_legacy_goal_links or resume_uses_persisted_runtime_context_without_rehydrating_legacy_links" -q` -> `4 passed, 24 deselected`
  - `python -m pytest tests/state/test_reporting_service.py -q` -> `8 passed`
  - `python -m pytest tests/app/test_predictions_api.py -k "create_list_and_detail or consume_strategy_trigger_rules_into_signals_and_recommendations or recommend_schedule_copy_points_to_fixed_sop_instead_of_workflow_templates or collects_industry_tasks_without_goal_anchor or reporting_surface_prediction_metrics" -q` -> `5 passed, 13 deselected`
  - `cmd /c npm --prefix console run test -- src/pages/Insights/presentation.test.ts` -> `1 passed`

### 3.3.4 `2026-04-07` residual-audit clarification

- 仍然成立的残留判断：
  - `industry` 域仍未完全纯化；残留主要在 bootstrap seed、统计视图、cleanup/archive、历史桥接，不在 runtime kickoff / auto-resume 前门。
  - reporting / prediction 已经是 task-first / industry-first / focus-first，但仍保留从 task 派生 goal 语义的次级分析链。
  - workflow 仍保留 `linked_goal_ids / linked_schedule_ids` 作为历史关联语言；它们不是当前 live main-chain truth。
  - `runtime_service_graph.py` + `runtime_bootstrap_models.py` 的手工 wiring graph 仍然偏重。
- 已经过时、不应继续复述的判断：
  - `README.md` 仍在强调 `goal-first execution`。
  - `service_activation.py` 仍通过 legacy goal dispatch 驱动 bootstrap `auto_dispatch`。
  - workflow schedule step 必须依赖持久化 `linked_schedule_ids` 才能恢复。
  - workflow resume 会无条件回填 legacy `linked_goal_ids`。

### 3.3.5 `2026-04-07` public-surface / prediction fallback follow-up

- prediction task collection 在已有 `industry_instance_id` task truth 时，已不再继续退回 `goal_ids` task query；`goal` 现在只保留为缺少 primary task anchor 时的次级兜底语义。
- workflow run / step 的公开序列化面已隐藏 `linked_goal_ids / linked_schedule_ids`；历史 link 仍保留在内部模型里供 step drill-down / compatibility 使用，但不再作为前台默认读面词汇。
- 本次追加 focused verification：
  - `python -m pytest tests/app/test_predictions_api.py::test_prediction_service_does_not_fallback_to_goal_id_queries_when_industry_tasks_exist -q` -> `1 passed`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_run_public_surface_hides_historical_goal_schedule_id_fields -q` -> `1 passed`
  - `python -m pytest tests/app/test_workflow_templates_api.py -k "run_step_detail_stays_read_only_and_service_resume_rehydrates_missing_links or step_detail_prefers_persisted_task_links_over_legacy_goal_links or resume_uses_persisted_runtime_context_without_rehydrating_legacy_links" -q` -> `3 passed, 26 deselected`

### 3.3.6 `2026-04-07` main-brain internal exception absorption closure

- 主脑内部异常吸收这一轮已正式落成同一条后台 truth chain，不新增 incident 子系统：
  - `MainBrainExceptionAbsorptionService` 继续只扫描现有 `AgentRuntimeRecord + mailbox + HumanAssistTask`。
  - `ActorSupervisor.snapshot()` / startup recovery / Runtime Center / 主脑聊天现在统一消费同一份 derived absorption summary。
- Runtime Center 主脑卡与主脑聊天 prompt 已收口成主脑口径：
  - 主脑卡会在存在内部异常压力时优先显示 shared absorption summary，并带 `exception_absorption` 结构化 meta。
  - 主脑聊天 scope snapshot 会带 `## 主脑异常吸收`，但不再把 `writer-contention` / `waiting-confirm-orphan` 这类低层 case 名直接暴露到前台口径。
- 结构性升级已补齐正式 escalation 落点，而不是自由文本告警：
  - `ReportReplanEngine.compile_exception_absorption_replan(...)` 会把重复同 scope blocker 这类结构性压力提升成正式 `cycle_rebalance / lane_reweight / follow_up_backlog` replan shell。
  - `HumanAssistTaskService.build_exception_absorption_contract(...)` 会把确实需要人的最终一步编成正式 human-assist contract，而不是 ad hoc 文案。
  - `MainBrainExceptionAbsorptionService.absorb(...)` 继续只在上述两个正式输出之间做 bounded 选择，不新增第二套 incident truth。
- 这轮把“typed output 还没接成运行时副作用”的残口正式收掉了：
  - runtime bootstrap 现在会真实实例化并注入 `MainBrainExceptionAbsorptionService`，不再只停留在单测构造。
  - `ActorSupervisor` 轮询与失败路径现在会在同一份 derived scan 之后调用 `absorb(...)`：
    - `replan` 走正式 runtime event 投影
    - `human-assist` 只会在解析到连续性锚点（尤其 `chat_thread_id/control_thread_id`）时，落成正式 `HumanAssistTask`
    - 锚点缺失时不会伪造 closure，只记录 `materialized=false` 的吸收动作结果
  - startup recovery 也复用同一套 absorb/materialize 纪律，并把结果回写到同一份 `StartupRecoverySummary`，不再只留一句摘要
- 本轮 focused verification：
  - `python -m pytest tests/kernel/test_main_brain_exception_absorption.py tests/kernel/test_actor_supervisor.py tests/kernel/test_actor_mailbox.py tests/app/test_startup_recovery.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_main_brain_chat_service.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py -q` -> `181 passed`
  - `python -m pytest tests/kernel/test_main_brain_exception_absorption.py tests/kernel/test_actor_supervisor.py tests/kernel/test_main_brain_chat_service.py tests/app/test_startup_recovery.py tests/app/runtime_center_api_parts/overview_governance.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_execution_provider_wiring.py -q` -> `225 passed`

### 3.3.6 `2026-04-07` final residual purity tightening

- `industry` 状态与删除链继续去 legacy bridge：
  - instance status 现在只以 live `cycle/backlog/assignment/report/schedule` surface 判定 active，不再依赖 goal status 才能把“静态 team + 无 live work”的实例收口为 completed。
  - instance delete / retire 的 task 收集现在优先按 `industry_instance_id`，并把 goal-linked leaf task 并入同一 task set；execution-core 自有 task 即使没有 `goal_id` 也不会再被清理链漏掉。
- reporting / prediction 继续去 goal 次级前门：
  - prediction task collection 已彻底删除 `goal_ids` query fallback，正式顺序收口为 `industry_instance_id -> owner_agent_id -> agent_ids`。
  - reporting task-scoped learning projection 不再因为“同 goal”把不在当前 task scope 内的 proposal 拉进 report。
- workflow 继续去历史 link 真相：
  - run detail / resume 的 goal step 现在优先按 `GoalOverride.compiler_context(workflow_run_id, workflow_step_id)` 派生 goal link，不再以持久化 `linked_goal_ids` 为正式真相。
  - schedule step 继续只按 deterministic schedule identity 恢复，不再读历史 `linked_schedule_ids`。
- `2026-04-07` follow-up hard cut:
  - `OperatingCycleService.reconcile_cycle(...)` 已删除 `goal_statuses` 输入，cycle status 现在只按 assignment/report truth 判定。
  - `PredictionService.create_cycle_case(...)` 不再把 `goal_statuses` 写进 cycle fingerprint 或 case metadata。
  - `WorkflowStepExecutionRecord` 已删除内部 `linked_goal_ids / linked_schedule_ids` 字段；step detail 改为读时推导，不再靠 step record 持有 legacy link。
- 这轮完成后仍然真实存在的残留只剩：
  - workflow `step_execution_seed` 仍允许保留 `linked_goal_ids / linked_schedule_ids` 作为旧 run 兼容回填输入，但公开 step record/detail 已不再依赖它们。
  - `runtime_service_graph.py` + `runtime_bootstrap_models.py` 的 wiring graph 仍偏重。

### 3.3.7 `2026-04-07` bootstrap draft-truth hardening

- `IndustryInstanceRecord` 新增正式 `draft_payload` 真相字段，并已落到 SQLite schema / repository 持久化。
- industry bootstrap 现在会把 canonicalized `IndustryDraftPlan` 原样落到 `IndustryInstanceRecord.draft_payload`，后续 strategy/runtime 读取行业草案时优先消费这份实例内真相，而不是再从 legacy goal truth 反推。
- bootstrap backlog/cycle/assignment seed 已改为直接消费 canonical goal specs；`GoalRecord` 改为在 assignment-native seed 完成后按稳定 `goal_id` 物化，避免“先 materialize goal 再把 goal 当唯一 bootstrap truth”的旧顺序。
- canonical goal identity 已按 `team_id + goal slug` 稳定化，同一实例的 bootstrap/replay/delete 都使用同一组 goal ids，同时避免跨实例 goal id 冲突。
- 这轮为了让 fresh 进程回归稳定收集，还补正了 `copaw.compiler.planning` 的公开导出面；`PlanningStrategicUncertainty / StrategyTriggerRule` 现已重新加入 package export，`IndustryService` 新进程导入不再因 planning package re-export 断层而在 collect 阶段失败。
- 本次追加 focused verification：
  - `python -m pytest tests/state/test_state_store_migration.py::test_sqlite_state_store_initialize_upgrades_legacy_tables_before_schema_indexes tests/state/test_sqlite_repositories.py::test_sqlite_override_repositories_crud_round_trip tests/app/industry_api_parts/bootstrap_lifecycle.py::test_public_bootstrap_persists_draft_truth_and_uses_draft_goal_identity tests/app/industry_api_parts/retirement_chain.py::test_industry_delete_retired_instance_removes_persisted_runtime_state tests/app/industry_api_parts/runtime_updates.py::test_industry_chat_writeback_approved_staffing_proposal_unblocks_materialization -q` -> `5 passed`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch -vv -s` -> `1 passed in 864.29s`

### 3.3.8 `2026-04-07` bootstrap hard-cut 2A

- `/industry/v1/bootstrap` 的正式公开 contract 已从 legacy `goals / schedules` 收口到 canonical `draft / backlog / cycle / assignments / schedule_summaries`；`routes` 里也不再暴露 legacy `goals` / `schedules` surface。
- bootstrap write-path 现已进一步从 “先持久化 legacy schedule，再把 `ScheduleRecord[]` 喂给 backlog seed” 改成 “先用 canonical `goal_specs + schedule_specs` 起 `backlog/cycle/assignment`，再在下游物化 compatibility `GoalRecord / ScheduleRecord`”。
- 这意味着此前“industry bootstrap 仍会 materialize bootstrap goal/schedule，再喂给 backlog/cycle”的残留判断已过时；当前 bootstrap 主链的正式起点已经收口到 canonical draft/spec truth。
- compatibility 边界仍然存在，但角色已经变化：
  - `GoalRecord / GoalOverrideRecord` 现在是 assignment-native seed 之后的 leaf/detail artifact。
  - `ScheduleRecord` 现在是 canonical schedule spec 落库后的 runtime/cadence artifact，不再是 bootstrap seed 的前置真相。
- 本次追加 focused verification：
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch or public_bootstrap_auto_dispatch_materializes_assignment_tasks_without_goal_dispatch or public_bootstrap_persists_draft_truth_and_uses_draft_goal_identity or public_bootstrap_hard_cuts_legacy_goal_schedule_response_surface or public_bootstrap_seeds_backlog_from_canonical_schedule_specs" -q` -> `5 passed, 42 deselected`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py::test_industry_delete_retired_instance_removes_persisted_runtime_state tests/app/industry_api_parts/retirement_chain.py::test_industry_delete_active_instance_clears_current_team tests/app/industry_api_parts/retirement_chain.py::test_industry_bootstrap_defaults_to_live_coordinating_contract -q` -> `3 passed`
  - `python -m pytest tests/app/industry_api_parts/runtime_updates.py::test_industry_bootstrap_goal_compile_regression_keeps_specialist_runtime_contract tests/app/industry_api_parts/runtime_updates.py::test_industry_bootstrap_specialist_runtime_metadata_only_persists_current_focus tests/app/industry_api_parts/runtime_updates.py::test_bootstrap_researcher_schedule_report_keeps_main_brain_continuity tests/app/industry_api_parts/runtime_updates.py::test_researcher_followup_assignment_persists_execution_core_continuity_without_backlog_anchor -q` -> `4 passed`

### 3.3.4 `2026-04-07` Buddy carrier direction-truth fix

- Buddy onboarding 的正式方向边界已补正：`BuddyOnboardingService._ensure_growth_scaffold(...)` 不再把 `HumanProfile` 当前资料直接写进 `IndustryInstanceRecord.profile_payload`。
- 当前权威口径收敛为：
  - `HumanProfile` 负责人的当前真实情况
  - `GrowthTarget` 负责已确认的主方向与最终目标
  - `IndustryProfile` 只负责 Buddy execution carrier 的正式执行方向
- 当前实现已新增 `_build_buddy_industry_profile(...)`，并把 Buddy carrier 的 `profile_payload` 改为合法 `IndustryProfile`：`industry <- primary_direction`、`goals <- [final_goal]`、`constraints <- human constraints`、`notes <- bootstrap context`。
- 前端 `/industry` 当前载体调整页也已同步收口心智：表单文案从“行业”改为“正式方向”，并明确说明这里填写的是主脑当前执行方向，不是用户当前职业。
- 本轮 focused verification：
  - `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_cutover.py -q` -> `14 passed`
  - `cmd /c npm --prefix console run test -- src/pages/Industry/pageHelpers.test.ts` -> `6 passed`

### 3.3.9 `2026-04-07` industry learning kickoff acquisition-closure

- `IndustryService.kickoff_execution_from_chat(...)` 默认已不再同步阻塞 `run_industry_acquisition_cycle(...)`；默认行为现已改成“前台 kickoff 立即返回、learning acquisition 在后台自动继续跑”。
- 只有显式传入 `include_learning_acquisition_cycle=True` 时，当前这次 kickoff 才会同步等待 acquisition 并把 `acquisition_cycle` 结果直接带回返回值。
- 这意味着默认 kickoff 主链只负责 assignment/backlog/cycle 的正式执行起链，不再因为自动 acquisition 扫描把 operator / retirement / runtime-detail 相关测试和读面一起拖进慢链；但系统仍会继续自动找 install-template / builtin runtime，不是直接关掉 acquisition。
- 当前收窄只作用于 kickoff 管理的 automatic acquisition：
  - install-template / builtin-runtime 仍保留在自动 acquisition 主链内；
  - SOP template 搜索仍由 discovery service 的独立 `sop_templates` 分支提供；
  - curated skill / MCP registry / remote provider 扫描不再作为 industry auto kickoff 的默认同步步骤。
- `LearningAcquisitionRuntimeService.run_industry_acquisition_cycle(...)` 的显式调用已恢复为 broad discovery default：
  - `/learning/acquisition/run` 在未显式指定 provider 时，不再被硬锁成 `providers=["install-template"]`；
  - 这意味着显式 acquisition run、后续 capability-gap / governed acquisition flow 仍能看到 `mcp-registry / curated-skill / remote`。
- `query_execution_tools.py` 的 `discover_capabilities` 前门已恢复 `mcp-registry / mcp` provider 透传，不再在 query/tool 层把 MCP discovery 截断。
- kickoff 背景 acquisition 现在会补 runtime event 可见性：
  - queued: `learning-acquisition.background-cycle-queued`
  - completed: `learning-acquisition.background-cycle-completed`
  - failed: `learning-acquisition.background-cycle-failed`
- 因此，`test_industry_learning_kickoff_materializes_acquisition_objects_and_exposes_them` 这条此前会长时间卡住的 industry learning 闭环现在已能在本地环境内 fresh 跑通。
- 本次追加 focused verification：
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_does_not_block_on_learning_acquisition_cycle_by_default -q` -> `1 passed`
  - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py::test_kickoff_execution_from_chat_publishes_background_acquisition_failure_event -q` -> `1 passed`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py::test_industry_learning_kickoff_scopes_acquisition_discovery_to_install_templates -q` -> `1 passed`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py::test_industry_learning_kickoff_materializes_acquisition_objects_and_exposes_them -q` -> `1 passed in 88.75s`
  - `python -m pytest tests/app/industry_api_parts/retirement_chain.py::test_industry_runtime_detail_and_goal_detail_use_formal_instance_store -q` -> `1 passed`
  - `python -m pytest tests/app/test_learning_api.py -k "acquisition_run or acquisition_review_gate" -q` -> `6 passed, 10 deselected`
  - `python -m pytest tests/kernel/query_execution_environment_parts/dispatch.py -k "discover_capabilities" -q` -> `1 passed, 10 deselected`
  - `python -m pytest tests/app/test_prediction_mcp_optimization_flow.py::test_missing_mcp_recommendation_executes_into_optimization_closure -q` -> `1 passed`

### 3.3.10 `2026-04-15` workflow compatibility / optimization closure hardening

- workflow launch / resume 的 compatibility materialization 已显式化：
  - workflow 叶子 `GoalRecord` 不再以通用 `goal` 类出现；
  - workflow materialization 现在统一落成 `goal_class="workflow-step-goal"`；
  - 对应 `GoalOverrideRecord.compiler_context` 会显式写入 `materialization_path="workflow-leaf-compatibility"`；
  - 这意味着 workflow 仍复用 canonical `GoalService`，但兼容叶子的边界已从“隐式普通 goal”收口为“显式 workflow leaf compatibility artifact”。
- bootstrap compatibility side-write 也已显式标注为历史桥接，而不是 live planning truth：
  - bootstrap 兼容 goal 现在统一是 `goal_class="compatibility-bootstrap-goal"`；
  - 对应 override 会带 `compatibility_materialization=True` 与 `compatibility_surface="bootstrap-goal-record"`；
  - assignment/backlog/cycle 仍是 bootstrap 主链正式真相，compatibility goal 只是下游 leaf/detail artifact。
- learning patch 正式新增 typed `workflow_patch`：
  - patch 模型现在支持 `workflow_template_id / workflow_run_id / workflow_step_id / patch_payload`；
  - workflow optimization 不再只能借 `plan_patch + diff_summary` 松散映射到 `GoalOverrideRecord`；
  - 当前已落地的真实副作用边界是：`workflow_patch(target_surface="workflow_template")` 可直接更新 `WorkflowTemplateRecord.step_specs`，并支持 rollback 恢复。
- 行业 runtime detail 现在新增 canonical `optimization_closure` 读投影：
  - 会把 `Proposal / Patch / Growth / Decision` 收口到单一 closure block；
  - link 以 `task_id` 为主锚，并继续保留 `assignment_id / backlog_item_id / agent_id / workflow_run_ids / workflow_step_ids`；
  - 这意味着 optimization 读面不再只能散落在 proposals/patches/growth 列表里，而是有了单一闭环故事。
- 本轮 fresh verification：
  - focused contract：
    - `python -m pytest tests/app/test_workflow_materialization_contracts.py tests/app/industry_api_parts/test_bootstrap_compatibility_contracts.py tests/kernel/test_learning_workflow_patch.py tests/industry/test_optimization_closure_projection.py -q -p no:cacheprovider` -> `5 passed`
  - 真实闭环场景：
    - `python -m pytest tests/app/test_workflow_industry_optimization_scenario.py -q -p no:cacheprovider` -> `1 passed`
    - 场景覆盖：`/industry/v1/bootstrap -> workflow service launch -> workflow resume fallback -> workflow_patch apply/rollback -> /runtime-center/industry/{instance_id}`，并验证 bootstrap compatibility、workflow compatibility、typed patch、optimization closure 同时跑通。
  - 相邻回归：
    - `python -m pytest tests/app/test_workflow_templates_api.py -k "resume_uses_persisted_runtime_context_without_rehydrating_legacy_links or resume_uses_goal_override_context_without_recreating_legacy_goal_links or run_public_surface_hides_historical_goal_schedule_id_fields" -q -p no:cacheprovider` -> `3 passed, 44 deselected`
    - `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "public_bootstrap_hard_cuts_legacy_goal_schedule_response_surface or public_bootstrap_persists_draft_truth_and_uses_draft_goal_identity or kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch" -q -p no:cacheprovider` -> `3 passed, 51 deselected`
    - `python -m pytest tests/kernel/test_compiler_learning.py::test_patch_executor_applies_profile_role_and_plan_side_effects tests/kernel/test_compiler_learning.py::test_learning_service_links_to_persisted_compiler_context -q -p no:cacheprovider` -> `2 passed`
    - `python -m pytest tests/industry/test_runtime_views_split.py tests/app/test_prediction_mcp_optimization_flow.py -q -p no:cacheprovider` -> `17 passed`
