# Active Surface State Graph, Capability Twin, And Reward Engine Design

## 0. 文档目的

这份文档用于把 `CoPaw` 当前“页面理解 / surface 操作”这条线，从：

- 看页面
- 找输入框
- 点按钮
- 回读一点文本

升级成更高一层的正式设计：

- 先编译当前 surface 的局部状态真相
- 对不确定区域主动探测
- 记录动作前后状态转移
- 归并成“这个系统能做什么”的能力孪生
- 再按当前职业目标做收益排序

这份设计不是第二套主链，也不是给 browser / desktop / document 各造一套平行 runtime。

它必须继续回映到仓库现有正式对象：

- `EnvironmentMount`
- `SessionMount`
- `CapabilityMount`
- `RuntimeFrame`
- `EvidenceRecord`
- `StrategyMemory`
- `OperatingLane / BacklogItem / Assignment / AgentReport`

一句话：

> 目标不再是“更会看页面”，而是“更会逆向理解一个系统的能力、状态和高价值路径”。

---

## 1. 为什么旧问题定义不够

当前问题如果被定义成：

- “怎么 100% 看懂任何页面”
- “怎么用截图 + 元素树一次性理解所有内容”

方向会越做越偏。

原因很直接：

1. 页面/应用/文档的“全部内容”本来就不是一次观察能拿全的。
2. 截图只能看到当前一帧，结构树也不等于业务真相。
3. 真正影响执行成败的，不是“看到多少像素”，而是：
   - 当前处于什么状态
   - 哪些动作现在可做
   - 做完会变成什么状态
   - 哪条路径对当前目标最值

所以正式问题定义要改成：

> 系统能不能围绕当前目标，持续建立、验证、更新一份可执行的局部状态真相，并在此基础上学会这个软件/页面/文档系统的高价值能力路径。

---

## 2. 新目标

新的正式目标不是 `page understanding engine`，而是：

## `Active Surface State Graph + Capability Twin + Reward Engine`

拆开看有三层：

1. `Surface State Graph`
   - 当前 surface 的局部状态图
   - 不是静态截图，不是原始 DOM dump

2. `Capability Twin`
   - 长期归并出来的“这个系统有哪些能力、怎么进入、前置条件是什么、会产生什么结果”

3. `Reward Engine`
   - 在当前职业目标下，对能力路径做收益和风险排序

这三层加起来，才是“会做事的职业 agent 底座”。

---

## 3. 核心原则

### 3.1 结构真相优先，视觉只补盲

浏览器、文档、桌面应用都不应该把截图当唯一真相。

优先级固定为：

1. 结构信号
2. 可读文本
3. 交互元素/控件
4. 视觉截图补盲

截图负责补：

- canvas
- 自绘控件
- 图标状态
- 颜色/禁用态
- 版面关系

### 3.2 不追求“一眼看懂一切”

系统第一次进入一个 surface 时，只需要先回答：

1. 当前处于什么状态
2. 哪些动作可做
3. 哪些区域不确定
4. 下一步该探什么

### 3.3 底座不决策，职业 agent 决策

执行底座只负责：

- 观察
- 探测
- 执行动作
- 回读验证

职业 agent 负责：

- 目标
- 优先级
- 是否继续探测
- 哪条路径收益更高

### 3.4 一切动作都必须可证据化

每次探测和执行都必须能回映到正式证据链：

- 动作前状态
- 动作
- 动作后状态
- diff
- 结论

### 3.5 不引入第二真相源

`Surface State Graph` 和 `Capability Twin` 不能变成散落在 tool 私有缓存里的第二套 runtime。

要求：

- live 当前态回映到 `EnvironmentMount / SessionMount / RuntimeFrame`
- 动作证据回映到 `EvidenceRecord`
- 长期归并结果回映到 learning/state 正式对象

---

## 4. 正式架构

## 4.1 Layer A: Surface Observation Compiler

职责：

