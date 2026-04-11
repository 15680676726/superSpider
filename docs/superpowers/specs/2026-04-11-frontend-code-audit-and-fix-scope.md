# 2026-04-11 前端代码核对与修正范围审计

## 1. 目的

这份文档只做三件事：

1. 对照当前真实代码，确认前端为什么会出现“切页卡、跳转慢、页面职责混乱”。
2. 把需要修正的地方按前端、后端、前后端联动三类列完整。
3. 给出本轮完整整改的大致改动量统计。

本次结论不是基于“页面显示内容多少”，而是基于“页面实际承担了多少控制、恢复、修复和拼装逻辑”。

补充说明：

- 本文是基于当前 `main` 的二次复核，不再把已经收掉的“全站 route preload”“外壳空白等待”“聊天页首屏直接拉治理总览”继续算进现状问题。
- 本文只保留当前代码里仍然成立的问题，以及为彻底收边界仍然需要改的地方。

---

## 2. 审计范围

### 2.1 已核对的前端文件

本次已核对 `33` 个前端文件：

- `console/src/App.tsx`
- `console/src/layouts/MainLayout/index.tsx`
- `console/src/layouts/RightPanel/index.tsx`
- `console/src/routes/index.tsx`
- `console/src/routes/entryRedirect.tsx`
- `console/src/runtime/buddyFlow.ts`
- `console/src/runtime/buddyChatEntry.ts`
- `console/src/runtime/buddyProfileBinding.ts`
- `console/src/runtime/runtimeSurfaceClient.ts`
- `console/src/api/modules/buddy.ts`
- `console/src/api/modules/industry.ts`
- `console/src/pages/BuddyOnboarding/index.tsx`
- `console/src/pages/Chat/index.tsx`
- `console/src/pages/Chat/ChatAccessGate.tsx`
- `console/src/pages/Chat/useRuntimeBinding.ts`
- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/sessionApi/index.ts`
- `console/src/pages/RuntimeCenter/index.tsx`
- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- `console/src/pages/RuntimeCenter/useRuntimeCenterAdminState.ts`
- `console/src/pages/Industry/index.tsx`
- `console/src/pages/Industry/useIndustryPageState.ts`
- `console/src/pages/Knowledge/index.tsx`
- `console/src/pages/Predictions/index.tsx`
- `console/src/pages/Reports/index.tsx`
- `console/src/pages/Performance/index.tsx`
- `console/src/pages/Calendar/index.tsx`
- `console/src/pages/CapabilityMarket/index.tsx`
- `console/src/pages/Settings/System/index.tsx`
- `console/src/pages/Settings/Channels/index.tsx`
- `console/src/pages/Settings/Models/index.tsx`
- `console/src/pages/Settings/Environments/index.tsx`
- `console/src/pages/Agent/Config/index.tsx`

### 2.2 已核对的后端文件

本次已核对 `8` 个后端文件：

- `src/copaw/app/routers/buddy_routes.py`
- `src/copaw/app/routers/runtime_center_routes_overview.py`
- `src/copaw/app/routers/industry.py`
- `src/copaw/app/runtime_center/service.py`
- `src/copaw/app/runtime_center/overview_cards.py`
- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/industry/service.py`
- `src/copaw/industry/view_service.py`

