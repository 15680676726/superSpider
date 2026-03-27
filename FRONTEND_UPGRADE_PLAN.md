# FRONTEND_UPGRADE_PLAN.md

本文件用于定义 `CoPaw` 前端从“设置页集合”升级为“运行中心 / 指挥中心 / 结果可见化中心”的路线。

当前总架构文档主要偏后端与中枢设计，本文件用于补齐前端升级方向。

---

## 0. 与当前开发计划对齐

截至 `2026-03-11`：

- `Phase A` 已完成
- `Phase B 行业初始化 MVP` 已完成
- `implementation_plan.md` 已改为新的四大版本计划：`V1 / V2 / V3 / V4`

因此本文件从现在开始不再按旧“前端独立阶段”理解，而是作为四个版本的前端对齐文档使用。

明确约束：

- 前端版本推进必须跟随后端版本推进
- 不允许只补后端、不补前端可见面
- 不允许前端为了抢进度自己造本地对象或 fallback 真相源

四大版本的前端对应关系：

| 版本 | 前端主题 | 关键页面 |
|---|---|---|
| `V1` | 行业团队正式化 | `Onboarding`、`Industry`、`AgentWorkbench`、`RuntimeCenter` 行业联动 |
| `V2` | 长期自治运营化 | `Knowledge`、`Reports`、`Performance`、`Calendar`、`Chat`、`AgentWorkbench` 增强 |
| `V3` | 产品化与规模化 | `CapabilityMarket`、`RuntimeCenter` 治理终态、`Settings`、首页健康/恢复入口 |
| `V4` | 预测与主动寻优 | `Predictions`、`Reports/Performance` 的预测视图、`RuntimeCenter` 的预测治理联动 |

明确边界：

- `V1/V2/V3` 仍然是必须先完成的稳定化版本
- `V4` 是建立在前三版稳定完成后的正式下一阶段
- 不允许为了赶 `V4` 反向污染当前前三版边界

---

## 1. 前端升级目标

前端升级的最终目标不是继续增加更多设置页，而是让系统做到：

- 一进来就知道系统在干什么
- 一进来就知道每个 agent 在负责什么
- 一进来就知道哪些地方需要人工决策
- 一进来就能看到结果、风险、证据、成长轨迹
- 一进来就会用，不需要先理解内部技术模块

前端最终应该成为：

> 运行事实的可见化面板，而不是技术配置的堆叠面板。

---

## 2. 前端设计原则

### 2.1 结果可见化优先

后端能力如果前端完全看不见，就不算真正完成。

前端必须优先表达：

- 目标
- 执行中事项
- agent 职责
- 当前风险
- 当前证据
- 最近产出

### 2.2 运行事实优先于技术分类

前端不要优先按这些技术模块组织：

- channels
- models
- skills
- mcp
- envs
- cron

前端应优先按运行对象组织：

- Goals
- Agents
- Tasks
- Environments
- Evidence
- Patches
- Decisions

### 2.3 看懂优先于配置

用户首先应该能“看懂现在发生了什么”，其次才是“去改配置”。

### 2.4 极简操作优先

避免：

- 深层菜单
- 过多弹窗
- 先配置一堆参数才看见结果
- 重要信息埋在技术细节里

---

## 3. 前端最终信息架构

建议未来前端以 6 个一级对象为主：

1. `Overview`
2. `Agents`
3. `Tasks`
4. `Evidence`
5. `Decisions & Patches`
6. `System & Settings`

说明：

- `System & Settings` 仍然保留，但降级为辅助区域
- 真正的一等入口必须围绕运行对象

---

## 4. 首页目标：运行总览

首页打开第一眼，应回答 4 个问题：

1. 系统当前目标是什么
2. 系统今天在推进什么
3. 哪些 agent 正在工作
4. 哪些地方需要我介入

### 首页关键模块

- 全局目标概览
- 今日推进摘要
- 运行中 agent 列表
- 当前高风险事项
- 待确认决策区
- 今日新增证据数
- 今日重要产出摘要

### 首页不应该优先展示的内容

- 技术配置表单
- 冗长聊天记录
- 孤立的工具入口

---

## 5. Agent 可见化是前端一级目标

前端必须把每个 agent 做成一等可见对象。

每个 agent 至少要有：

- 职责卡
- 工作台
- 日报入口
- 周报入口
- 成长轨迹入口

说明：

- agent 页面不应以“聊天记录”为主
- agent 页面应以“工作面”和“责任面”为主

---

## 6. 关键前端页面规划

### 6.1 Overview（运行总览）

展示：

- 当前总目标
- 任务推进概况
- agent 状态概况
- 风险概况
- 证据概况
- 待确认事项

