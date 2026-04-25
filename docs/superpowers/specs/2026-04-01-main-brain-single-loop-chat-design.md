# Main Brain Single-Loop Chat Design

## Goal

在不破坏 CoPaw 正式主脑边界的前提下，把聊天前台改造成接近 `cc` 体感的单环主脑体验：

- 用户前台永远只有一个聊天窗口
- 默认直接和主脑说话
- 普通聊天首环只打一轮主脑模型
- 是否回复、追问、建议执行、正式提交动作，默认都由主脑自己决定
- 只有风险确认、正式确认边界、或明确的人类协作节点，才需要人介入

一句话目标：

`像 cc 一样快地直接和主脑说话，但 CoPaw 的 writeback / backlog / assignment / governance 仍由 kernel 正式提交。`

## Problem

当前 CoPaw 聊天链路的核心问题不是模型本身，而是默认聊天路径太重。

当前主要慢点包括：

- 前端发送前会阻塞式检查 active model
- 默认请求固定带 `interaction_mode=auto`
- `auto` 模式下会先跑 main-brain intake contract
- intake contract 里又会额外触发一次聊天 writeback 模型决策
- 真正进入主脑纯聊天后，还会每轮重建较重的 prompt context 和 truth-first memory context
- 一些 writeback / summary / 次级整理仍然处在首 token 之前或与首 token 强耦合

这条路径让“普通主脑聊天”被错误地当成“执行治理前门”处理。

## Product Constraints

本设计的非谈判约束如下：

### 1. 全系统只有一个聊天窗口

- CoPaw 前台永远只保留一个主脑聊天窗口
- 不允许再次出现第二聊天产品、执行子聊天、`task-chat:*` 前台线程
- 后台可以继续存在 `Assignment / Task / Report / Evidence`，但它们只能作为侧边读面、状态卡、时间线和详情入口回流到这一个窗口

### 2. 默认由主脑自己决定

- 正常逻辑下，主脑自己决定本轮是继续回复、追问、建议动作，还是提交正式动作
- “主脑判断不了时问人”要收窄成“主脑信息不足时在当前窗口追问澄清”
- 不再由聊天前门或人工路由器代替主脑做普通消息分流

### 3. 只有风险问题才需要人

- 人只在 `confirm` 风险档介入
- `guarded` 不是人工批准档，而是内核带守护执行档
- 聊天要不要继续、要不要追问、要不要建议下一步，不需要人工参与

### 4. 必须满足的 5 条性能硬约束

1. 去掉普通聊天前那次额外模型判定
2. 前端发送前不再阻塞等 model precheck
3. 主脑 prompt 改成 `稳定前缀 + 动态尾部`，做 session 级缓存
4. truth-first memory 改成 `scope snapshot + 增量刷新`，不能每轮全量重建
5. writeback / summary / 次级整理后移，不阻塞首 token

### 5. 不破坏正式主脑边界

- CoPaw 正式主链仍是
  `writeback -> backlog -> cycle -> assignment -> report -> replan`
- 主脑文本不允许直接改状态
- 正式写回、治理、恢复、任务物化仍由 kernel 二阶段提交

## Runtime Mainline Principles

这条聊天主链应采用单环主查询，但不能整套复制外部产品前门。

直接保留的原则包括：

- 默认直接进入主查询循环，而不是先跑一轮业务前门分类
- 是否回复、追问、调能力、继续执行，默认由主模型自己决定
- classifier 主要放在 risk / permissions 边界，而不是每条普通聊天前
- system prompt 明确拆成静态可缓存前缀和动态尾部
- user/system context 使用会话级缓存
- tool summary 等次要工作后移，不阻塞下一次主调用

明确不保留的部分包括：

- Anthropic 专有 API 形态
- `cache_control`、provider beta header、`CLAUDE.md` 专属机制
- `cc` 的产品线程组织与 CoPaw 单窗口产品约束不一致的交互

因此，CoPaw 的正确落地方式是：

`用单环主脑原则重写 CoPaw 的聊天主链，再把正式提交链保留在 CoPaw kernel 内。`

## Proposed Architecture

### 1. Single Front Door

前台正式写入口保持单一：

- `POST /api/runtime-center/chat/run`

禁止：

