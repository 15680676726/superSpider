# CoPaw External Executor Runtime Hard-Cut Design
日期：`2026-04-20`

`2026-04-22` supplement:
- 面向客户交付的本地 `Codex` 执行体边界现已收口为：`managed local codex CLI sidecar + stdio`
- `CoPaw MainBrain -> ExecutorRuntimePort -> CodexAppServerAdapter -> managed local codex CLI sidecar`
- `COPAW_CODEX_APP_SERVER_WS_URL` 只保留显式 websocket compatibility/testing path；`COPAW_CODEX_APP_SERVER_BIN` 只保留 env-binary compatibility fallback
- CoPaw 必须统一持有 sidecar install truth、model policy、approval/recovery、version compatibility 与 upgrade/rollback 治理；这些不再允许散落到 sidecar 私有配置中失控演化
- 本地 customer-delivery path 不是“客户自己安装 codex 再手动配环境”，而是 CoPaw 以受管 sidecar 方式治理 `codex CLI`

---

## 0. 目标

本次设计不是继续增强 CoPaw 现有本地多 agent 执行器，也不是把某一个外部智能体当成普通插件挂在旧执行链后面。

本次设计要完成的是一条明确的硬切路线：

- `CoPaw` 保留主脑、记忆、战略、派工、审批、证据与回流真相
- 现有本地多执行位 runtime 退役
- 多个受控外部执行体替代现有多 agent 执行层
- 对外接入面从“任意开源项目 donor”收口成“受控执行体 runtime provider”
- 第一适配器是 `Codex App Server`
- 后续允许接入 `Hermes` 与其他具备正式控制面的开源智能体 runtime

一句话目标：

> 把 CoPaw 从“自带本地多执行器的主脑系统”升级成“以上层主脑为唯一真相源、以下层可插拔执行体为统一执行层”的长期执行框架。

---

## 1. 设计结论

### 1.1 选定路线

本次选定路线为：

- `CoPaw MainBrain -> ExecutorRuntimePort -> ExecutorAdapter -> External Executor Runtime`

不选：

- `纯 MCP` 作为主控总线
- `Desktop App` 作为长期底层
- 继续演化本地 `actor_worker / actor_supervisor / delegation execution`
- 继续把 GitHub / donor intake 当成“任意项目接入面”

正式口径：

- `Codex App Server` 是第一条已确认的正式控制面
- `Codex` 是第一适配器，不是唯一适配器
- `Hermes` 与其他执行体只要满足 formal control surface，就应能接入同一条 `ExecutorRuntimePort`

### 1.1.1 customer-delivery 本地接线

对于面向客户交付的本地执行形态，当前正式接线固定为：

- `CoPaw MainBrain`
- `ExecutorRuntimePort`
- `CodexAppServerAdapter`
- `managed local codex CLI sidecar`
- `stdio`

这意味着：

- 默认本地执行不再依赖 PATH 上“碰巧存在”的 `codex`
- 默认本地执行不再以 websocket 作为正式客户路径
- `Codex App Server` websocket 仍可保留为显式 compatibility/testing path，但不能再被描述成客户默认形态

### 1.2 根本判断

CoPaw 不直接“调用某个智能体的某个工具函数”。

CoPaw 负责：

- 创建和恢复执行体
- 下发正式任务
- 选择执行体
- 选择执行策略
- 选择模型调用策略
- 接收事件和证据
- 决定继续、插话、停止或收尾

外部执行体负责：

- 在受控项目内制定执行 plan
- 执行命令、修改文件、调用 MCP
- 输出计划、证据、阶段完成、任务完成等事件

一句话边界：

> CoPaw 管理执行体；外部智能体在主脑监管下执行具体动作。

### 1.3 V1 总策略

第一版不做复杂职业权限和复杂环境治理。

第一版采用：

- `高权限`
- `少限制`
- `自动放行`
- `强观测`
- `强回流`

这不是“完全无边界”，而是：

- 不做细粒度限制矩阵
- 保留最小运行边界
- 保留全事件记录
- 保留一键停止能力

### 1.4 执行体选择模式

系统必须同时支持两种模式：

