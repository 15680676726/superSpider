# API_TRANSITION_MAP.md

本文件用于定义 `CoPaw` 从现有 router / manager 体系迁移到未来 `SRK + state + evidence + capability + environment` 体系时的映射关系。

这不是最终 API 文档，而是：

- 旧接口职责识别表
- 旧模块到新服务的迁移映射表
- 保留 / 桥接 / 替换 / 删除 策略表

`2026-03-25` 补充说明：

- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md` 只作为 runtime-first 补充视角
- 该补充视角用于解释 runtime / environment / execution 的运行收口，不替代本文件的正式 API 迁移口径
- 如需使用 `ExecutionSession / EnvironmentHandle / RecoveryAction` 一类叙事名词，必须先映射回现有正式对象与正式写链
- `2026-03-26` 补充：`/sop-adapters` 与 `n8n Workflow Hub` 路径已从目标架构退役；后续固定 SOP 只允许以内建 `Native Fixed SOP Kernel` 形态存在
- `2026-03-27` 补充：browser / desktop live execution runtime 后续必须继续映射回
  `EnvironmentMount / SessionMount`，并通过 shared `Surface Host Contract` +
  browser `Site Contract` + Windows `Desktop App Contract` 暴露运行真相；主脑只负责
  assignment/supervision，不直接成为浏览器或桌面 driver
- `2026-03-27` 正式目标框架补充：
  - 上位正式目标改为 `Intent-Native Universal Carrier`
  - execution-side 正式框架改为 `Symbiotic Host Runtime`
  - `Seat Runtime / Host Companion Session / Workspace Graph / Host Event` 必须继续映射回统一 `state / evidence / capability / environment`

---

## 1. 迁移目标

当前 API 和 manager 体系的问题主要有：

- router 直接绑定旧 manager 或旧状态结构
- 渠道、cron、runner 等共同形成组合式主链，缺少唯一内核
- API 的资源组织方式更偏旧功能分类，不是未来运行对象分类

迁移目标是：

- 所有入口统一接入 `SRK` 或统一查询服务
- 旧 manager 从“真相源/主链”降级为 adapter 或被删除
- API 逐步围绕一级对象组织：
  - `Goal`
  - `Agent`
  - `Task`
  - `Environment`
  - `Evidence`
  - `Decision`
  - `Patch`

---

## 2. 迁移总原则

### 2.1 入口统一原则

所有写操作最终应走：

- `SRK`
- 或统一 service facade

### 2.2 查询统一原则

所有读操作最终应优先走：

- `StateQueryService`
- `EvidenceQueryService`
- `RuntimeCenterQueryService`

### 2.3 兼容隔离原则

旧 router 可以暂时保留路径，但其内部实现应逐步桥接到新服务，而不是继续直连旧 manager。

### 2.4 `2026-03-25` hard-cut 维护窗口规则

本轮迁移不再以“长期兼容旧主脑主线”为目标，而是以“单一自治主链”落地为目标。

当前 hard-cut 规则：

- 正式 operator 写入口必须逐步收口到 `MainBrainOrchestrator`
- `MainBrainChatService` 只保留聊天、澄清、状态说明与建议输出
- `Goal / Task / Schedule` 可以保留为执行层对象，但不再作为主脑规划主语义
- `delegate` 旧入口、chat 后台 writeback、app-name first 路由都应视为待删除兼容债
- 本系统处于 `2026-03-25` hard-cut 维护窗口，允许通过 reset 脚本直接清理旧 runtime data（以删旧为准，不做历史迁移）
- `2026-03-25` 完成补充：
  - `POST /runtime-center/tasks/{task_id}/delegate` 已从 runtime-center router 物理删除
  - 前台 capability / insights surface 不再公开 `dispatch_active_goals` / `dispatch_goal` 作为产品心智
  - execution-core 正式 query/runtime/tooling 口径已同步删掉 `dispatch_active_goals`，同时 execution-core baseline / prompt capability projection / actor capability surface 也已同步删掉 `dispatch_goal`
  - retired `dispatch_goal` 旧公共名已退役；goal service 现只保留显式 leaf dispatch family：`compile_goal_dispatch(...)`、`dispatch_goal_execute_now(...)`、`dispatch_goal_background(...)`、`dispatch_goal_deferred_background(...) + release_deferred_goal_dispatch(...)`
  - `dispatch_active_goals` 已从 router / system capability / goal service 公开面退役；prediction service 启动时会直接清理残留历史 recommendation，而不是继续改写后展示
  - 现役 prediction handoff 统一走 `manual:coordinate-main-brain + routes.coordinate`；前后端不再依赖旧 `goal_id / owner_agent_id / execute / activate / context` payload 做 dispatch 语义透传
  - `/goals` 叶子 compile/dispatch 返回面也已收口，不再额外回显 `compiled_specs` 与顶层 `trigger`；trigger 事实继续进入 override/runtime evidence，而不是在 dispatch payload 里再复制一份
  - `POST /goals/{goal_id}/dispatch`、`POST /goals/automation/dispatch-active`、`POST /runtime-center/goals/{goal_id}/dispatch` 已从 router 物理删除，不再保留 `410 Gone` 兼容壳；`GET /runtime-center/goals/{goal_id}` 这条 runtime-center goal detail alias 也已从 assembled root-router 退役，Goal detail 正式只保留 `/goals/{goal_id}/detail`
  - assembled root app 上的公开 `/goals` frontdoor 也已继续收口为 detail-only：`GET/POST /goals`、`GET/PATCH/DELETE /goals/{goal_id}` 与 `POST /goals/{goal_id}/compile` 不再挂到 root-router；如专项 app 仍需完整 `/goals` router，必须显式手工 include
  - `GET /goals/{goal_id}` 也已从 `goals` 公开 router 退役；public leaf read 只保留 `/goals/{goal_id}/detail`，不再继续暴露旧 `GoalRecord` 裸读面
  - `GET /runtime-center/industry/{instance_id}` 的正式 Current Focus 读面也已同步从 legacy goal 文本退场；当 live `assignment / backlog` 存在时，`execution.current_focus` 与 `main_chain.current_focus` 优先投影 live focus，节点 route 统一锚定到 `industry detail + assignment_id/backlog_item_id`，并通过 `focus_selection + selected assignment/backlog` 呈现 focused subview，不再回跳旧 goal detail
  - `Runtime Center / /industry / 行业 kickoff prompt` 现也已把 `strategy / lanes / current cycle / assignments / agent reports` 升成正式 planning surface：`Runtime Center` 的行业 focus section 已新增 `Main-Brain Planning` 卡，`/industry` 已新增 `工作泳道` 正式展示，kickoff prompt 会显式带出 `lane/backlog/cycle/assignment/report` 计数与 lane 摘要
  - `AgentProfile / AgentProfileOverrideRecord / runtime chat meta` 也已开始从 legacy `current_goal` 收口到 `current_focus_kind / current_focus_id / current_focus`；prompt appendix、Runtime Center conversations、overview agent meta 与主脑 roster 已优先消费 focus 字段，`current_goal / current_goal_id` 暂时只保留 leaf backlink 兼容
  - execution-side `host_twin` 也已开始作为正式前台 section 消费：`Runtime Center` detail drawer 现在会把 continuity / legal recovery / coordination / app-family twins / blocked surfaces 升成结构化 `Host Twin` section，而不是继续只递归展示 raw projection metadata
  - `RuntimeCenterStateQueryService` / task-review projection / overview governance` 也已开始消费 `host_twin_summary` 这类派生摘要，首屏读面优先显示 `seat_owner_ref / recommended_scheduler_action / active_app_family_keys / blocked_surface_count / legal_recovery_mode`，而不是继续靠 raw `host_twin` JSON 自行拼摘要
  - execution-side canonical host truth 现在也已补上“当前事实优先于历史 blocker 文案”的收口：stale blocker / stale handoff history 只会在当前 host/session 事实已 clean 且 latest handoff event 明确进入 `return-ready / return-complete` 时才会被抑制，不再因为残留 recovery metadata 就把 live blocker 吞掉
  - workflow resume / cron 与 fixed-SOP doctor/run 现在都会继续从 live `host_twin` 刷新执行面：workflow run detail / schedule meta 会回填 `host_snapshot / environment_ref / environment_id / session_mount_id / host_requirement`，fixed SOP 会正式阻断 `requires_human_return`、`legal_recovery.path=handoff` 与显式要求 `handoff/recover/retry` 的 blocker event，不再让 handoff-only 路径误判为可执行
  - workflow preview / fixed-SOP doctor 现在也会优先消费 top-level 或 nested `host_twin_summary`：当 canonical summary 已明确给出 `recommended_scheduler_action=proceed|continue`、`blocked_surface_count=0` 与非 handoff 的 `legal_recovery_mode` 时，消费面不再被 raw/stale handoff metadata 反向卡住
  - single-industry runtime focus 也已把 report follow-up truth 纳入同一条主链：当 backlog 来自 `source_report_id` 或 `synthesis_kind=followup-needed` 时，默认 focused runtime 会优先呈现该 follow-up backlog，并保留 supervisor/staffing/writeback metadata，而不是被无关 active assignment 抢走执行焦点
  - report follow-up backlog 现在还会继续保留 `control_thread_id / session_id / environment_ref / chat_writeback_channel / requested_surfaces`；即使后续只剩 session/control-thread 线索，governance、human-assist 与 runtime resume 也能把同一条 browser/desktop/document follow-up execution chain 接回正式主链
  - `HumanAssistTaskService` / runtime schedule resume 也已继续共享 `work_context_id + recommended_scheduler_action` 这条 continuity contract；pause/resume/reentry 不再各自猜当前执行身份
  - `GET /goals/{goal_id}/detail` 已进一步收口为只读 leaf detail；detail 读取不再隐式触发 `reconcile_goal_status()`，状态推进必须显式走 reconcile/write 链，不允许“看详情顺手改状态”
  - CLI `goals dispatch` 已从命令面物理删除，不再保留 retired shell；CLI 仅保留 `goals list/compile`
  - `GoalRecord` 仍可作为执行层 phase/leaf object 存在，但 operator 主入口必须优先经过 `strategy / lane / backlog / cycle / assignment / report`

