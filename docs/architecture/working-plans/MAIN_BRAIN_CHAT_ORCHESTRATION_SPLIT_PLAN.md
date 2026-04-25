# MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md

本文件用于定义 `V7 main brain autonomy` 阶段下，主脑聊天前台的下一轮正式收口方案：

> 把“纯聊天模式”与“执行编排模式”彻底拆开，默认聊天不再直接进入 `kernel query execution`，主脑先负责沟通、澄清、判断、规划；是否进入执行编排由主脑自动裁决，主脑判断不了时直接问人类。

如果与以下文档冲突，优先级依次为：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
5. 本文件 `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md`
6. `CHAT_RUNTIME_ALIGNMENT_PLAN.md`

本文件不推翻 `CHAT_RUNTIME_ALIGNMENT_PLAN.md` 中“删除 frontdoor / 删除 task-thread 前置拆分 / 把风险边界下沉到 runtime 和 governance”的方向；
它只正式修正其中一个已不再适用的假设：

- 旧假设：`/chat` 默认应直接进入统一执行内核
- 新假设：`/chat` 默认应进入主脑对话前台的 `auto` 裁决链：多数消息走纯聊天；需要执行时主脑自动切入执行编排；主脑判断不了时问人类（同时保留“一次性强制下一条执行编排”覆盖入口）。

`2026-04-12` 代码核对修正：

- 这份计划里的核心拆分已经基本落地：`KernelTurnExecutor auto` 当前默认多数消息走 `MainBrainChatService`，只有显式 `requested_actions`、确认/恢复连续性、attached intake contract、Buddy 强执行态、明显直接执行请求等信号才会转去 `MainBrainOrchestrator`。
- 因此，文中把“当前默认聊天仍是执行型 query runtime”当成现状的表述，现应视为历史背景，不再代表活代码。
- 文中保留的 `dispatch_goal / dispatch_active_goals / task-thread` 等描述，也只能视为当时待清理的历史问题，不代表当前前台正式能力面。

---

## 0. 用户口径与非谈判约束

本轮方案必须同时满足以下约束：

- 默认全交给主脑，但主脑先做沟通、判断和规划，不要一句话就直接派给某个执行位。
- 主脑判断不了时，要通过聊天窗口明确告知人类，由人类判断。
- `thinking / tool_use / tool_result` 默认不隐藏，operator 需要看见系统是否又在乱调工具。
- prompt 瘦身不能把团队职业成员删掉；主脑必须知道“团队里谁是谁、各自负责什么、能力范围是什么”。
- 默认聊天不要直接进 `kernel query execution`。
- 主脑聊天态不要再暴露 `dispatch_query / delegate_task / dispatch_active_goals`。
- 聊天态要减 prompt、减迭代、减 session 持久化、减本地 token 统计负担，但不能因为“完全失忆”而变傻。
- 日报 / 周报现有前端展示链本轮不动。

---

## 1. 当前已确认的真实问题

以下问题已经通过现有实现和本机配置确认：

### 1.1 当前 `/chat` 仍然直接进入执行主链

- 前端聊天默认发到 `POST /api/runtime-center/chat/run`
  - `console/src/pages/Chat/useChatRuntimeState.ts`
- `chat/run` 会直接流式调用 `KernelTurnExecutor.stream_request()`
  - `src/copaw/app/routers/runtime_center_routes_core.py`
- 后端继续走 `KernelQueryExecutionService` 常驻执行链
  - `src/copaw/kernel/turn_executor.py`
  - `src/copaw/kernel/query_execution_runtime.py`

这段现已过时：当前聊天前台虽然继续共用 `/runtime-center/chat/run` 这个统一前门，但 `auto` 默认多数消息已经回到纯聊天链，而不是默认作为“执行型 query runtime”处理。

### 1.2 本计划写作时，主脑聊天态仍暴露执行编排工具

当前 execution-core 对外仍允许以下 system capability：

- `system:dispatch_active_goals`
- `system:dispatch_goal`
- `system:dispatch_query`
- `system:delegate_task`
- `system:apply_role`
- `system:discover_capabilities`

