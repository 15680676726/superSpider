# Frontend Boundary P1 P2 Implementation Plan

## Status

- 状态：已完成
- 目标：把剩余主链页面从“首屏先把一堆事做完”收回到“页面先出来，重活后补”

---

## 1. P1 / P2 实际落地范围

这轮 P1 / P2 实际完成的是 5 块：

1. RightPanel 共享 Buddy summary
2. Runtime Center 改成 `cards first / main_brain later`
3. Industry 改成 `active first / retired later / detail on demand`
4. Knowledge / Predictions / Settings 改成 page-first staged loading
5. 对这些读链补了前端回归测试

这轮没有再新开一套后端接口，而是优先把前端重复读取和错误首屏时机收回到共享 truth。

---

## 2. 已落地内容

### 2.1 RightPanel 已改成共享 Buddy summary

当前正式事实：

- RightPanel 不再自己决定 Buddy 真相
- RightPanel 不再自己单独直连一套 Buddy 读取时机
- Buddy summary 已进入共享 store

已落地文件：

- `console/src/runtime/buddySummaryStore.ts`
- `console/src/layouts/RightPanel/index.tsx`
- `console/src/runtime/buddyProfileBinding.ts`

当前效果：

- 右侧固定区和主页面消费的是同一份 Buddy summary 真相
- RightPanel 继续保留自己的刷新节奏，但不再是“另起一套 truth”

### 2.2 Runtime Center 已改成 cards first

当前正式事实：

- 首屏先请求 `cards`
- `main_brain` 改成后续跟进请求
- 页面在 `main_brain` 未返回时仍可正常显示和使用

已落地文件：

- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- `console/src/pages/RuntimeCenter/index.tsx`

### 2.3 Industry 已不再首屏直读 Buddy surface

当前正式事实：

- `Industry` 首屏不再直接调 `api.getBuddySurface()`
- 当前 Buddy carrier 真相改为走：
  - `buddyProfileBinding`
  - `buddySummaryStore`
- 首屏先 active list
- retired list 后补
- detail 按需补

已落地文件：

- `console/src/pages/Industry/useIndustryPageState.ts`
- `console/src/runtime/buddySummaryStore.ts`
- `console/src/runtime/buddyProfileBinding.ts`

这条要特别说明：

> 本轮没有新加 Industry 专用后端 summary 接口。当前落地方案是“共享 Buddy truth + staged load”，不是“再开一个新后端前门”。

### 2.4 Knowledge / Predictions / Settings 已改成 staged loading

当前正式事实：

- `Knowledge`：主页面先显示，workspace/detail 后补
- `Predictions`：list first，detail/action later
- `Settings/System`：主要内容先显示，附加请求后补
- `Settings/Environments`：首屏不再同时硬等双请求

已落地文件：

- `console/src/pages/Knowledge/index.tsx`
- `console/src/pages/Predictions/index.tsx`
- `console/src/pages/Settings/System/index.tsx`
- `console/src/pages/Settings/Environments/index.tsx`

---

## 3. 本轮验证

### 3.1 前端专项验证

```bash
npm --prefix console test -- src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Predictions/index.page.test.tsx src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx
```

这组验证已包含在更大的前端回归里。

当前更大一轮实际验证结果：

```bash
npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Predictions/index.page.test.tsx src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx
```

结果：

- `17` 个测试文件
- `80 passed`

---

## 4. P1 / P2 收口后的正式边界

### 4.1 现在这些页面该怎么工作

- RightPanel：消费共享 Buddy truth，不再独自持有真相
- Runtime Center：首屏先 cards，不再默认 hard wait `main_brain`
- Industry：先 active list，不再首屏直读 Buddy surface
- Knowledge / Predictions / Settings：页面先可用，非必要读面后补

### 4.2 这轮没做什么

这轮 P1 / P2 没有声称完成这些内容：

- Reports / Performance / Calendar / CapabilityMarket 全量再审
- Channels / Models / Agent Config 全量 staged loading 整理
- 为 Industry 新增专门的后端轻 summary API
- 对所有页面再统一做一轮全量 IA 重设计

所以当前准确说法是：

> P1 / P2 已经把重点主链页面的首屏阻塞和 Buddy 重复读链收正，但没有宣称整站所有页面都完成同等级重构。

---

## 5. 施工后结论

P1 / P2 已完成，且当前有效结论只有两句：

1. Buddy 共享 truth 已进入 RightPanel / Industry 这一层的正式读链。
2. Runtime Center / Industry / Knowledge / Predictions / Settings 的首屏已经回到“页面先出来，重活后补”。