- `single-runtime mode`
  - 所有执行位统一绑定同一种执行体，例如全部使用 `Codex`
- `role-routed mode`
  - 不同职业或不同任务类型绑定不同执行体，例如研发用 `Codex`，其他职业用 `Hermes`

这两种模式都必须通过同一条 `ExecutorRuntimePort` 和同一套正式真相对象承载，不能再长出第二套 runtime 主链。

### 1.5 模型调用统一治理

执行体接入后，模型调用不能继续散落在各 runtime 私有配置里失控演化。

必须保留一层主脑可见的统一治理：

- 哪个执行体默认使用什么模型
- 哪些模型由执行体自己管理
- 哪些模型由 CoPaw 统一下发
- 角色级、任务级是否允许覆盖默认模型
- 模型调用证据和成本统计如何回流主脑

### 1.6 `ExecutorRuntime` 与 `MCP / skill` 的边界

这一层必须写死，不能继续混。

- `External Executor Runtime`
  - 指 `Codex / Hermes / future executors` 这类完整执行体
  - 它们替代的是本地多 agent 执行位
  - 它们是 `Assignment -> execution -> event -> evidence/report` 的正式承载体
- `MCP`
  - 是执行体或主脑可调用的工具/外部能力接入方式
  - 它不是执行体本身
  - 它不能替代 thread / turn / lifecycle / event stream 这类 executor control plane
- `skill`
  - 是执行体内部的工作方法、提示组织或能力增强
  - 它不是正式执行接缝，也不是正式真相对象

正式原则：

- CoPaw 对外接入的一级对象是 `ExecutorProvider / ExecutorRuntime`
- `MCP / skill` 只能作为执行体内部可用能力或 workflow 附属层
- 后续任何实现都不允许再把“接入一个 skill/MCP”表述成“接入一个执行体”

---

## 2. 架构分层

### 2.1 MainBrain

保留 CoPaw 主脑现有职责：

- 记忆
- 战略
- 派工
- 审批决策
- 结果判断
- 证据归档
- 前端读面真相

主脑仍然是唯一长期战略中心。

### 2.2 ExecutorRuntimePort

新增 CoPaw 内部统一执行接口。

职责：

- 对外提供“创建执行体、恢复执行体、启动 turn、停止 turn、读取状态”的统一语义
- 隔离上层业务与下层 App Server 协议
- 为未来替换底层实现保留接口位
- 为多执行体路由和统一模型治理保留接口位

### 2.3 ExecutorAdapter

新增底层适配器，负责：

- 对接具体执行体控制面，例如 `Codex App Server`
- 管理 thread / turn 或 runtime-native lifecycle
- 接收事件流
- 转发审批请求
- 输出标准化事件到 CoPaw

说明：

- `ExecutorAdapter` 对接的是执行体控制面
- 它不是 `MCP adapter`
- 也不是 `skill loader`

### 2.4 External Executor Runtime

外部执行体的 thread/turn 或等价 runtime unit 是真实执行单元。

它们不是主脑真相源，只是执行过程载体。

### 2.5 Executor Workspace

每个执行体绑定一个项目目录或等价 workspace。

项目目录承载：

- 角色合同投影
- 角色手册
- 项目说明
- runtime-specific 配置
- skills
- 计划、汇报、证据与运行态文件

---

## 3. 保留、删除与新增

### 3.1 必须保留

以下主脑真相链继续保留：

- `Assignment`
- `AgentReport`
- `EvidenceRecord`
- 主脑记忆对象
- 主脑战略/周期/派工对象
- Runtime Center 读面

### 3.2 删除目标

以下模块属于被外部执行体替代的旧执行层：

- 本地 `actor worker` 执行循环
- 本地 `actor supervisor`
- 当前 `delegation` 的执行后端

注意：

- 不是删除“派工”
- 不是删除“主脑”
- 而是删除“本地多工人执行器”

### 3.3 必须新增

V1 最小新增对象如下：

- `RoleContract`
- `ProjectProfile`
- `ExecutionPolicy`
- `ExecutorProvider`
- `RoleExecutorBinding`
- `ModelInvocationPolicy`
- `ExecutorSidecarInstall`
- `ExecutorSidecarCompatibilityPolicy`
- `ExecutorSidecarRelease`
- `ExecutorRuntimeInstance`
- `ExecutorThreadBinding`
- `ExecutorTurnRecord`
- `ExecutorEventRecord`

