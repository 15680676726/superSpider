# Console Runtime Center Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前控制台从“蓝金设置台”重构成更像运行中心的深色 command center，并让聊天、运行中心、行业工作台、能力市场等主场页面共享统一视觉与交互壳。

**Architecture:** 先重做全局设计 token、主布局和导航头部，再用统一页面 header/surface 组件把一级页面接到同一套运行中心语言上。风格采用 `awesome-design-md` 的 `linear.app` 方向，但保留 CoPaw 自己的“Buddy 主场 + Runtime Center + Industry”产品边界，不做品牌复刻。

**Tech Stack:** React, TypeScript, Ant Design, Less/CSS, Vitest

---

### Task 1: 锁定新壳的结构契约

**Files:**
- Create: `console/src/components/PageHeader.test.tsx`
- Create: `console/src/layouts/routePresentation.test.ts`
- Modify: `console/src/components/PageHeader.tsx`
- Create: `console/src/layouts/routePresentation.ts`

- [ ] **Step 1: 写页面 header 的失败测试**

```tsx
it("renders eyebrow, title, description, stats and actions", () => {
  render(
    <PageHeader
      eyebrow="Runtime Center"
      title="主脑驾驶舱"
      description="让运行事实优先可见"
      stats={[{ label: "运行中", value: "6" }]}
      actions={<button>刷新</button>}
    />,
  );

  expect(screen.getByText("Runtime Center")).toBeInTheDocument();
  expect(screen.getByText("主脑驾驶舱")).toBeInTheDocument();
  expect(screen.getByText("运行中")).toBeInTheDocument();
  expect(screen.getByText("6")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "刷新" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pnpm --dir console exec vitest run console/src/components/PageHeader.test.tsx console/src/layouts/routePresentation.test.ts`

Expected: FAIL because `PageHeader` 还不支持新 props，`routePresentation` 还不存在

- [ ] **Step 3: 写 route presentation 的失败测试**

```ts
it("returns runtime-centered presentation for known routes", () => {
  const meta = getRoutePresentation("runtime-center");
  expect(meta.title).toBe("主脑驾驶舱");
  expect(meta.description).toContain("运行");
  expect(meta.groupLabel).toBe("运行中心");
});
```

- [ ] **Step 4: 实现最小 PageHeader 与 route presentation**

实现内容：
- `PageHeader` 支持 `eyebrow / title / description / stats / actions / aside`
- `routePresentation.ts` 统一输出 `title / description / groupLabel / shortLabel / statusTone`

- [ ] **Step 5: 重跑测试确认通过**

Run: `pnpm --dir console exec vitest run console/src/components/PageHeader.test.tsx console/src/layouts/routePresentation.test.ts`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/components/PageHeader.tsx console/src/components/PageHeader.test.tsx console/src/layouts/routePresentation.ts console/src/layouts/routePresentation.test.ts
git commit -m "feat(console): add runtime page shell primitives"
```

### Task 2: 重做全局 theme 与主布局壳

**Files:**
- Modify: `console/src/theme/baizeTheme.ts`
- Modify: `console/src/styles/layout.css`
- Modify: `console/src/layouts/Header.tsx`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/layouts/index.module.less`
- Test: `console/src/layouts/routePresentation.test.ts`

- [ ] **Step 1: 写 Header/route presentation 的失败测试**

```ts
it("exposes compact route summary and quick actions", () => {
  const meta = getRoutePresentation("chat");
  expect(meta.shortLabel).toBe("Buddy");
  expect(meta.description).toContain("主场");
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pnpm --dir console exec vitest run console/src/layouts/routePresentation.test.ts`

Expected: FAIL because new route metadata not complete

- [ ] **Step 3: 最小实现全局主题与 shell**

实现内容：
- 把主色从蓝金切到深炭黑 + indigo accent + success green 的 runtime palette
- 重做 `Layout / Menu / Card / Button / Input / Tabs / Tag` token
- 侧边栏改成 command rail 风格：品牌、分组、轻量状态区、收起态可读
- 顶栏改成 route context bar：主标题、摘要、快捷跳转/状态动作
- `pageContent` 改成统一画布与留白系统

- [ ] **Step 4: 重跑相关测试**

Run: `pnpm --dir console exec vitest run console/src/layouts/routePresentation.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add console/src/theme/baizeTheme.ts console/src/styles/layout.css console/src/layouts/Header.tsx console/src/layouts/Sidebar.tsx console/src/layouts/index.module.less console/src/layouts/routePresentation.ts console/src/layouts/routePresentation.test.ts
git commit -m "feat(console): redesign global shell and theme"
```

### Task 3: 接入统一页面 header 与主场页面外壳

**Files:**
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/CapabilityMarket/index.tsx`
- Modify: `console/src/pages/Reports/index.tsx`
- Modify: `console/src/pages/Predictions/index.tsx`
- Modify: `console/src/pages/Settings/Channels/index.tsx`
- Modify: `console/src/pages/Chat/index.module.less`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Optionally Modify: `console/src/pages/CapabilityMarket/index.module.less`
- Test: `console/src/components/PageHeader.test.tsx`

- [ ] **Step 1: 写失败测试，锁住新的 header/stats 使用方式**

```tsx
it("renders multiple stats blocks in page header", () => {
  render(
    <PageHeader
      title="能力市场"
      stats={[
        { label: "已安装", value: "12" },
        { label: "待评估", value: "4" },
      ]}
    />,
  );

  expect(screen.getByText("已安装")).toBeInTheDocument();
  expect(screen.getByText("待评估")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pnpm --dir console exec vitest run console/src/components/PageHeader.test.tsx`

Expected: FAIL until stats rendering is finalized

- [ ] **Step 3: 最小实现页面级接入**

实现内容：
- Runtime Center：hero 头部、summary strip、card surface 节奏统一
- Industry：把说明、刷新、调整入口收口到新 header；主内容栅格统一
- Capability Market：把 tab/search/filter 变成明显的 market workbench
- Reports / Predictions / Channels：至少接入统一页面 header 与 section surface
- Chat：把顶部状态条、buddy sidecar、输入区的视觉与 global shell 对齐

- [ ] **Step 4: 重跑页面 header 测试**

Run: `pnpm --dir console exec vitest run console/src/components/PageHeader.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/RuntimeCenter/index.tsx console/src/pages/Industry/index.tsx console/src/pages/CapabilityMarket/index.tsx console/src/pages/Reports/index.tsx console/src/pages/Predictions/index.tsx console/src/pages/Settings/Channels/index.tsx console/src/pages/Chat/index.module.less console/src/pages/RuntimeCenter/index.module.less console/src/pages/CapabilityMarket/index.module.less console/src/components/PageHeader.tsx console/src/components/PageHeader.test.tsx
git commit -m "feat(console): apply runtime design shell to primary pages"
```

### Task 4: 验证前端重设计主链

**Files:**
- Test: `console/src/components/PageHeader.test.tsx`
- Test: `console/src/layouts/routePresentation.test.ts`
- Test: existing page tests touched by compilation

- [ ] **Step 1: 跑 targeted vitest**

Run: `pnpm --dir console exec vitest run console/src/components/PageHeader.test.tsx console/src/layouts/routePresentation.test.ts console/src/pages/RuntimeCenter/index.test.tsx console/src/pages/CapabilityMarket/index.test.tsx`

Expected: PASS

- [ ] **Step 2: 跑 console 构建**

Run: `pnpm --dir console exec tsc --noEmit`

Expected: PASS

- [ ] **Step 3: 如有可用，再跑前端构建**

Run: `pnpm --dir console exec vite build`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test(console): verify runtime center redesign"
```
