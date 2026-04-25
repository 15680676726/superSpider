# 最小可落地升级方案：控制线程 + 任务线程

本文档定义 `/chat` 从“单长会话壳”升级为“单前台指挥线程 + 多后台任务线程”的最小可落地版本，并作为本轮实现与验收基线。

---

## 1. 背景

当前仓库底层已经具备正式 `Task / delegation / mailbox / evidence / runtime conversation` 骨架，但聊天产品面仍偏向单线程长会话：

- 前台只有一个聊天入口是对的，但执行型请求仍和控制性对话混在同一线程里
- 执行中枢虽然已经成为唯一前台主脑，但没有正式“任务线程”容器承接拆出的执行请求
- 结果是：
  - 元对话会污染执行上下文
  - 长期任务缺少稳定的 task-scoped 会话入口
  - 控制线程看不到自己拆出去的任务链

本轮目标不是重写聊天系统，而是在不破坏现有 kernel/state 主链的前提下，把 `/chat` 收口到更接近真实执行系统的结构。

---

## 2. 开工前 6 问

### 2.1 这段代码属于哪一层

- `kernel/chat_threads.py`、`turn_executor.py`、`query_execution.py`：运行内核前门
- `app/runtime_center/conversations.py`、`state_query.py`、`routers/runtime_center.py`：正式读写/入口面
- `console/src/pages/Chat/*`：前台运行指挥面

### 2.2 接入哪个单一真相源

- 正式 `KernelTask`
- 正式 session snapshot
- 正式 `RuntimeConversationFacade`
- 正式 Runtime Center state query

### 2.3 是否绕过统一内核

- 不绕过
- 任务线程仍通过 `KernelTurnExecutor -> KernelDispatcher -> system:dispatch_query` 主链进入 kernel

### 2.4 是否增加新的能力语义分裂

- 不增加
- 只增加聊天线程身份语义：
  - `industry-chat:*` 作为控制线程
  - `task-chat:*` 作为任务线程别名

### 2.5 会产生什么证据

- 正式 kernel task
- 正式 task runtime / conversation history
- 任务线程在 Runtime Center 中可见

### 2.6 准备替换或删除哪段旧逻辑

- 逐步替换 `/chat` 的“单 thread 承载控制 + 执行全部语义”的旧产品行为
- 不再让执行型请求继续无边界污染控制线程

---

## 3. 目标形态

本轮最小版本只做 4 件事：

1. 前台仍保持一个可见主入口
   - 行业聊天默认仍进入 `Spider Mesh 执行中枢`
   - 不重新引入多个平级聊天脑

2. 执行型请求从控制线程拆出正式任务线程
   - 控制线程 id：`industry-chat:{instance_id}:execution-core`
   - 任务线程 id：`task-chat:{task_id}`
   - 真实运行 session：`task-session:{seed}`

3. 控制线程能看到自己拆出的任务线程
   - 通过 Runtime Center 正式读面列出当前控制线程下最近任务线程
   - Chat 左侧新增“任务线程”栏

4. 任务线程后续追问继续落在同一正式 task session
   - 不允许二次追问重新掉回控制线程或匿名 session

---

## 4. MVP 范围

### 4.1 后端

- 新增聊天线程身份辅助：
  - `src/copaw/kernel/chat_threads.py`
- 在 `KernelQueryExecutionService` 增加轻量 intake 规划：
  - 判断当前消息继续走控制线程，还是拆成任务线程
- 在 `KernelTurnExecutor` 增加 `prepare_chat_turn()`
  - 控制模式：原样继续
  - 任务模式：预先创建正式 kernel task，并返回 `task-chat` 线程信息
- Runtime Center 新增正式入口：
  - `POST /api/runtime-center/chat/intake`
  - `POST /api/runtime-center/chat/run`
  - `GET /api/runtime-center/chat/tasks`
- `RuntimeConversationFacade` 支持解析 `task-chat:{task_id}`

### 4.2 前端

- Chat 页发送消息前先调用 intake
- 若 intake 判定为任务线程：
  - 打开 `task-chat:{task_id}`
  - 后续流式请求改走 `/runtime-center/chat/run`
- 行业聊天左侧新增“任务线程”区块
- 任务线程会话保存真实 `runtime_session_id`，保证后续追问继续落在同一 `task-session:*`

### 4.3 测试

- `KernelTurnExecutor.prepare_chat_turn()` 控制/任务两条路径
- Runtime conversation 对 `task-chat:*` 的解析
- Runtime Center chat intake / run / tasks 三个接口
- 前端至少通过 `npm build`

---

## 5. 执行判定规则

本轮不引入复杂分类器，只做最小、可解释判断：

- 以下继续留在控制线程：
  - 空消息
  - 已在任务线程中的追问
  - slash command
  - query confirmation policy 切换口令
  - 非行业执行中枢上下文
  - 纯解释/问答型对话

- 以下可拆为任务线程：
  - 明确执行请求
  - 明确高风险外部代操
  - 明确会触发 chat writeback 的新增任务/纠偏/长期节奏要求

---

## 6. 前台交互原则

- 前台默认唯一主入口仍是 `Spider Mesh 执行中枢`
- 任务线程不是新的“第二大脑”，只是从控制线程拆出的正式执行上下文
- 用户在任务线程里追问，是对同一任务继续推进，不是开一段新闲聊
- 控制线程左侧必须能返回指挥线程，也必须能看到最近拆出的任务线程

---

## 7. 本轮增强版已补齐的内容

在最小版验收后，当前仓库已继续补齐以下增强项，并全部进入正式代码面：

- 控制线程富摘要回流卡片
- 控制线程下多任务看板、筛选与批量取消管理
- `task` 级长期记忆与更严格的跨任务记忆隔离
- 子 agent / 子任务专属任务线程执行面
- 任务线程自动复盘读面与前端复盘页

---

## 8. 验收标准

本轮完成后，必须满足：

1. 行业聊天默认仍只进入 `Spider Mesh 执行中枢`
2. 控制线程里发送执行型请求，会创建正式 `task-chat:{task_id}`
3. 任务线程后续追问继续落在同一 `task-session:*`
4. Chat 左侧能列出当前控制线程最近任务线程
5. Runtime Center conversation facade 能解析任务线程
6. 相关 pytest 通过
7. `npm --prefix console run build` 通过

---

## 9. 一句话结论

这不是“再做一个聊天分页”，而是把 `/chat` 从单会话壳，升级为：

> 一个前台指挥线程，挂接多个正式任务线程的最小执行指挥台。