对应位置：

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/query_execution_tools.py`
- `src/copaw/kernel/query_execution_prompt.py`

这会把主脑普通聊天，直接推向“学一点就分配、问一句就派工”的执行中枢人格，而不是先做理解和规划。

### 1.3 当前 prompt 还在明确鼓励主脑派工

当前 prompt 中存在明确的 delegation-first 规则，例如：

- control core 应把 learned procedure 转成 routing / assignment / verification
- 当有 teammate 时优先 `dispatch_query` 或 `delegate_task`
- prompt capability lines 会告诉模型“可直接把工作交给队友”

这会让普通聊天天然偏向编排，而不是先沟通。

### 1.4 当前聊天重负载来自执行 runtime，而不是 UI 显示本身

当前慢、卡、升温的根因主要在执行链：

- `max_iters` 走执行型配置
- resident agent 每轮会 `rebuild_sys_prompt()`
- 会 `load_session_state()` / `save_session_state()`
- 开启 memory manager 时会注册 `memory_search` 工具和 memory compaction hook
- 本地 token 统计、长 prompt、执行工具注册都会带来额外负担

对应位置：

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/agents/react_agent.py`

### 1.5 工具与思考流现在可见，而且这项能力要保留

当前 renderer 与本机配置已允许显示工具和 reasoning 细节：

- `src/copaw/app/channels/renderer.py`
- `C:\Users\21492\.copaw\config.json`

因此当前看到的：

- `Thinking`
- `dispatch_active_goals`
- `dispatch_query`
- `delegate_task`
- `memory_search`

不是“前端显示 bug”，而是聊天真的走到了工具执行链。本方案不隐藏这些内容，而是减少默认聊天态不必要地产生这些内容。

---

## 2. 本轮方案要解决的核心矛盾

当前系统已经完成了：

- 前台只保留主脑聊天入口
- 执行位汇报可以回流主脑控制线程
- `Decision / Patch` 默认先由主脑裁决
- `V7` 的 lane / backlog / cycle / assignment / report 主链已经建立

本计划写作时，聊天前台仍缺一个正式分层：

- “主脑和人类沟通”没有从“主脑执行编排”里物理拆出来
- “主脑知道团队结构”与“主脑能直接调用派工工具”混成一件事
- “聊天需要记忆”与“聊天必须开放 memory_search 工具”混成一件事
- “operator 要看见工具流”与“默认聊天就应该产生大量工具流”混成一件事

因此本计划当时的目标，不是继续微调 prompt，而是把主脑聊天前台拆成两条正式链。

---

## 3. 目标状态

### 3.1 一个聊天窗口，两条后台链

前端仍保留一个主脑聊天窗口，但后台正式拆成两种运行态：

1. `纯聊天模式`
   - 默认进入
   - 只负责沟通、理解、澄清、判断、规划、解释、汇报解读
2. `执行编排模式`
   - 由主脑自动裁决触发（或 operator 一次性强制下一条进入）
   - 才允许任务派发、执行编排、写回、调用执行型 system tool

这不是恢复旧的“双聊天入口”，而是在同一聊天窗口后面拆两条不同主链。

### 3.2 默认聊天不再进入执行内核

默认 `POST /api/runtime-center/chat/run` 不应再直接进入 `KernelTurnExecutor -> KernelQueryExecutionService`。

它应进入新的轻量主脑聊天链，只消耗最小必要上下文，并输出：

- 回复
- 澄清问题
- 建议计划
- 是否建议进入执行编排

### 3.3 执行编排默认由主脑裁决（不确定时问人类）

只有以下情形之一出现，才允许进入执行编排模式：

- operator 明确表达要执行（例如“开始执行 / 进入执行编排 / 现在执行”）
- operator 使用明确的 slash command / action chip / “下一条强制执行编排”
- 主脑判断该消息是明确的执行意图（例如具体动作请求、需要派工、需要写回）
- 系统已有待人确认的正式治理对象，需要通过聊天窗口完成确认后继续执行

