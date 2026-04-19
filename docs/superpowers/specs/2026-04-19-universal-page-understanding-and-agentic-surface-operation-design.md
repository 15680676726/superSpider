# Universal Page Understanding And Agentic Surface Operation Design

Date: `2026-04-19`
Status: `draft`
Owner: `Codex`

## 1. Problem

CoPaw 现在已经有真实的浏览器/文档/桌面动作能力，也已经有 environment、runtime、evidence 主链。

但它还没有真正达到这两个目标：

1. 通用页面理解
2. 职业 agent 非固定模式操作

当前真实状态不是“完全不会操作页面”，而是：

- 低层动作已经有
- source collection 前门已经有
- 浏览器共享底座已经起了一个头
- 但页面理解仍然主要依赖 provider/service 手工喂候选目标
- 职业 agent 还没有站在共享 surface 底座之上做正式的 `observe -> decide -> act -> reobserve` 循环

这导致系统现在更像：

- “共享底座 + 若干 provider 专用页面逻辑”

而不是：

- “职业 agent 自己理解当前页面语义，底座负责执行”

## 2. 当前代码真相

### 2.1 已经有的能力

- 真实浏览器动作能力：
  - `src/copaw/agents/tools/browser_control.py`
- 跨 browser/document/windows app 的统一动作路由：
  - `src/copaw/environments/surface_control_service.py`
- 新浏览器 substrate 基线：
  - `src/copaw/environments/surface_execution/browser/contracts.py`
  - `src/copaw/environments/surface_execution/browser/observer.py`
  - `src/copaw/environments/surface_execution/browser/resolver.py`
  - `src/copaw/environments/surface_execution/browser/verifier.py`
  - `src/copaw/environments/surface_execution/browser/service.py`
- profession agent 统一外部采集前门：
  - `src/copaw/kernel/query_execution_tools.py`
  - `src/copaw/app/runtime_bootstrap_domains.py`
  - `src/copaw/research/source_collection/*`

### 2.2 还没达到目标的关键原因

#### A. 页面理解仍然不是通用语义理解

`observer.py` 当前主要是把上层传进来的 `dom_probe` 组装成 `BrowserObservation`。

这意味着：

- 它还不是真正从页面 runtime/snapshot 自己抽取统一语义结构
- 它更像“别人先告诉它哪里能点、哪里能输，它再接一下”

#### B. resolver 仍然只有少数固定槽位

`resolver.py` 当前只稳定支持：

- `primary_input`
- `reasoning_toggle`

这不够支撑通用页面操作。

真正通用的页面操作至少要能收口：

- 主输入区
- 提交按钮
- 结果列表
- 列表项
- 翻页
- 筛选区
- 下载入口
- 弹窗确认/取消
- 登录态 blocker

#### C. 共享 service 只有一步，没有正式循环

`BrowserSurfaceExecutionService.execute_step(...)` 现在本质还是：

- observe
- resolve
- execute
- readback

但它还没有成为正式的循环 owner：

- 没有多步 `reobserve`
- 没有职业 agent 的下一步决策接口
- 没有 stop condition contract

#### D. provider-specific 页面逻辑还留在 Baidu service

`src/copaw/research/baidu_page_research_service.py` 里目前仍保留：

- `_build_baidu_surface_context(...)`
- `_select_chat_input_ref(...)`
- `#chat-textarea`
- `data-copaw-deep-think`

这说明当前 heavy 链路仍然是：

- Baidu service 自己做页面观察/提示/定位

而不是：

- 共享 surface foundation 负责观察和执行
- Baidu service 只负责研究 session orchestration 和薄 page profile

#### E. 新 substrate 还没有统一到 document/desktop

当前 `src/copaw/environments/surface_execution/` 下面只有 `browser/`。

但设计目标要求的是：

- browser
- document
- desktop/windows-app

要逐步收进同一套 surface execution contract，而不是只有 browser 一条新路、其他两条继续停在旧语义里。

#### F. 证据链还没进 substrate 正式主链

