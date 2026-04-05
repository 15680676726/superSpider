# RUNTIME_CENTER_UI_SPEC.md

本文件定义未来 `CoPaw` 运行中心（Runtime Center）的 UI 规范。

运行中心的核心目标是：

- 让系统当前目标清晰可见
- 让每个 agent 的职责与状态清晰可见
- 让结果、风险、证据与待确认事项清晰可见
- 让用户不用先理解技术模块，也能直接知道系统当前在做什么

---

## 0. 与当前版本计划对齐

截至 `2026-03-11`，`implementation_plan.md` 已切换为 `V1 / V2 / V3 / V4` 四个版本计划。

因此 Runtime Center 的 UI 规范也按三版本理解：

- `V1`
  - 行业实例、团队结构、角色职责、goal/schedule 联动
- `V2`
  - 知识、报告、绩效、委派、冲突、成长的长期运营可见化
- `V3`
  - 治理终态、批量审批、patch rollout / rollback、系统健康与恢复入口
- `V4`
  - prediction decision、建议动作、执行结果、预测复盘的治理联动

明确约束：

- Runtime Center 不是只读监控墙
- 也不是平行真相源
- 它必须跟随后端版本推进，把运行事实、治理事实、恢复事实做成一等可见面

### 0.1 `2026-04-06` Buddy 摘要位补充口径

- Runtime Center 不是 Buddy 主场。
- Buddy 的主场仍然是 `Chat`，Runtime Center 只保留一个紧凑摘要位，回答“主脑现在要把人带到哪里、此刻为什么是这一步”。
- 这个摘要位默认至少显示：
  - 最后目标
  - 当前任务
  - 为什么现在先做这个
  - 人类此刻唯一需要执行的下一步动作
  - 成长连续性摘要
- Runtime Center 不负责承接完整陪聊、命名、情绪接住、强陪跑对话；这些必须回到 `Chat`。
- `Industry` 的执行载体调整信息可以在 Runtime Center 被引用，但 Runtime Center 不应重新变成第二个身份创建入口。

---

## 1. 运行中心的一级目标

运行中心应优先展示 5 件事：

- 当前目标
- 当前环境
- 当前 owner
- 当前风险
- 当前证据

这是整个前端的最高优先级。

补充说明：

- 如果 Buddy 摘要与 Chat 主场展示不一致，以正式 Buddy surface / projection 为准。
- Runtime Center 可以显示 Buddy 当前节奏、风险与提醒，但不要把 Buddy 渲染成与职业执行位并列的普通 agent 卡。

---

## 2. 运行中心首页结构

首页建议分为以下 9 个区域：

### 2.1 顶部全局状态条

显示：

- 当前总目标
- 当前总状态（running / paused / blocked / degraded）
- 今日任务数
- 运行中的 agent 数
- 高风险项数
- 待确认项数

### 2.2 今日推进总览

显示：

- 今日完成事项数
- 今日新增证据数
- 今日新增产物数
- 今日失败 / 阻塞事项数
- 今日自动应用 patch 数

### 2.3 Agent 职责卡区域

显示：

- 每个 agent 的职责卡
- 快速状态
- 快速风险
- 快速进入工作台

### 2.4 当前关键任务区域

显示：

- 正在推进的关键任务
- 任务 owner
- 当前状态
- 风险级别
- 最近证据

### 2.5 风险提醒区域

显示：

- 当前高风险动作
- 当前阻塞任务
- 外部副作用待确认项

### 2.6 待确认事项区域

显示：

- 待确认决策
- 待确认 patch
- 待确认外部执行动作

### 2.7 结果产出区域

显示：

- 今日重要结果
- 最新日报入口
- 最新周报入口
- 最新 artifact

### 2.8 证据流摘要区域

显示：

- 最近证据时间线
- 最近关键动作
- 最近失败/回滚事件

### 2.9 Legacy Gates Area（已移除）

Legacy delete-gate surfaces 已从 Runtime Center UI 中移除，不再提供专门区块或审计/清理按钮。
若 `WORKING_DIR` 仍残留 `jobs.json` / `chats.json` / `sessions/` 文件，改为人工文件级清理与验证。