不允许：

- 因普通一句自然语言自动跳入执行编排
- 因命中“分析 / 研究 / 总结 / 看看 / 处理一下”等词直接启用执行工具

### 3.4 编排结束后返回纯聊天默认态

执行编排一旦完成当前轮：

- 结果摘要回写同一主脑聊天线程
- 前端默认回到纯聊天态
- 不保留“你现在一直在执行模式里”的长期粘滞状态

---

## 4. 两种模式的正式契约

## 4.1 纯聊天模式

### 4.1.1 主职责

纯聊天模式只负责：

- 理解 operator 需求
- 澄清歧义
- 解释团队当前状态
- 解释谁负责什么
- 解读日报 / 周报 / 汇报 / backlog / cycle / assignment
- 先把结果口号或模糊需求拆成执行前方案与结构化目标
- 输出计划草案、优先级建议、风险说明
- 判断是否需要进入执行编排
- 在主脑判断不了时，直接向人类提问

### 4.1.2 明确禁止暴露的能力

纯聊天模式默认不向模型暴露以下编排型 system tool：

- `system:dispatch_active_goals`
- `system:dispatch_goal`
- `system:dispatch_query`
- `system:delegate_task`

同时默认不开放：

- 浏览器 / 桌面实时外部动作
- host observation
- durable operating truth 写回
- 任意执行型 capability mount

纯聊天模式可以先自动拆执行前方案、生成结构化目标或写回建议；当主脑已经判断需求充分时，应自动切到执行编排，不要求客户再说固定触发词。

### 4.1.3 运行预算

纯聊天模式必须是轻量链：

- 默认单轮回答
- 最多允许极少量内部二次整理，不走执行型多轮工具循环
- 不挂 resident execution agent
- 不复用 execution-core 的大 prompt 和大工具包

## 4.2 执行编排模式

### 4.2.1 主职责

执行编排模式才负责：

- 正式创建 / 派发 / 激活任务
- 给职业成员派工
- 更新 backlog / lane / schedule / assignment
- 调用需要治理的 system tool
- 触发 kernel 风险判定和 evidence 链

### 4.2.2 允许暴露的能力

执行编排模式才允许按治理边界暴露：

- `system:dispatch_goal`
- `system:dispatch_query`
- `system:delegate_task`
- `system:dispatch_active_goals`
- 其它正式执行型 system capability

### 4.2.3 与纯聊天的关系

执行编排模式不是第二人格，不是另一个“平行主脑”。

它只是主脑在收到明确执行授权后的后台工作态。

---

## 5. Prompt 瘦身方案

## 5.1 纯聊天态必须保留的内容

纯聊天态 prompt 只保留 5 类信息：

1. 主脑身份
   - 主脑是谁
   - 当前行业 / 载体是什么
   - 当前沟通职责是什么
2. 当前运行摘要
   - 当前 cycle
   - 当前关键 lane
   - 当前最重要 backlog / blocker / 待确认事项
3. 团队职业成员 roster
   - 谁是谁
   - 每个人做什么
   - 每个人的能力范围
4. 最近会话摘要
   - 最近几轮在聊什么
   - 尚未解决的问题
5. 后端控制注入的记忆摘要
   - operator 长期偏好
   - 已确认策略
   - 关键历史决策

## 5.2 团队 roster 的最小注入格式

每个职业成员至少保留以下字段：

- `agent_id`
- `display_name`
- `role_name`
- `one-line responsibility`
- `capability envelope summary`
- `current assignment summary`
- `when to escalate back to main brain`

建议格式是“一人一行或两行”，不要把完整 capability mount、完整工作台 JSON、完整历史任务全部塞进 prompt。

主脑必须能直接回答：

- 团队里有哪些职业成员
- 谁负责研究、谁负责执行、谁负责内容、谁负责运营
- 某件事应该优先找谁
- 某个成员能做什么，不能做什么

## 5.3 纯聊天态必须删除的 prompt 负担

纯聊天态默认不再注入：

