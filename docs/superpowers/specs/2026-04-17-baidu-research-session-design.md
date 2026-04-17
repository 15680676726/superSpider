# CoPaw 百度多轮研究会话设计

日期：`2026-04-17`

---

## 0. 目标

这次不是简单“接一个百度聊天入口”，也不是做一个只会贴链接的 researcher。

这次要做的是把：

- `主脑发现信息缺口`
- `researcher 去百度页多轮深挖`
- `继续点在线链接`
- `必要时下载资料继续读`
- `整理成正式研究汇报`
- `再按稳定度分流到 report / evidence / work_context / industry`

真正收成一条正式研究主链。

一句话目标：

> 让 researcher 具备“短期多轮研究会话”能力，能围绕一个明确研究目标在同一研究线程里持续问答、深挖网页和资料，并把整理后的结果稳定汇报给主脑，而不是停留在一次问答或聊天解释层。

---

## 1. 这次要解决的真问题

当前系统已经具备：

- researcher 默认研究位
- `tool:browser_use` 正式浏览器执行能力
- 下载校验与浏览器 evidence 链
- `knowledge / memory / graph / sleep` 的正式真相层
- `AgentReport` 正式汇报链

但还缺一条完整闭环：

1. researcher 现在能用浏览器，但没有“多轮研究会话”这个正式对象
2. 百度页回答目前最多只能作为一次结果，不是可持续深挖的短期研究 session
3. 没有把“百度回答 -> 链接深挖 -> 下载资料 -> 汇报主脑”收成统一主链
4. 没有把研究结果按稳定度正式分流到 `evidence / report / work_context / industry`
5. 没有明确处理“未登录 / 页面改版 / 连续无新增信息”的停止边界

所以这次要补的不是“再多一个搜索入口”，而是 researcher 的正式研究会话能力。

---

## 2. 设计结论

### 2.1 正式对象

这次新增两个正式对象：

- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`

它们只负责“短期研究会话”，不是新的知识库，也不是新的记忆真相源。

### 2.2 researcher 与主脑边界

- `主脑` 负责判断是否需要外部研究，以及是否采纳结果
- `主脑` 必须先形成正式研究 brief / monitoring brief，再把任务交给 researcher
- `researcher` 负责执行研究会话、深挖网页与资料、整理研究汇报
- `researcher` 不是第二规划中心，不能自己决定“今天去研究什么”
- 百度回答不是正式真相，只是研究过程中的外部输入
- researcher 不能直接把百度结果写成正式最终事实，必须先汇报给主脑
- 一个合格的 research brief 至少要说明：
  - 为什么要查
  - 服务哪个目标 / assignment / work context
  - 这次要查什么范围
  - 期望产出是什么
  - 什么时候停止

### 2.3 统一主链

三类入口都必须汇到同一条 research session 主链：

- 用户聊天手动触发
- 主脑在运行中发现信息不足时临时追问
- 主脑或用户明确创建的监控任务触发

它们的差别只体现在 `trigger_source`，不体现在执行主链。

这里明确排除一种旧口径：

- 不存在 researcher 因为“属于某个行业”就每天自动做一次通用巡检
- 如果需要定时执行，也必须先有明确 monitoring brief，再由 schedule 负责唤醒

---

## 3. 总结构

这次保持单一真相源，不新增第二执行中心：

1. 研究请求层
   - 负责创建一次研究目标
   - 入口可来自主脑、手动、或已存在的监控任务

2. 研究会话层
   - 负责多轮研究状态、轮次、停止条件、链接和下载记录
   - 对象是 `ResearchSessionRecord / ResearchSessionRoundRecord`

3. 页面与资料执行层
   - researcher 通过百度页面发问
   - 继续深挖引用网页
   - 必要时下载资料并读取文本

4. 汇报层
   - researcher 把本轮研究整理成正式 `AgentReport`
   - 主脑读取 report 再决定是否采纳

5. 沉淀层
   - 高价值结果按稳定度分流到：
     - `evidence`
     - `work_context memory`
     - `industry knowledge`
   - 这一步不新增新的 truth store

---

## 4. ResearchSession 正式模型

### 4.1 ResearchSessionRecord

一个 `ResearchSessionRecord` 应至少包含：

- `id`
- `provider`
  - 当前固定为 `baidu-page`
- `industry_instance_id`
- `work_context_id`
- `owner_agent_id`
  - 默认是 researcher
- `supervisor_agent_id`
  - 默认是主脑
- `trigger_source`
  - `user-direct / monitoring / main-brain-followup`
- `goal`
  - 这次到底要研究什么
- `status`
  - `queued / running / waiting-login / deepening / summarizing / completed / failed / cancelled`
- `browser_session_id`
- `round_count`
- `link_depth_count`
- `download_count`
- `stable_findings`
- `open_questions`
- `final_report_id`
- `failure_class`
- `failure_summary`
- `created_at / updated_at / completed_at`

### 4.2 ResearchSessionRoundRecord

一个 `ResearchSessionRoundRecord` 应至少包含：

- `id`
- `session_id`
- `round_index`
- `question`
- `generated_prompt`
- `response_excerpt`
- `response_summary`
- `raw_links`
- `selected_links`
- `downloaded_artifacts`
- `new_findings`
- `remaining_gaps`
- `decision`
  - `continue / stop / login_required / failed`
- `evidence_ids`
- `created_at`

### 4.3 为什么必须落正式表

因为这条链天然有：

- 多轮状态
- 等待登录
- 浏览器连续会话
- 重启恢复
- 中途失败继续追查

如果不进正式状态层，后面一定会出现：

- 主脑看不到当前研究做到哪
- researcher 重启后忘记做到第几轮
- 链接/下载和最终汇报对不上

---

## 5. 多轮研究会话流程

### 5.1 会话主流程

一次标准研究会话按以下顺序运行：

1. 主脑或手动入口，或已存在的监控任务入口，创建或复用同一条 `ResearchSession`
2. researcher 打开百度聊天页并检查登录
3. 进入第 1 轮总问题提问
4. 从回答中识别：
   - 新增信息
   - 还没回答清楚的问题
   - 值得继续点开的链接
   - 值得下载的资料
5. 根据缺口继续下一轮追问或外链深挖
6. 达到停止条件后进入总结阶段
7. researcher 生成正式研究汇报给主脑
8. 主脑决定采纳、继续追问、还是转成 backlog / assignment / decision
9. 高价值内容再分流到正式沉淀层

### 5.2 多轮研究不是无限对话

researcher 和百度的关系应该是：

> 一个围绕单一研究目标持续推进、以“问题问清”为主停止条件、以安全上限为兜底的短期研究会话

不是：

- 一次问答就结束
- 也不是无穷无尽地追问

### 5.3 停止条件

第一版应写死的是“安全上限”，不是“主停止逻辑”：

- 主停止逻辑：当前研究问题已经问清，关键缺口已补齐，继续追问只会重复
- 默认 follow-up 必须优先复用同一条 active `ResearchSession`
- 同一条 active `ResearchSession` 必须优先复用同一百度 chat thread，而不是每轮新开对话
- 单次 `run_session(...)` 最多推进 `5` 轮百度追问，只作为安全上限，不限制同一研究线程后续再次 resume
- 最多深挖 `3` 个在线网页，只作为安全上限
- 最多下载 `2` 个文档，只作为安全上限
- 连续 `2` 轮没有新增有效信息时可触发停止评估，但不应先于“问题是否问清”的判断
- 达到总时长上限则强制停止

---

## 6. 提问策略

### 6.1 动态生成，格式写死

问题内容应动态生成，但要求百度输出固定结构：

1. 结论摘要
2. 关键事实
3. 当前不确定点 / 风险点
4. 建议继续看的来源链接
5. 如果信息不足，明确说信息不足

### 6.2 第一轮与后续轮的区别

- 第 1 轮先问总问题，建立全局框架
- 第 2 轮开始只追当前最关键的缺口
- 如果已有高价值链接，优先先读链接
- 如果已有高价值资料，优先先读资料
- 已经形成稳定结论时，不再为了“多轮”而硬追问

---

## 7. 百度回答之后如何继续深挖

### 7.1 网页深挖

从百度回答中抽取在线链接后：

- researcher 最多选择 `3` 个高价值链接继续打开
- 优先级应考虑：
  - 官方来源
  - 高信息密度
  - 当前目标相关度
  - 可读性与稳定性

网页深挖要提取：

- 页面标题
- 来源站点
- 发布时间
- 正文摘要
- 原文关键片段
- 可继续下载的资料链接

### 7.2 文档深挖

如果网页提供：

- `pdf`
- `txt`
- `md`
- `csv`
- `xlsx`

且价值高，则 researcher 最多再选择 `2` 个继续下载。

下载后第一版应支持：

- 读取文本
- 提取标题/来源
- 提取关键信息片段
- 把结果并回当前 research session

### 7.3 下载不是终点

下载文档只是研究过程中的动作，不是研究终点。

统一终点永远是：

> researcher 整理后汇报给主脑

---

## 8. 登录与失败边界

### 8.1 登录边界

第一版默认 researcher 复用本机已经登录好的百度账号状态。

如果未登录：

- research session 状态变为 `waiting-login`
- researcher 不瞎编，不继续研究
- 主脑在聊天中提示用户登录百度

### 8.2 失败分类

失败必须显式分型：

- `login_required`
- `page_contract_missing`
- `response_timeout`
- `extract_partial`
- `download_failed`
- `no_useful_answer`
- `guardrail_blocked`

### 8.3 失败也要留证据

失败时至少保留：

- 页面截图
- 关键 DOM snapshot
- 原始回答文本或错误文本
- 对应 session / round 锚点

---

## 9. researcher 最终输出给主脑的结构

每次研究会话结束后，必须形成一份正式 researcher report。

固定输出至少包含：

- `研究结论`
- `关键依据`
  - 网页、文档、原文片段、链接
- `当前仍不确定的点`
- `建议下一步`
- `建议沉淀位置`
  - 哪些进 `work_context`
  - 哪些进 `industry`
  - 哪些只留 `evidence/report`

也就是说，researcher 最终返回的不是散乱原文，而是：

> 可被主脑判断、采纳、继续追问和正式沉淀的结构化研究汇报

---

## 10. 研究结果如何沉淀

### 10.1 evidence

所有研究动作都要至少落证据：

- 原问题
- 回答摘要
- 原文片段
- 网页链接
- 下载文件
- 页面截图

### 10.2 report

每次正式研究会话结束必须产出 `AgentReport`。

### 10.3 work_context memory

当前任务连续推进强相关的研究结果，优先沉到 `work_context`。

典型内容：

- 当前项目用到的术语
- 当前项目采用的规则口径
- 当前项目的关键约束
- 当前项目必须连续记住的设定

### 10.4 industry knowledge

稳定、跨多个任务可复用、带明确来源的研究结果，才允许沉到 `industry knowledge`。

典型内容：

- 平台规则
- 稳定方法论
- 通用术语体系
- 行业基础概念
- 持续有效的官方说明

### 10.5 不允许的错误

不允许把：

- 百度一次回答
- 未核实的软文
- 当前一轮的模糊推测

直接写成正式长期真相。

---

## 11. 前台可见化

第一版前台只做最小可见化，不做复杂研究工作台。

### 11.1 聊天页

聊天页至少能显示：

- `百度研究中`
- `待登录百度`
- `研究已完成`
- `研究失败`

### 11.2 Runtime Center

researcher 卡片至少显示：

- 当前研究状态
- 当前研究目标
- 当前第几轮
- 是否等待登录
- 最近一次研究汇报时间

点击 researcher 后可见：

- 当前研究会话摘要
- 最近几轮问答
- 已选链接
- 已下载资料
- 最终汇报摘要

---

## 12. 代码边界

### 12.1 推荐 owner

推荐新增：

- `src/copaw/research/models.py`
- `src/copaw/research/baidu_page_contract.py`
- `src/copaw/research/baidu_page_research_service.py`

### 12.2 不该落的地方

不应该把整套逻辑继续散落在：

- `main_brain_chat_service.py`
- `compiler.py`
- 前端页面组件
- 临时 browser 脚本

这些位置只能做：

- 入口路由
- 状态展示
- metadata 透传

真正的多轮研究 owner 必须集中。

---

## 13. 验收标准

只有同时满足这些，才算这轮真正完成：

1. 百度研究是正式多轮会话，不是一问一答
2. 可以继续点在线链接深挖
3. 可以处理高价值下载资料
4. research session 可以重启恢复
5. 未登录时会正确停在 `waiting-login` 并提示用户登录
6. researcher 最终会统一汇报给主脑
7. 研究结果可以按稳定度分流到 `evidence / work_context / industry`
8. 手动触发、监控任务触发、主脑追问三条入口都能走通
9. 有真实 live smoke，不只是单元测试

---

## 14. 本轮明确不做

第一版先不做这些：

- 百度私有接口抓包直连
- 无限制网页爬虫扩散
- 视频 / 音频 / 多模态资料解析
- 压缩包深度拆包
- 复杂私有登录文件区自动绕过
- 新的平行知识库 UI 系统

这轮只把 researcher 的百度多轮研究主链做完整、做稳定。
