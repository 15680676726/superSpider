# V4：能力市场 2.0、Workflow 模板中心与主动寻优规划

本文件是对当前 `V4` 阶段的专项补充规划。

它不替代 `implementation_plan.md`，而是在现有 `V3` 基线已经完成的前提下，明确回答以下 4 个问题：

1. 当前系统里所谓的“workflow automation”今天到底靠什么在跑。
2. 为什么 `V4` 不能只写 `prediction / 独立自动优化侧链`，还必须先补齐能力安装体验与 workflow 模板中心。
3. `skills / integrations / mcp` 在产品层和内部语义层应该怎么统一。
4. `Capability Market 2.0 -> MCP 模板安装面 -> Workflow 模板中心 -> Predictions / 独立自动优化侧链` 应该如何排期。

如果与以下文档冲突，优先级依次为：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `implementation_plan.md`
4. `TASK_STATUS.md`
5. 本文件 `V4_WORKFLOW_CAPABILITY_PLAN.md`

---

## 1. 先说结论

`V4` 不应再被理解为“纯 prediction 版本”。

在当前真实代码基线下，`V4` 应拆成一条连续升级链：

1. 先把 `Capability Market` 从“读写入口”升级成“可发现、可安装、可诊断、可示例运行”的产品面。
2. 先把 `MCP template install` 从后端已有能力，升级成前端可用的模板安装面。
3. 再把当前分散在 `goal / schedule / automation / delegation / bootstrap` 里的 workflow 底座对象化为正式 `Workflow Template Center`。
4. 最后再在这套自动化底座之上叠加 `Predictions / governed recommendation / 旧独立自动优化 / review`。

也就是说：

- `V3` 解决的是“能力集成入口已经存在”。
- `V4-A` 要解决的是“能力安装和自动化复用如何产品化”。
- `V4-B` 才是“预测、建议、主动寻优如何建立在这套产品化自动化底座之上”。

---

## 2. 当前真实基线

`V4` 必须继承以下已落地现实，而不是重写：

### 2.1 已完成的能力集成基线

- `Capability Market` 已是 canonical 产品入口：
  - `/api/capability-market/capabilities*`
  - `/api/capability-market/skills`
  - `/api/capability-market/mcp`
  - `/api/capability-market/hub/*`
- 前端已有 `/capability-market` 页面，当前主要是：
  - Installed
  - Skills
  - MCP
  - Hub
- 后端已经存在正式 install template 安装能力：
  - `GET /api/capability-market/install-templates`
  - `GET /api/capability-market/install-templates/{template_id}`
  - `POST /api/capability-market/install-templates/{template_id}/install`
- 当前已存在 `desktop-windows` 模板，可把本机桌面 host adapter 以外部 `desktop_windows` MCP client 的方式挂入统一 capability graph。

### 2.2 已完成的自动化运行基线

- `Runtime Center -> Automation` 已正式承接：
  - heartbeat 配置、运行、状态查看
  - schedules CRUD / run / pause / resume
- `ScheduleRecord` 已进入统一 `state`，而不是继续由 `jobs.json` 充当运行真相。
- `CronManager` 运行态会持续回写 `ScheduleRecord`。

### 2.3 已完成的 workflow 底座

- `GoalService` 已能：
  - `compile_goal`
  - `dispatch_goal`
  - `dispatch_active_goals`
- `SemanticCompiler` 已能把 `goal / plan / directive` 编译成 `KernelTask`。
- `TaskDelegationService` 已能创建真实 child task，并回流治理与证据。
- `IndustryService` 已能在 bootstrap 时生成：
  - team draft
  - goal seeds
  - schedule seeds
  - runtime-visible routes

### 2.4 当前缺的不是“有没有底座”，而是“有没有产品化对象”

今天系统已经有 workflow automation 的底座，但它是分散的：

