# CoPaw 理想载体升级总方案

## 0. 文档目的

这份文档是 `CoPaw` 升级为“长期自主执行载体”的总设计说明书。

它用于在未来多次迭代中，持续回答以下问题：

- 这次升级的最终目的是什么
- 升级的方向是什么
- 需要改哪些内容
- 按什么流程推进
- 各阶段的交付物和验收标准是什么
- 代码应该遵守什么规范
- 改动规模有多大，预计要多久完成

如果本次升级没有一次完成，下次重新打开本仓库时，优先阅读本文件即可快速恢复上下文。

`2026-03-26` supplement:

- `n8n / Workflow Hub` 不再是目标架构组件；它只代表一段已完成但已被放弃的旧基线
- 固定 SOP 后续必须收口为 CoPaw 内部的 `Native Fixed SOP Kernel`，不再依赖外部 workflow adapter 作为正式产品面
- 浏览器、桌面应用、文件/文档等真实电脑操作继续归 execution agent 的 `Agent Body Grid` 负责，而不是交给 SOP 编排层
- execution-side browser / desktop / document surface 后续必须统一落到
  `EnvironmentMount / SessionMount`，并共享同一组 host/session/handoff/recovery 契约；
  browser 只额外追加 `Browser Site Contract`，Windows desktop 只额外追加 `Desktop App Contract`
- `2026-03-27` 正式目标框架补充：
  - 上位正式目标改为 `Intent-Native Universal Carrier`
  - execution-side 正式框架改为 `Symbiotic Host Runtime`
  - `Full Host Digital Twin` 保留为正式成熟态，但不得被当成“一次性全量施工”的单阶段目标
  - 详细定义见 `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`

---

## 1. 升级目标

### 1.1 最终目标

把 `CoPaw` 从“多渠道 AI 助手 / 聊天执行平台”，升级为“可长期运行的本地自治执行载体”。

最终形态不是继续堆更多按钮，而是形成 5 个单一核心：

- 单一真相源
- 单一运行内核
- 单一能力图谱
- 单一证据链
- 单一 patch 演进模型

### 1.1.1 正式目标框架

当前正式目标框架应按两层理解：

- 上位正式目标：`Intent-Native Universal Carrier`
- execution-side 正式框架：`Symbiotic Host Runtime`

含义：

- CoPaw 的目标不只是“更强地控制浏览器/桌面”，而是成为 AI 想法的统一执行载体
- Windows 宿主、浏览器、文档、应用是当前最强、最关键的一组本地执行环境，但不是唯一世界
- execution-side 深绑定仍然必须落回统一 `state / evidence / capability / environment` 主链
- `Full Host Digital Twin` 是正式成熟态，不是一次性单阶段交付物

### 1.2 理想载体的核心特征

理想载体应具备以下能力：

- 能把高层目标编译成长期计划、角色分工与任务 seed
- 能把 `skill / MCP / tool` 统一成同一能力语义
- 能给长期任务挂载持续环境，而不是每轮重新构建世界
- 能用一个统一内核处理渠道、cron、交互、执行、状态与风险
- 能对所有动作留存证据、支持回放与审计
- 能把学习与优化输出为标准 patch，而不是隐式改变人格或系统事实

### 1.3 非目标

本次升级**不以“新增更多用户可见小功能”为第一目标**。以下事项不是第一优先级：

- 再增加一批零散工具按钮
- 继续堆更多独立页面而不统一底层模型
- 先做宏大的行业世界模型但不统一运行真相
- 让多个平级 agent 长期各自维护一套状态

---

## 2. 当前 CoPaw 的定位与差距

### 2.1 当前 CoPaw 的优势

`CoPaw` 已经具备可复用的优质底座：

- 多渠道接入层已经存在，可作为载体的“耳目与通道”
- Provider / 本地模型适配层已存在，可作为模型接入底座
- 文件、shell、浏览器、桌面等工具执行能力已存在，可复用为执行器
- FastAPI / CLI / 控制台外壳已存在，可继续作为操作面与治理面
- cron、MCP、workspace 等模块已具备实装基础

### 2.2 当前 CoPaw 的关键不足

