# REAL_ISSUES.md

本文件用于记录 `2026-03-14` 对当前仓库真实架构问题的校正结论。

它的目标不是再做一份泛化系统综述，而是明确：

- 哪些问题经源码核验后确实成立
- 哪些问题方向成立，但原始表述存在夸大或已过时
- 哪些问题其实已经失效，不应继续写进后续问题单
- 当前更合理的拆分优先级是什么

本文件优先服务于后续架构收口、删旧和服务拆分工作。

---

## 1. 校验范围

本轮直接阅读了以下核心文件：

- `src/copaw/app/_app.py`
- `src/copaw/app/runtime_bootstrap.py`
- `src/copaw/app/runtime_bootstrap_models.py`
- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/runtime_manager_stack.py`
- `src/copaw/app/runtime_state_bindings.py`
- `src/copaw/app/runtime_lifecycle.py`
- `src/copaw/capabilities/service.py`
- `src/copaw/capabilities/catalog.py`
- `src/copaw/capabilities/execution.py`
- `src/copaw/capabilities/system_handlers.py`
- `src/copaw/capabilities/system_skill_handlers.py`
- `src/copaw/capabilities/execution_support.py`
- `src/copaw/compatibility/skills.py`
- `src/copaw/learning/service.py`
- `src/copaw/goals/service.py`
- `src/copaw/kernel/dispatcher.py`
- `src/copaw/kernel/governance.py`
- `src/copaw/capabilities/sources/skills.py`
- `src/copaw/app/routers/skills.py`
- `src/copaw/cli/skills_cmd.py`
- `src/copaw/cli/init_cmd.py`
- `src/copaw/kernel/models.py`
- `src/copaw/kernel/lifecycle.py`
- `src/copaw/kernel/persistence.py`
- `src/copaw/app/runtime_center/state_query.py`

同时参考：

- `AGENTS.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

---

## 2. 真实问题清单

### 2.1 启动装配过重问题曾真实存在，`2026-03-14` 已完成第三轮模块化收口

- 结论：`原判断成立，但本轮已不再属于当前未完成项`
- 原始证据：
  - 最早的 `lifespan` 曾同时串联 state 仓储初始化、service 装配、recovery、channel/cron/watcher 启动、automation loop、restart callback 与 teardown
  - 第一轮把 `_app.py` 中的大段组装抽到 `src/copaw/app/runtime_bootstrap.py`
  - 第二轮又把 automation/restart 生命周期抽到 `src/copaw/app/runtime_lifecycle.py`
- 当前状态：
  - `src/copaw/app/runtime_bootstrap_models.py` 已承接运行时结构模型
  - `src/copaw/app/runtime_service_graph.py` 已承接 repository + service graph 装配
  - `src/copaw/app/runtime_manager_stack.py` 已承接 channel/cron/mcp watcher 的启停栈
  - `src/copaw/app/runtime_state_bindings.py` 已承接 `app.state` 绑定面
  - `src/copaw/app/runtime_bootstrap.py` 当前已退为薄聚合出口
- 更准确的表述：
  - 当前问题已经从“启动装配集中在单个入口/单个 bootstrap 文件”收口为“边缘入口调用多层装配模块”
  - `_app.py` 仍然是应用入口，但它已不再直接承担大块运行图拼装责任
- 剩余风险：
  - 后续如继续深化，重点应是 live/provider/host 真实世界硬化，而不是回到启动装配结构拆分
  - 不应再把新的 service graph 组装逻辑堆回 `_app.py` 或单个 bootstrap 文件

### 2.2 `CapabilityService` 上帝对象问题曾真实存在，`2026-03-14` 已完成当前轮细粒度收口

- 结论：`原判断成立，但本轮也已不再属于当前未完成项`
- 原始证据：
  - 在本轮审计开始时，`src/copaw/capabilities/service.py` 仍同时承载 capability catalog/admin、execution、`system:*` handler、skill/MCP compat helper
  - 主文件当时仍在 `2000` 行级别
- 当前状态：
  - `src/copaw/capabilities/catalog.py` 已承接 capability 目录读取、summary、显式 allowlist 判定、skill/mcp 信息读取、toggle/delete 等 catalog/admin 面
  - `src/copaw/capabilities/execution.py` 已承接 `resolve_executor / execute_task / skill&mcp 执行 / evidence 包装`
  - `src/copaw/capabilities/system_handlers.py` 现只保留 capability 路由分发壳
  - `src/copaw/capabilities/system_dispatch.py`、`src/copaw/capabilities/system_team_handlers.py`、`src/copaw/capabilities/system_actor_handlers.py`、`src/copaw/capabilities/system_config_handlers.py`、`src/copaw/capabilities/system_learning_handlers.py` 已分别承接对应子域 handler
  - `src/copaw/capabilities/system_skill_handlers.py` 已把 `create_skill / install_hub_skill` 从通用 config facade 里继续拆出
  - `src/copaw/capabilities/execution_support.py` 已承接执行面共用 helper
  - `src/copaw/capabilities/service.py` 当前已压缩到约 `255` 行，只保留依赖注入、facade 代理和 evidence 记录壳
  - `src/copaw/compatibility/skills.py` 已成为 skill legacy subsystem 的单点 compat seam；`service / execution / source / system handler` 不再各自散落直连 `SkillService`