---

## 3. 未来服务分层（建议）

建议未来服务按以下方向收敛：

- `SRKService`
  - 统一写入口与调度内核入口
- `StateQueryService`
  - 查询目标、任务、agent、runtime 等运行事实
- `EvidenceService`
  - 写入证据、查询证据、关联 replay/artifact
- `CapabilityService`
  - 查询能力、角色可见能力、能力元信息
  - 在 kernel / decision governance 下执行 capability mounts
- `EnvironmentService`
  - 管理环境挂载、会话 lease、环境状态
  - 统一 browser / desktop / document execution surface 的 host/session contract，而不是让
    每种 surface 各自发明 readiness/handoff/recovery 语义
  - 后续还应统一管理 `Seat Runtime`、`Host Companion Session`、workspace composition、
    以及 host-event-to-recovery 入口
- `DecisionService`
  - 待确认请求、审批结果、治理记录
- `HumanAssistTaskService`
  - 负责 human-only checkpoint 的发布、提交、验收、恢复排队
- `PatchService`
  - proposal、patch、apply、revert
- `ConfigService`
  - 声明式配置读写
- `CompatibilityBridge`
  - 为旧接口提供过渡适配
- `EnvironmentService` 的 execution-side 目标应进一步收敛为：
  - `Seat Runtime`
  - `Host Companion Session`
  - `Workspace Graph` projection 组装
  - `Host Event` 摄取、恢复与 runtime mechanism 接线
- 当前 `Workspace Graph` projection 组装的正式边界，已不再只是 refs/count：
  - 需要统一组装 `download_status / surface_contracts / handoff_checkpoint / latest_host_event_summary`
  - 需要继续派生 `locks[]` 与 `surfaces.browser|desktop|file_docs|clipboard|downloads|host_blocker`
  - 需要继续派生 grounded `ownership / collision_facts`，但仍然只能回映既有
    `EnvironmentMount / SessionMount / host-event / artifact-evidence` truth

---

## 4. 当前 router 映射表

下表中的“策略”含义：

- `keep`：未来仍保留类似职责，但实现迁移到新服务
- `bridge`：短期保留路径，内部桥接
- `replace`：未来应由新对象 / 新服务重组替代
- `delete`：未来应删除，而不是保留同构接口

---

### 4.1 `/config` -> `ConfigService`

- 当前 router：`src/copaw/app/routers/config.py`
- 当前职责：channel 配置、agent llm routing 等声明式配置读写；heartbeat 已从该 router 退役
- 未来归属：`ConfigService`
- 策略：`keep`
- 迁移说明：
  - 声明式配置仍然需要保留
  - 但不应继续承载运行真相
  - 前端 `Channels` 已不再作为独立 `Control` 页面存在；canonical UI 入口现为 `Settings -> /settings/channels`，旧 `/channels` 前端兼容壳已从主路由物理删除

---

### 4.2 `/models` -> `ProviderAdminService` + `Capability/Model registry` 桥接

- 当前 router：`src/copaw/app/routers/providers.py`
- 当前职责：provider 配置、激活模型、测试连接、发现模型、自定义 provider 管理
- 未来归属：
  - `ConfigService`（provider 声明式配置）
  - `CapabilityService`（模型能力元信息）
  - `ProviderAdminService`（管理动作）
- 策略：`bridge -> keep`
- 迁移说明：
  - 旧路径可保留一段时间
  - 但内部不应继续直连旧 `ProviderManager` 作为主真相源

---

### 4.3 `/local-models` -> `LocalModelService`

- 当前 router：`src/copaw/app/routers/local_models.py`
- 当前职责：本地模型下载、列表、删除、状态
- 未来归属：`LocalModelService`
- 策略：`keep`
- 迁移说明：
  - 本地模型能力仍保留
  - 但应与统一 `CapabilityMount` / model slot 对齐

---

### 4.4 `/ollama-models` -> `ProviderAdminService` / `LocalModelService`

- 当前 router：`src/copaw/app/routers/ollama_models.py`
- 当前职责：Ollama 模型管理
- 未来归属：
  - `ProviderAdminService`
  - `LocalModelService`
- 策略：`bridge`
- 迁移说明：
  - 未来可继续收敛到统一 provider / local model 管理面

---

### 4.5 `/skills` -> `CapabilityService`

- 当前 router：`src/copaw/app/routers/skills.py`
- 当前职责：skill 列表、启停、导入、删除、hub 安装
- 未来归属：`CapabilityService`
- 策略：`replace`
- 迁移说明：
  - skill 不再作为独立主语义
  - 当前列表/只读返回已经复用 `app.state.capability_service`
  - skill mounts 继续复用统一 capability execute contract，但 `2026-03-25` 起人类前台的 `/api/capabilities/{id}/execute` 已物理删除，只保留主脑/内核调用
  - 旧 `/skills/{name}/enable|disable` 与 `DELETE /skills/{name}` 现已桥接到 `system:set_capability_enabled` / `system:delete_capability`，不再绕过 kernel admit / risk / decision / evidence
- `Capability Market` 当前已通过 `/api/capability-market/skills` 与 `/api/capability-market/hub/*` 提供 canonical 产品读写面
- `2026-03-16` 起远程 hub 发现链已收口为 `SkillHub-first + legacy ClawHub fallback`：对上层调用仍保持 `search_hub_skills/install_skill_from_hub` 同一契约，但适配层优先走 `src/copaw/adapters/skillhub.py`，不要求另装外部 CLI，也不新增第四套能力语义
- 旧 `/skills` 当前主要保留为 legacy/compat admin alias 与 skill file/load 辅助面，不再承担正式产品入口
- `2026-03-15` 起旧 `/api/skills*` 已以显式 legacy capability alias 装配，并统一返回 `Deprecation + X-CoPaw-Compatibility-*` 头，指向 `/api/capability-market/skills`

---

### 4.6 `/mcp` -> `CapabilityService` + `ConfigService`

- 当前 router：`src/copaw/app/routers/mcp.py`
- 当前职责：MCP client 管理与配置
- 未来归属：
  - `ConfigService`（声明式配置）
  - `CapabilityService`（统一能力视图）
- 策略：`replace`
- 迁移说明：
  - MCP 不应长期作为与 tool/skill 平行的一等能力语义
  - 当前列表/只读返回已经复用 `app.state.capability_service`
  - MCP mounts 继续复用统一 capability execute contract，但 `2026-03-25` 起人类前台的 `/api/capabilities/{id}/execute` 已物理删除，只保留主脑/内核调用
