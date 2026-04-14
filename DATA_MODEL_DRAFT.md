# DATA_MODEL_DRAFT.md

`2026-03-26` supplement:
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md` is an execution-side supplement only
- it must not replace the formal object model in this draft
- `AgentBody` maps to `EnvironmentMount`
- `BodySession` maps to `SessionMount`
- `BodyLease` maps to `SessionMount` lease metadata and resource-slot lease records
- `BodyCheckpoint` maps to `AgentCheckpointRecord + RuntimeFrame`
- external `n8n / Workflow Hub` is retired from the target architecture
- future fixed SOP orchestration must stay inside CoPaw as a minimal internal kernel
- `FixedSopTemplate / FixedSopBinding / FixedSopRun` should remain workflow-layer objects inside unified `state`, not become an external second truth source
- any fixed SOP step that needs browser/desktop/document work must dispatch into `EnvironmentMount / SessionMount / routine` execution instead of owning a separate UI runtime
- `2026-03-27` supplement:
  - `Intent-Native Universal Carrier` is upper architecture framing only; it must not become a second top-level state vocabulary
  - `Symbiotic Host Runtime` maps back to `EnvironmentMount / SessionMount / CapabilityMount / EvidenceRecord`
  - `Seat Runtime`, `Host Companion Session`, `Workspace Graph`, and `Host Event` are execution-side mappings, not new primary truth stores
- `2026-03-29` supplement:
  - `host_twin_summary` is the canonical consumer summary for workflow preview/run/resume, fixed-SOP doctor/run, and Runtime Center read surfaces; it may be cached at top-level detail payloads or nested inside `host_snapshot`, but it remains a derived projection of canonical `host_twin`
  - follow-up backlog records born from `failed report -> synthesis -> replan` must preserve `control_thread_id / session_id / environment_ref / chat_writeback_channel / requested_surfaces`, so governance, human-assist, and resume flows can reconnect to the same execution chain before a new assignment exists
  - `work_context_id + recommended_scheduler_action` now form a shared continuity contract across human-assist, schedule resume, runtime chat media, and recovery/reentry surfaces; they are continuity keys on the same runtime truth chain, not a second runtime state model
- `2026-04-02` supplement:
  - single-loop main-brain chat keeps exactly one formal chat/control thread; `/runtime-center/chat/run` streams reply tokens first and same-thread commit sidecar events second, and must not reintroduce `task-chat:*` or a second chat object
  - `main_brain.phase2_commit` is canonical session snapshot state; conversation read surfaces may project it as `meta.main_brain_commit` for same-thread reload, but that projection is not a new top-level runtime object
  - truth-first main-brain scope snapshots are derived caches keyed by `work_context / industry / agent`; media adopt/retain/writeback must dirty-mark the relevant scope and refresh incrementally instead of rebuilding the entire prompt memory every turn
- `2026-04-08` supplement:
  - Buddy stage progression now uses `capability_points + promotion gates` as the canonical truth on active `BuddyDomainCapabilityRecord`; `capability_score` stays only as compatibility/read-model metadata.
  - `1` valid closure = `2` points. A valid closure requires a settled `Assignment` with a completed linked `AgentReport` and non-empty evidence.
  - Canonical promotion gates are:
    - `bonded`: `capability_points >= 20`
    - `capable`: `capability_points >= 40` and `settled_closure_count >= 1`
    - `seasoned`: `capability_points >= 100` and `distinct_settled_cycle_count >= 3`
    - `signature`: `capability_points >= 200`, `independent_outcome_count >= 10`, `recent_completion_rate >= 0.92`, `recent_execution_error_rate <= 0.03`
  - Canonical stage demotion may drop at most one level per refresh; Buddy stage truth must not oscillate across multiple levels in a single growth pass.
  - Active Buddy growth read models must now project `capability_points / settled_closure_count / independent_outcome_count / recent_completion_rate / recent_execution_error_rate / distinct_settled_cycle_count / demotion_cooldown_until` from the same active domain record.
- `2026-04-11` supplement:
  - Buddy onboarding no longer uses a clarification interview loop as canonical state.
  - Canonical onboarding session fields now include:
    - `service_intent`
    - `collaboration_role`
    - `autonomy_level`
    - `confirm_boundaries`
    - `report_style`
    - `collaboration_notes`
  - Canonical onboarding progression is:
    - `identity submitted`
    - `contract compiled`
    - `direction confirmed`
    - `naming pending / completed`
  - Contract compile output is formal session truth and must preserve:
    - `candidate_directions`
    - `recommended_direction`
    - `selected_direction`
    - `final_goal`
    - `why_it_matters`
    - `backlog_items`
  - `question_count / tightened / next_question / existing_question_count` are retired from the active Buddy onboarding data model and may remain only in explicit migration cleanup logic or migration tests.
- `2026-04-07` supplement:
  - Buddy 的成长阶段正式拆成“关系层”和“领域能力层”两条链路，禁止再把 `CompanionRelationship.companion_experience` 直接投影成 stage
  - active `BuddyDomainCapabilityRecord` 是 Buddy 当前领域能力的唯一正式对象，承载 `domain_key / domain_label / capability_score / evolution_stage / strategy_score / execution_score / evidence_score / stability_score`
  - Chat surface、Runtime Center buddy summary 与前端 stage 展示必须统一读取 active `BuddyDomainCapabilityRecord`
  - `CompanionRelationship` 继续只负责命名、陪伴风格、亲密度、契合度、沟通次数与关系记忆，不再主导 stage
  - 换目标写链允许 `keep-active / restore-archived / start-new` 三种领域能力切换，旧领域档案归档保留，后续切回可恢复
  - `BuddyDomainCapabilityRecord` 现已正式绑定自己的 execution carrier continuity：`industry_instance_id / control_thread_id`；一个 active domain record 只能对应一个 active Buddy carrier
  - 新领域不再继续复用 profile-global `buddy:{profile_id}` carrier；legacy shared carrier 只允许一次性 backfill 到已有 active domain record，之后新 domain 必须生成自己的 domain-owned carrier id
  - Buddy 聊天只负责扩展当前 active domain 的范围与能力，不负责硬切换 carrier；页面确认流只负责主领域切换与 archived-domain 恢复
  - archived `BuddyDomainCapabilityRecord` 与其绑定 carrier 必须一起归档保留；后续切回该 domain 时，应恢复原 carrier / control thread continuity，而不是新建平行 runtime truth

本文件用于定义 `CoPaw` 理想载体升级中的**正式数据模型草案**。

这不是最终数据库实现文件，也不是 ORM 代码，而是面向架构、后端、前端、迁移与测试的统一建模草案。

`2026-03-25` 补充说明：

- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md` 只作为 runtime-first 补充视角
- 该补充视角不能引入第二套一级对象，也不能覆盖本文件中的正式对象模型
- 凡是 `ComputerControlRuntime / ExecutionSession / EnvironmentHandle` 一类叙事性名词，若后续使用，必须先映射回本文件的正式对象

本文件的目标：

- 统一一级对象定义
- 统一对象之间的关系
- 区分“稳定核心字段”与“待实现验证字段”
- 指导 `state / evidence / kernel / frontend` 协同演进

---

## 1. 建模原则

### 1.1 单一真相源原则

- 运行真相必须进入统一 `state` 层
- 声明式配置与运行态必须分离
- 不允许多个 manager 长期各自持有平行核心状态

### 1.2 对象优先原则

先定义一级对象，再定义 API、页面和执行流。

一级对象优先级高于：

- 旧页面结构
- 旧 manager 边界
- 旧 router 路径命名

### 1.3 证据优先原则

所有重要动作、状态跃迁、patch 应用和决策都必须能关联到证据。

### 1.4 patch 优先原则

系统的学习和优化不应是隐式状态漂移，而应是显式 `Patch` 生命周期。

### 1.5 稳定核心 / 可调整边界原则

本草案将字段分成三类：

- **稳定核心字段**：当前就应尽量保持稳定
- **建议字段**：推荐具备，可随实现微调
- **待验证字段**：依赖后续实现和运行反馈再确认

---

## 2. 一级对象总览

未来建议把以下对象视为系统一级对象：

- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`
- `WorkContext`
- `Goal`
- `Agent`
- `Task`
- `HumanAssistTask`
- `TaskRuntime`
- `RuntimeFrame`
- `CapabilityMount`
- `EnvironmentMount`
- `SessionMount`
- `EvidenceRecord`
- `DecisionRequest`
- `Patch`

辅助对象包括：

- `Artifact`
- `ReplayPointer`
- `Proposal`
- `GrowthEvent`
- `CapabilityAcquisitionProposal`
- `InstallBindingPlan`
- `OnboardingRun`
- `IndustryProfile`
- `RoleBlueprint`
- `TeamBlueprint`
- `IndustryGoalSeed`
- `BusinessPlan`

---

## 3. 运行真相 vs 声明式配置

### 3.1 属于运行真相的对象

以下对象应进入统一 `state` 或 `evidence` 层：

- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`
- `WorkContext`
- `Goal`
- `Agent`
- `Task`
- `HumanAssistTask`
- `TaskRuntime`
- `RuntimeFrame`
- `EnvironmentMount`
- `SessionMount`
- `EvidenceRecord`
- `DecisionRequest`
- `Patch`

### 3.2 属于声明式配置的对象

以下内容优先保留在 `config` 层：

- channel 声明式配置
- provider 基础配置
- 默认模型槽位
- feature flags
- 系统默认策略参数

### 3.3 边界规则

规则：

- 能描述“现在系统正在发生什么”的，应进 `state`
- 能描述“系统默认怎么启动、怎么接线”的，可留在 `config`

---

## 4. 核心对象关系图（概念层）

推荐的主关系如下：

- `StrategyMemory 1 -> N OperatingLane`
- `StrategyMemory 1 -> N BacklogItem`
- `OperatingLane 1 -> N BacklogItem`
- `OperatingLane 1 -> N Goal`
- `OperatingLane 1 -> N Assignment`
- `BacklogItem 1 -> 0..N OperatingCycle`
- `OperatingCycle 1 -> N Assignment`
- `Assignment 1 -> N Task`
- `Assignment 1 -> 0..N HumanAssistTask`
- `Assignment 1 -> N AgentReport`
- `WorkContext 1 -> N Task`
- `Goal 1 -> N Task`
- `Agent 1 -> N Task`
- `Task 1 -> 0..N HumanAssistTask`
- `HumanAssistTask 1 -> N EvidenceRecord`
- `Task 1 -> 1 TaskRuntime`
- `Task 1 -> N EvidenceRecord`
- `Task 1 -> N DecisionRequest`
- `Task 1 -> N Patch`
- `Task 1 -> N GrowthEvent`
- `TaskRuntime 1 -> 1 current RuntimeFrame`
- `TaskRuntime 1 -> N EnvironmentMount`
- `EnvironmentMount 1 -> N SessionMount`
- `CapabilityMount N <-> N Agent`
- `Proposal 1 -> N Patch`
- `Patch N -> 0..N Goal/Agent/Task/Capability`
- `Patch 1 -> N GrowthEvent`
- `Agent 1 -> N GrowthEvent`
- `CapabilityAcquisitionProposal 1 -> 1 InstallBindingPlan`
- `InstallBindingPlan 1 -> 1 OnboardingRun`
- `EvidenceRecord 0..N -> Artifact`
- `EvidenceRecord 0..N -> ReplayPointer`
- `IndustryProfile 1 -> 1 TeamBlueprint`
- `TeamBlueprint 1 -> N RoleBlueprint`
- `RoleBlueprint 1 -> N IndustryGoalSeed`

说明：

- `RuntimeFrame` 更像某时刻的运行事实快照
- `TaskRuntime` 更像某个任务的持续运行态容器

---

## 5. 对象正式草案

## 5.1 `Goal`

### 定义

`Goal` 表示系统当前周期内的阶段性目标对象，用来承接 `strategy / lane / backlog / cycle` 物化出的短中期 focus，不再承载主脑长期使命。

### 稳定核心字段

- `id`
- `title`
- `summary`
- `status`
- `priority`
- `owner_scope`
- `created_at`
- `updated_at`

### 建议字段

- `goal_type`
- `source`
- `constraints_summary`
- `success_criteria`
- `current_progress_summary`