### 6.2 Agents（agent 列表与工作台）

展示：

- agent 职责卡列表
- 每个 agent 的状态、环境、产出、风险
- 进入单个 agent 工作台

### 6.3 Tasks（任务视图）

展示：

- 当前任务树
- 所属 goal
- owner agent
- 当前状态
- 最近证据
- 风险级别

### 6.4 Evidence（证据中心）

展示：

- 最近动作证据
- 按 agent / task / risk 过滤
- 产物与回放入口

### 6.5 Main Brain Suggestions & Confirmations（主脑建议与例外确认）

产品口径：

- 默认由主脑决定，不把 `Decision / Patch` 当成普通客户的一线心智。
- 普通客户优先看到“主脑建议 / 需要你确认 / 已自动生效建议”，而不是底层治理原语。
- 只有主脑无法独立判断，或动作触及外部责任边界时，才进入显式确认。

展示：

- 需要人工确认的主脑建议
- 主脑提出的修复 / 优化建议
- 已自动应用的低风险建议
- 成长轨迹关联项

### 6.6 System & Settings（系统与设置）

展示：

- channels
- models
- envs
- mcp
- system health

说明：

- 这些页面仍保留，但不再是前端主入口
- `Channels` 的 canonical route 已固定为 `Settings -> /settings/channels`
- `Heartbeat / Cron Jobs` 不再作为独立设置页存在，而是收口进 `RuntimeCenter -> Automation`
- `Heartbeat` 的 canonical API 已从 `/api/config/heartbeat` 切换到 `/api/runtime-center/heartbeat`，页面不再直接依赖旧 config surface

---

## 7. 前端分阶段升级路线

## Frontend Phase A：运行总览 MVP

### 目标

- 让系统第一次具备“结果可见化”能力

### 交付物

- 运行总览首页
- agent 卡片列表（最小版）
- 风险提醒区
- 待确认事项区

### 预计工期

- `1 ~ 1.5` 周

---

## Frontend Phase B：Agent 工作台

### 目标

- 每个 agent 具备清晰的职责卡和工作台

### 交付物

- 单 agent 页面
- 职责展示
- 当前任务
- 当前环境
- 最近证据
- 日报入口 / 周报入口 / 成长轨迹入口

### 预计工期

- `1 ~ 2` 周

---

## Frontend Phase C：Evidence / Reports

### 目标

- 把结果和产出真正沉淀成可见化的证据与报告体系

### 交付物

- 证据中心
- 日报页面
- 周报页面
- 证据过滤与回放入口

### 预计工期

- `1 ~ 2` 周

---

## Frontend Phase D：Decisions / Patches / Growth

### 目标

- 把治理与成长变成前端第一类对象

### 交付物

- patch proposal 列表
- 决策确认中心
- 成长轨迹视图

### 预计工期

- `1 ~ 2` 周

---

## 8. 前后端协作边界

### 8.1 前端不直接围绕旧 manager 设计

前端应优先围绕这些未来对象设计：

- `Goal`
- `Agent`
- `Task`
- `EnvironmentMount`
- `EvidenceRecord`
- `Patch`
- `DecisionRequest`

### 8.2 前端可以早于完整后端完成视觉骨架

允许：

- 先定义页面结构
- 先定义字段协议
- 先做 mock 数据视图

但必须避免：

- 直接把旧技术分类页面当成最终形态

---

## 9. 当前建议的下一步

前端下一步优先做两件事：

1. 基于 `RUNTIME_CENTER_UI_SPEC.md` 定义总览页和 agent 职责卡
2. 基于 `AGENT_VISIBLE_MODEL.md` 固定每个 agent 的可见字段模型

---

## 10. 一句话总结

前端升级的核心不是“重做 UI 风格”，而是：

> 让系统从技术设置台，升级为运行事实清晰、结果持续可见、人人一进来就会用的运行中心。

---

## 11. 当前执行映射

为了避免和新的 `implementation_plan.md` 脱节，当前前端执行统一按下面映射推进：

### `V1` 前端收口

- `Onboarding`
  - 行业输入
  - 团队方案预览
  - 激活确认
  - 启动前检查
