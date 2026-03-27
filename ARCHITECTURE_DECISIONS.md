# ARCHITECTURE_DECISIONS.md

本文件用于记录 `CoPaw` 在“理想载体升级”中的核心架构决策。

目的：

- 防止未来在关键方向上反复摇摆
- 为后续 agent 提供明确的设计边界与取舍依据
- 让“为什么这么做”可追溯，而不是只剩结论

建议后续继续使用 ADR（Architecture Decision Record）风格追加。

---

## ADR-001：项目升级目标不是继续堆功能，而是升级为本地自治执行载体

### 状态

- `accepted`

### 背景

当前 `CoPaw` 已具备多渠道、FastAPI、工具、Provider、cron、控制台等基础能力，但核心仍偏“聊天执行系统”。

未来目标不是继续扩充零散功能，而是成为长期运行的本地自治执行载体。

### 决策

项目统一目标定义为：

> 一个统一事实、统一能力、统一环境、统一证据、统一 patch 的本地自治执行内核。

### 后果

- 新增功能需要服从架构升级目标
- 不再以堆页面和堆工具为第一优先级

---

## ADR-002：采用单一真相源，运行真相不得长期散落在多处

### 状态

- `accepted`

### 背景

当前运行事实散落在 `config / jobs / chats / sessions / managers` 中，会导致迁移、审计和长期自治困难。

### 决策

- 未来运行真相统一落在 `state` 层
- `config` 只保留声明式配置
- 不允许旧 manager 长期私有持有核心运行事实

### 后果

- 会触发较大规模的状态模型重构
- 但能显著降低历史遗留和双真相源问题

---

## ADR-003：只保留一个公开主内核：SRK

### 状态

- `accepted`

### 背景

当前存在 runner、cron、channels、routers、多个 manager 共同形成的组合式执行系统，缺乏唯一主链。

### 决策

- 未来只保留一个公开主内核：`SRK`
- 短回合执行器、cron、channels、control-plane 都只能作为 SRK 的边缘入口或内部组件

### 后果

- 所有入口都会逐步改接 SRK
- 旧 runner 主链会退化或删除

---

## ADR-004：统一能力语义为 CapabilityMount

### 状态

- `accepted`

### 背景

当前 `tool / MCP / skill` 是三套并行能力语义，导致授权、风险、规划与证据模型无法统一。

### 决策

统一能力对象：`CapabilityMount`

每个能力至少声明：

- 做什么
- 需要什么环境
- 风险级别
- 对哪些角色开放
- 产生什么证据

### 后果

- 旧 skill/MCP/tool 不一定马上删除
- 但它们不能继续以平行主语义存在

---

## ADR-005：长期任务必须拥有持续环境挂载

### 状态

- `accepted`

### 背景

如果长期任务每轮都重新恢复世界，系统就更像聊天机器人，不像有身体的执行体。

### 决策

引入环境系统，至少包括：

- `EnvironmentMount`
- `SessionMount`
- `ObservationCache`
- `ActionReplay`
- `ArtifactStore`

### 后果

- 浏览器、桌面、工作目录、渠道会话等需要从“临时调用”升级为“持续租约”

---

## ADR-006：风险模型只保留三档

### 状态

- `accepted`

### 背景

过多审批档位会让系统越来越难理解和越来越难维护。

### 决策

统一风险模型仅保留：

- `auto`
- `guarded`
- `confirm`

### 后果

- 风险边界将更清晰
- 业务层不得继续私自扩展审批层级

---

## ADR-007：证据是第一公民，日志不是最终真相

### 状态

- `accepted`

### 背景

日志适合排查，证据适合审计、复盘、学习与回放。

### 决策

引入 `EvidenceRecord` 统一表示动作证据。

观测面聚焦 5 件事：

- 当前目标
- 当前环境
- 当前 owner
- 当前风险
- 当前证据

### 后果

- 重要动作不能只落日志
- 运行中心、日报、周报都应优先建立在证据层之上

---

