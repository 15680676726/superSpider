# CoPaw 内部统一知识图谱设计

## 2026-04-06 Implementation Supplement

The following seams are now implemented on the live code path:

- `src/copaw/memory/knowledge_graph_service.py` is the thin internal knowledge-graph facade.
  It owns request subgraph activation, kernel-metadata subgraph extraction, compact task-subgraph summary shaping, and writeback entry delegation without introducing a second truth source.
- `src/copaw/kernel/main_brain_execution_planner.py` now activates the current task subgraph during orchestrate intake and attaches the compact `knowledge_graph` summary to the canonical main-brain runtime context.
- `src/copaw/kernel/main_brain_intake.py`, `src/copaw/kernel/query_execution_context_runtime.py`, and `src/copaw/kernel/query_execution_prompt.py` now preserve and consume that `knowledge_graph` runtime section through resume/checkpoint/prompt paths.
- `src/copaw/app/runtime_center/state_query.py`, `src/copaw/app/runtime_center/task_detail_projection.py`, and `src/copaw/app/runtime_center/task_list_projection.py` now project `task_subgraph` summaries from canonical kernel metadata into Runtime Center task detail/list reads.
- `src/copaw/app/runtime_service_graph.py`, `src/copaw/app/runtime_bootstrap_domains.py`, `src/copaw/app/runtime_bootstrap_models.py`, and `src/copaw/app/runtime_state_bindings.py` now bootstrap and publish `knowledge_graph_service` as part of the shared runtime state instead of keeping the facade as an ad-hoc local helper.

This closes the previously identified three real gaps:

1. unified `knowledge_graph_service` facade
2. main-brain planner/runtime-context integration
3. Runtime Center task-subgraph read surface

## 0. 目标

本设计用于把 CoPaw 当前已经存在的：

- truth-first memory
- activation layer
- strategy memory
- planning chain
- execution evidence

收口成一套统一的内部知识图谱设计。

一句话目标：

> 让 CoPaw 拥有一套统一的、可生长的、证据驱动的内部知识图谱；主脑每次只激活当前任务子图来规划和执行，执行结束后再把结果和经验写回总图。

这份设计不追求：

- 新建第二套 memory truth
- 引入新的顶层主链语义
- 把知识图谱做成重型百科库
- 让主脑每次直接读取整张总图

这份设计追求：

- 统一对象模型
- 统一关系模型
- 统一知识进入规则
- 统一任务子图激活入口
- 统一执行后回写规则

---

## 1. 核心判断

### 1.1 知识图谱不是数据源

知识图谱不是外部数据来源，而是 CoPaw 组织知识的正式方式。

外部网页、文件、工具结果、执行结果、报告、人类输入、系统推断，都只是输入源。

它们进入系统后，必须被归一成统一对象和统一关系，才能成为主脑可用的正式知识。

### 1.2 统一的是内部真相，不是外部来源数量

CoPaw 可以存在多个知识输入源，但系统内部只能有一套正式知识图谱。

主脑、planner、execution、report synthesis 不得各自维护一套平行知识入口。

### 1.3 图谱服务主脑，不取代主脑

知识图谱是认知底座，不是第二个大脑。

主脑仍然负责：

- 目标判断
- 规划收敛
- 执行编排
- 风险升级
- 复盘与再规划

知识图谱负责：

- 统一长期认知
- 提供当前任务子图
- 给执行与复盘提供结构化依据

### 1.4 系统默认自治，人类是边界与讨论伙伴

CoPaw 必须保持：

- 独立思考
- 独立完成任务
- 独立形成假设和路径

同时也必须保留：

- 听从人类最高指令
- 在高风险和重大取舍时请示
- 在不确定和冲突场景中与人类讨论

因此，人类相关信息应进入知识图谱，但只能作为边界、约束、审批与讨论对象，不得喧宾夺主成为图谱中心。

---

## 2. 设计原则

### 2.1 一套总图，一套主链

系统内部只能有一套正式知识图谱总图。

以下内容最终都必须归一到这套总图里：

- 事实
- 观点
- 关系
- 证据
- 策略对象
- 执行对象
- 人类边界对象

### 2.2 总图沉淀，子图运行

总图用于长期沉淀。

主脑运行时只读取“当前任务子图”，不直接扫全图。

这是避免主链过重的第一原则。

### 2.3 对象类型少而稳，关系实例持续生长

对象模型必须稳定，后续增长主要体现在：

- 新节点增加
- 新关系增加
- 关系权重变化
- 知识状态变化
- 生命周期变化

不得频繁重写一级对象定义。

### 2.4 正式知识必须可追溯

正式图谱中的知识必须尽可能能回答：

