# AGENT_VISIBLE_MODEL.md

本文件用于定义“每个 agent 在系统中应该如何被看见”。

目标不是把 agent 做成一个模糊聊天人格，而是让每个 agent 成为：

> 一个职责清晰、状态清晰、风险清晰、结果清晰、成长清晰的可见执行体。

---

## 0. 与当前版本计划对齐

截至 `2026-03-11`，agent 可见化模型需要同时覆盖：

- 当前已落地的系统岗：
  - `Manager`
  - `Researcher`
- `V1` 将新增的行业业务专员 Agent
- `V2` 将增强的知识、报告、绩效、委派、冲突、成长视图
- `V3` 将增强的治理、恢复、能力市场关联视图
- `V4` 将增强的预测贡献、建议来源、执行结果与复盘视图

明确约束：

- 不能只让系统岗可见，业务岗不可见
- 不能只让后端对象存在，前端没有统一入口
- 不能把 agent 可见化退化成“只有聊天记录”

### 0.1 `2026-04-06` Buddy 例外口径

- Buddy 不属于普通职业执行位。
- Buddy 是主脑唯一对外人格壳，是人类看到、命名、建立陪伴关系的那个外显对象。
- 因此 Buddy 的可见化主场不在 `AgentWorkbench`，而在 `Chat`。
- `Runtime Center` 只显示 Buddy 的紧凑摘要，不把 Buddy 当成一个普通 seat 卡来渲染。
- `Industry` 只承接 Buddy 当前执行载体与执行位编排，不负责再次创建 Buddy 身份。

---

## 1. 核心原则

每个 agent 必须天然可见，至少能让任何人快速回答：

- 它是谁
- 它负责什么
- 它现在在干什么
- 它在哪个环境工作
- 它有没有风险
- 它产出了什么结果
- 它最近有没有成长或变化

Buddy 的同类问题需要换一种问法：

- 它正在陪你走向哪个最后目标
- 它此刻希望你只做哪一个动作
- 它和你的关系、默契、成长处于什么阶段
- 它背后正在调动哪些执行位替你推进系统可自动完成的部分

---

## 2. 每个 agent 必须具备的 7 个可见入口

### 2.1 职责卡

展示该 agent 的角色定义与当前工作身份。

### 2.2 当前工作台

展示该 agent 当前正在推进的任务、环境与风险。

### 2.3 日报入口

展示该 agent 当天的产出、阻塞与计划。

### 2.4 周报入口

展示该 agent 一周的成果、问题与变化趋势。

### 2.5 成长轨迹入口

展示其 patch、能力变化、职责变化与优化历史。

### 2.6 当前环境入口

展示它当前挂载的浏览器、桌面、渠道、工作目录等环境状态。

### 2.7 当前证据入口

展示它最近的关键动作与证据。

### 2.8 Buddy 专属入口（不套用普通执行位卡）

Buddy 需要单独的可见入口合同，至少包括：

- 伙伴形象与当前形态
- 伙伴名称
- 最后目标
- 当前任务
- 单一步动作
- 关系状态
- 成长/进化阶段
- 聊天主入口

约束：

- 这些入口不替代职业执行位的 7 个正式入口
- 职业执行位仍应继续通过职责卡、工作台、日报、周报、成长轨迹、环境、证据被看见
- Buddy 负责“对外陪伴与主脑解释”，执行位负责“对内推进与结果产出”

---

## 3. 职责卡字段规范

每个 agent 的职责卡至少包含：

- `agent_id`
- `name`
- `role_name`
- `role_summary`
- `current_owner`
- `current_goal_id`
- `current_goal`
- `current_primary_task`
- `status`
- `risk_level`
- `environment_summary`
- `today_output_summary`
- `latest_evidence_summary`
- `report_entry`
- `growth_entry`

### 状态字段建议

- `idle`
- `running`
- `waiting`
- `blocked`
- `needs-confirm`
- `degraded`

### 3.1 岗位生命周期字段

职责卡还应显式区分“这个执行位是什么类型”和“它平时怎么被唤醒”：

- `employment_mode`
- `activation_mode`

字段语义必须固定为：

- `employment_mode=career | temporary`
- `activation_mode=persistent | on-demand`

约束：

- `employment_mode` 决定 seat 生命周期，回答“它是不是长期职业位”
- `activation_mode` 只决定唤醒方式，回答“它是常驻还是按需唤醒”
- 两者不能混用，不能再把“常驻/临时”写成一套混合语义