V1 最小新增模块如下：

- `src/copaw/kernel/executor_runtime_port.py`
- `src/copaw/adapters/executors/codex_app_server_adapter.py`
- `src/copaw/state/models_executor_runtime.py`
- `src/copaw/state/executor_runtime_service.py`
- `src/copaw/kernel/executor_event_ingest_service.py`
- `src/copaw/compiler/role_contract_projection.py`

---

## 4. 正式对象模型

### 4.1 RoleContract

`RoleContract` 是 CoPaw 主脑中的动态角色真相对象。

V1 最小字段建议：

- `role_id`
- `display_name`
- `summary`
- `responsibilities`
- `planning_contract`
- `reporting_contract`
- `escalation_rules`
- `default_skill_set`
- `default_project_profile`
- `status`

它的职责：

- 供主脑派工和治理使用
- 投影生成项目中的 `AGENTS.md` 与 `ROLE.md`

### 4.2 ProjectProfile

描述某个执行体 workspace 的结构映射。

V1 最小字段建议：

- `project_profile_id`
- `root_path`
- `agents_md_path`
- `role_md_path`
- `project_md_path`
- `skill_root`
- `runtime_root`
- `status`

### 4.3 ExecutionPolicy

V1 先只做一个正式策略：`open_default`

V1 最小字段建议：

- `policy_id`
- `policy_name`
- `sandbox_mode`
- `approval_mode`
- `network_mode`
- `notes`
- `status`

V1 语义：

- 默认高权限执行
- 默认自动放行
- 暂不按职业做细粒度差异化治理

### 4.4 ExecutorProvider

描述可接入的外部执行体 provider。

V1 最小字段建议：

- `provider_id`
- `provider_kind`
- `runtime_family`
- `control_surface_kind`
- `install_source_kind`
- `source_ref`
- `default_protocol_kind`
- `status`

边界：

- 它代表“可治理的执行体 runtime”
- 不再代表“任意 GitHub donor 项目”

### 4.5 RoleExecutorBinding

描述角色或任务类型如何选择执行体。

V1 最小字段建议：

- `binding_id`
- `role_id`
- `executor_provider_id`
- `selection_mode`
- `project_profile_id`
- `execution_policy_id`
- `status`

### 4.6 ModelInvocationPolicy

描述模型调用统一治理口径。

V1 最小字段建议：

- `policy_id`
- `ownership_mode`
- `default_model_ref`
- `role_overrides`
- `task_overrides_allowed`
- `cost_tracking_mode`
- `status`

说明：

- `ownership_mode` 至少支持：
  - `runtime_owned`
  - `copaw_managed`
  - `hybrid`

### 4.6.1 ExecutorSidecarInstall

描述 CoPaw 受管本地 sidecar 的正式安装真相。

V1 最小字段建议：

- `install_id`
- `runtime_family`
- `channel`
- `version`
- `install_root`
- `executable_path`
- `install_status`
- `last_checked_at`

边界：

- 它描述的是“当前机器上被 CoPaw 接管的 sidecar 安装”
- 它不是 PATH 探测结果，也不是用户自己随手安装的环境变量事实

### 4.6.2 ExecutorSidecarCompatibilityPolicy

描述 CoPaw 与 sidecar 的正式兼容契约。

V1 最小字段建议：

- `policy_id`
- `runtime_family`
- `channel`
- `supported_version_range`
- `required_copaw_version_range`
- `status`

建议 metadata：

- `required_protocol_features`
- `fail_closed`

### 4.6.3 ExecutorSidecarRelease

描述受管 sidecar 的升级/回滚发布物真相。

V1 最小字段建议：

- `release_id`
- `runtime_family`
- `channel`
- `version`
- `artifact_ref`
- `artifact_checksum`
- `status`

说明：

- staged upgrade / rollback 必须围绕正式 `ExecutorSidecarRelease` 执行
- 不能把 sidecar 升级简化成“直接把客户机器上的 `codex` 全局升级掉”

