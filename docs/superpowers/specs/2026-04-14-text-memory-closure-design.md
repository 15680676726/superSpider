# CoPaw 文本记忆系统收口设计

日期：`2026-04-14`

## 1. 目标

这轮只做一件事：

> 把 CoPaw 的正式文本记忆系统彻底收干净，让“长期正式记忆”和“私有聊天压缩”彻底分家。

这轮明确不做：

- 不做向量检索
- 不做 embedding 主链
- 不做多模态实现
- 不新建第二套记忆真相源
- 不让聊天压缩继续冒充正式记忆

## 2. 结论先说死

CoPaw 正式记忆系统的终态是：

- `truth-first`
- `no-vector formal memory`
- 共享正式记忆只来自 canonical `state / evidence / runtime`
- 私有聊天压缩只服务单线程对话，不进入正式规划、正式执行、正式汇报主链

这轮完成后，系统里只允许保留两条边界清晰的记忆线：

1. 正式长期记忆线
2. 私有聊天压缩线

它们可以共存，但不能再混用。

## 3. 当前问题

现在主线已经有：

- `StrategyMemoryRecord`
- `KnowledgeChunkRecord`
- derived `fact / entity / opinion / relation`
- activation layer
- execution graph projection
- `work_context` 优先召回

但还差最后一层收口：

1. 不是所有进入系统的文本都应该进正式记忆
2. 不同类型的信息还缺少明确的“写到哪一层”的规则
3. 召回预算和优先级还不够收死
4. 重复、低价值、过期文本还缺正式压缩规则
5. 私有聊天压缩虽然已经不算正式真相，但旧兼容壳还在

## 4. 设计原则

### 4.1 不新造真相源

正式记忆仍然只建立在已有正式对象之上：

- `state`
- `evidence`
- `strategy`
- `backlog`
- `cycle`
- `assignment`
- `report`
- `work_context`

记忆层只能派生、归纳、投影，不能反过来变成主链 owner。

### 4.2 记忆只保留高价值内容

默认不是“有内容就记”。

只有这几类内容允许进入正式长期记忆：

- 稳定事实
- 明确约束
- 可复用偏好
- 执行结果
- 失败模式
- 恢复路径
- 证据锚点
- 战略结论

普通寒暄、一次性废话、没有稳定价值的中间推测，不进入正式记忆。

### 4.3 先近后远召回

正式召回顺序收死为：

1. `work_context`
2. `task / assignment / report`
3. `agent`
4. `industry`
5. `global / strategy`

不允许一上来就把全局内容灌进当前 prompt。

### 4.4 私有聊天压缩只做私有工具

`conversation_compaction_service` 可以继续存在，但它的职责只剩：

- 压缩当前聊天线程上下文
- 提供当前线程私有搜索
- 为上下文窗口节流

它不再承担：

- 正式长期记忆写入
- 正式规划补丁真相
- 正式执行主链召回兜底

## 5. 最终结构

这轮记忆系统正式收成 4 层：

### 5.1 真相层

系统现有正式对象层，不新增。

### 5.2 正式长期记忆层

保留并强化：

- `StrategyMemoryRecord`
- `KnowledgeChunkRecord`
- derived `MemoryFactIndexRecord`
- derived `MemoryEntityViewRecord`
- derived `MemoryOpinionViewRecord`
- derived `MemoryRelationViewRecord`
- execution graph projection

### 5.3 记忆加工层

新增/强化三类规则：

- `selective ingestion`
- `tier routing`
- `canonical compaction`

也就是：

- 先判断值不值得记
- 再判断该记到哪一层
- 最后判断是不是该合并、降重或失效

### 5.4 私有聊天压缩层

保留 `conversation_compaction_service`，但只作为对话 sidecar。

旧 `agents/memory/memory_manager.py` 正式退役。

## 6. 这轮要落地的能力

### 6.1 选择性写入

系统新增统一记忆判定入口，至少判断：

- 是否稳定
- 是否可复用
- 是否有证据
- 是否属于当前正式 scope
- 是否只是一次性聊天噪音

输出只允许是：

- 写入正式长期记忆
- 仅保留在私有聊天压缩
- 丢弃

### 6.2 分层路由

新增统一路由规则：

- 战略内容 -> `strategy_memory`
- 执行连续性 -> `work_context`
- 行业共识 -> `industry`
- agent 可复用经验 -> `agent`
- 临时聊天碎片 -> 私有压缩层

禁止调用方自己猜 scope。

### 6.3 规范压缩

正式长期记忆不做“无限追加文本”。

需要支持：

- 重复合并
- 失败模式聚合
- 恢复路径聚合
- 偏好/约束归一
- 旧结论失效或降权

### 6.4 预算感知召回

召回不是“能拿多少拿多少”。

需要显式限制：

- 每层 scope 的最大召回量
- relation/path 的最大展开量
- evidence 引用数
- strategy 注入上限

目标是让规划和执行 prompt 读到的永远是“够用的相关内容”，不是一坨历史垃圾。

### 6.5 图关系检索继续用现有主链

不引入图数据库。

继续使用现有：

- `knowledge_graph_service`
- `knowledge_writeback_service`
- `relation views`
- `activation_service`

但把关系召回的用途收死为：

- 找上下文
- 找证据链
- 找失败/恢复链
- 找执行对象之间的正式关系

## 7. 删除与退役

这轮明确退役：

- `src/copaw/agents/memory/memory_manager.py`

退役原则：

- 正式运行主链不再引用它
- 旧 alias 不再保留
- 测试改为只认 `conversation_compaction_service`

## 8. 风险控制

这轮不允许出现以下偏差：

- 重新把私有聊天压缩抬成正式记忆
- 重新引入 vector/embedding 作为正式依赖
- 再造一套新 memory DB 真相
- 调用方绕过统一 ingestion/tier routing 直接乱写 `KnowledgeChunkRecord`
- relation/activation 读面反过来变成正式 owner

## 9. 验收标准

这轮完成后必须满足：

1. 正式长期记忆和私有聊天压缩边界明确
2. 正式写入只走统一 selective-ingestion + tier-routing
3. 正式召回遵守 scope priority + retrieval budget
4. `memory_manager` 兼容壳删除
5. 现有记忆主链、执行写回、Runtime Center 记忆读面不回退

## 10. 实施顺序

按下面顺序做：

1. 文档收口
2. selective ingestion contract
3. tier routing contract
4. retrieval budget contract
5. canonical compaction rules
6. 退役 `memory_manager`
7. 全链回归测试

## 11. 一句话总结

这轮不是“重写记忆系统”，而是把现有已经存在的 `truth-first` 记忆主链彻底做干净：

- 正式记忆只记该记的
- 记到该去的层
- 取的时候先近后远
- 压缩只发生在正式规则里
- 私有聊天压缩彻底退回私有 sidecar