- 重新引入第二聊天入口
- 恢复旧的 `chat/intake` 前门作为默认链
- 让“普通发消息”先跳到另一个任务聊天线程

### 2. Lightweight Turn Routing

`KernelTurnExecutor` 继续存在，但只保留极轻规则，不再承担重聊天前门职责。

它只允许在以下情况做直接路由判断：

- 请求显式带 `requested_actions`
- 当前存在待确认的正式治理对象
- 当前存在明确 resume / human-assist / recovery 语义
- 明确的“下一条强制执行编排”覆盖入口

其余情况：

- 默认直接进入主脑单环聊天链

这意味着：

- 普通消息不会再先跑额外 intake 模型判定
- 普通消息不会再因“像任务”而提前物化线程

### 3. Main Brain Single Loop

主脑首环必须退化成一条真正轻量、直出的流式主链。

首 token 前允许保留的步骤只有：

- session cache 读取
- scope snapshot 读取
- 极轻规则分流
- 流式主脑调用本身

首 token 前禁止保留的步骤包括：

- 普通聊天前额外模型判定
- 全量 truth-first profile + lexical recall 重建
- durable writeback 正式提交
- 次级 summary / 整理 / 补充写回
- 提前创建任务线程或前台跳线程

### 4. Turn Result Contract

主脑每一轮都输出一个正式 `MainBrainTurnResult`。

建议形态：

```ts
type MainBrainTurnResult = {
  reply_text: string
  action_envelope: {
    version: "v1"
    kind: "reply_only" | "suggest_action" | "commit_action"
    summary: string | null
    action_type:
      | "none"
      | "orchestrate_execution"
      | "writeback_operating_truth"
      | "create_backlog_item"
      | "resume_execution"
      | "submit_human_assist"
    risk_hint: "auto" | "guarded" | "confirm" | null
    payload: Record<string, unknown> | null
  }
}
```

语义说明：

- `reply_only`
  - 只回复，不提交正式动作
- `suggest_action`
  - 主脑建议下一步动作，但不直接提交
- `commit_action`
  - 主脑已经决定要做动作，交给 kernel 做正式裁决和提交

payload 约束：

- `orchestrate_execution`
  - 至少包含：
    - `goal_summary`
    - `requested_surfaces`
    - `continuity_ref` 或 `work_context_id`
    - `operator_intent_summary`
- `writeback_operating_truth`
  - 至少包含：
    - `target_kind`
    - `summary`
    - `facts`
    - `source_refs`
- `create_backlog_item`
  - 至少包含：
    - `lane_hint`
    - `title`
    - `summary`
    - `acceptance_hint`
    - `source_refs`
- `resume_execution`
  - 至少包含：
    - `resume_target_kind`
    - `resume_target_id`
    - `continuity_ref`
    - `resume_reason`
- `submit_human_assist`
  - 至少包含：
    - `task_type`
    - `request_summary`
    - `acceptance_anchors`
    - `continuity_ref`

补充规则：

- `payload` 缺关键字段时，kernel 只能把该 envelope 退化成 `suggest_action` 或要求主脑补充澄清，不能盲提交
- 正式 risk decision 不信任 `risk_hint`，只能把它当主脑建议值
- `writeback_operating_truth.target_kind` 不是任意字符串，当前只允许映射到正式 canonical targets：
  - `strategy_memory`
  - `operating_lane`
  - `backlog_item`
- 如需写入其他对象，必须通过显式新增 action type 或显式 kernel capability，而不是把 `writeback_operating_truth` 扩成万能写入口

### 5. Two-Phase Commit For Formal Side Effects

CoPaw 不应把“单环主脑体验”做成“单环直接提交所有副作用”。

正式落地必须是：

- 第一阶段：主脑单环决策
  - 产出 `reply + action_envelope`
- 第二阶段：kernel 正式提交
  - 校验 payload
  - 风险裁决
  - 能力/环境可执行性检查
  - state / evidence / governance 正式提交

这样可以同时得到：

- 接近 `cc` 的首响应体验
- CoPaw 正式主链的可审计、可重放、可治理边界

phase-2 传输契约：

- canonical 方案是：
  - `chat/run` 在同一条流里先发送 reply token
  - reply 完成后，在同一条流里继续发送结构化 sidecar events