### 待验证字段

- `industry_profile_ref`
- `world_model_ref`
- `planning_horizon`

### 状态建议

- `draft`
- `active`
- `paused`
- `blocked`
- `completed`
- `archived`

---

## 5.2 `Agent`

### 定义

`Agent` 表示系统中的可见执行体，不是抽象人格，而是职责、能力、环境、产出和成长可追踪的工作角色。

### 稳定核心字段

- `id`
- `name`
- `role_name`
- `role_summary`
- `employment_mode`
- `activation_mode`
- `status`
- `risk_profile`
- `created_at`
- `updated_at`

### 建议字段

- `owner`
- `current_focus_kind`
- `current_focus_id`
- `current_focus`
- `current_primary_task_id`
- `today_output_summary`
- `latest_evidence_summary`

说明：

- `current_focus_*` 是 agent 当前执行焦点的正式前台口径，可指向 goal/backlog/assignment 等 live focus。
- `goal_id / goal_title` 不再允许作为 live runtime metadata 的正式焦点字段；如历史数据仍存在，只能停留在兼容读取边界，不得重新回写。

### 待验证字段

- `profile_patch_version`
- `growth_score`

### 状态建议

- `idle`
- `running`
- `waiting`
- `blocked`
- `needs-confirm`
- `degraded`

### 5.2.1 岗位生命周期补充

`Agent` 当前必须显式区分两套正交语义：

- `employment_mode=career | temporary`
- `activation_mode=persistent | on-demand`

固定含义：

- `employment_mode` 决定 seat 生命周期，回答“这是长期职业位还是短期临时位”
- `activation_mode` 只决定唤醒方式，回答“它是常驻还是按需唤起”

正式规则：

- `career` 表示可长期复用、可持续承担同类任务的职业位
- `temporary` 表示围绕当前 live work 存在的短期 seat，工作清空后应退出团队编制
- `temporary` 在没有显式 `goal` 时，不应自动创建默认长期目标
- 对同一 temporary role 的重复补位，系统应优先复用现有 seat
- 当已有 `temporary` seat 被确认需要长期存在时，应走“晋升为 `career`”而不是新建第二个同类 seat
- `temporary` seat 在 backlog / assignment / pending report / live goal 都清空后，应允许自动退场
- 预测侧生成的 team-gap `role_recommendation` 默认应落为 `career` seat，除非 operator 或上层策略明确要求临时位

---

## 5.3 `Task`

### 定义

`Task` 表示系统内可调度、可执行、可观察、可报告的工作单元，是 `Goal` 的执行分解结果。

### 稳定核心字段

- `id`
- `goal_id`
- `title`
- `summary`
- `task_type`
- `status`
- `priority`
- `owner_agent_id`
- `created_at`
- `updated_at`

### 建议字段

- `parent_task_id`
- `seed_source`
- `constraints_summary`
- `acceptance_criteria`
- `current_risk_level`

### 待验证字段

- `schedule_ref`
- `business_plan_ref`
- `role_blueprint_ref`

### 状态建议

- `created`
- `queued`
- `running`
- `waiting`
- `blocked`
- `needs-confirm`
- `completed`
- `failed`
- `cancelled`

---

## 5.3a `HumanAssistTask`

### 定义

`HumanAssistTask` 表示系统执行链上一个“必须由宿主补一段”的正式协作任务。它只用于
`blocked-by-proof / human-owned checkpoint`，不是泛提醒，也不是第二聊天线程。
当前正式 `task_type` 至少包括 `checkpoint / ui-assist / evidence-submit / host-handoff-return`。

### 稳定核心字段

- `id`
- `industry_instance_id`
- `assignment_id`
- `chat_thread_id`
- `title`
- `summary`
- `task_type`
- `required_action`
- `status`
- `submission_mode`
- `acceptance_mode`
- `acceptance_spec`
- `resume_checkpoint_ref`
- `issued_at`
- `updated_at`

### 建议字段

- `reason_code`
- `reason_summary`
- `block_evidence_refs`
- `submission_evidence_refs`
- `verification_evidence_refs`
- `reward_preview`
- `reward_result`
- `submitted_at`
- `verified_at`
- `closed_at`
- `expires_at`

### 待验证字段

- `issuer_agent_id`
- `owner_scope`
- `host_hint`
- `verification_window_seconds`

### 状态建议

- `created`
- `issued`
- `in_progress`
- `submitted`
- `verifying`
- `accepted`
- `resume_queued`
- `closed`
- `rejected`
- `expired`
- `cancelled`
- `handoff_blocked`

### 验收补充

- 没有 `acceptance_spec` 不允许发布
- 用户说“我完成了”只表示进入验证，不表示直接通过
- 验收优先读取 `EvidenceRecord / EnvironmentMount / SessionMount / Runtime projection`
- 奖励只在通过验收后正式写回

---

## 5.4 `TaskRuntime`

### 定义

`TaskRuntime` 表示某个任务在运行中的持续状态容器，负责承载任务当前阶段、风险、环境挂载和最近结果摘要。

### 稳定核心字段

- `task_id`
- `runtime_status`
- `current_phase`
- `risk_level`
- `updated_at`

### 建议字段

- `active_environment_id`
- `last_result_summary`
- `last_error_summary`
- `last_owner_agent_id`
- `last_evidence_id`

### 待验证字段

- `checkpoint_ref`
- `resource_budget`
- `retry_policy_ref`

### 状态建议

- `cold`
- `hydrating`
- `active`
- `waiting-input`
- `waiting-env`
- `waiting-confirm`
- `blocked`
- `terminated`

---

## 5.5 `RuntimeFrame`

### 定义

`RuntimeFrame` 表示某一时刻“给内核 / 给模型 / 给前端看的统一事实帧”。

它不是完整历史，而是对当前运行状态的结构化聚合视图。

### 稳定核心字段

- `id`
- `task_id`
- `goal_summary`
- `owner_agent_id`
- `current_phase`
- `current_risk_level`
- `environment_summary`
- `evidence_summary`
- `created_at`

### 建议字段

- `constraints_summary`
- `capabilities_summary`
- `pending_decisions_summary`
- `budget_summary`

### 待验证字段

- `frame_kind`（snapshot / derived / replay）
- `source_evidence_ids`
- `render_cache_hash`

### 实现备注

`RuntimeFrame` 在实现上可能有三种方案：

- 独立快照表
- 查询视图
- 事件聚合产物

当前阶段不强行定死，但语义必须稳定。

---

## 5.6 `CapabilityMount`

### 定义

`CapabilityMount` 是统一能力图谱中的标准能力对象，用来替代 `tool / MCP / skill` 的主语义分裂。

### 稳定核心字段

- `id`
- `name`
- `summary`
- `kind`
- `risk_level`
- `environment_requirements`
- `role_access_policy`
- `evidence_contract`

### 建议字段

- `executor_ref`
- `provider_ref`
- `timeout_policy`
- `replay_support`

### 待验证字段

- `quota_policy`
- `cost_profile`

### kind 建议

- `local-tool`
- `remote-mcp`
- `skill-bundle`
- `provider-admin`
- `system-op`

### 当前稳定实现补充

- `CapabilityService.execute_task()` 已是统一 execute 入口，能力执行不应绕过 admit / risk / evidence 主链
- `system:dispatch_query` 当前通过 `KernelTurnExecutor` 承担 request/stream wrapper，实际流执行由 `KernelQueryExecutionService` 负责
- 学习层对能力/角色/计划的持久化改动会通过 override records 显式物化，而不是隐式漂移

---

## 5.7 `EnvironmentMount`

### 定义

`EnvironmentMount` 表示某个任务或 agent 持有的持续环境挂载，是长期执行“身体”的核心对象。

### 稳定核心字段

- `id`
- `mount_type`
- `owner_kind`
- `owner_ref`
- `status`
- `summary`
- `lease_status`
- `created_at`
- `updated_at`

### 建议字段

- `session_ref`
- `lease_owner`
- `lease_token`
- `lease_acquired_at`
- `lease_expires_at`
- `live_handle_ref`
- `is_reusable`
- `last_observation_summary`

### 待验证字段

- `health_score`
- `resource_usage`
- `recovery_policy_ref`

### mount_type 建议

- `seat`
- `browser`
- `desktop`
- `channel-session`
- `workspace`
- `file-view`
- `observation-cache`

### `SessionMount`（持续会话挂载）

`SessionMount` 是 `EnvironmentMount` 之下的持久会话对象，用来承载 channel/browser/workspace 等长期交互上下文中的会话实例。

稳定核心字段建议：

- `id`
- `environment_id`
- `channel`
- `session_id`
- `status`
- `created_at`
- `last_active_at`

建议字段：

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
- `current_gap_or_blocker`
- `user_id`
- `metadata`
- `lease_status`
- `lease_owner`
- `lease_token`
- `lease_acquired_at`
- `lease_expires_at`
- `live_handle_ref`

### 当前稳定实现补充

- `EnvironmentMount / SessionMount` 的 detail read model 已显式暴露 `recovery.status / recoverable / host_id / process_id / note`
- replay 相关 detail 已显式暴露 `replay_support.replay_count / executor_types / fallback_mode`
- 当前 orphan lease recovery 会优先尝试按 channel restorer 在同 host 复绑 live handle；无法直接复绑时再回到既有 kernel replay 路径

### Symbiotic Host Runtime / Seat Runtime 补充

`Intent-Native Universal Carrier` 不是新一级对象。

execution-side 正式框架应理解为 `Symbiotic Host Runtime`，但它必须继续映射回现有正式对象：

- `Seat Runtime` -> `EnvironmentMount` subtype
- `Host Companion Session` -> `SessionMount` subtype
- `Workspace Graph` -> `TaskRuntime + EnvironmentMount + SessionMount + Artifact/Evidence` 的派生投影
- `Host Event` -> `EvidenceRecord + ObservationCache + environment/runtime detail`
- `Cooperative Adapter` -> `CapabilityMount` family
- `Execution-Grade Host Twin` -> derived runtime projection（当前基线），不是第二真相源
- `Full Host Digital Twin` -> 在同一 derived projection 口径上的 phase-next 成熟态扩面，不引入第二套 host truth store

对 `Seat Runtime` 来说，推荐补充字段：

- `seat_kind`
- `host_id`
- `user_session_ref`
- `desktop_session_ref`
- `workspace_scope`
- `host_companion_session_ref`
- `active_surface_mix`
- `companion_status`

约束：

- `Seat Runtime` 的目标是让 execution agent 持有一具长期 Windows 工位，而不是让主脑直接控整机
- `seat` 不应替代 browser/desktop/document 等现有 subtype；它更像这些 live surface 的上层 execution carrier
- 同一 `Seat Runtime` 下的 browser/app/file/doc 工作区，仍然要通过既有 lease/evidence/recovery 主链管理

对 `Host Companion Session` 来说，推荐补充字段：

- `companion_role`
- `user_session_ref`
- `desktop_session_ref`
- `foreground_desktop_ref`
- `active_window_graph_ref`
- `clipboard_bucket_ref`
- `download_bucket_ref`
- `notification_stream_status`
- `network_power_state`
- `event_stream_status`

约束：

- 它用于承载 Windows user/desktop/session 连续性，不是新的宿主数据库
- 它应优先提供 host/session/workspace 事实，减少每轮重新“猜电脑”的成本
- 它可以强化 browser/desktop/document surface 的可恢复性，但不能绕过统一 evidence/governance

对 `Workspace Graph` 来说，推荐理解为派生投影，而不是第二套 object tree。

推荐最小投影内容：

- `workspace_id`
- `seat_ref`
- `browser_context_refs`
- `app_window_refs`
- `file_doc_refs`
- `clipboard_refs`
- `download_bucket_refs`
- `lock_refs`
- `active_lock_summary`
- `pending_handoff_summary`
- `handoff_checkpoint`
- `download_status`
- `surface_contracts`
- `locks[]`
- `surfaces.browser / desktop / file_docs / clipboard / downloads / host_blocker`
- `owner_agent_id / account_scope_ref / workspace_scope / handoff_owner_ref`
- `ownership / ownership_summary`
- `collision_facts / collision_summary`
- `latest_host_event_summary`

约束：