- 执行型 system tool 详细说明
- delegation-first 规则
- 全量 capability mount 列表
- 全量 runtime/environment appendix
- 大段 evidence / schedule / task dump
- 重复 strategy payload
- 针对 `dispatch_query / delegate_task` 的操作说明

## 5.4 瘦身不是失忆

本方案明确反对两种极端：

1. 保留完整执行 prompt，导致聊天又慢又重
2. 什么都不注入，导致主脑连团队是谁都不知道

正确做法是：

- 保留“主脑理解局势所需的最小稳定上下文”
- 删掉“只有执行编排才需要的大段操作性上下文”

---

## 6. 记忆策略

## 6.1 纯聊天态保留记忆，但改成后端控制注入

纯聊天态不能因为关闭 `memory_search` 就变傻，所以要保留记忆，但记忆来源改成后端控制：

1. 稳定记忆
   - operator 偏好
   - 主脑长期使命
   - 已确认策略和约束
2. 运行记忆
   - 当前 cycle / lane / backlog / assignment / latest report 摘要
3. 对话记忆
   - 最近会话摘要
   - 未解决问题
   - 上一轮主脑给出的计划和用户反馈

### 6.2 纯聊天态默认不开放自由 `memory_search`

纯聊天态默认不向模型注册：

- `memory_search` tool
- memory compaction hook

如果确实需要更深历史记忆，应由后端在进入模型前先做受控检索，再把结果摘要注入 prompt，而不是让模型在纯聊天态自由发起 `memory_search`。

### 6.3 记忆注入的目标

目标不是“让模型知道所有历史”，而是保证它不在以下问题上失忆：

- 当前团队构成
- 最近几轮聊到了哪
- operator 的长期偏好
- 当前正在推进的核心事情

---

## 7. 可观测性与产品表现

## 7.1 工具 / 思考流不隐藏

保持以下原则不变：

- `thinking` 不默认隐藏
- `tool_use` 不默认隐藏
- `tool_result` 不默认隐藏

因为这关系到 operator 是否知道系统又在调用什么。

## 7.2 纯聊天态要靠“少调用工具”变干净，而不是靠“隐藏内容”变干净

纯聊天态的目标不是把工具流遮住，而是：

- 默认就不暴露不必要的工具
- 默认就不进入执行编排
- 因此自然减少 `dispatch_query / delegate_task / memory_search` 等输出

## 7.3 进入执行编排时要有显式标识

虽然仍然是同一个聊天窗口，但 UI 应让 operator 明确知道当前消息是：

- `纯聊天`
- 还是 `执行编排`

推荐形式：

- 顶部 mode pill
- 输入框旁 action chip
- 消息级别“本轮已进入执行编排”的状态条

---

## 8. 前后端拆链方案

## 8.1 API 拆链

建议正式拆成两条写入口：

1. `POST /api/runtime-center/chat/run`
   - 默认 `auto` 裁决入口（多数走纯聊天，必要时由主脑切到执行编排）
2. `POST /api/runtime-center/chat/orchestrate`
   - 显式执行编排入口

如果过渡期必须兼容单一路由，也至少要在请求层显式区分：

- `interaction_mode = auto`
- `interaction_mode = chat`
- `interaction_mode = orchestrate`

但最终目标仍应是两条物理链，避免后端继续偷偷共用同一执行 runtime。

## 8.2 后端服务拆链

不建议继续把纯聊天逻辑塞进 `KernelQueryExecutionService`。

建议新增轻量主脑聊天服务，例如：

- `MainBrainChatSurfaceService`

职责：

- 组装纯聊天 prompt
- 注入团队 roster 与受控记忆摘要
- 输出答复 / 澄清 / 建议执行编排

现有：

- `KernelTurnExecutor`
- `KernelQueryExecutionService`

只保留给执行编排链使用。

## 8.3 前端交互收口

前端需要做到：

- 默认发送走 `auto` 裁决入口
- 提供“一次性强制下一条执行编排”的覆盖入口
- 编排结束后自动回到 `auto` 默认态
- 不再把“普通发消息”偷偷当成执行编排入口

