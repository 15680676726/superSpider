# Browser Substrate Pattern Audit And Cutover Design

Date: `2026-04-18`
Status: `draft`
Owner: `Codex`

## 1. Problem

CoPaw 现在已经有真实浏览器能力，但“浏览器底座”还没有收成一个稳定、职业无关、页面无关的正式执行层。

当前真问题不是“完全不能控浏览器”，而是：

- 低层能力已经有了
- channel 也已经有了
- guardrail/evidence 也已经有了
- 但上层真实页面执行还在混着 provider-specific 规则和临时 heuristic

结果就是：

- 一条 Baidu 研究链会长出私有页面规则
- 以后别的职业页也会继续长第二套、第三套私有规则
- live 测试一到真实页面，脆弱定位和回读就开始断

这轮要先把浏览器底座模式审清楚，再定死 cutover 设计，然后再落代码。

## 2. 审计范围与结论

### 2.1 OpenClaw：值得直接借的部分

基于官方 Browser 文档与 AGENTS.default，可确认 OpenClaw 的浏览器底座有 4 个关键特征：

- 浏览器分两条正式路径：
  - managed browser profile
  - existing-session attach path
- 交互默认走 `snapshot -> ref -> act`
  - 优先用快照 ref，不鼓励到处写 CSS selector
- 页面操作和页面观察是同一套正式工具面
  - `snapshot / click / type / drag / select / evaluate`
- “attach 到真实已登录浏览器”是正式模式，但能力弱于 managed path，不假装两者完全等价

这几点和 CoPaw 当前方向是顺的，应该直接借：

1. `managed` 与 `attach-existing-session` 并存
2. ref-first，而不是 selector-first
3. 观察和动作走同一条底座
4. attach 路径能力不足时 fail closed，不硬装成“都能做”

### 2.2 OpenAI computer use / Codex 风格：值得直接借的部分

基于 OpenAI 官方 computer use 文档，可确认它的核心不是“某个网站脚本”，而是统一循环：

1. 给模型任务
2. 模型返回动作
3. 执行动作
4. 回传最新 screen/observation
5. 再决定下一步

这套模式真正值得借的是：

- `observe -> act -> readback -> next-step` 的闭环
- 执行层不替职业 agent 做业务判断
- 高风险、登录、安全警告、CAPTCHA 必须显式 handoff

不该照搬的是：

- 直接把 CoPaw 全部改成 screenshot-only 的 computer-use runtime
- 让视觉 loop 取代现有 `SessionMount / EnvironmentMount / EvidenceRecord`

CoPaw 已经有更强的 state/environment/evidence 主链，不需要重做第二套。

### 2.3 本地 cc 仓库：只能借分层思想，不能借缺失源码

本地 `cc` 仓库可确认两件事：

- `claude-in-chrome` skill 明确要求先读 tabs context，再做浏览器动作
- `WebBrowserTool` 在本地这份仓库里没有可直接复用的完整源码，只能看到文档和 skill 接线

所以这里能借的是：

- 先读当前 browser context
- 再让浏览器工具执行动作
- 浏览器作为 MCP/tool substrate，而不是规划中心

不能借的是：

- 假装本地已经有一套可直接抄的 `WebBrowserTool` 实现

### 2.4 CoPaw 当前底座：已经有的正式能力

当前 CoPaw 自己已经有一条不弱的正式底座：

- `src/copaw/environments/surface_control_service.py`
  - 已有统一 browser/document/windows action routing
- `src/copaw/environments/browser_channel_policy.py`
  - 已明确 `built-in-browser` 与 `browser-mcp`
- `src/copaw/environments/cooperative/browser_companion.py`
  - 已把 attach/companion truth 挂到 environment/session metadata
- `src/copaw/capabilities/browser_runtime.py`
  - 已支持 attach-required fail closed
- `src/copaw/agents/tools/browser_control.py`
  - 已有 `snapshot / click / type / evaluate / screenshot / press_key`

也就是说：

- CoPaw 不缺浏览器通道
- 不缺真实动作
- 不缺 guardrail
- 不缺 evidence 主链

真正缺的是“浏览器上层执行收口层”。

### 2.5 CoPaw 当前真坏味道

当前最典型的坏味道在：

- `src/copaw/research/baidu_page_research_service.py`

这里还残留了几类 provider-specific heuristic：

1. `_resolve_chat_input_target(...)`
   - 用 snapshot 行文本 + DOM 评分去猜输入框
   - 还会临时打 `data-copaw-chat-input`
2. `_read_chat_input_readback(...)`
   - 只从 `[data-copaw-chat-input="1"]` 读回写结果
   - 没把“执行目标”和“读回目标”拆开
3. `_read_baidu_deep_think_state(...)`
   - 全页扫 `button / label / span / div`
   - 靠文本 contains 命中“深度思考”
   - 真实 live 会命中整块容器，不是真开关

这些规则的问题不是“写得丑”，而是它们违反了底座边界：