- `Workspace Graph` 优先回答“这个任务当前实际拿着哪些浏览器、应用、文件和宿主上下文”
- 它必须复用既有 `TaskRuntime / EnvironmentMount / SessionMount / Artifact / Evidence`
- `locks / surfaces / ownership / collision` 都只能是 projection 字段，不是新的持久对象库
- 它应服务于跨 surface 连续执行，而不是替代正式任务对象

对 `Cooperative Adapter` 来说，正式语义仍然必须留在 `CapabilityMount`。

典型家族：

- browser extension / browser companion
- office add-in / document object-model bridge
- app-specific plugin / companion bridge
- filesystem / download / notification watcher

约束：

- cooperative path 是优先级，不是第四套 capability 语言
- 没有 native/cooperative path 时，才退回 browser/desktop/document operator

### Browser Session 补充（`mount_type=browser`）

对浏览器 body 来说，正式对象仍然是 `SessionMount`，但 browser subtype
不能继续塌缩成一团不透明 metadata。

稳定核心字段建议：

- `browser_mode`（`managed-isolated | attach-existing-session | remote-provider`）
- `tab_scope`（`single-tab | tab-group | browser-wide`）
- `login_state`（`anonymous | authenticated | unknown`）

建议字段：

- `profile_ref`
- `attach_transport_ref`
- `provider_kind`
- `provider_session_ref`
- `download_policy`
- `storage_scope`
- `site_risk_contract_ref`
- `site_contract_status`
- `account_scope_ref`
- `handoff_state`
- `handoff_reason`
- `handoff_owner_ref`
- `manual_resume_required`
- `active_tab_ref`
- `last_verified_url`
- `last_verified_dom_anchor`
- `capability_summary`

当前稳定实现补充：

- browser session 的 detail/read model 后续必须显式区分
  `navigation / dom_interaction / multi_tab / uploads / downloads / pdf_export / storage_access / locale_timezone_override / resume_kind`
- `attach-existing-session` 已视为正式 browser mode；但不保证天然拥有
  `managed-isolated` 的全部能力，mode 缺口必须以前台 capability/health/recovery
  事实暴露，不允许继续伪装成统一 `browser ready`
- 已知后台/站点的 authenticated writer work 后续必须解析 `site_contract_ref`
  或等价 contract metadata；没有 site contract 时，默认只能降级为 read-only、
  launch blocker 或 governed handoff，不允许继续假装“通用 browser action 足够”
- human login / CAPTCHA / MFA / rescue takeover 后续必须进入正式 handoff 状态，
  不允许只靠 prompt 记忆或聊天文本判断“现在已经可以继续”
- 浏览器恢复继续统一映射到现有
  `resume-environment / rebind-environment / attach-environment / fresh`
  语义，不引入第二套 browser-only recovery vocabulary

### Browser Site Contract / Human Handoff 补充

这两者不应升级成第二套 operator 主链对象，但它们也不能只留在提示词里。

推荐落点：

- `site_contract_ref / site_contract_status / site_risk_contract_ref`
  进入 `SessionMount` 或与之紧邻的 browser runtime metadata
- workflow preview/launch 使用共享 contract 生成 launcher/blocker 判断
- human handoff 通过 `DecisionRequest + AgentCheckpointRecord + EvidenceRecord + SessionMount handoff metadata`
  共同留痕，而不是创建平行 chat/runtime 真相

推荐 handoff 状态：

- `none`
- `requested`
- `active`
- `returned`
- `manual-only-terminal`

### Shared Surface Host Contract 补充

无论是 `browser` 还是 `desktop`，live execution surface 后续都应先投影同一组
host/session 真相字段，再追加 surface-specific 字段。

推荐共享字段：

- `surface_kind`
- `host_mode`
- `lease_class`
- `access_mode`
- `session_scope`
- `account_scope_ref`
- `continuity_source`
- `handoff_state`
- `handoff_reason`
- `handoff_owner_ref`
- `resume_kind`
- `verification_channel`
- `capability_summary`
- `current_gap_or_blocker`

约束：

- browser / desktop 不允许各自重新发明 `resume / handoff / readiness` 语义
- `host_mode` 是 shared host truth，至少应能表达 `local-managed / attach-existing / provider-hosted`
- `lease_class` 应显式回答调度口径，至少覆盖 `exclusive-writer / parallel-read / pooled / queued-side-effect`
- `access_mode` 应显式回答当前交互姿态，至少覆盖 `read-only / writer / side-effect-queued`
- Runtime Center、Agent Workbench、workflow launch blocker 后续都应优先消费共享 host contract，
  再消费 browser/app 细项
- 当前如果只有 `browser_surface_ready / desktop_surface_ready` 这类粗粒度健康位，
  也只能视为 host contract 的外层摘要，不再代表完整能力真相
- live writer surface 若缺少明确 `lease_class / access_mode`，应视为 malformed runtime state，
  不能继续假装“环境正常”

### Desktop / App Contract 补充（`mount_type=desktop`）

当前仓库应按 Windows-first 口径理解 desktop runtime。

推荐共享 desktop 字段：

- `app_identity`
- `window_scope`
- `active_window_ref`
- `active_process_ref`
- `control_channel`
- `app_contract_ref`
- `app_contract_status`
- `writer_lock_scope`
- `window_anchor_summary`

Windows-first 约束：

- `control_channel` 默认优先
  `accessibility-tree / window-tree / process-window / vision-fallback`
- desktop host 侧的本地/续接/远端差异应继续通过共享 `host_mode` 表达，
  Windows app contract 只负责 app/window 细项，不另造第二套 host vocabulary
- 对已知 Windows 应用，没有 `app_contract_ref` 或等价 contract metadata 时，
  mutating writer work 默认应进入 launch blocker、governed handoff 或 read-only downgrade
- 对 mutating desktop work，`lease_class / access_mode` 必须与 `writer_lock_scope`
  一起进入正式 session/lease 真相，不允许只放在宿主实现细节里
- app/window/account 级锁冲突必须进入正式 lease/contention 事实，不允许只留在宿主日志里
- human login / OS prompt / modal rescue 也应复用共享 `handoff_state / resume_kind` 语义，
  不允许另造 desktop-only continuity 模型

### Host Event / Host Twin 补充

`Host Event` 不应成为独立 event truth store。

推荐落点：

- `EvidenceRecord`
- `ObservationCache`
- `EnvironmentMount / SessionMount detail`
- Runtime Center / Agent Workbench 的环境投影

最低事件家族建议：

- `active-window-changed`
- `modal-or-uac-appeared`
- `download-completed`
- `process-exited-or-restarted`
- `lock-unlock`
- `network-or-power-changed`

约束：

- host event 的目标是触发 `re-observe / recover / handoff / retry`
- `Execution-Grade Host Twin` 只能从统一 state/evidence 派生，不允许新建第二套 host twin 存储
- `Full Host Digital Twin` 属于 phase-next 成熟态扩面，但仍必须是同一条 derived projection（从统一 state/evidence 派生），不允许新建第二套存储

---

## 5.8 `EvidenceRecord`

### 5.7.1 `ScheduleRecord`（Phase 1 shadow）

### 定义

`ScheduleRecord` 是 `Phase 1` 为 Runtime Center 引入的调度投影对象。
它的目的不是把最终 `ScheduleService` 一次定死，而是先把旧 `cron` 的关键运行事实显式同步进统一 state，而不是继续让 `jobs.json` 充当运行真相。

### 稳定核心字段

- `id`
- `title`
- `cron`
- `timezone`
- `status`
- `enabled`
- `created_at`
- `updated_at`

### 建议字段

- `task_type`
- `target_channel`
- `target_user_id`
- `target_session_id`
- `last_run_at`
- `next_run_at`
- `last_error`
- `source_ref`
- `spec_payload`

说明：

- `spec_payload` 用于保存完整 cron 规格快照，避免旧 `jobs.json` 同名文件即使仍残留在工作目录中，也被误当成运行中的调度真相

### 状态建议

- `scheduled`
- `paused`
- `running`
- `success`
- `error`
- `deleted`

### 定义

`EvidenceRecord` 表示动作证据，是系统可回放、可审计、可生成日报周报、可反哺 patch 的基础事实单位。

### 稳定核心字段

- `id`
- `task_id`
- `actor_ref`
- `environment_ref`
- `capability_ref`
- `risk_level`
- `action_summary`
- `result_summary`
- `created_at`

### 建议字段

- `artifact_ref`
- `replay_ref`
- `status`
- `input_digest`
- `output_digest`

### 待验证字段

- `raw_payload_ref`
- `token_usage`
- `cost_estimate`

### 状态建议

- `recorded`
- `materialized`
- `linked`
- `failed`

---

## 5.9 `DecisionRequest`

### 定义

`DecisionRequest` 表示需要人工或治理策略确认的事项，是风险治理层的标准对象。

### 稳定核心字段

- `id`
- `task_id`
- `decision_type`
- `risk_level`
- `summary`
- `status`
- `created_at`

### 建议字段

- `source_evidence_id`
- `source_patch_id`
- `requested_by`
- `resolution`
- `resolved_at`

### 待验证字段

- `expires_at`
- `escalation_policy`

### 状态建议

- `open`
- `reviewing`
- `approved`
- `rejected`
- `expired`

---

## 5.10 `Patch`

### 定义

`Patch` 表示系统级学习、优化、配置变更或角色/能力/计划修订的标准载体。

### 稳定核心字段

- `id`
- `kind`
- `title`
- `description`
- `risk_level`
- `status`
- `created_at`

### 建议字段

- `proposal_id`
- `goal_id`
- `task_id`
- `agent_id`
- `diff_summary`
- `evidence_refs`
- `source_evidence_id`
- `applied_by`
- `applied_at`
- `rolled_back_at`

### 待验证字段

- `diff_payload_ref`
- `version_before`
- `version_after`

### patch_type 建议

- `profile_patch`
- `role_patch`
- `capability_patch`
- `plan_patch`
- `config_patch`

### 状态建议

- `proposed`
- `approved`
- `applied`
- `rejected`
- `rolled_back`

### 当前稳定实现补充

- learning 持久化模型当前已经显式支持 `goal_id / task_id / agent_id / source_evidence_id`
- `capability_patch / profile_patch / role_patch / plan_patch` 当前都会进入持久化执行器并产生真实副作用

---

## 5.11 `GrowthEvent`

### 定义

`GrowthEvent` 表示 patch 应用、能力增长、角色变化或策略调整之后留下的可审计成长轨迹。

### 稳定核心字段

- `id`
- `agent_id`
- `change_type`
- `description`
- `result`
- `risk_level`
- `created_at`

### 建议字段

- `goal_id`
- `task_id`
- `source_patch_id`
- `source_evidence_id`

### 待验证字段

- `score_delta`
- `rollup_window`

### 当前稳定实现补充

- 当前 Runtime Center 已提供 `/api/runtime-center/learning/growth/{event_id}` detail 读面
- 当前 `GrowthEvent` 已能由 learning patch apply 流自动写入，并与 patch/evidence/task 建立显式关联
- 当前 approved/applied patch 与 recent growth 已会被编译层回收为 `feedback_summary / feedback_items / feedback_patch_ids / feedback_growth_ids / feedback_evidence_refs / next_plan_hints`，作为下一轮 planning/compile 的稳定输入
- `2026-03-29` 补充：single-item patch 写链也已正式收口到 governed Runtime Center surface；`/api/runtime-center/learning/patches/{id}/approve|reject|apply|rollback` 现全部通过 kernel-governed `system:*patch` mounts 执行，旧 `/api/learning/patches/{id}/*` 单条写入口已退役，`apply/rollback` 的 confirm 结果也会继续把 `DecisionRequest + KernelTask + EvidenceRecord + GrowthEvent/writeback` 串成同一条正式链路

---

## 6. 辅助对象草案

## 6.1 `Artifact`

表示截图、导出文件、报告文件、抓取结果等大对象。

建议字段：

- `id`
- `artifact_type`
- `storage_uri`
- `summary`
- `created_at`

## 6.2 `ReplayPointer`

表示可回放动作链的入口。

建议字段：

- `id`
- `replay_type`
- `storage_uri`
- `summary`

## 6.3 `CapabilityOverride`