当前版本距离“理想载体”仍有明显差距：

- 真相源分散在 `config / jobs / chats / sessions / managers` 中
- 运行主链仍偏“请求驱动的一次性会话执行”
- `skill / MCP / tool` 三套能力语义并存
- 长期任务没有统一、持续的环境挂载
- 证据链不统一，日志、会话、管理页面并未形成单一审计模型
- 学习与优化没有 patch 化，缺乏可回滚的成长轨迹

### 2.3 核心判断

本次升级应采用的不是“继续缝补现有主链”，而是：

> 保留 CoPaw 的边缘适配层与操作壳，重构 CoPaw 的状态中枢、运行内核、能力模型、环境模型与证据模型。

---

## 3. 升级总原则

### 3.1 真相原则

- 所有运行态必须有单一真相源
- 运行态不能同时散落在多个 manager、多个 JSON、多个临时对象中
- 配置文件只描述“声明式配置”，不再承载核心运行真相

### 3.2 内核原则

- 全系统只保留一个公开主内核：`SRK`（Single Runtime Kernel）
- `fastloop` 之类短回合执行器只作为 SRK 的内部执行组件
- 控制面、渠道接入、cron、交互 API 都只接入 SRK，不再成为平行事实源

### 3.3 能力原则

- 不再并列维护 `skill / MCP / tool` 三套主语义
- 所有能力统一抽象为 `CapabilityMount`
- 所有能力必须显式声明环境需求、风险级别、证据产出与角色开放范围

### 3.4 环境原则

- 长期任务必须拥有持续环境，不再每次执行都“重新投胎”
- 环境是第一类对象，至少包括浏览器、桌面、渠道会话、工作目录、观察缓存、回放句柄、产物存储
- execution-side 当前应遵守：
  - `native-first`
  - `host-companion-backed`
  - `workspace-centered`
  - `event-driven`
  - `ui-fallback`

### 3.5 风险原则

- 审批模型仅保留 3 档：`auto / guarded / confirm`
- 高风险、不可逆、外部执行边界动作必须确认
- 其余优化应允许自动应用，但必须记录工作日志与证据

### 3.6 证据原则

- 所有外部动作必须产出 `EvidenceRecord`
- 所有长期运行必须可回放
- 所有 agent 的变化必须进入成长轨迹

### 3.7 学习原则

- 学习层不直接偷偷改运行态
- 学习输出只允许是标准 patch
- 低风险 patch 可自动 apply，高风险 patch 必须走确认路径

---

## 4. 目标架构：7 层结构

### 4.1 语义编译层（Semantic Compiler）

**职责**

- 接收行业画像、子行业、经营目标、约束与历史运行数据
- 编译出团队蓝图、角色定义、经营计划、长期任务 seed
- 提供高层世界模型、风险本体与节奏生成

**输入**

- 行业画像
- 子行业信息
- 长期目标
- 约束条件
- 历史运行结果

**输出**

- `TeamBlueprint`
- `RoleBlueprint`
- `BusinessPlan`
- `LongHorizonTaskSeed[]`

**说明**

这是“前额叶”层，不直接执行，不直接控制底层工具。

---

### 4.2 统一能力图谱层（Capability Graph）

**统一对象：`CapabilityMount`**

每个能力只描述 5 件事：

- 能做什么
- 需要什么环境
- 风险级别
- 对哪些角色开放
- 会产生什么证据

**职责**

- 统一封装 tool / MCP / skill
- 提供按角色、按环境、按风险过滤能力的能力注册表
- 为内核提供稳定、可审计的能力查询接口

---

### 4.3 任务挂载环境层（Environment Mounts）

**核心对象**

- `EnvironmentMount`
- `SessionMount`
- `ObservationCache`
- `ActionReplay`
- `ArtifactStore`

**职责**

- 为任务或角色提供持续环境句柄
- 保持浏览器、桌面、渠道、工作目录与文件视图的连续性
- 将观测与动作证据化、可回放化
- 为 execution-side live surfaces 提供统一 host/session/handoff/recovery contract，
  而不是让 browser/desktop 各自发明第二套运行语言

**关键目标**