- 旧 `/mcp/{client_key}/toggle` 与 `DELETE /mcp/{client_key}` 现已桥接到 `system:set_capability_enabled` / `system:delete_capability`，不再绕过 kernel 治理面
- `Capability Market` 当前已通过 `/api/capability-market/mcp*` 提供 canonical 产品读写面
- `GET/POST /api/capability-market/install-templates*` 当前已作为 host adapter 的 canonical 安装面；`desktop-windows` 模板会把本机桌面控制挂载为外部 `desktop_windows` MCP client，而不是在内核里新增平行 desktop tool 语义
- 旧 `/api/capability-market/mcp/templates*` 已从产品面物理删除，不再保留第二套路由壳
- `2026-03-13` 起 `V4` 规划补充：install template 产品面必须继续复用 actor/agent capability governance 正式写面；安装进入统一 capability pool 不等于自动分配给全部 agent，默认应支持按角色/agent 精确挂载，并遵守“单个业务 agent 非系统基线能力默认上限 12”
- `2026-03-13` 起 `V4` 规划补充：`industry preview/bootstrap` 也应复用同一套 install template 与 actor capability governance；preview 负责生成推荐安装包，bootstrap 负责执行 install plan 与角色分配，不允许另造第二套团队初始化安装逻辑
- `2026-03-13` 起 `V4` 规划补充：内部 canonical `execution-core / copaw-agent-runner` 暂继续保留，但 install template 与 workflow template 的产品面应把它视为团队总控核而不是默认执行员；大多数外部执行能力应优先推荐给 researcher / specialist / worker
- 旧 `/mcp` 当前主要保留为 legacy/compat alias 与外部客户端过渡面，不再承担正式产品入口
- `2026-03-15` 起旧 `/api/mcp*` 已以显式 legacy capability alias 装配，并统一返回 `Deprecation + X-CoPaw-Compatibility-*` 头，指向 `/api/capability-market/mcp`

---

### 4.7 `/capabilities` -> `CapabilityService` + `SRKService` + `DecisionService`

- 当前 router：`src/copaw/app/routers/capabilities.py`
- 当前职责：统一能力列表、汇总、启停、删除，以及 capability execute 入口
- 未来归属：
  - `CapabilityService`
  - `SRKService`
  - `DecisionService`
- 策略：`keep -> expand`
- 迁移说明：
  - 当前 `GET /capabilities` / `GET /capabilities/summary` 已提供统一 capability 读面
  - `tool / skill / MCP / system` mounts 的统一 execute contract 仍保留在 `CapabilityService + SRK` 内部，供主脑/内核调用
  - `2026-03-25` 起人类直打的 `POST /capabilities/{id}/execute` 已从 router 物理删除；产品链路固定为“人类 -> 主脑聊天 -> 主脑决定是否编排执行”
  - 当前 `PATCH /capabilities/{id}/toggle` 与 `DELETE /capabilities/{id}` 也已改为 kernel-governed write：分别经 `system:set_capability_enabled` / `system:delete_capability` 执行；delete 为 confirm-risk，需走 Runtime Center decision review/approve
  - `Capability Market` 当前已通过 `/api/capability-market/capabilities*` 提供 canonical 产品读写 facade；`/capabilities` 保留为较低层 capability read/governance 面，而不是人类可直接触发的执行写面
  - 当前 confirm-risk capability admission 已返回 `decision_request_id`，后续确认/拒绝由 Runtime Center 的 decision surface 统一承接
  - 当前 system mounts 已覆盖 `dispatch_query / dispatch_command / discover_capabilities / set_capability_enabled / delete_capability / update_industry_team / goal dispatch / learning strategy / patch apply/approve/reject` 等系统动作
  - `2026-03-19` 起 capability discovery 已收口到 `CapabilityService -> CapabilityDiscoveryService -> system:discover_capabilities`：行业 preview 推荐、prediction capability-gap 远程候选发现、以及 query execution 中主脑可调用的 discovery tool 复用同一 discovery 内核，不再由 `IndustryService` 与 `PredictionService` 各自维护一套 query 生成与远程目录搜索逻辑
  - `2026-03-23` 起 `capabilities execute` CLI 也已同步退役，不再保留第二条“人类直打能力执行”的入口
  - 当前已经补齐 `skill / MCP / system` capability internal execution 的自动化验收；剩余缺口是角色授权、环境约束与真实外部 provider 端到端覆盖

---

### 4.8 `/workspace` -> `WorkspaceService` + `ArtifactService`

- 当前 router：`src/copaw/app/routers/workspace.py`
- 当前职责：workspace 导入导出
- 未来归属：
  - `EnvironmentService`（workspace mount）
  - `ArtifactService`
- 策略：`bridge -> keep`
- 迁移说明：
  - 工作目录仍保留
  - 但应纳入环境系统与产物系统

---

### 4.9 `/envs` -> `ConfigService`

- 当前 router：`src/copaw/app/routers/envs.py`
- 当前职责：环境变量增删改查
- 未来归属：`ConfigService`
- 策略：`keep`
- 迁移说明：
  - 声明式系统配置能力保留

---

### 4.10 `/agent` -> `AgentWorkspaceService` + `Profile/Memory facade`

- 当前 router：`src/copaw/app/routers/agent.py`
- 当前职责：working files、memory files、running config 等
- 未来归属：
  - `AgentService`
  - `WorkspaceService`
  - `Memory/Profile facade`
- 策略：`replace`
- 迁移说明：
  - 未来 agent 应成为一级对象
  - 当前共享 `query_execution_service` 已通过 `app.state` 注入 direct `/api/agent` ingress 与 `KernelTurnExecutor`，为统一 turn execution 语义提供单一执行面
  - 当前 `src/copaw/app/agent_runtime.py` 已替换外部 `AgentApp` 宿主，`/api/agent/process` 通过本地 FastAPI ingress 直接调用 `KernelTurnExecutor`
  - 不应继续主要围绕“md 文件管理”组织接口

---

### 4.11 `/goals` -> `GoalService` + `SemanticCompiler` + `SRKService`

- 当前 router：`src/copaw/app/routers/goals.py`
- 当前职责：Goal CRUD、compile、leaf execution support
- 未来归属：
  - `GoalService`
  - `SemanticCompiler`
  - `SRKService`
- 策略：`bridge -> leaf`
- 迁移说明：
  - `GoalRecord + SqliteGoalRepository + GoalService + /goals` 后端一等对象已经落地
  - `POST /goals/{id}/compile` 继续保留为 leaf compiler/read boundary；`dispatch` / `dispatch-active` 旧入口已物理删除
  - Runtime Center 当前只保留 `/api/runtime-center/goals/{id}/compile`；旧 `/dispatch` 入口已删除，不再给 operator 暴露第二条派工 HTTP 路径
  - `GET /goals/{id}/detail` 已成为 Goal detail 的唯一正式 HTTP 读面；`GET /api/runtime-center/goals/{id}` runtime-center alias 已退役，Agent Workbench 与 Runtime Center 统一改走稳定的 leaf detail route
  - compiler 现已把 `compiler/task_seed/evidence_refs` 与 `feedback_summary / feedback_items / feedback_patch_ids / feedback_growth_ids / feedback_evidence_refs / next_plan_hints` 一并持久化到 state-backed `system:dispatch_query` task spec
  - learning proposal/patch/growth 现已自动补全 compiler seed 的 `goal_id / task_id / agent_id / source_evidence_id / evidence_refs`，且 approved/applied patch 与 recent growth 会反哺下一轮 planning/compile；`AgentProfile.current_focus_id` 已作为新的前台 focus 深链路主口径，`current_goal_id` 仅保留叶子 goal backlink 兼容
- `2026-03-25` hard-cut 补充：`Goal` 现在应被视为 cycle 下游的 phase/leaf object，而不是主脑长期规划入口；operator 主入口应优先消费 `strategy / lane / backlog / cycle / assignment / report`
- `2026-03-25` hard-cut 完成补充：旧 goal dispatch 只允许保留在执行层或 system capability 内部；前台不再暴露 direct delegate / goal-dispatch 心智

---

### 4.11a `/industry` -> `IndustryService` + `RuntimeCenter` industry surface

- 当前 router：`src/copaw/app/routers/industry.py`
- 当前职责：行业 bootstrap、行业实例 summary/detail 读面
- 未来归属：
  - `IndustryService`
  - `SemanticCompiler`
  - `GoalService`
  - `ScheduleService`
  - `RuntimeCenterQueryService`