表示对单个能力的持久化覆盖策略（由 patch 执行器写入）。
建议字段：
- `capability_id`
- `enabled`
- `forced_risk_level`
- `reason`
- `source_patch_id`
- `created_at`
- `updated_at`

### 当前稳定实现补充

- `compiler_context` 当前不再只是 compile 请求快照，还会持久化 learning feedback 摘要，包括 `feedback_summary / feedback_items / feedback_patch_ids / feedback_growth_ids / feedback_evidence_refs / next_plan_hints`
- 相同反馈字段会镜像进 state-backed task 的 `task_seed` metadata，供 Runtime Center detail 与后续 compile 恢复

---

## 6.4 `AgentProfileOverride`

表示对可见 agent profile 的持久化覆盖策略（由 `profile_patch / role_patch` 执行器写入）。

建议字段：

- `agent_id`
- `name`
- `role_name`
- `role_summary`
- `status`
- `risk_level`
- `current_focus_kind`
- `current_focus_id`
- `current_focus`
- `current_task_id`
- `environment_summary`
- `today_output_summary`
- `latest_evidence_summary`
- `capabilities`
- `capability_budget_max`
- `capability_selection_mode`
- `reason`
- `source_patch_id`
- `created_at`
- `updated_at`

---

## 6.5 `GoalOverride`

表示对 Goal 投影与 plan 视图的持久化覆盖策略（由 `plan_patch` 执行器写入）。

建议字段：

- `goal_id`
- `title`
- `summary`
- `status`
- `priority`
- `owner_scope`
- `plan_steps`
- `compiler_context`
- `reason`
- `source_patch_id`
- `created_at`
- `updated_at`

---

## 6.6 `IndustryPreviewRequest / IndustryProfile / IndustryDraftPlan / TeamBlueprint / RoleBlueprint / IndustryGoalSeed`

表示 Phase B 行业初始化当前已经稳定的产品层编译对象。

建议字段：

- `IndustryPreviewRequest.industry / company_name / sub_industry / product / business_model / region`
- `IndustryPreviewRequest.target_customers / channels / goals / constraints / budget_summary / notes / owner_scope`
- `IndustryProfile.industry / company_name / sub_industry / product / business_model / region`
- `IndustryProfile.target_customers / channels / goals / constraints / budget_summary / notes`
- `IndustryDraftPlan.team / goals / schedules / generation_summary`
- `TeamBlueprint.team_id / label / summary / agents`
- `RoleBlueprint.role_id / agent_id / role_name / role_summary / mission / risk_level`
- `RoleBlueprint.employment_mode / activation_mode / environment_constraints / allowed_capabilities / preferred_capability_families / recommended_capabilities / capability_budget_max / operating_mode / delegation_policy / direct_execution_policy / evidence_expectations`
- `IndustryGoalSeed.kind / owner_agent_id / title / summary / plan_steps / compiler_context`

### 当前稳定实现补充

- `src/copaw/industry/models.py` 已正式定义 `IndustryPreviewRequest`、`IndustryProfile`、`IndustryDraftPlan`、`IndustryRoleBlueprint`、`IndustryTeamBlueprint`、`IndustryGoalSeed`
- `src/copaw/industry/draft_generator.py` 已负责通过 active chat model 生成 `IndustryDraftPlan`
- `src/copaw/industry/compiler.py` 已负责 profile normalization、draft canonicalization、goal seed 编译与 dispatch context 构造
- `2026-03-17` 对象补充：`IndustryRoleBlueprint.preferred_capability_families` 已成为角色级显式能力族锚点；行业推荐默认仍可从 brief/goal/role 文本推断，但一旦 role 明确声明该字段，`SkillHub` 推荐与查询词生成必须优先服从该显式族集合
- `2026-03-20` 对象补充：`IndustryRoleBlueprint`、`AgentProfileOverrideRecord` 与 `AgentRuntimeRecord` 现在统一保留 `employment_mode / activation_mode`；`employment_mode` 是 seat 生命周期契约，`activation_mode` 是唤醒方式契约，两者不再混用
- `2026-03-20` 生命周期补充：`system:update_industry_team` 与 `IndustryService.add_role_to_instance_team()` 现在把“新增、复用、晋升、退场”收口到同一条 canonical team update 写链；duplicate temporary add 应复用 seat，temporary -> career 应视为晋升，completed temporary 应允许自动退场
- 这些对象当前主要属于 compiler/product-layer objects，其中 `IndustryInstanceRecord` 已进入 `state` 一级真相对象
- `IndustryBootstrapRequest` 当前语义已收敛为 `{ profile, draft, activation options }`，bootstrap 不再从 brief 重新生成模板团队
- steady-state 持久化与 `/api/industry/v1/instances*`、`/api/runtime-center/industry*` 读面已统一读取 `IndustryInstanceRecord`；`GoalOverride.compiler_context` 与 `AgentProfileOverride` 只保留最小链接字段和一次性 legacy backfill 清洗职责
- `IndustryInstanceRecord.execution_core_identity_payload` 已成为“唯一物理 Spider Mesh 执行中枢如何绑定到当前行业实例”的正式真相字段；`goal detail`、`runtime detail` 与 `query execution` 只做只读投影，不再各自维护平行行业身份状态
- `2026-04-07` 对象补充：`IndustryInstanceRecord.draft_payload` 已成为 bootstrap canonical draft 的正式持久化字段；industry strategy/runtime consumer 现在优先读取实例内 `draft_payload`，而不是再从 legacy `GoalRecord`/`ScheduleRecord` 反推出 bootstrap 草案
- `2026-04-07` bootstrap hardening：canonical bootstrap goal identity 现已稳定到 `team_id + goal slug`，backlog/cycle/assignment seed 直接消费 goal specs；`GoalRecord` 改为 assignment-native seed 完成后按同一稳定 `goal_id` 物化，避免 bootstrap write path 再把 materialized goal 当唯一 draft truth
- `2026-04-07` bootstrap hard-cut 2A：bootstrap 对外响应面已收口到 `draft / backlog / cycle / assignments / schedule_summaries`；legacy `goals / schedules` 不再属于正式 bootstrap response contract
- `2026-04-07` bootstrap hard-cut 2A：bootstrap 内部现在先以 canonical `goal_specs + schedule_specs` 起 `backlog/cycle/assignment`，再下游持久化 compatibility `GoalRecord / ScheduleRecord`；`ScheduleRecord` 不再是 bootstrap seed 的前置真相
- `V4` 规划补充：内部 canonical `execution-core` 与物理 runtime 继续保留，但其产品语义应逐步收敛为“团队总控核”；后续对象字段应能显式表达其 `operating_mode=control-core` 与 `direct_execution_policy=fallback-only`
- `2026-03-14` 对象补充：`IndustryTeamBlueprint` 现应显式承载 `topology=solo|lead-plus-support|pod|full-team`；`researcher` 从固定常驻岗降为可选支援角色，由 draft/compiler 按 brief 的独立证据环路决定是否生成

---

## 6.7 `IndustryScheduleSeed / IndustryInstanceSummary / IndustryInstanceDetail / IndustryReportSnapshot`

表示 Phase B 当前已经稳定的行业实例运行读模型与默认节奏模型。

建议字段：

- `IndustryScheduleSeed.schedule_id / title / summary / cron / timezone / owner_agent_id`
- `IndustryScheduleSeed.dispatch_channel / dispatch_user_id / dispatch_session_id / dispatch_mode / request_payload / metadata`
- `IndustryExecutionCoreIdentity.binding_id / agent_id / role_id / industry_instance_id / identity_label / industry_label / industry_summary / role_name / role_summary / mission / thinking_axes / environment_constraints / allowed_capabilities / operating_mode / delegation_policy / direct_execution_policy / evidence_expectations`
- `IndustryInstanceSummary.instance_id / bootstrap_kind / label / summary / owner_scope / profile / team / execution_core_identity / status / updated_at / stats / routes`
- `IndustryInstanceDetail.goals / agents / schedules / tasks / decisions / evidence / patches / growth / proposals / acquisition_proposals / install_binding_plans / onboarding_runs / staffing / reports`
- `IndustryReportSnapshot.window / since / until / evidence_count / proposal_count / patch_count / applied_patch_count / growth_count / decision_count / recent_evidence / highlights`

### 当前稳定实现补充

- `src/copaw/industry/models.py` 已正式定义 `IndustryScheduleSeed`、`IndustryExecutionCoreIdentity`、`IndustryInstanceSummary`、`IndustryInstanceDetail`、`IndustryReportSnapshot`
- `IndustryInstanceDetail.execution_core_identity` 与 `GoalDetail.industry.execution_core_identity` 已成为稳定读面，用来显式表达“同一个 Spider Mesh 执行中枢在当前行业实例下的行业身份壳”
- `2026-03-24` 对象补充：`IndustryInstanceDetail.staffing` 已成为 seat-gap/staffing 的正式读面，统一带出 `active_gap / pending_proposals / temporary_seats / researcher`，供 `/industry`、`Runtime Center`、主脑 prompt 与等待启动提示复用；补位状态不再只藏在 backlog metadata 或 decision repository 里
- `/api/industry/v1/instances*` 与 `/api/runtime-center/industry*` 已把这些读模型作为正式 operator/read surface 暴露
- 默认 schedule 仍通过既有 `ScheduleRecord` 主链持久化，而不是行业模块自带平行调度器
- `2026-03-29` 补充：schedule 的正式 operator 写链现在也已收口到 kernel-governed mutation；`/api/runtime-center/schedules*` 与 `/cron/jobs*` 的 create/update/delete/run/pause/resume 不再直接调用 `CronManager`，而是统一物化为 `system:create_schedule / update_schedule / delete_schedule / run_schedule / pause_schedule / resume_schedule` task，再通过 `DecisionRequest`/kernel confirm 链完成落地
- 日报/周报摘要当前是 evidence-driven read model，不是独立 reporting store
- `2026-03-22` 对象补充：`IndustryInstanceDetail` 已显式带出 `acquisition_proposals / install_binding_plans / onboarding_runs`，用于表达“学习阶段发现缺口 -> proposal 审批 -> 物化安装/绑定计划 -> onboarding 验证”的正式读面，而不是把这条链藏在日志里

### 6.7a `CapabilityAcquisitionProposal / InstallBindingPlan / OnboardingRun`

表示行业 learning stage 把“发现缺能力”正式落为可审计 acquisition 闭环时使用的对象。

建议字段：

- `CapabilityAcquisitionProposal.id / proposal_key / industry_instance_id / owner_scope / target_agent_id / target_role_id / acquisition_kind / title / summary / risk_level / status / install_item / binding_request / decision_request_id / approved_by / approved_at / rejected_by / rejected_at / discovery_signals / evidence_refs / created_at / updated_at`
- `InstallBindingPlan.id / proposal_id / industry_instance_id / target_agent_id / target_role_id / risk_level / status / install_item / binding_request / install_result / binding_id / doctor_status / blocked_reason / metadata / evidence_refs / created_at / applied_at / updated_at`
- `OnboardingRun.id / plan_id / proposal_id / industry_instance_id / target_agent_id / target_role_id / status / summary / checks / evidence_refs / created_at / completed_at / updated_at`

### 当前稳定实现补充

- `src/copaw/learning/models.py` 已正式定义这 3 个对象，并通过 `LearningEngine + SqliteLearningStore` 持久化
- `LearningService.run_industry_acquisition_cycle()` 当前已把 `capability discovery -> acquisition proposal governance -> install/binding plan materialize -> onboarding validate -> growth/experience/evidence 回写` 接成一条正式链路
- acquisition proposal 当前已正式接入 `DecisionRequest` 治理链：低风险默认由主脑自动批准并留审计，高风险/需 review 的提案会先停在 `open`，等批准后再继续 materialize/install/onboarding
- 当前 acquisition plan 不另造执行器，而是复用既有 `IndustryServiceActivation._execute_install_plan()`、`SopAdapterService.create_binding/run_doctor/trigger_binding()` 与现有 evidence/growth 主链
- `IndustryService.delete_instance()` 当前已同步清理这 3 类对象及其 audit/evidence 尾巴，避免行业实例删除后残留学习侧垃圾数据

---

## 6.8 `KnowledgeChunkRecord / MetricRecord / ReportRecord`