- 目标编排在 `GoalService + SemanticCompiler`
- 定时运行在 `Runtime Center Automation + CronManager + ScheduleRecord`
- 多 agent 编排在 `TaskDelegationService`
- 行业初始化种子在 `IndustryDraft / GoalSeed / ScheduleSeed`
- 能力安装模板只在 MCP 层有正式对象

缺少的是：

- 通用 `WorkflowTemplate` 一等对象
- 通用 `WorkflowRun` 一等对象
- 模板参数填写、预览、启动、追踪的前端中心
- 能力模板安装与 workflow 模板之间的产品级联动

### 2.5 已有 actor 级 capability 治理底座，但还没产品化成“精确挂载”

当前仓库已经不是“所有 agent 默认共享全部能力”的状态。

`V3` 已经落地：

- actor / agent 级 capability 读写与治理面
- `baseline / blueprint / explicit / recommended / effective` capability surface
- `Agent Workbench` 的 capability governance 面板

但这套能力治理还没有被提升成 `V4` 的产品化规则：

- 安装一个 `skill / integration / MCP` 之后，还没有正式形成“分配给哪些角色/agent”的主产品流程
- 还没有把“统一能力池”与“单个 agent 的有效可调用面”严格分开
- 还没有把“单个业务 agent 的能力预算”写成正式上限和验收要求

因此 `V4` 必须显式补上：

- 能力可以统一进入全局池子
- 但 agent 只应拿到自己工作的最小有效子集
- 单个业务 agent 的非系统基线能力默认上限为 `12`
- 超出预算时，必须走替换、拆岗或治理确认，而不是继续堆能力

### 2.6 新客户冷启动时，行业组团和能力安装应联成一条链

新客户刚装系统时，往往没有足够的 `skill / MCP / integration` 预装能力。

如果要求用户先自己研究能力市场、先自己安装一批能力、再回去创建行业团队，体验会很差，而且团队 draft 会和真实可用能力脱节。

因此 `V4` 应把“行业团队生成”和“能力安装推进”联成冷启动主链：

1. `industry preview` 时，模型除了生成团队/目标/计划，还同时生成一份“推荐能力安装包”
2. operator 在预览页一并看到：
   - 推荐角色
   - 推荐 workflow
   - 推荐 `skills / integrations / MCP`
   - 每项能力建议分配给哪些角色/agent
3. operator 可以修改、删减、替换
4. `bootstrap` 确认组团时：
   - 先执行 install plan
   - 再写入角色/agent capability assignment
   - 再激活团队、goal、schedule

这样团队一旦成型，就已经带着可工作的能力面，而不是“团队先创建成功，但一运行就发现没有工具可用”。

### 2.7 `execution-core` 在 `V4` 中应收敛为“团队总控核”

当前兼容现实是：

- 内部 canonical `role_id` 仍为 `execution-core`
- 唯一物理 agent/runtime 仍是 `copaw-agent-runner`
- 现有部分产品文案仍会把它叫作 `Spider Mesh 执行中枢`

但 `V4` 的产品语义应明确收敛为：

> 它是行业团队的总控核，不是默认亲自下场干叶子活的前线执行员。

默认职责应是：

- 接收目标与上下文
- 规划、拆解、排程
- 分派任务给证据支援岗 / 专员 / worker
- 监督执行、检查证据、控制风险
- 调整角色能力与安装建议
- 汇总结果、生成日报/周报/阶段汇报

默认不应承担：

- 大量浏览器细操作
- 桌面/软件逐步点击输入
- 渠道一线沟通
- 表格、数据库、文件等叶子执行工作

这些动作应优先下放给专业 agent。

保留例外：

- 当团队里还没有合适 worker
- 或当前动作只是极短链、低风险、一次性的补位动作

此时总控核可以进入 `fallback execution`，但必须：

- 明确记录原因
- 默认走 `guarded` 或更高治理
- 不得长期演化成“最强万能执行脑”

---

## 3. 当前“workflow 模板中心”的真实逻辑是什么

在 `V4-A2` 之前，仓库里没有正式的一等“workflow template center”。

`2026-03-13` 更新：