---

## 3. Agent 职责卡 UI 规范

每张 agent 卡必须至少包含：

- 名称
- 角色定位
- 岗位类型（`employment_mode`）
- 激活方式（`activation_mode`）
- 当前 owner
- 当前状态
- 当前主任务
- 当前环境
- 当前风险
- 今日产出摘要
- 最近证据摘要
- 快捷入口：
  - 工作台
  - 日报
  - 周报
  - 成长轨迹

### 卡片状态建议

- `idle`
- `running`
- `waiting`
- `blocked`
- `needs-confirm`
- `degraded`

### 卡片颜色建议

- 绿色：稳定推进
- 黄色：等待 / guarded
- 红色：阻塞 / confirm / 失败
- 灰色：空闲 / 暂停

### 岗位标签补充

Agent 卡、Industry 团队详情、Agent Workbench 当前都应复用同一套 seat 标签语义：

- `employment_mode=career | temporary`
- `activation_mode=persistent | on-demand`

显示规则：

- `career` 用于表达长期职业位，可长期复用
- `temporary` 用于表达短期 seat，应使用醒目提示，避免误解为长期编制
- `persistent` / `on-demand` 只表达唤醒方式，不能替代 `career` / `temporary`
- 当 `temporary` seat 已进入“待退场”条件时，界面应显式提示 operator 这是即将退出团队的短期执行位

---

## 4. 单个 Agent 工作台结构

建议单个 agent 工作台分 6 个页签：

### 4.1 Overview

显示：

- 角色定义
- Role Contract（含 `employment_mode / activation_mode`）
- 当前目标
- 当前状态
- 当前风险
- 当前 owner

### 4.2 Tasks

显示：

- 当前任务列表
- 最近完成任务
- 阻塞任务

### 4.3 Environment

显示：

- 当前环境挂载
- 浏览器 / 桌面 / 渠道 / 工作目录状态
- 最近环境变更

#### Shared Surface Host 字段清单

对于 live `browser / desktop / document` surface，Runtime Center 应先显示共享 host/session 字段：

- `surface_kind`
- `host_mode`
- `lease_class`
- `access_mode`
- `session_scope`
- `account_scope_ref`
- `continuity_source`
- `handoff_state`
- `resume_kind`
- `verification_channel`
- `capability_summary`
- `current_gap_or_blocker`

显示规则：

- 共享 host 字段优先于 surface-specific 字段显示
- 不允许把 live surface 继续压缩成单一 `*_surface_ready`
- `handoff_state` 与 `resume_kind` 应使用跨 browser/desktop 一致的标签语义
- `lease_class` 与 `access_mode` 必须让 operator 一眼看出当前是 `writer / read-only / queued`
  哪一种姿态，而不是把写锁争用藏进日志

#### Seat Runtime / Host Companion 字段清单

对 execution-side 的长期 Windows 工位，Runtime Center 还应显式显示：

- `seat_id`
- `seat_status`
- `host_id`
- `user_session_ref`
- `desktop_session_ref`
- `host_companion_status`
- `workspace_scope`
- `active_surface_mix`
- `event_stream_status`

显示规则：

- `seat` 是 execution agent 当前持有的正式工位，不应退化成“某个桌面工具已连接”
- `host_companion_status` 应回答当前宿主连续性是否真实在线
- 当 seat 存在时，应先显示 seat/workspace 概况，再显示单个 browser/app surface

#### Workspace Graph 字段清单

对 live workspaces，Runtime Center 至少应显示：

- `workspace_id`
- `browser_context_summary`
- `app_set_summary`
- `file_doc_summary`
- `clipboard_bucket_ref`
- `download_bucket_ref`
- `lock_summary`
- `pending_handoff_summary`
- `latest_host_event_summary`

显示规则：