前端展示要求：

- 职责卡、Agent Workbench、行业团队详情都必须同时展示这两个标签
- `temporary` 必须有清晰的短期提示，避免被误解为长期编制
- 当 `temporary` 已完成当前 live work、进入退场条件时，界面应允许 operator 一眼看出它将被自动退场

---

## 4. 日报字段规范

每个 agent 的日报至少包含：

- 日期
- 今日目标
- 今日完成事项
- 今日主要证据
- 今日产出物
- 今日风险 / 阻塞
- 明日计划

### 日报生成原则

- 由证据与任务状态自动汇总生成
- 允许人工补充，但不能完全依赖人工手写

---

## 5. 周报字段规范

每个 agent 的周报至少包含：

- 周目标
- 推进概况
- 重要成果
- 风险与异常
- 能力表现变化
- 下周重点

### 周报生成原则

- 应基于证据、任务与 patch 历史自动汇总

---

## 6. 成长轨迹字段规范

成长轨迹不是抽象人格描述，而是明确展示：

- 职责如何变化
- 能力如何变化
- 风险边界如何变化
- 哪些 patch 被应用
- 哪些 proposal 被否决
- 结果质量如何变化

### 成长轨迹建议字段

- 时间
- 变化类型
- 来源 proposal / patch
- 来源证据
- 风险等级
- 应用结果

---

## 7. 当前环境可见化规范

每个 agent 应能看到自己当前挂载的环境摘要：

- 浏览器环境
- 桌面环境
- 渠道会话
- 工作目录
- 文件视图
- 观察缓存

每项环境应至少显示：

- 类型
- 当前状态
- 最近更新时间
- 是否可复用
- 是否异常

### 7.1 Shared Surface Host 补充字段

若当前环境属于 live `browser / desktop / document` surface，则环境摘要至少还应先显示：

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

展示约束：

- shared host 字段优先于 browser/app 细项
- `handoff_state` 与 `resume_kind` 必须跨 browser/desktop 复用同一套语义
- 不允许把 live execution surface 摘要退化成单一“环境正常”
- `lease_class / access_mode` 必须把当前能否写、是否排队、是否只读直接说清楚

### 7.1.1 Seat Runtime / Host Companion 补充字段

若当前 agent 持有长期 Windows 工位，则环境摘要至少还应显式显示：

- `seat_id`
- `seat_status`
- `host_id`
- `user_session_ref`
- `desktop_session_ref`
- `host_companion_status`
- `workspace_scope`
- `active_surface_mix`
- `event_stream_status`

展示约束：

- `seat` 应回答“这个 agent 当前占着哪具正式工位”
- `host_companion_status` 应回答“Windows 宿主连续性是否还活着”
- 当 seat 存在时，环境摘要不应继续只围绕单一 browser/app surface 组织

### 7.1.2 Workspace / Host Event 补充字段

若当前 agent 正在跨 surface 工作，则环境摘要至少还应显式显示：

- `workspace_id`
- `browser_context_summary`
- `app_set_summary`
- `file_doc_summary`
- `clipboard_bucket_ref`
- `download_bucket_ref`
- `lock_summary`
- `pending_handoff_summary`
- `latest_host_event_summary`

展示约束：

- 工作区摘要应帮助 operator 一眼看出当前任务同时拿着哪些浏览器、应用、文件和宿主上下文
- `Workspace Graph` 必须保持 projection 语义，不得暗中升级成第二套环境真相
- `latest_host_event_summary` 不应退化成后台日志；它应直接解释当前停顿、恢复或 handoff 原因

### 7.2 Browser 环境补充字段

若当前环境包含 `browser`，则环境摘要至少还应显式显示：

- `browser_mode`
- `login_state`
- `tab_scope`
- `active_site`
- `site_contract_status`
- `handoff_state`
- `resume_kind`
- `last_verified_anchor`
- `capability_summary`
- `current_gap_or_blocker`

含义要求：

- `browser_mode` 回答“这具 body 是隔离 profile、真实浏览器续接，还是远程浏览器”
- `site_contract_status` 回答“当前站点是否已经具备正式 writer contract”
- `handoff_state` 回答“当前是否处于人工登录 / CAPTCHA / MFA / rescue takeover”
- `resume_kind` 回答“这具 browser body 当前连续性来自哪里”
- `current_gap_or_blocker` 回答“它为什么现在不能继续做”