表示 `V2-B1 / V2-B2` 当前已经落地的正式知识对象与 evidence-driven 报告/绩效对象。

建议字段：

- `KnowledgeChunkRecord.id / document_id / title / content / summary / source_ref / chunk_index / role_bindings / tags / created_at / updated_at`
- `MetricRecord.key / label / window / scope_type / scope_id / value / unit / display_value / numerator / denominator / formula / source_summary / metadata / created_at`
- `ReportRecord.title / summary / window / scope_type / scope_id / since / until / highlights / metrics`
- `ReportRecord.task_status_counts / runtime_status_counts / goal_status_counts`
- `ReportRecord.focus_items / completed_tasks / key_results / primary_evidence / blockers / next_steps`
- `ReportTaskDigest.task_id / title / summary / status / runtime_status / current_phase / last_result_summary / last_error_summary / updated_at / route`
- `ReportEvidenceDigest.evidence_id / task_id / action_summary / result_summary / risk_level / capability_ref / created_at`
- `ReportRecord.evidence_count / proposal_count / patch_count / applied_patch_count / rollback_patch_count / growth_count / decision_count`
- `ReportRecord.task_count / goal_count / agent_count / evidence_ids / task_ids / goal_ids / agent_ids / routes / created_at`

### 当前稳定实现补充

- `src/copaw/state/models.py` 已正式定义 `KnowledgeChunkRecord`、`MetricRecord`、`ReportRecord`
- `src/copaw/state/knowledge_service.py` 已提供正式 knowledge import / split / retrieve / CRUD 入口，并由 `/api/runtime-center/knowledge*` 暴露
- `src/copaw/state/reporting_service.py` 已基于 `EvidenceLedger + Task/Goal/Runtime + DecisionRequest + Learning` 计算正式 reports/performance 读面，并由 `/api/runtime-center/reports` 与 `/api/runtime-center/performance` 暴露
- 这些对象当前是统一 `state/evidence` 主链上的正式读模型，不是新的平行 reporting store

---

## 6.9 `Task.parent_task_id / delegation / replay support`

表示 `V2-B3 / V2-B4` 当前已经稳定的任务层级与环境恢复补充语义。

当前稳定实现补充：

- `Task.parent_task_id` 已成为正式层级字段，`/api/runtime-center/tasks/{id}` 会显式返回 `parent_task / child_tasks / child_task_status_counts / child_results`
- `src/copaw/kernel/delegation_service.py` 已提供正式 child-task 写路径，并在最小治理检查后写入统一 kernel/task store
- `EnvironmentMount / SessionMount` detail 当前已把 `recovery`、`replay_support`、`replay_count`、`executor_types` 视为正式运行元数据
- `/api/runtime-center/recovery/latest`、`/api/runtime-center/replays/{id}/execute`、`/api/runtime-center/sessions/{id}/lease/force-release` 已构成正式 operator recovery/replay surface

---

## 7. 生命周期建议

## 7.1 `Goal` 生命周期

- `draft -> active -> paused/blocked -> completed -> archived`

## 7.2 `Task` 生命周期

- `created -> queued -> running -> waiting/blocked/needs-confirm -> completed/failed/cancelled`

## 7.3 `DecisionRequest` 生命周期

- `open -> reviewing -> approved/rejected/expired`

## 7.4 `Patch` 生命周期

- `proposed -> approved/applied -> rejected -> rolled_back(可选)`

---

## 8. 索引与查询建议（概念层）

以下字段建议作为早期高频索引候选：

- `Task.status`
- `Task.owner_agent_id`
- `Task.goal_id`
- `TaskRuntime.runtime_status`

---

## 17. `2026-03-24` 运行状态口径补充

为避免 `idle / running / waiting` 继续混用，当前运行时读面应以以下语义为准：

- `assigned`：任务或 assignment 已分配给 agent，但还没有 mailbox claim，不应显示为执行中。
- `queued`：mailbox 已正式入队，等待 worker 领取。
- `claimed`：worker 已 claim mailbox，说明执行位已接单，但还没进入稳定执行阶段。
- `executing`：worker 已开始真实执行，允许显示为活跃执行中。
- `blocked`：执行因确认、资源、错误或外部前置条件受阻。

兼容说明：

- `running / waiting` 仍可能作为历史兼容值存在于旧记录或旧 UI 分支里，但新读面与新 UI 口径应优先收敛到
  `assigned / queued / claimed / executing / blocked`。
- Runtime Center、Agent Workbench、Chat runtime badge 等前端展示，不应再把“只有 assignment、没有 mailbox claim”的 seat 渲染成正在执行。
- `EvidenceRecord.task_id`
- `EvidenceRecord.actor_ref`
- `EvidenceRecord.risk_level`
- `DecisionRequest.status`
- `Patch.status`
- `Patch.goal_id`
- `Patch.task_id`
- `Patch.agent_id`
- `GrowthEvent.agent_id`
- `GrowthEvent.task_id`
- `GrowthEvent.source_patch_id`

---

## 9. 与前端的关系

前端运行中心和 agent 工作台应优先围绕这些对象建模：

- 首页：`Goal / Agent / Task / DecisionRequest / EvidenceRecord`
- agent 卡片：`Agent + TaskRuntime + EvidenceRecord`
- 任务页：`Task + TaskRuntime + EvidenceRecord + DecisionRequest + Patch`
- 证据中心：`EvidenceRecord + Artifact + ReplayPointer`
- 成长轨迹：`GrowthEvent + Patch + EvidenceRecord`

这意味着：

- 前端不应继续以旧 manager 或旧技术分类页面作为核心建模基础

---

## 10. Phase 1 最小落地范围

在 `Phase 1` 中，优先落地以下最小子集即可：

- `Task`
- `TaskRuntime`
- `RuntimeFrame`
- `EvidenceRecord`

当前已额外落地的最小扩展：

- `ScheduleRecord` shadow（供 Runtime Center 脱离 cron fallback）
- `DecisionRequest` repository / read model（供治理入口脱离 placeholder）

可后置到后续阶段的对象：

- `Goal` 完整扩展字段
- `CapabilityMount`
- `EnvironmentMount` 详细 subtype
- `Patch` 复杂版本化细节

---

## 10.1 `V4` 补充对象（landed baseline, fields still evolving）

以下对象是 `2026-03-13` 起为了支撑 `V4_WORKFLOW_CAPABILITY_PLAN.md` 而显式登记的 `V4` 产品层/运行层补充对象。

当前 `Capability Market / Workflow Template Center / Predictions` 的最小可用对象链已经落地到代码与前端产品面；后续仍允许字段、子对象与查询视图继续演进，但不应再回退到页面本地状态或 manager 私有结构。

### 10.1.1 `CapabilityInstallTemplate`

定位：

- 产品层安装模板对象
- 服务于 `Skills / Integrations / MCP` 的统一发现、安装、诊断与示例运行

关键要求：

- 这是产品层模板对象，不是新的运行时能力语义
- 安装结果最终仍要收敛为 `CapabilityMount`

建议字段：

- `id / category / title / summary / provider`
- `parameter_schema / secret_requirements`
- `generated_capability_refs`
- `suggested_roles / default_assignment_policy / capability_budget_cost / control_core_fit`
- `diagnostic_actions / example_runs / notes`
- `risk_level / created_at / updated_at`

### 10.1.1a `IndustryCapabilityRecommendationPack`

定位：

- `industry preview` 阶段返回给 operator 的冷启动推荐安装包

关键要求：

- 它是行业 draft 与 capability install templates 的桥接对象
- 它只负责推荐与预览，不直接执行安装

建议字段：

- `industry_profile_snapshot / owner_scope`
- `recommended_template_ids / recommended_templates`
- `role_bindings / workflow_bindings / control_core_summary`
- `rationale / risk_summary / budget_summary`
- `editable / created_at / updated_at`
- `sections[]`：按 `system-baseline / execution-core / shared / role` 分组的正式 operator 读面；前端应优先消费该结构而不是把 `items[]` 再自行拍平成本地列表
- `items[]` 中的单项 recommendation 当前还应显式带出 `recommendation_group / assignment_scope / shared_reuse`，用于表达“这是系统基线、执行中枢专属、可复用共享 skill，还是岗位专属 skill”
- `items[]` 中的单项 recommendation 当前还应显式带出 `discovery_queries / match_signals / governance_path`，用于表达“是用哪些 discovery query 找到它、为什么和当前角色/目标匹配、后续必须走哪条治理写链”，不再让这些关键信息只存在于行业/预测私有字符串或前端猜测里
- 远程 skill recommendation 当前必须经过两层治理：
  - `preferred_capability_families` / role-goal context 锚点
  - 跨行业漂移过滤 + 能力族预算约束；典型目标是避免把金融交易类 skill 漂到电商/客服团队，或在已有 `browser-local` runtime 后继续堆叠泛 browser skill

### 10.1.2 `WorkflowTemplateRecord`

定位：

- operator 可见的可复用自动化模板对象

关键要求：

- 模板启动必须 materialize 到正式 `Goal / Schedule / Task / Decision / Evidence`
- 不允许引入平行 workflow executor

建议字段：

- `id / name / summary / category`
- `owner_scope / parameter_schema / default_inputs`
- `required_capabilities / owner_role_bindings / step_capability_requirements / capability_budget_impact / control_owner_role_id / fallback_execution_policy / materialization_strategy`
- `goal_blueprint / schedule_blueprint / delegation_blueprint`
- `risk_baseline / evidence_expectations`
- `created_at / updated_at`

### 10.1.3 `WorkflowPresetRecord`

定位：

- `WorkflowTemplateRecord` 的可复用参数预设对象

建议字段：

- `id / template_id / name / summary`
- `owner_scope / industry_scope`
- `parameter_overrides / created_by / created_at`

### 10.1.4 `WorkflowRunRecord`

定位：

- workflow 模板启动后的运行锚点对象

关键要求：

- 它不替代 `Task / TaskRuntime`
- 它只记录一次 workflow materialization 与运行链的聚合锚点

建议字段：

- `id / template_id / preset_id / status`
- `input_payload / owner_agent_id / owner_scope`
- `materialized_goal_ids / materialized_schedule_ids / root_task_ids`
- `decision_ids / evidence_ids`
- `last_error / launched_at / completed_at`

### 10.1.5 `ExecutionRoutineRecord`

定位：

- agent-local、environment-bound 的可复用叶子执行记忆对象

关键要求：

- 它不替代 `WorkflowTemplateRecord / WorkflowRunRecord`
- 它必须复用既有 `CapabilityMount / EnvironmentMount / SessionMount / EvidenceRecord`
- 第一阶段先服务浏览器 routine，不引入平行 workflow DSL

建议字段：

- `id / routine_key / name / summary / status`
- `owner_scope / owner_agent_id / source_capability_id / trigger_kind`
- `environment_kind / session_requirements / isolation_policy / lock_scope`
- `input_schema / preconditions / expected_observations / action_contract`
- `success_signature / drift_signals / replay_policy / fallback_policy`
- `risk_baseline / evidence_expectations`
- `source_evidence_ids / last_verified_at / success_rate / created_at / updated_at`

当前实现状态：

- 已落地到 `src/copaw/state/models.py`，并由 `SqliteExecutionRoutineRepository` 持久化
- 当前 `engine_kind` 已收口为 `browser / desktop`；固定 SOP 已上移到 `SopAdapterService`，不再作为 routine engine kind
- 当前 `source_evidence_ids + action_contract` 已支持从稳定 browser evidence（`open / navigate / click / screenshot`）自动提炼

### 10.1.6 `RoutineRunRecord`

定位：

- 一次 routine capture / replay / fallback 的运行锚点对象

关键要求：

- 它只记录一次 leaf routine 运行，不替代 `TaskRuntime` 或 `WorkflowRunRecord`
- 它必须显式记录 deterministic replay 结果、失败分类与 fallback 去向

建议字段：

- `id / routine_id / source_type / source_ref / status`
- `input_payload / owner_agent_id / owner_scope`
- `environment_id / session_id / lease_ref / checkpoint_ref`
- `deterministic_result / failure_class / fallback_mode / fallback_task_id / decision_request_id`
- `output_summary / evidence_ids / started_at / completed_at`