### 4.7 ExecutorThreadBinding

描述角色/项目与执行体 thread 的绑定关系。

V1 最小字段建议：

- `binding_id`
- `role_id`
- `executor_provider_id`
- `project_profile_id`
- `thread_id`
- `runtime_status`
- `last_turn_id`
- `last_seen_at`

### 4.8 ExecutorTurnRecord

描述某次正式执行回合。

V1 最小字段建议：

- `turn_record_id`
- `thread_binding_id`
- `assignment_id`
- `turn_id`
- `turn_status`
- `started_at`
- `completed_at`
- `summary`

### 4.9 ExecutorEventRecord

描述外部执行体原始事件的归档对象。

V1 最小字段建议：

- `event_id`
- `turn_record_id`
- `event_type`
- `source_type`
- `payload`
- `created_at`

派生关系：

- `Assignment` 触发 `ExecutorTurnRecord`
- `ExecutorEventRecord` 派生 `EvidenceRecord`
- `ExecutorEventRecord` 汇总生成 `AgentReport`

---

## 5. 角色合同分层

角色定义必须拆成 4 层，不能全部压进 `AGENTS.md`。

### 5.1 RoleContract

主脑正式真相。

负责“角色是什么”。

### 5.2 AGENTS.md

项目内简版强制执行合同。

负责“进入项目后必须立刻遵守什么”。

建议只放：

- 当前角色身份摘要
- 项目内强制流程
- plan 纪律
- report 纪律
- evidence 纪律
- 升级条件
- 禁区

### 5.3 ROLE.md

项目内详细角色手册。

负责“这个角色通常怎么判断和工作”。

建议放：

- 职责范围
- 非职责范围
- 决策边界
- 质量标准
- 常见任务模式
- 常见错误
- 推荐能力与推荐工作法

### 5.4 copaw-worker-core skill

项目内统一执行方法。

负责“收到任务后按什么流程做”。

建议负责：

- session start checklist
- plan workflow
- execution workflow
- reporting workflow
- blocking workflow
- completion workflow

它不是：

- 主脑
- 审批器
- 长期记忆
- 正式状态真相源

---

## 6. 项目目录规范

每个执行体项目先统一成以下最小模板：

```text
<executor-project>/
  AGENTS.md
  ROLE.md
  PROJECT.md
  executors/
    codex/
      provider.toml
    hermes/
      provider.toml
  .agents/
    skills/
      copaw-worker-core/
  plans/
  reports/
  evidence/
  runtime/
```

目录职责：

- `AGENTS.md`：主脑合同投影
- `ROLE.md`：详细角色定义
- `PROJECT.md`：项目背景与完成定义
- `executors/`：CoPaw 侧 provider projection 与 runtime-specific 配置源；若某执行体要求原生配置文件位置（例如 `Codex` 的 `.codex/config.toml`），应由 adapter 从这里投影生成，`executors/` 才是 CoPaw 侧正式配置真相
- `.agents/skills/`：工作方法增强层
- `plans/`：计划草案和阶段计划
- `reports/`：阶段汇报、日报、周报
- `evidence/`：人类可读的证据索引与产物摘要
- `runtime/`：thread/session 绑定信息和运行态摘要

---

## 7. 消息协议

### 7.1 基本原则

协议必须采用事件驱动，而不是让主脑和外部执行体自由聊天。

原则如下：

- 主脑发任务
- 执行体发事件
- 主脑按事件决定继续、插话、停机或收尾

### 7.2 主脑到执行体

V1 只保留 4 类业务语义：

- `assignment_start`
- `assignment_followup`
- `approval_decision`
- `assignment_stop`

这些语义在底层映射为：

- thread 创建或恢复
- turn start
- turn steer
- stop / interrupt

### 7.3 执行体到主脑

V1 规范化事件集：

- `plan_submitted`
- `phase_started`
- `phase_completed`
- `blocked`
- `approval_requested`
- `evidence_emitted`
- `task_completed`
- `task_failed`

典型映射：

- `turn/plan/updated` -> `plan_submitted`
- `commandExecution` -> `evidence_emitted`
- `fileChange` -> `evidence_emitted`
- `mcpToolCall` -> `evidence_emitted`
- `turn/completed` -> `task_completed`
- `turn/failed` -> `task_failed`