展示约束：

- 不允许只显示“浏览器环境：正常”这类失真摘要
- `attach-existing-session` 必须显式可见，避免被误判成可随时重建的隔离浏览器
- 当 handoff 正在进行时，应优先提示 handoff 状态，而不是继续把 agent 展示成普通 running
- `capability_summary` 必须允许 operator 一眼看出当前是否支持 `multi_tab / uploads / downloads / pdf_export / storage_access / locale_timezone_override`

### 7.3 Windows Desktop 环境补充字段

若当前环境包含 `desktop`，则环境摘要至少还应显式显示：

- `app_identity`
- `window_scope`
- `active_window_ref`
- `active_process_ref`
- `app_contract_status`
- `control_channel`
- `writer_lock_scope`
- `window_anchor_summary`

含义要求：

- `app_identity` 回答“现在到底在操作哪个 Windows 应用/系统”
- `app_contract_status` 回答“这个应用当前是否具备正式 writer contract”
- `control_channel` 回答“当前主要靠 accessibility/window/process，还是已经退回视觉兜底”
- `writer_lock_scope` 回答“现在写锁锁的是哪个窗口/文档/账号范围”
- `window_anchor_summary` 回答“最近一次 verify 绑定在哪个窗口/控件/区域锚点上”

展示约束：

- 不允许只显示“桌面环境：正常”或“应用已打开”这类失真摘要
- 对已知 Windows 应用，`app_contract_status` 必须显式可见
- 当桌面 body 正在处理登录/UAC/模态框/焦点争用 handoff 时，应优先展示 handoff/blocker，而不是普通 running
- `control_channel=vision-fallback` 时应醒目标记，因为这表示控制和验证可信度低于语义/控件树路径

---

## 8. 当前证据可见化规范

每个 agent 最近证据至少展示：

- 最近动作
- 最近结果
- 最近 artifact
- 最近高风险动作
- 最近失败 / 回滚记录

目的：

- 让用户快速知道这个 agent 最近到底干了什么

---

## 9. 设计上的禁止事项

### 9.1 不要把 agent 只做成聊天头像

agent 不应只是：

- 一个名字
- 一个头像
- 一段聊天记录

### 9.2 不要把 agent 页面主视图做成纯对话页

agent 的主视图应是：

- 职责
- 任务
- 环境
- 风险
- 证据
- 成长

聊天只作为辅助视图。

### 9.3 不要让成长不可追溯

如果一个 agent 的能力、职责或行为发生变化，但无法知道为什么变化，那这不是成长，而是不可控漂移。

---

## 10. 最小可落地版本

如果只做最小版本，每个 agent 至少要先有：

- 职责卡
- 当前主任务
- 当前风险
- 今日产出摘要
- 最近证据摘要
- 日报入口
- 成长轨迹入口

做到这一步，agent 的“结果可见化”就已经开始成形。

---

## 11. 一句话总结

每个 agent 最终不应像一个模糊人格，而应像一个：

> 职责清晰、状态清晰、环境清晰、风险清晰、结果清晰、成长清晰的可见执行体。

---

## 10. Post-`V6`：主脑 vs 职业 agent 可见边界（planned）

下一正式阶段开始，前端必须显式区分“主脑”与“职业执行位”，不能再默认把所有 agent 视为平级小主脑。

### 10.1 主脑卡片必须新增字段

- `mission`
- `north_star`
- `current_cycle`
- `current_focuses`
- `active_lane_ids`
- `pending_reports`
- `pending_brain_decisions`

### 10.2 职业 agent 卡片必须新增字段

- `assignment_id`
- `assignment_summary`
- `current_routine`
- `latest_report_summary`
- `escalation_state`
- `requires_brain_decision`

### 10.3 职业 agent 的“日报/周报”需要升级为正式汇报对象

下一阶段不再只把日报/周报看成报告文本入口，而要显式支持：

- `task_completed`
- `task_failed`
- `blocked`
- `risk_alert`
- `opportunity_found`
- `strategy_suggestion`

也就是说，职业 agent 的可见化不只展示“他说了什么”，而是展示：

- 他完成了什么
- 有什么证据
- 卡在哪里
- 提了什么建议
- 主脑是否已消费这条回流