- 策略：`keep -> expand`
- 迁移说明：
  - `POST /industry/v1/preview` 当前先把行业简报编译为 AI 生成、可编辑的 `IndustryDraftPlan`，而不是直接产生活跃实例
  - `POST /industry/v1/bootstrap` 当前已经统一进入 goal/schedule/kernel 主链，并且只激活 operator 最终编辑后的 `profile + draft`，而不是另起行业执行器或重走固定模板编译
  - `PUT /industry/v1/instances/{instance_id}/team` 当前已成为现有团队拓扑的 canonical 更新入口；它继续复用同一条 bootstrap 激活主链，但锁定现有 `instance_id` 做 team patch，使“新增/删除职业位”不再依赖隐式 re-bootstrap 语义
  - `system:update_industry_team` 当前已作为 kernel-governed team write capability 落地；prediction / recommendation 若发现执行中枢长期兜底某个叶子环路，会通过这条能力把“补岗位”正式回写到现有行业实例，而不是停留在手工说明层
  - `2026-03-20` 起 canonical team seat contract 已正式固定为 `employment_mode + activation_mode`：`employment_mode=career|temporary` 负责 seat 生命周期，`activation_mode=persistent|on-demand` 只负责唤醒方式；行业编译、团队运行态、Agent Workbench 与预测补位都必须复用这同一组字段，不再允许另造“临时/常驻/兼职”平行心智
  - `2026-03-20` 起 `system:update_industry_team` / `IndustryService.add_role_to_instance_team()` 已支持同一主链上的 seat lifecycle 动作：duplicate temporary add 复用现有 seat、temporary -> career 视为晋升而不是新建第二个岗位、completed temporary 在无 live work 时自动退场；temporary seat 若没有显式 `goal`，不再自动生成默认长期 goal
  - `2026-03-19` 起行业推荐侧的 install-template / curated / hub discovery 已从 `IndustryService` 私有实现切到共享 `CapabilityDiscoveryService`，`/industry` 读面返回的 recommendation 也会直接带出 `discovery_queries / match_signals / governance_path`，前后端不再各自猜测“为什么推荐、下一步如何治理”
  - `GET /industry/v1/instances` 与 `GET /industry/v1/instances/{instance_id}` 已提供正式行业 summary/detail 读面
  - `GET /runtime-center/industry` 与 `GET /runtime-center/industry/{instance_id}` 已把行业实例接入 Runtime Center operator surface
  - `2026-03-19` 起 `/industry` preview/bootstrap 已接入媒体分析主链：preview 接受 `media_inputs`，返回 `media_analyses / media_warnings`；bootstrap/update-team 接受 `media_analysis_ids` 并通过 `MediaService.adopt_analyses_for_industry()` 把已分析材料写回当前行业实例；前端 `/industry` 也已显式展示这些分析结果，而不是只保留 brief 文本
  - `2026-03-22` 起行业 chat kickoff 的 `learning` 阶段已不再只停留在调研目标；`LearningService.run_industry_acquisition_cycle()` 会在 kickoff 内正式产出 `CapabilityAcquisitionProposal -> InstallBindingPlan -> OnboardingRun`，并复用既有 install-plan / fixed-SOP binding / kernel dry-run 主链完成 capability install 与 growth/evidence 回流
  - 当前读面已显式聚合 goals / agents / schedules / tasks / decisions / evidence / patches / growth / proposals / acquisition_proposals / install_binding_plans / onboarding_runs / reports，并暴露默认 schedule 与 runtime drill-down route
  - 当前 steady-state 读面已完成从 carrier 到正式 repository/projection 的迁移；剩余债务主要收敛为 `IndustryService` 启动时的一次性 legacy backfill 与 override 清洗，而不是运行期读面继续依赖旧 carrier

---

### 4.11b `/media` -> `MediaService` + industry/chat/runtime surfaces

- 当前 router：`src/copaw/app/routers/media.py`
- 当前职责：统一链接解析、上传接入、媒体分析、analysis list/detail 查询
- 未来归属：
  - `MediaService`
  - `EvidenceService`
  - `KnowledgeService`
  - `Strategy/Backlog writeback boundary`
- 策略：`keep -> expand`
- 迁移说明：
  - `/api/media/*` 现在是建队入口与聊天入口共享的 canonical media ingress，而不是页面私有 upload helper
  - `POST /media/resolve-link`、`POST /media/ingest`、`POST /media/analyses`、`GET /media/analyses*` 已落地
  - 媒体分析的 durable truth 已收口到 `MediaAnalysisRecord + SqliteMediaAnalysisRepository`
  - `/runtime-center/chat/run` 会消费顶层 `media_analysis_ids`，并通过 `MediaService.build_prompt_context()` 把已分析材料注入本轮 prompt
  - 当前前端 `/chat` 已改为“先分析、再透传 analysis ids”的模式，不依赖第三方 chat widget raw attachment block 作为正式主链
  - 当前 `video-deep` 仍是 capability-gated path；默认 shipped video path 只有 `video-lite`

---

### 4.11c `/predictions` -> `PredictionService` + main-brain coordination bridge

- 当前 router：`src/copaw/app/routers/predictions.py`
- 当前职责：主脑晨会 / 晚会复盘 case 查询、recommendation 查看、review 回写，以及 recommendation 交接
- 未来归属：
  - `PredictionService`
  - `RuntimeCenterQueryService`
  - `Main-brain backlog / chat coordination bridge`
- 策略：`keep -> bridge`
- 迁移说明：
  - `/predictions` 当前已经不是“人类直接执行 recommendation”的入口，而是主脑 operating cycle 的复盘结果面
  - `2026-03-25` 起 `POST /predictions/{case_id}/recommendations/{recommendation_id}/execute` 已从 router 物理删除
  - 新的 `POST /predictions/{case_id}/recommendations/{recommendation_id}/coordinate` 只负责把 recommendation 登记给主脑 backlog / control-thread，不再由人类前台直接打到底层执行
  - 前端 `/predictions` 与 Runtime Center capability optimization 面已经统一改成“交给主脑”，产品链路固定为“人类 -> 主脑 -> agent 执行”

---

### 4.12 `/chats` -> `Task / Conversation facade`

- 当前公开 router：已删除旧 `/chats` ingress；前端正式改走 `src/copaw/app/routers/runtime_center.py` 下的 `/runtime-center/conversations/{thread_id}`
- 当前职责：按正式 thread_id 解析 agent/industry 会话，不再暴露旧 chat shell CRUD
- 未来归属：
  - `TaskQueryService`
  - `ConversationFacade`
  - `RuntimeCenterQueryService`
- 策略：`replace`
- 迁移说明：
  - 当前 chat 模型更像旧式会话壳
  - 未来应围绕 `Task / Agent / Evidence` 重组
  - `2026-03-14` 起旧 chat shell 层已物理删除；正式会话当前统一由 `RuntimeConversationFacade + AgentThreadBindingRecord + SessionRuntimeThreadHistoryReader` 解析
  - `2026-03-11` 起 widget session persistence 已改走 `GET /api/runtime-center/conversations/{thread_id}`，thread_id 采用 `industry-chat:{instance_id}:{role_id}` / `agent-chat:{agent_id}` 正式语义
- `2026-03-21` 起 `/chat` 已正式收口为“单一主脑控制线程前台”：行业前台控制线程保持 `industry-chat:{instance_id}:execution-core`，前端不再暴露 `task-chat:*` 第二聊天入口，也不再通过 `/runtime-center/chat/tasks*` 维护任务线程看板；执行结果应通过 `assignment / task / report / evidence / work-context` 正式读面回看
- `2026-03-25` hard-cut 补充：`/runtime-center/chat/run` 将成为 `MainBrainChatService + MainBrainOrchestrator` 的 auto frontdoor；纯聊天不再直接进行 durable writeback，所有正式写入改由 orchestrator 负责
- `2026-03-25` hard-cut 补充：`/runtime-center/chat/orchestrate` 已从 router 物理删除；显式执行编排 handoff 统一并回 `/runtime-center/chat/run` 的 auto/orchestrate 裁决链
- `2026-03-21` 起 runtime conversation facade 只接受 `industry-chat:{instance_id}:{role_id}` 与 `agent-chat:{agent_id}` 两类正式线程 id；`actor-chat:*` 与 `task-chat:*` 已从前台产品与正式解析链退役，请求会直接返回 `400`
- `2026-03-21` 起 execution-core 聊天前门的结构化输出已删除 `query_confirmation_policy_change` 分支；“默认执行 / 恢复确认”不再是持久治理能力，风险动作统一回到 kernel 既有 `auto / guarded / confirm` 链，浏览器/桌面等高风险外部动作默认继续显式确认
- `2026-03-19` 起 `/chat` 已新增显式 media panel，先经 `/api/media/*` 产出 `MediaAnalysisRecord`，再把 `media_analysis_ids` 顶层透传到 `chat/intake|run`；聊天主链消费的是分析结果而不是页面本地附件真相
- `2026-03-29` 补充：prompt recall 现已优先消费 `work_context_id`。当线程/任务已绑定共享工作上下文时，媒体分析与长期记忆的 recall 不再只按 `task_id` 兜底，而会优先命中同一 `work_context` scope，避免共享工作区里的素材/记忆在 follow-up turn 中漏召回
- `2026-03-29` 补充：runtime chat media 正式写回链也已补成 `work_context` 闭环。media analyze / adopt / retain / recall 现在都会显式透传 `work_context_id`；聊天附件 writeback 会进入 `memory:work_context:*` scope，recall hit 也会优先回显原始 `source_ref`
- `2026-03-19` 起已新增 `CHAT_RUNTIME_ALIGNMENT_PLAN.md` 作为下一轮迁移约束：当前 `chat/intake + ChatFrontdoorDecision + task-thread-first` 仅视为过渡方案，不得继续扩张；正式目标是删除 `/runtime-center/chat/intake`，让 `/chat` 默认直通 `chat/run`，并把宿主观察、task/create、durable writeback、风险确认收口到 tool/runtime/governance 显式边界
- `2026-03-28` 补充：对“系统不能做 / 不该做 / 暂缺宿主证明”的步骤，正式目标是在主脑控制线程内物化 `HumanAssistTask`，由 `HumanAssistTaskService + ConversationFacade + RuntimeCenterQueryService` 提供当前任务条、历史列表、聊天提交与自动验收；它不是 `task-chat:*` 的回潮，也不是新的公开聊天入口
- `2026-03-28` 补充：`/runtime-center/chat/run` 后续需要先判定当前线程是否存在活动 `HumanAssistTask`。当宿主发送“已完成 / 已上传 / 已处理”类回执时，应先进入 `submitted -> verifying -> accepted|rejected|need_more_evidence` 正式链，再决定是否把执行恢复排队回内核
- `2026-03-28` 补充：`HumanAssistTask` 只允许承接 `checkpoint / ui-assist / evidence-submit` 等 human-only step；没有验收契约的提醒文案不得作为正式任务发布
- `2026-03-29` 补充：`HumanAssistTask` 当前第一条正式 producer 已接到 runtime governance / host-twin blocker 上。环境 handoff 要求人返回时，治理层会直接物化 `task_type=host-handoff-return` 协作任务，并复用同一条聊天线程承接宿主回执。
- `2026-03-29` 补充：活动 `HumanAssistTask` 的聊天提交判定已经从“只认显式 `submit_human_assist` / media-only”扩大到“显式动作 + 验收锚点命中 + 完成回执话术”；自然语言回执不再需要额外 legacy chat frontdoor。
- 前端 `/chat` 侧栏已改为真实行业角色 / agent 列表，`/sessions` 页面与 `New Chat` shell 已删除
  - 旧 `/chats` HTTP router 与 `copaw chats` CLI 已删除，不再保留公开兼容入口
  - `chats.json` 主链 bootstrap/read fallback 已删除，legacy delete-gate surfaces 已移除；query turn 也不再额外写入 `chat:*` metadata task；如工作目录仍出现同名文件，也只应视为历史 artifact，不参与 runtime