- 更准确的表述：
  - 当前“主服务文件上帝对象”问题已经明显缓解
  - 当前 capability 主链已经从“单文件混装 + 分散 skill compat”收口为“主服务壳 + 多个子域 facade + 单点 compat seam”
- 剩余风险：
  - `CapabilityService` 仍是 facade 汇聚壳，但这已经是可控的装配壳，不再是当前架构阻塞点
  - 后续如继续深化，应围绕真实 provider / 更深产品 drilldown / 最终删掉 `skills_manager` 底座推进，而不是回到 capability 主链粗拆分

### 2.3 skill 兼容层入口旁路问题曾真实存在，已于 `2026-03-14` 完成第二轮收口

- 结论：`原判断成立，但本轮已完成第二轮收口，不再是当前未完成项`
- 过时说法：
  - `LearningService` 或 `GoalService` 仍直接依赖 `SkillService`
- 当前真实情况：
  - `src/copaw/learning/service.py` 未直接引用 `SkillService`
  - `src/copaw/goals/service.py` 未直接引用 `SkillService`
  - legacy `/skills` router 的 `create / hub-install / file-load` 已分别收口到 `system:create_skill`、`system:install_hub_skill` 与 `CapabilityService.load_skill_file()`
  - CLI `skills list`、`skills config` 与 `init` 的“enable all skills”入口已统一改走 `CapabilityService`
  - `src/copaw/compatibility/skills.py` 现已成为 skill legacy 的单点 compat adapter；`CapabilityService / CapabilityExecutionFacade / capability skill source / system skill handlers` 已统一经该 seam 访问旧 `skills_manager`
- 当前证据：
  - `src/copaw/app/routers/skills.py`
  - `src/copaw/cli/skills_cmd.py`
  - `src/copaw/cli/init_cmd.py`
  - `src/copaw/capabilities/service.py`
- 更准确的表述：
  - 本轮关闭的是“后端/CLI/legacy router 对外入口继续直连旧 skill 写面/读面”的问题
  - 当前又进一步关闭了“capability 主链内部散落多个 `SkillService` 直连点”的问题
  - `SkillService` 仍存在于 compat adapter 背后，但这已属于未来最终物理删旧，不再属于当前 capability 主链收口缺口
- 剩余风险：
  - 后续如继续做物理删旧，应继续压缩 `skills_manager` 在 capability 内部的存在感
  - 不应再新增任何绕过 `CapabilityService` / kernel 治理面的 skill 管理入口

### 2.4 跨服务调试可观测性缺口曾真实存在，`2026-03-14` 已落下第一条正式 trace 链

- 结论：`原判断成立，但最关键的 trace / correlation 缺口已完成第一轮收口`
- 证据：
  - `KernelDispatcher.execute_task()` 进入 capability 执行链
  - admission / block 继续经过 `src/copaw/kernel/governance.py`
  - capability 再按具体类型分发到 goal、learning、environment、delegation、turn executor 等服务
- 当前状态：
  - `KernelTask` 与 `KernelResult` 已正式带出 `trace_id`
  - evidence metadata、runtime event、Runtime Center task / decision / evidence 读面都已统一暴露 `trace_id`
  - capability execution 返回 payload 也已附带 `trace_id`
- 更准确的表述：
  - 不是所有请求都走同一条超长路径
  - 但核心执行面确实存在“按 capability 条件分叉的深链路”，因此需要统一 correlation 标识才能低成本回放
- 剩余风险：
  - 当前已具备第一条正式 correlation 链，但更深的前端 drilldown / 可视化聚合仍可继续增强
  - 后续若新增执行分支却不继续复用 `trace_id`，会重新把调试体验打回拼日志状态

---

## 3. 已证伪或已过时的问题

### 3.1 `LearningService` / `GoalService` 直接依赖 `SkillService`

- 结论：`不成立`
- 当前核验结果：
  - `src/copaw/learning/service.py` 中不存在 `SkillService` / `skills_manager` 直接引用
  - `src/copaw/goals/service.py` 中不存在 `SkillService` / `skills_manager` 直接引用