从“每轮新建 agent 和工具上下文”，升级为“任务持有持续身体”。

**执行侧补充**

- 主脑不直接控制浏览器或桌面；主脑只分派和监督，真正持有 surface 的是 execution agent
- `Agent Body Grid` 现在应被理解为 `Symbiotic Host Runtime` 的 execution substrate，而不是独立于 carrier 目标的传统 computer-control 子系统
- execution-side 当前正式阶段应先落成 `Windows Seat Runtime Baseline`，即：
  - `Seat Runtime`
  - `Host Companion Session`
  - 最小 `Workspace Graph` projection
  - 最小 `Host Event Bus` mechanism
  - browser/document/app 三类必备执行能力
- browser / desktop / document live surface 应先暴露 shared `Surface Host Contract`
  字段，例如 `host_mode / lease_class / access_mode / session_scope / handoff_state /
  resume_kind / verification_channel`
- 优先级必须是：
  - `Cooperative Adapter / Native semantic path`
  - `semantic operator`
  - `visual fallback`
- browser writer work 还需要 `Browser Site Contract`
- 当前仓库的 desktop/app runtime 以 Windows-first 为正式基线，并通过 `Desktop App Contract`
  表达 app/window/control-channel/writer-lock 细项
- `Full Host Digital Twin` 只应被视为 host-side 成熟态，不得跳过前序 `Seat Runtime / Workspace projection / Host Event mechanism` 直接施工

---

### 4.4 统一运行内核层（SRK）

**唯一主内核：`SRK`**

**职责**

- 意图接入
- 任务调度
- agent 生命周期管理
- 任务状态管理
- 能力挂载
- 环境挂载
- 风险决策
- 结果提交与证据写入

**说明**

- `SRK` 是唯一主链
- 短回合执行器、控制台 API、cron、channels 都是 `SRK` 的边缘接口，而不是独立真相源

---

### 4.5 风险治理层（Risk Governance）

**三档模型**

- `auto`
- `guarded`
- `confirm`

**职责**

- 统一判断动作的风险档位
- 为内核提供“是否可自动执行”的裁决
- 为日志、日报、补丁应用提供统一边界模型

---

### 4.6 证据与观测层（Evidence & Observability）

**观测面只看 5 件事**

- 当前目标
- 当前环境
- 当前 owner
- 当前风险
- 当前证据

**职责**

- 所有动作都写入证据
- 所有长期运行都支持回放
- 所有状态变更都可追踪

---

### 4.7 学习与优化层（Learning & Optimization）

**职责**

- 发现瓶颈
- 生成 proposal
- 产出 patch
- 对低风险 patch 自动 apply

**标准 patch 类型**

- `profile_patch`
- `role_patch`
- `capability_patch`
- `plan_patch`

**说明**

学习层不应是“另一套系统”，而应是 SRK 的上层优化回路。

---

## 5. 理想主链

最终的主链应为：

1. 用户输入行业画像 / 目标 / 约束
2. 系统载入世界模型
3. 语义编译层生成团队蓝图与计划
4. 为角色挂载能力图谱
5. 为任务挂载环境
6. 对“系统不能做 / 不该做 / 暂时缺少宿主证明”的步骤，显式物化为 `HumanAssistTask`
7. SRK 接管任务调度、阻塞、人工协作 handoff 与恢复生命周期
8. 自动执行
9. 自动记录证据
10. 自动生成日报 / 周报
11. 对低风险优化自动生成并应用 patch
12. 对高风险变更提交确认

补充约束：

- `HumanAssistTask` 不是第二条聊天主链，也不是 prompt 里的提醒文案
- 它是正式运行对象，用来承接 `blocked-by-proof / human-owned checkpoint`
- 它必须带验收契约、证据锚点与恢复点，不能只靠“用户口头说完成了”直接闭环

---

## 6. 目标核心对象模型

建议在升级后统一引入以下核心对象：

### 6.1 运行与规划对象

- `Goal`
- `TeamBlueprint`
- `RoleBlueprint`
- `BusinessPlan`
- `Task`
- `HumanAssistTask`
- `TaskRuntime`
- `RuntimeFrame`