### 2.3 已核对的架构/前端约束文档

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `FRONTEND_UPGRADE_PLAN.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `RUNTIME_CENTER_UI_SPEC.md`
- `AGENT_VISIBLE_MODEL.md`

---

## 3. 总结论

当前前端慢和乱，主因不是“页面显示内容多”，而是：

1. 页面承担了太多本该由后端给出明确结果的业务判断。
2. 页面一挂载就承担了启动、恢复、纠偏、重定向、拼装读面。
3. 部分读接口不是纯读取，而是“读取时顺手修系统”。
4. 多个页面和右侧固定区在重复读取同一份 Buddy 真相。
5. 核心页面文件过大，页面状态、路由分流、运行时恢复、展示逻辑混在一起。

同时要明确一件事：

- 之前最表层的几个问题已经收过一轮，所以现在的主因已经不是“全站都在 preload”或“外壳先白一下再出来”。
- 当前剩下的主要问题，集中在入口真相、读接口副作用、页面自带恢复逻辑、以及共享状态缺失。

一句话收口：

> 现在前端不是“显示层”，而是“半个控制器 + 半个恢复器 + 半个聚合器”。

这和仓库文档里“前端应逐步升级为运行中心，但仍需围绕正式状态对象显示事实”的方向不一致。

### 3.1 这次整改不能丢的边界原则

这次复核必须把下面几句话钉死，不允许后续实现再绕回去：

1. 前端不是“开系统”的地方。
   - 页面不该一挂载就自己判断“我是谁、有没有伙伴、该开哪条线程、状态对不对、要不要修正、要不要重定向”。
   - 一旦页面自己承担这些判断，它就不再是普通显示页，而会变成“小控制器”。

2. 前端只该做前端该做的事。
   - 显示数据。
   - 收集用户输入。
   - 处理界面临时状态。
   - 例如：草稿、展开收起、加载中、当前选中的 tab、局部提示。

3. 后端必须给出业务真相。
   - 判断真实业务状态。
   - 例如：有没有绑定伙伴、该开哪条聊天线程、当前处于哪一步。
   - 执行真正的动作。
   - 例如：创建、绑定、恢复、修复、调度。

4. 页面不该把“初始化”和“显示”绑死。
   - 正常顺序应该是：系统先准备好正式结果，页面再显示这个结果。
   - 不应该反过来让每个页面自己去开机、自己补上下文、自己恢复状态。

5. 这次前端慢，核心不是 UI 内容多，而是页面被写成了运行入口。
   - 真正的问题不是“页面上看起来只有几块内容”。
   - 真正的问题是页面背后承担了启动、恢复、校正、分流、拼数据、再显示这整条链。

---

## 4. 关键问题清单

## 4.1 高优先级：前后端边界错位

### 问题 A：Buddy 入口判断被前端重复实现

当前同一套 Buddy 入口判断散落在多个地方：

- `console/src/routes/entryRedirect.tsx:29-65`
- `console/src/pages/BuddyOnboarding/index.tsx:298-316`
- `console/src/runtime/buddyChatEntry.ts:27-54`
- `console/src/runtime/buddyFlow.ts:24-35`

现象：

- `EntryRedirect` 自己判断要不要去建档或开聊天。
- `BuddyOnboarding` 自己恢复 surface，再决定继续建档还是开聊天。
- `buddyChatEntry` 自己读取 surface，再决定直接开聊天还是退回建档。
- `Chat` 页面虽然不再直接做 `surface -> decision`，但仍会通过 `resumeBuddyChatFromProfile(...)` 触发这套前端入口链。

结论：

- 这不是“前端显示数据”，这是前端在自己决定系统真相。
- 需要改成单一后端入口结果，不允许页面各自猜。

需要修正：

- 后端新增正式 Buddy 聊天入口判定结果，或者在正式 surface 中提供单一 `entry` 合同。
- 前端所有 Buddy 主链页面只消费这一个结果。

归类：

- 前后端联动问题。

---

### 问题 B：`GET /buddy/surface` 不是纯读接口

当前后端在读取 `buddy surface` 时会顺手做修复：

- `src/copaw/app/routers/buddy_routes.py:561-577`

具体行为：

- `repair_active_domain_schedules(profile_id=profile_id)`
- `repair_failed_activation(profile_id=profile_id)`
- 如命中失败 activation，还会继续触发 `_maybe_activate_buddy_execution(...)`

同时前端多个地方都在读这条接口：

- `console/src/routes/entryRedirect.tsx:40`
- `console/src/runtime/buddyChatEntry.ts:27`
- `console/src/layouts/RightPanel/index.tsx:105`
- `console/src/layouts/RightPanel/index.tsx:121`
- `console/src/pages/BuddyOnboarding/index.tsx:298`
- `console/src/pages/Industry/useIndustryPageState.ts:233`

结论：

- 只要页面、侧栏、入口都在读它，就会把“读”变成“多次读 + 多次修”。
- 这条接口必须收成纯读；修复和重试要么后台做，要么走显式写入口。

需要修正：

- 后端：把 schedule repair / activation retry 从 `GET /buddy/surface` 移走。
- 前端：减少重复读取，改为共享 Buddy 真相缓存或共享 summary。

归类：

- 前后端联动问题，且后端是主要责任点。

---

### 问题 C：聊天页比之前轻了，但仍然没有完全收回成显示页

当前聊天页做了以下事：

- 入口回退和重定向：`console/src/pages/Chat/index.tsx:304-349`
- 线程 bootstrap：`console/src/pages/Chat/index.tsx:368-377`
- 运行态事件驱动刷新：`console/src/pages/Chat/index.tsx:409-440`
- 绑定上下文判断：`console/src/pages/Chat/useRuntimeBinding.ts`
- runtime sidecar / commit 审批 / suggested industry recovery：`console/src/pages/Chat/useChatRuntimeState.ts`
- 错误门禁与回退入口：`console/src/pages/Chat/ChatAccessGate.tsx`

同时聊天会话读接口也不是纯消息接口：

- `console/src/pages/Chat/sessionApi/index.ts:763-786`
- `console/src/pages/Chat/sessionApi/index.ts:852-881`
- `src/copaw/app/runtime_center/conversations.py:81-87`
- `src/copaw/app/runtime_center/conversations.py:92-166`

当前 `conversation meta` 里还会拼：

- `main_brain_commit`
- `human_assist_task`
- `human_assist_tasks_route`

结论：

- 和前一轮相比，`/chat` 已经去掉了一部分不该挡首屏的内容，但它仍然不是纯聊天页。
- `/chat` 现在依旧承担“入口回退 + 线程恢复 + 运行态 sidecar + 附加上下文拼装”。
- 需要把“能不能进聊天、该开哪条线程”前置成正式入口结果，把聊天页收回为显示页。
- 会话接口需要支持轻读面，不要每次都把大块附加状态塞给聊天首屏。

需要修正：

- 前端：拆分 `ChatEntryGate`、`ChatThreadBootstrap`、`ChatRuntimeSidecar`、`ChatView`。
- 后端：为聊天页提供更轻的 entry/session 合同，至少允许把“消息主体”和“附加 meta”拆开。

归类：

- 前后端联动问题。

---

## 4.2 高优先级：首屏阻塞链过长

### 问题 D：`Runtime Center` 首屏默认就等 `cards + main_brain`

当前前端默认请求：

- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts:274-284`

