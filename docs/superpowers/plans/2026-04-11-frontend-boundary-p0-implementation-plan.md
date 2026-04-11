# Frontend Boundary P0 Implementation Plan

## Status

- 状态：已完成
- 目标：把 Buddy / Chat 主链从“前端自己判断真相”收回到“后端给入口结果，前端只消费结果”

---

## 1. P0 最终落地范围

这轮 P0 实际完成的是 3 条主链：

1. Buddy 正式入口收口
2. runtime conversation 轻/富合同收口
3. 聊天前门只吃正式 entry + light conversation

这不是“重做聊天页”，而是先把最容易导致错跳、重复读取、首屏发闷的入口链收正。

---

## 2. 已落地内容

### 2.1 Buddy entry 已经成为正式单跳入口

当前正式事实：

- `/buddy/entry` 返回：
  - `start-onboarding`
  - `resume-onboarding`
  - `chat-ready`
- `chat-ready` 直接带：
  - `profile_display_name`
  - `execution_carrier`

已落地文件：

- `src/copaw/app/routers/buddy_routes.py`
- `console/src/runtime/buddyFlow.ts`
- `console/src/runtime/buddyChatEntry.ts`
- `console/src/routes/entryRedirect.tsx`
- `console/src/pages/BuddyOnboarding/index.tsx`

当前前端主链不再依赖：

- `/buddy/entry -> /buddy/surface -> open chat`

而是改成：

- `/buddy/entry -> open chat`

### 2.2 `/buddy/surface` 已收成纯读

当前正式事实：

- `GET /buddy/surface` 不再承担 repair / retry / activation side effect
- Buddy 读面和 Buddy 写面边界已分开

已落地文件：

- `src/copaw/app/routers/buddy_routes.py`
- `tests/app/test_buddy_routes.py`

### 2.3 runtime conversation 已改成默认轻读

当前正式事实：

- `/runtime-center/conversations/{conversation_id}` 默认返回 light contract
- 只有显式传 `optional_meta` 才补富 meta
- 当前支持的显式富 meta：
  - `main_brain_commit`
  - `human_assist_task`
  - `all`

已落地文件：

- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/app/routers/runtime_center_routes_ops.py`
- `console/src/api/modules/conversation.ts`
- `console/src/pages/Chat/sessionApi/index.ts`

聊天页当前实际使用：

- 显式请求 `main_brain_commit`
- 不默认把 `human_assist_task` 拖进首屏

### 2.4 聊天页前门不再自己重建 Buddy 真相

当前正式事实：

- 聊天页入口以 Buddy entry 结果为准
- Chat access gate 只拦真正的入口失败
- 聊天页不再靠第二跳 Buddy surface 再判断一次能不能开

已落地文件：

- `console/src/pages/Chat/index.tsx`
- `console/src/pages/Chat/ChatAccessGate.tsx`
- `console/src/pages/Chat/sessionApi/index.ts`

---

## 3. 本轮验证

### 3.1 后端

```bash
python -m pytest tests/app/test_buddy_routes.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_chat_thread_binding.py -q
```

结果：

- `33 passed`

### 3.2 前端

```bash
npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts
```

说明：

- 这组是 P0 直接相关的主链验证子集
- 更大的 staged-loading / shared summary 验证在 `P1/P2` 文档记录

---

## 4. P0 收口后的正式边界

### 4.1 前端现在该怎么做

前端主链现在应该只做：

- 调 Buddy 正式入口
- 按 entry mode 分流
- 打开聊天
- 读取 light conversation
- 按需请求富 meta

### 4.2 后端现在必须提供什么

后端现在必须稳定提供：

- 可直接消费的 Buddy entry 结果
- 纯读的 Buddy surface
- 默认轻量的 runtime conversation
- 显式 opt-in 的富 meta

---

## 5. P0 没做的事

这轮 P0 没有声称完成以下内容：

- 把聊天页物理拆成多个小模块
- 重做聊天页全部 UI
- 为所有非聊天消费者统一定义一套富 meta 拉取策略
- 重审整站所有页面的入口边界

所以当前准确说法是：

> P0 已经把 Buddy/Chat 主入口和 conversation 合同收正，但没有宣称聊天页内部已经彻底轻到极致。

---

## 6. 施工后结论

P0 已完成，且当前有效结论只有两句：

1. Buddy 入口真相已经回到后端。
2. 聊天页首屏现在走的是“正式入口 + 默认轻 conversation”。