### 6.2 能力对象

- `CapabilityMount`
- `CapabilityPolicy`
- `CapabilityExecutor`

### 6.3 环境对象

- `EnvironmentMount`
- `SessionMount`
- `ObservationCache`
- `ActionReplay`
- `ArtifactStore`

### 6.4 治理与证据对象

- `EvidenceRecord`
- `DecisionRequest`
- `RiskDecision`
- `GrowthTrajectory`

### 6.5 学习与变更对象

- `Patch`
- `PatchProposal`
- `PatchApplyResult`

---

## 7. CoPaw 现有模块与目标架构的映射

### 7.1 保留并迁移的模块

- `src/copaw/app/channels/*`
  - 继续作为渠道 adapter
- `src/copaw/providers/*`
  - 继续作为模型 provider adapter
- `src/copaw/agents/tools/*`
  - 继续作为底层 capability executor 的实现基础
- `src/copaw/cli/*`
  - 继续作为运维、操作与接入外壳
- `console/src/*`
  - 继续作为控制台 UI 壳

### 7.2 需要重构的模块

- `src/copaw/app/_app.py`
  - 从装配中心降级为边缘接入壳
- `src/copaw/app/runner/runner.py`
  - 从一次性聊天执行器升级为 SRK 的一部分
- `src/copaw/agents/react_agent.py`
  - 降级为 SRK 内部短回合执行器
- `src/copaw/agents/skills_manager.py`
  - 被统一能力注册表取代
- `src/copaw/config/config.py`
  - 只保留声明式配置，不再承载核心运行真相
- `src/copaw/app/crons/*`
  - 转为 schedule ingress，而不是平行主链

---

## 8. 新目录结构建议

建议新增并逐步迁移到如下结构：

```text
src/copaw/
  kernel/
    srk.py
    intent_ingress.py
    scheduler.py
    lifecycle.py
    runtime_frame.py
    risk_gateway.py
  state/
    models.py
    repositories/
    migrations/
    store.py
  capabilities/
    models.py
    registry.py
    executors/
    providers/
  environments/
    models.py
    manager.py
    browser/
    desktop/
    channel/
    workspace/
  evidence/
    models.py
    ledger.py
    replay.py
    artifacts.py
  compiler/
    team_compiler.py
    role_compiler.py
    plan_compiler.py
  learning/
    analyzer.py
    proposals.py
    patches.py
  compatibility/
    runner_adapter.py
    cron_adapter.py
    channel_adapter.py
```

说明：

- 新内核与新数据模型先以新增目录方式落地
- 旧系统通过 `compatibility/` 层渐进迁移，不建议 Big Bang 一次性替换

---

## 9. 代码规范与工程规范

### 9.1 总体规范

- 所有新功能优先围绕单一真相源设计
- 不允许新增平行事实源
- 不允许新增绕过内核直接修改运行态的路径
- 所有外部副作用必须通过统一 capability 执行
- 所有状态变更必须能追溯到证据与 patch

### 9.2 数据与状态规范

- `config.*` 只负责声明式配置
- `state.*` 负责运行真相
- `artifacts/` 只放大对象，不放运行真相
- 不允许多个 manager 各自私有持有关键状态并长期漂移

### 9.3 能力规范

- 新增能力必须注册为 `CapabilityMount`
- 新增能力必须声明：用途、环境需求、风险级别、开放角色、证据产出
- 禁止新增“仅在 prompt 文本里存在，但系统模型不可见”的能力

### 9.4 环境规范

- 所有长期任务必须通过 `EnvironmentMount` 获取上下文
- 需要持续浏览器、桌面、渠道、文件视图时，必须显式挂载会话
- 禁止在没有 mount 的情况下长期持有隐式临时状态

### 9.5 风险规范

- 风险决策只允许 `auto / guarded / confirm`
- 审批边界必须由统一风险网关控制
- 不允许在业务代码中到处散落自定义审批逻辑

### 9.6 证据规范

- 所有外部动作都必须产生 `EvidenceRecord`
- 所有 patch 应关联来源证据
- 日报、周报、审计面板只读取证据系统，不读取散乱日志拼接

