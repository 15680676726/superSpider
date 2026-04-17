# Runtime Center Trace Tab Frontend Completion Plan

> 当前这份计划不是“从零做 trace 主链”，而是“基于已经落地的后端 trace payload，把前端读面补完整”。

**Goal:** 把 `Runtime Center` 里主脑和职业 agent 的 `追溯` tab 真正做出来，让用户能读到今天的执行顺序细节。

**Current Truth:** 后端 `trace` 合同和 builder 已经落地；前端还没有 `trace` 类型映射、tab、共享渲染组件和详情入口。

**Architecture:** 直接消费 `main_brain.cockpit.main_brain.trace` 与 `main_brain.cockpit.agents[].trace`，前端只负责映射和渲染，不再从其他字段派生 trace。

---

## File Map

**Frontend type + mapping**
- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`

**Frontend UI**
- Create: `console/src/pages/RuntimeCenter/CockpitTraceSection.tsx`
- Create: `console/src/pages/RuntimeCenter/CockpitTraceSection.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Test: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

---

## Task 1: Sync frontend types and Runtime Center mapping

**Files:**
- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] 写失败测试，证明现有 surface mapping 不会把 backend trace 映射到 cockpit panel props。
- [ ] 在 `runtimeCenter.ts` 补正式 `trace` 类型。
- [ ] 在 `index.tsx` 把主脑和 agent 的 `trace` 透传到 panel 层。
- [ ] 复跑定向前端测试，确认 mapping 已打通。

---

## Task 2: Add shared trace section and wire cockpit tabs

**Files:**
- Create: `console/src/pages/RuntimeCenter/CockpitTraceSection.tsx`
- Create: `console/src/pages/RuntimeCenter/CockpitTraceSection.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Test: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] 写失败测试，证明当前两个 cockpit panel 都还没有 `追溯` tab。
- [ ] 新建共享 `CockpitTraceSection`，负责渲染一行一条的 trace。
- [ ] 在 `AgentWorkPanel` 和 `MainBrainCockpitPanel` 接入 `追溯` tab。
- [ ] 如 trace 行带 `route`，接入现有详情打开能力；没有 `route` 时只读展示。
- [ ] 复跑定向前端测试，确认 tab、空态、排序、详情入口都通过。

---

## Task 3: Final verification

- [ ] 运行：
  - `npm --prefix console test -- src/pages/RuntimeCenter/CockpitTraceSection.test.tsx src/pages/RuntimeCenter/AgentWorkPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/pages/RuntimeCenter/index.test.tsx`
- [ ] 运行：
  - `npm --prefix console run build`
- [ ] 回归确认：
  - `C:\Python312\python.exe -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`

---

## Done Means

只有同时满足下面几点，才算这条收口：

1. 主脑和职业 agent 都能切到 `追溯` tab。
2. 前端读的是后端正式 `trace`，不是 fallback 派生。
3. 没有 trace 时显示空态。
4. 有 route 的 trace 能继续打开现有详情。
5. 定向前端测试、console build、后端回归都通过。