- 不再把二阶段结果放到另一条聊天链或另一个前台线程里
- 同流 sidecar event 建议至少包含：
  - `turn_reply_done`
  - `commit_started`
  - `confirm_required`
  - `committed`
  - `commit_failed`
  - `commit_deferred`
- 若同一条流已结束，但后台提交还未完成：
  - canonical 后续读面仍回到当前 control thread / conversation record
  - 不允许新开第二聊天窗口承接提交结果
  - 前端可通过当前线程的后续状态事件或正式读面刷新，继续在同一窗口渲染结果
- 规划和实现必须以“同流 sidecar + 同线程后续回流”为唯一正式模式，不再发明第二套 transport

二阶段提交结果要求：

- 第一阶段一旦开始对用户流式回复，就视为“主脑已形成一轮正式聊天结果”
- 第二阶段只负责处理 `commit_action`，不能反向改写已输出的回复正文
- 第二阶段的成功、失败、待确认、待补充信息，都必须回流到当前唯一聊天窗口

二阶段失败语义：

- `payload_invalid`
  - kernel 发现缺字段、字段非法、目标对象不存在
  - UI 回流为“提交失败：动作描述不完整或目标无效”
  - 不重放主脑回复正文
  - 允许主脑在下一轮补充 envelope 或退化成 `suggest_action`
- `governance_denied`
  - kernel/governance 明确拒绝本次提交
  - UI 回流为“未提交：治理拒绝”
  - 必须展示拒绝原因和建议下一步
- `confirm_required`
  - 风险裁决升级到 `confirm`
  - UI 回流为“待确认”
  - 不得把动作标成已提交
- `environment_unavailable`
  - 所需 surface / continuity / session mount 不可用
  - UI 回流为“暂不能执行”
  - 应提示可选恢复路径，例如 `resume`、`rebind`、`handoff`
- `idempotent_replay`
  - 用户或系统重试同一 `commit_action`
  - kernel 必须基于 idempotency key 或等价 continuity key 识别重复提交
  - 对已成功提交的动作，不得重复物化第二份正式对象

二阶段回流规则：

- 所有失败和待确认结果都必须作为当前窗口内的状态卡/时间线事件回流
- 失败不会创建第二聊天线程
- 失败不会把用户强制带离当前控制线程
- 若失败可恢复，应给出明确的下一步类型：
  - `retry`
  - `confirm`
  - `resume`
  - `clarify`
  - `handoff`

幂等要求：

- `commit_action` 必须带可稳定推导的提交键，优先复用：
  - `control_thread_id`
  - `session_id`
  - `work_context_id`
  - `continuity_ref`
  - `action_type`
- kernel 对正式写回和任务物化必须提供“重复提交不重复落库”的保证

## Risk Model

风险判断不再放在聊天前门，而放在 `commit_action` 提交前。

### `auto`

- 主脑已决定，kernel 直接提交
- 典型场景：
  - 普通回复
  - 低风险 operating truth 写回
  - 创建 backlog
  - 创建 human-assist 任务
  - 无风险 resume

### `guarded`

- 主脑已决定，kernel 带守护执行
- 典型场景：
  - 低风险宿主读取
  - 低风险 browser/desktop/file 读面动作
  - 带 continuity 前提的恢复

说明：

- `guarded` 不需要人工批准
- 它只是由 kernel 增加守护条件和观测要求

### `confirm`

- 主脑已决定动作方向，但提交前必须由人确认
- 典型场景：
  - 资金类动作
  - 不可逆外部动作
  - 敏感账号动作
  - 高风险真实发送/发布/提交
  - 删除、转移、覆盖关键数据

原则：

- 人只拦动作，不拦思考
- 风险判断基于正式 capability / environment / mutation facts，而不是聊天关键词
- `confirm` 的 canonical authority 只属于 kernel/governance
- 模型不再单独产出“request governance confirmation”作为第二条确认主链
- 模型只负责表达意图动作；kernel/governance 决定该动作最终是 `auto`、`guarded` 还是 `confirm`
- 当 kernel 把某个 `commit_action` 升格为 `confirm` 时，前端只渲染同一个动作的 `confirm_required` 状态，而不是重新造第二种 action type