---

### 4.13 `/cron` -> `ScheduleIngress` + `SRKService`

- 当前 router：`src/copaw/app/crons/api.py`
- 当前职责：job 增删改查、暂停恢复、手动运行
- 未来归属：
  - `ScheduleService`
  - `SRKService`
- 策略：`replace`
- 迁移说明：
  - cron 应作为统一调度入口的一部分，而不是平行主链
  - `Phase 1` 已通过 `CronManager + StateBackedJobRepository` 直接把 cron CRUD / 运行状态收口到 `ScheduleRecord` 与统一 `state`
  - `jobs.json` 主链 bootstrap/read fallback 已删除，legacy delete-gate surfaces 已移除；如工作目录仍出现同名文件，也只应视为历史 artifact，不参与 runtime
  - cron 文本与 cron-agent 任务均通过 `system:dispatch_query` 进入 kernel-owned query execution path（`KernelTurnExecutor` 包装 + `KernelQueryExecutionService` 实际流执行）
  - channel ingress / cron agent dispatch 现在都会先推断 `dispatch_query` 或 `dispatch_command` 及其 risk，再提交 kernel，避免 `/command` 旁路
  - Runtime Center 已把 schedule 暴露为一等对象：`/api/runtime-center/schedules`、`/api/runtime-center/schedules/{id}`、`/api/runtime-center/schedules/{id}/run|pause|resume` 已落地，且 `CronManager` runtime state 会持续回写 `ScheduleRecord`
  - `2026-03-29` 补充：schedule 写 frontdoor 现已统一进入 governed mutation；`/api/runtime-center/schedules*` 与 `/cron/jobs*` 的 create/update/delete/run/pause/resume 不再直接调用 `CronManager`，而是统一物化为 `system:create_schedule / update_schedule / delete_schedule / run_schedule / pause_schedule / resume_schedule` kernel task，并通过 `/api/runtime-center/decisions/*` 承接 confirm 链
- 前端独立 `/cron-jobs` 与 `/heartbeat` 页面及其 redirect 壳均已退役；steady-state operator IA 已收口为 `Runtime Center -> Automation`
- heartbeat 的 canonical HTTP surface 已迁入 `/api/runtime-center/heartbeat`（detail/update/run），旧 `/api/config/heartbeat` 已删除；前端 `AutomationTab` 只再消费 Runtime Center heartbeat surface
- `EnvironmentService` 现已补齐 orphaned lease recovery；`/api/runtime-center/environments|sessions|observations|replays|artifacts` 也已具备 detail 路由，环境对象不再只是列表读面
- `src/copaw/app/crons/executor.py`、`src/copaw/app/crons/manager.py`、`src/copaw/app/crons/heartbeat.py` 已删除无效 runner/channel 依赖；`CronManager` 现持有 heartbeat 运行态并向 Runtime Center 暴露 `status / last_run_at / next_run_at / query_path`，剩余缺口收敛为更深的宿主恢复与 service 边界继续收缩
- `2026-03-13` 起 `V4` 规划补充：当前 schedule/heartbeat surface 只是 workflow 底座的一部分；后续 `WorkflowTemplateRecord / WorkflowRunRecord` 必须复用现有 `/runtime-center/schedules*` 与 kernel-governed goal/task 主链，不允许在 `cron` 旁边再长出平行 workflow 主链

---

### 4.13a `workflow-templates`（planned） -> `WorkflowTemplateService` + existing `Goal/Schedule/Kernel` surfaces

- 当前 router：`not landed`
- 当前职责：无；今天的 workflow 逻辑仍分散在 `GoalService / Runtime Center Automation / Delegation / Industry bootstrap`
- 未来归属：
  - `WorkflowTemplateService`
  - `GoalService`
  - `ScheduleService`
  - `KernelDispatcher`
  - `DecisionService`
  - `EvidenceService`
- 策略：`add-on-top-of-existing`
- 迁移说明：
  - 这是在现有主链上的产品化对象补充，不是新运行内核
  - 建议新增：
    - `GET /api/workflow-templates`
    - `GET /api/workflow-templates/{template_id}`
    - `GET /api/workflow-templates/{template_id}/presets`
    - `POST /api/workflow-templates/{template_id}/presets`
    - `POST /api/workflow-templates/{template_id}/preview`
    - `GET /api/workflow-runs`
    - `GET /api/workflow-runs/{run_id}`
    - `POST /api/workflow-runs/{run_id}/cancel`
    - `GET /api/workflow-runs/{run_id}/steps/{step_id}`
  - `preview` 只返回 materialization diff，不直接执行
  - template `launch` / run `resume` 现只保留在 workflow service 内部能力边界，不再保留公开 HTTP 前门
  - `WorkflowRunRecord` 只做运行锚点，不替代 `Task / TaskRuntime`

---

### 4.13b `routines` -> `RoutineService` + `BrowserRuntimeService` + existing `Environment/Evidence/Workflow` surfaces

- 当前 router：`src/copaw/app/routers/routines.py`
- 当前职责：正式 routine 定义、evidence 提炼、replay/fallback、run 读面与 diagnosis 读面
- 未来归属：
  - `RoutineService`
  - `BrowserRuntimeService`
  - `EnvironmentService`
  - `EvidenceService`
  - `WorkflowTemplateService`
  - `RuntimeCenterQueryService`
- 策略：`add-on-top-of-existing`
- 迁移说明：
  - `routine` 是 agent-local、environment-bound 的叶子执行记忆，不是平行 workflow executor
  - 当前已落地：
    - `POST /api/routines`
    - `POST /api/routines/from-evidence`
    - `GET /api/routines`
    - `GET /api/routines/{routine_id}`
    - `GET /api/routines/{routine_id}/diagnosis`
    - `GET /api/routines/runs`
    - `GET /api/routines/runs/{run_id}`
  - `POST /api/routines/{routine_id}/replay` 已于 `2026-03-25` 从 router 物理删除；routine replay 只允许留在 `system:replay_routine` 内核/能力边界
  - Runtime Center 当前通过 `/api/runtime-center/overview` 的 routines card 暴露 routine summary，detail/drawer 则直接深链到 `/api/routines/*`
  - routine replay 必须复用既有 `EnvironmentService` lease/replay/session restore
  - 细粒度锁当前通过 `EnvironmentService` 的 `resource-slot:*` pseudo session mount 复用既有 session lease semantics
  - routine 失败回退必须回到 canonical `Task / Decision / Evidence / Kernel` 主链
  - routine replay evidence 当前直接写 `EvidenceRecord`，task id 使用 synthetic `routine-run:{routine_run_id}`，避免混入普通 query task
  - routine 不是固定 SOP 内核本身的执行目标；固定 SOP 只负责 workflow/schedule 层的低判断编排，routine/workflow truth 仍在统一 `state`

