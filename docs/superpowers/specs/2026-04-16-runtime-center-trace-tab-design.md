# 2026-04-16 Runtime Center Trace Tab Design

## Status

当前真实状态已经不是“从零开始设计 trace”：

- 后端 `cockpit trace` 合同已经正式落地
- `overview_cards.py` 已经会构建主脑和职业 agent 的人类可读 `trace` 行
- `main_brain.cockpit.main_brain.trace` 与 `main_brain.cockpit.agents[].trace` 已进入正式 payload

现在缺的不是后端真相，而是前端还没有把这组正式字段接成普通用户可读的 `追溯` tab。

## Why This Still Exists

当前 `Runtime Center` 的驾驶舱页面已经有：

- `简介`
- `日报`
- `统计`

但用户还看不到“今天它到底做了什么”的顺序化执行细节。

这次要补的是一个很轻的 `追溯` 读面：

- 像日志，但不是运维日志墙
- 一行一条
- `时间 + 内容`
- 能看主脑
- 也能看每个职业 agent

## Goals

1. 复用现有正式 `trace` payload，为主脑和职业 agent 都补上 `追溯` tab。
2. `追溯` 只展示今天的人类可读执行细节，不展示原始 JSON、prompt、tool payload。
3. 前端只做读面渲染，不在前端重新拼业务真相。
4. 需要深看某条记录时，继续复用现有 `Drawer`，不另开平行页面。

## Non-Goals

- 不重新设计后端 `trace` 合同
- 不重做 `overview_cards.py` 的 trace builder
- 不新增第二套“日志中心”或“系统控制台”
- 不让前端自己从 assignments / reports / evidence 重新猜 trace

## Current Truth

### Backend

后端已具备：

- `RuntimeHumanCockpitTraceEntry`
- `RuntimeHumanCockpitMainBrain.trace`
- `RuntimeHumanCockpitAgent.trace`
- 由 cockpit builder 统一构建 today-first、human-readable 的 trace 行

### Frontend

前端当前还缺：

- `console/src/api/modules/runtimeCenter.ts` 对 `trace` 的正式类型映射
- `RuntimeCenter/index.tsx` 对 `trace` 的 surface 映射
- `MainBrainCockpitPanel.tsx` 的 `追溯` tab
- `AgentWorkPanel.tsx` 的 `追溯` tab
- 共享 trace 渲染组件

所以现在是“后端有真相，前端没读面”，而不是“整条 trace 链还没做”。

## Chosen Approach

这次采用：

- 直接消费现有 `cockpit trace` 正式 payload
- 在现有 cockpit panel tab 结构里新增 `追溯`
- 新建一个共享 trace section 组件
- 复用现有 `Drawer` 作为深链详情入口

不采用：

- 前端临时拼装 trace
- 另开独立 trace 页面
- 再回头扩张后端 schema

## Trace Presentation

### Core Form

`追溯` 只显示一块轻量日志区。

每行固定为：

- `时间  内容`

可选轻标签：

- `INFO`
- `WARN`
- `ERROR`

但整体视觉必须轻，不做成系统控制台。

### Ordering

- 默认只显示今天
- 按时间正序
- 旧的在上
- 新的在下

### Interaction

- 默认不分组
- 默认不折叠
- 默认不做复杂过滤
- 如果某条 trace 带 `route`，该行显示轻量 `详情` 入口
- 点击后复用现有 `Runtime Center` 详情 `Drawer`

### Empty State

当今天还没有可展示的追溯时，显示：

- `今天还没有新的追溯记录。`

## Acceptance Standard

通过标准只有这些：

1. 用户进入驾驶舱后，选中主脑或任一职业 agent，都能看到 `追溯` tab。
2. `追溯` 展示的是正式 payload 里的 trace，不是前端临时拼的卡片。
3. 日志是一行一条，按时间从旧到新。
4. 有 `route` 的记录可以继续打开现有 `Drawer`。
5. 没有 trace 时显示明确空态，不显示脏占位。

## Verification

至少补三类验证：

1. 前端类型 / surface 映射测试
2. cockpit trace 渲染测试
3. Runtime Center 面板切换与详情打开测试

后端只做回归确认，不再重复把“trace 合同是否存在”当成本轮主目标。