`BrowserExecutionResult` 已经预留了 `evidence_ids`，但当前 browser substrate service 并没有真的写统一 evidence。

结果是：

- 动作执行了
- readback 也有了
- 但“为什么点这个、点完看到什么、验证是否通过”还没有正式 evidence truth

## 3. 目标边界

这轮正式目标不是：

- 重做第二套 browser runtime
- 重做 screenshot-only computer use
- 重做第二套 planner
- 把 provider service 彻底删光

这轮正式目标是：

1. 建一套通用 surface observation/execution contract
2. 让职业 agent 通过这套 contract 自己决定下一步
3. 把 provider-specific 页面逻辑降成薄 page profile
4. 把 browser/document/desktop 逐步收进同一语义边界
5. 把动作真相正式写入 evidence/runtime 主链

## 4. 正式设计

### 4.1 分层

#### 第一层：职业 agent 决策层

负责：

- 当前目标是什么
- 现在需要读页面的哪一块
- 下一步做什么
- 要不要继续
- 什么时候停止

不负责：

- 直接手搓 selector
- 自己当浏览器 driver

#### 第二层：通用 surface foundation

负责：

- 当前页面/窗口观察
- 目标候选归一
- 动作执行
- readback
- verification
- evidence

不负责：

- 业务规划
- 研究结论
- 职业判断

#### 第三层：page/app profile

允许存在，但只能是薄提示层。

负责：

- 声明页面特有的 probe
- 声明局部 control group
- 声明某些槽位的优先识别规则

不负责：

- 直接拥有整套观察/执行逻辑
- 替代共享 resolver/service

### 4.2 正式对象

当前 browser substrate 要补强为以下正式对象。

#### `BrowserObservation`

当前页面/标签页统一观察结果。

最少应稳定包含：

- `page_url`
- `page_title`
- `snapshot_text`
- `interactive_targets`
- `readable_sections`
- `control_groups`
- `login_state`
- `blockers`
- `slot_candidates`

补充目标：

- 当没有 provider 手工喂候选时，也能从 snapshot/ref/runtime probe 生成基础候选

#### `BrowserTargetCandidate`

统一目标候选对象。

至少包含：

- `target_kind`
- `action_ref`
- `action_selector`
- `readback_selector`
- `element_kind`
- `scope_anchor`
- `score`
- `reason`
- `metadata`

其中 `metadata` 至少允许承载：

- `target_slots`
- `group_kind`
- `enabled`
- `label`
- `is_page_wide`

#### `BrowserExecutionStep`

职业层给底座的一步动作请求。

至少包含：

- `intent_kind`
- `target_slot`
- `payload`
- `success_assertion`
- `fallback_policy`

后续要扩展的 `intent_kind` 至少包括：

- `type`
- `click`
- `toggle`
- `press`
- `read`
- `open_result`
- `open_link`
- `next_page`
- `confirm`

#### `BrowserExecutionResult`

每一步动作的正式结果。

至少包含：

- `status`
- `resolved_target`
- `before_observation`
- `after_observation`
- `readback`
- `verification_passed`
- `blocker_kind`
- `evidence_ids`

### 4.3 新的共享能力

#### A. 通用观察能力

共享 observer 不再只消费外部 `dom_probe`。

它要支持三类输入合流：

1. snapshot text / ref
2. page profile probe result
3. provider/app 局部补充 hint

要求：

- provider 不再自己手写“主输入目标解析器”
- observer 能从 snapshot 自动产出基础输入候选
- page profile 只负责补充局部结构，而不是替代 observer

#### B. 更通用的 resolver

resolver 不再写死只有 `primary_input / reasoning_toggle`。

正式方向：

- 优先按 `target_slot` 在 observation 的 `slot_candidates` 内解析
- 没有显式 slot 时，再走通用 fallback
- ranking 规则按 target kind/group scope 统一处理

#### C. 正式 reobserve

service 不能再把 `after_observation` 直接等于 `before_observation`。

每次真实动作后，都要允许：

- 重新 snapshot
- 重新跑 profile probe
- 生成新的 `after_observation`

#### D. surface step loop