## Prompt And Cache Architecture

### 1. Stable Prefix

主脑 prompt 必须拆成稳定前缀和动态尾部。

稳定前缀应包括：

- 主脑身份
- 单窗口产品约束
- 主脑职责边界
- 行业/角色/运行中心稳定事实
- 输出契约说明

缓存粒度：

- session 级
- 或 `session + user + stable_context_signature`

失效条件：

- 主脑身份或角色变化
- 行业实例切换
- 主脑职责约束变化
- 相关正式配置版本变化

### 2. Scope Snapshot

truth-first memory 不再每轮构建完整 profile + lexical recall，而是读取一个受控的 scope snapshot。

scope 优先级：

`work_context > task/runtime continuity > industry > agent > global`

snapshot 建议包含：

- 当前焦点摘要
- 活跃约束
- 最新关键事实
- 最近历史事实
- 建议下一步
- 支撑 refs

要求：

- snapshot 是派生读面，不是新真相源
- 它必须来自正式 truth-first memory / activation / reporting / evidence 链

owner 建议：

- `MainBrainChatService` 不负责自己拼装 snapshot
- 正式 owner 应为独立的派生读面服务，例如 `MainBrainScopeSnapshotService`
- 该服务负责从：
  - truth-first memory recall
  - knowledge activation
  - reporting / synthesis
  - continuity / recovery state
  派生出单一 snapshot payload
- `MainBrainChatService` 只消费该服务结果，不再自己散着拼 profile、latest facts、history、lexical recall

### 3. Dynamic Tail

动态尾部只保留每轮真正变化的内容：

- 当前用户消息
- 最近少量对话历史
- 当前 turn 的 continuity / recovery / assist state
- 当前 turn 必要的可见 runtime facts

### 4. Incremental Refresh

scope snapshot 只能增量刷新，不能每轮全量重建。

建议触发条件：

- scope 变化
- 正式 writeback 成功
- report closure / synthesis 成功
- media analysis adopt / retain 成功
- resume / recovery 状态变化

刷新策略建议：

- 默认读取策略：
  - 先读内存缓存
  - 命中则直接进入主脑首环
  - 未命中或已失效时，才触发同步快照构建
- 默认 refresh 规则：
  - 同一 `work_context` 的短时连续聊天，优先复用最近 snapshot
  - scope 未变且没有正式状态变更时，不主动刷新
  - 正式 writeback / report synthesis / recovery state 变化后，异步标记相关 scope dirty
  - 下一轮命中 dirty scope 时，做一次增量重建并回填缓存

## Deferred Work

以下工作必须从首 token 主路径中后移：

- durable writeback 正式提交
- summary / 次级整理
- 补充性 truth sync
- 辅助 notice 和非关键 UI 摘要
- 非必要的 follow-up materialization

这些动作可以发生在：

- 首 token 之后
- 主脑回复完成之后
- 或二阶段提交完成之后

但不能卡住主脑起流。

## Single-Window UX Contract

由于 CoPaw 前台只有一个聊天窗口，所有正式动作结果都必须回流到当前窗口。

允许的回流形式：

- 回复正文
- “主脑已决定”状态卡
- “已提交 / 待确认 / 已恢复 / 已写回”状态条
- assignment / report / evidence / human-assist 详情卡
- 侧栏详情、时间线、可点击读面
- reply 结束后的 sidecar commit 事件

禁止的回流形式：

- 第二聊天窗口
- task-chat 前台线程
- 需要用户跳到另一种聊天产品里继续

## Reuse Map

### Directly Reusable Patterns

- 单环主脑入口
- risk-only classifier 边界
- prompt 静态/动态拆分
- session 级上下文缓存
- 次级 summary 后移
- 并行而非串行的上下文加载

### Reuse With Adaptation

- 流式主响应 + 末尾结果 sidecar
- 轻量上下文预取
- 动作决定与回复同轮产出

适配点：

- 必须映射回 CoPaw 的 kernel / state / evidence / governance
- 必须符合单窗口产品约束

### Must Not Reuse Directly

- Anthropic 专有调用细节
- provider-specific cache headers
- `CLAUDE.md` 机制
- `cc` 的多线程/执行交互心智

