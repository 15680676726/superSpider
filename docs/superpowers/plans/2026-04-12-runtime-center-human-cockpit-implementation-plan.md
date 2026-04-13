# Runtime Center Human Cockpit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Runtime Center 首页收口成“普通人可读的多 agent 驾驶舱”，默认展示主脑汇总，点击 agent 卡片切换对应内容，并把治理/恢复/自动化后置到主脑系统管理。

**Architecture:** 保留现有 `main_brain`、`reports`、`decisions`、`governance`、`automation`、`recovery` 数据面，不先改后端对象模型；前端新增“agent 卡片条 + 选中 agent 内容区”组合层，在 UI 层把现有运行数据重组为 `简介 / 日报 / 统计 / 审批 / 系统管理`。旧顶层 `governance / recovery / automation` 不删除能力，只从首页入口后置到主脑内容区。

**Tech Stack:** React, TypeScript, Ant Design, ECharts, Less, Vitest, Testing Library

---

## File Map

- Modify: `console/src/pages/RuntimeCenter/index.tsx`
  - 顶层 IA 收口，接入 agent 卡片 strip、选中态、下方内容区。
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
  - 新驾驶舱布局、agent 卡片、tab 内容区、系统管理二级菜单样式。
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
  - 暴露页面所需 agent 汇总、主脑数据、职业 agent 数据的轻量派生。
- Modify: `console/src/pages/RuntimeCenter/text.ts`
  - 新的人话文案、tab 名称、空态文案。
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
  - 从“首页整屏面板”收口成“主脑内容区组件”，只负责主脑 tab 内容。
- Create: `console/src/pages/RuntimeCenter/AgentCardStrip.tsx`
  - 顶部 agent 卡片条，负责排序、选中、进度、待处理图标。
- Create: `console/src/pages/RuntimeCenter/HumanCockpitPanel.tsx`
  - 下方统一内容容器，按当前选中 agent 切换主脑/职业 agent 视图。
- Create: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
  - 普通职业 agent 的 `简介 / 日报 / 统计`。
- Create: `console/src/pages/RuntimeCenter/MainBrainSystemManagement.tsx`
  - 主脑 `系统管理` tab，复用自动化、治理、恢复旧能力。
- Modify: `console/src/pages/RuntimeCenter/index.test.tsx`
  - 顶层 IA、默认主脑、agent 切换、旧 tab 隐藏测试。
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
  - 主脑 tab、审批、系统管理收口测试。
- Create: `console/src/pages/RuntimeCenter/AgentCardStrip.test.tsx`
  - 卡片排序、选中、待处理图标、主脑固定第一测试。
- Create: `console/src/pages/RuntimeCenter/HumanCockpitPanel.test.tsx`
  - 主脑/普通 agent 切换渲染测试。
- Create: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
  - 简介、早报/晚报显示规则、统计展示测试。

## Task 1: 收口顶层信息架构

**Files:**
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/text.ts`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] **Step 1: 写顶层行为测试**

覆盖以下行为：
- 默认选中主脑
- 顶层不再直接暴露 `governance / recovery / automation` 作为用户主入口
- 点击 agent 卡片后切换下方内容区

- [ ] **Step 2: 运行测试，确认失败**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] **Step 3: 在 `index.tsx` 引入选中 agent 状态和新布局**

最小实现方向：
- 保留 overview 路由
- 将主脑内容和职业 agent 内容组合到同一页
- 统一由顶部卡片条驱动下方内容区

- [ ] **Step 4: 更新文案与空态**

把首页文案改成普通人能看懂的“谁在做事、当前状态、今日推进”口径。

- [ ] **Step 5: 重跑顶层测试**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/index.test.tsx`

## Task 2: 新增 agent 卡片条

**Files:**
- Create: `console/src/pages/RuntimeCenter/AgentCardStrip.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Test: `console/src/pages/RuntimeCenter/AgentCardStrip.test.tsx`

- [ ] **Step 1: 写卡片条测试**

覆盖以下行为：
- 主脑固定第一
- 卡住/待处理优先前置
- 卡片只显示名字、职业、状态、进度、小手图标
- 点击卡片触发选中切换

- [ ] **Step 2: 运行测试，确认失败**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/AgentCardStrip.test.tsx`

- [ ] **Step 3: 实现 `AgentCardStrip.tsx`**

实现点：
- 接收 agent 列表、当前选中 agent、切换回调
- 统一排序
- 简化状态与进度表达
- 待处理显示小手图标