- 工作区是正式执行面，不应只让 operator 分别点开 browser/desktop/file 卡片自行拼脑图
- 对跨 `browser + app + file/doc` 的任务，UI 应优先显示 workspace，而不是零散 surface 列表
- `Workspace Graph` 是 projection，不是新的运行真相源；它必须与 task/runtime/environment detail 保持一致
- 当 host event 正在影响执行时，workspace 卡片应先显示 blocker/recovery 状态

#### Browser Body 字段清单

对 `browser` 环境，Runtime Center 不应只显示一个模糊的“浏览器已连接 / 未连接”标签。

至少应显示：

- `browser_mode`
  - `managed-isolated | attach-existing-session | remote-provider`
- `login_state`
  - `anonymous | authenticated | unknown`
- `tab_scope`
  - `single-tab | tab-group | browser-wide`
- `active_site`
  - 当前站点/系统标识，而不是只显示 URL 碎片
- `site_contract_status`
  - `missing | read-only | writer-ready | handoff-required | blocked`
- `handoff_state`
  - `none | requested | active | returned | manual-only-terminal`
- `resume_kind`
  - `resume-environment | rebind-environment | attach-environment | fresh | resume-after-human-*`
- `last_verified_anchor`
  - 最近一次正式 verify 使用的 URL / title / DOM anchor 摘要
- `capability_summary`
  - 至少覆盖 `multi_tab / uploads / downloads / pdf_export / storage_access / locale_timezone_override`
- `current_gap_or_blocker`
  - 当前 mode gap / site contract gap / handoff blocker

显示规则：

- 不允许把 mode-dependent 差异压扁成统一 `browser_surface_ready`
- 对已知后台/站点，应优先显示 `site_contract_status`，而不是让 operator 猜“为什么现在不能点”
- 发生 handoff 时，应显式看到 handoff 原因与是否已满足 return 条件
- 当 browser body 处于 `attach-existing-session` 时，界面应提醒这是“续接真实用户浏览器”，不是可随意重建的隔离 profile

#### Windows Desktop Body 字段清单

对 `desktop` 环境，当前应按 Windows-first 口径显示：

- `app_identity`
  - 当前应用/系统身份
- `window_scope`
  - `single-window | window-group | app-wide`
- `active_window_ref`
  - 当前前台或目标窗口锚点
- `active_process_ref`
  - 当前进程锚点
- `app_contract_status`
  - `missing | read-only | writer-ready | handoff-required | blocked`
- `control_channel`
  - `accessibility-tree | window-tree | process-window | vision-fallback`
- `writer_lock_scope`
  - 当前窗口/文档/账号写锁范围
- `window_anchor_summary`
  - 最近一次 verify 使用的窗口/控件/区域锚点

显示规则：

- 当前仓库默认应把 Windows desktop body 当成正式 surface，而不是附属调试能力
- 对已知应用，优先显示 `app_contract_status`，而不是只显示“桌面已连接”
- 当 `vision-fallback` 正在生效时，界面应显式提醒 operator 当前验证可信度下降
- 若发生登录/UAC/模态框/焦点争用 handoff，UI 应先显示 handoff/blocker，而不是继续把桌面 body 标成普通 running

#### Host Event 字段清单

对 execution-side 宿主事件，Runtime Center 至少应显示：

- `latest_host_event_type`
- `latest_host_event_at`
- `event_stream_health`
- `pending_host_blocker`
- `last_recovery_action`

显示规则：

- host event 不应只写日志；它应成为 runtime 可见事实
- `Host Event Bus` 是运行机制，不是第二套 event truth store
- `download-completed / modal-or-uac-appeared / process-exited / lock-unlock / network-or-power-changed`
  这类事件应能直接解释“为什么系统现在停住或恢复了”

### 4.4 Evidence

显示：

- 最近证据流
- 最新 artifact
- 回放入口

### 4.5 Reports

显示：

- 今日日报
- 本周周报
- 历史报告索引

### 4.6 Growth

显示：

- 成长轨迹
- 已应用 patch
- proposal 历史

---

## 5. 任务页 UI 规范

任务页应至少展示：

