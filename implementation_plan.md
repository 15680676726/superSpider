# CoPaw 开发计划（2026-03-12 版）

> `2026-03-17` 同步说明：`V4` 与 `V5` 已完成当前轮收口；post-`V5` 的下一正式阶段已登记为 `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`。`V5` 的范围与落地边界详见 `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`，`V6` 的范围与落地边界详见 `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md` 与 `TASK_STATUS.md`。本文件当前继续作为四个版本的交付基线与后续升级参考。

本文件是 `CoPaw` 在 `Phase A 收尾完成 / Phase B 行业初始化 MVP 完成` 之后，并在 `V1 / V2 / V3 / V4` 完成收口后的正式开发计划/交付基线。

它的职责只有一个：

> 把后续开发拆成 4 个版本，并以 `V1 / V2 / V3 / V4` 的已落地边界作为后续删旧、硬化和升阶增强的基线。

本文件不是概念蓝图，不再承担“把所有想法都先写进来”的职责。

如果与以下文档冲突，优先级依次为：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. 本文件 `implementation_plan.md`

---

## 1. 当前现实基线

截至 `2026-03-11`，已经完成的不是草案，而是当前后续开发必须继承的现实基线：

- `Phase A` 已完成：`A1/A2/A3/A4/A5`
- `Phase B` 已完成：`B1` 到 `B12`
- 统一 `state / evidence / capabilities / environments / kernel / goals / learning` 主骨架已落地
- Runtime Center 已成为统一读面和主要操作面
- 行业初始化 MVP 已落地：
  - `POST /api/industry/v1/preview`
  - `POST /api/industry/v1/bootstrap`
  - `GET /api/industry/v1/instances*`
  - `GET /api/runtime-center/industry*`
  - `/industry` 最小前端入口
- 当前系统已经有固定团队根岗：
  - canonical `execution-core`（唯一物理 agent：`copaw-agent-runner`，产品可见名：`Spider Mesh 执行中枢`）
- 当前代码主链里，`researcher` 仍会被补齐为研究支援位；但正确产品边界应是：它不是按行业默认空跑的巡检器，而是主脑的研究执行位。只有主脑围绕当前目标写出正式研究 brief / monitoring brief 时，它才应启动并把结果汇报回主脑，不是一个单独对外展示的“知识库 builder”
- `2026-03-13` 语义补充：内部 canonical `execution-core` 与物理 runtime `copaw-agent-runner` 当前继续保留；但 `V4` 起产品语义应把它收敛为“团队总控核”，默认负责规划、分派、监督、治理与汇报，而不是长期承担叶子执行
- `2026-03-14` 组团语义补充：产品规划目标仍是按 `solo / lead-plus-support / pod / full-team` 收敛最小合理拓扑；但 `researcher` 即使作为默认可用支援位存在，也不代表它拥有默认启动权。角色可保留，启动必须由主脑派工或显式监控任务触发
- `2026-03-13` 补充：`IndustryInstance` 现持有显式 `IndustryExecutionCoreIdentity` 绑定对象；系统仍只有一个物理 `Spider Mesh 执行中枢`，但会按行业实例挂载不同的行业身份壳，`industry detail / goal detail / query execution` 都从同一对象读取行业使命、思考维度、约束与证据要求，不再靠默认 profile 猜测行业执行框架
- `2026-03-16` 补充：行业创建入口现已显式区分 `system-led / operator-guided` 两种规划模式；`IndustryProfile` 已持久化 `experience_mode / experience_notes / operator_requirements`，可把操作方已有经验、硬要求与缺失环路正式写入草案生成与战略记忆；控制台创建团队默认提交 `auto_dispatch + execute`。当前 live code 仍可在草案缺失时补齐 `researcher` 这个研究支援位，但已不再默认补 researcher 巡检 schedule。
- `2026-04-17` 补充：`researcher` 的正确边界正式改为“主脑派工优先”。主脑必须先形成清楚的研究任务，再让 researcher 执行；最少应明确：
  - 这次为什么要查
  - 服务哪个目标 / assignment / work context
  - 要查什么范围
  - 期望产出是什么
  - 什么时候停止
- `2026-04-17` 补充：researcher 的正式触发原因只保留四类：
  - `goal-gap`：主脑发现当前目标存在信息缺口
  - `task-required`：当前执行任务明确需要外部资料
  - `monitoring`：主脑或用户显式建立了带目标的持续监控任务
  - `user-direct`：用户直接要求发起研究