- `Workflow Template Center MVP` 已经落地
- 但其底层仍然复用以下既有主链，而不是另造执行器

今天所谓的 workflow 逻辑，本质上是以下几条链拼出来的：

### 3.1 Runtime Center Automation

- 这是现有最接近“自动化中心”的正式页面。
- 但它只覆盖：
  - heartbeat
  - schedules
- 它解决的是“已有自动化任务怎么运行和治理”，不是“给用户挑模板并一键启动”。

### 3.2 Goal -> Compiler -> KernelTask

- 这是现有最接近“流程编排内核”的主链。
- 它解决的是：
  - 把 goal 编译成任务
  - 把任务送进 kernel
- 但它仍是 goal 驱动，不是模板目录驱动。

### 3.3 Delegation

- 这是现有最接近“多 agent workflow step handoff”的主链。
- 它已经支持 parent/child task 和治理回流。
- 但它是执行链能力，不是模板产品。

### 3.4 Industry bootstrap

- 这是现有最接近“预置业务流程种子”的主链。
- 它已经会生成默认 roles / goals / schedules。
- 但它只服务行业初始化，不是可复用的 workflow gallery。

### 3.5 MCP template

- 这是现有最成熟的“模板”对象。
- 但它属于 capability install template，不属于 workflow template。

一句话总结当前现状：

> 今天系统里已经有 workflow 底座，并且已经落下正式的 `Workflow Template Center MVP`；其深层运行仍是复用既有 `Goal / Schedule / Delegation / Kernel` 主链。`preset / cancel / assignment-gap / budget diagnostics / install-return flow` 已补齐，当前后续重点转向更深的治理诊断、示例运行与 prediction/recommendation 闭环。

---

## 4. `Skills / Integrations / MCP` 到底是不是 3 种

对外产品层：是。

对内运行语义层：不是。

### 4.1 对外产品分类，允许保留 3 类

`V4` 前端可以明确展示 3 类发现与安装入口：

- `Skills`
  - 本地技能包
  - 提示词、脚本、参考材料、轻量任务包
- `Integrations`
  - 面向产品的官方/半官方集成
  - 例如微信、飞书、Slack、浏览器、桌面、数据库、表格、云盘等
- `MCP`
  - 面向高级用户的协议级客户端配置面
  - 保留原始 transport/command/env 等高级入口

### 4.2 对内统一语义，只允许两层

内部不允许继续长成三套执行系统。

统一后只保留：

- `CapabilityMount`
  - 真正进入执行图谱和治理图谱的统一能力对象
- `CapabilityInstallTemplate`
  - 面向产品的安装模板对象
  - 安装结果最终仍然落成 `CapabilityMount` 或其配置变体

明确禁止：

- 不新增 `SkillRuntime`
- 不新增 `IntegrationRuntime`
- 不新增独立的 `MCPRuntime`
- 不让 workflow 模板直接绕过 capability graph / kernel / evidence

### 4.3 统一能力池不等于“所有 agent 都能调所有能力”

`V4` 必须明确区分两件事：

- `Capability Pool`
  - 系统已安装、已挂载、可被治理的统一能力库存
- `Agent Effective Capability Surface`
  - 单个 agent 在当前角色、当前行业、当前治理状态下真正可调用的能力子集

规则：

- 安装到能力池，不等于自动分配给全部 agent
- `skill / MCP / integration` 都应先进入统一池子，再按角色/agent 形成有效面
- 业务 agent 默认只保留完成其职责所需的最小能力集
- 单个业务 agent 的非系统基线能力默认上限为 `12`
- `system:*` 基线能力不计入这 `12` 个业务能力预算

如果超过上限，只允许以下几种处理：

- 替换低价值能力
- 拆分角色 / 拆分 agent
- 以 `guarded / confirm` 提交治理请求并显式留痕

明确禁止：

- 安装一个 MCP 后默认所有业务 agent 都可调用
- 为了“方便”给单个 agent 长期挂几十个 skill / MCP
- 用 prompt 暗示 agent 会某能力，但 effective capability surface 里并没有

