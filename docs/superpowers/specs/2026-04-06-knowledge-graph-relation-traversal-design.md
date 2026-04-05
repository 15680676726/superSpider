# CoPaw 知识图谱关系路径推演增强设计

## 0. 目标

这次升级不是重做知识图谱，也不是引入新的 memory engine。

这次只做一件事：

> 在现有 truth-first knowledge graph 之上，补一层关系路径推演，让主脑规划和执行不再只消费“关系摘要”，而是显式消费“关键关系路径”。

目标结果：

- 激活层不再只返回 `top_relations`，还返回可解释的关键路径包
- planner 会因为依赖链、阻塞链、支持链、反驳链而改变计划顺序
- execution 会因为失败链、恢复链、依赖链而改变动作顺序
- 整个系统仍然只有一套正式知识真相源

---

## 1. 为什么要做

当前知识图谱已经具备：

- 正式 truth
- 子图激活
- 报告/执行回写
- 进入 planning 主链

但当前主链对关系的消费还偏浅：

- activation 更像“关键词 + 置信度 + 关系摘要”打分
- planner 主要消费 `top_relations / top_relation_kinds`
- execution 还没有真正显式按关系路径调整动作顺序

这意味着系统已经“有图谱”，但还没有真正“顺着图谱思考”。

---

## 2. 本次不做什么

明确不做：

- 不引入 graph DB
- 不引入 vector-first formal memory
- 不引入第二套 memory truth
- 不把外部研究仓直接接入主链
- 不把关系路径包做成新的正式持久化对象
- 不先做 Runtime Center UI

一句话：

> 借鉴多关系图检索和 traversal 思想，但只强化 CoPaw 自己的运行时推演层。

---

## 3. 设计原则

### 3.1 不换底座

正式真相仍然只有：

- `knowledge_chunks`
- `memory_fact_index`
- `memory_relation_views`

关系路径包只是运行时派生结果，不是第二套 truth。

### 3.2 路径服务主脑，不反客为主

关系路径推演是主脑的认知辅助层，不是第二个 planner。

主脑仍负责：

- 目标判断
- 规划收敛
- 执行编排
- 风险升级
- 复盘回写

### 3.3 先让系统更会用现有图谱

这次不是增加更多 node/relation 类型，而是让现有图谱更可检索、更可解释、更能改变执行顺序。

### 3.4 路径必须有证据

任何关键路径都必须能回答：

- 由哪些节点组成
- 由哪些关系组成
- 绑定了哪些证据
- 为什么这条路径比另一条更重要

---

## 4. 关系分层

当前 relation type 保留现有 formal 集合，但在激活和推演阶段按认知用途收敛成 5 组：

### 4.1 结构关系

- `belongs_to`
- `part_of`
- `instance_of`
- `located_in`

作用：

- 确定对象归属和上下文边界

### 4.2 时间关系

- `follows`
- `updates`
- `replaces`

作用：

- 识别先后顺序、替代关系、最新状态

### 4.3 因果关系

- `causes`
- `affects`
- `indicates`

作用：

- 找成因、结果、征兆

### 4.4 判断关系

- `supports`
- `contradicts`
- `suggests`

作用：

- 找支持链、反驳链、候选方向

### 4.5 执行关系

- `depends_on`
- `blocks`
- `uses`
- `produces`
- `recovers_with`
- `constrained_by`

作用：

- 识别前置条件、阻塞点、恢复路径、执行约束

---

## 5. 关系路径推演模型

### 5.1 新增的不是新真相，而是运行时派生结果

在现有 `TaskSubgraph` 之上，补一层运行时路径包：

- `support_paths`
- `contradiction_paths`
- `dependency_paths`
- `blocker_paths`
- `recovery_paths`

### 5.2 单条路径的最小结构

每条路径至少包含：

- `path_type`
- `score`
- `node_ids`
- `relation_ids`
- `relation_kinds`
- `summary`
- `evidence_refs`
- `source_refs`

### 5.3 路径是压缩后的认知骨架

路径不是完整图搜索结果，也不是全量图遍历日志。

路径只保留：

- 对当前任务最关键的几条链
- 能改变规划顺序或执行顺序的链
- 能解释“为什么”的链

---

## 6. 激活层升级

### 6.1 当前状态

当前 activation 已经能返回：

- top entities
- top opinions
- top relations
- top relation kinds
- contradictions

这说明基础很好，升级点不在“有没有图谱”，而在“怎么扩散关系”。

### 6.2 新的激活流程

激活改成三段：

1. `seed extraction`
   从 query / task / work context / assignment / strategy 中抽种子点
2. `typed traversal`
   按关系类型做有限 hop 扩散
3. `path packing`
   把扩散结果压缩成关键路径包

### 6.3 traversal policy

第一版 traversal policy 不追求复杂学习，只做确定性策略：

- 先看执行关系
- 再看判断关系
- 再看因果关系
- 最后看时间关系和结构关系

原因：