---

### 4.13c `/sop-adapters` -> `delete`

- 当前 router：`deleted`
- 当前职责：已删除；旧 `n8n / Workflow Hub / community template` adapter 面不再属于正式产品面
- 策略：`delete`
- 迁移说明：
  - `2026-03-27` 已完成 hard-cut：`src/copaw/sop_adapters/*`、`src/copaw/app/routers/sop_adapters.py`、旧 state `SopAdapter*` record/repository/export 与 fresh schema `sop_adapter_*` 表均已移除
  - `2026-03-27` 已继续完成 console 清尾：`console/src/api/modules/sopAdapters.ts`、`workflow-hub` 导航 alias 与 `Capability Market -> 工作流` 旧入口已删除；`WorkflowTemplates` 独立页已退役，前台自动化面正式收口到 `Runtime Center -> Automation`
  - `2026-03-27` capability-market install template 的 `workflow_resume.return_path` 已改指向 `Runtime Center -> Automation`；不再回跳到已退休的 `/workflow-templates/*` 页面壳
  - `2026-03-27` prediction / Insights 等 operator-facing copy 也已同步改为固定 SOP / 运行计划口径；不再把“工作流模板”当作前台正式产品对象
  - `POST /api/sop-callbacks/n8n/{binding_id}` 与社区模板同步如仍有残留，应继续按同一 retirement set 清空
  - 不再保留“继续收窄但长期共存”的兼容口径；如仍存在历史 runtime data，应通过 reset / hard-cut cleanup 直接清理，而不是继续维持双系统
  - 正式替代方案见下一节 `/fixed-sops`

---

### 4.13d `/fixed-sops` -> `FixedSopKernelService` + `WorkflowTemplateService` + `RuntimeCenterQueryService`

- 当前 router：`src/copaw/app/routers/fixed_sops.py`
- 当前职责：内建 fixed SOP template/binding 读写与 run detail 查询；旧 `sop_adapters` 已退役
- 未来归属：
  - `FixedSopKernelService`
  - `WorkflowTemplateService`
  - `RuntimeCenterQueryService`
  - `DecisionService`
  - `EvidenceService`
- 策略：`replace / landed`
- 迁移说明：
  - 固定 SOP 必须变成 CoPaw 内建最小内核，而不是外部 adapter 或社区 workflow marketplace
  - v1 只保留极小节点集：`trigger / guard / http_request / capability_call / routine_call / wait_callback / writeback`
  - schedule / webhook 继续复用既有 cron 与 ingress；fixed SOP kernel 只负责定义低判断链路，不另造第二调度系统
  - 任一步骤如果需要浏览器/桌面/文件真实 UI 动作，必须通过 `routine_call` 或 `capability_call` 回到 CoPaw 的 body runtime / routine 主链
  - workflow truth、evidence truth、decision truth、recovery truth 继续留在 CoPaw，不允许外包到外部 workflow engine
  - canonical operator 产品面应转到 `Runtime Center -> Automation`，不再保留 `Capability Market -> 工作流` 与独立 `WorkflowTemplates` 页面
  - 建议最小路由：
    - `GET /api/fixed-sops/templates`
    - `GET /api/fixed-sops/templates/{template_id}`
    - `GET /api/fixed-sops/bindings`
    - `POST /api/fixed-sops/bindings`
    - `PUT /api/fixed-sops/bindings/{binding_id}`
    - `POST /api/fixed-sops/bindings/{binding_id}/run`
    - `GET /api/fixed-sops/runs/{run_id}`

---

### 4.14 `/console` -> `RuntimeStreamService`

- 当前 router：`src/copaw/app/routers/console.py`
- 当前职责：console push stream
- 未来归属：`RuntimeStreamService`
- 策略：`bridge -> keep`
- 迁移说明：
  - 未来更适合作为运行中心流式状态或事件通道

---

### 4.15 `/voice` -> `ChannelAdapter` + `SRK ingress`

- 当前 router：`src/copaw/app/routers/voice.py`
- 当前职责：voice / Twilio / relay 相关入口
- 未来归属：
  - `ChannelAdapter`
  - `SRKService`
- 策略：`bridge`
- 迁移说明：
  - voice 仍保留
  - 但应作为 channel ingress，而不是特殊平行主链

---

### 4.16 `/runtime-center` -> `RuntimeCenterQueryService` + `State/Evidence/Decision/Patch facade`

- 当前 router：`src/copaw/app/routers/runtime_center.py`
- 当前职责：overview、goal/schedule/operator 动作、evidence、environments、kernel task、learning 等聚合读面与治理动作
- 未来归属：
  - `RuntimeCenterQueryService`
  - `StateQueryService`
  - `EvidenceService`
  - `DecisionService`
  - `PatchService`
- 策略：`bridge -> keep`
- 迁移说明：
  - 当前 Runtime Center 已经是前端运行中心的主要 operator surface，`surface` 是唯一主语义，旧 `bridge` 命名壳已在 `V3-B4` 删除
  - 当前 kernel task confirm、goal compile/dispatch、schedule detail/run/pause/resume、decision list/detail/review/approve/reject、patch approve/reject/apply/rollback、task detail、goal detail、patch detail、growth detail、agent detail、environment detail、learning 持久化读面已经落地
  - execution-side browser/desktop environment detail 后续应统一先暴露 shared
    `Surface Host Contract` 字段，再追加 browser `Site Contract` 与 Windows
    `Desktop App Contract` 细项；不再继续只给前台一个 `browser_surface_ready /
    desktop_surface_ready` 粗粒度摘要
  - 在 `Symbiotic Host Runtime` 目标下，Runtime Center 还应继续暴露 `seat / workspace /
    host events / cooperative adapter availability`，而不是把 execution-side 继续理解为几块孤立 surface
  - 当前 workspace detail 的正式读面已经推进到结构化工作区：前台不应再只消费
    `workspace_id + refs + counts`，而应继续读取 `locks / surfaces / ownership / collision /
    handoff / download status` 这些正式 projection 字段
- 当前 actor-first 能力治理面也已进入 Runtime Center：`GET /runtime-center/actors/{agent_id}/capabilities` 与 `GET /runtime-center/agents/{agent_id}/capabilities` 会返回 baseline / blueprint / explicit / recommended / effective capability surface 以及最近治理决策；`POST /runtime-center/actors/{agent_id}/capabilities/governed` 与 `POST /runtime-center/agents/{agent_id}/capabilities/governed` 默认走 confirm-risk 治理提交流，而不是前端直接改本地权限状态
- `V4` 的 install template / workflow template 产品面应直接建立在这套 actor capability governance 上，而不是再造“模板安装后全员默认可用”的平行分配逻辑
- `V4` 的角色治理语义还应继续收紧：`execution-core` 产品上应呈现为团队总控核，推荐能力集以 dispatch / delegate / supervise / summarize 为主；外部执行能力推荐应优先出现在专业 agent 的 capability surface 中
  - 当前 overview 已覆盖 tasks / routines / goals / schedules / industry / agents / predictions / capabilities / evidence / governance / decisions / patches / growth 等正式卡片，前端直接消费 `/runtime-center/overview`，不再合成 mock/chat fallback，并已接入 decision approve/reject、routine replay/diagnosis 与 Patch/Growth 一等卡片
  - 当前 `/runtime-center/conversations/{thread_id}` 已成为 chat widget 的正式线程读面，替代旧 `/chats` session shell persistence
  - 当前 `GET /runtime-center/decisions/{id}` 已保持纯读；`POST /runtime-center/decisions/{id}/review` 才负责把 `open` 显式推进到 `reviewing`
  - 当前 `/runtime-center/events` 已提供 SSE runtime event stream；前端只把它当作 reload trigger，而不是第二真相源
  - 当前 `/runtime-center/recovery/latest` 与 `/runtime-center/sessions/{id}/lease/force-release` 仍是一等 operator 动作；`/runtime-center/replays/{id}/execute` 已于 `2026-03-25` 从 router 物理删除，不再允许人类前台直接重放执行
  - `V6` 的 routine diagnosis / lock conflict / replay fallback 也应继续落在 Runtime Center detail/drawer 体系里，不允许再造 page-local routine operator 面
  - 当前 `/runtime-center/learning/proposals|patches|growth` 已统一走共享 `LearningService`，不再旁路到底层 engine
  - `2026-03-29` 补充：single-item patch 写动作现也已统一收口到 Runtime Center governed surface；`/api/runtime-center/learning/patches/{id}/approve|reject|apply|rollback` 全部通过 kernel-governed `system:*patch` mounts 执行，旧 `/api/learning/patches/{id}/approve|reject|apply|rollback` 已物理删除