- 从哪来
- 什么时候成立
- 可信度多少
- 适用范围是什么
- 现在是否仍有效
- 被哪些证据支持或反驳

### 2.5 图谱是活的认知骨架

知识图谱不是死表，也不是只进不出的仓库。

它必须支持：

- 新建
- 增强
- 降权
- 失效
- 替换
- 合并

---

## 3. 三层认知结构

### 3.1 世界认知层

回答：

> 世界是什么样的？

主要承载：

- 实体
- 事件
- 事实
- 观点
- 关系
- 证据
- 约束

### 3.2 执行认知层

回答：

> 要做什么？怎么做更可能成功？

主要承载：

- strategy
- lane
- backlog
- cycle
- assignment
- report
- capability
- environment
- runtime outcome
- failure pattern
- recovery pattern

### 3.3 人类边界与讨论层

回答：

> 人类给了什么边界？什么时候需要讨论？形成了什么共识？

主要承载：

- instruction
- approval
- rejection
- discussion
- consensus
- preference

这层不是主角，但必须存在。

---

## 4. 统一对象模型

## 4.1 世界认知对象

### 实体 `entity`

用于表示：

- 人
- 公司
- 产品
- 行业
- 机构
- 地区
- 概念

### 事件 `event`

用于表示带时间和结果的发生事实，例如：

- 某次执行失败
- 某次策略调整
- 某次市场变化
- 某次人类审批
- 某次能力安装或失效

### 事实 `fact`

用于表示已确认成立的信息。

### 观点 `opinion`

用于表示：

- 判断
- 预测
- 假设
- 风险看法
- 结论

观点可以进入正式图谱，但必须带证据和置信度。

### 证据 `evidence`

用于表示：

- 网页
- 文件
- 报告
- 工具结果
- 执行结果
- 外部输入

### 约束 `constraint`

用于表示：

- 时间限制
- 预算限制
- 法律或合规限制
- 平台限制
- 风险红线
- 环境前置条件

### 关系 `relation`

关系是正式对象，不只是隐含字段。

每条关系至少应具备：

- relation_type
- source_id
- target_id
- evidence_refs
- confidence
- scope
- valid_from
- valid_to
- status

## 4.2 执行认知对象

以下对象不重新发明第二套 vocabulary，而是直接复用 CoPaw 现有正式主链对象：

