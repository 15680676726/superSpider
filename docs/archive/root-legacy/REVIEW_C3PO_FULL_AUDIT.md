# COPAW 项目全局审计文档（修订稿）

## 1. 审计目的

本文档的目的不是评价项目“有没有功能”，而是系统性回答以下问题：

- 这个项目想做什么
- 这个项目现在实际上做成了什么
- 它的主脑 / 执行位 / 委派协作设计意图是什么
- 当前实现与该设计意图之间的真实差距在哪里
- 哪些闭环已经落地，哪些仍然没有形成强闭环
- 哪些核心模块、文件、函数最值得怀疑
- 后续应该如何整改，并以什么标准要求 Codex 执行

---

## 2. 相对初稿的关键校正

本修订稿相对初稿，先做 4 个事实校正：

1. 不再把 `V7` 主脑对象与周期对象写成“尚不存在”。
   当前仓库已经正式落地 `OperatingLaneRecord / BacklogItemRecord / OperatingCycleRecord / AssignmentRecord / AgentReportRecord`，并已接入行业运行主链。

2. 不再把 `_main_brain_boundary.py` 写成主分流核心。
   该文件当前主要负责“旧的人类直连执行入口退役提示”，真正的 `auto/chat/orchestrate` 分流在 `src/copaw/kernel/turn_executor.py` 与 `src/copaw/app/routers/runtime_center_routes_core.py`。

3. 不再把“主脑聊天拆链”写成完全没有落地。
   当前已经存在 `MainBrainChatService` 纯聊天链，以及 `POST /api/runtime-center/chat/run` 的 `interaction_mode=auto` 裁决链；但它仍是“骨架已落地、边界仍未彻底收干净”，不是“问题已解决”。

4. 不再把“子 agent 汇报闭环”写成完全没有。
   当前已经存在 `AgentReportRecord`、`AssignmentRecord`、`run_operating_cycle()`、`_process_pending_agent_reports()` 以及“执行位回流到主脑控制线程”的正式链路；但报告协议仍偏薄，综合与 replan 仍弱。

---

## 3. 项目目标：它想成为什么

结合根目录规划文档、当前 `state / kernel / industry` 代码和测试来看，COPAW 的目标不是单个聊天 agent，而是：

> 一个以单主脑为控制中心、以行业团队为组织模型、以多执行位为工作单元、以 capability / MCP / skill / browser / desktop 为能力层、以 runtime / checkpoint / mailbox / evidence / report / cycle 为治理骨架的本地自治执行平台。

换句话说，它试图实现的是：

- 一个统一的主脑 / 执行内核
- 一个行业团队与岗位体系
- 一个可治理的能力市场
- 一个可挂载浏览器、桌面、文件、MCP、skill 的执行层
- 一个多任务、多 actor、多会话的运行时
- 一个围绕目标、周期、派工、汇报、证据、治理、学习的长期主链

这仍然是平台级目标，而不是“更会聊天的 AI”。

---

## 4. 项目现状：它实际上更像什么

### 4.1 它已经是一个较强的多 agent operating platform

当前仓库已经稳定具备以下平台特征：

- 角色体系与 execution-core 单脑收口
- capability 治理与 capability market
- MCP / skill / tool 接入与发现
- industry preview / bootstrap / update / retire
- runtime center / agent workbench / reports / evidence
- actor mailbox / checkpoint / lease / work context
- task / runtime / decision / patch / growth 主链

### 4.2 它已经落地了一部分“主脑自治骨架”

当前不是“完全没有主脑对象”，而是已经有一条正式骨架：

- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`
- `IndustryService.run_operating_cycle()`
- `AssignmentService.reconcile_assignments()`
- `AgentReportService.record_task_terminal_report()`

这说明系统已经不只是“goal/task/evidence 平台”，而是开始进入“主脑周期规划 + 派工 + 汇报回流”阶段。

### 4.3 但它仍然不是一个同等成熟的“强综合主脑系统”

当前最核心的问题不是“没有主脑”，而是：

- 主脑控制壳已经建立
- 主脑聊天前台已经拆出
- 周期 / 派工 / 汇报对象已经建立
- 但 turn 级 planning / synthesis / replan 仍然弱于运行时、治理和委派

因此用户感受到的“不够聪明”，主要不是因为系统没有角色、没有 runtime、没有 delegation，而是因为：

- 主脑综合责任已被对象化，但没有被同等强度工程化
- 汇报有对象，但报告质量不够支撑强综合
- 周期有对象，但冲突处理与再规划还不够显式
- 平台复杂度仍然强于认知闭环表达

---

## 5. 当前主链：项目现在是怎么运作的（校正版）

### 5.1 入口与主脑前门

当前正式聊天入口是：

- `POST /api/runtime-center/chat/run`

它进入：

- `src/copaw/app/routers/runtime_center_routes_core.py`
- `src/copaw/kernel/turn_executor.py`

当前 `chat/orchestrate` 显式前台入口已经退役，旧的人类直连执行入口也已退役为 `410`。

### 5.2 主脑聊天前台

`src/copaw/kernel/main_brain_chat_service.py` 当前负责：

- 轻量主脑聊天 prompt
- 注入 roster / 运行摘要 / 战略摘要 / 受控记忆
- 输出前台聊天回复
- 在控制线程场景下异步做 background intake
- 根据结构化模型决议决定是否 writeback / kickoff

因此它确实是“轻聊天主脑前台”，不是完整 orchestration 内核。

### 5.3 重执行内核

`src/copaw/kernel/query_execution.py` 与 `src/copaw/kernel/query_execution_runtime.py` 当前负责：

- resident agent
- capability surface
- tool / skill / MCP / system mounts
- mailbox / checkpoint / lease / evidence
- prompt appendix
- 真实流式执行

这仍是全仓最强的执行容器。

### 5.4 委派与运行治理

`src/copaw/kernel/query_execution_tools.py`、`src/copaw/kernel/delegation_service.py`、`src/copaw/kernel/actor_mailbox.py` 当前负责：

- `dispatch_query`
- `delegate_task`
- child task / mailbox / checkpoint
- delegation governance
- actor runtime projection

这条链已经非常工程化。

### 5.5 行业自治与主脑周期链

当前真正承接“主脑周期 / 派工 / 汇报”的不是单一 prompt，而是：

- `src/copaw/state/main_brain_service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/industry/service_strategy.py`

这条链已经支持：

- 从 backlog 物化 cycle
- 从 cycle 物化 assignment
- 从 task 终态生成 agent report
- 将 agent report 写回 control thread
- 根据 goal / task / report 重新 reconcile assignment 和 cycle

所以“主脑周期对象完全不存在”这一结论已经不准确。

### 5.6 证据型发现：当前最值得保留的源码线索

以下发现适合作为后续整改、评审和验收时反复引用的“证据型线索”：

1. `query_execution_runtime.py` 的核心循环，本质上是“把一个大而重的 resident agent 跑起来”。
   它最强的对象是 capability context、lease、prompt appendix、system tools、resident agent、streaming 和 checkpoint；而不是显式的 `plan / subtasks / reports / synthesis / replan` 主循环。

2. `main_brain_chat_service.py` 当前确实更像“轻前台”。
   它负责 snapshot、memory、prompt messages、聊天回复与 session persist，然后通过 background intake 异步决定是否 writeback / kickoff。因此它更像 conversation frontdoor + intake trigger，而不是主脑 orchestration loop 本身。

3. `query_execution_tools.py` 对“怎么派出去”已经做了强工程化。
   `dispatch_query / delegate_task` 的 target、权限、payload、治理和返回格式都很清楚；但同层没有同等级的 `collect_reports / compare_results / resolve_conflicts / replan_from_reports` 工具。

4. `delegation_service.py` 更像任务与状态基础设施，而不是认知协作基础设施。
   它非常关注 mailbox、checkpoint、phase、summary、error、experience 和记账，这使它更接近 production-grade workflow engine，而不是“主脑与下属之间的正式认知协作协议层”。

5. `industry/compiler.py` 非常强化组织模型。
   execution core、researcher、business roles、baseline capabilities、environment constraints、mission、reports_to、goal seeds、schedule seeds 和 topology 都被编译得很清楚；这强化了组织结构，但不会自动等于主脑持续综合权已经同等级落地。

6. `service_strategy.py` 里的不少“智能”，更接近路由启发式。
   explicit role match、context match、keyword match、intent match、file/desktop/browser capability match 等机制在工程上很实用，但它们更像“猜谁适合接”而不是“主脑先理解、再拆解、再回收、再拍板”的完整判断链。

---

## 6. 一句话总判断

COPAW 当前最准确的判断不是：

> “只有多 agent 平台，没有主脑设计。”

而是：

> “主脑对象骨架、主脑聊天前台、周期派工回流链都已经落地，但 delegation / runtime / governance 的工程化强度，仍然显著高于 planning / synthesis / replan 的工程化强度。”

### 6.1 用户体感层的真实判断

这套系统当前非常容易给用户一种典型体验：

- 很复杂
- 很完整
- 模块很多
- 术语很多
- 很像一个先进系统

但一旦落到真实任务上，用户又会明显感觉到：

- 不够聪明
- 不够聚焦
- 不够像一个统一大脑

这不是错觉。

更准确的解释是：

- 项目的“世界观”比“执行闭环”更成熟
- 项目的“组织感”强于“主脑感”
- 项目的“平台复杂度”强于“统一责任中心”

因此用户看到的往往是：

> 一个世界观完备、模块众多、治理很强的平台；
> 但还不是一个在任务理解、拆解、回收、综合和拍板上都足够强势的统一主脑。

### 6.2 当前缺的不是更多模块，而是统一责任中心

当前仓库里已经有很多“各自负责一段”的模块：

- `turn_executor` 负责入口分流
- `main_brain_chat_service` 负责轻聊天前台
- `query_execution_runtime` 负责重执行
- `delegation_service` 负责任务委派
- `actor_mailbox` 负责收件箱与 checkpoint
- `industry/service*` 负责行业团队与生命周期
- `capability_*` 负责能力接入和治理

问题不在于“模块不够”，而在于：

- 谁对主脑计划负责
- 谁对主脑综合负责
- 谁对主脑最终判断负责
- 谁在失败后强制 replan

这些责任在代码结构上仍然不够集中。

---

## 7. 已落地骨架 vs 未闭环部分

### 7.1 已经落地的骨架

以下内容已经是仓库事实：

- `execution-core` 已被收口为单主脑控制核，而不是多个平级 manager
- 主脑聊天前台已从重执行链中拆出 `MainBrainChatService`
- 周期对象、派工对象、汇报对象已经进入 `state.models`
- `run_operating_cycle()` 已能从 backlog 启动 cycle、物化 goal / assignment、驱动调度
- `AgentReportRecord` 已可从 task terminal state 自动生成
- 执行位汇报已可回写 `industry-chat:{instance_id}:execution-core` 控制线程

### 7.2 仍然缺的闭环 A：用户 turn 级任务建模仍然偏弱

虽然系统已经有 `Backlog / Cycle / Assignment`，但“用户这一轮意图如何被拆成清晰任务设计”仍然不够显式：

- turn 级 plan 对象不够清楚
- 任务依赖关系和完成标准没有成为强约束的一等对象
- chat writeback 仍然更像“结构化落单”，而不是“显式任务设计器”

证据：

- 在 `query_execution_runtime.py` 主循环里，最重的对象是 capability context、prompt appendix、system tools、resident agent 和流式运行。
- 还看不到同等级的 `plan object / subtask registry / synthesis state / unresolved questions list`。

后果：

- 用户 turn 的拆解仍较依赖 prompt + model 决议
- 可审计的是落单结果，不是完整思考链

### 7.3 仍然缺的闭环 B：子 agent 报告协议仍然太薄

当前 `AgentReportRecord` 已经存在，但主要字段仍偏轻：

- `headline`
- `summary`
- `result`
- `evidence_ids`
- `decision_ids`

它还缺更稳定的认知协议，例如：

- findings
- uncertainties
- recommendation
- needs_followup
- conflict_with

证据：

- `AgentReportRecord` 已经是一等正式对象，但当前字段仍以 `headline / summary / result / evidence_ids / decision_ids` 为主。
- `delegation_service.py` 与 `query_execution_tools.py` 返回的核心信息也仍偏向 `summary / status / checkpoint / mailbox / phase`，而不是稳定的分析报告 schema。

后果：

- 主脑拿回的是“可运营的回流对象”，但还不是“高质量认知报告”
- 目前更适合做状态回流，不够适合做强综合判断

### 7.4 仍然缺的闭环 C：主脑综合 / replan 核心仍然弱

当前系统已经有 reconcile，但强度仍主要体现在：

- 根据任务状态刷新 assignment 状态
- 根据 report 结果刷新 backlog / cycle
- 把失败项转成 follow-up backlog

它还没有同等显式地做强综合：

- 多报告比较
- 冲突检测
- 证据冲突归因
- 缺口识别
- 二轮 replan
- 最终对外统一裁决

证据：

- 当前已经存在 `run_operating_cycle()`、`_process_pending_agent_reports()`、`reconcile` 等回流与协调入口。
- 但仓库里还没有一个同等级清晰的 `synthesize_subresults()`、`decide_after_reports()`、`resolve_conflicts_between_workers()` 之类的中心化综合模块。

后果：

- “回流”存在，但“综合”仍不够强
- 系统更像会收报告的调度中枢，而不是会强综合的主脑

### 7.5 仍然缺的闭环 D：聊天前台与执行内核仍是部分拆链

当前“主脑聊天拆链落地”这个说法：

- 作为“仓库已有事实”是对的
- 作为“问题已经解决”是错的

真实状态是：

- `MainBrainChatService` 已存在
- 控制线程默认先走主脑聊天前台
- background intake 再异步推进 writeback / kickoff
- 但 `KernelTurnExecutor` 与 `KernelQueryExecutionService` 仍然和主脑聊天共享部分写回/点火语义

证据：

- `MainBrainChatService` 主体处理 snapshot / memory / prompt / chat / persist。
- `QueryExecutionRuntime` 主体处理 resident agent / lease / tool / MCP / streaming / checkpoint。
- 二者之间目前靠 intake、writeback、kickoff 等桥接语义衔接，而不是单一阶段机式的共享认知内核。

后果：

- 前台和后台不再是完全同一个脑
- 但也还没有完全收成两个边界清晰的子系统

### 7.6 仍然缺的闭环 E：能力调用与认知修正之间仍缺显式桥梁

项目对 browser / desktop / skill / MCP 的调用能力很强；
但“调用结果如何改变主脑判断、是否形成新的任务设计或 replan”，仍不够显式。

证据：

- shell / file / browser 等 evidence sink 与 capability mount 已经接得很深。
- 但这些结果更多先进入审计、记录和回放链，而不是一个显式的“认知修正层”。

后果：

- 有 evidence，不等于有更强 decision
- 有 capability，不等于有更强 synthesis

---

## 8. 模块级问题定位（修正版）

### 8.1 `src/copaw/app/routers/_main_brain_boundary.py`

当前定位：

- 旧直连执行入口退役 helper

结论：

- 不应继续把它当作主脑分流核心分析对象

### 8.2 `src/copaw/kernel/turn_executor.py`

当前定位：

- 真正的 `interaction_mode=auto|chat|orchestrate` 分流核心

风险：

- 它已经在承担“主脑聊天 / 执行编排切换”的关键责任
- 但分流后的主脑综合责任并未在这里完全显式化

### 8.3 `src/copaw/kernel/main_brain_chat_service.py`

当前定位：

- 轻主脑聊天前台 + background intake

风险：

- 前台确实已拆出，但真正的 writeback / kickoff 仍由后台 intake 承接
- 因此它更像“沟通前台 + 落单前台”，还不是完整的主脑综合器

### 8.4 `src/copaw/kernel/query_execution_runtime.py`

当前定位：

- 最强执行容器

风险：

- resident agent、mounts、lease、prompt appendix、delegation-first guard 都在这里
- 它对“怎么执行”表达很强，对“怎么综合”表达仍弱

### 8.5 `src/copaw/kernel/query_execution_tools.py`

当前定位：

- 委派工具层

风险：

- `dispatch_query / delegate_task` 都非常清晰
- 但没有同等级的 `collect / compare / synthesize / replan` 系统工具

### 8.6 `src/copaw/state/main_brain_service.py`

当前定位：

- 主脑周期对象与汇报对象的正式 service

风险：

- 对象存在
- 基础 reconcile 存在
- 但高级综合规则仍然偏薄

### 8.7 `src/copaw/industry/service_lifecycle.py`

当前定位：

- 行业自治实际运行主链

风险：

- 已经承接 cycle / assignment / report / reconcile
- 但这部分逻辑非常集中，且以 lifecycle/coordination 为主，缺一个更显式的 report synthesis / replan 子域

### 8.8 `src/copaw/industry/compiler.py`

当前定位：

- 团队与 execution-core 编译器

风险：

- 对“单主脑控制核 + 多执行位”表达清楚
- 但组织编译强，不等于主脑综合已经强

### 8.9 `src/copaw/agents/react_agent.py`

当前定位：

- 通用 ReAct worker 基底

风险：

- 执行位的底座仍是通用 LLM + tools + memory
- 专精性主要来自 prompt 和 capability envelope，不来自更强的角色专用 cognition contract

---

## 9. 测试覆盖揭示出的价值偏向（修正版）

### 9.1 当前测试强覆盖的方向

- runtime lifecycle
- approvals / confirmations
- capability market / install / governance
- delegation / mailbox / checkpoint
- industry bootstrap / update / retire / operating cycle

### 9.2 当前已经存在、但仍偏弱的主脑相关覆盖

以下测试已经存在，不能再说“完全没有”：

- `MainBrainChatService` 前台 prompt / background intake
- `KernelTurnExecutor` 的 auto 路由
- `run_operating_cycle()` 的 assignment 物化
- `AgentReportRecord` 回流 control thread

### 9.3 仍然偏弱的方向

- 多个 agent report 的冲突处理
- 主脑如何比较不同报告并给出统一裁决
- 主脑何时主动 replan
- 最终答案是否优于“摘要拼接”

---

## 10. 排名问题清单

### S 级

- 主脑不是唯一强认知中心。`MainBrainChatService`、`KernelTurnExecutor` 与 `QueryExecutionRuntime` 已经形成职责拆分，但仓库里仍缺一个显式的 `planning + synthesis heart` 作为单一强认知中心。
- delegation 已经被一等工程化，synthesis 还没有同等级工程化。`dispatch_query / delegate_task` 很清晰，但 `collect / compare / resolve / replan` 仍主要散落在 report 回流与生命周期处理中。
- 平台抽象整体上强于认知抽象。这里要强调的是“相对更强”，不是“主脑对象不存在”；当前已经有 `Lane / Backlog / Cycle / Assignment / Report`，但它们更像治理骨架，尚未被收束成强认知闭环。

### A 级

- 组织编译器相对过强，execution core 的持续综合权工程化偏弱。`industry/compiler.py` 已经很强地编译团队结构、岗位关系和 capability baseline，但没有同样强地落下“主脑持续综合权”的显式模块。
- 子 agent 当前更像可配置 worker，而不是天然稳定的 specialist。`react_agent.py` 本质上仍是通用 LLM + tools + skills + MCP + memory 容器，专精主要来自 role/capability 包装，而不是强制分析协议与正式汇报契约。
- 聊天 writeback / kickoff 更像桥接层，而不是统一内核。这里不能写成“拆链是错的”，更准确的说法是：拆链本身合理，但 chat 前台与执行主链之间仍然存在边界桥接感，而不是单心智内核。

### B 级

- prompt 的制度感偏重。这是有根据的倾向判断，但不应写成已经被完全证实的根因；更准确的说法是，它提高了“控制器/治理器”语气的比重，可能压缩综合判断的表达空间。
- 路由启发式容易冒充智能。这个判断部分成立，因为 `service_strategy.py` 确实大量使用 role/context/keyword/capability match；但也不能写成“系统只靠启发式”，因为 `turn_executor.py` 里已经存在 model-assisted auto-mode resolution。
- 工具能力接入复杂度可能持续吞噬认知清晰度。这里更适合定义为架构风险与趋势，而不是已经被完全证明的既成事实；当前能确认的是 capability/MCP/skill/tool 体系很重，而且确实在持续挤压主脑简洁度。

---

## 11. 整改原则

后续让 Codex 动手时，必须遵守以下原则：

1. 不接受伪修复。
   不接受只调 prompt 文案、只多加几个 summary 字段、只继续加路由规则、只继续堆能力系统复杂度。

2. 必须建立在现有主链上整改。
   当前正式主链已经是：
   `Backlog -> OperatingCycle -> Assignment -> AgentReport -> reconcile`
   不允许再平行新造一套 planning/report truth source。

3. 能力层必须继续降级为工具层。
   MCP / skill / browser / desktop 是手脚，不是主脑本身。

4. 主脑聊天前台继续只负责沟通、理解、规划、裁决。
   真正执行必须继续走内核与治理主链。

5. 先补报告协议和综合协议，再补更花哨的能力和角色外观。

6. 在主脑闭环补齐前，原则上不优先继续加模块。
   尤其不应再优先扩张新的 skill、MCP、role、capability surface、workflow、router 或 template；否则大概率只会继续提高复杂度、稀释主脑责任，而不会显著提升统一智能效果。

---

## 12. 推荐整改顺序

### 第一优先级

增强 `AgentReportRecord` 正式协议。

最少补齐：

- findings
- uncertainties
- recommendation
- needs_followup

### 第二优先级

在现有 `OperatingCycle / Assignment / AgentReport` 主链上增加显式 synthesis / replan 子模块。

至少做到：

- collect reports
- compare results
- detect conflicts / holes
- create follow-up backlog or replan signal
- surface final brain judgment

### 第三优先级

继续收紧 `MainBrainChatService` 与执行 runtime 的边界。

目标不是回退，而是把“已落地的拆链骨架”收干净。

### 第四优先级

弱化 control-core prompt 里的 delegation-first 倾向，强化：

- task understanding
- integration responsibility
- final decision ownership

### 第五优先级

补测试：

- 主脑多报告综合测试
- 冲突处理测试
- replan 测试
- 最终答案质量测试

---

## 13. 最终判断

COPAW 不是失败项目。

它已经成功地做成了：

- 可治理的多 agent 平台
- 有正式主链对象的行业自治骨架
- 有真实回流与证据主链的运行系统

但也必须诚实地说：

它当前更成功地做成了“会运行、会治理、会派工、会回流的平台”，
而不是“一个已经完成强综合闭环的主脑系统”。

当前最准确的评价不是：

> 没有主脑，没有拆链，没有周期对象。

而是：

> 主脑骨架、聊天拆链、周期派工回流都已落地；真正缺的是更强的报告协议、更强的综合核心和更强的 replan 闭环。