### 9.7 学习规范

- 学习层只产出 proposal 与 patch
- 低风险 patch 可以自动应用，但必须留下证据
- 高风险 patch 必须进入确认流

### 9.8 兼容迁移规范

- 优先渐进迁移，不一次性推翻所有旧接口
- 新内核上线期间，旧接口通过适配层转到新模型
- 每个阶段都要定义可回滚边界

### 9.9 测试规范

每个阶段必须同时补齐：

- 单元测试：对象模型、策略、判定逻辑
- 集成测试：kernel 与 adapter 协作
- 端到端测试：典型主链（渠道/cron/执行/证据）

测试策略要求：

- 新内核的测试优先级高于新增页面测试
- 运行主链测试优先级高于宣传功能测试
- Windows / macOS / Linux 的差异路径必须有回归覆盖

---

## 10. 升级实施流程

### 10.1 总体策略

采用 **“保留边缘、重构中枢、渐进替换”** 的策略。

推荐迁移顺序：

1. 统一状态与证据
2. 统一能力图谱
3. 引入持续环境挂载
4. 引入 SRK 唯一内核
5. 收口风险治理
6. 重构控制台与 API 为新内核视图
7. 引入语义编译层
8. 引入学习与 patch 优化层

### 10.2 禁止的做法

- 不要先做复杂多 agent 编排
- 不要先做行业大脑而忽略底层状态统一
- 不要让旧 manager 体系与新 SRK 长期双写
- 不要继续堆分散设置页而不统一数据模型

---

## 11. 分阶段详细规划

> 说明：以下时间为粗略工程估算。
>
> 默认前提：
>
> - 由 1 名主开发者持续推进，并配合 AI 辅助
> - 同时需要维护现有仓库基本可运行
> - 不含大规模商业化 polish 与多组织联调

---

### Phase 0：基线冻结与设计校准

**目标**

- 冻结现有 CoPaw 主链认知
- 明确新对象模型、迁移策略与边界
- 建立后续升级的 ADR / 术语表 / 里程碑机制

**主要工作**

- 梳理现有模块边界与数据流
- 明确旧系统中哪些是保留层、哪些是待替换层
- 输出对象模型草图与迁移关系图
- 制定分阶段验收标准

**交付物**

- 本总方案文档
- 对象模型草图
- 迁移地图
- 阶段性验收清单

**验收标准**

- 团队对“最终目标”“迁移顺序”“内核定义”达成一致
- 没有关键术语歧义

**预计时间**

- `2 ~ 4` 天

---

### Phase 1：统一状态与证据基线

**目标**

- 建立单一真相源雏形
- 建立统一证据账本雏形

**主要工作**

- 引入 `state/` 模块与数据库存储（优先 SQLite）
- 定义 `Goal / Task / TaskRuntime / EvidenceRecord / Patch` 等核心表
- 将当前 `jobs / chats / sessions` 的核心运行态映射进新 store
- 引入 `EvidenceLedger` 与 `ArtifactStore`

**建议改动范围**

- 新增：`src/copaw/state/*`
- 新增：`src/copaw/evidence/*`
- 适配：`src/copaw/app/runner/*`
- 适配：`src/copaw/app/crons/*`

**阶段输出**

- `state.db` 或等价持久化层
- 统一对象模型与仓储接口
- 最小化证据写入链路

**验收标准**

- 至少一条主链可以把任务状态与证据统一写入新 store
- 不再新增新的平行状态 JSON

**主要风险**

- 旧会话迁移复杂
- 新旧状态双写容易漂移

**预计时间**

- `1.5 ~ 2.5` 周

---

### Phase 2：统一能力图谱

**目标**

- 把 `tool / skill / MCP` 收口为统一的能力语义

**主要工作**

- 定义 `CapabilityMount`
- 建立 `CapabilityRegistry`
- 为现有工具能力生成统一描述
- 为 MCP client 生成远程能力描述
- 为 skill 生成声明式能力条目

**建议改动范围**

- 新增：`src/copaw/capabilities/*`
- 适配：`src/copaw/agents/tools/*`
- 适配：`src/copaw/agents/skills_manager.py`
- 适配：`src/copaw/config/config.py` 中 MCP 配置

