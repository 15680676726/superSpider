# WorkContext Purpose And Implementation Target

本文档用于把 `WorkContext` 的真实目的、产品价值、边界定义与实现目标写清楚，避免后续把它误做成：

- 新的聊天线程壳
- 新的 memory backend
- 某个业务线的专用补丁
- 另一套并行 runtime chain

---

## 1. 一句话定义

`WorkContext` 不是“某个窗口”，也不是“某个 agent”，更不是“某次 task”。

它表示的是：

> 系统中一件连续工作的正式身份与边界。

更直白一点：

> 没有 `WorkContext`，系统只能认线程；有了 `WorkContext`，系统才能认事情。

---

## 2. 它到底要解决什么问题

当前系统已经能跑：

- 聊天
- task
- mailbox
- checkpoint
- report
- evidence
- recall

但系统仍然缺一个正式对象，去稳定表达：

- 这个聊天窗口到底在服务哪一件事
- 这批 task 到底属于哪一件事
- 多个 agent 协作时到底是在处理哪一件事
- 多轮追问、补料、汇报、证据，到底是不是还属于同一件事

如果没有这个对象，系统就只能继续靠：

- `agent-chat`
- `actor-chat`
- `task-chat`
- `session_id`
- prompt transcript
- metadata 猜测

去推断上下文。

这在单线简单场景下还能勉强工作，但在多线并行场景下会直接失真。

---

## 3. 真实产品目的

`WorkContext` 的真实产品目的，不是为了多一个抽象概念，而是为了让系统具备“并行多线工作时分清谁是谁”的能力。

它至少要解决下面 3 类核心场景。

### 3.1 多 agent + 多聊天窗口

当多个 agent 同时工作、同时聊天时，系统必须能分清：

- 这个窗口在聊哪个工作单元
- 这个窗口的追问应该回到哪条连续工作线上
- 哪些 evidence / report / recall 应该对这个窗口可见

系统不能只知道：

- 这是某个 agent 的线程

它必须知道：

- 这是某个 agent 正在处理的哪一件事

### 3.2 多个研究方案并行

当同一个行业实例、同一个 operator、甚至同一个 agent 同时推进多个研究方案时，系统必须能分清：

- 方案 A 的证据
- 方案 A 的结论
- 方案 A 的分派任务
- 方案 A 的后续追问

不能被方案 B 污染。

也就是说，系统要能区分：

- 研究方案本身的连续工作边界
- 同一团队/同一 agent 的公共背景经验

### 3.3 多个客户并行

当系统同时服务多个客户时，必须能分清：

- 客户甲当前在推进什么
- 客户乙当前在推进什么
- 哪些任务、报告、证据属于客户甲
- 哪些任务、报告、证据属于客户乙

不能把：

- 客户甲的材料
- 客户甲的分析
- 客户甲的跟进状态

串进客户乙。

这类“客户/案件/机会/工单/方案级别”的隔离，就是 `WorkContext` 的核心价值。

---

## 4. 四类对象的区别

后续实现时，必须严格区分以下对象。

### 4.1 `Chat Thread / Session`

它是交互表面。

负责：

- 展示消息
- 承接输入输出
- 暂存交互入口信息

它不是连续工作的真相源。

### 4.2 `Agent`

它是执行者。

负责：

- 执行
- 协作
- 汇报
- 使用能力

`Agent` 可以同时服务很多 `WorkContext`，所以它不能天然等于某一件事。

### 4.3 `Task`

它是一次可调度、可执行的工作单元。

一个 `WorkContext` 可以包含多个 `Task`。

因此：

- `Task` 是执行切片
- `WorkContext` 是持续工作边界

### 4.4 `WorkContext`

它是“这件事本身”的正式身份。

它承载的是：

- 这一条连续工作线是谁
- 它的主要对象是谁
- 它当前处于什么状态
- 哪些 task / report / evidence / recall 属于它

---

## 5. 为什么不能继续用线程代替

线程只能解决“从哪里聊”，解决不了“在聊哪件事”。

原因有 5 个：

1. 同一件事可能跨多个窗口、多个 turn、多个 task。
2. 同一个窗口里可能先指挥、后执行、再追问，线程不是稳定业务边界。
3. 多个 agent 可以协作同一件事，线程无法天然表达共享边界。
4. 同一个 agent 可以同时处理很多事，不能靠 agent 私有记忆顶替正式对象。
5. 后端的 evidence / report / memory recall 都需要正式归属，线程 alias 不是可靠真相源。

所以：

- 线程可以映射到 `WorkContext`
- 线程不能充当 `WorkContext`

---

## 6. `WorkContext` 应该怎么理解

可以把 `WorkContext` 理解成系统里的正式“案件号 / 客户号 / 方案号 / 工作单元号”。

它对应的并不一定是固定业务名词，而是一个统一抽象：

- 一个客户跟进线
- 一个售后问题
- 一个研究方案
- 一个项目专题
- 一个事故排查
- 一个经营机会
- 一个持续执行中的主题工作

重点不在名字，而在于：

> 系统要能稳定知道，哪些运行事实属于同一件事。

---

## 7. 与记忆系统的关系

`WorkContext` 不是新的记忆库。

它不应该保存另一份平行长期记忆正文。

它真正负责的是：