- 当前系统最缺的是更稳的规划和执行，不是更花的知识探索

### 6.4 hop 和预算纪律

必须限制：

- 每类路径最多保留固定条数
- 每次 traversal 的最大 hop 数固定
- 总输出预算固定

避免主链越来越重。

---

## 7. Planner 接线

### 7.1 cycle planner

cycle planner 不能再只看关系摘要。

它要显式消费：

- `dependency_paths`
- `blocker_paths`
- `contradiction_paths`
- `support_paths`

规则：

- 有强依赖链时，先解前置
- 有强阻塞链时，压住推进
- 有强矛盾链时，优先澄清和验证
- 有强支持链时，提高相关计划分支优先级

### 7.2 assignment planner

assignment planner 要把路径包编译成更明确的执行约束：

- 必须先完成的前置条件
- 需要先补证据的矛盾点
- 应优先采用的能力和环境路径
- 可以优先尝试的恢复路径

### 7.3 planning 输出要能体现关系依据

planning 元数据里不只保留：

- relation ids
- relation kinds

还应保留：

- 被采用的关键路径 ids
- 路径类型摘要
- 为什么某条路径改变了计划顺序

---

## 8. Execution 接线

### 8.1 execution 不只“看到路径”

execution 侧不能只把路径塞进提示词。

它要显式用于：

- 决定动作顺序
- 决定是否先做前置验证
- 决定是否避开高失败链
- 决定是否优先走已知恢复链

### 8.2 execution 侧的 4 条纪律

1. 前置依赖未满足时，不硬做后续动作
2. 历史阻塞链强时，优先做解除阻塞动作
3. 历史失败链匹配时，降低同路径动作优先级
4. 已知恢复链可用时，优先采用更稳的恢复顺序

### 8.3 这不是自动决策越权

路径只影响：

- 排序
- 提示
- 守护
- 重试/恢复建议

它不替代治理层，不绕过 `auto / guarded / confirm`。

### 8.4 本次实际落地边界

本次实现已经落到 4 个真实消费面：

- activation
  - 现在会稳定产出 `support / contradiction / dependency / blocker / recovery` 五类路径包
- planner
  - cycle planner 会把路径 relation evidence 计入排序和 affected relation surface
  - assignment planner 会把路径编译进 checkpoint、`knowledge_subgraph` 和 `execution_ordering_hints`
- compiler
  - compiler 会把 assignment sidecar 中的路径提示暴露进 compiled payload / task seed
  - 这些提示会直接写进执行 prompt 文本，而不只是留在 relation ids 里
- execution
  - query execution prompt 会在 activation context 下显式展示 dependency / blocker / recovery / contradiction 路径
  - execution feedback appendix 会把路径作为排序/守护提示显示出来

明确没有落地的内容：

- 没有新增第二套持久化 truth
- 没有把路径包写成正式 graph truth 对象
- 没有引入 graph DB / vector-first memory
- 没有做 Runtime Center UI 新读面
- 没有让路径绕过治理层直接触发动作

---

## 9. 与 MAGMA 的关系

这次只借 3 个思想：

- 多关系图视角
- relation-type-aware traversal
- benchmark 驱动的 memory/activation 评测

不借：

- 独立 memory engine
- graph database 架构中心
- vector-first truth
- 外部项目的整体系统形态

所以这不是“接入 MAGMA”，而是：

> 在 CoPaw 现有知识图谱上吸收更成熟的关系检索纪律。

---

## 10. 测试与验收

### 10.1 激活测试

需要证明：

- 相同 seed 下，不同 relation type 会导出不同关键路径
- `contradicts / depends_on / recovers_with` 等类型会真实影响路径排序
- 产出的不是散乱关系列表，而是结构化路径包

### 10.2 planner 测试

需要证明：

- 有依赖链时，planner 会先解前置
- 有阻塞链时，planner 会压住推进
- 有矛盾链时，planner 会先澄清
- 有支持链时，planner 会调整优先级

### 10.3 execution 测试

需要证明：

- execution 会根据路径改变动作顺序
- execution 会在 prompt / feedback appendix 中显式看到路径提示
- 遇到高匹配失败链会避开原路径
- 有 recovery path 时会优先采用更稳的恢复顺序

### 10.4 结构性验收标准

这次完成必须同时成立：

1. 激活层能稳定产出 5 类关键路径
2. planner 会因为路径不同而改变计划顺序
3. execution 会因为路径不同而改变动作顺序
4. 历史失败链和恢复链能真实影响后续执行
5. 全程不引入第二套正式 memory truth

---

## 11. 实施顺序

推荐按 4 步推进：

1. 关系分层和 traversal policy
2. 路径包输出
3. planner 消费关键路径
4. execution 消费关键路径

不建议一开始就扩 UI 或引入外部引擎。

---

## 12. 最终定义

这次升级的最终定义是：

> 保留 CoPaw 当前知识图谱底座，只新增一层关系路径推演，让主脑和执行器真正能顺着关系链思考、排序和避坑。