- `2026-03-22` 起 `/api/learning/acquisition/proposals|plans|onboarding-runs|run` 已作为 learning 写读面落地，用于承接行业 learning stage 自动产出的 acquisition/install/onboarding 闭环；`CapabilityAcquisitionProposal` 现也已正式接入 approval gate，并开放 approve/reject 写入口；Runtime Center 的行业 detail 也已直接消费这些正式对象，而不是从日志推断
  - 当前 `RuntimeOverviewResponse.bridge` 与 `X-CoPaw-Bridge-*` header 已删除；Runtime Center discovery/header contract 现统一使用 `RuntimeCenterSurfaceInfo` 与 `X-CoPaw-Runtime-*` / `X-CoPaw-Runtime-Surface-*`
  - 当前这些 detail route 已被 Runtime Center 前端统一消费为 drawer drill-down；overview/card/detail 已完成对正式 service 与治理动作验收的收口，不再保留 runtime-center bridge fallback
  - `2026-03-29` 补充：`GovernanceStatus` 当前已正式纳入 `host_twin / handoff / staffing / human_assist` blocker 摘要；`GovernanceService.admission_block_reason(...)` 除 emergency stop 外，也会在 `system:dispatch_query / system:dispatch_command` 前检查 handoff、人协作阻塞与 staffing confirmation

---

## 5. 当前 manager 映射表

### 5.1 `AgentRunner` -> `RuntimeHost + KernelTurnExecutor + KernelQueryExecutionService`

- 当前类：`deleted (2026-03-12; src/copaw/app/runner/runner.py)`
- 当前职责：已由 `RuntimeHost`、`KernelTurnExecutor`、`KernelQueryExecutionService` 与本地 agent ingress 接管
- 未来归属：
  - `SRKService`
  - `RuntimeHost`
  - `TurnExecutor`
- 策略：`deleted`
- 说明：
  - `system:dispatch_query` 现经 `CapabilityService -> kernel admit/risk -> KernelTurnExecutor -> KernelQueryExecutionService`
  - direct `/api/agent/process` 已由 `src/copaw/app/agent_runtime.py` 承接，并使用本地 `_local_tasks` 注册表配合 restart 取消在途请求
  - `_app.py` 现直接装配 `RuntimeHost + KernelQueryExecutionService + KernelTurnExecutor`，不再创建 `app.state.runner`
  - 环境 lease/recovery/replay 的主语义已迁入 `RuntimeHost + EnvironmentService`
  - 该旧宿主壳已在 `V3-B4` 完成真实退役，不再作为公开主链或兼容装配点

---

### 5.2 `ChatManager` / `StateBackedChatRepository` -> deleted

- 当前类：`src/copaw/app/runner/manager.py`、`src/copaw/app/runner/repo/state_repo.py`
- 当前职责：旧 chat spec CRUD / chat shell state bridge
- 未来归属：
  - `ConversationFacade`
  - `AgentThreadBindingRecord`
  - `SessionRuntimeThreadHistoryReader`
- 策略：`deleted`
- 说明：
  - `2026-03-14` 起上述旧 chat shell 组件已物理删除，不再承担任何 query lifecycle 元数据职责
  - 正式 thread 解析统一收口到 `RuntimeConversationFacade`，历史恢复统一收口到 `src/copaw/app/runtime_threads.py`
  - 如工作目录仍出现 `chats.json` 或旧 `chat:*` 记录，只能视为历史 artifact，不可重新接回 runtime 主链

---

### 5.3 `CronManager` -> `ScheduleService`

- 当前类：`src/copaw/app/crons/manager.py`
- 当前职责：job 调度与 heartbeat 维护
- 未来归属：
  - `ScheduleService`
  - `SRKService`
- 策略：`replace`
- 说明：
  - `Phase 1` 当前已不再经 bridge，同步 cron CRUD / 运行状态直接进入 `ScheduleRecord` 与 state-backed repository
  - `StateBackedJobRepository` 已成为 sole runtime read/write surface，`jobs.json` delete-gate surface 已移除；如工作目录仍出现同名文件，也只应视为历史 artifact，不参与 runtime

---

### 5.4 `ChannelManager` -> `ChannelAdapterRegistry`

- 当前类：`src/copaw/app/channels/manager.py`
- 当前职责：channel 生命周期与消息路由
- 未来归属：
  - `ChannelAdapterRegistry`
  - `SRK ingress`
- 策略：`bridge -> keep`
- 说明：
  - 渠道适配价值高，可保留
  - 但其不应继续成为主链调度中心
- 当前 channel consume/process 已改为 kernel-backed ingress（`system:dispatch_query`），不再直连 runner

---

### 5.5 `MCPClientManager` -> `CapabilityProvider`

- 当前类：`src/copaw/app/mcp/manager.py`
- 当前职责：MCP client 生命周期与 client 获取
- 未来归属：
  - `CapabilityProvider`
  - `ConfigService`
- 策略：`replace`
- 说明：
  - MCP provider 应承担“外部能力接入点”，而不是继续在核心层扩散 host-specific tool 语义
  - 当前 Windows desktop control 已通过 `src/copaw/adapters/desktop/` 以 stdio MCP adapter 形式接入，证明“控整机”主链可以走外部 provider 挂载而不是平行内建工具

---

### 5.6 `ProviderManager` -> `ProviderAdminService` + `Capability/Model registry`

- 当前类：`src/copaw/providers/provider_manager.py`
- 当前职责：provider 配置、active model、model discovery、custom provider
- 未来归属：
  - `ProviderAdminService`
  - `ConfigService`
  - `CapabilityService`
- 策略：`bridge -> keep`
- 说明：
  - provider 适配价值高
  - 但不应继续成为高层主事实源

---

### 5.7 `skills_manager` -> `CapabilityRegistry source`

- 当前模块：`src/copaw/agents/skills_manager.py`
- 当前职责：skill 发现、同步、启停
- 未来归属：`CapabilityRegistry source`
- 策略：`replace`
- 说明：
  - 当前 skill 已被桥接为 capability source，并可通过 `/capabilities` 暴露统一读面
  - skill 执行已收口到统一 capability execute path，但 `2026-03-23` 起人类前台 `/capabilities/{id}/execute` 已物理删除，只保留主脑/内核调用
  - 旧 manager 仍保留 discovery / sync / enable 语义，尚未完全降级为纯 source/provider

---

### 5.8 `MemoryManager` -> `Knowledge/Evidence adjunct service`

- 当前类：`src/copaw/agents/memory/memory_manager.py`
- 当前职责：长期记忆与检索增强
- 未来归属：
  - `KnowledgeService`
  - `MemoryRecallService`
  - `MemoryReflectionService`
  - `DerivedMemoryIndexService`
  - `Evidence/Memory adjunct`
- 策略：`bridge -> shrink`
- 说明：
  - 记忆应继续存在
  - 但不能替代统一运行真相和证据链
  - durable truth 应继续落在 `StrategyMemoryRecord / KnowledgeChunkRecord / EvidenceRecord`
  - 后续允许接入 `QMD / LanceDB / vector` sidecar，但只能作为 recall backend 或 rebuildable index
  - 不允许把 sidecar、Markdown memory 文件或 `MemoryManager` 自身重新升级为第二真相源

---

## 6. API 迁移优先级

补充（截至 `2026-03-29` 的 phase-next 牵引项，影响 API contract 的演进顺序，但不意味着终态已交付）：

- `Full Host Digital Twin` 扩面（基线为 `Execution-Grade Host Twin`；后续仍会继续补 multi-seat/multi-agent coordination 与更长时间的 live smoke）
- single-industry 真实世界扩面（更长周期、更高并发、更真实的 supervisor/handoff/staffing 组合）
- 主脑 cockpit 扩面（当前 repo 定义内的 unified runtime chain read surface 已收口；后续继续把 `strategy / lanes / backlog / cycles / assignments / agent reports` 推进到更完整的治理写链与可见化）
- 回归与 live smoke 扩面（优先扩 `industry/runtime/human-assist/host recovery` 聚合回归与真实宿主链）
- 重模块拆分（Chat runtime derivation / human-assist presenter / transport request 与 industry page presenter 已完成一轮下沉；router/service/query presenter/console pages 后续仍要继续拆）

### 第一优先级（Phase 1 收口）