说明：

- 上述示例来自 `Codex App Server`
- 其他执行体必须适配到同一套规范化事件集，不能把 runtime-native 事件直接暴露成第二套业务真相
- `approval_requested / approval_resolved / restart / interrupt` 在 customer-delivery 本地链路里也必须继续通过这套正式事件/证据真相回流，不能只停留在 sidecar console 输出

### 7.4 主脑回复策略

V1 只有以下情况必须回复：

- `approval_requested`
- `blocked`
- 需要审核的 `plan_submitted`
- 需要纠偏的执行过程

其余情况可静默：

- `evidence_emitted`
- `phase_completed`
- `task_completed`

### 7.5 真相原则

文本回复不是正式真相。

正式真相是：

- `ExecutorEventRecord`
- `EvidenceRecord`
- `AgentReport`

---

## 8. V1 执行策略

### 8.1 open_default

V1 第一版统一采用 `open_default`。

它的核心语义：

- 默认高权限执行
- 默认自动放行
- 不做复杂职业权限矩阵
- 不做复杂环境细分

### 8.2 V1 仍然保留的底线

即便第一版少限制，也必须保留：

- 全事件记录
- thread/turn 状态映射
- 一键停止能力
- 独立项目工作区
- 完整证据回流
- sidecar approval / recovery / restart 控制
- sidecar version compatibility gate
- managed install truth，而不是 PATH 偶然成功

设计原则：

> 第一版可以弱治理，但不能弱观测。

---

## 9. 第一阶段最小可跑链路

第一阶段只验证一条真实闭环：

1. 用户给主脑一个执行任务
2. 主脑创建 `Assignment`
3. 主脑根据全局默认或角色绑定选择执行体
4. 主脑生成或更新 `AGENTS.md / ROLE.md / PROJECT.md`
5. `ExecutorRuntimePort` 创建或恢复 thread
6. 第一适配器通过 `Codex App Server` 发起 `turn/start`
7. 执行体先产出 `plan`
8. 执行体真执行改动
9. 事件持续回流
10. CoPaw 生成 `EvidenceRecord` 与 `AgentReport`
11. 主脑决定继续或停止

这条链跑通，就证明：

- 外部执行体可以替代现有本地多执行位执行层
- `CoPaw` 可以保留主脑真相链
- `Codex App Server` 可以作为第一条长期控制面

---

## 10. V1 明确不做

以下内容不属于第一阶段必须交付：

- 复杂职业权限模型
- 多环境类型治理
- 复杂能力白名单
- MCP 安装审批闭环
- 改写现有 `MCP/skill` canonical 安装、搜索、演进主链
- 把 `/api/capability-market/skills`、`/api/capability-market/hub/*`、`/api/capability-market/mcp*`、`/api/capability-market/install-templates*` 误并入 executor runtime provider intake
- 自动学习 patch 闭环
- 多职业并发调度优化
- 桌面/浏览器/文档三套环境治理细分
- 完整日报/周报自动化体系
- 第二个执行体的真正落地适配

第一阶段只证明主链，不追求功能大全。

---

## 11. 风险与后续阶段

### 11.1 当前代码已发现的 7 个主要风险

1. 现有外部 runtime 真相模型仍是 capability-centric，不足以表达执行体 thread/turn 主链  
   代码锚点：`src/copaw/state/models_external_runtime.py`
2. 现有 external adapter taxonomy 只支持 `mcp/http/sdk` 请求响应，不足以表达 `app_server / event stream / thread-turn control`  
   代码锚点：`src/copaw/capabilities/external_adapter_contracts.py`、`src/copaw/capabilities/external_adapter_execution.py`
3. 应用 bootstrap 仍把 `ActorMailboxService / ActorWorker / ActorSupervisor` 当正式执行底座硬接  
   代码锚点：`src/copaw/app/runtime_bootstrap_execution.py`、`src/copaw/app/runtime_service_graph.py`
