# CHAT_RUNTIME_ALIGNMENT_PLAN.md

> `2026-03-22` 更新说明
>
> 本文档仍然有效的部分是：
>
> - 删除 `/chat` 前面的 frontdoor 分类器
> - 删除 task-thread 前置拆分
> - 把宿主观察、writeback、风险边界下沉到 runtime / governance
>
> 但本文档中“`/chat` 默认应直接进入统一执行主链”的假设，已被
> `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md`
> 正式修正为：
>
> - 默认 `/chat` 进入主脑纯聊天链
> - 只有显式进入时，才进入执行编排链
>
> 后续如两份文档有冲突，聊天入口与模式拆链以
> `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md` 为准。
>
> `2026-04-12` 代码核对修正：
>
> - `task-chat:*` 已不再是正式前台导航目标，也不是 `RuntimeConversationFacade` 的正式会话 id。
> - 前台正式聊天线程现在收口为主脑控制线程 `industry-chat:*`；`agent-chat:*` 与 `task-chat:*` 最多只应被理解为后台/兼容 artifact。
> - 下文残留 `task-chat:*` 相关内容，如未显式改写为“后台 artifact / 历史规划”，都应按历史背景理解。

## 0. 文档目的

本文件用于定义 `/chat` 从“执行前门 + 任务线程预拆分 + 聊天治理混合入口”重构为“单聊天窗口 + 单 turn 主链 + 工具层显式边界”的完整改造方案。

这不是一个“前端加模式切换按钮”的方案。

目标是：

- 保留单聊天窗口体验
- 让模型在默认主链里自行判断“回复”还是“直接做事”
- 把审批、沙箱、宿主观察、真实外部动作、durable writeback 等边界下沉到工具/runtime 层
- 删除当前 `/chat` 入口前面的业务型 frontdoor 分类器

---

## 1. 结论来源

本方案基于两部分事实：

1. 本仓库当前 `/chat` 主链源码现状
2. 对 `openai/codex` 开源源码的本地审查结论

审查基线：

- `openai/codex` 提交：`32d2df5c1e97948cb5c55481f0b5fd3f8dfabf43`

关键结论：

- Codex 默认不是“先做业务前门分类，再决定是否执行”
- Codex 是“单 turn loop + 默认直接执行倾向 + tool approval/sandbox/runtime 硬边界”
- Codex UI 只有一个聊天窗，但“是否真的做了事”是事后按实际 tool/patch/command 结果标注，不是事前把消息路由成 `chat` 或 `task`

对 CoPaw 的含义：

- 不能再把 `/chat` 的默认主链建立在 `ChatFrontdoorDecision` 这种单独的治理前门上
- 不能再依赖 `/runtime-center/chat/intake -> prepare_chat_turn -> plan_chat_task_thread` 这种 pre-send 路由
- 也不能继续把 `status chat / writeback / kickoff / policy-change / risky actuation / host observation` 全塞进一个 frontdoor 结构化判定器里

---

## 2. 当前问题定义

当前 `/chat` 的主要问题不是“模型不够聪明”，而是入口架构错了。

当前链路是：

1. 前端先发 `/api/runtime-center/chat/intake`
2. 后端 `KernelTurnExecutor.prepare_chat_turn()` 先调用 `plan_chat_task_thread()`
3. `KernelQueryExecutionService.plan_chat_task_thread()` 先跑 `ChatFrontdoorDecision`
4. frontdoor 决定这条消息是 `chat / discussion / status-query / execute-task`
5. frontdoor 还同时决定：
   - `host_observation_requested`
   - `risky_actuation_requested`
   - `kickoff_allowed`
   - `should_writeback`
   - `query_confirmation_policy_change`
   - `team_role_gap_action`
6. 这条历史设计里，如果是执行型请求，前端会在真正开始流式执行前先导航到 `task-chat:{task_id}`；当前活代码已不再这样做。

这条链的问题有 4 个：

### 2.1 聊天和治理被耦死

一句普通的“你现在在干嘛”会被塞进 execution-core 治理前门，而不是直接进入主模型 turn。

### 2.2 任务线程创建过早

当前 task thread 不是“实际创建了任务后出现”，而是“用户刚发消息，前门判定像任务，就先拆线程”。

### 2.3 durable writeback 被前置成消息分类问题

当前 `strategy / backlog / schedule` 写回不是由模型在 turn 中显式调用工具，而是由 frontdoor 在执行前猜测并 materialize。

### 2.4 宿主观察边界不干净