**阶段输出**

- 统一能力注册表
- 角色可见能力过滤逻辑
- 风险标签基础能力表

**验收标准**

- 至少 80% 常用能力可通过 `CapabilityRegistry` 查询
- 新内核不再直接区分“这是 tool 还是 MCP 还是 skill”

**主要风险**

- 旧 prompt 和旧 agent 对能力来源耦合较深
- 某些 skill 更像说明书而非执行能力，需要拆层

**预计时间**

- `1.5 ~ 2` 周

---

### Phase 3：环境挂载与持续身体

**目标**

- 补齐长期任务最缺失的“持续环境”，并把 execution-side 正式升级到 `Symbiotic Host Runtime` 的第一阶段：`Windows Seat Runtime Baseline`

**主要工作**

- 定义 `EnvironmentMount / SessionMount / ObservationCache / ActionReplay`
- 定义 execution-side shared `Surface Host Contract`
- 定义 `Seat Runtime` 与 `Host Companion Session`
- 先实现最关键两类 mount：
  - 浏览器环境
  - 工作目录 / 文件视图环境
- 再逐步扩展：
  - Windows-first 桌面环境
  - 渠道会话环境
- 为任务提供最小 `Workspace Graph` projection
- 为宿主变化提供最小 `Host Event Bus` mechanism
- 为高价值本地能力预留 `Cooperative Adapter` 挂载位
- 为 browser 补 `Site Contract`，为 Windows desktop 补 `Desktop App Contract`
- 为长任务分配可续存的环境 lease

**建议改动范围**

- 新增：`src/copaw/environments/*`
- 适配：浏览器 / shell / file 工具
- 新增：Windows host companion / workspace graph / host events
- 适配：voice / channels 中与会话相关的路径

**阶段输出**

- 首批 `EnvironmentMount` 实现
- `Seat Runtime Baseline`
- execution-side shared surface host/site/app contract 基线
- 最小 `Workspace Graph` projection 与 host event mechanism 基线
- 任务级环境持有与回收机制
- 初版观测缓存与动作回放接口

**验收标准**

- 至少一个 execution agent 能持续持有同一具 Windows seat，并跨 `browser + app + file/doc` 连续工作
- 同一任务多轮执行不再依赖纯 prompt 记忆恢复环境
- Runtime Center/Agent Workbench 对 live browser/desktop 至少能显示 shared host contract，
  且已知 writer site/app 不再在无 contract 情况下默许执行
- cooperative/native path 已成为优先实现方向，UI fallback 不再被当作唯一架构主语义
- `Full Host Digital Twin` 不作为本阶段完成标准；本阶段只要求把 `Seat Runtime / Workspace projection / Host Event mechanism` 基线做实

**主要风险**

- 环境资源泄漏
- 浏览器与桌面环境跨平台行为不一致
- 若直接跳过 `Seat Runtime Baseline` 去追求全量 host twin，极易把执行链重新做成第二真相源或过重的 Windows 控台产品

**预计时间**

- `2 ~ 3` 周

---

### Phase 4：SRK 唯一内核落地

**目标**

- 用单一运行内核接管任务生命周期与调度

**主要工作**

- 实现 `SRK` 核心接口：
  - `submit_intent`
  - `schedule_task`
  - `attach_capabilities`
  - `attach_environment`
  - `run_turn`
  - `commit_result`
- 将 `AgentRunner` 改造成 SRK 内部短回合执行器
- 让 channels / cron / API 都通过 SRK 接入

**建议改动范围**

- 新增：`src/copaw/kernel/*`
- 重构：`src/copaw/app/runner/runner.py`
- 重构：`src/copaw/app/crons/*`
- 适配：`src/copaw/app/channels/*`

**阶段输出**

- 单一运行主链
- 兼容层：旧接口 -> SRK
- 生命周期管理、状态更新与结果提交闭环

**验收标准**

- 渠道消息、定时任务、手动触发至少 3 类入口都由 SRK 调度
- 不再允许平行 manager 长期直接驱动主执行路径

**主要风险**