- 页面观察、目标解析、动作执行、回读验证，本该在共享浏览器底座里
- 现在却被塞进 Baidu provider service 里临时拼

这就是后面一到真实运行就反复断线程、断回读、断开关定位的根因。

## 3. 三种方案

### 方案 A：继续在 Baidu 竖链上补规则

做法：

- 继续在 `BaiduPageResearchService` 里补更多 selector、更多打标、更多 fallback

优点：

- 最快

缺点：

- 继续加私有页面逻辑
- 以后别的职业页还会再长一套
- 与已批准的 universal surface foundation 方向冲突

结论：

- 不采用

### 方案 B：在现有 channel/tool 之上补一层共享 browser substrate

做法：

- 保留现有 `built-in-browser / browser-mcp / surface_control / browser_use`
- 在它们上面新增一层共享浏览器执行底座
- provider 只声明页面语义槽位和局部 profile
- 职业 agent 决策，底座只观察/执行/回读/验证

优点：

- 和当前架构方向一致
- 不推翻现有主链
- 能把 Baidu 当前坏规则收回共享层
- 后续 writer/listing/researcher 都能复用

缺点：

- 需要一次正式 cutover

结论：

- 推荐方案

### 方案 C：直接重做成完整 computer-use 视觉 runtime

做法：

- 直接以 screenshot/vision 为主，重做一套浏览器动作循环

优点：

- 终态想象空间大

缺点：

- 这轮明显过大
- 会和现有 `SessionMount / Evidence / channel_resolution` 重叠
- 容易再长第二套 runtime

结论：

- 现在不做

## 4. 正式设计

### 4.1 总原则

这轮不重做浏览器 runtime，只补共享 browser substrate。

正式边界写死：

- 职业 agent 负责：
  - 目标判断
  - 这一步该做什么
  - 输入什么内容
  - 是否继续深挖
  - 是否停止
- 浏览器底座只负责：
  - 观察当前页面
  - 解析目标
  - 执行动作
  - 回读结果
  - 验证结果
  - 记录证据

### 4.2 层级位置

推荐落位：

- `src/copaw/environments/surface_execution/browser/`

它是：

- `universal surface execution foundation`
  的 browser specialization

它不是：

- 第二个 browser runtime
- 第二个 research runtime
- 第二个 planner

### 4.3 内部模块

建议拆成这些模块：

- `contracts.py`
  - 共享 typed contract
- `observer.py`
  - 当前页面观察
- `resolver.py`
  - 从 observation 中解析目标
- `executor.py`
  - 委托现有 `surface_control` / `browser_use`
- `verifier.py`
  - 统一回读与验证
- `profiles.py`
  - 页面族 profile，不允许职业 service 自己私拼规则
- `service.py`
  - 一步执行 orchestrator

### 4.4 正式 typed contract

至少要有 4 个正式对象：

#### `BrowserObservation`

表示当前页面真实观察结果，至少包括：

- `page_url`
- `page_title`
- `snapshot_text`
- `interactive_targets`
- `primary_input_candidates`
- `control_groups`
- `readable_sections`
- `login_state`
- `blockers`

#### `BrowserTargetCandidate`

表示一个可操作目标，至少包括：

- `target_kind`
  - `input | button | toggle | link | menu | tab | upload`
- `action_ref`
  - 用于真正动作执行
- `action_selector`
  - 仅作为兜底
- `readback_selector`
  - 用于读真实 DOM 状态
- `element_kind`
  - `textarea | input | contenteditable | button | generic`
- `scope_anchor`
  - 目标所在局部区域锚点
- `score`
- `reason`

这里必须显式拆开：

- action target
- readback target

不能再把一个 ref/selector 当成所有事情的唯一真相。

#### `BrowserExecutionStep`

表示职业层要求浏览器做的一步，至少包括：

- `intent_kind`
  - `type | click | toggle | press | read`
- `target_slot`
  - 比如 `primary_input`、`reasoning_toggle`、`submit_button`
- `payload`
- `success_assertion`
- `fallback_policy`

#### `BrowserExecutionResult`

至少包括：

- `status`
  - `succeeded | blocked | failed`
- `resolved_target`
- `before_observation`
- `after_observation`
- `readback`
- `verification_passed`
- `blocker_kind`
- `evidence_ids`

### 4.5 Page Profile 机制

这轮允许 provider/page 有 profile，但不允许职业 service 自己内嵌页面私逻辑。

正确方式是：

- 底座共享一套观察/解析/执行/回读框架
- 页面只提供 profile

比如 Baidu 页 profile 只声明：

- `primary_input`
- `submit_button`
- `reasoning_toggle_group`
- `answer_stream_region`

而不是在 `BaiduPageResearchService` 里直接手写：

- 整页扫什么标签
- 临时塞什么 data attribute
- 命中哪个 div 就算成功

也就是说：

- 允许 profile
- 不允许 provider service 自己拥有浏览器底座

### 4.6 正式执行循环

共享浏览器底座只做这一条循环：

1. `observe`
   - 读取 snapshot + 必要 DOM probe