当前 host observation 是在 frontdoor 层做限制补丁，而不是 runtime 层的正式显式边界。

---

## 3. 架构落位

这次改造的落位如下：

- 所属层：`kernel / app runtime ingress / evidence / frontend runtime center`
- 单一真相源：`state + evidence`
- 是否绕过统一内核：否
- 是否新增能力语义分裂：否
- 会产生的证据：
  - turn work summary
  - tool call evidence
  - host observation grant/use evidence
  - writeback evidence
  - task creation evidence
- 计划替换/删除的旧代码：
  - `/runtime-center/chat/intake`
  - `KernelTurnExecutor.prepare_chat_turn()`
  - `plan_chat_task_thread()`
  - `ChatFrontdoorDecision`
  - `_CHAT_WRITEBACK_MODEL_SYSTEM_PROMPT`
  - `/chat` pre-send task-thread redirect

---

## 4. 目标状态

### 4.1 单窗口，不加“聊天/执行”模式切换

最终产品仍然只有一个聊天窗口。

用户不需要先点“聊天模式”或“执行模式”。

### 4.2 默认 turn 直通主执行链

`/chat` 默认请求应直接进入统一 runtime turn 执行主链，而不是先走单独 intake frontdoor。

### 4.3 模型判断发生在主 turn 内，不发生在独立前门里

是否回复、是否直接做事、是否需要调用工具，应该由主模型在当前 turn 中判断。

### 4.4 风险和权限在工具层处理

真正的边界应该是：

- 能不能写文件
- 能不能跑命令
- 能不能看宿主实时窗口
- 能不能做浏览器/桌面真实外部动作
- 能不能写 durable operating truth

这些都应该在 tool/runtime/governance 层显式处理。

### 4.5 task thread 是结果，不是入口

只有当 turn 里真的创建了正式任务、派发了后台执行或 materialize 了 task object，后台/兼容层才可能残留 `task-chat:{task_id}` 一类 artifact；前台不应再把它当正式聊天入口。

---

## 5. 5 条硬规则

### 5.1 默认聊天路径直通 `chat/run`

`/chat` 默认不再依赖 `/chat/intake`。

### 5.2 不再保留独立 chat frontdoor 分类器

不得再让 `intent_kind / task_thread_allowed / writeback_allowed / kickoff_allowed` 这类业务前门结果决定 turn 是否进入执行主链。

### 5.3 宿主观察必须是显式边界

桌面/窗口/前台页面/当前屏幕这类 live observation 不得因为一句普通状态聊天而自动触发。

### 5.4 durable writeback 必须显式调用

写入 `strategy / lane / backlog / schedule` 不再由 intake/frontdoor 猜测，必须经显式 system tool/governance 动作完成。

### 5.5 task thread 只能从真实任务产生

task thread 只能来自真实 `Task / TaskRuntime / dispatch_query / assignment / background chain` 的创建结果，不能来自 pre-send 路由判断。

---

## 6. 完整改动范围

## 6.1 前端 `/chat`

必须改动：

- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/index.tsx`
- `console/src/api/modules/runtimeCenter.ts`
- `console/src/utils/runtimeChat.ts`
- `console/src/pages/Chat/chatPageHelpers.tsx`

必须完成的动作：

- 删除前端对 `prepareRuntimeChatTurn()` 的默认依赖
- 删除“先 intake，再决定是否切去 task thread”的 pre-send 路径
- 让聊天页默认只向 `POST /api/runtime-center/chat/run` 发请求
- 保留当前“单输入框 + media_inputs/media_analysis_ids”契约，不回退到独立参考材料工作流
- 保留 task panel，但改为“本轮产生任务后再展示/跳转”
- 把“创建任务 / durable writeback / inspect host”做成可选显式动作入口，而不是全局模式切换

显式动作入口形式允许为：

- 输入框 action chip
- slash command
- compose panel 小按钮

但不得做成：

- 全局 `聊天模式 / 执行模式` toggle

## 6.2 Runtime chat API

必须改动：

- `src/copaw/app/routers/runtime_center_routes_core.py`
- `src/copaw/app/routers/runtime_center_shared.py`

必须完成的动作：

- 删除 `/api/runtime-center/chat/intake`
- `POST /api/runtime-center/chat/run` 成为聊天页唯一正式写入口
- `run` 顶层请求允许带可选 `requested_actions`
- `requested_actions` 只是显式 hint，不是必填，也不是模式切换

建议的 `requested_actions` 语义：

- `inspect_host`
- `create_task`
- `writeback_strategy`
- `writeback_backlog`
- `writeback_schedule`

这些 hint 的作用是：

- 给 UI 一个无歧义入口
- 给 runtime 一个正式边界
- 但不替代主模型在自然语言上的判断

## 6.3 `KernelTurnExecutor`

必须改动：

- `src/copaw/kernel/turn_executor.py`

必须完成的动作：

- 删除 `prepare_chat_turn()`
- 删除该函数对 `plan_chat_task_thread()` 的依赖
- 默认 turn 不再改写 `session_id -> task-session:*`
- 默认 turn 不再在执行前制造 `task_id / task thread / control_thread_id` 跳转结果

保留项：

- `stream_request()`
- `handle_query()`
- kernel-owned stream wrapping

如果还需要“显式创建任务线程”能力，应拆成新的正式动作，而不是复用旧的 `prepare_chat_turn()` 兼容壳。

## 6.4 Query execution 主链

必须改动：

- `src/copaw/kernel/query_execution_shared.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/query_execution_team.py`
- `src/copaw/kernel/query_execution_prompt.py`
- `src/copaw/kernel/query_execution_tools.py`

必须删除或退役的内容：

- `ChatFrontdoorDecision`
- `_CHAT_WRITEBACK_MODEL_SYSTEM_PROMPT`
- `_resolve_chat_frontdoor_decision()`
- `plan_chat_task_thread()`
- `task_thread_allowed`
- `intent_kind` 作为 pre-send 路由结果
- `query_confirmation_policy_change` 作为 frontdoor 聊天分类字段

必须保留但要改成显式动作的内容：

- risky actuation confirmation
- durable writeback
- team role gap approve/reject
- host observation

新的承载方式应为：

- 主模型在 turn 中决定是否调用 system tool
- system tool 进入 kernel admission / governance / evidence
- tool/runtime 再决定 `auto / guarded / confirm`

而不是：

- frontdoor 先把消息分类
- runtime 再被动执行分类结果

## 6.5 宿主观察边界

必须改动：

- `src/copaw/kernel/query_execution_team.py`
- 相关 system tool / capability handler

目标：

- `get_foreground_window`
- `list_windows`
- 当前页面/屏幕类 live observation

不再靠 frontdoor 的 `host_observation_requested` 控制。

正式方案：

- observation tool 默认受 turn-scoped grant 约束
- grant 来源只能是：
  - operator 显式 action hint
  - 或模型在 turn 内调用专门的 host-observation grant tool
- grant 与实际 observation 都要留 evidence

这样做的边界是：

- 不需要前端模式切换
- 也不需要独立前门模型
- 但“你在干嘛”不会再直接拉起窗口观察

## 6.6 durable writeback

必须改动：

- `src/copaw/industry/chat_writeback.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/kernel/query_execution_runtime.py`

目标：

- `strategy / lane / backlog / schedule` 写回不再由 frontdoor 预分类触发
- 改为显式 system tool 或 formal action

建议承载：

- `system:writeback_operating_truth`
- `system:create_backlog_item`
- `system:create_schedule`
- `system:update_strategy_memory`

保留现有 materializer，但只让它消费显式结构化 payload，不再消费原始聊天文本。

## 6.7 任务线程与 conversation facade

必须改动：

- `src/copaw/kernel/chat_threads.py`
- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/app/runtime_center/state_query.py`
- `console/src/utils/runtimeChat.ts`

目标：

- 保留 `control thread` 作为正式读模型；`task thread` 如仍存在，也只能作为后台/兼容读痕迹
- 删除“任务线程优先于执行”的入口语义
- task thread 只能由真实任务创建反推

新的语义应为：

- control thread：主脑/执行中枢对话面
- task thread：如果仍出现，只能解释为已经存在正式任务后的后台/兼容工作线程，不是前台可切换聊天页
- chat 页面里的 task list：从实际 task metadata/evidence 派生

而不是：

- control thread 发消息
- intake 判断像任务
- 先拆线程
- 再执行

## 6.8 Prompt 与默认行为

必须改动：

- `src/copaw/kernel/query_execution_prompt.py`

目标：

- 把默认行为改成近似 Codex 的“合理假设 + 直接执行”
- 但保留 CoPaw 自己的风险治理边界

必须明确写进 prompt 的规则：

