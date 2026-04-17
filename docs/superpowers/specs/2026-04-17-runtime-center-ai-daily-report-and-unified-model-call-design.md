# 2026-04-17 Runtime Center AI Daily Report And Unified Model Call Design

## Why This Exists

`Runtime Center` 的 `日报` 已经偏成系统字段列表：

- 正文混入 `汇报数 / 证据数 / 待确认数`
- 前端在后端缺字段时本地拼接 fallback
- 各模型调用点分别维护自己的超时、重试、校验和报错

这会带来两个正式问题：

1. `早报 / 晚报` 不再像给人看的工作汇报，而像给系统看的运行摘要
2. 模型是全局依赖，但模型调用纪律没有全局统一，导致错误边界、超时策略、结构化校验和观测口径分裂

本设计把这两件事一起收口：

- `日报` 改回 AI 生成的人话汇报
- 模型调用规则收进统一 runtime model call 层

## Goals

1. `日报` 页面只展示 `早报 / 晚报` 两份中文汇报，不再混入统计数字和审批信息。
2. `早报 / 晚报` 固定为 6 个正式槽位，不再使用弱约束的 `items[]` 自由列表。
3. `日报` 正文必须由 AI 生成，不做本地拼句 fallback。
4. 所有 runtime 侧模型调用统一执行 `120s` 超时、`3` 次重试、中文/结构化校验、错误分级和失败观测。
5. 模型短时失败只打断当前模块；模型持续不可用时升级为系统级错误。

## Non-Goals

- 本次不重做主脑/职业 agent 的其它 cockpit 信息架构。
- 本次不把所有模型调用都改成流式协议。
- 本次不把统计、审批、系统管理重新设计成新的导航结构；本次只要求它们不要混入日报正文。

## Runtime Center Daily Report Contract

`日报` 是正式汇报面，不是系统摘要面。

### Page Rules

- `日报` 页面只负责展示 `早报 / 晚报`
- `统计`、`审批`、`系统管理` 继续走各自读面
- `日报` 正文不出现任何数量型系统指标

### Morning Report

`早报` 固定 3 个槽位：

- `今天要做什么`
- `重点先做什么`
- `风险提醒`

### Evening Report

`晚报` 固定 3 个槽位：

- `今天完成了什么`
- `产出了什么结果`
- `明天继续什么`

### Content Rules

- 正文必须全中文
- 允许出现具体产物名或任务名
- 不允许把 `汇报数 / 证据数 / 待确认数` 这类数字塞进正文
- 不允许显示本地 fallback 拼句

## Daily Report Payload

后端正式合同改为：

```text
RuntimeHumanCockpitReportBlock
  kind: morning | evening
  title: 早报 | 晚报
  status: ready | error
  sections: ReportSection[]
  generated_at: ISO datetime | null
  error: ReportError | null

ReportSection
  key: stable internal key
  label: 中文标题
  content: 中文正文

ReportError
  code: string
  message: string
```

固定 `sections`：

- `早报`
  - `what_today`
  - `priority_first`
  - `risk_note`
- `晚报`
  - `done_today`
  - `produced_result`
  - `next_step`

同时，`RuntimeHumanCockpitPayload` 新增：

```text
model_status
  level: ok | error
  code: string | null
  message: string | null
  consecutive_failures: int
  last_failure_at: ISO datetime | null
```

## Unified Model Call Rules

这套规则不是日报专用，而是 runtime 全局统一规范。

### Base Policy

- 单次等待反馈：`120s`
- 单次超时后自动重试
- 最大重试次数：`3`
- 仍失败则本次调用失败

### Validation

- 中文任务要求全中文输出
- 结构化任务要求 schema 校验通过
- 空返回、非中文、结构不合法都视为失败
- 不允许“有字就算成功”

### Error Levels

#### Module Error

下列情形先视为模块级错误：

- `120s` 超时后重试 `3` 次仍失败
- 结构化返回不合法
- 中文校验失败
- 上游 provider 临时不可用

结果：

- 当前模块显示错误
- 不做本地兜底

#### System Error

模型是系统全局依赖。

当满足以下条件时，升级为系统级模型错误：

- 连续 `3` 次完整调用链失败
- 且最近 `15` 分钟没有任何成功调用

结果：

- `Runtime Center` 顶部和关键主链入口显示统一系统级错误
- 业务运行面停止假装可用
- 维护/诊断入口仍可访问

一旦重新出现成功调用，系统级错误自动解除。

## Integration Scope

统一模型调用层第一批覆盖：

- `Runtime Center` `早报 / 晚报` 生成
- Buddy onboarding contract compile
- chat writeback decision
- industry draft generation
- runtime provider 对外暴露的 active chat model

## Runtime Center Integration

`overview_cards.py` 不再直接拼装系统句子，而是：

1. 汇总日报事实摘要
2. 调日报生成服务
3. 日报生成服务调用统一模型调用层
4. 返回固定结构 `ReportBlock`

前端改为：

- 只渲染 `sections`
- 删除本地日报 fallback 构造
- `status=error` 时显示正式错误块
- `model_status.level=error` 时显示系统级错误提醒

## Verification Requirements

至少覆盖以下验证：

### Backend

- 统一模型调用层的超时、重试、中文校验、结构化校验、错误升级
- Buddy onboarding / writeback / industry draft 对统一层的接线
- `Runtime Center` cockpit payload 的新日报合同

### Frontend

- `日报` 只渲染固定 6 槽位
- 前端不再本地合成日报
- 模块级错误显示
- 系统级模型状态提醒显示

## Rollout Order

1. 统一模型调用层
2. 迁移 Buddy onboarding / writeback / industry draft
3. 迁移 `Runtime Center` 日报后端合同
4. 更新前端类型与渲染
5. 同步 `TASK_STATUS.md` 与 focused verification