### 4.4 行业初始化应成为 install template 的首个高转化入口

对新客户来说，最自然的入口不是 `Capability Market`，而是 `Industry bootstrap`。

因此 `V4` 应明确：

- `Capability Market` 仍是通用能力市场
- `Industry preview / bootstrap` 则承接冷启动推荐安装包

也就是说：

- 老用户可以直接去能力市场安装
- 新用户应在行业 preview 阶段就拿到一份模型建议的安装清单
- 这份清单的安装结果最终仍进入统一 capability pool，并继续走角色/agent 分配治理

### 4.5 顶层总控与专业执行必须分层

`V4` 应明确团队内至少有两类业务角色：

- `Team Control Core`
  - 默认由 `execution-core` 兼容承载
  - 负责规划、调度、监督、汇报、能力治理
- `Specialist / Worker Roles`
  - 负责真正调用 `skills / MCP / integrations` 做外部动作和叶子执行

默认分配原则：

- install template 推荐角色时，优先推荐显式候选的 specialist / worker / 支援岗
- workflow 模板编排时，优先让总控核做 launch / review / summary
- workflow 的叶子步骤优先绑定模板显式声明的候选专业 agent，而不是把 researcher 当默认硬编码首选

明确禁止：

- 把大多数外部执行能力都默认挂到 `execution-core`
- 因为团队暂时缺角色，就把总控核长期当成万能执行员

---

## 5. `V4` 的正式目标重写

`V4` 的正式目标应从：

> 预测与主动寻优

扩成：

> 在 `V3` 已完成的统一能力入口与 Runtime Center 基线之上，先把能力安装与自动化复用产品化，再建立可治理的预测、建议与主动寻优闭环。

因此 `V4` 的正式交付应包含 4 条主线：

1. `Capability Market 2.0`
2. `Install Template Surface`
3. `Workflow Template Center`
4. `Predictions / governed recommendation / 旧独立自动优化 / review`

并增加一条跨批次硬约束：

5. `Role-scoped capability assignment and budget`

---

## 6. `V4` 批次拆分与排期

建议总周期：`6-7 周`

建议顺序：

1. `V4-A1` 能力市场模板安装面
2. `V4-A2` Workflow Template Center MVP
3. `V4-A3` Workflow 模板和能力模板联动
4. `V4-B1` Prediction / Recommendation
5. `V4-B2` 独立自动优化 / Review / Acceptance

### 6.1 `V4-A1` Capability Market 2.0 + MCP 模板安装面

建议周期：`1 周`

目标：

- 先把后端已存在的 install template 能力变成前端正式可用入口
- 先把当前 `MCP` 页从“手写 JSON / 手改 transport”升级成“模板安装 + 高级配置”双层入口
- 为后续 `Skills / Integrations / MCP` 三类统一发现面打基础
- 把“安装完成后分配给谁”变成正式产品动作，而不是默认全员可用
- 把行业 preview 的“推荐安装包”读面一起补出来，为冷启动用户铺路
- 把“总控核默认不吃叶子执行能力”写进模板推荐策略

本批次明确基于现有实现升级：

- 不再保留旧 `/api/capability-market/mcp/templates*` 产品壳
- 不重写 `Capability Market`
- 不新造一套安装执行链
- 继续复用 `system:create_mcp_client`

后端产出：

- `Capability Market` 新增 install template 聚合读面
- `install-templates*` 补 diagnostics / examples / notes 扩展字段
- 不再保留旧 `mcp/templates*` sub-surface
- install template 响应补齐：
  - `suggested_roles`
  - `default_assignment_policy`
  - `capability_budget_cost`
  - `control_core_fit`
- `industry preview` 响应补齐推荐安装包：
  - 推荐模板
  - 推荐原因
  - 建议角色绑定
  - 预估安装风险

前端产出：