- 处理建议：
  - 后续问题单中不要再把这一条列为 learning/goals 层缺陷
  - 如需记录 skill 历史遗留，应引用 “2.3 已于 `2026-03-14` 完成第二轮收口”的口径，而不是继续写成当前未完成项

### 3.2 `system:run_learning_strategy` / `system:auto_apply_patches` 返回格式不统一

- 结论：`不成立`
- 当前核验结果：
  - `LearningService.auto_apply_low_risk_patches()` 返回标准 `dict`
  - `LearningService.run_strategy_cycle()` 返回标准 `dict`
  - 两者都具备 `success / summary` 等统一字段
- 处理建议：
  - 不应再把这两条列为当前真实缺陷
  - 若未来发现新漂移，必须按当前代码重新举证

---

## 4. 当前更合理的拆分优先级

### Priority-1：已完成启动装配分层收口

- 目标：
  - 把 `_app.py` 中的 service assembly、runtime orchestration、automation bootstrap、restart/teardown 继续拆成独立装配器 / 生命周期模块
- 进展：
  - `2026-03-14` 已完成第一刀：新增 `src/copaw/app/runtime_bootstrap.py`
  - `2026-03-14` 已完成第二刀：新增 `src/copaw/app/runtime_lifecycle.py`
  - `2026-03-14` 已完成第三刀：新增 `src/copaw/app/runtime_bootstrap_models.py`、`src/copaw/app/runtime_service_graph.py`、`src/copaw/app/runtime_manager_stack.py`、`src/copaw/app/runtime_state_bindings.py`
- 原因：
  - 这是当前最大单点复杂度来源
  - 也是后续所有服务拆分的上游阻塞点

### Priority-2：已完成 capability 主链当前轮细粒度收口

- 目标：
  - 继续把 capability execution / system handler 从大块混合体拆成稳定子域
- 进展：
  - `2026-03-14` 已完成第一刀：新增 `src/copaw/capabilities/catalog.py`
  - `2026-03-14` 已完成第二刀：新增 `src/copaw/capabilities/execution.py`、`src/copaw/capabilities/system_handlers.py` 与 `src/copaw/capabilities/execution_support.py`
  - `2026-03-14` 已完成第三刀：新增 `src/copaw/capabilities/system_dispatch.py`、`src/copaw/capabilities/system_team_handlers.py`、`src/copaw/capabilities/system_actor_handlers.py`、`src/copaw/capabilities/system_config_handlers.py`、`src/copaw/capabilities/system_learning_handlers.py`
  - `2026-03-14` 已完成第四刀：新增 `src/copaw/compatibility/skills.py` 与 `src/copaw/capabilities/system_skill_handlers.py`
- 当前剩余点：
  - 当前轮需要处理的 capability 主链结构问题已经收口
  - 后续若继续推进，重点应是最终压缩 compat 底座和增强真实世界测试，不再是 capability 主链的拆分阻塞
- 原因：
  - capability 主链仍是第二大复杂度来源
  - 不继续拆，skill/MCP/治理/执行边界很难真正稳定

### Priority-3：已完成 skill legacy 入口与主链 compat 收口

- 已完成内容：
  - legacy `/skills` router 的 `create / hub-install / file-load` 已收口到 `CapabilityService` / kernel-governed system capabilities
  - CLI `skills list`、`skills config` 与 `init` 的“enable all skills”入口已不再直接触碰旧 skill 写面
  - capability 内部 skill 读写也已经统一压到 `src/copaw/compatibility/skills.py` 单点 seam
- 后续剩余点：
  - 后续若继续删旧，重点应是内部 `SkillService` / `skills_manager` 承载压缩，而不是重复处理外层入口旁路

### Priority-4：已完成首条执行链路 trace / correlation 收口

- 已完成内容：
  - `KernelTask / KernelResult / EvidenceRecord metadata / RuntimeEventBus / Runtime Center task|decision|evidence` 已统一暴露 `trace_id`
  - capability execution 返回面也已带出 `trace_id`，operator 可以沿同一 correlation id 回看执行链
- 后续剩余点：
  - 后续如继续增强，应聚焦前端 drilldown、跨页深链和可视化聚合，而不是再补一套新的 tracing 语义

---

## 5. 一句话结论

本轮问题单里最真实的内部架构缺口，已经完成当前轮收口：

- 启动装配过重：已拆成结构模型、service graph、manager stack、state bindings 四层
- capability 主链细粒度删旧与测试收口：已补齐单点 skill compat seam、system skill facade 与对应回归

当前没有必须继续按同级阻塞项追踪的内部结构缺口。后续工作只剩更深删旧、真实世界硬化与更强可视化，不再沿用这轮已失效的问题口径。
