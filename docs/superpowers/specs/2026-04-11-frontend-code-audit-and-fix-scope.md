# 2026-04-11 前端代码核对与修正范围审计

## 1. 目的

这份文档只回答 4 件事：

1. 当前 `main` 上，前端慢和乱的主因到底是什么。
2. 这轮已经收口了哪些真正的前后端断层。
3. 这轮没有覆盖哪些范围，避免后续误以为“整站都已经彻底完成”。
4. 当前可以继续作为施工依据的事实是什么。

本版是基于 `2026-04-11` 当前 `main` 的现码和现测重新整理的有效版本。之前已经失效的判断已经删掉，不再保留为“当前问题”。

---

## 2. 这轮不能再丢的边界

### 2.1 前端不是“开系统”的地方

前端只负责：

- 显示数据
- 收集用户输入
- 处理界面临时状态
- 做最小的路由展示分流

前端不该负责：

- 判断业务真相
- 猜当前应开哪条线程
- 自己恢复或修正正式状态
- 读接口时顺手触发修复动作

### 2.2 后端必须给出业务真相

后端负责：

- 判断是否已建档
- 判断 Buddy 当前是否可直接进入聊天
- 返回可直接打开聊天所需的正式 handoff
- 控制 conversation 读面的轻重合同

一句话收口：

> 前端可以管界面，但不该管系统真相。

---

## 3. 当前已经收口的 4 个关键问题

### 3.1 问题 A：runtime conversation 轻/富合同分裂

#### 旧问题

之前的风险点是：

- 聊天页首屏不需要的富 meta 也跟着每次 conversation read 一起返回。
- 文档、前端和后端测试对这份合同的理解不一致。
- 一旦默认合同继续膨胀，聊天页就会重新变成“消息 + 运行侧车 + 附加状态大拼盘”。

#### 当前正式合同

现在正式合同已经收口成：

- `GET /runtime-center/conversations/{conversation_id}` 默认返回 **light contract**
- 只有显式传入 `optional_meta` 才补充富 meta
- 当前受支持的显式富 meta 键：
  - `main_brain_commit`
  - `human_assist_task`
  - `all`

相关代码：

- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/app/routers/runtime_center_routes_ops.py`
- `console/src/api/modules/conversation.ts`
- `console/src/pages/Chat/sessionApi/index.ts`

当前前端实际行为：

- 聊天页会显式请求 `main_brain_commit`
- 聊天页不会默认把 `human_assist_task` 一起拖进首屏

#### 结论

这条断层已经收口。

当前正确说法不是“聊天接口已经只剩消息”，而是：

> 默认轻读，富 meta 按需显式加。

---

### 3.2 问题 B：Buddy entry 还是两跳

#### 旧问题

之前的问题不是只有“前端判断太多”，而是 Buddy 入口本身也不完整：

- 前端先读 `/buddy/entry`
- 再补读 `/buddy/surface`
- 然后才决定能不能开聊天

这会造成：

- 入口真相分散
- 首屏多一次 Buddy 读取
- 入口和 surface 之间可能出现临时不一致

#### 当前正式入口合同

现在 `/buddy/entry` 已经是正式单跳入口：

- `start-onboarding`
- `resume-onboarding`
- `chat-ready`

当返回 `chat-ready` 时，payload 直接带：

- `profile_display_name`
- `execution_carrier`

也就是前端已经不需要再补读 `/buddy/surface` 才能开聊天。

相关代码：

- `src/copaw/app/routers/buddy_routes.py`
- `console/src/runtime/buddyFlow.ts`
- `console/src/runtime/buddyChatEntry.ts`
- `console/src/routes/entryRedirect.tsx`
- `console/src/pages/BuddyOnboarding/index.tsx`

#### 结论

这条断层已经收口。

当前正确说法是：

> Buddy 主入口现在有单一后端结果，前端主链不再靠第二跳 surface 再猜一次。

---

### 3.3 问题 C：Industry 首屏直接读 Buddy surface

#### 旧问题

之前 `Industry` 首屏会自己读 `api.getBuddySurface()`，这会带来两个问题：

- `Industry` 自己再读一遍 Buddy 真相
- 右侧固定区、入口页、建档页、聊天页之间的 Buddy 真相无法共享

这不是“多一个请求”这么简单，而是：

> 同一份 Buddy 真相，被多个页面各自管理。

#### 当前正式读链

现在 `Industry` 首屏不再直接读 `api.getBuddySurface()`。

它改为走：

- `buddyProfileBinding`
- `buddySummaryStore`

也就是先拿当前 Buddy profile 绑定，再消费共享 Buddy summary。

相关代码：

- `console/src/pages/Industry/useIndustryPageState.ts`
- `console/src/runtime/buddySummaryStore.ts`
- `console/src/runtime/buddyProfileBinding.ts`

#### 结论

这条断层已经收口。

当前正确说法不是“Industry 完全不依赖 Buddy truth”，而是：

> Industry 不再自己直连 Buddy surface，而是消费共享 Buddy truth。

---

### 3.4 问题 D：文档本身过时，继续误导施工

#### 旧问题

旧版文档里还混着几类已经不成立的结论：

- 还把已经收掉的问题写成当前主因
- 还把未落地的“预期方案”写成现状
- 没把真正已经收口的合同改写为正式事实

这样后续施工会出现两个风险：

- 继续改已经改完的东西
- 漏掉真正还没覆盖的范围

#### 当前处理原则

这版文档已经按当前现码重写，只保留：

- 仍然成立的架构边界
- 已正式收口的合同
- 本轮明确未覆盖的范围

---

## 4. 当前仍然成立的页面级结论

### 4.1 聊天页比之前轻了，但不是“整站问题的唯一来源”

当前聊天主链已经收过两轮，正式边界是：

- Buddy 入口真相由后端给出
- conversation 读面默认轻量
- 聊天页首屏不再依赖第二跳 Buddy surface

但这不等于：

- 聊天页已经完成所有内部拆分
- 所有 runtime sidecar 都已经彻底抽离

当前能确认的是：

> 聊天主链已经回到“能进、能开、能读”的正确边界；更深的 UI/模块拆分不在本轮审计结论内。

### 4.2 Runtime Center / RightPanel / Industry 的首屏策略已经按本轮方案落地

当前现码已成立的事实：

- `Runtime Center`：`cards first / main_brain later`
- `RightPanel`：共享 Buddy summary，不再各自重复持有 Buddy 真相
- `Industry`：active list first，不再首屏直读 Buddy surface

所以这 3 条在本轮审计里不再作为“当前仍未修”的问题保留。

---

## 5. 这轮明确未覆盖的范围

这份审计文档现在不再声称“整个前端全部完成”，以下范围没有被这轮重新定义为已完成：

- `console/src/pages/Reports/index.tsx`
- `console/src/pages/Performance/index.tsx`
- `console/src/pages/Calendar/index.tsx`
- `console/src/pages/CapabilityMarket/index.tsx`
- `console/src/pages/Settings/Channels/index.tsx`
- `console/src/pages/Settings/Models/index.tsx`
- `console/src/pages/Agent/Config/index.tsx`

另外也没有在这轮里新做这些事：

- 新增全新的 Buddy summary 后端接口
- 把聊天页彻底拆成多个物理子模块
- 对整站所有页面再做一轮全量汉化审计

所以当前准确说法是：

> 这轮完成的是 Buddy/Chat 主入口、conversation 轻重合同、RightPanel 共享 Buddy truth、Runtime Center/Industry/Knowledge/Predictions/Settings 首屏减重。不是整站所有页面都重新审过一遍。

---

## 6. 当前有效的验证边界

### 6.1 后端

已验证：

```bash
python -m pytest tests/app/test_buddy_routes.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_thread_binding.py -q
```

结果：

- `33 passed`

这组验证覆盖：

- Buddy entry 正式入口合同
- `/buddy/surface` 纯读行为
- runtime conversation light/optional meta 合同
- runtime chat thread binding 主链

### 6.2 前端

已验证：

```bash
npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Predictions/index.page.test.tsx src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx
```

结果：

- `17` 个测试文件
- `80 passed`

这组验证覆盖：

- Buddy 单跳入口
- 建档页与入口分流
- 聊天页 entry/session 消费
- RightPanel 共享 Buddy summary
- Runtime Center staged load
- Industry staged load
- Knowledge / Predictions / Settings staged load

### 6.3 build

已验证：

```bash
npm --prefix console run build
```

当前本轮文档定稿前必须以 build 通过为准。

---

## 7. 结论

这轮审计的最终结论现在收口为：

1. 前端慢和乱的核心，不是页面显示内容少不少，而是页面曾经承担了太多本该由后端给结果的入口判断和状态恢复。
2. 这轮最关键的 4 条断层已经收口：
   - runtime conversation 轻/富合同
   - Buddy 单跳入口
   - Industry 不再直读 Buddy surface
   - 文档本身过时的问题
3. 当前仍需保持清醒的是：
   - 这不是“整个前端全量升级已完成”
   - 这是“主链边界和重点首屏读链已经收正”

一句话总结：

> 当前前端主链已经更接近“显示页 + 明确后端入口结果”，不再是“页面自己开系统”。