- `Chat`
  - `/chat` 只允许从 `Industry` / `AgentWorkbench` 打开的正式 agent 线程进入
  - 行业聊天前台保持单一控制线程，默认只进入 `Spider Mesh 执行中枢`
  - 执行型请求不再暴露 `task-chat:{task_id}` 第二聊天入口；结果应通过 `assignment / task / report / evidence / work-context` 正式读面回看
  - `/chat` 的默认主屏应保持“聊天优先”，只保留当前对话对象、线程类型、必要状态标签与跳转入口；复杂运行信息不应默认铺满整页
  - 控制线程左侧来源列表、V7 控制面、报告回流卡片、任务执行面、参与智能体与自动复盘等信息，应优先收纳到侧栏、二级抽屉或正式读面，而不是再造第二聊天区
  - Chat 内仍必须提供多任务看板、筛选与批量管理，但这些能力应作为按需打开的治理面，而不是默认主视觉
  - 长期记忆在任务线程内必须按 `task` 严格隔离，不能继续把其他任务的 agent 记忆直接串进来
  - 左侧来源使用真实角色 / agent 列表，不再展示 `/chats` session 壳、`/sessions` 管理页或行业场景下的 `New Chat`
  - widget session persistence 统一走 `Runtime Center Conversation` facade
- `Industry`
  - 团队总览
  - 角色卡片
  - 首轮目标 / schedule / 当前状态
- `RuntimeCenter`
  - 行业实例与 goal/schedule/detail 联动
  - `Automation` 子页承接 heartbeat 与 schedules 的统一读写、run/pause/resume/delete 动作；heartbeat detail 同时暴露 `status / last_run_at / next_run_at / query_path`
- `AgentWorkbench`
  - 系统岗与业务岗职责、风险、能力边界可见
- `Settings`
  - `Channels` 正式收口到 `/settings/channels`
  - 旧 `/channels`、`/cron-jobs`、`/heartbeat` 不再保留 redirect 壳或平行页面实现，主路由只暴露 canonical route

### `V2` 前端收口

- `Knowledge`
- `Reports`
- `Performance`
- `Calendar`
- `Chat`
  - Manager 委派、回传、待确认提醒
- `AgentWorkbench`
  - 知识、证据、成长、任务层级、冲突状态可见

### `V3` 前端收口

- `CapabilityMarket`
  - `精选中心` 后必须直接提供 `工作流` 页签，不再把 workflow/n8n workflow 入口藏到平行深链
  - `工作流` 卡片应复用精选中心的卡片式入口，而不是新造第三套工作流市场 UI
  - 每条 workflow 在进入 preview / launch 前必须先选对应 `agent`，前端应把该选择显式作为 `owner_agent_id` 传给后端，而不是本地猜测
  - `doctor` 必须产品化为系统内置体检动作，而不是额外安装组件
- `RuntimeCenter`
  - 批量审批
  - patch rollout / rollback
  - 审计与治理视图
  - emergency stop / resume
- `Settings`
  - 备份恢复
  - 启动自检
  - provider fallback / 集成配置
- 首页 / CommandCenter 等价入口
  - 健康状态
  - 启动失败提示
  - 恢复入口

### `V4` 前端收口

- `Predictions`
  - 预测议题列表
  - 单次预测详情
  - 多场景对比
  - 信号来源与假设边界
- `Predictions`
  - 主脑周期预测结果
  - recommendation 队列与治理状态
  - capability gap 与 telemetry
  - 审批与驳回入口
- `Reports`
  - 预测 vs 实际结果复盘
- `Performance`
  - 命中率、偏差率、建议采纳率、执行收益
- `RuntimeCenter`
  - prediction decision / evidence / approved action 联动
---

## 8. 2026-03-18 同步：post-`V6` 的前端升级方向

post-`V6` 的下一正式前端同步范围已登记为 `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`。

这一轮不是只给 Runtime Center 多加几张卡片，而是要求前端从“goal/task/schedule 可见化”升级为“主脑身份、责任车道、周期计划、职业派工、结构化汇报回流”的同链路可见化。

必须同步覆盖：

- `Runtime Center`
  - 新增 `carrier / strategy / lanes / cycle / assignments / agent-reports` 一等对象
  - 首页直接回答“主脑现在是谁、这轮 focus 是什么、派给谁了、哪些汇报待处理”
- `/industry`
  - 从“团队初始化 + 团队详情”升级为长期载体工作台
  - 同步展示 `mission / strategy / lanes / current cycle / backlog / recent reports`
- `Chat`
  - 保持“单主脑控制线程”
  - 明确展示本轮 focus、待主脑处理 report、当前这句 writeback 将进入 `strategy / lane / backlog / immediate goal` 哪一类
- `AgentWorkbench`
  - 明确把职业 agent 呈现为执行位，不再假装每个 agent 都是小主脑
  - 每个职业 agent 至少显示 `assignment / task / routine / latest report / escalation`

前后端一致性规则：

- 前端不本地推导 `current_cycle`
- 前端不本地推导 `current_focus`
- 前端不本地推导 `assignment owner`
- 前端不本地推导某条指令最终写进了 `strategy / lane / backlog / goal`

这些都必须直接消费后端正式读面。