- 默认直接完成用户请求，不为普通执行请求额外征询确认
- 只有高风险、不可逆、真实对外变更才进入 `confirm`
- 不得因为挂载了 desktop/browser capability 就默认做 live observation
- 不得把普通状态聊天解释成需要查看宿主状态
- 如果真实任务已经开始、创建了 task 或 writeback，应在结果中显式说明

## 6.9 `/api/agent/process` 与 `/runtime-center/chat/run`

必须改动：

- `src/copaw/app/agent_runtime.py`
- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/api/modules/agent.ts`

目标：

- 聊天页正式只使用 `/api/runtime-center/chat/run`
- `/api/agent/process` 保留为低层 direct ingress/兼容入口，不再作为聊天页默认 API

这样做的好处：

- 前端只有一条正式聊天写主链
- media enrich / runtime-center surface / conversation semantics 不再分叉

## 6.10 测试

必须重写或删除的测试：

- `tests/kernel/test_turn_executor.py`
- `tests/kernel/query_execution_environment_parts/shared.py`
- `tests/kernel/query_execution_environment_parts/confirmations.py`
- `tests/kernel/query_execution_environment_parts/lifecycle.py`
- `tests/app/runtime_center_api_parts/overview_governance.py`
- `tests/app/runtime_center_api_parts/shared.py`

必须新增的测试主题：

- 普通状态聊天不会触发 host observation tool
- 明确执行请求可直接进入主 turn，不经 intake
- risky browser/desktop mutation 仍会进入 confirm
- durable writeback 只能来自显式 system action
- task thread 只在真实 task 创建后出现
- `/chat` 前端不再依赖 `/runtime-center/chat/intake`
- 单输入框媒体链在直通 `chat/run` 下保持可用

## 6.11 文档同步

至少同步：

- `TASK_STATUS.md`
- `API_TRANSITION_MAP.md`
- `RUNTIME_CENTER_UI_SPEC.md`
- `AGENT_VISIBLE_MODEL.md`

必要时同步：

- `docs/archive/root-legacy/REAL_ISSUES.md`
- `ARCHITECTURE_DECISIONS.md`

---

## 7. 删除清单

最终完成态必须物理删除：

- `POST /api/runtime-center/chat/intake`
- `prepareRuntimeChatTurn()`
- `KernelTurnExecutor.prepare_chat_turn()`
- `KernelQueryExecutionService.plan_chat_task_thread()`
- `ChatFrontdoorDecision`
- `_CHAT_WRITEBACK_MODEL_SYSTEM_PROMPT`
- chat frontdoor 相关 `intent_kind/status-query/task_thread_allowed` 预分类测试

允许存在的唯一过渡期是：

- 同一开发分支内前后端尚未一起落地时的短暂编译兼容

不允许：

- merge 后长期保留前后两套路径
- 保留 `chat/intake` 但说“前端先不用”
- 保留 frontdoor classifier 但说“以后再删”

---

## 8. 施工顺序

### 阶段 A：切默认聊天主链

- 前端移除 `chat/intake`
- `/chat` 统一直发 `chat/run`
- backend 删除 `prepare_chat_turn()`

### 阶段 B：把 durable action 改成显式 system tool

- host observation grant
- durable writeback
- task creation
- team role gap decision
- confirmation policy action

### 阶段 C：把 task thread 降级成结果面

- 若仍保留 task thread artifact，只允许由真实任务创建后回推，不能恢复成前台路由
- 重写 conversations/task list/query surfaces

### 阶段 D：删旧 + 文档 + 验收

- 删 frontdoor classifier
- 删旧测试
- 更新 UI/运行中心说明
- 补全 E2E

---

## 9. 完成标准

以下条件必须同时满足，才算这项工作完成：

- `/chat` 默认发送链只剩一条正式路径
- `/runtime-center/chat/intake` 已删除
- 普通状态聊天不再触发 live host observation
- 普通执行请求不再需要“先判定成任务线程”
- risky 外部动作仍然走 `auto / guarded / confirm`
- durable writeback 已转成显式 system action
- task thread 只会在真实任务创建后出现
- 单输入框 media 链保持工作
- 前后端 build/test 通过
- 相关文档已同步，不再把旧 frontdoor 叙事写成当前 canonical 主链

---

## 10. 一句话结论

这次不是“把 frontdoor 再调聪明一点”，而是：

> 彻底取消 `/chat` 默认主链前面的业务分类前门，让聊天直接进入统一 turn 执行内核，再把宿主观察、任务创建、durable writeback、风险确认全部改成工具层和治理层的显式边界。