默认 sections：

- `["cards", "main_brain"]`

后端 surface 也确实会按这两块一起组装：

- `src/copaw/app/routers/runtime_center_routes_overview.py:53-70`
- `src/copaw/app/runtime_center/service.py:45-77`
- `src/copaw/app/runtime_center/overview_cards.py:1719-1752`

而 `cards` 本身就会拼很多卡：

- `src/copaw/app/runtime_center/overview_cards.py:49-61`

包括：

- tasks
- work-contexts
- routines
- industry
- agents
- predictions
- capabilities
- evidence
- governance
- decisions
- patches
- growth

结论：

- 这不是“页面内容多”，而是“第一页就要后端把大部分运行概览拼完”。
- 正确方式应该是 cards-first，main-brain-second。

需要修正：

- 前端：首屏只请求 `cards`，`main_brain` 延后。
- 后端：保留现有 sections 合同即可；如仍慢，再补更轻的 main-brain summary。

归类：

- 主要是前端请求编排问题，后端次要。

---

### 问题 E：`Industry` 首屏一次拉三份，再补一份 detail

当前 `Industry` 首屏这样做：

- `console/src/pages/Industry/useIndustryPageState.ts:233-240`

也就是同时请求：

- `buddySurface`
- `list active instances`
- `list retired instances`

如果当前 Buddy carrier 不在列表里，还会继续补一份 detail：

- `console/src/pages/Industry/useIndustryPageState.ts:257-275`

随后选中项又会继续拉整份 detail：

- `console/src/pages/Industry/useIndustryPageState.ts:313-339`

当前 detail 读的是 runtime 详情接口：

- `console/src/api/modules/industry.ts:812-829`
- `src/copaw/app/routers/industry.py:46-70`
- `src/copaw/industry/view_service.py:40-61`

结论：

- `Industry` 现在不是“先显示列表，再按需看详情”，而是“先建出完整上下文，再让页面出来”。
- 这页需要明显拆层。

需要修正：

- 前端：首屏先 active list，retired list 延后，detail 按需，当前 carrier 不要靠首屏补整份 detail。
- 后端：考虑给 summary 增加 `is_current_buddy_carrier` / `current_focus_summary` 一类轻字段，减少首屏必须拉 detail 的需要。

归类：

- 前后端联动问题。

---

## 4.3 中优先级：共享真相缺失，导致重复读取

### 问题 F：右侧固定区独立维护 Buddy 真相

当前右侧固定区：

- 自己从 `window.currentThreadMeta` 和 storage 解析 profile：`console/src/layouts/RightPanel/index.tsx:48-75`
- 自己首屏调 `getBuddySurface`：`console/src/layouts/RightPanel/index.tsx:96-114`
- 自己定时刷新：`console/src/layouts/RightPanel/index.tsx:116-129`