## ADR-008：学习层只产出 patch，不直接偷偷改运行态

### 状态

- `accepted`

### 背景

如果学习系统直接隐式修改行为，会导致不可审计和不可回滚。

### 决策

学习层只允许：

- 发现瓶颈
- 生成 proposal
- 产出 patch

优先 patch 类型：

- `profile_patch`
- `role_patch`
- `capability_patch`
- `plan_patch`

### 后果

- 学习层变成“优化管道”，而不是“隐式人格漂移器”

---

## ADR-009：采用渐进迁移，但必须一次切主链

### 状态

- `accepted`

### 背景

全仓 Big Bang 重写风险太高，但长期双主链会把项目拖成屎山。

### 决策

采用：

- 开发上分阶段
- 切换上一次完成主链切换

即：

- 可以分期建设新系统
- 但在关键里程碑必须让 SRK 成为唯一主链

### 后果

- 兼容层允许短期存在
- 但必须有明确删除条件和时间窗

---

## ADR-010：兼容代码只能存在于专门区域，且必须登记删除计划

### 状态

- `accepted`

### 背景

历史遗留和屎山最常见的来源，是兼容逻辑散落在核心代码中，且没有删除计划。

### 决策

- 兼容逻辑只能进入：
  - `compatibility/`
  - `adapters/`
  - `legacy/`
- 所有兼容逻辑必须登记到 `DEPRECATION_LEDGER.md`

### 后果

- 删除旧代码将变得可操作
- 核心层更容易保持干净

---

## ADR-011：删除旧代码是正式交付物

### 状态

- `accepted`

### 背景

如果重构只有新增，没有删除，最终只会得到更大的系统复杂度。

### 决策

每个阶段都必须同时定义：

- 新增内容
- 冻结内容
- 退役内容
- 删除内容

### 后果

- 重构会更像真正升级
- 兼容层不会自然永生

---

## ADR-012：Kernel 不得维护独立真相源，运行态必须回写统一 state/evidence

### 状态

- `accepted`

### 背景

如果 kernel 再维护一套独立 SQLite 或独立内存事实，项目会重新出现“state 一套、kernel 一套”的双真相源。

### 决策

- `KernelTaskStore` 不得创建 kernel-only 真相源
- kernel task、runtime、decision、evidence 必须优先回写统一 `state / evidence`
- 风险确认统一落到 `DecisionRequestRecord`

### 后果

- kernel 的持久化实现会更依赖 state/evidence repository
- 但可以避免第二条事实链再次成形

---

## ADR-013：Goal 只能落在 state 层，独立 goal_repository 已退役

### 状态

- `accepted`

### 背景

`Goal` 是规划、任务分解、学习与报告的上层锚点。如果 Goal 单独维护一套仓储和状态枚举，会直接制造双真相源。

### 决策

- `Goal` 仓储统一进入 `src/copaw/state/repositories/`
- 独立的 `src/copaw/state/goal_repository.py` 退役删除
- 后续 Goal service / router 只能接 `state` 层

### 后果

- Goal 与 Task/Runtime/Decision 的语义边界会更一致
- 但后续 Goal 可见化与 API 也必须跟着走统一 state 模型

---

## ADR-014：Capability 执行与风险确认必须统一进入 Kernel / DecisionRequest

### 状态

- `accepted`

### 背景

如果 capability 只是统一读模型，而执行、审批、证据仍散落在各模块里，就无法真正完成能力统一。

### 决策

- capability execute 必须通过 kernel admission / risk gate 进入执行链
- 需要确认的动作统一落到 `DecisionRequest`
- capability 的执行结果必须回写 evidence

### 后果

- `/capabilities` 不再只是展示入口，而会逐步变成统一执行入口
- skill / MCP / tool 的底层实现可以不同，但不能继续维持分裂的治理语义

---

## ADR-015：Learning 对外暴露前必须持久化，Compiler 未接证据闭环前不得包装成 live 能力

### 状态

- `accepted`

### 背景