- `2026-04-17` 补充：不存在“因为属于某个行业，所以 researcher 每天自动跑一次通用巡检”这条产品逻辑。即使是股票、电商、舆情这类高频场景，也应先由主脑写成正式监控任务，再由 schedule 驱动执行，而不是 researcher 自己决定跑什么。
- `2026-04-17` research session 基线补充：formal `ResearchSessionRecord / ResearchSessionRoundRecord`、`SqliteResearchSessionRepository`、`BaiduPageResearchService`、runtime bootstrap 注入、`GET /runtime-center/research` 与 Runtime Center 主脑 cockpit research surface 已落地；这表示研究过程对象、仓储、服务与读面已经形成正式基线
- `2026-04-17` research session 进度补充：主脑 `user-direct` 触发、schedule monitoring brief 触发、runtime bootstrap 注入、`/runtime-center/research` 读面与 cockpit summary 已打通；浏览器 runtime 稳定性问题已修复，research session 默认也会把百度登录态持久化到 `WORKING_DIR/state/research_browser_storage/<owner_agent_id>.json`。当前已在真实登录态下跑通百度问答，`search?word=` 发问、页面答案提取、登录误判修正与内部导航链接过滤都已进入正式链
- `2026-04-17` universal external information collection 补充：研究链已不再只等于 `BaiduPageResearchService` 单线。当前正式主链新增 `source_collection` 编排层，稳定动作模型收口为 `discover / read / interact / capture`，而 `search / web_page / github / artifact` 只作为 phase-1 adapters 落地；但当前 phase-1 light adapters 仍主要是 metadata-backed 的 typed shapers，真实外部多轮采集 owner 仍是 heavy `BaiduPageResearchService`
- `2026-04-17` source collection frontdoor 补充：runtime bootstrap 现已注入 `SourceCollectionFrontdoorService`。主脑 `user-direct`、`main-brain-followup`、cron `monitoring`、以及职业 agent 的 `collect_sources` 工具调用，现在都优先走 `run_source_collection_frontdoor(...)` 统一前门；`researcher` 是 heavy 默认执行位，但不再是唯一入口
- `2026-04-18` research continuity 补充：heavy research frontdoor 现已从“只会新建 session”收口为“跟进问题优先复用同一 matching reusable \`ResearchSession\`”；`BaiduPageResearchService` 也已补上 `resume_session(...)` 与同一 chat page 复用逻辑。当前主停止规则已从“固定轮次”收正为“当前问题是否已经问清”，而 `MAX_BAIDU_ROUNDS / MAX_DEEP_LINKS / MAX_DOWNLOADS` 只保留为安全上限，不再作为主产品语义；其中 `MAX_BAIDU_ROUNDS` 现已明确收口为单次 `run_session(...)` 的安全切片上限，而不是整个 research session 生命周期上限
- `2026-04-17` research truth 补充：`ResearchSessionRecord` 已正式持久化 session-level `brief`，`ResearchSessionRoundRecord` 已正式持久化 round-level `sources`；`findings / gaps / conflicts` 当前仍主要通过 `stable_findings / open_questions / metadata` 聚合投影到 Runtime Center，而不是已经升成独立 top-level persisted fields
- `2026-04-17` writeback 边界补充：当前 heavy `BaiduPageResearchService.summarize_session()` 会继续把研究结果写成 `AgentReportRecord`，并把摘要写入 `work_context / industry` 知识面；`StateKnowledgeService.ingest_research_session(...)` 与 `KnowledgeWritebackService.build_research_session_writeback(...)` 也已具备正式 builder 能力，但 light inline collection 还没有在 live frontdoor 上自动把 report / knowledge / graph writeback 全量应用，也还没有为 light path 统一新写一条 dedicated `EvidenceRecord`
- `2026-04-17` Runtime Center 研究读面补充：`GET /runtime-center/research` 与 cockpit research card 现在正式暴露 `brief / findings / sources / gaps / conflicts / writeback_truth`，不再只显示 provider-only latest summary
- `2026-03-16` 补充：执行中枢在行业聊天中收到“新增任务 / 改规划 / 加长期节奏”后，已不再只是 prompt 里理解；当前会经正式 chat writeback 路径把 operator 指令写回 `IndustryProfile.operator_requirements`、`StrategyMemoryRecord`、新增 goal override 与 recurring schedule，并在同一轮 query prompt 中直接读到回写后的正式状态。新建 goal 也会立刻进入正式 `dispatch_goal` 主链；长期节奏支持工作日 / 季度 / 年度 / 每 N 天(周/月) 等通用 cadence，而不是写死某个行业模板。若指令与团队中现有专业执行位匹配，goal / schedule owner 会直接落到该角色；只有没有合适执行位时才保留在 `execution-core`。
- `2026-03-17` 补充：执行中枢发现岗位空缺时，补位建议现已统一走 `decision-first` 主链。`team_role_gap` recommendation 会先生成正式 `DecisionRequest`，预测页点击“执行”不再直接改团队；operator 可在执行中枢聊天里直接回复“批准补位 / 拒绝补位”复用同一条 kernel 治理链完成批准或驳回。
- `2026-03-16` 补充：`/chat` 已开始从“单长会话壳”升级为“单控制线程 + 多任务线程”的正式形态。行业前台仍只暴露 `Spider Mesh 执行中枢` 作为唯一主入口；当控制线程里出现明确执行型请求时，前门会预先创建正式 `system:dispatch_query` task，并把会话拆到 `task-chat:{task_id}` / `task-session:*`。控制线程本身继续承载指挥、纠偏、追加任务与状态追问，不再把执行噪声长期混在同一聊天线程里。
- 当前系统已改为 draft-first 激活：
  - preview 先生成 AI draft
  - operator 可在 `/industry` 直接编辑团队/目标/计划
  - bootstrap 只激活最终 draft，不再重走固定模板编译
- 当前系统已经能生成行业实例、初始 goal、默认 schedule、evidence-driven daily/weekly snapshot
- `2026-03-12` 补充：`V3` 已真实完成，Capability Market、Runtime Center governance/recovery/automation、Settings/System 产品化入口，以及 `AgentRunner`/runtime-center `bridge` 删尾均已收口；正式验收见 `V3_RELEASE_ACCEPTANCE.md`

这意味着后续开发不能再回退为：

- 再造一套平行行业 JSON/store
- 再造一套平行 industry executor / reporting store
- 再把 chat/cron/localStorage/fallback 拉回真相源
- 再把 `execution-core/researcher` 当成“未来再做”的草案

---

## 2. 当前已完成的版本收口

截至 `2026-03-13`，`V1 / V2 / V3 / V4` 已全部完成，当前不再存在“版本级主链尚未落地”的缺口。

`V4` 的已落地边界如下：

- `V4-A` 已完成：
  - 能力安装体验、`MCP` 模板安装面、`Workflow Template Center`
  - 统一能力池 -> 角色/agent 精确挂载 -> 单 agent 能力预算
  - 行业 `preview recommendation_pack -> bootstrap install_plan -> capability assignment`
  - install-return / workflow resume 单链路
- `V4-B` 已完成：
  - `PredictionCase / Scenario / Signal / Recommendation / Review` 正式对象化并入仓储
  - `PredictionRecommendation -> DecisionRequest -> approved action -> evidence -> review` 治理闭环
  - 旧独立自动优化侧链已在 `2026-03-19` 删除，周期预测与 recommendation 结果面收敛到 `/predictions`
  - `Reports / Performance / Runtime Center / Predictions` 前端结果面

当前专项计划文档仍保留，用于记录边界、验收口径与后续增强顺序：

- `V4_WORKFLOW_CAPABILITY_PLAN.md`

当前版本收口结论：

- 预测对象已正式进入仓储与查询面
- 预测输入已统一接入 `industry / reports / metrics / evidence / workflow run / role judgment`
- 预测建议已接入统一治理闭环
- 预测复盘、命中率、采纳率、执行收益等指标已进入正式 reporting/performance 面
- 主动寻优的节流、冷却、预算与失败降级边界已建立
- 自动化回归已覆盖 workflow / prediction / recommendation / reporting / console build 主链

## 3. 规划原则

后续开发统一遵守以下原则：

### 3.1 四个版本都必须可上线

这里的“上线”不是写完若干模块，而是满足：

- 有明确边界
- 有完整主链
- 有自动化验收
- 有手工验收口径
- 有兼容收口说明
- 有删旧交付物

### 3.2 不再重开 Phase A / Phase B

`Phase A` 与 `Phase B` 的已完成内容只允许：

- 继承
- 增强
- 正式化
- 删除过渡位

不允许：

- 按旧草案重写一遍
- 因为新需求把旧真相源接回去
- 因为做页面再造一个平行对象层

### 3.3 删除旧代码和过渡位是正式交付物

每个版本都必须明确：

- 本版本新增什么
- 本版本允许哪些短期兼容位
- 本版本删掉什么
- 哪些旧路径从本版本起禁止继续扩张

### 3.4 前端只做结果面，不再另造真相源

所有新增页面和工作台都必须直接消费：

- `state`
- `evidence`
- `industry`
- `runtime_center`

不允许再出现：

- 浏览器本地造对象
- 页面内 fallback 成“空数据就是没事”
- 页面 UI 行为看起来可用，实际后端主链断掉

---

## 4. 四个版本总览

| 版本 | 主题 | 核心目标 | 预计周期 | 当前状态 |
|---|---|---|---|---|
| `V1` | 行业团队正式化 | 把“行业初始化 MVP”升级为“正式行业团队系统”，补齐业务专员 Agent 生成与正式对象仓储 | `4-6 周` | `completed (2026-03-11)` |
| `V2` | 长期自治运营化 | 把知识、报告、绩效、节奏、环境宿主做成长期自治闭环 | `5-7 周` | `completed (2026-03-12)` |
| `V3` | 产品化与规模化 | 把能力市场、治理终态、备份恢复、安装交付、兼容退役全部收口 | `6-8 周` | `completed (2026-03-12)` |
| `V4` | 自动化产品化、预测与主动寻优 | 在前三版稳定闭环之上，先补能力模板安装与 workflow 模板中心，再建立可治理、可回溯、可执行的预测与策略寻优系统 | `6-7 周` | `completed (2026-03-13)` |

旧蓝图里的 `Phase C` 到 `Phase F` 不再作为 4 个松散大阶段继续维护，而是合并重排为以上 3 个可上线版本：

- `V1` 吸收旧 `Phase C` 中真正需要优先落地的正式对象化和业务专员生成
- `V2` 吸收旧“知识 / 报告 / 指标 / 多 Agent 协作 / 长期节奏”的主闭环
- `V3` 吸收旧“能力市场 / 治理升级 / 产品化交付 / 最终删尾”
- `V4` 吸收旧“workflow automation 产品化 + 分布式智能预测系统 / Predictions / 独立自动优化侧链”这条高阶自动化与寻优产品线

明确边界：

- `V1/V2/V3` 是已经完成并必须持续守住的硬承诺版本
- `V4` 是建立在前三版稳定完成之后、并已于 `2026-03-13` 完成收口的正式版本
- 不允许为了赶 `V4`，反向污染 `V1/V2/V3` 的对象化、治理和环境宿主收口

---

## 4.1 `implementation_plan1.md` 功能映射

旧 `implementation_plan1.md` 里的功能主题，并没有被整体丢掉，但已经按“当前现实基线 + 可上线边界”重排到新三版本里。

映射关系如下：

| `implementation_plan1.md` 主题 | 新计划落点 | 说明 |
|---|---|---|
| 行业初始化引导 / 行业激活 | `V1-B3` | 升级为正式启动控制面和系统自检入口 |
| `Manager` 固定核心岗 + `Researcher` 默认研究支援岗 | `V1-B2` 基线继承 | `execution-core` 是固定团队总控核；当前运行主链会默认补齐 `researcher`，由它负责研究回流与证据补充 |
| 行业业务岗位自动生成 | `V1-B2` | 这是 `V1` 的核心新增项 |
| 行业对象仓储 / repository / instance 持久化 | `V1-B1` | 从 carrier 迁到正式对象仓储 |
| 报告中心 | `V2-B2` | 从当前 snapshot 升级为正式 report 对象和页面 |
| 知识库 / SOP | `V2-B1` | 纳入正式 knowledge 模块 |
| 经营指标 / KPI / 绩效 | `V2-B2` | 与报告一起进入正式对象和页面 |
| 多 Agent 协作 / Manager 委派 | `V2-B3` | 进入正式委派、任务层级、冲突治理语义 |
| 长期运营节奏 / Calendar | `V2-B3` | 作为 schedule 与运营节奏产品面落地 |
| 环境宿主深化 / replay / 持续会话 | `V2-B4` | 不是独立产品线，归到长期自治硬能力 |
| 能力市场 | `V3-B1` | 作为正式能力集成入口落地 |
| 运营治理面升级 | `V3-B2` | Runtime Center 终态治理中心 |
| 备份恢复 / 启动自检 / 多 provider 降级 / 安装交付 | `V3-B3` | 统一放进产品化交付批次 |
| 兼容退役 / AgentRunner 最终退场 | `V3-B4` | 作为正式删尾交付物 |
| 通知渠道 / 成长可视化 / 健康检查 / 冲突处理 / 负载均衡 / 持续记忆 | `V2-B1/B2/B3` 与 `V3-B2` | 这些不再单独拆散写，而是收敛到知识、报告、协作、治理四类主线 |
| workflow automation 模板中心 / 安装模板体验 / 分布式智能预测系统 / Predictions / 独立自动优化侧链 | `V4` | 作为前三版完成后的正式下一阶段，不前置进入 `V1/V2/V3` |

明确结论：

- 旧文档里的主产品线，除了“workflow automation 产品化 / 分布式智能预测系统”这类 `V4` 项，已经全部收敛进新三版本
- 但不再按旧文档那种“主题堆叠式周计划”维护
- 从现在开始，任何新开发都必须按已完成的 `V1/V2/V3` 基线与 `V4` 的版本边界推进

---

## 4.2 前端同步原则

后续四个版本都不能只写后端目标，前端必须同步落地到对应工作面。

统一要求：

- 每个后端一等对象，都必须有对应前端可见入口
- 每个版本结束时，前端和后端都必须达到同一版本完成态
- 不允许出现“后端已完成，但前端还停在占位页/旧设置页”的假完成

前后端同步矩阵如下：

| 版本 | 后端主交付 | 前端必须同步交付 |
|---|---|---|
| `V1` | 行业对象仓储、业务专员生成、启动控制面 | `Onboarding/Industry` 升级、团队预览、角色详情、首轮计划、启动确认、Runtime Center 行业联动 |
| `V2` | knowledge / reporting / metrics / delegation / environment deepening | `Knowledge`、`Reports`、`Performance`、`Calendar`、`AgentWorkbench` 增强、`Chat/CommandCenter` 的 Manager 协作可见化 |
| `V3` | capability market / governance final / backup-recovery / product delivery | `CapabilityMarket`、`RuntimeCenter` 治理终态、`Settings` 的备份恢复/启动自检/集成配置入口 |
| `V4` | capability market 2.0 / workflow templates / prediction / governed execution loop | `CapabilityMarket` 的模板安装与诊断、`WorkflowTemplates`、`Predictions`、`Reports/Performance` 的预测视图、`RuntimeCenter` 的模板/预测审批与执行联动 |

---

## 5. Version 1：行业团队 1.0

### 5.1 版本目标

把当前“行业初始化 MVP”升级为“正式可运营的行业团队系统”。

用户在 `V1` 结束后，应能得到：

- 一个正式持久化的行业实例
- 一支正式持久化的团队
- 固定系统核心岗 `Manager`，以及按需加入的 `Researcher`/其他支援岗
- 至少一组由行业画像自动生成的业务专员 Agent
- 一条能从初始化直接进入日常运行的主链

### 5.2 本版本必须解决的问题

- 行业对象不能再长期挂在 override carrier 上
- bootstrap 不能再只生成固定双岗
- Manager 必须有可以委派的业务角色
- `/industry` 与 Runtime Center 必须看见真实团队，而不是投影拼装物

### 5.3 批次拆分

### 5.3A 前端同步范围

`V1` 不是纯后端版本，前端至少必须同步完成以下页面收口：

- `Onboarding`
  - API/Provider 基础检查
  - 行业输入
  - 团队方案预览
  - 激活确认
- `Industry`
  - 团队总览
  - 角色卡片
  - 首轮目标 / schedule / 当前状态
- `AgentWorkbench`
  - 能看见系统岗与业务岗的职责、风险、能力边界
- `RuntimeCenter`
  - 行业实例、团队、goal、schedule 可联动跳转

`V1` 前端验收口径：

- 用户完成行业初始化时，不需要去读技术对象名才知道自己启动了什么
- 用户能直接看到“系统将启动哪些 Agent、各自负责什么、接下来会跑什么”
- 行业实例不是只有后端对象存在，前端也能完整看见

#### `V1-B1` 正式行业对象仓储

目标：

- 建立正式 `Industry / TeamBlueprint / RoleBlueprint / IndustryInstance` 读写模型
- 把行业长期读面从 `GoalOverrideRecord.compiler_context` 与 `AgentProfileOverrideRecord` 迁出
- 让 `/api/industry/v1/instances*` 与 `/api/runtime-center/industry*` 读正式对象仓储

主要产出：

- `industry` 正式 repository / query service / projection
- bootstrap 后的行业实例、团队蓝图、角色蓝图持久化
- Runtime Center 和 `/industry` 对正式对象的稳定 detail/read surface

兼容规则：

- 允许极短期双读
- 禁止继续双写扩张
- 本批次结束前必须明确 carrier 删除条件

删除目标：

- 删除行业 detail 对零散 `compiler_context` carrier 的长期依赖
- 删除“industry 主要靠 override 投影可见”的默认假设

验收标准：

- 重启后行业 detail 仍可完整恢复
- 行业实例 detail 不依赖隐式 override 拼装
- 自动化测试覆盖 bootstrap -> persist -> list -> detail -> restart recovery

#### `V1-B2` 行业业务专员生成器

目标：

- 保留 `Manager` 作为固定系统核心岗，并保留 `Researcher` 作为可挂载的研究支援岗
- 基于行业画像与团队复杂度自动生成最小合理的业务专员 Agent
- 让编译链稳定产出业务角色蓝图、goal seed、初始 capability/risk/env 约束
- 让主脑能够给 `Researcher` 下达清楚的研究 brief / monitoring brief，而不是让它空转

主要产出：

- 行业角色生成器
- `IndustryRoleBlueprint` 扩展为：
  - `agent_class = system | business`
  - 业务专员的 role/risk/capability/evidence contract
- 业务角色的 goal seed 编译
- 业务角色的默认 schedule seed 策略
- `Researcher` 的研究 brief / monitoring brief seed 策略

明确要求：

- 不删 `Manager`
- 不删 `Researcher` 这类证据支援角色；当前运行真相仍保留默认补齐，但没有主脑正式 brief 时不应启动
- `Researcher` 不能自发决定长期研究方向；研究目标、监控对象、停止条件必须由主脑或用户明确给出
- 如果存在研究 schedule，它必须绑定到明确的监控 brief，而不是“通用 researcher loop”
- 不把业务专员生成写死成固定行业模板
- 不生成没有 capability/risk/env 边界的空壳 Agent

删除目标：

- 删除 `compiler.py` / `service.py` 中对“只存在 manager/researcher 双岗”的硬编码假设
- 删除测试里默认团队永远只有 2 个角色的假设

验收标准：

- 任一行业初始化后，系统至少能生成 `Manager + Researcher + >=1 business role`；其中 `Researcher` 负责执行主脑派发的研究回流、正式记忆保留与图谱投影的上游输入，而不是默认空跑
- 业务专员在 Runtime Center / Agent Workbench / `/industry` 可见
- Manager 能将任务稳定委派给业务专员

#### `V1-B3` 团队可视化与启动控制面

目标：

- 让行业初始化从“API 可用”升级为“产品可用”
- 用户能在激活前看见将要启动的团队、职责、默认计划和风险边界
- 激活后能直接看到团队运行，而不是只看到 goal/schedule 碎片

主要产出：

- 行业初始化引导增强
- 团队结构预览
- 团队启动确认面
- `/industry` 团队总览、角色详情、首轮计划、首轮 schedule 可见化
- 启动前系统自检：
  - provider 可用性
  - 必要配置
  - 写库/工作目录可用性

删除目标：

- 删除“bootstrap 成功但用户看不见真实团队结构”的灰态体验
- 删除行业入口对隐式默认配置成功的乐观假设

验收标准：

- 新用户可以完成“初始化 -> 审核团队 -> 激活 -> 看见团队运行”
- 启动前缺失关键条件时，系统能明确阻断并提示
- 至少一条 operator manual E2E 路径完成录制与文档化

#### `V1-B4` 发布硬化与删尾

目标：

- 让 `V1` 具备正式上线条件
- 同步文档、测试、删旧、兼容登记

必须完成：

- `TASK_STATUS.md` 同步
- `DEPRECATION_LEDGER.md` 同步
- 对象/API 变更同步到 `DATA_MODEL_DRAFT.md`、`API_TRANSITION_MAP.md`
- 自动化测试矩阵补齐
- `console` build 通过

`V1` 上线门槛：

- 行业实例正式持久化
- 业务专员生成稳定可用
- 初始化后可直接看到真实团队
- 不存在未登记的行业 carrier
- 不存在“前端已可见，后端主链仍断”的假闭环

### 5.4 `V1` 非目标

`V1` 不承诺以下内容：

- 完整知识库产品
- 完整绩效系统
- 完整能力市场
- 跨 host/process 的最强环境恢复
- 最终产品化安装交付

---

## 6. Version 2：长期自治运营 1.0

### 6.1 版本目标

把 `V1` 的正式行业团队，升级为能长期运行的自治运营系统。

当前完成记录：`2026-03-12` 已完成 `V2-B1 ~ V2-B5`，正式验收见 `V2_RELEASE_ACCEPTANCE.md`。

用户在 `V2` 结束后，应能得到：

- 可上传和检索的知识库 / SOP
- evidence-driven 的日报 / 周报 / 月报
- 正式绩效和经营指标
- Manager 对团队的长期节奏与委派闭环
- 更强的环境宿主恢复和 replay 能力

### 6.2 本版本必须解决的问题

- 研究结果和经验不能只停在 evidence/文本里，必须进入正式知识层
- 报告和绩效不能再停留在 snapshot 起点
- 长期任务不能继续主要依赖“每轮 prompt 恢复世界”
- 多 Agent 团队协作必须进入明确调度与冲突治理语义

### 6.3 批次拆分

### 6.3A 前端同步范围

`V2` 前端必须把长期自治结果面补齐，至少包括：

- `Knowledge`
  - 文档上传
  - 分类浏览
  - 适用角色绑定
- `Reports`
  - 日报 / 周报 / 月报
  - 团队与 Agent 双视角
- `Performance`
  - KPI / 成功率 / 负载 / 异常率 / patch 生效情况
- `Calendar`
  - 例行 schedule 与运营节奏
- `Chat`
  - Manager 对话中的委派结果、待办汇总、待确认事项提醒
- `AgentWorkbench`
  - 知识、证据、成长、任务层级、冲突状态可见

`V2` 前端验收口径：

- 用户不打开日志也能看懂团队过去一天/一周做了什么
- 用户不打开数据库也能知道哪个 Agent 表现好、哪个在卡住
- Manager 的委派不是黑箱，用户能在前端看到任务拆分和回传

#### `V2-B1` 知识库与记忆层

目标：

- 建立正式 `knowledge` 模块
- 支持 SOP / reference / history / memory 等知识对象
- 让 `Researcher` 或等价的证据支援角色成为主要知识增量入口
- 让 `Manager` 和业务专员在执行前可检索相关知识

主要产出：

- `KnowledgeChunk` 正式对象
- 文档导入、切分、索引、检索
- 任务执行前的 knowledge retrieve 注入
- Manager 的跨会话摘要记忆与长期事实写入

删除目标：

- 删除“知识只存在于聊天上下文或零散 evidence 里”的长期形态
- 删除人工硬塞 prompt 的临时知识注入

验收标准：

- 上传 SOP 后，相关任务执行能引用该知识
- report / task detail 能回溯知识来源
- Manager 跨会话能恢复用户长期事实

#### `V2-B2` 报告中心与经营指标

目标：

- 建立正式 `reporting` 与 `metrics` 服务
- 把 daily/weekly snapshot 升级为可追溯的正式报告体系
- 把绩效和经营指标做成一等对象和页面

主要产出：

- 日报 / 周报 / 月报
- 团队绩效面板
- Agent 负载、成功率、人工介入率、异常率、patch 生效情况等指标
- Reports / Performance 页面

明确要求：

- 指标必须来自 `EvidenceLedger + Task/Goal/Runtime`
- 报告必须 evidence-driven
- 不允许重新引入静态文案式假报告

删除目标：

- 删除静态兜底报告
- 删除接口失败时吞成“今天没数据”的伪可见性

验收标准：

- 任一报告都能追溯其 evidence/task 来源
- 任一指标都能追溯其计算口径
- 页面失败时明确报错，不伪装成空白正常态

#### `V2-B3` 长期节奏与多 Agent 协作

目标：

- 让 Manager 真正承担团队调度职责
- 建立 daily/weekly/monthly 运营节奏
- 建立委派、回传、冲突、负载均衡的正式语义

主要产出：

- 委派协议
- parent/child task 或等价层级模型
- 例行 schedule 模板
- 资源冲突/占用锁
- 基础负载均衡与失败接管规则

删除目标：

- 删除“Manager 实际只能自己干活”的隐性单 Agent 模式
- 删除多 Agent 并发操作同一资源时无治理的灰态

验收标准：

- Manager 能把高层目标拆给多个业务专员
- 子任务结果能稳定回流并汇总
- 冲突和过载有明确观测和处理路径

#### `V2-B4` 环境宿主深化

目标：

- 继续做深 `EnvironmentMount / SessionMount / ObservationCache / ActionReplay / ArtifactStore`
- 提升 live handle 的恢复能力
- 提升 replay 的原位恢复/原位回放能力

主要产出：

- 更正式的 session restorer 机制
- 跨 host/process 的恢复策略
- 更强 replay executor 语义
- 长期任务的环境持有和恢复测试

删除目标：

- 删除对 same-host 临时恢复假设的默认依赖
- 删除“replay 只是再走一遍 kernel 提交”的弱语义前提

验收标准：

- 启动恢复、异常恢复、手动 replay 都有稳定边界
- 至少一条跨进程恢复链路通过自动化和手工验收

#### `V2-B5` 发布硬化与真实世界验收

目标：

- 让 `V2` 具备“长期自治运营版”上线条件

必须完成：

- live provider smoke 扩面
- operator manual E2E 扩面
- restart recovery / approval / rollback 验收扩面
- 文档与删旧台账同步

`V2` 上线门槛：

- 一套行业团队可持续运行
- 知识、报告、绩效都进入正式对象和页面
- Manager 委派闭环稳定
- 环境恢复能力明显强于当前 MVP
- 不存在新的平行 reporting/knowledge/runtime 真相源

当前完成备注：

- `2026-03-12` 已达到上述上线门槛
- 旧 `runner / config / old routers / legacy bridge alias` 的核心删尾不属于 `V2`；该事项已在 `2026-03-12` 由 `V3-B4` 完成收口，剩余仅限显式 redirect/compat surface

### 6.4 `V2` 非目标

`V2` 不承诺以下内容：

- 能力市场最终态
- 最终安装包和商业化交付
- 全部兼容壳彻底删除
- 多租户云版

---

## 7. Version 3：产品化与规模化 1.0

### 7.1 版本目标

把 `V2` 的长期自治系统，升级为可交付、可治理、可恢复、可扩展的正式产品。

当前完成记录：`2026-03-12` 已完成 `V3-B1 ~ V3-B4`，正式验收见 `V3_RELEASE_ACCEPTANCE.md`。

用户在 `V3` 结束后，应能得到：

- 可安装、可配置、可卸载的能力市场
- 最终收紧的治理中心
- 完整备份恢复、启动自检、多 provider 降级
- 更清晰的产品安装交付路径
- 已登记兼容位的大规模退役

### 7.2 本版本必须解决的问题

- 真实业务集成不能继续靠手改配置和散乱 skill/MCP 入口
- 高风险治理不能只停留在当前基础审批面
- 本地部署产品必须具备恢复、备份、自检、交付能力
- 兼容壳不能无限挂着不删

### 7.3 批次拆分

### 7.3A 前端同步范围

`V3` 前端必须把产品化和治理面补齐，至少包括：

- `CapabilityMarket`
  - 推荐
  - 安装
  - 配置
  - 卸载
- `RuntimeCenter`
  - 批量审批
  - patch rollout / rollback
  - 审计与治理视图
  - emergency stop / resume
- `Settings`
  - 备份与恢复
  - 启动自检结果
  - provider fallback / 集成配置
- `CommandCenter` 或等价首页
  - 启动异常、关键决策、系统健康、恢复入口

`V3` 前端验收口径：

- 真实用户可以不用开发工具完成能力安装、恢复、审批和治理操作
- 启动异常和恢复路径不能只存在于日志或控制台
- 前端不再只是结果展示，也能成为正式产品操作面，但仍不得自造真相源

#### `V3-B1` 能力市场

完成状态：`completed (2026-03-12)`
- `/capability-market` 已成为正式能力集成入口
- 旧 `/capabilities`、`/skills`、`/mcp` 的独立前端入口已降级为 redirect/compat surface，不再承担正式产品入口
- Capability Market 前后端当前读写已统一切到 `/capability-market/*` canonical surface（含 `capabilities / capabilities/summary / skills / mcp / hub/install / capability toggle/delete`）
- `/api/skills` 与 `/api/mcp` 仍作为 legacy/compat 管理 API 保留；删除条件是 legacy 客户端迁移完成、skill file/load 等剩余兼容能力找到归宿并补齐回归
- `/api/capabilities` 保留为统一 capability service / execute contract，不再承担 Capability Market 的产品写面

目标：

- 建立正式 `capability_market`
- 支持能力发现、推荐、安装、卸载、配置
- 让行业初始化和学习层都能推荐能力，而不是假设固定工具集

主要产出：

- 能力包元数据模型
- 能力注册表
- installer / uninstaller
- 基于行业画像和失败记录的 capability recommender
- Capability Market 页面

明确要求：

- 安装/卸载/配置必须进入统一 kernel 治理链
- 能力市场不能变成新的平行配置真相源

删除目标：

- 删除靠旧 `/skills`、`/mcp` admin 语义硬拼产品能力集成的长期模式
- 删除隐式手改配置作为主要集成方式

验收标准：

- 用户可安装、配置、卸载能力包
- 安装后的能力立即进入统一 capability graph
- learning/service 可对能力缺口给出推荐

#### `V3-B2` 治理中心终态

完成状态：`completed (2026-03-12)`
- Runtime Center 已具备 `overview / governance / recovery / automation` 四个正式工作面
- 批量审批、patch rollback、emergency stop / resume 已进入统一治理面
- `Settings -> /settings/system` 已承接启动恢复、自检与 canonical runtime route 暴露

目标：

- 让 Runtime Center 成为正式治理中心，而不是“有些操作能做、有些还在旁路”的半成品
- 把剩余 config/admin 写面和高风险动作全部收口到统一治理面

主要产出：

- 更正式的角色授权模型
- 环境约束与能力策略终态
- 批量审批 / 审计 / patch rollout / emergency stop / resume
- Settings 与 Runtime Center 的职责边界终态

删除目标：

- 删除剩余 legacy write path
- 删除剩余 `bridge` alias/header 的默认依赖
- 删除未登记的旁路治理入口

验收标准：

- 所有高风险写操作都能追溯到 decision/evidence
- 批量审批、patch rollback、紧急停止都通过手工和自动化验收

#### `V3-B3` 备份恢复与产品交付

完成状态：`completed (2026-03-12)`
- startup recovery、system self-check、provider fallback 与产品化系统入口均已落地
- `/api/runtime-center/recovery/latest` 与 `/settings/system` 已成为正式恢复/自检可见面
- `ProviderManager` 已修复 provider fallback 的共享状态污染问题

目标：

- 把系统做成可交付产品，而不是只能开发态运行

主要产出：

- 备份/恢复
- 行业归档/重置
- 启动自检
- 多 provider fallback
- 本地安装交付路径

可选交付：

- 安装包
- 加固/编译方案
- license 方案评估

删除目标：

- 删除“出问题只能手工救火”的产品形态
- 删除“启动失败但用户只看到空白页面”的体验

验收标准：

- 新安装环境可完成 bootstrap
- 既有环境可完成备份、恢复、重启
- 关键失败场景有明确自检和降级路径

#### `V3-B4` 最终删尾与规模化收口

完成状态：`completed (2026-03-12)`
- `src/copaw/app/runner/runner.py` 已真实删除
- `src/copaw/app/runtime_center/bridge.py` 已真实删除
- `RuntimeOverviewResponse.bridge`、`X-CoPaw-Bridge-*`、前端 `data?.bridge` 与 runtime-center bridge fallback 已全部移除
- `_app.py` 已直接装配 `RuntimeHost + KernelQueryExecutionService + KernelTurnExecutor`

目标：

- 把本轮架构升级中剩余的兼容壳、误导命名、旧宿主壳收掉
- 为后续更高阶功能留下干净基线

必须处理：

- `AgentRunner` 最终退役条件兑现
- remaining compatibility/legacy/bridge 命名收口
- carrier/override 过渡位最终清理
- 真实世界验收矩阵扩到版本收口标准

删除目标：

- 删除“虽然主链已经换了，但名字和入口还像旧系统”的长期误导
- 删除未登记兼容代码

`V3` 上线门槛：

- 当前状态：`achieved (2026-03-12)`

- 能力市场正式可用
- 治理面达到最终收口标准
- 备份恢复和产品交付链条稳定
- 主要兼容壳已退役
- `TASK_STATUS.md`、`DEPRECATION_LEDGER.md`、`DATA_MODEL_DRAFT.md`、`API_TRANSITION_MAP.md` 完整同步

### 7.4 `V3` 非目标

`V3` 之后才考虑，不进入本轮承诺：

- 分布式智能预测系统
- 多租户云平台
- 广义行业仿真平台
- 公共生态市场和外部商业平台化

---

## 8. Version 4：自动化产品化、预测与主动寻优 1.0

### 8.1 版本定位

`2026-03-13` 落地结论：

- `V4-A` 已完成：能力安装体验、MCP 模板安装面、Workflow Template Center、角色/agent 精确挂载、业务 agent 能力预算、行业 preview/bootstrap 推荐安装与 install-return 回流都已落地
- `V4-B` 已完成：正式 prediction objects、governed recommendation、review/metrics、Predictions/Reports/Performance/Runtime Center 结果面都已落地；旧独立自动优化 config/run/daemon 已在 `2026-03-19` 删除
- `V4` 当前不再是“待开工版本”，本节以下内容保留为边界/验收说明书

`V4` 不是一个“再加一个页面”的版本，而是：

> 在 `V1/V2/V3` 已经把行业团队、知识、报告、指标、治理、恢复、交付做稳之后，把系统升级为“能提出受治理约束的前瞻性判断与优化建议”的版本。

`V4` 的目标不是做一个好看的预测面板，而是形成：

- 可回溯的数据来源
- 可解释的预测场景
- 可审计的建议生成
- 可治理的执行落地
- 可回看、可纠偏的预测结果复盘

`2026-03-13` 范围补充：

`V4` 不能只从 prediction 开始做。基于当前真实代码基线，`V4` 必须先完成：

- `Capability Market 2.0`
- `MCP` 模板安装前端产品面
- `Workflow Template Center`
- `role / agent scoped capability assignment`
- `单个业务 agent 非系统基线能力默认上限 12`
- `industry preview/bootstrap` 的推荐安装包与组团即安装能力
- `execution-core` 的团队总控化与叶子执行下放

然后再叠加：

- `Predictions`
- `governed recommendation`
- `review`

专项排期与对象/API 建议见：

- `V4_WORKFLOW_CAPABILITY_PLAN.md`

### 8.2 开工前置条件

`V4` 只能在以下条件全部满足后开工：

- `V1` 完成：
  - 行业实例、团队蓝图、角色蓝图、业务专员 Agent 已正式对象化
- `V2` 完成：
  - knowledge / reports / metrics / delegation / long-running environment 已稳定
- `V3` 完成：
  - capability market、治理终态、备份恢复、自检、provider fallback 已稳定
- 当前真实世界验收矩阵已覆盖：
  - operator manual E2E
  - live provider smoke
  - restart recovery
  - approval / rollback

如果这些条件不满足，`V4` 一律不得提前穿透施工。

### 8.3 本版本必须解决的问题

- 系统不仅要能“执行”，还要能基于历史事实与外部情报做前瞻性判断
- 预测结果不能是不可解释的黑箱文字，必须能说明来源、假设、风险和建议动作
- 预测不能绕过治理直接改运行事实
- 主动寻优不能演变成无边界自动执行，必须受 `auto / guarded / confirm` 模型约束
- 顶层 `execution-core` 不能继续兼任万能执行员，必须逐步收敛为团队总控角色，并把大部分外部执行能力下放给专业 agent

### 8.4 批次拆分

### 8.4A 前端同步范围

`V4` 前端至少必须新增或增强以下页面与视图：

- `Predictions`
  - 预测议题列表
  - 单次预测详情
  - 场景对比
  - 预测信号来源
  - 建议动作
- `Predictions`
  - 主脑周期预测列表
  - recommendation 队列与治理状态
  - capability gap / optimization stage / telemetry
  - 人工审批入口
- `Reports`
  - 历史预测 vs 实际结果复盘
- `Performance`
  - 预测命中率、建议采用率、建议执行收益
- `RuntimeCenter`
  - 预测相关的 decision / evidence / action 联动

`V4` 前端验收口径：

- 用户能看见每次预测依据了哪些历史事实、哪些外部信号、哪些角色判断
- 用户能区分“系统建议”“已批准动作”“已执行动作”“执行后结果”
- 用户能回看预测是否命中，而不是只看到一次性漂亮摘要

#### `V4-B1` 预测对象与数据管线

目标：

- 建立正式 `prediction` 模块
- 把预测从随意 prompt 输出，收敛为正式对象和正式数据管线

主要产出：

- `PredictionCase`
- `PredictionScenario`
- `PredictionSignal`
- `PredictionRecommendation`
- `PredictionReview`

推荐数据来源分层：

- 内部历史层：
  - `EvidenceRecord`
  - `Task / Goal / Runtime`
  - `Report`
  - `Metric`
- 岗位专家层：
  - `Manager`
  - `Researcher` 或其他证据支援角色
  - 业务专员 Agent 的结构化判断
- 外部情报层：
  - `Researcher` 或等价证据角色收集的市场、竞品、政策、渠道信号

明确要求：

- 预测对象必须入正式仓储
- 每个预测都必须保存输入范围、时间窗、信号来源、生成时间、owner
- 不允许把预测长期只存在于聊天回复或 markdown 报告里

验收标准：

- 任一预测都能追溯到数据来源和角色贡献
- 任一预测都能按行业实例、目标、时间窗查询

#### `V4-B2` 场景预测引擎

目标：

- 支持用户提问式预测和系统主动触发式预测
- 支持多场景对比，而不是单点拍脑袋结论

主要产出：

- 预测议题输入 contract
- `best/base/worst` 或等价多场景输出
- 影响维度：
  - 目标达成率
  - 任务负载
  - 风险变化
  - 资源占用
  - 外部副作用
- 预测置信度与不确定性说明

建议问题类型：

- “如果把资源转向 X，会怎样”
- “如果新增一个业务专员，会怎样”
- “如果关闭某能力或某渠道，会怎样”
- “如果采用某外部策略，会怎样”

删除目标：

- 删除“只有一段自然语言总结，没有场景比较和边界条件”的伪预测

验收标准：

- 同一预测议题至少能输出可比较的多场景结果
- 输出中显式包含假设、风险、置信度、建议动作

#### `V4-B3` 主动寻优与建议生成

目标：

- 让系统能基于持续运行事实主动发现优化点
- 但只生成受治理约束的建议，不直接越权执行

主要产出：

- 主动触发器：
  - 指标异常
  - 成功率下滑
  - 冲突频发
  - 资源过载
  - 外部风险变化
- 建议类型：
  - `plan_recommendation`
  - `role_recommendation`
  - `capability_recommendation`
  - `schedule_recommendation`
  - `risk_recommendation`
- 节流与成本控制：
  - 触发频率
  - 最小信号阈值
  - 冷却时间
  - provider 成本预算

明确要求：

- 主动寻优必须有节流机制
- 不允许无限制高频调用模型做“看起来很聪明”的空分析

验收标准：

- 系统能在异常和机会信号出现时给出结构化建议
- 建议队列可排序、可过滤、可追溯来源

#### `V4-B4` 预测到执行的治理闭环

目标：

- 把预测建议接到统一治理链，而不是另造自动化旁路

主要产出：

- `PredictionRecommendation -> DecisionRequest -> approved action -> evidence -> outcome review` 闭环
- 与 `Goal / Patch / Capability / Schedule` 的受治理联动
- 低风险建议可自动落地的边界定义
- 中高风险建议的审批与回滚策略

明确要求：

- 所有建议动作仍经 kernel
- 所有自动执行仍需符合 `auto / guarded / confirm`
- 不允许预测模块直接改 runtime state

验收标准：

- 从预测建议到实际执行有完整 evidence 和 decision 链
- 预测动作失败或效果差时，能回滚并进入复盘

#### `V4-B5` 预测复盘与命中率学习

目标：

- 让系统不只是“会预测”，还要“知道自己预测得准不准”

主要产出：

- `PredictionReview`
- 预测结果与实际结果比对
- 命中率、偏差率、建议采纳率、执行收益等指标
- 对预测策略的学习反馈

明确要求：

- 预测系统必须有自我纠偏机制
- 不允许预测只产出、不复盘

验收标准：

- 任一历史预测可回看真实结果
- 系统能给出预测质量趋势
- 预测失败会形成后续策略修正输入

### 8.5 `V4` 上线门槛

`V4` 只有在以下条件同时满足时才算完成：

- 预测对象正式持久化
- 预测场景、建议、审批、执行、复盘形成闭环
- 前端 `Predictions / Reports / Performance / RuntimeCenter` 全部能看见关键结果
- 预测不会绕过统一治理面
- 预测有节流、预算和失败降级策略
- 命中率与复盘指标可观测

`2026-03-13` 验收结果：

- 上述上线门槛已满足
- 专项回归：`python -m pytest tests/app/test_workflow_templates_api.py tests/app/test_capability_market_api.py tests/app/test_industry_api.py tests/app/test_capabilities_write_api.py tests/app/test_predictions_api.py tests/state/test_reporting_service.py -q` -> `53 passed`
- 全量回归：`python -m pytest -q` -> `390 passed, 1 skipped`
- 前端构建：`cmd.exe /c npm --prefix console run build` 通过

### 8.6 `V4` 非目标

`V4` 仍然不承诺以下内容：

- 全行业仿真沙盘
- 多租户分布式预测平台
- 宏观社会级模拟系统
- 独立于 `CoPaw` 主系统之外的外部预测产品线

### 8.7 post-`V4` 下一正式阶段：`V5`

`V4` 完成后，后续工作不应再以“零散硬化备注”的方式推进，而应明确收口为新的正式阶段：

- `V5` 名称：`执行表面升级`
- 专项文档：`V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`

`V5` 的目标不是重做 `V4`，而是在当前真实基线上继续补齐 5 条主线：

- 浏览器从 tool 升级为产品面
- 治理从 risk-level 升级为 execution-strategy surface
- `skills / integrations / MCP` 的安装配置升级为 manifest/schema/lifecycle contract
- workflow 升级为更强的 runtime shell
- operator diagnose / example run / error drilldown 收口为统一产品面

`V5` 的产品口径补充：

- 顶层 workflow 应是一个 `WorkflowRun` 跨多个 step 和多个 agent 的运行壳
- 不是默认“一人一条 workflow”
- `execution-core` 默认负责规划、分派、监督、汇报，而不是长期承担叶子执行

换句话说：

- `implementation_plan.md` 继续维护 `V1 / V2 / V3 / V4` 的完成边界
- `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md` 负责登记 post-`V4` 的下一正式升级阶段
- `TASK_STATUS.md` 负责记录 `V5` 当前做到哪里、先做哪一批

### 8.8 post-`V5` 下一正式阶段：`V6`

`V5` 完成后，后续工作不应退回“零散补几个 browser action / 直接接一个外部 workflow 引擎”的松散推进，而应明确收口为新的正式阶段：

- `V6` 名称：`routine / muscle memory 升级`
- 专项文档：`V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`

`V6` 的目标不是重做 workflow，而是在当前真实基线上继续补齐 6 条主线：

- 浏览器 routine 对象化
- routine 回放与失败回退
- Runtime Center routine 诊断
- 资源锁细化
- `n8n` 作为固定 SOP 编排层
- 桌面级 muscle memory 后置落地

`V6` 的产品口径补充：

- 顶层 workflow 继续是一个 `WorkflowRun` 跨多个 step 和多个 agent 的运行壳
- routine 是 agent-local、environment-bound 的叶子执行记忆，不是平行 workflow DSL
- 总控负责判断哪些工作流固定、哪些保留为灵活判断
- `n8n` 只能承接固定 SOP、schedule、webhook、API 串联，不是 workflow/routine 的真相源，也不是浏览器执行肌肉层
- 桌面级 muscle memory 必须建立在浏览器 routine、回放、诊断与资源锁稳定之后

换句话说：

- `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md` 继续维护 `V5` 的边界与验收
- `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md` 负责登记 post-`V5` 的下一正式升级阶段
- `TASK_STATUS.md` 负责记录 `V6` 当前批次、当前并行硬化项与推荐施工顺序

---

## 9. 每个版本都必须遵守的上线检查

每个版本发布前必须同时满足以下 6 类检查：

### 8.1 对象检查

- 新增对象是否有正式仓储/查询面
- 是否还依赖未声明的 carrier
- 是否还在借旧 override 承载长期真相

### 8.2 主链检查

- 所有写操作是否进入 kernel
- 所有重要读面是否来自统一 query service
- 是否新增了平行执行链

### 8.3 证据检查

- 关键外部动作是否留证据
- 报告和指标是否可追溯
- approval / rollback / replay 是否可审计

### 8.4 兼容检查

- 新增了哪些兼容位
- 每个兼容位的删除条件是什么
- 本版本删掉了哪些旧逻辑

### 8.5 自动化检查

- 单元测试
- 集成测试
- operator E2E
- provider smoke
- `console` build

### 8.6 文档检查

- `TASK_STATUS.md`
- `DEPRECATION_LEDGER.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

只要其中任一项缺失，该版本就不能视为“已完成可上线”。

---

## 10. 文档同步方式

本文件只负责四个版本和批次边界。

从本文件开始，后续执行按下面方式同步：

- `implementation_plan.md`
  - 维护 `V1/V2/V3/V4` 的版本边界、批次、版本上线标准
- `TASK_STATUS.md`
  - 维护当前做到哪里、当前正在做什么、下一步是什么
- `DEPRECATION_LEDGER.md`
  - 维护兼容位、删除条件、owner、删除阶段
- 版本执行文档
  - `V1` 开工时创建 `PHASEC_EXECUTION_PLAN.md`
  - `V2` 开工时创建 `PHASED_EXECUTION_PLAN.md`
- `V3` 开工时创建 `PHASEE_EXECUTION_PLAN.md`
- `V4` 开工时创建 `PHASEF_EXECUTION_PLAN.md`
- post-`V4` 的正式升级文档
  - `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`
  - `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`

说明：

- `V4` 已完成，不再作为“下一阶段”描述
- post-`V4` 的下一正式阶段已登记为 `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`
- post-`V5` 的下一正式阶段已登记为 `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
- 如果未来确实出现超出 `V6` 的新产品线，再另开新文档，不在本文件提前堆想法

---

## 11. 明确退场的旧写法

从本版开始，以下写法不再作为正式计划内容继续维护：

- “先把所有能想到的页面和模块都列出来”
- “用 Week 7-20 的方式并排堆很多主题，但不区分上线边界”
- “把远期研究项和当前版本承诺写在同一层”
- “只写新增，不写删旧”
- “只写想做什么，不写当前代码基线是什么”

---

## 12. 一句话总结

后续四个版本的顺序已经明确：

1. `V1` 先把行业团队做实，补齐业务专员 Agent 和正式对象仓储。
2. `V2` 再把长期自治做实，补齐知识、报告、绩效、协作和环境宿主。
3. `V3` 最后把产品化做实，补齐能力市场、治理终态、备份恢复、交付和删尾。
4. `V4` 再把自动化产品化、预测与主动寻优做实，补齐能力模板安装、workflow 模板中心、预测对象、场景对比、建议治理和复盘学习。

这四版做完，`CoPaw` 才算从“已有主骨架的行业 MVP”真正升级到“可长期运行、可治理、可交付、可前瞻优化的自治载体产品”。




---

## Appendix A. 2026-03-18 同步：post-`V6` 的 `V7` 主脑长期自治方向

post-`V6` 的下一正式规划已登记为 `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`。

`V7` 的主题不是再造平行行业系统，而是把现有：

`industry instance -> goals/schedules -> tasks -> evidence -> reconcile`

升级为：

`main brain carrier -> strategy -> operating lanes -> cycle plan -> assignments -> career agent execution -> reports/evidence -> brain reconcile -> next cycle`

这轮的关键边界是：

- 长期身份、长期目标、战略优先级只属于主脑。
- 职业 agent 只持有职责、能力、routine、当前任务，不再各自持有平行长期战略。
- `Goal` 降级为周期内可关闭对象，不再承担长期使命。
- Runtime Center、`/industry`、`Chat`、`AgentWorkbench` 必须同步升级到同一条主脑自治读面。

详细对象表、后端改造表、前端同步表、测试要求与规模评估见：

- `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