结论：

- 它虽然是展示区，但现在是独立 reader。
- 这会和入口页、建档页、聊天页、Industry 一起重复读取 Buddy。

需要修正：

- 前端新增应用级 Buddy summary store 或 query cache。
- 右侧固定区改为消费共享状态，不再自己单独决定何时读 surface。

归类：

- 前端共享状态问题。

---

### 问题 G：公共外壳和根入口仍然承担分流职责

当前根入口：

- `console/src/routes/index.tsx`
- `console/src/routes/entryRedirect.tsx`

当前外壳：

- `console/src/layouts/MainLayout/index.tsx`

复核后确认：

- `/` 仍然是“专门负责分流”的中间页，而不是纯粹路由前门。
- `App.tsx` 和 `MainLayout` 已经不再是当前卡顿主因；它们的问题主要是还没有承载应用级共享 Buddy 读面。
- Buddy 状态没有提升到应用级共享读面，导致页面还在各自拉取。

需要修正：

- 应用级前门只保留“拿正式入口结果，再渲染正确页面”，不要再让 `/` 成为带业务判断的中间页。
- Buddy / Runtime summary 要有共享只读源，不能散落在各页面。

归类：

- 前后端联动 + 前端架构问题。

---

## 4.4 次级页面快照盘点

以下页面没有发现和主链同等级的严重边界错位，但仍有明显的首屏并发或大文件问题。

### 中优先级

- `Knowledge`
  - 文件尺寸：`1282` 行
  - 首屏双加载：`console/src/pages/Knowledge/index.tsx:493-496`
  - 选中 agent 后继续 detail 加载：`console/src/pages/Knowledge/index.tsx:498-500`
  - 结论：需要拆首屏和 detail，文件也需要切块。

- `Predictions`
  - 文件尺寸：`921` 行
  - 首屏先列表，再按选中 case 拉 detail：`console/src/pages/Predictions/index.tsx:258-268`
  - 结论：逻辑还算正常，但文件过大，应该拆成 list/detail/admin action。

- `Settings/System`
  - 文件尺寸：`564` 行
  - 首屏 `Promise.all` 四份数据：`console/src/pages/Settings/System/index.tsx:215-220`
  - 结论：不是主链问题，但可以做 staged loading。

- `Settings/Environments`
  - 文件尺寸：`442` 行
  - 首屏双请求：`console/src/pages/Settings/Environments/index.tsx:86-89`
  - 结论：问题不大，但仍可后补 provider context。

### 低优先级

- `Reports`
  - 单页加载，文件 `303` 行，当前没有明显契约越界。

- `Performance`
  - 单页加载，文件 `352` 行，当前没有明显契约越界。

- `Calendar`
  - 单页加载，文件 `220` 行，当前没有明显契约越界。

- `CapabilityMarket`
  - 文件 `532` 行，主要复杂度来自安装 job 与轮询，不是当前主链卡顿的核心原因。

- `Settings/Channels`
  - 文件 `154` 行，读写较轻。

- `Settings/Models`
  - 文件 `110` 行，读写较轻。

- `Agent/Config`
  - 文件 `145` 行，读写较轻。

---

## 5. 建议修正清单

## 5.1 必须修改：前后端联动

1. 新增正式 Buddy 聊天入口合同。
   - 目标：前端不再自己判断“建档/聊天/线程”。
   - 建议落点：Buddy router 或 runtime chat front-door。

2. 把 `GET /buddy/surface` 收成纯读。
   - 目标：读取不再触发 repair / activation retry。

3. 为聊天页补轻量 entry/session 合同。
   - 目标：聊天首屏优先拿线程和消息主体，附加 meta 延后。

4. 为 `Industry` summary 增加当前 carrier/当前 focus 的轻字段。
   - 目标：首屏不必先补整份 detail。

## 5.2 必须修改：前端主链

1. 入口前门只消费单一 Buddy entry 结果。
2. `BuddyOnboarding` 不再自己读 surface 决定去哪。
3. `Chat` 继续收口为显示页；保留已拆出来的部分，同时把剩余入口回退、线程 bootstrap、sidecar 判断继续前移或下沉。
4. `Runtime Center` 首屏 cards-first，main-brain-second。
5. `Industry` 首屏先 active list，retired/detail 后补。
6. 右侧固定区改为消费共享 Buddy summary，不再自己独立拉同一份 truth。