- `/capability-market?tab=mcp` 增加 Template Gallery
- 模板详情 Drawer：
  - 模板说明
  - 风险等级
  - 安装参数
  - 生成的 capability tags
  - 示例运行
  - 诊断入口
- 安装流程增加：
  - 仅安装到池子
  - 安装并提交分配到指定角色/agent
  - 预算占用与超限提示
  - 对总控核分配给出额外告警
- `/industry` preview 页增加：
  - 推荐能力安装包卡片
  - 按角色查看建议能力
  - 勾选/取消/替换建议项
- 保留“高级 JSON / 原始 MCP 配置”作为 expert mode，而不是主入口

验收标准：

- Operator 不需要手写 JSON 也能安装 `desktop-windows`
- 安装后能直接在 Capability Market 看见已生成的 mount
- 安装后不会默认把该能力暴露给全部业务 agent
- 单个业务 agent 的有效业务能力数超过 `12` 时，前端和后端都能显式阻断或进入治理流
- 安装失败能返回可见错误，而不是只写日志
- 新客户在行业 preview 页就能看到一份可编辑的推荐安装包，而不必先手工研究能力市场
- 大多数外部执行模板不会默认建议分配给 `execution-core`

### 6.2 `V4-A2` Workflow Template Center MVP

状态补充（`2026-03-13`）：

- 已落地最小正式对象：`WorkflowTemplateRecord / WorkflowPresetRecord / WorkflowRunRecord`
- 已落地正式后端面：`/api/workflow-templates*`、`/api/workflow-runs*`、`/api/workflow-templates/{template_id}/presets`
- 已落地正式前端面：`/workflow-templates`、`/workflow-runs/:runId`
- 已落地正式最小治理动作：`POST /api/workflow-runs/{run_id}/cancel`
- 当前仍未补齐：按 agent assignment gap / budget enforcement、run filter/deep-link 扩展

建议周期：`2 周`

目标：

- 把当前分散的 workflow 底座对象化成正式模板中心
- 先做“可发现、可预览、可参数化、可启动、可追踪”的 MVP
- 明确 workflow 运行复用既有 `Goal / Schedule / Task / Decision / Evidence`，不另造运行内核
- 明确 workflow 模板不仅声明“需要哪些能力”，还要声明“由哪些角色/agent 使用这些能力”
- 明确总控核默认只拥有 `launch / supervise / summarize` 相关步骤

本批次明确基于现有实现升级：

- 复用 `GoalService`
- 复用 `SemanticCompiler`
- 复用 `ScheduleRecord / Runtime Center schedules`
- 复用 `KernelDispatcher`
- 复用 `TaskDelegationService`
- 复用 `EvidenceLedger`

不允许：

- 新建平行 workflow executor
- 用前端本地状态伪造 workflow run
- 让 workflow 跳过 kernel 直接写任务状态

后端正式对象：

- `WorkflowTemplateRecord`
- `WorkflowPresetRecord`
- `WorkflowRunRecord`

前端页面：

- `/workflow-templates`
  - 模板列表
  - 分类筛选
  - 适用行业/团队筛选
  - 依赖能力状态提示
- `/workflow-templates/{template_id}`
  - 模板说明
  - 参数表单
  - 依赖能力
  - owner / target role
  - 角色能力预算影响
  - 预览结果
  - 一键启动
- `/workflow-runs/{run_id}`
  - 运行状态
  - materialized goals / schedules / tasks
  - decisions
  - evidence
  - 失败原因

验收标准：

- 至少能用模板启动一个正式 workflow run
- run detail 能追到已有 `goal / schedule / task / decision / evidence`
- 预览和启动分离，用户能先看到将产生什么对象再确认执行
- 模板预览时能看见各步骤 owner、所需能力、缺失项和预算占用
- 模板预览时能区分“总控步骤”和“叶子执行步骤”

### 6.3 `V4-A3` Workflow 模板与能力模板联动

状态补充（`2026-03-13`）：