- 这是重构脊柱，风险最大
- 若边界不清，容易产生“旧 runner + 新 kernel”双主链

**预计时间**

- `2 ~ 3` 周

---

### Phase 5：风险治理统一化

**目标**

- 引入 `auto / guarded / confirm` 三档统一风险模型

**主要工作**

- 定义风险分类规则
- 实现 `RiskGateway`
- 为高风险 capability 和外部副作用动作接入确认链路
- 为低风险优化与 patch 应用提供自动化边界

**阶段输出**

- 风险分类器
- 统一确认流
- 决策记录与证据关联

**验收标准**

- 系统中不再散落多套审批逻辑
- 所有高风险动作都能被统一挡住并形成 `DecisionRequest`

**预计时间**

- `0.5 ~ 1` 周

---

### Phase 6：控制台与 API 迁移到新模型

**目标**

- 让前端从“设置台”升级为“运行中心”

**主要工作**

- 控制台改为围绕以下视图组织：
  - 当前目标
  - 当前环境
  - 当前 owner
  - 当前风险
  - 当前证据
- 路由和接口不再直接绑定旧 manager 概念
- 引入运行态、证据态、patch 态的统一 API

**建议改动范围**

- `console/src/*`
- `src/copaw/app/routers/*`

**阶段输出**

- 新控制台信息架构
- 与 SRK / state / evidence 对齐的 API 层

**验收标准**

- 控制台可直接查看任务、环境、风险、证据
- 页面不再依赖旧分散 manager 作为核心数据源

**预计时间**

- `1 ~ 2` 周

---

### Phase 7：语义编译层落地

**目标**

- 让系统拥有“前额叶”，能从行业画像编译出经营世界

**主要工作**

- 定义 `TeamBlueprint / RoleBlueprint / BusinessPlan`
- 构建从用户输入到长期任务 seed 的编译流程
- 把编译输出接入 SRK 的计划与调度入口

**阶段输出**

- 团队蓝图编译器
- 角色编译器
- 计划编译器

**验收标准**

- 系统可从结构化画像生成一套可执行的角色与任务框架
- 编译层只输出计划与 seed，不直接越权执行底层动作

**预计时间**

- `1.5 ~ 2.5` 周

---

### Phase 8：学习与 patch 优化层

**目标**

- 让系统能基于证据进行可审计的持续优化

**主要工作**

- 建立瓶颈分析器
- 建立 proposal 生成器
- 建立 patch 管理与 apply 流程
- 为低风险 patch 提供自动应用能力

**阶段输出**

- `PatchProposal`
- `PatchApplyResult`
- 成长轨迹记录

**验收标准**

- 学习输出全部转为 patch
- 低风险 patch 可自动 apply，高风险 patch 必须确认
- 所有 patch 都可追踪来源证据与回滚

**预计时间**

- `1.5 ~ 2.5` 周

---

## 12. 改动规模评估

### 12.1 改动性质

本次升级属于：

> **换脊柱级重构，而不是局部增强。**

### 12.2 改动大小判断

可粗略估计为：

- 后端核心运行链：`60% ~ 70%` 级别重构
- 状态与数据模型：`70%+` 级别重构
- 前端控制台的数据模型与信息架构：`30% ~ 50%` 级别重构
- 边缘适配层（channels / providers / tools）：保留为主，`20% ~ 30%` 改造

### 12.3 工程量结论

这不是几个 PR 就能完成的工作，也不适合靠“先补一点功能”自然演化到终态。

正确判断应为：

- 保留壳
- 保留边缘适配器
- 重构中枢

---

## 13. 时间估算

### 13.1 MVP 时间估算

如果目标是先做出“理想载体雏形”，建议 MVP 只覆盖：

- Phase 0
- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5 的基础版

**预计时间**

- 单人主开发：`6 ~ 9` 周
- 2~3 人小团队：`4 ~ 6` 周

### 13.2 完整版时间估算

如果目标是覆盖完整 7 层并形成较稳定闭环：

- 单人主开发：`10 ~ 16` 周
- 2~3 人小团队：`6 ~ 10` 周

### 13.3 影响工期的关键因素