- 任务标题
- 所属 goal
- owner agent
- 当前阶段
- 当前状态
- 当前风险
- 当前环境
- 最近证据
- 最近结果摘要
- 相关 patch / decision

任务页不应只显示聊天记录。

---

## 6. Evidence 中心 UI 规范

证据中心应支持以下视角：

- 按 agent 查看
- 按 task 查看
- 按风险查看
- 按时间查看
- 按 capability 查看

每条证据应至少显示：

- 时间
- actor
- task
- capability
- environment
- risk
- result summary
- artifact / replay 入口

---

## 7. 主脑建议与例外确认 UI 规范

产品口径：

- 底层正式对象仍是 `DecisionRequest / Patch`，用于治理、审计与回放。
- 普通用户面不应要求理解这些内部对象，产品优先显示为“主脑建议 / 需要你确认 / 待生效建议”。
- 默认由主脑决定；只有主脑无法独立判断，或动作触及真实外部责任边界时，才显式请求人类确认。

### 7.1 需要你确认

显示：

- 主脑建议动作
- 为什么需要你确认
- 风险等级
- 影响范围
- 来源 agent / task
- 证据摘要

### 7.2 主脑变更建议

显示：

- 主脑提出的修复 / 优化建议
- 建议类型
- 来源证据
- 风险等级
- 当前状态（draft / auto-applied / confirmed / rejected）
- 是否已由主脑自动生效

---

## 8. 报告视图规范

### 8.1 日报

日报必须标准化展示：

- 今日目标
- 今日完成事项
- 今日证据摘要
- 今日结果产出
- 阻塞与风险
- 明日计划

### 8.2 周报

周报必须标准化展示：

- 周目标推进率
- agent 概览
- 高价值成果
- 风险与异常
- 瓶颈分析
- 下周建议

---

## 9. 交互原则

运行中心交互必须遵守：

- 先看结果，再看配置
- 先看对象，再看技术模块
- 先看风险，再做动作
- 先看证据，再做判断

---

## 10. 第一版 MVP 最小落地内容

第一版运行中心 MVP 只要先做出以下内容，就已经有明显质变：

- 全局运行总览页
- agent 职责卡列表
- 待确认事项区
- 最近证据流摘要
- 单个 agent 工作台入口

---

## 11. 一句话总结

运行中心不是“另一个管理后台”，而是：

> 把系统目标、agent 状态、风险、证据和产出压缩成任何人一进来就能看懂的可视化工作面。
---

## 10. Post-`V6`：主脑长期自治 UI 扩展（planned）

下一正式阶段的 Runtime Center 不再只围绕 `goal / task / schedule / evidence` 展示，而要把 `carrier / strategy / lane / cycle / assignment / report` 做成正式 operator surface。

### 10.1 顶部全局状态条必须补齐

- 当前 `carrier`
- 当前 `mission / north star`
- 当前 `cycle type`
- 当前 `cycle deadline`
- 当前 `focus count`
- 未消费 `agent report` 数
- 待主脑决策项数

### 10.2 首页必须新增的 6 个区块

- `Main Brain`
  - 主脑身份、使命、当前状态
- `Current Cycle`
  - 当前周期、focus、review 截止时间、为什么排这些
- `Operating Lanes`
  - 每条 lane 的健康度、owner 策略、最近阻塞
- `Assignments`
  - 这轮派工给了谁，输出预期是什么
- `Agent Reports`
  - 最新 completion / blocker / risk / opportunity 回流
- `Brain Reconcile`
  - 主脑最近一次重排、改派、暂停 lane、提升优先级的决策结果

### 10.3 Detail drawer 必须扩展的字段

- `current_cycle_id`
- `current_focuses`
- `lane_id`
- `assignment_id`
- `report_type`
- `report_consumed`
- `next_cycle_due_at`

### 10.4 可见化硬规则

- Runtime Center 不把 `cycle / assignment / report` 藏进通用 JSON block
- Runtime Center 不把职业 agent 的汇报退化成聊天消息
- Runtime Center 不把主脑的周期规划退化成一段 prompt 文本