如果 learning 仍是请求级内存实例，或者 compiler 还没有 evidence/persistence/patch 闭环，却被 API 暴露成“已上线”，会制造严重的能力错觉。

### 决策

- learning 的 proposal / patch / growth 至少要持久化落库后，才允许作为运行中心可见能力暴露
- compiler 在接上 evidence refs、持久化输出与 patch 流程前，不得包装成 live write path

### 后果

- 运行中心展示会更保守，但更真实
- 上层语义能力的上线门槛被明确抬高，减少“看起来有、实际没有”的假落地

---

## ADR-016：记忆增强只能新增 derived index，不得新增第二真相源

### 状态

- `accepted`

### 背景

`CoPaw` 当前已经形成：

- `StrategyMemoryRecord`
- `KnowledgeChunkRecord`
- `EvidenceRecord`
- `ExecutionRoutineRecord / RoutineRunRecord`
- `AssignmentRecord / AgentReportRecord`

这一阶段继续增强记忆能力时，容易受到 file-first / sidecar-first memory 方案影响，重新引入：

- Markdown truth source
- sidecar truth source
- private memory DB truth source

这会直接破坏单一真相源原则。

### 决策

- 未来记忆增强只允许新增可重建的 `derived memory index`
- `Retain / Recall / Reflect` 必须接到现有 `state / evidence / reporting / learning` 主链
- `entity / opinion / confidence` 只能作为 read model、compiled summary 或 reviewable output
- `QMD / LanceDB / vector` 等后端只允许作为可替换 recall backend，不得成为 canonical write target

### 后果

- 可以吸收更强的 recall / reflection 能力
- 但不会重新引入双写、漂移和不可审计的第二真相源
- 旧 `MemoryManager` 会继续收缩为 bridge / helper，而不是 durable memory authority

---

## ADR-017：`n8n` 只能作为固定 SOP Adapter，不得成为 browser/desktop 执行真相或第二工作流内核

### 状态
- `accepted`

### 背景

仓库曾短期落地 `RoutineN8nService` 与 `RoutineService.engine_kind="n8n-sop"` 的桥接实现，用于迁移期承接 webhook trigger、timeout 和 response normalize；该兼容桥已于 `2026-03-21` 删除。

这条桥接是有价值的，但如果继续把 `n8n` 视为 routine engine，本质上会混淆三层边界：

- workflow / schedule 层的固定 SOP 编排
- browser / desktop routine 的叶子执行记忆
- `WorkflowRun / Evidence / AgentReport` 的统一事实回流

同时，社区 `n8n` workflow 很丰富，后续系统确实需要发现、导入、匹配与安装这类模板；如果没有正式对象边界，很容易把外部 workflow JSON 直接放大成第二套 runtime truth。

### 决策

- `n8n` 在 CoPaw 中的正式定位是固定 SOP adapter sidecar
- `n8n` 不负责 browser / desktop UI 执行主链
- `n8n` 不负责 canonical workflow/routine run truth
- 社区/官方 `n8n` workflow 只能先导入为可治理模板，再绑定、体检、触发与回流
- 固定 SOP 的正式运行链必须是 `sop_binding_id -> system:trigger_sop_binding -> SopAdapterService`
- `RoutineService.engine_kind="n8n-sop"` 兼容桥必须退役，且已于 `2026-03-21` 删除
- canonical run / evidence / report truth 继续留在统一主链：
  - `WorkflowRunRecord`
  - `ExecutionRoutineRecord`
  - `RoutineRunRecord`
  - `EvidenceRecord`
  - `AgentReportRecord`
  - `ReportRecord`

### 后果

- 主脑后续可以匹配 `sop template / binding`，而不是每次从零推断重复流程
- 社区 workflow 可以进入系统，但必须先经过治理补注和 doctor 校验
- `n8n -> CoPaw routine -> WorkflowRun / Evidence / AgentReport` 会形成正式可审计闭环
- 旧 `n8n-sop` engine 分支已经删除，routine 层重新收口为 browser/desktop 叶子执行记忆