当前实现状态：

- 已落地到 `src/copaw/state/models.py`，并由 `SqliteRoutineRunRepository` 持久化
- routine run evidence 当前统一写成 synthetic task：`routine-run:{routine_run_id}`
- routine fallback 当前继续复用 canonical `system:dispatch_query`，不旁路 kernel

### 10.1.7 `RoutineDiagnosis`

定位：

- Runtime Center 消费的 routine 诊断读模型

建议字段：

- `routine_id / last_run_id / status / drift_status`
- `selector_health / session_health / lock_health / evidence_health`
- `recent_failures / fallback_summary / resource_conflicts`
- `recommended_actions / last_verified_at`

当前实现状态：

- 当前 diagnosis 由 `RoutineService.get_diagnosis()` 生成
- Runtime Center routines card 只消费后端真相，不在前端本地派生 routine 状态

---

## 11. 当前稳定结论

以下结论当前可以视为稳定：

- `Goal / Agent / Task / TaskRuntime / RuntimeFrame / CapabilityMount / EnvironmentMount / SessionMount / EvidenceRecord / DecisionRequest / Patch` 是一级对象
- `ScheduleRecord` 当前是 Runtime Center 的 Phase 1 投影对象，未来可收敛为 `ScheduleService` 所拥有的正式模型或派生视图
- `config` 不再承载核心运行真相
- `RuntimeFrame` 是统一运行事实帧
- `CapabilityMount` 已不只是只读注册对象，而是必须显式声明执行入口、风险与证据契约的统一能力对象
- `EnvironmentMount / SessionMount` 已稳定承载 lease/live-handle 相关字段，租约生命周期属于正式运行模型的一部分
- `EvidenceRecord` 是系统可见化、审计、报告和学习的底座
- `Patch` 是学习输出的标准载体，当前稳定的真实执行落点包括 `CapabilityOverride / AgentProfileOverride / GoalOverride`
- `Patch / GrowthEvent` 当前已经显式挂上 `goal_id / task_id / agent_id / source_evidence_id` 等学习闭环锚点
- `compiler_context / task_seed` 当前已经稳定承载 learning feedback metadata，不再只是 compile 输入快照
- `IndustryInstanceRecord` 已成为正式 `state` repository object，并作为 `/api/industry/v1/instances*` 与 `/api/runtime-center/industry*` 的 steady-state truth source
- `IndustryInstanceRecord.draft_payload` 当前已进入正式 schema/repository contract，用于持久化 canonical `IndustryDraftPlan`；它与 `execution_core_identity_payload` 一起构成 industry bootstrap 的实例内真相锚点
- `IndustryProfile / IndustryRoleBlueprint / IndustryTeamBlueprint / IndustryGoalSeed` 已有正式模型与编译器；它们现在是稳定的 compiler/product-layer objects，不再承担长期运行真相源
- `employment_mode / activation_mode` 已成为稳定岗位契约字段：前者定义 `career / temporary` seat 生命周期，后者定义 `persistent / on-demand` 唤醒方式；`/industry`、`Runtime Center` 与 `AgentWorkbench` 必须消费同一套字段
- `2026-03-14` 语义补充：`IndustryTeamBlueprint.topology` 已进入正式模型，用于约束“最小合理团队”；`execution-core` 继续固定为团队总控核，而 `researcher` 只作为可选支援角色存在
- `IndustryScheduleSeed / IndustryInstanceSummary / IndustryInstanceDetail / IndustryReportSnapshot` 已成为稳定的产品层节奏/读模型
- `KnowledgeChunkRecord` 已成为正式知识库对象，knowledge import/retrieve 不再只存在于聊天上下文或零散 evidence 中
- `KnowledgeChunkRecord` 当前也承载长期记忆文档语义，`memory:{scope_type}:{scope_id}` 已成为稳定 scope 约定
- `MetricRecord / ReportRecord` 已成为正式 evidence-driven V2 报告/绩效读对象，用于承载 Reports / Performance 产品面
- `Task.parent_task_id` 已成为正式 delegation hierarchy anchor，不再只是临时读面拼接字段
- `EnvironmentMount / SessionMount` 的 detail 读面当前已把 recovery 与 replay_support 视为正式运行元数据的一部分
- `PredictionCaseRecord / PredictionScenarioRecord / PredictionSignalRecord / PredictionRecommendationRecord / PredictionReviewRecord` 已成为正式 `state` objects，并被 `Predictions / Reports / Performance / Runtime Center` 直接消费
- 即使进入 post-`V5` 的 `routine / muscle memory` 深化，顶层 workflow 也必须继续保持 run-centric；未来 `ExecutionRoutineRecord` 只能作为叶子执行记忆，不能替代 `WorkflowRunRecord` 或拉出平行执行内核

以下结论当前保留实现级灵活性：

- `RuntimeFrame` 的物化方式
- `Patch` 的 diff 存储方案
- `EnvironmentMount` 各子类型最终字段全集
- 某些聚合查询是否走物化表还是派生视图

---

## 12. 一句话总结

本草案的核心不是把数据库字段一次定死，而是先把系统真正的一等对象定下来，让后端、前端、迁移和删旧代码都围绕同一组对象推进。

---

## 12.1 2026-03-13 landed V4-A1 objects

The following V4 cold-start objects are now live in code and should be treated as
formal product-contract objects rather than planning-only notes:

- `IndustryCapabilityRecommendation`
  - preview-stage recommendation for one installable capability template
  - carries `template_id / default_client_key / capability_ids / suggested_role_ids / target_agent_ids`
  - explicitly separates "installed in global pool" from "assigned to selected agents"
- `IndustryCapabilityRecommendationPack`
  - returned by `POST /api/industry/v1/preview`
  - groups operator-facing install recommendations and warnings for bootstrap review
- `IndustryBootstrapInstallItem`
  - accepted by `POST /api/industry/v1/bootstrap`
  - records the approved install decision, target agents, and assignment mode
- `IndustryBootstrapInstallResult`
  - returned by `POST /api/industry/v1/bootstrap`
  - records install status plus per-agent assignment outcome
- `IndustryBootstrapResponse`
  - returned by `POST /api/industry/v1/bootstrap`
  - canonical surface is now `profile / team / draft / recommendation_pack / install_results / backlog / assignments / cycle / schedule_summaries / readiness_checks / media_analyses / routes`
  - legacy `goals / schedules` no longer belong to the formal bootstrap response contract

Current V4-A1 boundary:

- install still lands in the unified capability pool through canonical capability executors
- assignment still lands in `AgentProfileOverrideRecord.capabilities`
- install into pool does not imply team-wide exposure

## 12.2 2026-03-13 landed V4-A2 / A3-min objects

The following workflow/install-link objects are now live in code and should be
treated as formal product-contract objects rather than planning-only notes:

- `WorkflowTemplateRecord`
  - persisted template catalog object in unified `state`
  - backs `/api/workflow-templates*` and the `/workflow-templates` product surface
- `WorkflowPresetRecord`
  - persisted template parameter preset object in unified `state`
  - lets workflow launch stay object-backed instead of hiding reusable inputs in page-local state
- `WorkflowRunRecord`
  - persisted workflow materialization anchor in unified `state`
  - records the template launch outcome while reusing existing `Goal / Schedule / Task / Decision / Evidence`
- `WorkflowTemplatePreview`
  - canonical preview/read model for parameterized workflow launch
  - projects step owners, dependency status, assignment-gap, budget impact, launch blockers, and materialized objects
- `WorkflowTemplateDependencyStatus`
  - canonical dependency projection for one workflow-required capability
  - now carries `installed / enabled / available` readiness signals plus install-template refs, so workflow preview can distinguish missing vs disabled dependencies and jump into productized install surfaces
- `WorkflowTemplateInstallTemplateRef`
  - lightweight install-link object attached to workflow dependency previews
  - keeps the install suggestion in product/object space instead of pushing that mapping back into page-local heuristics
- `WorkflowTemplateAgentBudgetStatus`
  - canonical per-agent workflow budget diagnostic object
  - compares baseline/effective/planned capability surfaces against the V4 business-agent budget rule
- `WorkflowTemplateLaunchBlocker`
  - canonical launch-time governance blocker object for workflow preview/launch
  - unifies missing-install, assignment-gap, target-agent-unavailable, and budget-overflow diagnostics

Current V4-A2 / A3-min boundary:

- workflow launch still materializes into canonical `GoalService` and `ScheduleRecord`; no parallel workflow executor exists
- workflow run cancel currently archives goals, pauses schedules, and updates the run anchor; it does not yet hard-cancel in-flight runtime tasks
- workflow preview/launch now enforce per-agent assignment-gap and budget blockers before materialization
- install-link is no longer only a preview/detail product chain; install completion can now auto-assign target agents and auto-return into workflow preview/launch without creating a parallel runtime path

## 12.3 2026-03-13 landed V4-B objects

The following prediction/recommendation objects are now live in code and
should be treated as formal state/product-contract objects rather than planning-only
notes:

- `PredictionCaseRecord`
  - persisted prediction case anchor in unified `state`
  - backs `POST /api/predictions`, `GET /api/predictions*`, and both manual and cycle-created cases
- `PredictionScenarioRecord`
  - persisted multi-scenario prediction object
  - records comparable `best / base / worst` (or equivalent) outcomes instead of reducing prediction output to one summary blob
- `PredictionSignalRecord`
  - persisted structured signal object
  - captures facts coming from reports, metrics, evidence, workflow runs, industry state, and role judgments
- `PredictionRecommendationRecord`
  - persisted governed recommendation object
  - records recommendation type, confidence, risk, target scope, execution/decision refs, and whether execution was auto-triggered
- `PredictionReviewRecord`
  - persisted review/outcome object
  - records hit/miss judgment, adoption state, benefit score, and operator commentary for later reporting and learning
Current V4-B boundary:

- prediction/recommendation execution still reuses canonical kernel/capability/evidence paths; no parallel prediction executor exists
- unsupported recommendation actions remain explicit `manual-only` objects rather than being faked as auto-executable
- standalone optimization-side-chain throttling/budget objects have been removed; cycle prediction now stays on the canonical `/predictions` surface

## 12.4 2026-03-16 memory layer boundary

The memory boundary is now explicitly closed into three layers instead of being
left as prompt convention only.

### Strategic layer

Formal object:

- `StrategyMemoryRecord`

Fields that must belong to the strategic layer:

- `strategy_id / scope_type / scope_id / owner_agent_id / owner_scope / industry_instance_id`
- `title / summary / mission / north_star`
- `priority_order / thinking_axes`
- `delegation_policy / direct_execution_policy`
- `execution_constraints / evidence_requirements`
- `active_goal_ids / active_goal_titles`
- `teammate_contracts`
- `source_ref / status / metadata`

Current code landing:

- persistence: `src/copaw/state/models.py`, `src/copaw/state/store.py`, `src/copaw/state/repositories/*`
- service: `src/copaw/state/strategy_memory_service.py`
- industry write path: `IndustryService` now materializes/refreshes the execution-core strategy record from canonical `IndustryInstanceRecord + IndustryExecutionCoreIdentity + Goal` state
- runtime read path: `KernelQueryExecutionService` now injects strategy memory into execution-core runtime context
- goal compile read path: `GoalService` now injects `strategy_id / strategy_summary / strategy_items` into compiler context, and `SemanticCompiler` now consumes them in prompt construction
- shared consumer read contract: `GoalService / WorkflowTemplateService / PredictionService / KernelQueryExecutionService` must all resolve strategy payload through `state.strategy_memory_service.resolve_strategy_payload()`
- direct `get_active_strategy()` reads are reserved for strategy producer/service boundaries such as `state/strategy_memory_service.py` and `industry/service.py`, not planning/workflow/prediction/execution consumer surfaces
- contract-test guardrail: any new strategic consumer must extend the strategy-memory contract test instead of introducing a private read path
- visible product surface: `IndustryInstanceSummary / Detail` now expose `strategy_memory`

### Fact layer

These fields must remain in the shared fact layer instead of being copied into
private brain state:

