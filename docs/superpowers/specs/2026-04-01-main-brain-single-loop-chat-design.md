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

## Reference Model From `cc`

`cc` 在“聊天主链怎么跑”这件事上是更好的参考，但不能整套照搬。

可直接借鉴的原则包括：

- 默认直接进入主查询循环，而不是先跑一轮业务前门分类
- 是否回复、追问、调能力、继续执行，默认由主模型自己决定
- classifier 主要放在 risk / permissions 边界，而不是每条普通聊天前
- system prompt 明确拆成静态可缓存前缀和动态尾部
- user/system context 使用会话级缓存
- tool summary 等次要工作后移，不阻塞下一次主调用

不能直接照搬的部分包括：

- Anthropic 专有 API 形态
- `cache_control`、provider beta header、`CLAUDE.md` 专属机制
- `cc` 的产品线程组织与 CoPaw 单窗口产品约束不一致的交互

因此，CoPaw 的正确落地方式不是“复制 `cc`”，而是：

`用 cc 的单环主脑原则重写 CoPaw 的聊天主链，再把正式提交链保留在 CoPaw kernel 内。`

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
      | "request_governance_confirmation"
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

1. 普通聊天链只打一轮主脑模型
2. 前端发送前不再阻塞 `getActiveModels()`
3. `resolve_chat_writeback_model_decision(...)` 不再处于普通聊天主路径
4. `MainBrainChatService` 首环 prompt 构建不再每轮全量重建 truth-first memory
5. writeback / summary / 次级整理不阻塞首 token
6. 全系统仍只有一个聊天窗口，不新增第二线程产品
7. `commit_action` 仍通过 kernel/governance 正式提交
8. `confirm` 动作在当前窗口回流，不要求跳出当前聊天产品

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
