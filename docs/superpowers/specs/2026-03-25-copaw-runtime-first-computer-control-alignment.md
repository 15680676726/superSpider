# CoPaw Runtime-First Computer-Control Alignment Spec

## 1. 文档定位

本文件不是新的总方案，也不替代以下现有正式文档：

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`

本文件的作用只有一个：

> 把“以 Runtime / Environment / Execution 为中心的整机控制优化”收敛成对现有 `hard-cut autonomy rebuild` 主线的补充视角，而不是再创造第二套顶层架构语言。

因此，本文件使用“Control Plane / Execution Plane / Environment Plane / Knowledge Plane”作为运行视角，但这些平面必须映射回现有正式 7 层架构与唯一自治主链。

换句话说：

> 本文只是 runtime-first 补充视角，不能替代现有 7 层正式总架构，也不能替代现有 hard-cut 主链。

---

## 2. 当前代码基线结论

以下判断基于当前仓库真实代码，而不是理想图：

### 2.1 正确且已经存在的部分

- `MainBrainChatService` 与 `MainBrainOrchestrator` 已经分流。
- `KernelTurnExecutor` 已经是 `chat / orchestrate / auto` 的正式分流入口。
- `Environment` 已经是独立 package，不再只是 capability 附属脚注。
- Runtime Center 已经存在 `core / actor / ops / overview / memory / knowledge / reports / industry` 按域拆分。
- `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan` 已经是正式 hard-cut 主链。

### 2.2 仍然成立的主要问题

- `MainBrainOrchestrator` 已不再只是 `KernelQueryExecutionService` 的 forwarding facade；当前剩余问题主要是这套协调链路还没有继续外扩到 Runtime Center / environment plane / provider demotion 的更大收口面。
- `runtime_service_graph.py` 仍然是偏大的组合根，但 runtime bootstrap 已正式拆出 `repositories / observability / query / execution / domains` 五类装配模块；剩余问题是 assemble、startup prewarm 与 health wiring 还集中在同一入口。
- `runtime_center_routes_core.py` 仍偏重，但已不再承载 `overview / memory / knowledge / reports / industry` 这些域；当前剩余债务主要是 governance/chat/tasks/work-contexts/goals 仍集中在 core，且 `runtime_center_shared.py` 仍偏大。
- `state/models.py` 已转成兼容 re-export 面；canonical/runtime-carrier/override/reporting/prediction/workflow/industry 记录已物理拆到分层模块中。当前剩余工作主要是继续收紧 package 导出层次，而不是继续把记录都堆回单文件。
- `EnvironmentService` 已降为稳定 façade，但环境子域的语义统一与后续收口仍未结束。
- `ProviderManager` 已降为兼容 façade；`registry / storage / resolution / chat-model factory / fallback` 已物理拆成独立协作者，但 bootstrapping、router/CLI 边界与 `memory_manager` 兼容链上仍保留有限 `get_instance()` 入口。

### 2.3 不应再使用的过时表述

以下说法不再准确，不应继续出现在新文档里：

- “主脑聊天仍在后台正式 writeback/kickoff”
- “Runtime Center 仍只有一个大 core 文件”
- “Environment 还只是 capability 附属物”
- “当前还没有正式主脑编排入口”

这些说法会抹掉已经完成的 hard-cut 收口成果，导致下一轮施工再次基于过时地图开工。

---

## 3. 与现有正式架构的映射关系

### 3.1 7 层架构是正式总图

现有正式总图仍然是：

1. 语义编译层
2. 统一能力图谱层
3. 任务挂载环境层
4. 统一运行内核层
5. 风险治理层
6. 证据与观测层
7. 学习与优化层

本文件不重写这 7 层。

### 3.2 四平面只是运行视角

本文件定义的四平面应视为“看系统如何跑起来”的横切视角：

- `Control Plane`
- `Execution Plane`
- `Environment Plane`
- `Knowledge Plane`

它们与 7 层的关系如下：

| 运行视角 | 对应正式层 | 当前核心对象/模块 |
| --- | --- | --- |
| Control Plane | 风险治理层 + 证据与观测层 + 部分统一运行内核层 | `Runtime Center`、`GovernanceService`、`RuntimeHealthService`、`system/self-check` |
| Execution Plane | 统一运行内核层 + 部分语义编译层 | `KernelTurnExecutor`、`MainBrainOrchestrator`、`KernelQueryExecutionService`、`TaskDelegationService`、`ActorMailbox/Worker/Supervisor` |
| Environment Plane | 任务挂载环境层 + 证据与观测层 | `EnvironmentRegistry`、`EnvironmentService`、`SessionMountRepository`、`ObservationCache`、`ActionReplayStore`、`ArtifactStore` |
| Knowledge Plane | 语义编译层 + 学习与优化层 + 证据与观测层 | `StateStrategyMemoryService`、`StateKnowledgeService`、`MemoryRecallService`、`MemoryReflectionService`、`DerivedMemoryIndexService` |

结论：

> 四平面可以用来指导 runtime-first 收口，但绝不能替换现有正式对象模型与 7 层总架构。

---

## 4. 当前最真实的结构判断

### 4.1 组合根

`runtime_service_graph.py` 已经不是零散初始化，而是事实上的组合根。

问题不在“它有没有设计”，而在：

- 组合根过大
- 生命周期边界不够显式
- 控制平面 / 执行平面 / 环境平面 / 知识平面还未正式分模块装配

因此下一步不是发明新的 bootstrap 入口；这一步已经完成。后续重点应转向继续瘦身组合根，并把 orchestrator / environment / provider 的职责边界继续收紧。

### 4.2 主脑

当前主脑链已经分成：

- 纯聊天前台：`MainBrainChatService`
- durable execution 前门：`MainBrainOrchestrator`
- 正式分流器：`KernelTurnExecutor`

这条方向是对的。

当前这一步已经落地为：

- orchestrator 先产出 `execution intent / execution mode / environment binding / recovery mode`
- request runtime context 由 orchestrator 显式提交，再交给 query execution 继续执行
- query runtime 优先消费 orchestrator 已挂载的 intake contract，而不是再次各自判定

因此后续任务不再是“把 orchestrator 从 0 变成 1”，而是继续把这条协调链外扩到更完整的 Runtime Center / Environment / Provider 收口。

### 4.3 Runtime Center

Runtime Center 当前状态应判断为：

- 已按域完成第一轮物理拆分
- URL 已保持稳定
- 但 shared surface 仍然偏大，core 也还没有瘦到最终形态

当前的主要债不是 URL，而是 Python 模块边界：

- `runtime_center_routes_core.py` 仍过重
- `runtime_center_shared.py` 仍承担过多公共 schema / helper / router 责任
- 已退役入口相关 schema 残留已开始清理，但 shared surface 还没彻底收口

### 4.4 状态模型

当前 `state/models.py` 的核心问题已经从“物理没拆开”变成“兼容导出仍然较厚”。

已经存在的对象边界现在已按模块落位，但兼容面仍需要继续约束：

- canonical truth
- runtime carrier
- override
- derived memory/report view

因此下阶段目标应是“物理拆层，不先改字段真义”。

### 4.5 环境域

环境域已经是系统亮点之一。

当前真实问题不是“是否升格”，而是：

- `EnvironmentService` 不应再重新长回第二个大壳
- session / lease / replay / artifact / health 已拆出协作者，但 environment/session/lease 语义仍需继续统一

因此目标应是“把环境 package 内部继续服务化”，而不是“重新定义一套环境概念”。

### 4.6 Provider 层

当前 Provider 层的真实状态应判断为：

- `ProviderManager` 已从“全能中心类”收成 compat façade
- `provider_registry / provider_storage / provider_resolution_service / provider_chat_model_factory / provider_fallback_service` 已落位，配置、存储、迁移、fallback 与 chat-model 构造不再继续堆在一个类里
- 运行时主链里可注入的调用点已经优先改成显式实例，但 `ProviderManager.get_instance()` 仍在 bootstrapping、router/CLI 边界、`memory_manager` 兼容链和 façade 静态入口中保留少量残余

因此当前目标不再是“从 0 开始拆 Provider”，而是继续把残余单例入口压缩到明确兼容边界，而不是让 Provider 重新回到 runtime 平台中心。

---

## 5. 补充设计原则

### 5.1 不允许第二套主链

Runtime-first 收口必须建立在现有 hard-cut 主链上：

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

本文件不允许再引入新的 operator 主写链。

### 5.2 不允许第二套一级对象

如果要表达“整机控制 runtime 语言”，必须优先复用现有对象：

- `RuntimeFrame`
- `EnvironmentMount`
- `SessionMount`
- `DecisionRequest`
- `Assignment`
- `AgentReport`

如果确实需要引入新的术语，只能作为别名或 view model，必须先给出映射：

| 新提法 | 必须映射到的现有正式对象 |
| --- | --- |
| `ExecutionSession` | `SessionMount` / `WorkContext` / runtime thread binding |
| `EnvironmentHandle` | `EnvironmentMount` |
| `ExecutionCheckpoint` | `AgentCheckpointRecord` / `RuntimeFrame` |
| `RecoveryAction` | `DecisionRequest` + runtime recovery command |

未给出映射前，不允许把这些词写成新的一级真相源。

### 5.3 不允许掩盖已完成成果

所有新文档必须显式承认：

- chat/orchestrate 已拆
- hard-cut 主链已切
- environment package 已存在
- runtime-center 已部分拆分

否则就是把仓库拉回旧基线。

---

## 6. 推荐的重构任务组

以下任务组是在当前真实代码基础上的修正版，而不是从零构思。

### A. 正式拆分 runtime bootstrap

目标：

- 保留 `build_runtime_bootstrap(...)` 外部入口
- 把现有 `runtime_service_graph.py` 内部 helper 正式拆成多文件装配模块

重点不是改行为，而是让依赖边界显式化。

### B. 把 orchestrator 做实

目标：

- 保持 `KernelTurnExecutor` 为正式入口
- 保持 `MainBrainChatService` 为纯聊天链
- 把 `MainBrainOrchestrator` 扩成真正的协调者

应新增的协调责任至少包括：

- request classification
- execution mode planning
- environment coordination
- recovery coordination
- result commit

### C. 清理 Runtime Center 共享边界

目标：

- 把 `core / actor / ops` 从“共享一个大 shared 模块”继续收缩成按域依赖
- 删除退役 delegate schema 和旧共享 helper 扩散
- 保持现有 URL，不先动前端路径

### D. 物理拆分 state models

目标：

- 第一轮只拆模块与 import
- 不先重命名 record
- 不先重写 repository contract

建议优先拆成：

- `models_core`
- `models_goals_tasks`
- `models_agents_runtime`
- `models_memory`
- `models_reporting`
- `models_industry`
- `models_prediction`
- `models_governance`

### E. 继续服务化 Environment package

目标：

- 保持 `EnvironmentService` 对外 façade
- 内部拆出 session / lease / replay / artifact / health 协调服务，并把 observation 读面并入 replay/evidence 侧
- 统一 environment/session/lease 命名归属

### F. 降权 ProviderManager

目标：

- 拆出 registry / storage / resolution / factory / fallback
- 保留 `ProviderManager` 仅作为 compat façade
- 减少全仓静态 `get_instance()` 外溢

### G. Runtime-first vocabulary 只能作为映射层

目标：

- 可以整理“整机控制”叙事语言
- 但必须把语言映射回现有正式对象
- 不允许变成新的 state truth 或新的 planner vocabulary

---

## 7. 推荐实施顺序

### 第一优先级：结构拆边界

1. `runtime_service_graph.py`
2. `runtime_center_routes_core.py` / `runtime_center_shared.py`
3. `state/models.py`

原因：

- 这些工作风险相对可控
- 能直接降低后续主脑/环境改造成本

### 第二优先级：做实主脑

4. `MainBrainOrchestrator`
5. execution planner / environment coordinator / recovery coordinator / result committer

原因：

- 主脑边界已经存在，现在差的是实装强度

### 第三优先级：环境域内部服务化

6. `EnvironmentService` 内部分解
7. 继续统一 session / lease / replay / artifact 语义与所有权

### 第四优先级：provider 降权与遗留清理

8. 拆 `ProviderManager`
9. 清理 runtime-center 共享残留与 retired schema
10. 清理全仓 `ProviderManager.get_instance()` 直接依赖

---

## 8. 非目标

本补充 spec 当前不主张：

- 再创建一个新的“ComputerControlRuntime”一级核心对象
- 重画一张替代 `MASTERPLAN` 的总架构图
- 先做大量新 desktop/browser 能力，再回头拆边界
- 把现有 hard-cut 主链重新包回旧 `goal/task/schedule` 心智

---

## 9. 验收标准

当本补充 spec 对应的重构完成时，至少应满足：

1. `runtime_service_graph.py` 只保留轻量 assemble 逻辑
2. `MainBrainOrchestrator` 不再只是 forwarding facade
3. Runtime Center 路由按域清晰拆开，`runtime_center_shared.py` 不再是大杂烩
4. `state/models.py` 已物理拆层
5. `EnvironmentService` 已降为 façade，环境子域服务独立
6. `ProviderManager` 不再作为全仓单点 runtime 入口
7. runtime-first 文档语言全部能映射到现有正式对象模型，不再新增第二套真相源

---

## 10. 最终结论

“以 Runtime / Environment / Execution 为中心的整机控制优化”这个方向是对的。

但它只能作为：

> 对现有 `hard-cut autonomy rebuild` 主线的补充强化

不能再变成：

> 一套与 `MASTERPLAN + TASK_STATUS + DATA_MODEL_DRAFT` 平行竞争的新总架构。

当前最正确的做法不是“重写世界观”，而是：

- 承认已经完成的收口成果
- 在真实基线上继续拆边界
- 把 orchestrator、environment、runtime-center、state-model、provider 五个剩余大壳真正拆开
- 用现有正式对象模型承接整机控制叙事