- 已落地最小联动链：workflow dependency preview -> install template ref -> Capability Market `Install Templates` 前端页
- 已新增首个 desktop/install-linked workflow 模板：`desktop-outreach-smoke`
- 当前已补齐：安装完成后自动回流 workflow 启动、安装时默认带出按 agent `merge` capability assignment、以及已安装但 disabled 模板的 ready 恢复
- 当前仍未补齐：install template diagnose / example run / error drilldown，以及 preset/install plan 更深级联

建议周期：`1 周`

目标：

- 让 Workflow Template Center 真正形成“缺什么能力就补什么能力”的产品链路
- 把模板中心做成“常用自动化流程模板 + 一键运行 + 参数填写”的正式产品面
- 把“安装模板 -> 角色分配 -> workflow 启动”做成单链路
- 把“行业组团确认 -> 安装推荐包 -> capability assignment -> bootstrap 激活”做成冷启动单链路
- 缺 worker 时优先建议补 worker/补能力，而不是把能力堆给总控核

核心产品动作：

- 当 workflow 模板缺少依赖 capability 时：
  - 直接展示缺失项
  - 直接跳转到对应 install template
  - 安装时默认带出建议角色/agent 分配
  - 安装完成后回流 workflow 模板详情继续启动
- 支持 workflow preset：
  - 行业默认预设
  - 团队默认预设
  - operator 自定义预设
- 支持 bootstrap install preset：
  - 行业默认安装包
  - operator 调整后的最终安装包

验收标准：

- 一个 workflow 模板可以明确声明自己依赖哪些 capabilities
- 缺依赖时用户不会卡在黑盒错误里
- 从模板详情到能力安装到回流启动形成单链路
- workflow 所需能力不会自动扩散到无关 agent
- 从行业 preview 到组团确认到安装再到激活形成单链路
- 当缺少合适执行角色时，系统会优先提示“补角色/补能力”，而不是默认让总控核代劳

### 6.4 `V4-B1` Predictions / Recommendation

建议周期：`1-2 周`

目标：

- 在 workflow/productized automation 底座之上，建立正式 prediction 对象
- 让 prediction 不再只是聊天里的一段分析文字

本批次新增正式对象：

- `PredictionCase`
- `PredictionScenario`
- `PredictionSignal`
- `PredictionRecommendation`

输入来源：

- `industry`
- `reports`
- `metrics`
- `evidence`
- `learning feedback`
- `WorkflowRunRecord`
- `Goal / Schedule / Task / Delegation` 运行历史

验收标准：

- 任一 prediction 能追到输入来源
- 任一 recommendation 能追到关联 workflow / goal / schedule
- 支持多场景输出，而不是单点结论

### 6.5 `V4-B2` 独立自动优化 / Review / Acceptance

建议周期：`1 周`

目标：

- 把 recommendation 接入统一治理链
- 建立 prediction review 与 workflow execution review
- 完成 V4 首轮真实世界验收

核心闭环：

- `PredictionRecommendation -> DecisionRequest -> approved action -> execution -> evidence -> review`
- `WorkflowRun -> outcome -> review -> next preset / next recommendation`

验收标准：

- 所有 recommendation 仍经过 `auto / guarded / confirm`
- workflow / prediction 都不能绕过 kernel
- `Reports / Performance / Runtime Center` 能统一看见结果

---

## 7. `Workflow Template Center` 建议对象模型

以下对象是 `V4` 的最小新增对象，不是全新运行系统。

### 7.1 `CapabilityInstallTemplate`

定位：

- 面向产品的安装模板对象
- 服务于 `Skills / Integrations / MCP` 的发现、安装、诊断、示例运行

建议字段：

- `id`
- `category`：`skill | integration | mcp`
- `title`
- `summary`
- `provider`
- `parameter_schema`
- `secret_requirements`
- `generated_capability_refs`
- `suggested_roles`
- `default_assignment_policy`
- `capability_budget_cost`
- `control_core_fit`
- `diagnostic_actions`
- `example_runs`
- `risk_level`
- `notes`