- `StrategyMemoryRecord`
- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`
- capability mounts
- environment/session truth
- runtime outcome / failure / recovery projections

它们在知识图谱里不是“影子对象”，而是正式节点。

## 4.3 人类边界对象

人类相关内容只进入以下语义范围：

- 指令
- 约束
- 审批
- 否决
- 偏好
- 讨论
- 共识

它们不是主图谱中心，但必须能影响规划、执行和治理。

---

## 5. 最小正式关系集合

第一版关系类型只保留高价值主干，不追求枚举世界。

### 5.1 结构关系

- `belongs_to`
- `part_of`
- `instance_of`
- `located_in`

### 5.2 影响与依赖关系

- `depends_on`
- `affects`
- `causes`
- `blocks`

### 5.3 认知判断关系

- `supports`
- `contradicts`
- `indicates`
- `suggests`

### 5.4 执行关系

- `uses`
- `targets`
- `produces`
- `recovers_with`

### 5.5 演化关系

- `follows`
- `updates`
- `replaces`
- `derived_from`

### 5.6 人类边界关系

- `requested_by`
- `approved_by`
- `rejected_by`
- `constrained_by`
- `discussed_with`

关系数量必须克制；真正丰富度应来自关系属性，而不是无限新增关系名。

---

## 6. 知识流转规则

## 6.1 统一进入

所有知识来源统一先进入候选知识层。

输入源包括：

- 聊天结论
- 报告
- 执行结果
- 工具输出
- 文件
- 网页
- 人类输入
- 系统推断

### 6.2 统一归一

候选知识进入系统后，必须先归一为正式对象：

- entity
- event
- fact
- opinion
- evidence
- constraint

归一动作至少包括：

- 去重
- 命名归一
- scope 归一
- 来源挂载
- 时间归一
- 置信度初始赋值

### 6.3 统一关联

归一之后必须优先建边，不鼓励只写孤立节点。

没有关系的知识，长期价值很低。

### 6.4 统一激活

每次主脑接到任务时，只能通过统一入口激活一个任务子图。

子图激活种子一般来自：

- 当前 strategy
- 当前 lane / backlog / cycle / assignment
- 当前任务文本中的核心实体和关键词
- 当前 capability / environment
- 当前约束
- 最新强证据

排序信号至少包括：

- 相关度
- 新近性
- 证据强度
- 置信度
- 历史成功率
- 当前 scope 亲和度

### 6.5 统一回写

执行、报告、复盘后，必须把以下内容正式写回总图：

- 新事实
- 新事件
- 新证据
- 观点修正
- 关系变化
- 失败模式
- 恢复路径
- 策略影响

### 6.6 统一失效

旧知识不能永久累积不清理。

必须支持：

- 降权
- 过期
- 反驳
- 替换
- 合并

---

## 7. 自动入图与保守入图边界

## 7.1 可自动入图

以下信息可以默认自动进入正式图谱：

- 明确工具输出
- 明确执行结果
- 明确文件内容
- 明确结构化系统状态
- 已确认的 capability / environment / assignment / report 事实
- 带时间、对象、结果的明确事件

## 7.2 可入图但必须降级为观点

以下信息可以入图，但不得直接当事实：

- 模型推断
- 趋势判断
- 风险判断
- 策略建议
- 报告综合结论
- 不完全确定的归因

这类信息应写成：

- opinion
- 假设
- 风险判断
- 候选关系

并绑定证据与置信度。

## 7.3 不可直接入正式图谱

以下信息不得直接进入正式图谱：

- 纯聊天随口猜测
- 未验证的幻觉式总结
- 无来源说法
- 一次性情绪表达
- 没有对象锚点的泛化判断
- 仅对当前一轮 prompt 有意义的局部碎片

---

## 8. 主脑如何使用图谱

## 8.1 规划

主脑在规划短、中、长期动作时，应先读取当前任务子图，而不是只看 prompt 文本。

规划子图中至少应包含：

- 当前 strategy
- 当前 lane / backlog / cycle / assignment
- 相关实体和事件
- 当前风险和约束
- 最近强证据
- 类似任务历史结果

## 8.2 执行

执行前应从图谱中获取：

- 可用 capability
- 可用 environment
- 历史成功路径
- 常见阻塞点
- 失败模式
- 恢复路径

## 8.3 复盘

复盘不只是文本总结，而是对知识图谱的正式更新。

至少要更新：

- 支持了哪些观点
- 推翻了哪些观点
- 哪条路径更有效
- 哪个 capability 更适合
- 哪类失败应绑定哪类恢复

## 8.4 讨论

系统在以下情况可以主动发起与人类的讨论：

- 多条路径都可行但价值取舍不同
- 证据冲突
- 长期方向可能需要改变
- 超出当前授权
- 系统对判断长期不稳定

讨论时图谱应提供：

- 候选观点
- 支持与反驳证据
- 分歧点
- 受影响的 strategy / backlog / assignment

---

## 9. 与现有代码边界的关系

本设计不替换现有：

- `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`
  正式主链
- 现有 knowledge activation layer
- 现有 truth-first memory

本设计是在这些基础上增加一个更高层的统一口径：

- activation layer 是任务子图激活机制
- derived index 是总图的可重建派生层
- strategy memory 和 planning chain 是图谱中的正式执行节点
- execution evidence 与 reports 是图谱增长的正式输入

因此，本设计与以下文档互补，而不是替代：

- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- `docs/architecture/working-plans/MEMORY_VNEXT_PLAN.md`
- `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`

---

## 10. 第一阶段完成标准

第一阶段不追求百科式大图谱，只追求主脑闭环可用。

完成标准是：

1. 主脑能稳定获得当前任务子图
2. planner 明确消费任务子图，而不是只消费 prompt 文本
3. execution 能从图谱获得能力、环境、风险与历史经验
4. report / execution 结果能正式回写总图
5. 旧知识支持降权、失效、替换

如果上述 5 条未成立，则只能算“结构化记忆增强”，不能算“正式知识图谱进入主链”。

---

## 11. 最终定义

CoPaw 的内部统一知识图谱应定义为：

> 一套统一的、证据驱动的、可生长的内部认知总图。它以世界、目标、行动、结果为主语，沉淀世界认知、执行认知和人类边界；主脑运行时只激活当前任务子图，执行结束后再把结果和经验写回总图。


## 12. 2026-04-06 实现收口

- 正式图谱真相仍留在现有 truth-first memory 体系内，没有新建第二套图谱真相源。
- canonical graph writeback 现在正式落到三层：
  - `knowledge_chunks`：持久化源真相
  - `memory_fact_index`：活跃节点投影
  - `memory_relation_views`：活跃关系投影
- 旧知识不再只是追加：
  - invalidated node 会被降出 active read path
  - invalidated relation 会被过滤出 activation / planning 读链
- 共享持久化回写已经接到两条主链：
  - report synthesis closeout
  - query execution runtime closeout