- 是否坚持渐进迁移而非 Big Bang
- 是否同时背负大量现网兼容需求
- 浏览器 / 桌面 / 跨平台环境挂载复杂度
- 是否同步做大规模控制台 UI 重构
- 是否要把语义编译层做得很深

---

## 14. 推荐里程碑

### Milestone A：运行事实统一

- `state + evidence` 基础打通
- 至少一条执行主链进入统一 store

### Milestone B：能力与环境统一

- `CapabilityRegistry` 可用
- 首批环境挂载可用

### Milestone C：SRK 接管主链

- channel / cron / API 入口统一通过 SRK 调度

### Milestone D：运行中心上线

- 控制台改为围绕任务、环境、风险、证据展示

### Milestone E：语义编译与学习闭环

- 语义编译、patch 优化与成长轨迹接入系统主链

---

## 15. 下一次继续升级时的恢复入口

如果下次继续推进本升级，建议按以下顺序恢复上下文：

1. 先阅读本文件 `第 1, 3, 4, 10, 11, 12, 13` 节
2. 明确当前停在哪个 Phase
3. 检查以下 5 个对象是否已落地：
   - `SRK`
   - `CapabilityMount`
   - `EnvironmentMount`
   - `EvidenceRecord`
   - `Patch`
4. 只要这 5 个对象没落稳，就不要过早上复杂上层能力

---

## 16. 最终结论

`CoPaw` 非常适合被改造成理想载体，但方式必须正确。

正确方式不是继续把它做成“功能更多的助手平台”，而是把它升级成：

> 一个统一事实、统一能力、统一环境、统一证据、统一 patch 的本地自治执行内核。

简化成一句工程决策：

> 保留 CoPaw 的手脚耳目，重做 CoPaw 的脊柱和中枢。
---

## 11. 2026-03-18 同步：主脑长期自治升级方向

post-`V6` 的下一正式阶段已登记为 `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`。

这轮的目标不是推翻当前 `state / evidence / capabilities / environments / kernel / goals / routines / runtime-center` 骨架，
而是在其上把以下语义正式化：

- 单主脑长期身份
- 单主脑长期目标
- 周期规划 `daily / weekly / event`
- 职业派工
- 结构化汇报回流
- Runtime Center / `/industry` / `Chat` / `AgentWorkbench` 的同链路可见化
- `2026-03-30` supplement: memory architecture has converged to `truth-first` and `no-vector formal memory`; shared formal memory is rebuilt from canonical `state / evidence / runtime`, while private conversation compaction stays isolated and non-canonical. QMD/vector references are physically removed residuals, not pending runtime cleanup.

当前系统已经具备“行业实例 + goals/schedules 自动驱动”的持续运行能力；
`V7` 要解决的是让系统正式升级为：

`main brain carrier -> strategy -> lanes -> cycle -> assignments -> execution -> reports/evidence -> reconcile -> next cycle`

详细对象表、后端改造表、前端同步表、测试要求与改动规模见：

- `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`

## 17. 2026-03-21 同步：旧 `n8n` SOP Adapter / Workflow Hub 边界（历史基线，已退役）

本节只记录 `2026-03-21` 时点的旧基线，避免后续回看时失去历史上下文。

`2026-03-26` 起，以下口径已经被新方案取代：

- `SOP Adapter + Workflow Hub` 不再是固定 SOP 的正式落位
- 旧 `sop_binding_id -> system:trigger_sop_binding -> SopAdapterService` 链进入 retirement set
- 前端 `Capability Market -> 精选中心 -> 工作流` 不再是目标产品面
- 正式替代物为 CoPaw 内建 `Native Fixed SOP Kernel`

本节唯一仍保留的有效架构结论只有：

- 固定 SOP 即使存在，也位于 workflow / schedule 层之上，而不是 routine engine 内部
- routine 层继续只负责 `browser / desktop` 叶子执行记忆
- canonical run truth 继续留在统一 `state / evidence / report` 主链，即：
  - `WorkflowRunRecord`
  - `ExecutionRoutineRecord`
  - `RoutineRunRecord`
  - `EvidenceRecord`
  - `AgentReportRecord`
  - `ReportRecord`