主改动面：

- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/index.tsx`
- `console/src/utils/runtimeChat.ts`
- `console/src/api/modules/runtimeCenter.ts`

## 8.4 执行链约束

执行编排链仍继续复用正式：

- kernel
- governance
- evidence
- state writeback

本方案不是要削弱正式治理，而是要把它从默认聊天里拿开。

---

## 9. 性能瘦身清单

纯聊天态至少要从以下 5 个方面减负：

### 9.1 Prompt 减负

- 删除执行工具说明
- 删除 delegation-first 规则
- 删除长 runtime appendix
- 删除全量 capability projection

### 9.2 迭代减负

- 纯聊天默认单轮回答
- 不走执行型 `max_iters`

### 9.3 Session 减负

- 不再加载执行 agent 的完整 resident session
- 不再每轮保存重型 execution session state

### 9.4 记忆减负

- 纯聊天态不挂 `memory_search`
- 不挂 memory compaction hook
- 记忆改成后端预取摘要

### 9.5 本地统计减负

- 纯聊天态不再承担执行链的本地 token 统计和多工具循环负担
- 必要的统计应改成轻量观测，不阻塞聊天响应

---

## 10. 迁移顺序

### 阶段 A：先拆契约

- 明确两种模式的 API 契约
- 前端默认只发纯聊天
- 新增显式进入编排的入口

### 阶段 B：落轻量主脑聊天服务

- 新建纯聊天 service
- 接入团队 roster 注入
- 接入后端控制记忆注入
- 去掉执行工具暴露

### 阶段 C：执行编排回到显式链

- 只有显式编排才进 `KernelTurnExecutor`
- 执行摘要回写同一聊天线程
- 聊天结束后回到纯聊天默认态

### 阶段 D：删旧与验收

- 删除或收紧纯聊天态下对执行 capability 的暴露
- 删除“默认聊天=执行 runtime”的旧假设
- 同步文档、测试和观测指标

---

## 11. 完成标准

以下条件必须同时满足，才算本方案完成：

- 默认聊天不再直接进入 `KernelTurnExecutor -> KernelQueryExecutionService`
- 纯聊天态不再暴露 `dispatch_active_goals / dispatch_goal / dispatch_query / delegate_task`
- 纯聊天态 prompt 中明确包含团队职业成员 roster
- 主脑能直接回答“团队里谁是谁、各自做什么、能力范围是什么”
- 纯聊天态默认不注册 `memory_search`
- 纯聊天态默认不挂 memory compaction hook
- `thinking / tool_use / tool_result` 不被前端默认隐藏
- 纯聊天态普通短聊不再频繁出现 `dispatch_query / delegate_task / memory_search`
- 执行编排仍保留正式 kernel / governance / evidence 主链
- 执行编排结果会回到同一主脑聊天线程
- 日报 / 周报现有页面链保持不受影响

性能验收至少要补一条正式 benchmark：

- 在同机同模型下，纯聊天态短消息基准的首 token 和完整回复耗时，必须显著优于当前执行编排链
- 目标口径：不再出现“普通聊天动辄几分钟”的默认体验

---

## 12. 本轮额外补充的 4 个必须项

除用户已明确提出的要求外，本方案额外补上 4 个必须项，避免后面再留下尾巴：

1. 显式升级契约
   - 主脑什么时候只能继续聊天，什么时候可以建议进入编排，必须写死。
2. 受控记忆注入
   - 解决“关闭 memory_search 会不会变傻”的问题。
3. 工具流可见性政策
   - 明确不是隐藏，而是减少默认误调用。
4. 性能验收基准
   - 否则后面又会变成“感觉快了一点”但没有硬标准。

---

## 13. 一句话结论

这次不是“把默认聊天的执行 prompt 再调温柔一点”，而是：

> 让主脑聊天前台默认回到真正的沟通与判断链，保留团队认知与受控记忆；只有在显式进入执行编排后，才开放派工、调度、写回和正式执行能力。
