# CoPaw Codex App Server Hard-Cut Design
日期：`2026-04-20`

---

## 0. 目标

本次设计不是继续增强 CoPaw 现有本地多 agent 执行器，也不是把 Codex 当成普通插件挂在旧执行链后面。

本次设计要完成的是一条明确的硬切路线：

- `CoPaw` 保留主脑、记忆、战略、派工、审批、证据与回流真相
- 现有本地多执行位 runtime 退役
- 多个受控 `Codex` 执行体替代现有多 agent 执行层
- 底层控制面统一收敛到 `Codex App Server`

一句话目标：

> 把 CoPaw 从“自带本地多执行器的主脑系统”升级成“以 App Server 为底层控制协议、以 Codex 为标准执行体、以 CoPaw 为唯一真相源和唯一监工”的长期执行载体。

---

## 1. 设计结论

### 1.1 选定路线

本次选定路线为：

- `CoPaw MainBrain -> CodexRuntimePort -> AppServerAdapter -> Codex`

不选：

- `纯 MCP` 作为主控总线
- `Desktop App` 作为长期底层
- 继续演化本地 `actor_worker / actor_supervisor / delegation execution`

### 1.2 根本判断

CoPaw 不直接“调用 Codex 的某个工具函数”。

CoPaw 负责：

- 创建和恢复执行体
- 下发正式任务
- 选择执行策略
- 接收事件和证据
- 决定继续、插话、停止或收尾

Codex 负责：

- 在受控项目内制定执行 plan
- 执行命令、修改文件、调用 MCP
- 输出计划、证据、阶段完成、任务完成等事件

一句话边界：

> CoPaw 管理 Codex 执行体；Codex 在主脑监管下执行具体动作。

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

### 2.2 CodexRuntimePort

新增 CoPaw 内部统一执行接口。

职责：

- 对外提供“创建执行体、恢复执行体、启动 turn、停止 turn、读取状态”的统一语义
- 隔离上层业务与下层 App Server 协议
- 为未来替换底层实现保留接口位

### 2.3 AppServerAdapter

新增底层适配器，负责：

- 对接 `Codex App Server`
- 管理 thread 和 turn 生命周期
- 接收事件流
- 转发审批请求
- 输出标准化事件到 CoPaw

### 2.4 Codex Thread / Turn

Codex 的 thread/turn 是真实执行单元。

它们不是主脑真相源，只是执行过程载体。

### 2.5 Project Workspace

每个 Codex 执行体绑定一个项目目录。

项目目录承载：

- 角色合同投影
- 角色手册
- 项目说明
- 项目级 Codex 配置
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

以下模块属于被 Codex 执行体替代的旧执行层：

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
- `CodexThreadBinding`
- `CodexTurnRecord`
- `CodexEventRecord`

V1 最小新增模块如下：

- `src/copaw/kernel/codex_runtime_port.py`
- `src/copaw/adapters/codex/app_server_adapter.py`
- `src/copaw/state/models_codex_runtime.py`
- `src/copaw/state/codex_runtime_service.py`
- `src/copaw/kernel/codex_event_ingest_service.py`
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

描述一个 Codex 项目的结构映射。

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

### 4.4 CodexThreadBinding

描述角色/项目与 Codex thread 的绑定关系。

V1 最小字段建议：

- `binding_id`
- `role_id`
- `project_profile_id`
- `thread_id`
- `runtime_status`
- `last_turn_id`
- `last_seen_at`

### 4.5 CodexTurnRecord

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

### 4.6 CodexEventRecord

描述 App Server 原始事件的归档对象。

V1 最小字段建议：

- `event_id`
- `turn_record_id`
- `event_type`
- `source_type`
- `payload`
- `created_at`

派生关系：

- `Assignment` 触发 `CodexTurnRecord`
- `CodexEventRecord` 派生 `EvidenceRecord`
- `CodexEventRecord` 汇总生成 `AgentReport`

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

每个 Codex 项目先统一成以下最小模板：

```text
<codex-project>/
  AGENTS.md
  ROLE.md
  PROJECT.md
  .codex/
    config.toml
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
- `.codex/`：项目级 Codex 配置
- `.agents/skills/`：工作方法增强层
- `plans/`：计划草案和阶段计划
- `reports/`：阶段汇报、日报、周报
- `evidence/`：人类可读的证据索引与产物摘要
- `runtime/`：thread/session 绑定信息和运行态摘要

---

## 7. 消息协议

### 7.1 基本原则

协议必须采用事件驱动，而不是让主脑和 Codex 自由聊天。

原则如下：

- 主脑发任务
- Codex 发事件
- 主脑按事件决定继续、插话、停机或收尾

### 7.2 主脑到 Codex

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

### 7.3 Codex 到主脑

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

- `CodexEventRecord`
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

设计原则：

> 第一版可以弱治理，但不能弱观测。

---

## 9. 第一阶段最小可跑链路

第一阶段只验证一条真实闭环：

1. 用户给主脑一个执行任务
2. 主脑创建 `Assignment`
3. 主脑生成或更新 `AGENTS.md / ROLE.md / PROJECT.md`
4. `CodexRuntimePort` 创建或恢复 thread
5. `AppServerAdapter` 发起 `turn/start`
6. Codex 先产出 `plan`
7. Codex 真执行改动
8. App Server 事件持续回流
9. CoPaw 生成 `EvidenceRecord` 与 `AgentReport`
10. 主脑决定继续或停止

这条链跑通，就证明：

- `Codex` 可以替代现有本地多执行位执行层
- `CoPaw` 可以保留主脑真相链
- `App Server` 可以承担长期底层控制面

---

## 10. V1 明确不做

以下内容不属于第一阶段必须交付：

- 复杂职业权限模型
- 多环境类型治理
- 复杂能力白名单
- MCP 安装审批闭环
- 自动学习 patch 闭环
- 多职业并发调度优化
- 桌面/浏览器/文档三套环境治理细分
- 完整日报/周报自动化体系

第一阶段只证明主链，不追求功能大全。

---

## 11. 风险与后续阶段

### 11.1 主要风险

- App Server 事件归一化不稳会导致 Evidence/Report 派生混乱
- 项目合同层与主脑真相层边界不清会重新长出双真相
- 过早引入复杂职业和环境治理会拖慢主链验证

### 11.2 Phase 2 方向

在 V1 主链稳定后，再逐步追加：

- 细粒度 `ExecutionPolicy`
- 多种 `EnvironmentMount`
- skill/MCP 治理状态机
- 角色差异化能力治理
- 更丰富的 Runtime Center 可见面

---

## 12. 最终结论

本次设计的正式结论如下：

1. `Codex App Server` 是 CoPaw 长期执行层的正式底层控制面
2. `Codex` 替代现有本地多 agent 执行器，而不是替代 CoPaw 主脑
3. `CoPaw` 继续保留唯一主脑、唯一正式真相链和唯一监工职责
4. 第一版采用 `open_default`，优先跑通“主脑派工 -> Codex 执行 -> 事件回流 -> 主脑收尾”的真实闭环
5. 后续能力扩展优先通过 `AGENTS.md / ROLE.md / skill / MCP / ProjectProfile` 演进，而不是继续发明本地执行器