- 从多源观察构建统一的 surface 观察输入
- 把浏览器/文档/桌面应用压成同一种“可消费结构”

输入源：

### 浏览器

- DOM / snapshot
- `document.body.innerText`
- accessibility tree
- 当前交互元素
- 路由/url/title
- 截图

### 文档

- 原始文本
- 段落/标题/表格结构
- 元数据
- 渲染截图或版面快照

### 桌面应用

- UIA / accessibility tree
- 控件树
- 窗口信息
- 焦点状态
- 截图

输出不是原始数据，而是统一观察片段：

- `text_blocks`
- `interactive_controls`
- `state_indicators`
- `blockers`
- `regions`
- `visual_hints`

这层是“统一输入编译器”，不是决策器。

## 4.2 Layer B: Surface State Graph

职责：

- 把 observation 编译成“当前局部状态图”
- 让上层不再直接面对零散文本和零散元素

一个最小 `Surface State Graph` 应包含：

- 当前状态节点
- 当前可做动作
- 当前阻塞
- 关键区域
- 结果区
- 关键对象
- 关键关系
- 置信度

节点类型建议统一为：

- `surface`
- `region`
- `text`
- `control`
- `indicator`
- `blocker`
- `result`
- `entity`

边类型建议统一为：

- `contains`
- `adjacent_to`
- `controls`
- `updates`
- `blocks`
- `belongs_to`
- `suggests`

注意：

这层不是要持久化“整个网页的完整镜像”，而是生成“当前任务足够用的局部图”。

## 4.3 Layer C: Probe Engine

职责：

- 当状态图不够确定时，执行低风险主动探测
- 补齐隐藏内容和不确定区域

Probe 不是业务动作，而是“为了看清楚”的动作。

正式探针类型建议包括：

- `scroll`
- `expand`
- `hover`
- `focus`
- `open-tab`
- `open-panel`
- `open-dropdown`
- `open-detail-and-return`
- `paginate`
- `refresh-local-region`

规则：

- 如果某个关键节点置信度不足，不允许直接做高价值动作
- 先 probe，再重编译 state graph

这层是整套架构的关键差异点。

没有 probe，就还是“半瞎操作”。

## 4.4 Layer D: Transition Miner

职责：

- 记录每个动作带来的状态变化
- 不再只记“执行成功/失败”
- 而是记“状态从 A 变到 B”

正式记录内容应包括：

- `before_state_graph_ref`
- `action`
- `after_state_graph_ref`
- `changed_nodes`
- `new_blockers`
- `resolved_blockers`
- `result_summary`
- `evidence_refs`

这层是后面做 capability twin 的原材料。

因为真正重要的不是“这个按钮叫提交”，而是：

> 点完这个动作，会把系统从“草稿态”推进到“已发布态”。

## 4.5 Layer E: Capability Twin

职责：

- 从大量状态转移中归并出“这个系统有哪些正式能力”
- 让系统学会一个网站/应用，而不是每次重新看页面

一个正式 `Capability Twin` 至少描述：

- `capability_name`
- `capability_kind`
- `entry_conditions`
- `entry_regions`
- `required_state_signals`
- `probe_steps`
- `execution_steps`
- `result_signals`
- `risk_level`
- `evidence_examples`
- `failure_modes`

例子，不是“有个按钮”：

- 发布商品
- 批量改价
- 提交审核
- 导出订单
- 发起营销活动
- 上传小说章节
- 调整文档结构
- 在桌面应用中完成某类录入

这层一旦建立，职业 agent 就不需要每次从零摸页面。

## 4.6 Layer F: Reward Engine

职责：

- 按当前职业目标，对 capability twin 做收益排序

注意：

reward 不是固定写死的“哪个能力永远最好”。

它必须依赖上层正式目标：

- `StrategyMemory`
- `OperatingLane`
- 当前 `Assignment`
- 当前 role/profession 的 success criteria

因此它更准确地说，是：

## `Goal-Conditioned Capability Ranking`