## Migration Surface

本设计的首批代码触点预计包括：

### Frontend

- `console/src/pages/Chat/runtimeTransport.ts`
  - 移除发送前阻塞式 model precheck
  - 保留必要的失败提示，但不阻塞默认发送
- `console/src/pages/Chat/runtimeTransportRequest.ts`
  - 保持单一 `chat/run` 主入口
  - 仅在显式入口时附加 `requested_actions`

### Backend

- `src/copaw/kernel/turn_executor.py`
  - 把 `auto` 收缩成极轻规则路由
- `src/copaw/kernel/main_brain_intake.py`
  - 移除普通聊天前额外模型决策的现役职责
- `src/copaw/kernel/query_execution_writeback.py`
  - 停止普通聊天主路径上的 writeback model decision
- `src/copaw/kernel/main_brain_chat_service.py`
  - 改成单环主脑主链
  - 加入稳定前缀缓存
  - 加入 scope snapshot 缓存
  - 输出 `action_envelope`

### Supporting Services

- truth-first memory / activation 相关派生读面
  - 提供 scope snapshot
- kernel / governance
  - 提供 `commit_action` 二阶段提交

## Deletion And Retirement

本设计要求明确删旧，而不是只叠新层。

需要退役或降级的现役逻辑包括：

- 普通聊天前的额外 intake model decision
- 发送前依赖 active model precheck 才允许发消息的逻辑
- “像任务就先拆线程”的前门心智
- 把 durable writeback 当成聊天前分类问题的逻辑

删除完成的判断标准：

- 普通聊天链首环只打一轮主脑模型
- 不再存在第二聊天产品
- 正式写回只来自 kernel 二阶段提交

## Acceptance Criteria

本设计的完成验收不使用“感觉快了”，而使用以下正式条件：

1. 纯聊天场景下，首 token 前主路径只允许一次主脑模型调用；普通聊天链不得再触发前置 intake 模型判定。
2. 前端默认发送链不再阻塞 `getActiveModels()` 成功返回；即使模型检查失败，发送链也必须先进入后端正式请求，由后端给出权威错误。
3. `resolve_chat_writeback_model_decision(...)` 不再处于普通聊天主路径；它若保留兼容边界，也只能出现在非默认链或已退役兼容壳中。
4. `MainBrainChatService` 首环 prompt 构建必须消费稳定前缀缓存和 scope snapshot；同一 `work_context` 的短时连续聊天不得每轮全量重建 truth-first profile + lexical recall。
5. writeback / summary / 次级整理不得阻塞首 token；它们只能发生在首 token 之后、回复完成后，或二阶段提交中。
6. 全系统仍只有一个聊天窗口；真实任务创建后只允许以状态卡、时间线和详情入口回流，不能出现第二聊天线程产品。
7. `commit_action` 只能经 kernel/governance 正式提交；主脑回复正文不能直接改 state。
8. `confirm` 动作必须先在当前窗口出现治理确认 UI，确认完成后才能提交；未确认前不得把动作标记为已提交。
9. 二阶段提交失败时，当前窗口必须能区分至少以下状态：`提交失败`、`治理拒绝`、`待确认`、`暂不能执行`；且失败不会重复物化正式对象。
10. 对同一 `commit_action` 的重复提交，kernel 必须保证幂等，不得因为 retry 产生重复 backlog / assignment / human-assist / writeback 记录。

## Validation Plan

### Unit

- `action_envelope` 结构和语义测试
- risk decision 测试
- scope snapshot 命中 / 失效 / 刷新测试

### Integration

- 普通聊天只走单环主脑
- `commit_action` 走 kernel 二阶段提交
- `confirm` 动作在同一窗口回流
- resume / human-assist / recovery 在单窗口语义下保持可用

### Frontend

- `chat/run` 成为唯一正式发送链
- 发送前不再阻塞 model precheck
- 不再跳第二聊天线程
- 状态卡 / 提交结果 / 确认结果回流到当前窗口

## Final Decision

本设计的最终落点不是“继续把前门分类器调聪明”，而是：

`把 CoPaw 聊天前台重写成类似 cc 的单环主脑体验，让主脑默认自己决定回复和动作，再把正式副作用交给 kernel 二阶段提交。`
