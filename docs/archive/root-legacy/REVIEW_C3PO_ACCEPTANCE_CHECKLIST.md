# C3PO 主脑闭环整改验收清单

> 配套文档：
> - 审计基线：[docs/archive/root-legacy/REVIEW_C3PO_FULL_AUDIT.md](/D:/word/copaw/docs/archive/root-legacy/REVIEW_C3PO_FULL_AUDIT.md)
> - 执行计划：[2026-03-24-main-brain-cognitive-closure.md](/D:/word/copaw/docs/superpowers/plans/2026-03-24-main-brain-cognitive-closure.md)

**目的：** 本清单只回答一件事：本轮整改是否真的补上了主脑闭环，而不是做了看起来很忙、实际上没有改变根问题的伪修复。

**使用方式：**

- 代码实现前，用它约束范围。
- 代码评审时，用它判断是否偏题。
- 功能验收时，用它判断是否放行。

**总放行规则：**

- `S` 级项必须全部通过。
- `A` 级项不能存在明显反例。
- `B` 级项允许渐进优化，但不能继续恶化。

---

## 1. 全局红线

- 不允许新造第二套 planner、第二套 report store、第二套 orchestration kernel。
- 不允许把更多责任塞给 `skill / MCP / browser / desktop / capability surface`，再把它包装成“主脑变聪明了”。
- 不允许只改 prompt 文案就宣称闭环补齐。
- 不允许只加几个 `summary` 字段、不补真实综合行为，就宣称子 agent 报告协议完成。
- 不允许只加更多 role / route / capability match 规则，拿启发式路由冒充主脑判断。
- 不允许在未补主脑闭环前继续优先扩张新的 role、skill、MCP、workflow、router、template。

---

## 2. S 级验收项

### S1. 主脑是否成为唯一强认知中心

**通过标准：**

- 必须存在一个显式负责 `planning / synthesis / final judgment / replan` 的主脑认知中心，而不是继续散落在 `chat service / turn executor / query runtime` 之间。
- `MainBrainChatService`、`KernelTurnExecutor`、`QueryExecutionRuntime` 的职责边界必须更清楚：
  - chat 负责沟通与 intake
  - runtime 负责受治理执行
  - 主脑认知中心负责计划、综合、裁决
- 面向 operator 的最终结论必须体现为主脑统一结论，而不是若干子结果拼接。

**不通过信号：**

- 仍然找不到一个同等级显式的主脑综合入口。
- chat 和 runtime 继续各自持有一部分判断逻辑，形成双脑感。
- 最终输出仍主要来自 resident agent 顺势生成，而不是主脑显式综合后给出。

**最低验证：**

- 至少一条单元/集成测试证明：主脑收到多份回流后会进入统一综合路径。
- 至少一条端到端链路证明：用户前台理解、后台执行、最终回答属于同一认知闭环。

### S2. delegation 与 synthesis 是否达到同等级工程化

**通过标准：**

- 除了 `dispatch_query / delegate_task` 之外，必须有同等级清晰的 `collect / compare / synthesize / decide / replan` 行为入口。
- report 回流后，主脑必须能：
  - 比较多份结果
  - 识别冲突
  - 识别缺口
  - 判断是否需要补派或 replan
  - 形成统一裁决

**不通过信号：**

- 仍然只有“派出去”的正式工具，没有“拿回来综合”的正式机制。
- report 回流后只做状态更新、follow-up 落单或摘要回写。
- 依旧主要靠单轮 LLM 顺势写一段“看起来像总结”的文本。

**最低验证：**

- 至少一条单元测试覆盖冲突识别。
- 至少一条集成测试覆盖 follow-up / replan 信号生成。
- 至少一条用户故事测试覆盖“多报告 -> 主脑统一结论”。

### S3. 平台抽象是否真正让位于认知闭环

**通过标准：**

- 本轮新增的中心对象和代码路径，主要围绕 `plan / report / synthesis / replan` 收束，而不是继续扩张 role、capability、runtime、governance 复杂度。
- `Lane / Backlog / Cycle / Assignment / Report` 必须更明显地为主脑闭环服务，而不是继续只表现为治理骨架。

**不通过信号：**

- 新增工作主要是更多 capability mount、更多 routing rule、更多 workflow surface。
- 代码体量明显增加，但主脑综合、报告协议、replan 仍然没有成为正式一等行为。

**最低验证：**

- 变更说明里必须能明确指出：本轮新增了哪些认知闭环对象、删掉了哪些伪闭环做法、限制了哪些平台膨胀点。

---

## 3. A 级验收项

### A1. 组织编译器是否仍在稀释主脑持续综合权

**通过标准：**

- `industry/compiler.py` 继续保留单主脑控制核，但 execution core 的持续综合责任要有更明确的工程落点。
- 组织结构、岗位关系、baseline capability 不能继续替代主脑综合模块本身。

### A2. 子 agent 是否具备更正式的汇报契约

**通过标准：**

- `AgentReportRecord` 或等价正式对象必须至少能稳定承载：
  - `findings`
  - `uncertainties`
  - `recommendation`
  - `needs_followup`
- 子 agent 回流结果必须更像正式认知报告，而不只是 `summary / status / checkpoint`。

### A3. chat/runtime 拆链是否从“桥接”收束成“清晰边界”

**通过标准：**

- 拆链可以保留，但不能继续维持双脑体验。
- intake / writeback / kickoff 的共享语义必须集中，不应继续在 chat 与 runtime 两边各留一半。

---

## 4. B 级验收项

### B1. prompt 是否从制度执行器收束回判断者

**通过标准：**

- control-core prompt 仍可保留治理和 delegation 约束，但必须更明确强调：
  - task understanding
  - report comparison
  - conflict detection
  - final decision ownership

### B2. 路由启发式是否退回辅助位

**通过标准：**

- `service_strategy.py` 的 role/context/keyword/capability match 仍可存在，但只能作为辅助信号，不能继续冒充主脑判断主体。

### B3. 能力平台复杂度是否被主动节制

**通过标准：**

- 本轮整改期间，不以新增 skill、MCP、role、workflow、router 为主要交付物。
- capability 继续只作为手脚和外设，不重新承担主脑责任。

---

## 5. 伪修复判定

出现以下任一情形，默认判定为伪修复：

- 只是重写 prompt 文案，没有新增或收束真实闭环对象。
- 只是加 `summary`、`headline`、`note` 一类轻字段，没有新增综合行为。
- 只是扩写 routing rule、keyword match、capability match。
- 只是把原有逻辑搬个文件，不改变责任边界。
- 只是新增更多角色、更多能力、更多模板，让系统看起来更像平台。
- 只是让前端显示更多信息，但后端仍没有统一综合和 replan。

---

## 6. 最低测试矩阵

本轮至少需要以下验证：

- 单元测试：报告协议持久化、综合规则、冲突识别、replan 信号。
- 集成测试：`Backlog -> Cycle -> Assignment -> AgentReport -> synthesis -> follow-up / replan` 主链。
- 内核测试：chat/runtime 共享 intake 路径、`interaction_mode=auto` 路由不回退成双脑。
- 前端或 API 验证：operator 能看到主脑综合结果、冲突状态、follow-up 状态。

---

## 7. 最终放行问题

只有当下面 4 个问题都能明确回答“是”，本轮整改才应放行：

1. 主脑是否已经比以前更像唯一强认知中心？
2. 多 agent 是否已经从“会派工”升级到“会综合”？
3. 用户是否更容易感觉自己在和一个统一大脑协作，而不是在使用一个复杂平台？
4. 本轮是否真正减少了伪闭环，而不是继续增加模块复杂度？