### 7.1a `IndustryCapabilityRecommendationPack`

定位：

- 行业 preview 阶段生成的冷启动推荐安装包
- 是“团队建议”和“能力建议”的桥接对象

建议字段：

- `industry_profile_snapshot`
- `recommended_templates`
- `role_bindings`
- `workflow_bindings`
- `control_core_summary`
- `rationale`
- `risk_summary`
- `budget_summary`
- `editable`

### 7.2 `WorkflowTemplateRecord`

定位：

- 面向 operator 的可复用自动化模板对象

建议字段：

- `id`
- `name`
- `summary`
- `category`
- `owner_scope`
- `parameter_schema`
- `default_inputs`
- `required_capabilities`
- `owner_role_bindings`
- `step_capability_requirements`
- `capability_budget_impact`
- `control_owner_role_id`
- `fallback_execution_policy`
- `materialization_strategy`
- `goal_blueprint`
- `schedule_blueprint`
- `delegation_blueprint`
- `risk_baseline`
- `evidence_expectations`
- `created_at`
- `updated_at`

### 7.3 `WorkflowPresetRecord`

定位：

- 模板的可复用参数预设对象

建议字段：

- `id`
- `template_id`
- `name`
- `summary`
- `owner_scope`
- `industry_scope`
- `parameter_overrides`
- `created_by`
- `created_at`

### 7.4 `WorkflowRunRecord`

定位：

- 模板实例化后的运行锚点对象
- 它不替代 `Task`，而是把一次模板启动锚到既有执行链

建议字段：

- `id`
- `template_id`
- `preset_id`
- `status`
- `input_payload`
- `owner_agent_id`
- `owner_scope`
- `materialized_goal_ids`
- `materialized_schedule_ids`
- `root_task_ids`
- `decision_ids`
- `evidence_ids`
- `last_error`
- `launched_at`
- `completed_at`

明确要求：

- `WorkflowRunRecord` 只做锚点与查询，不再造平行 step runtime
- 具体执行状态继续复用 `Task / TaskRuntime / DecisionRequest / EvidenceRecord`

---

## 8. 建议 API 面

### 8.1 能力安装面

当前正式 canonical 接口：

- `GET /api/capability-market/install-templates`
- `GET /api/capability-market/install-templates/{template_id}`
- `POST /api/capability-market/install-templates/{template_id}/install`

`V4-A1` 后的扩展接口：

- `GET /api/capability-market/install-templates`
- `GET /api/capability-market/install-templates/{template_id}`
- `POST /api/capability-market/install-templates/{template_id}/install`
- `POST /api/capability-market/install-templates/{template_id}/diagnose`

说明：

- 不再保留旧 `mcp/templates*`
- 聚合 install templates 只是产品层聚合，不引入第四套执行语义

### 8.2 Workflow 模板面

建议新增：

- `GET /api/workflow-templates`
- `GET /api/workflow-templates/{template_id}`
- `POST /api/workflow-templates/{template_id}/preview`
- `POST /api/workflow-templates/{template_id}/launch`
- `GET /api/workflow-runs`
- `GET /api/workflow-runs/{run_id}`
- `POST /api/workflow-runs/{run_id}/cancel`

明确要求：

- `preview` 只返回 materialization diff，不直接执行
- `launch` 仍走统一 kernel / governed write path
- `run detail` 必须返回跳转到既有 `goal / schedule / task / decision / evidence` 的 route

### 8.3 行业冷启动安装面

建议复用现有行业接口扩展，而不是新造平行 onboarding 系统：

- `POST /api/industry/v1/preview`
  - 返回 `draft + capability recommendation pack`
- `POST /api/industry/v1/bootstrap`
  - 接受 `final draft + approved install plan`

明确要求：

- preview 只生成推荐，不直接安装
- bootstrap 才执行真实安装与角色分配
- install 失败时必须显式返回失败项，且不允许假装团队已完整激活

---

## 9. 建议前端 IA