4. Runtime Center 与主脑上下文仍是 actor-first 读面，尚未收口成 generic executor 读面  
   代码锚点：`src/copaw/app/routers/runtime_center_dependencies.py`、`src/copaw/app/runtime_center/models.py`、`src/copaw/kernel/main_brain_chat_service.py`
5. `query_execution_runtime` 仍把本地 browser/desktop/document/file/shell tool 与 agent runtime 仓库写死在执行前门  
   代码锚点：`src/copaw/kernel/query_execution_runtime.py`
6. `TaskDelegationService` 不只是便利层，而是 child-task/mailbox/run-once 的正式派单链，不能直接物理删除  
   代码锚点：`src/copaw/kernel/delegation_service.py`
7. 旧本地 actor runtime 已有完整 persisted truth chain，但新执行体侧还没有同等级 formal object chain  
   代码锚点：`src/copaw/state/models_agents_runtime.py`

### 11.2 架构级纠偏要求

- 必须把旧 GitHub donor/open-source intake 收口成“只接执行体 runtime provider”的正式入口
- 必须支持“全局统一执行体”和“按职业路由不同执行体”两种模式
- 必须把模型调用治理纳入主脑正式对象，不允许每个执行体各自变成黑箱
- 必须先完成 generic executor seam，再退役本地 actor runtime
- 必须显式保护现有 `MCP/skill` capability-market 与 evolution 主链；执行体 provider intake 不能吞并现有 capability acquisition taxonomy

### 11.2.1 旧 donor / 外接项目体系必须显式收口的内容

这部分不能只靠“以后别这么想”处理，必须在实现和删旧台账里显式收口。

1. `项目安装前门` 收口
   - 旧 `/capability-market/projects/install*` 不应继续作为“任意 GitHub 项目导入”的 canonical product surface
   - 后续要么退役，要么降为 compatibility alias，并明确只接受 executor runtime provider
2. `taxonony` 收口
   - `project-package / adapter / runtime-component` 不应继续作为执行层一级产品语义
   - 执行层正式语义应收口成 `ExecutorProvider / control_surface_kind / protocol_surface_kind / workspace_contract_kind`
3. `donor state/service` 收口
   - `CapabilityDonorService / DonorPackageService / CapabilityPortfolioService / donor trust/trial/retirement`
   - 不能继续直接代表执行层主链；要么降为 acquisition/governance 子系统，要么缩窄成 executor provider governance
4. `Runtime Center donor 读面` 收口
   - `/runtime-center/capabilities/donors` 与 `/runtime-center/external-runtimes*`
   - 必须区分“候选供给面”和“当前活动执行体”，不能继续混在同一条执行主链里
5. `旧 donor contract/spec` 收口
   - `project_donor_contracts.py` 及 `2026-04-04/04-06` donor-first 设计
   - 必须补 supersede 或 compatibility 边界，避免继续被理解成 active executor mainline
6. `命名与测试口径` 收口
   - donor-first 测试、task status 和记述文档必须显式标注“这是 compatibility/acquisition 方向，不再是执行层正式方向”

### 11.3 Phase 2 方向

在 V1 主链稳定后，再逐步追加：

- 细粒度 `ExecutionPolicy`
- 多种 `EnvironmentMount`
- skill/MCP 治理状态机
- 角色差异化能力治理
- 更丰富的 Runtime Center 可见面
- 第二、第三执行体适配器
- 统一执行体市场 / provider registry
- 更细的模型成本、策略、路由治理

---

## 12. 最终结论

本次设计的正式结论如下：

1. `CoPaw` 的长期定位是“主脑框架 + 可插拔外部执行层”，不是 `Codex-only` 产品
2. 被替换的是本地多 agent 执行层，不是 CoPaw 主脑
3. `Codex App Server` 是第一条正式控制面，但不是唯一控制面
4. 外部项目 / donor intake 必须收口成“执行体 runtime provider intake”，不再继续以“任意项目接入”为目标
5. 系统必须支持“全部执行位统一一种执行体”与“不同职业绑定不同执行体”两种模式
6. 模型调用必须进入主脑统一治理，而不是完全散落在各执行体私有配置中
7. 第一版采用 `open_default`，优先跑通“主脑派工 -> 执行体执行 -> 事件回流 -> 主脑收尾”的真实闭环