- 给 recall 提供正式 scope
- 让“这件事的连续事实”有稳定落点
- 让跨 turn / 跨 child-task 的上下文在同一工作边界内聚合

落地后，正式 recall 顺序应为：

1. current `task`
2. current `work_context`
3. current `agent`
4. current `industry`
5. current `global`
6. needed `strategy summary`

这意味着：

- 同一任务的即时上下文最高优先
- 同一工作单元的连续事实第二优先
- agent 自身经验只能作为更低优先级背景

---

## 8. 与多 agent 协作的关系

多个 agent 可以挂在同一个 `WorkContext` 上协作。

允许共享：

- evidence
- task terminal reports
- compiled memory summary
- 与该工作单元直接相关的 recall 结果

不允许共享：

- 私有 mailbox
- 私有 checkpoint
- 私有 runtime transient state
- 隐式 chain-of-thought

规则必须是：

- 同一 `WorkContext` 共享正式结果与事实
- 不同 `WorkContext` 默认隔离

---

## 9. 当前阶段的默认映射规则

当前阶段不要求一开始就覆盖所有业务命名，但必须先把正式锚点打通。

第一批正式锚点应为：

1. `task-chat / task-session:*`
2. parent-task delegation inheritance
3. 显式 front-door `work_context_id / context_key`

这意味着：

- 一个稳定 task-thread 应能稳定对应一个 `WorkContext`
- child task 默认继承 parent 的 `work_context_id`
- 后续任何 front-door 只要能提供稳定 `work_context_id` 或 `context_key`，都应复用同一套主链

---

## 10. 当前要补的实现目标

这轮实现的目标不是“先做个能跑的壳”，而是把主线一次性补到可继续扩展的正确位置。

### 10.1 正式对象

必须新增：

- `WorkContextRecord`

建议稳定字段至少包括：

- `id`
- `title`
- `summary`
- `context_type`
- `status`
- `context_key`
- `owner_scope`
- `owner_agent_id`
- `industry_instance_id`
- `primary_thread_id`
- `source_kind`
- `source_ref`
- `parent_work_context_id`
- `metadata`

### 10.2 核心记录补 `work_context_id`

必须补到：

- `TaskRecord`
- `AgentMailboxRecord`
- `AgentCheckpointRecord`
- `AgentThreadBindingRecord`
- `AgentReportRecord`
- `KernelTask`

`EvidenceRecord` 当前阶段继续走：

- `metadata["work_context_id"]`

不额外开第二套 evidence store。

### 10.3 recall 与 memory scope

必须把 `work_context` 变成正式 scope，而不是只停留在文档里。

当前只有：

- `global`
- `industry`
- `agent`
- `task`

后续应升级为：

- `global`
- `industry`
- `agent`
- `task`
- `work_context`

### 10.4 Runtime Center 读面

运行中心后续必须能看见：

- 当前窗口绑定哪个 `WorkContext`
- 当前 task 属于哪个 `WorkContext`
- 当前 evidence / report 属于哪个 `WorkContext`
- 相关 task-thread 是不是同一工作单元

不能继续只靠线程别名和 metadata 猜。

---

## 11. 实现验收标准

只有满足下面标准，`WorkContext` 才算真的落地，不算“登记了但没完成”。

### 11.1 辨识能力

系统必须能稳定区分：

- 多个 agent 的不同工作窗口
- 同一个 agent 并行处理的不同事项
- 多个研究方案
- 多个客户
- 同一事项下的多 task / 多次追问 / 多 agent 协作

### 11.2 归属能力

系统必须能稳定归属：

- task 属于哪个 `WorkContext`
- mailbox / checkpoint 属于哪个 `WorkContext`
- report 属于哪个 `WorkContext`
- evidence 属于哪个 `WorkContext`
- memory recall 命中的内容属于哪个 `WorkContext`

### 11.3 隔离能力

系统必须默认避免：

- 客户 A 上下文串到客户 B
- 方案 A 结论串到方案 B
- agent 私有 working state 被误当成共享真相

### 11.4 继承能力

系统必须支持：

- child task 继承 parent `work_context_id`
- task-thread 稳定映射 `WorkContext`
- front-door 显式复用已有 `work_context_id / context_key`

---

## 12. 非目标

这轮明确不做：

- 第二套 memory backend
- 第二套 evidence ledger
- 为客服/销售/研究分别写三套专用实现
- 把聊天线程直接升级为真相源
- 给每个 agent 再造一套私有长期脑

---

## 13. 删除目标

`WorkContext` 落地之后，后续应逐步删除这些旧式依赖：

- 仅靠 `agent-chat / actor-chat / task-chat` 猜业务边界
- 仅靠线程 alias 推断“是不是同一件事”
- 仅靠 prompt transcript 恢复连续工作上下文
- 仅靠 agent 私有历史经验承接多线并行工作

真正要实现的是：

> 线程是入口，agent 是执行者，task 是执行单元，`WorkContext` 才是这件事的正式身份。

---

## 14. 最终判断标准

判断 `WorkContext` 是否做对，不看有没有新表、不看有没有新字段，而看系统是否已经具备下面这句话的能力：

> 当多个 agent、多个窗口、多个方案、多个客户同时在线时，系统仍然能明确知道“谁是谁、哪件事是哪件事、哪些事实该归到哪里”，并且不串线。