### 9.1 Capability Market

建议从当前：

- Installed
- Skills
- MCP
- Hub

升级为：

- Installed
- Skills
- Integrations
- MCP
- Diagnostics

其中：

- `Skills` 偏轻量技能包与 Hub 安装
- `Integrations` 偏产品化官方集成与 host adapter
- `MCP` 保留高级原始配置
- `Diagnostics` 负责健康检查、示例运行、错误定位

并增加一个统一动作原则：

- 任何安装动作都必须能继续走到“分配给谁”
- 默认推荐“按角色/agent 精确分配”，而不是默认全员开启

### 9.2 Workflow Template Center

建议新增一级入口：

- `/workflow-templates`

最小交互：

- 模板列表
- 模板详情
- 参数表单
- 预览
- 启动
- 运行详情

与现有页面联动：

- `Capability Market`
  - 负责依赖能力安装
- `Runtime Center`
  - 负责运行中状态、治理、evidence drill-down
- `Reports / Performance`
  - 负责模板运行效果和复盘指标

### 9.3 Industry Preview / Bootstrap

`/industry` 在 `V4` 应新增以下交互：

- 团队草案编辑
- 推荐安装包预览
- 按角色能力建议查看
- 明确区分“团队总控职责”和“专业执行职责”
- 勾选后生成最终 install plan
- 组团确认时统一执行 bootstrap + install

---

## 10. 删旧与兼容要求

`V4` 必须坚持“在现有基础上升级”，所以兼容策略如下：

### 10.1 保留并升级

- 保留 `Capability Market`，不新开第二个集成中心
- 保留 `Runtime Center -> Automation`，不新开第二个 schedule/heartbeat 控制面
- 保留 `GoalService / SemanticCompiler / KernelDispatcher / DelegationService`
- 保留 `industry preview/bootstrap`，在其上扩展推荐安装包，不新开第二个团队初始化系统
- 内部兼容保留 `execution-core / copaw-agent-runner`，但产品语义逐步收敛为“团队总控核”

### 10.2 逐步降级

- `Agent/MCP` 现有手工 JSON 创建页降级为 expert mode
- 旧 `/skills`、`/mcp` legacy 客户端依赖继续收缩，不再扩张

### 10.3 明确禁止

- 不新增 workflow 本地 JSON 真相源
- 不新增 workflow 专属执行器
- 不新增绕过 kernel 的模板启动路径
- 不新增 `skill runtime / integration runtime / mcp runtime` 三套内部语义
- 不把统一能力池误做成“所有业务 agent 默认全量可调用”
- 不允许单个业务 agent 长期持有超过 `12` 个非系统基线能力而没有治理与说明
- 不允许行业 preview 只生成团队、不生成能力建议，导致 bootstrap 后团队天然残废
- 不允许继续把 `execution-core` 默认设计成一线万能执行员

---

## 11. `V4` 验收顺序

`V4` 应按以下 gate 放行，而不是一次性大爆炸：

### Gate-1：能力模板安装面可用

- `desktop-windows` 可从前端模板面直接安装
- 安装结果进入统一 capability graph
- 安装失败显式可见

### Gate-2：Workflow Template Center MVP 可用

- 至少 3 个内置 workflow 模板
- 支持参数填写、预览、启动
- run detail 可回看 materialized runtime objects

### Gate-3：Prediction / Recommendation 可用

- prediction 对象正式持久化
- recommendation 进入统一治理链
- 不存在 prediction 旁路写状态

### Gate-4：Review / 独立自动优化可用

- workflow / prediction 都能复盘
- `Reports / Performance / Runtime Center` 可见
- 完成 operator E2E 与 provider/environment 组合验收

---

## 12. 一句话版本定义

`V4` 的正确版本定义应是：

> 基于已经完成的 `V3` 能力市场与 Runtime Center 主链，先把能力安装与 workflow 自动化产品化，再把 prediction / recommendation / 旧独立自动优化能力建立在这套正式自动化底座之上。