- [ ] **Step 4: 增加样式**

实现横向卡片条、主脑主卡、职业 agent 小卡、移动端横滑适配。

- [ ] **Step 5: 重跑卡片测试**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/AgentCardStrip.test.tsx`

## Task 3: 主脑与职业 agent 内容区组件化

**Files:**
- Create: `console/src/pages/RuntimeCenter/HumanCockpitPanel.tsx`
- Create: `console/src/pages/RuntimeCenter/AgentWorkPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Test: `console/src/pages/RuntimeCenter/HumanCockpitPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: 先写普通 agent 内容区测试**

覆盖：
- `简介 / 日报 / 统计` 三个 tab
- 简介包含职责、主要负责工作、当前重点、最新进展、当前卡点
- 日报按早报/晚报规则显示
- 统计默认近 7 天，可切近 30 天

- [ ] **Step 2: 再写主脑内容区测试**

覆盖：
- `简介 / 日报 / 统计 / 阶段总结 / 审批 / 系统管理`
- 审批先只显示待处理
- 系统管理默认打开自动化

- [ ] **Step 3: 运行组件测试，确认失败**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/HumanCockpitPanel.test.tsx console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 4: 实现 `HumanCockpitPanel.tsx`**

实现点：
- 根据当前选中 agent 判断渲染主脑或职业 agent
- 统一注入人话化后的展示数据

- [ ] **Step 5: 实现 `AgentWorkPanel.tsx`**

实现点：
- 普通 agent 简介固定结构
- 日报按早晚时段切换默认展开态
- 统计用现有数据源派生 `完成数量 / 完成率 / 质量评分`

- [ ] **Step 6: 收口 `MainBrainCockpitPanel.tsx`**

实现点：
- 去掉其“整页首页”职责
- 保留主脑专属内容生成
- 把审批和系统管理放进主脑 tab

- [ ] **Step 7: 重跑组件测试**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/HumanCockpitPanel.test.tsx console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

## Task 4: 后置治理/恢复/自动化到主脑系统管理

**Files:**
- Create: `console/src/pages/RuntimeCenter/MainBrainSystemManagement.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] **Step 1: 写系统管理后置测试**

覆盖：
- 首页普通视图不再直接出现治理/恢复/自动化大区块
- 主脑系统管理内存在二级菜单 `自动化 / 治理 / 恢复`
- 默认选中 `自动化`

- [ ] **Step 2: 运行测试，确认失败**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] **Step 3: 实现 `MainBrainSystemManagement.tsx`**

最小策略：
- 复用现有自动化 tab 和管理态数据
- 治理/恢复先以收口块方式嵌入，不做后端能力改造

- [ ] **Step 4: 从首页顶层移除旧管理入口**

只后置隐藏，不删能力、不改接口。

- [ ] **Step 5: 重跑相关测试**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx console/src/pages/RuntimeCenter/index.test.tsx`

## Task 5: 样式与回归验证

**Files:**
- Modify: `console/src/pages/RuntimeCenter/index.module.less`
- Modify: `console/src/pages/RuntimeCenter/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Create: `console/src/pages/RuntimeCenter/AgentCardStrip.test.tsx`
- Create: `console/src/pages/RuntimeCenter/HumanCockpitPanel.test.tsx`
- Create: `console/src/pages/RuntimeCenter/AgentWorkPanel.test.tsx`

- [ ] **Step 1: 补移动端/桌面样式细节**

覆盖：
- 顶部卡片条横滑
- 下方 tab 内容区留白和视觉层次
- 简化图标、进度条、小手提示

- [ ] **Step 2: 跑 Runtime Center 全量前端测试**

Run: `cmd /c npm --prefix console run test -- --run console/src/pages/RuntimeCenter`

- [ ] **Step 3: 跑 console 构建**

Run: `cmd /c npm --prefix console run build`

- [ ] **Step 4: 人工检查关键页面路径**

重点看：
- `/runtime-center`
- 默认主脑
- 切换职业 agent
- 主脑审批
- 主脑系统管理

- [ ] **Step 5: 更新推进状态文档（如本轮落地范围改变）**

必要时同步：
- `TASK_STATUS.md`
- `FRONTEND_UPGRADE_PLAN.md`
- `RUNTIME_CENTER_UI_SPEC.md`
- `AGENT_VISIBLE_MODEL.md`