输出内容：

- 当前最值得探索的能力
- 当前最值得执行的能力
- 预估收益
- 风险级别
- 预估成本
- 推荐顺序

这层才真正回答：

> 怎么得到更多结果、更大利益

---

## 5. 正式对象映射

为了不造第二套世界，这套设计必须映射回现有正式对象。

## 5.1 当前态映射

### `SurfaceGraphSnapshot`

建议性质：

- 正式 runtime 派生对象
- 初期可以先作为 `RuntimeFrame` / `SessionMount` 的 typed projection
- 不建议一开始单独发明一套孤立 sqlite 表

承载内容：

- 当前局部状态图
- 当前 probe 结论
- 当前 blockers
- 当前可执行动作摘要

## 5.2 动作证据映射

### `SurfaceProbeEvidence`
### `SurfaceTransitionEvidence`

建议性质：

- 不新造旁路日志
- 直接归入 `EvidenceRecord`

evidence kind 建议新增：

- `surface-probe`
- `surface-transition`
- `surface-discovery`

## 5.3 长期知识映射

### `SurfaceCapabilityTwinRecord`

建议性质：

- learning/state 正式对象
- 属于“长期归并知识”
- 不属于短期 live runtime

作用域：

- `site`
- `application`
- `document_family`
- `role_scope`
- `industry_scope`

### `SurfacePlaybookRecord`

建议性质：

- `Capability Twin` 的可执行精简投影
- 供职业 agent 快速消费

### `RewardProfile`

不建议作为新顶级对象单独发明。

应该来自现有正式对象派生：

- `StrategyMemory`
- `OperatingLane`
- `Assignment`
- `role blueprint`

---

## 6. 三类 surface 的统一表达

## 6.1 浏览器

浏览器不是“看 DOM”这么简单。

正式要统一表达的，是：

- 当前页面状态
- 可交互区域
- 结果区
- 阻塞区
- 登录/授权状态
- 详情页/列表页/编辑页/提交流程

截图在浏览器里只做补盲，不做唯一真相。

## 6.2 文档

文档不应该只被当成“一个文本文件”。

正式要统一表达的，是：

- 正文结构
- 标题层级
- 表格/列表/段落
- 关键实体
- 当前修改目标
- 修改前后 diff

文档的终态不是“能写文本”，而是“理解文档结构并可验证改动结果”。

## 6.3 桌面应用

桌面应用不应该只被当成：

- 找窗口
- 聚焦
- 输入

正式要统一表达的，是：

- 当前窗口状态
- 当前工作区块
- 当前可见控件关系
- 当前结果区/状态区
- 当前 modal/blocker

这意味着 desktop 不能长期停留在“控件树 + 输入框”级别。

---

## 7. 执行流

一个统一执行回合应按下面的顺序：

1. `observe`
   - 多源观察当前 surface

2. `compile`
   - 生成当前 `Surface State Graph`

3. `score uncertainty`
   - 标出哪些关键区域不确定

4. `probe if needed`
   - 低风险探测补图

5. `rank capabilities`
   - capability twin 给出当前可行能力

6. `rank by reward`
   - 结合职业目标做优先级排序

7. `act`
   - 执行真正业务动作

8. `reobserve`
   - 重建图谱

9. `diff`
   - 记录状态转移

10. `learn`
   - 更新 capability twin / playbook

这套流比“读页面 -> 直接点”多了 4 个关键层：

- compile
- probe
- diff
- learn

---

## 8. 电商案例

如果职业 agent 是电商运营，这套设计的目标不是让它“会点电商后台页面”。

而是让它逐步学会：

- 这个后台有哪些能力
- 哪些能力和曝光/点击/转化/GMV 相关
- 哪些路径风险更低
- 哪些能力值得优先使用

第一次进入后台时，系统不需要立刻开始“帮你做运营”。

它可以先：

1. 发现模块
   - 商品
   - 订单
   - 广告
   - 数据
   - 营销
   - 客服