共享 foundation 要有正式的 step loop owner。

最小闭环：

1. observe
2. 职业 agent 决定 step
3. resolve
4. execute
5. verify
6. reobserve
7. 判断继续/停止

### 4.4 Page Profile 机制

page/app profile 允许存在，但只能保留薄 seams。

正式要求：

- profile 描述“这个页面有哪些局部语义槽位/组”
- profile 可注册 probe code
- profile 可声明 slot hint
- profile 不再内嵌整套执行逻辑

例如 Baidu page profile 只允许表达：

- composer 区
- primary input
- reasoning toggle group
- answer stream region

而不再允许 Baidu service 自己维护：

- 输入框候选解析器
- 深度思考全页扫描器
- provider 私有 readback owner

### 4.5 Browser / Document / Desktop 统一方向

这轮先从 browser 落地，但正式目标写死为：

- `src/copaw/environments/surface_execution/browser/`
- `src/copaw/environments/surface_execution/document/`
- `src/copaw/environments/surface_execution/desktop/`

它们共享同一套大语义：

- observation
- candidate resolution
- execution
- verification
- evidence

低层 executor 继续复用现有：

- browser: `browser_control.py`
- document/windows-app: `surface_control_service.py`

### 4.6 Evidence

每一步 surface 动作都必须可证据化。

正式最小 evidence 面：

- before summary
- chosen target
- action summary
- readback summary
- verification result
- after summary

这层必须接回：

- `EvidenceLedger`
- Runtime Center
- 后续 replay/read surface

## 5. 代码落位

### 5.1 本轮必须动的文件

- `src/copaw/environments/surface_execution/browser/contracts.py`
- `src/copaw/environments/surface_execution/browser/observer.py`
- `src/copaw/environments/surface_execution/browser/resolver.py`
- `src/copaw/environments/surface_execution/browser/verifier.py`
- `src/copaw/environments/surface_execution/browser/service.py`
- `src/copaw/research/baidu_page_research_service.py`
- `tests/environments/test_browser_surface_execution.py`
- `tests/research/test_baidu_page_research_service.py`

### 5.2 本轮建议新增

- `src/copaw/environments/surface_execution/browser/profiles.py`

用途：

- page profile contract
- live observation helper
- browser profile probe runner

## 6. Cutover 顺序

### Stage 1

先补 browser substrate 的正式能力：

- snapshot 自动候选
- slot candidate
- live observe/reobserve
- page profile 薄 contract

### Stage 2

把 Baidu 输入和 toggle 收回到共享 substrate。

要求：

- `_select_chat_input_ref(...)` 退役
- `_build_baidu_surface_context(...)` 降为 profile usage
- `_read_baidu_deep_think_state(...)` 不再自己拥有完整页面观察逻辑

### Stage 3

补 surface step loop，让职业 agent 能逐步接入共享循环。

### Stage 4

再把 document/desktop 对齐到同一 contract。

## 7. 验收标准

### L1

- contracts/observer/resolver/service/profile 单测通过

### L2

- Baidu research service 已切到共享 substrate + thin page profile
- resolver 不再只靠 provider 私有目标构造

### L3

- 真实浏览器页面能连续多轮对话，不再一轮一重开
- 输入/readback/reobserve 一致
- 登录缺失时能正确收口为 `waiting-login`

### L4

- 连续多轮 follow-up 不断线程
- 重启后 attach/session 可继续
- browser/document/desktop 后续统一接线不再分裂

## 8. 这轮不做的事

- 不重做第二套浏览器运行时
- 不把 CoPaw 改成 screenshot-only
- 不让职业 agent 直接手写 provider selector
- 不在 provider service 里继续堆新的私有 heuristic

## 9. 最终判断

当前系统离目标差的，不是“没有浏览器动作能力”。

真正差的是中间这层：

- 通用 observation
- 通用 candidate resolution
- 正式 reobserve
- agent step loop
- page profile 降级
- evidence truth

只有把这层补实，CoPaw 才能从“按页面写规则”升级到“职业 agent 看懂当前页面，再决定怎么操作”。