- industry truth: `IndustryInstanceRecord`, `IndustryExecutionCoreIdentity`
- operating objects: `GoalRecord / TaskRecord / TaskRuntimeRecord / ScheduleRecord / DecisionRequestRecord`
- evidence chain: `EvidenceRecord / RuntimeFrameRecord / ReportRecord / MetricRecord`
- knowledge and long-term memory: `KnowledgeChunkRecord`
- prediction/optimization objects: `Prediction* / Patch / Growth`

Current code landing:

- `src/copaw/state/`
- `src/copaw/evidence/`
- `src/copaw/industry/`
- `src/copaw/learning/`
- `src/copaw/predictions/`

### Working memory layer

These fields must stay with the local executing agent instead of being promoted
to shared truth by default:

- `AgentRuntimeRecord.current_task_id / current_mailbox_id / current_environment_id`
- `AgentRuntimeRecord.employment_mode / activation_mode`
- `queue_depth / last_started_at / last_heartbeat_at / last_stopped_at`
- `last_error_summary / last_result_summary / last_checkpoint_id`
- `AgentMailboxRecord.payload / result_summary / error_summary / lease_owner / lease_token / attempt_count`
- `AgentCheckpointRecord.phase / cursor / snapshot_payload / resume_payload / summary`
- `AgentThreadBindingRecord.thread_id / alias_of_thread_id / active`
- `AgentLeaseRecord.lease_token / owner / expires_at / heartbeat_at`

Current code landing:

- `src/copaw/kernel/actor_mailbox.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/state/models.py`
- `src/copaw/state/repositories/*`

## 12.5 `V6` operation memory boundary

The next memory-layer deepening must land as operation memory instead of
re-expanding private prompt text.

Formal planned objects:

- `ExecutionRoutineRecord`
- `RoutineRunRecord`
- `RoutineDiagnosis`

Fields that belong to the operation-memory layer:

- routine identity and scope: `routine_key / owner_scope / owner_agent_id / source_capability_id`
- environment contract: `environment_kind / session_requirements / isolation_policy / lock_scope`
- deterministic execution contract: `preconditions / expected_observations / action_contract / success_signature`
- replay and fallback policy: `replay_policy / fallback_policy / failure_class / checkpoint_ref`
- verification telemetry: `last_verified_at / success_rate / drift_signals / recent_failures`

Fields that must not be copied into routine memory by default:

- full prompt transcripts
- full chat history
- full HTML / DOM snapshots as inline record payload
- large screenshots / videos / downloaded files

Boundary rules:

- raw browser artifacts remain in `Evidence / Artifact / Replay`
- routine memory stores compact structural anchors and recent summarized telemetry
- if V6 needs finer-grained browser locks, it should first extend existing environment/session lease semantics before introducing a dedicated resource-lease object
- if fixed SOP is introduced later, it should land as internal `sop_kernel` objects above the routine layer; operation memory is still owned by `ExecutionRoutineRecord / RoutineRunRecord`

Current intended landing:

- `src/copaw/routines/`
- `src/copaw/routines/service.py`
- `src/copaw/app/routers/routines.py`
- `src/copaw/sop_kernel/`
- `src/copaw/app/routers/fixed_sops.py`
- `src/copaw/capabilities/browser_runtime.py`
- `src/copaw/environments/`
- `src/copaw/evidence/`
- `src/copaw/state/`

Current landed boundary:

- browser replay, capture, failure classify, fallback, desktop replay 都已接回现有 `state / evidence / environments / kernel / runtime-center`
- 固定 SOP 调度已经上移到 `SopAdapterService + system:trigger_sop_binding`，不再停留在 routine engine 内部
- finer-grained browser locks 当前优先复用 `EnvironmentService + SessionMountRepository`，以 `resource-slot:*` pseudo session mount 承载

### Automatic child-agent experience write-back

The child-agent outcome write-back path is now live:

- `ActorWorker` writes terminal child outcomes into `memory:agent:{agent_id}`
- `TaskDelegationService` also writes back when delegated child tasks are executed inline
- the write-back service is `src/copaw/state/agent_experience_service.py`
- the sink remains the existing unified long-term memory surface `KnowledgeChunkRecord`, so no parallel memory store was introduced

## 12.6 Post-`V7` memory vNext boundary

The next memory enhancement must land as a derived layer on top of unified
`state / evidence`, not as a second durable memory source.

`2026-03-30` supplement:
- memory vNext is explicitly `truth-first`
- the target is `no-vector formal memory`
- shared formal memory must be derived from canonical `state / evidence / runtime`
- private conversation compaction may remain separate, but it must not become a second runtime memory truth
- QMD/vector references are physically removed residuals and must not be reintroduced into the formal memory contract

`2026-04-14` supplement:
- formal text memory writes must first pass explicit selective-ingestion policy; low-value chat noise is rejected, durable work continuity routes to `work_context`, and shared durable domain knowledge routes to `industry`
- formal recall surfaces must share one fixed related-scope order `work_context -> task -> agent -> industry -> global` plus explicit fetch budgets; activation/read surfaces must not over-read beyond that contract
- repeated durable text anchors may be canonically merged; compaction normalizes formal text memory presentation but does not replace source-backed truth
- `ConversationCompactionService` is private transcript compaction only; the old `agents/memory/memory_manager.py` shell is retired and must not be reintroduced as a second memory truth boundary
- old memory-db additive upgrade is no longer part of the formal contract; current memory/state baseline assumes rebuildable fresh canonical schema instead of historical db migration guarantees

### Canonical truth remains:

- `StrategyMemoryRecord` for strategic memory
- `KnowledgeChunkRecord` for long-term fact memory
- `Goal / Task / Schedule / RoutineRun / AgentReport` for execution truth
- `EvidenceRecord / Artifact / Replay / ReportRecord / MetricRecord` for evidence-backed trace

### New memory capabilities may add:

- rebuildable `derived memory index`
- `Retain / Recall / Reflect` services
- `EntityMemoryView / OpinionMemoryView / MemoryRecallHit` read models
- rebuildable profile/latest/history projections over canonical truth
- `Knowledge Activation Layer` derived from `StrategyMemoryRecord + KnowledgeChunkRecord + MemoryFactIndexRecord + Entity/Opinion/Profile/Episode/Relation views`
- `KnowledgeNeuron / ActivationInput / ActivationResult` as derived activation-layer objects for scope-first neuron activation and evidence/strategy rehydration

### Hard boundary:

- no new canonical Markdown memory source
- no durable dual-write between `state` and a private memory DB
- no direct caller dependency on a concrete vector backend
- no QMD/vector sidecar in the formal memory path
- no silent strategic drift from reflection jobs

### Integration rule:

- `Retain` writes durable facts back into canonical services such as
  `KnowledgeChunkRecord` and controlled `StrategyMemoryRecord` refreshes
- `Recall` is exposed through a unified recall facade, not through backend-specific callers
- `Reflect` produces read models, compiled summaries, or reviewable patch/proposal inputs
- all derived indexes must be fully rebuildable from canonical `state / evidence`

### `2026-04-01` activation-layer supplement

The next memory-layer enhancement has now started landing as a derived activation layer instead of a new memory truth source.

Current landed objects and service surface:

- `KnowledgeNeuron`
- `ActivationInput`
- `ActivationResult`
- `MemoryActivationService`

Current landed consumer surfaces:

- query prompt retrieval
- goal compiler memory context

`2026-04-01` phase 2 supplement:

Current additionally-landed consumer surfaces:

- industry report synthesis
- follow-up backlog / replan materialization
- current-cycle runtime surface payload

Current activation-derived carry-over fields now include:

- `activation.top_constraints`
- `activation.top_next_actions`
- `activation.support_refs`
- `activation.contradiction_count`

`2026-04-01` phase 3 supplement:

Current additionally-landed Runtime Center surfaces:

- `GET /runtime-center/memory/activation`
- `GET /runtime-center/memory/profiles*` with opt-in `include_activation + query`
- `GET /runtime-center/memory/episodes` with opt-in `include_activation + query`
- Runtime Center task list/detail read payloads with compact `activation` summaries

Current Runtime Center conservative activation summary fields now include:

- `activation.activated_count`
- `activation.contradiction_count`
- `activation.top_entities`
- `activation.top_constraints`
- `activation.top_next_actions`
- `activation.support_refs`
- `activation.evidence_refs`
- `activation.strategy_refs`

Hard boundary remains:

- activation-derived fields are still projections over canonical truth
- backlog / assignment metadata may carry activation-derived hints, but those hints do not become a second durable memory truth

Hard boundary:

- activation remains derived from existing `StrategyMemory / KnowledgeChunk / FactIndex / reflection views`
- no graph database or separate durable activation store has been introduced
- dedicated activation visualization beyond current Runtime Center route/read-surface payloads remains a follow-up integration phase

`2026-04-01` phase 4 supplement:

Current additionally-landed derived relation objects/read surfaces:

- `MemoryRelationViewRecord`
- SQLite-backed `memory_relation_views` compiled read model inside the unified state store
- `DerivedMemoryIndexService.list_relation_views(...)`
- `DerivedMemoryIndexService.rebuild_relation_views(...)`
- `GET /runtime-center/memory/relations`

Current hard boundary after phase 4:

- persisted relation views are derived-only and rebuildable from existing `MemoryFactIndexRecord + MemoryEntityViewRecord + MemoryOpinionViewRecord`
- persisted relation views remain SQLite-backed compiled read models, not a second durable memory truth source
- no graph database or graph-native execution write path has been introduced
- generic `rebuild_all` / `POST /runtime-center/memory/rebuild` does not yet auto-rebuild relation views; relation rebuild currently remains an explicit derived-index operation
---

## 12.7 2026-03-19 media analysis ingest boundary

The media ingest chain is now partially landed and should be treated as a
formal object boundary instead of page-local attachment state.

Formal object:

- `MediaAnalysisRecord`

Current canonical fields already live in code:

- identity and scope: `analysis_id / industry_instance_id / thread_id / entry_point / purpose`
- source anchor: `source_kind / source_ref / source_hash / declared_media_type / detected_media_type / analysis_mode`
- operator-visible summary: `title / url / filename / mime_type / size_bytes`
- derived outputs: `structured_summary / timeline_summary / entities / claims / recommended_actions / warnings`
- evidence/writeback anchors: `asset_artifact_ids / derived_artifact_ids / transcript_artifact_id / knowledge_document_ids / evidence_ids / strategy_writeback_status / backlog_writeback_status`
- lifecycle: `status / error_message / metadata / created_at / updated_at`

Current product-contract additions on top of existing industry objects:

- `IndustryPreviewRequest.media_inputs`
- `IndustryPreviewResponse.media_analyses / media_warnings`
- `IndustryBootstrapPayload.media_analysis_ids`
- `IndustryInstanceDetail.media_analyses`

Current frontend boundary:

- `/industry` brief/preview now owns only transient `media_inputs`; analyzed truth stays in `MediaAnalysisRecord`
- `/chat` no longer needs to depend on raw widget attachments for this chain; it sends `media_analysis_ids` as explicit request metadata
- important visible result surfaces are now the analyzed summaries and warnings, not opaque upload state

Current capability boundary:

- `video-lite` is the default shipped video path
- `video-deep` remains capability-gated and unavailable by default
- this means “video deep analysis missing” is currently an intentional capability boundary, not a state/model gap

Persistence/query landing:

- repository: `src/copaw/state/repositories/sqlite_media.py`
- service: `src/copaw/media/service.py`
- routers: `src/copaw/app/routers/media.py`, `src/copaw/app/routers/runtime_center_routes_core.py`

## 13. Post-`V6` 主脑长期自治对象升级方向（hard-cut baseline）

`2026-03-25` 起，主脑长期自治正式进入一次性硬切重构窗口。

这轮不是继续把 `GoalRecord / ScheduleRecord` 扩成更大的主脑规划中心，而是把正式写链收口为：

`StrategyMemoryRecord -> OperatingLaneRecord -> BacklogItemRecord -> OperatingCycleRecord -> AssignmentRecord -> AgentReportRecord -> synthesis / replan`

硬约束：