2. 探测入口
   - 发布
   - 编辑
   - 筛选
   - 导出
   - 促销
   - 投流

3. 记录状态转移
   - 从商品列表进到商品编辑
   - 从草稿变成待审核
   - 从广告页进入投放配置

4. 归并能力 twin
   - 批量改价
   - 更新标题
   - 提交活动
   - 查看转化结果

5. 按当前目标排序
   - 如果目标是提升点击率，优先内容和标题相关路径
   - 如果目标是清库存，优先价格和活动路径
   - 如果目标是提升 GMV，优先高影响低风险组合路径

这才是“职业 agent 真正会用后台”的样子。

---

## 9. 与现有仓库的关系

这套设计不是要推翻现有 `shared surface substrate`。

当前已经存在的基线应该保留：

- `observe`
- `execute`
- `reobserve`
- `guided owner`
- browser/document/desktop frontdoor
- evidence sink

这次真正新增的是上层：

- `surface_graph`
- `probe_engine`
- `transition_miner`
- `capability_twin`
- `reward_engine`

所以它是：

> 在现有 shared surface substrate 之上，补一层“状态理解 + 主动探测 + 能力归并 + 收益排序”。

不是重写 browser/document/desktop 底座。

---

## 10. 分阶段落地

## Phase 1: Surface Graph Baseline

目标：

- 浏览器 / 文档 / 桌面统一输出最小 `SurfaceGraphSnapshot`
- 当前 blockers / regions / controls / results 可见化

这阶段不追求长期学习。

## Phase 2: Probe Engine

目标：

- 支持通用低风险探测动作
- 状态不确定时先 probe，不再盲执行

## Phase 3: Transition Mining

目标：

- 正式记录动作前后状态差分
- 不再只记“点了成功”

## Phase 4: Capability Twin

目标：

- 归并站点/应用/文档系统的高层能力
- 形成可复用 playbook

## Phase 5: Reward Engine

目标：

- 接 strategy / lane / assignment
- 让职业 agent 真正能做“高价值路径选择”

---

## 11. 正式边界

### 11.1 不做的事

这份设计不承诺：

- 一次观察就 100% 看懂整个系统
- 底座自己决定商业目标
- 用截图替代所有结构读取
- 让 browser / desktop / document 各玩各的

### 11.2 必须坚持的边界

- 底座只负责观察/探测/执行/回读
- 职业 agent 负责目标和决策
- reward 必须来自正式目标，不得脱离 `StrategyMemory / Lane / Assignment`
- 所有学习结果都要留证据和版本

---

## 12. 验收口径

这套设计后续验收必须按 `UNIFIED_ACCEPTANCE_STANDARD.md` 分层：

### `L1`

- state graph 编译规则
- probe 选择规则
- diff 规则
- capability twin 归并规则
- reward ranking 规则

### `L2`

- browser/document/desktop 的统一 graph 合同
- probe -> reobserve -> diff -> evidence 主链合同
- capability twin 写链与读链一致

### `L3`

- 真浏览器页面探索
- 真文档读写与结构回读
- 真桌面应用窗口探索
- Runtime Center / query read surface 能看到同一份正式状态

### `L4`

- 多轮探索后 state graph 不脏
- capability twin 不串 scope
- reward ranking 不被旧缓存/旧 fallback 冲掉
- 重启/恢复/并发后仍能续上同一条 surface 学习链

---

## 13. 最终结论

如果继续把目标定义成：

- “更强截图理解”
- “更强页面识别”

最终只会得到一个更复杂的自动点点点系统。

真正值得做的终态是：

> 让 `CoPaw` 学会把浏览器、文档、桌面应用都看成“可被逆向编译的状态系统”，再从状态转移里归并能力，并按职业目标做收益排序。

所以这次正式推荐方向是：

## `Active Surface State Graph + Capability Twin + Reward Engine`

它比“页面理解器”更接近真正长期自治的执行底座。