2. `resolve`
   - 结合 page profile 和 step target slot，得到真实 target candidate
3. `execute`
   - 调 `surface_control` / `browser_use`
4. `readback`
   - 读动作后的真实 DOM/snapshot 状态
5. `verify`
   - 判断 success assertion 是否成立
6. `evidence`
   - 写入统一证据链

这一步完成后，职业 agent 再决定下一步，不由底座接管。

## 5. 照搬 / 替换 / 删除 清单

### 5.1 直接照搬

#### 来自 OpenClaw

- `managed browser` 和 `existing-session attach` 双通道
- `snapshot ref` 作为主操作锚点
- attach 通道能力受限时明确 fail closed
- selector 只做少量兜底，不做主线

#### 来自 OpenAI computer use

- `observe -> act -> readback -> next-step` 闭环
- 高风险登录/安全/破坏性动作明确 handoff

#### 来自 CoPaw 现有底座

- `SurfaceControlService`
- `browser_channel_policy`
- `BrowserCompanionRuntime`
- `browser_use`
- 现有 guardrail/evidence/state 主链

### 5.2 需要替换

1. 把 provider 内私有 DOM heuristic
   - 替换成共享 `observer/resolver/verifier`
2. 把“一个 selector 既负责动作又负责回读”
   - 替换成 `action target + readback target`
3. 把“全页 contains 文本找深度思考”
   - 替换成“先找输入区，再在输入区邻域找 toggle group”
4. 把“页面成功与否由 provider 自己瞎猜”
   - 替换成 typed `success_assertion + verification`

### 5.3 必须删除的旧瞎规则

这轮需要从正式主线删除或退役的旧规则包括：

1. `[data-copaw-chat-input="1"]` 作为唯一输入回读真相
2. `_read_baidu_deep_think_state(...)` 的全页 `button/label/span/div` 扫描命中
3. `_resolve_chat_input_target(...)` 里 provider 私有的输入框打标回读逻辑
4. `BaiduPageResearchService` 自己拥有“浏览器目标解析器”的事实

## 6. Cutover 顺序

### Stage 1：先落共享 browser substrate 壳

- 新增 browser substrate 模块
- 先不改职业决策层
- 让它能跑通：
  - observe
  - resolve input
  - resolve local toggle
  - readback value

### Stage 2：先迁 Baidu 的两个真问题

第一批只迁：

- 聊天输入目标解析/回读
- 深度思考 toggle 定位/验证

因为这两处已经被 live 验证打实。

### Stage 3：把 Baidu provider service 降级

让 `BaiduPageResearchService` 只保留：

- 研究 session orchestration
- round management
- research synthesis
- provider page profile usage

不再直接拥有浏览器底层 heuristic。

### Stage 4：再扩到其他职业页面

后续再用同一底座证明：

- researcher
- writer
- listing operator

但那是下一步扩面，不是本轮先决条件。

## 7. 验收标准

### L1

- resolver/verifier 单测
- `action target` 与 `readback target` 分离测试
- scoped toggle 定位测试

### L2

- browser substrate 对 `built-in-browser` 和 `browser-mcp` 都能跑通
- `BaiduPageResearchService` 已改为调用共享 substrate

### L3

真实浏览器 live 验收至少要证明：

- 同一对话框连续多轮追问不重开线程
- 输入回读准确
- 深度思考只命中真实开关
- 登录失效时正确收口 `waiting-login`

### L4

长时间 soak 至少证明：

- 连续多轮 follow-up 不因 stale ref 乱掉
- 跨重启后 attach/session 还能接回
- built-in 与 attach 两条通道不会串状态

## 8. 本轮不做的事

- 不把整个 CoPaw 改成 screenshot-only runtime
- 不重做第二套 browser session model
- 不在 provider service 里继续加特例
- 不先扩 writer/listing，再回来补底座

## 9. 最终结论

这轮正确方向不是：

- 继续补 Baidu 私有脚本
- 也不是重做第二套 computer-use runtime

而是：

在 CoPaw 已有 `channel + tool + guardrail + evidence + state` 主链之上，
正式补一层共享 browser substrate，
把当前已经被 live 打实的私有 heuristic 收回共享层，
再让职业 agent 继续只负责目标判断和步骤决策。

## 10. 审计参考

- OpenClaw Browser tool:
  - `https://docs.openclaw.ai/tools/browser`
- OpenAI computer use:
  - `https://platform.openai.com/docs/guides/tools-computer-use`
- 本地 cc 参考：
  - `cc/src/skills/bundled/claudeInChrome.ts`
  - `cc/README.md`
  - `cc/README_CN.md`
- CoPaw 当前正式底座：
  - `src/copaw/environments/surface_control_service.py`
  - `src/copaw/environments/browser_channel_policy.py`
  - `src/copaw/environments/cooperative/browser_companion.py`
  - `src/copaw/capabilities/browser_runtime.py`
  - `src/copaw/agents/tools/browser_control.py`
  - `src/copaw/research/baidu_page_research_service.py`