- `jobs/chats/sessions` 旧真相源清退（已完成，残留文件需人工清理）
- `/cron`
- `/chats`
- runner query lifecycle

原因：

- 这些路径直接牵涉主链退役、删旧验收与 state 单一真相源

### 第二优先级（Phase 2）

- `/capabilities`
- `/skills`
- `/mcp`

原因：

- 这些路径直接牵涉能力语义统一、execute contract 与风险治理统一

### 第三优先级（Phase 2.5 ~ 4）

- `/runtime-center`
- `/goals`
- decision / patch / growth 相关对象接口

原因：

- 这些路径直接影响前端可见化与上层语义闭环

### 第四优先级（Phase 4 之后）

- provider / local-models / envs / agent 等治理型接口再做进一步整理

---

## 7. 新 API 组织建议（未来视角）

未来建议逐步过渡到更清晰的对象导向路径，例如：

- `/goals/*`
- `/agents/*`
- `/tasks/*`
- `/runtime/*`
- `/environments/*`
- `/runtime/seats/*`
- `/runtime/workspaces/*`
- `/runtime/host-events/*`
- `/evidence/*`
- `/decisions/*`
- `/patches/*`
- `/config/*`

说明：

- 旧路径不一定一次性删除
- 但新前端和新服务应优先围绕这些对象建模

---

## 8. 当前稳定结论

以下结论当前可以视为稳定：

- `/config` 未来大概率保留，但职责会收窄到声明式配置
- `/skills` 与 `/mcp` 最终不应继续作为平行一级能力接口
- `/capabilities` 已成为统一能力读面，并已承接 `tool / skill / MCP / system` execute；toggle/delete 也已进入 kernel-governed write，confirm-risk admission 会返回 `decision_request_id`
- `SRK` 当前已经拥有持久化 admit/risk/decision/evidence 闭环，并已接管 channels / cron / heartbeat 的 ingress；`system:dispatch_query` / `system:dispatch_command` 已改为 `CapabilityService -> KernelTurnExecutor -> KernelQueryExecutionService` 的 kernel-owned 执行链，direct `/api/agent/process` 也已直连本地 kernel ingress，`AgentRunner` 宿主壳已在 `V3-B4` 删除
- `EnvironmentService` 已持久化 `EnvironmentMount / SessionMount` 的 `lease_status / lease_owner / lease_token / lease_acquired_at / lease_expires_at / live_handle_ref`，并具备 `acquire / heartbeat / release / reap` 生命周期；当前下一正式补齐项已明确为 shared `Surface Host Contract`、browser `Site Contract`、Windows `Desktop App Contract`、`Seat Runtime / Host Companion Session / Workspace Graph / Host Event`，以及对应的宿主恢复/交接策略
- `/goals` 已成为后端一级对象接口，Goal detail 正式只通过 `/goals/{id}/detail` 落地；`/api/runtime-center/goals/{id}` alias 已退役，Agent Workbench 与 Runtime Center 都已接入稳定对象深链路；compiler 也已把 `compiler/task_seed/evidence_refs` 与 learning feedback metadata 持久化到 state-backed tasks
- `/runtime-center/decisions/*` 已成为统一的 DecisionRequest 读写治理面；detail 已纯读，review/approve/reject 为显式动作，且 Runtime Center 已补齐 governance / recovery / automation 正式工作面
- `/runtime-center/learning/*` 已经成为当前 proposal/patch/growth 读面，且读取已统一走共享 `LearningService`；`capability / profile / role / plan` patch 已可通过持久化 override executor 产生真实副作用，patch/growth detail 也已显式挂上 `goal/task/agent/evidence` 关联，并会反哺下一轮 compile feedback context
- `/runtime-center` 已不止 overview 卡片，还具备 task/goal/agent/patch/growth/environment detail 路由，以及 patch approve/reject/apply/rollback operator 路由；这些 detail/actions 已被前端或测试真实消费，V3 operator surface 已完成收口，后续缺口转入 V4 prediction / governed recommendation
- `/cron` ingress 已进入 `SRK`，旧 runner 主链也已从实际 turn execution 中退出
- `/chats` 未来应退化为 task/conversation facade，而不是一级主模型
- `learning` 已经具备持久化 proposal/patch/growth 闭环；`compiler` 也已把 growth/patch 结果收进下一轮 planning/compile，后续问题转入 prediction review、governed recommendation 与更真实的 provider/environment 覆盖
- `ChannelManager`、`ProviderManager` 更适合保留为 adapter / admin service，而不是主真相源

以下内容保留实现级弹性：

- 新 REST 路径的最终命名
- 某些流式接口是走 SSE 还是 WebSocket
- 某些前端聚合接口的具体粒度

---

## 9. 一句话总结

本映射表的目标不是立刻废掉所有旧 API，而是明确：哪些旧路径要保留、哪些只桥接、哪些必须替换，以及它们最终应该接到哪个新服务上。


---

## 10. Post-`V6` 主脑 cockpit（现状 + phase-next）

下一正式阶段的迁移目标不是在 `industry` 旁边再造第二套执行器，而是在现有 `IndustryService + Runtime Center` 基线之上把主脑自治对象与 API 硬切成唯一正式主链。

现状（截至 `2026-03-29`）：`Runtime Center / /industry / kickoff prompt` 已把 `strategy / lanes / current cycle / assignments / agent reports` 提升为正式 planning 读面基线；这一轮又继续补上 `Unified Runtime Chain` 聚合读面、`focus_kind + focus_id` drill-down、以及 `/runtime-center/reports` 的 `industry / assignment / lane / cycle / needs_followup / processed` 过滤面。但“更完整的 cockpit 写链、治理动作、回归与 live smoke 扩面”仍属于 phase-next。

phase-next 候选独立 surfaces（如后续需要把 cockpit 从 `industry detail` 投影进一步拆成专用 endpoint，再锁定最终路径命名）：

- `/api/runtime-center/main-brain/{carrier_id}`
  - 聚合 `carrier / identity / strategy / current cycle / current focuses / next review`
- `/api/runtime-center/lanes`
  - 读写长期责任车道
- `/api/runtime-center/backlog`
  - 读写 backlog item
- `/api/runtime-center/cycles`
  - 读写 `daily / weekly / event` cycle 与 cycle plan
- `/api/runtime-center/assignments`
  - 主脑派工读面与操作面
- `/api/runtime-center/agent-reports`
  - 职业 agent 回流读面与主脑消费入口

迁移原则：

- 不另造平行 planner truth source
- 不另造平行执行器
- `dispatch-active-goals` 不再作为主脑默认 planning entry；若保留，只能作为 cycle 下游或 legacy leaf executor
- operator chat writeback 默认优先写入 `strategy / lane / backlog / immediate-goal` 之一，而不是无差别直接写 active goal
- 正式写链应统一经过 `MainBrainOrchestrator`

前端同步要求：

- Runtime Center、`/industry`、`Chat`、`AgentWorkbench` 必须消费同一批 canonical surfaces
- 不允许前端本地推导 `current_cycle / current_focus / assignment_owner / report_consumed`

---

## 11. WorkContext 迁移补充

### 目标

未来正式“连续工作单元”不再依赖 `agent-chat / actor-chat` 主线程去猜，而是收敛为：

- `WorkContextRecord`
- `TaskRecord.work_context_id`
- `AgentMailboxRecord.work_context_id`
- `AgentCheckpointRecord.work_context_id`
- `AgentReportRecord.work_context_id`

### 迁移原则

- `task-thread` 是当前第一批默认 `WorkContext` 锚点
- child task 默认继承 parent `work_context_id`
- runtime conversation facade 继续保留，但其上下文边界应逐步从“线程别名”转为“线程 + WorkContext”

### 当前 canonical contract

- Runtime Center 正式读面：
  - `GET /api/runtime-center/work-contexts`
  - `GET /api/runtime-center/work-contexts/{context_id}`
- Runtime Center overview 已新增 `work-contexts` card，`WorkContext` 不再只能隐身在 task detail JSON 里
- conversation facade 对 industry / agent 线程统一补齐：
  - `context_key`
  - `work_context_id`
  - `work_context`
- `/chat` front-door 写契约改为：
  - 优先显式传 `work_context_id`
  - 否则显式传 `context_key`
  - 当前默认锚点优先复用 `control-thread:{control_thread_id}`

### 边界说明

- `industry-chat / agent-chat` 是当前仅保留的正式聊天入口
- `actor-chat / task-chat` 已从正式 facade 退役，请求会直接拒绝，不再承担历史兼容职责
- 线程 id 可以帮助定位 `WorkContext`
- 线程 id 不能替代 `WorkContextRecord`
- 前端禁止仅凭本地线程类型去推断“这件事是谁”；应优先消费后端返回的 `work_context_id / context_key / work_context`