## 5.3 应该修改：前端次级页面

1. `Knowledge` 拆 `page + detail + memory workspace`。
2. `Predictions` 拆 `list + detail + action panel`。
3. `Settings/System` 和 `Settings/Environments` 改 staged loading。

---

## 6. 建议改动文件清单

## 6.1 前端源码：必须修改

预计 `18` 个文件：

- `console/src/routes/index.tsx`
- `console/src/routes/entryRedirect.tsx`
- `console/src/runtime/buddyFlow.ts`
- `console/src/runtime/buddyChatEntry.ts`
- `console/src/runtime/buddyProfileBinding.ts`
- `console/src/runtime/runtimeSurfaceClient.ts`
- `console/src/runtime/buddySummaryStore.ts`（新增）
- `console/src/layouts/RightPanel/index.tsx`
- `console/src/pages/BuddyOnboarding/index.tsx`
- `console/src/pages/Chat/index.tsx`
- `console/src/pages/Chat/ChatAccessGate.tsx`
- `console/src/pages/Chat/useRuntimeBinding.ts`
- `console/src/pages/Chat/useChatRuntimeState.ts`
- `console/src/pages/Chat/sessionApi/index.ts`
- `console/src/pages/RuntimeCenter/index.tsx`
- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- `console/src/pages/Industry/index.tsx`
- `console/src/pages/Industry/useIndustryPageState.ts`

## 6.2 前端源码：第二批建议修改

预计 `4` 个文件：

- `console/src/pages/Knowledge/index.tsx`
- `console/src/pages/Predictions/index.tsx`
- `console/src/pages/Settings/System/index.tsx`
- `console/src/pages/Settings/Environments/index.tsx`

## 6.3 后端源码：必须修改

预计 `7` 个文件：

- `src/copaw/app/routers/buddy_routes.py`
- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/app/routers/runtime_center_routes_overview.py`
- `src/copaw/app/runtime_center/service.py`
- `src/copaw/app/runtime_center/overview_cards.py`
- `src/copaw/app/routers/industry.py`
- `src/copaw/industry/view_service.py`

## 6.4 测试文件：需要同步补齐

预计：

- 前端测试 `12` 到 `16` 个
- 后端测试 `6` 到 `8` 个

最少应覆盖：

- Buddy entry / surface contract
- Chat entry / session bootstrap
- Runtime Center staged loading
- Industry list/detail split
- RightPanel shared summary

---

## 7. 改动量统计

基于当前代码尺寸和职责混杂程度，完整整改建议按三批计算。

### 第一批：主链纠偏

- 前端源码：`18` 个文件
- 后端源码：`7` 个文件
- 测试：`12` 到 `16` 个文件
- 预计改动：约 `1400` 到 `2200` 行

目标：

- 把 Buddy/Chat/Runtime Center/Industry 从“页面控制器”收回到“显示页 + 明确入口结果”。

### 第二批：次级页面减重

- 前端源码：`4` 个文件
- 测试：`4` 到 `6` 个文件
- 预计改动：约 `500` 到 `900` 行

目标：

- 收 `Knowledge / Predictions / Settings` 的首屏并发和大文件。

### 总量估算

- 前端源码：`22` 个文件
- 后端源码：`7` 个文件
- 测试：`16` 到 `22` 个文件
- 文档：`1` 到 `2` 个文件
- 预计总代码改动：约 `1900` 到 `3100` 行

说明：

- 这不是“新增很多功能”，而是“收边界、拆职责、减首屏阻塞”。
- 真正的大头不是 UI 组件，而是入口合同和读面合同。
- 上述统计已经排除了这轮已不再成立的外壳白屏 / 全站 preload 类问题。

---

## 8. 实施优先级

### P0

- Buddy 入口合同单一化
- `/buddy/surface` 纯读化
- Chat 页职责收口

### P1

- Runtime Center 首屏拆层
- Industry 首屏拆层
- RightPanel 共享 Buddy summary

### P2

- Knowledge / Predictions / System / Environments 减重

---

## 9. 最终判断

当前前端的核心问题不是“组件慢”或者“显示内容多”，而是：

1. 业务真相没有被单点后端入口收口。
2. 页面自己承担了太多恢复和决策。
3. 读接口混入了修复动作。
4. 共享状态缺失，导致多页面重复读取同一真相。

所以这次整改的核心不是继续抠样式和局部微优化，而是：

> 把前端收回到“显示正式结果”，把后端收回到“给出单一真相和单一入口结果”。