- `StrategyMemoryRecord` 是长期使命、KPI、行业边界与委派原则的唯一正式锚点。
- `GoalRecord` 只保留“周期内阶段目标”语义，不再承担主脑长期规划真相。
- `ScheduleRecord` 仍可保留为自动化/节奏触发对象，但不再承担主脑计划展开的上游真相。
- `TaskRecord / TaskRuntimeRecord` 继续作为执行单元与执行 runtime 对象。
- 若旧 `GoalRecord` 主依赖被完全切掉，可直接删除而不是继续桥接。
- `POST /runtime-center/tasks/{task_id}/delegate` 这类人类直打执行位的前台入口不再是数据模型的一部分；前台正式写链只允许进入 `MainBrainOrchestrator -> Backlog/Assignment/Report`。
- 仍然留在 repo 内的 `GoalRecord` 与 legacy goal-dispatch 语义，只能解释为执行层 phase/leaf object，不得再被前台、prompt 或 UI 文案描述成主脑规划中心；当前服务层只保留显式 goal leaf dispatch family（`compile_goal_dispatch / dispatch_goal_execute_now / dispatch_goal_background / dispatch_goal_deferred_background`），prediction 侧对 retired goal-dispatch 只保留启动期历史 recommendation 清理语义，而不是运行期正式对象能力。

### 13.1 永续对象

- `IndustryInstanceRecord`
  - 语义从“行业实例 + 阶段状态”进一步收敛为长期 `MainBrainCarrier`
- `IndustryExecutionCoreIdentity`
  - 继续承接主脑身份壳
- `StrategyMemoryRecord`
  - 继续承接使命、北极星、优先级、委派原则、证据要求
- `ExecutionRoutineRecord`
  - 继续承接职业 agent 的肌肉记忆
- `OperatingLaneRecord`
  - 长期责任车道
- `BacklogItemRecord`
  - 未立即执行的机会、要求、问题、假设

### 13.2 周期对象

- `OperatingCycleRecord`
  - `daily / weekly / event`
- `CyclePlan` 当前允许内嵌在 `OperatingCycleRecord.plan_payload` 或等价字段中
- `GoalRecord`
  - 降级为周期内阶段目标，而不是长期使命
- `AssignmentRecord`
  - 主脑给职业 agent 的正式派工单

### 13.3 完成即关闭对象

- `TaskRecord / TaskRuntimeRecord`
- `RoutineRunRecord`
- `WorkflowRunRecord`
- `DecisionRequestRecord`
- `PredictionCaseRecord`
- `AgentReportRecord`

### 13.4 phase-next：建议升级为一等产品面/API surface 的对象

注：这些对象已在 hard-cut baseline 中存在；此处的“下一阶段”指把它们从“只在 detail 投影/内部写链可见”升级为稳定可见可操作的 cockpit surfaces，并补齐更宽回归与 live smoke。

- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`
- `HumanAssistTaskRecord`

### 13.5 前端同步要求

既然这些对象已引入，前端必须同步把以下对象升级为一等可见对象，而不是继续只围绕 `goal / task / schedule`：

- `carrier`
- `strategy`
- `lane`
- `cycle`
- `assignment`
- `agent report`
- `host_twin`
- `workspace_graph`
- `host_event_summary`

补充约束：

- `Runtime Center / /industry / Chat kickoff prompt` 必须显式消费 `strategy / lanes / current cycle / assignments / agent reports` 这类主脑 planning surface；不允许这些对象只存在于后端 read-model 而前台继续停留在旧 `goal / task / schedule` 心智。
- execution-side 前台必须把 `host_twin` 当作正式结构化对象来展示 current owner、continuity、legal recovery、coordination、blocked surfaces 与 app-family twins，不允许继续只把 `host_twin` 当 raw JSON detail 递归展开。
- `host_twin` 对 stale blocker / stale handoff history 的抑制只能发生在“当前 host/session 事实已恢复 clean + latest handoff event 明确进入 `return-ready / return-complete`”时；不得仅凭残留 recovery metadata 就把 live blocker 误判为已恢复。
- workflow / cron / fixed-SOP 可以持有 `host_snapshot`、`environment_ref`、`session_mount_id` 等执行缓存，但这些字段都必须视为 canonical `host_twin / environment detail` 的派生投影，不得被消费面重新升格为第二套 host 真相源。
- 当 backlog 明确来自 `source_report_id` 或 `synthesis_kind=followup-needed` 时，single-industry 的默认 runtime focus 允许优先呈现该 report follow-up backlog，并携带 supervisor/staffing/writeback metadata；这属于同一条 live focus 主链中的优先级选择，不构成第二套 planning/runtime 真相。
- 记忆/媒体 follow-up 读链里，`work_context_id` 是正式优先 scope；`task_id` 仅作为兜底，不允许消费面跳过 `work_context` 直接各自猜 recall scope。

### 13.5.1 硬切 reset 约束

- 本轮允许直接清理旧 runtime artifacts，而不是做历史迁移。
- reset 基线以 `scripts/reset_autonomy_runtime.py` 为准。
- 任何依赖旧 `phase1.sqlite3` 或 `memory/qmd` 内容才能启动的新实现，都视为错误接线。

---

## 13.6 `WorkContext` 补充对象

### 定义

`WorkContext` 表示一个连续工作的正式容器。

它不是聊天线程，也不是某个 agent 的私有长期脑，而是“这件事本身”的统一边界。

### 稳定核心字段

- `id`
- `title`
- `summary`
- `context_type`
- `status`
- `context_key`
- `owner_scope`
- `owner_agent_id`
- `industry_instance_id`
- `created_at`
- `updated_at`

### 建议字段

- `primary_thread_id`
- `source_kind`
- `source_ref`
- `parent_work_context_id`
- `metadata`

### 与现有对象关系

- `WorkContext 1 -> N Task`
- `WorkContext 1 -> N AgentMailboxRecord`
- `WorkContext 1 -> N AgentCheckpointRecord`
- `WorkContext 1 -> N AgentReportRecord`
- `WorkContext 1 -> N EvidenceRecord(metadata.work_context_id)`

### 边界说明

- `Task` 是执行单元，`WorkContext` 是持续工作边界
- `Thread / Session` 是交互表面，可映射到 `WorkContext`
- `mailbox / checkpoint / runtime` 仍是私有 working state，不提升为共享真相

### 读面契约补充

- Runtime Center 应提供 `WorkContext` 的 list / detail 正式读面，而不是只让 operator 从 task/thread 明细里反推
- conversation / task read surface 应显式暴露：
  - `work_context_id`
  - `context_key`
  - `work_context` summary
- media/chat writeback 与 memory recall 也必须显式把 `work_context_id` 作为正式 scope 消费；当媒体分析、长期记忆或 report drill-down 已绑定共享工作上下文时，不允许再次退回只靠 `task_id` 猜当前工作身份
- `control_thread_id`、`task-session:*` 这类线程锚点可以参与解析，但不应单独充当正式工作身份
- conversation read surface 在同线程存在主脑 phase-2 commit 持久态时，可把 canonical session snapshot 投影为 `meta.main_brain_commit`；这只是聊天 reload/read-model 的派生字段，不构成新的 `ChatCommit` 一级对象。

### 13.6.1 Execution Graph Projection Contract

`2026-04-14` 起，execution truth 到 memory graph 的正式收口合同补充如下：

- 正式 canonical owner 只允许放在 `state` 服务层：
  - `BacklogService`
  - `OperatingCycleService`
  - `AssignmentService`
  - `AgentReportService`
  - `WorkContextService`
- `industry/service_lifecycle.py`、`industry/report_synthesis.py`、`kernel/buddy_*` 这类业务入口可以继续写 canonical state，但不再是 raw execution graph writeback 的长期 owner。
- memory graph 的 execution 主节点至少包括：
  - `backlog`
  - `cycle`
  - `assignment`
  - `report`
  - `work_context`
  - `runtime_outcome`
- 稳定 node id 约定：
  - `backlog:{backlog_id}`
  - `cycle:{cycle_id}`
  - `assignment:{assignment_id}`
  - `report:{report_id}`
  - `work-context:{work_context_id}`
  - `runtime-outcome:{outcome_ref}`
- 正式必备关系方向：
  - `backlog belongs_to cycle`
  - `backlog produces assignment`
  - `assignment belongs_to cycle`
  - `assignment belongs_to work_context`
  - `assignment produces report`
  - `report belongs_to work_context`
  - `runtime_outcome belongs_to work_context`
- canonical execution 状态要直接投影到 graph node status，而不是只塞进字符串 summary：
  - backlog: `open / selected / materialized / completed`
  - cycle: `planned / active / review / completed`
  - assignment: `planned / queued / running / waiting-report / completed / failed`
  - report: `recorded / processed`
  - work_context: `active / paused / completed / archived`
- 如果 canonical link 发生迁移，graph projection 必须显式失效旧关系，不能只 upsert 新关系。至少包括：
  - 旧 `backlog -> cycle`
  - 旧 `backlog -> assignment`
  - 旧 `assignment -> cycle`
  - 旧 `assignment -> work_context`
  - 旧 `assignment -> report`
  - 旧 `report -> work_context`
  - 旧 `runtime_outcome -> work_context`
- `report_synthesis` 仍负责 `latest_findings / conflicts / holes / recommended_actions / replan`，但不再负责 raw report graph writeback；原始 `report` 节点与其 execution anchor 必须从 `AgentReportService.record_task_terminal_report(...)` 这条 canonical 写路径产生。
- 这次收口不新增第二套 graph-native runtime truth；memory graph 只是 canonical execution truth 的正式投影面，不反向替代 `state`。

## 13.7 Fixed SOP Kernel

### 定位

`Native Fixed SOP Kernel` 在 CoPaw 中的正式边界不是新的 routine engine，也不是第二执行中心，而是位于 workflow / schedule 层之上的内部固定 SOP 内核。

它只负责：

- 固定 SOP 编排
- schedule / webhook / API 串联
- 调用 CoPaw 已有 capability 或 routine

它不负责：

- browser / desktop UI 执行主链
- 独立 workflow/routine 真相
- 社区 workflow 导入 marketplace
- 私有 evidence / run history

### 建议对象

固定 SOP 仍应落在统一 `state`，不允许把运行真相外包到外部 workflow 系统。建议对象为：

- `FixedSopTemplateRecord`
  - 内建或受控模板对象
  - 只承接系统内核可支持的最小节点集
- `FixedSopBindingRecord`
  - 模板安装到具体环境、行业实例或 workflow 之后的正式绑定对象
  - 显式声明 `owner_agent_id`、行业/运行时上下文与风险基线

建议核心字段最少包括：

- `template_id / binding_id / run_id`
- `name / summary / status / version`
- `owner_scope / owner_agent_id / industry_instance_id / workflow_template_id`
- `risk_baseline / timeout_policy / retry_policy`
- `input_schema / output_schema / writeback_contract`
- `node_graph`
- `metadata`

### 真相边界

本轮不新增第二套 run truth。以下对象继续承担 canonical run / evidence / report 主链：

- `WorkflowRunRecord`
- `ExecutionRoutineRecord`
- `RoutineRunRecord`
- `EvidenceRecord`
- `AgentReportRecord`
- `ReportRecord`

明确不新增：

- 外部 callback run history 作为第二真相源
- `n8nExecutionRecord`

### 模板来源边界

`2026-03-26` 起，v1 `Native Fixed SOP Kernel` 不再支持社区 workflow 导入或 `Workflow Hub` marketplace。

当前最小边界是：

1. 模板仅来自内建/受控源码
2. 模板必须符合最小节点集：`trigger / guard / http_request / capability_call / routine_call / wait_callback / writeback`
3. 绑定对象仍需显式声明行业实例、`owner_agent_id`、风险基线与输入输出契约
4. operator canonical 产品面应转到 `Runtime Center -> Automation`

### 执行与回流边界

当固定 SOP 需要调用 CoPaw browser / desktop routine 时，应走：

`fixed sop kernel -> CoPaw capability/routine -> WorkflowRun / Evidence / AgentReport / Report 回写`

其中：

- routine 仍是叶子执行记忆
- `WorkflowRunRecord` 仍是 workflow 运行锚点
- `EvidenceRecord / AgentReportRecord / ReportRecord` 仍是前端可见结果与回流事实
- UI 动作只能通过 `capability_call` / `routine_call` 回到 CoPaw 自己的 body runtime
- 不允许再保留 `sop_binding_id -> system:trigger_sop_binding -> SopAdapterService` 作为目标运行链
