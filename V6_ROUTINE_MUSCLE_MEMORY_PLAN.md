# V6 Routine / Muscle Memory 升级计划

`2026-03-26` supplement:
- with `Agent Body Grid` as the new execution-side direction, `workflow / routine / SOP` must now be aligned with `body scheduler / lease` semantics instead of treated as a separate future concern
- the formal layering is `Assignment -> Role Workflow -> Body Scheduler -> Body Lease -> Routine/Operator -> Evidence/Report`
- `workflow` remains the role-coherent execution shell, and `routine` remains the leaf execution memory
- external `n8n / Workflow Hub` path is retired from the target architecture
- all later `n8n` references in this document are historical and should now be read as `Native Fixed SOP Kernel`
- fixed SOP remains an internal low-judgment orchestration layer for webhook / schedule / API-first paths only
- future workflow preview/launch must validate body/session/resource availability in addition to capability availability
- fixed SOP must not grow into the browser/desktop/document execution engine; any real UI action must still run through CoPaw body/routine execution

本文件用于把 post-`V5` 的下一正式阶段收口成一个明确、可执行、可验收的版本计划。

`V6` 不是重做 `V5`，也不是另起一套 workflow/RPA 系统；它解决的是当前系统在“固定 SOP / 灵活判断 / 浏览器执行肌肉 / 总控跨职业协调”四层之间还没有完全分清边界，尤其浏览器叶子执行层仍缺少“可对象化、可回放、可诊断、可治理”的 `routine / 肌肉记忆`。

---

## 1. 为什么是 `V6`

`V5` 已经把以下主链做成正式产品面：

- `WorkflowTemplateRecord / WorkflowRunRecord`
- `browser-local` profile / session / start / attach / stop
- `EnvironmentService` lease / recovery / replay
- `Runtime Center` operator diagnose / recovery / governance / workflow drilldown
- 统一 `capability / kernel / evidence / decision` 主链

当前真正缺的不是“还能不能跑 workflow”，而是：

- 固定 SOP 和灵活工作流还没有被正式分层
- 浏览器叶子执行仍主要停留在即时 tool 调用和证据回放
- 同类动作反复执行时，还没有稳定的 `routine` 对象承载“怎么做”
- 失败后可以 replay，但还缺“deterministic replay -> drift diagnose -> controlled fallback”这一层
- Runtime Center 还没有把“routine 健康度 / 漂移 / 锁冲突 / 最近回退”做成 operator 可见对象
- 多 agent 共享浏览器 profile/session/account 时，锁粒度还不够细

所以 `V6` 的一句话目标是：

> 在不引入平行 workflow 内核的前提下，明确固定 SOP 与灵活工作流的分工，把浏览器叶子执行升级为正式 `routine` 对象，并补齐 replay、fallback、diagnose、resource lock 与固定 SOP 编排层的接线边界。

---

## 2. `V6` 的稳定边界

`V6` 必须先把几个语义写死，否则后面很容易绕偏。

### 2.1 workflow 和 routine 不是一回事

- `WorkflowTemplate / WorkflowRun` 是跨 step、跨 agent、跨 goal/schedule 的顶层运行壳
- `Routine` 是单 agent、单环境类型、可重复复用的叶子执行记忆
- workflow 继续保持 run-centric
- routine 只负责“这个动作链怎么稳定完成”，不取代 workflow 编排

### 2.2 routine 不是新的 workflow DSL

- 不允许为 routine 再造一套顶层编排语法
- 不允许让 routine 脱离既有 `Goal / Task / Decision / Evidence / Environment` 主链
- 不允许为了回放方便，在 `RuntimeHost + Kernel` 旁边再长出私有执行器主链

### 2.3 固定工作流和灵活工作流必须分层

- 固定工作流 = 可重复、低判断、低 token、稳定 SOP
- 灵活工作流 = 需要 agent 判断、需要跨职业协作、不能写死为静态条件树
- 总控负责判断“哪些进入固定 SOP，哪些继续由 agent 决策”
- 顶层 workflow 仍保持 run-centric；固定 SOP 只是其中一类可执行策略，不替代 workflow 真相源

### 2.4 `n8n` 只是固定 SOP 编排层，不是执行肌肉层

- `n8n` 只能在 `V6-E` 承接固定 SOP、webhook、定时任务、API 串联
- `n8n` 不是浏览器 `routine` 的执行引擎
- routine 的正式对象、状态、诊断、证据、回退仍在 `CoPaw` 自己的统一 `state / environment / evidence` 中
- 不允许把 workflow 或 routine 的定义外包给 `n8n` 作为第一真相源

### 2.5 桌面级 muscle memory 必须后置

- 浏览器是 `V6` 第一优先
- 桌面级执行只能在浏览器 routine、回放、诊断、锁治理稳定后再做
- 不允许为了“桌面也要有”提前把架构复杂度一次性拉满

---

## 3. 当前基线与 `V6` 的承接方式

`V6` 不是绿地开发，应直接承接当前真实模块：

- `src/copaw/workflows/service.py`
- `src/copaw/capabilities/browser_runtime.py`
- `src/copaw/environments/service.py`
- `src/copaw/agents/tools/browser_control.py`
- `src/copaw/evidence/`
- `src/copaw/state/models.py`
- `Runtime Center` 现有 recovery / replay / workflow diagnosis / actor detail surfaces

当前已经具备的可复用能力：

- workflow template / run / schedule / cron 正式主链
- 浏览器 session/profile 的持久化与 attach
- environment lease / orphan recovery / replay executor
- browser evidence sink
- workflow run 的 diagnosis / step execution / checkpoint drilldown 基础
- operator 级 confirm/governance 主链
- execution-core 对行业 goal / schedule / chat writeback 的正式控制链

因此 `V6` 的正确做法是：

- 让总控明确区分固定 SOP 与灵活工作流
- 让固定 SOP 可以在外部编排层稳定执行，但真相仍回到 `CoPaw`
- 在现有 browser/environment/evidence/workflow 基线之上加一层正式 `routine` 对象与诊断面
- 让 routine replay 复用现有 replay/lease/session restore 基础设施
- 让 fallback 回到既有 kernel/task/decision/evidence 主链

而不是：

- 重做浏览器运行时
- 引入新的外部 workflow 主链
- 重新发明一套状态、锁和诊断面

---

## 4. `V6` 的核心设计原则

### 4.1 证据优先

- 每次 routine capture / replay / fallback 都必须产生正式 `EvidenceRecord`
- screenshot / page snapshot / selector drift / fallback summary 不能只写日志

### 4.2 环境优先

- routine 必须声明它依赖哪种 `EnvironmentMount / SessionMount`
- 不允许继续靠 prompt 文本恢复“当前浏览器在哪个页面、登录没登录”

### 4.3 锁优先

- routine 一旦进入正式运行，就必须显式声明资源锁范围
- 不允许多个 agent 盲目共享同一 profile/session/account/tab

### 4.4 回放优先于再理解

- 已有稳定 routine 时，优先 deterministic replay
- replay 失败后先进入诊断，再决定是否回退到 LLM 重新理解
- 不允许把每次相同动作都重新交给模型解释

### 4.5 结构化记忆优先于全文存档

- routine 记忆保存结构化动作契约、前置条件、校验点、锁策略、失败分类、成功签名
- 原始截图、DOM、视频、长日志放到 evidence/artifact store
- 不把完整 prompt、完整 transcript、整页 HTML 全量复制进 routine 记录

### 4.6 总控定义分层，外部编排只负责固定 SOP

- 总控负责定义哪些工作流固定、哪些工作流灵活
- 固定 SOP 可以交给外部编排层运行
- 灵活判断、跨职业协调、异常升级仍属于 `CoPaw` 总控和各职业 agent
- 不允许把“谁来决策”外包给外部编排器

### 4.7 浏览器优先于桌面

- `V6-A/B/C/D` 只承诺浏览器 routine
- `V6-E` 才补固定 SOP 编排层
- `V6-F` 才进入桌面 muscle memory

---

## 5. `V6` 新增或升级的对象

`V6` 不需要一次性引入很多对象，但至少要有一组正式对象把 routine 放进统一真相源。

### 5.1 `ExecutionRoutineRecord`

定位：

- agent-local、environment-bound 的可复用叶子执行记忆对象

必须满足：

- 不替代 `WorkflowTemplateRecord / WorkflowRunRecord`
- 必须挂在现有 `CapabilityMount / EnvironmentMount / SessionMount / EvidenceRecord` 之上
- 第一阶段先服务浏览器 routine

建议字段：

- `id / routine_key / name / summary / status`
- `owner_scope / owner_agent_id / source_capability_id / trigger_kind`
- `environment_kind / session_requirements / isolation_policy / lock_scope`
- `input_schema / preconditions / expected_observations / action_contract`
- `success_signature / drift_signals / replay_policy / fallback_policy`
- `risk_baseline / evidence_expectations`
- `source_evidence_ids / last_verified_at / success_rate / created_at / updated_at`

### 5.2 `RoutineRunRecord`

定位：

- 一次 routine capture / replay / fallback 的运行锚点对象

必须满足：

- 只记录一次 leaf routine 运行，不替代 `TaskRuntime` 或 `WorkflowRun`
- 必须显式记录 deterministic replay 结果、失败分类、fallback 去向

建议字段：

- `id / routine_id / source_type / source_ref / status`
- `input_payload / owner_agent_id / owner_scope`
- `environment_id / session_id / lease_ref / checkpoint_ref`
- `deterministic_result / failure_class / fallback_mode / fallback_task_id / decision_request_id`
- `output_summary / evidence_ids / started_at / completed_at`

### 5.3 `RoutineDiagnosis`

定位：

- Runtime Center 消费的 routine 诊断读模型

建议字段：

- `routine_id / last_run_id / status / drift_status`
- `selector_health / session_health / lock_health / evidence_health`
- `recent_failures / fallback_summary / resource_conflicts`
- `recommended_actions / last_verified_at`

### 5.4 资源锁对象边界

`V6-D` 需要更细锁粒度，但不应急着造平行环境系统。

第一原则：

- 先扩展现有 `EnvironmentService` 与 `SessionMount` 的 lease 语义
- 如果现有 `lease_status / lease_owner / lease_token` 无法表达子资源锁，再引入独立 `ExecutionResourceLeaseRecord`

锁粒度最少要覆盖：

- browser profile
- browser session
- domain/account
- page/tab
- workspace artifact target

---

## 6. `V6` 的正式施工顺序

`V6` 不是一个模糊大阶段，必须按 6 个连续批次推进。

### 6.1 `V6-A` 浏览器 routine 对象化

目标：

- 把重复浏览器动作沉淀成正式 `routine` 对象，而不是只保留即时 tool 调用和证据尾迹

本批次必须解决：

- 定义 `ExecutionRoutineRecord`
- 确定 routine 来源：手动创建、从稳定 browser run 提炼、从 workflow step 固化
- 为 routine 绑定 `browser-local` session/profile/environment 约束
- 定义最小 `action_contract`，描述页面前置条件、关键动作、验证点、预期产物
- 把 routine 接到现有 capability/workflow/industry 主链，而不是单独挂在某个页面私有状态里

后端落点：

- `src/copaw/routines/`（planned）
- `src/copaw/capabilities/browser_runtime.py`
- `src/copaw/environments/service.py`
- `src/copaw/state/models.py`
- `src/copaw/workflows/service.py`

前端落点：

- `Runtime Center`
- `workflow run detail`
- `browser-local` 相关详情面

第一批次推荐的 routine 来源顺序：

1. operator 显式标记一个稳定浏览器执行为 routine
2. workflow step 在多次成功后被建议沉淀为 routine
3. query-tool/browser actuation 的稳定路径被人工确认后固化

本批次不做：

- 全自动无限录制一切动作
- 桌面级 routine
- `n8n` 集成
- 跨环境的通用宏语言

验收标准：

- 浏览器 leaf execution 可以正式查询到 `routine` 对象
- routine 有 owner、环境约束、风险、证据要求
- workflow/query/browser product surface 可以引用该 routine，而不是把它退回文本描述

### 6.2 `V6-B` routine 回放与失败回退

目标：

- 让 routine 从“被记录下来”升级为“能稳定 replay，并在失败后进入受控 fallback”

本批次必须解决：

- routine replay 调用现有 `EnvironmentService` lease/replay/session restore
- 每次 replay 记录 `RoutineRunRecord`
- 定义失败分类：前置条件不满足、页面漂移、鉴权失效、资源锁冲突、风险确认阻断、未知执行错误
- 定义 fallback 策略：
  - `retry-same-session`
  - `reattach-or-recover-session`
  - `pause-for-confirm`
  - `return-to-llm-replan`
  - `hard-fail`
- 把 fallback 回到 canonical `Task / Decision / Evidence / Kernel` 主链

必须新增的诊断输出：

- replay 是否 deterministic 成功
- 失败发生在哪个 checkpoint
- 回退到了哪个 task/decision
- 这次失败是否会让 routine 进入 `degraded`

本批次不做：

- 失败后私自无限重试
- 在 routine 自己内部维护一套绕过 kernel 的补救逻辑

验收标准：

- 已存在 routine 可以被显式 replay
- replay 失败时会产出结构化 failure class 与 fallback summary
- operator 可以看到“这次是回放失败”还是“回到模型重规划”

### 6.3 `V6-C` Runtime Center 展示 routine 诊断

目标：

- 把 routine 变成 Runtime Center 中真正可看、可诊断、可追责的一等对象

本批次必须解决：

- routine 列表、detail、最近运行、最近回退、最近冲突
- routine 健康度：成功率、最近验证时间、漂移状态、依赖 session/profile 状态
- routine 与 workflow run / task / evidence / decision 的双向跳转
- operator 能看见：
  - routine 当前绑定哪个环境
  - 最近是谁持有锁
  - 最近失败的类别
  - 最近一次 fallback 的去向
  - 是否已进入 `degraded`

前端最少要有的诊断卡：

- `Routine Summary`
- `Replay History`
- `Failure / Drift`
- `Lock / Session`
- `Evidence / Snapshot`

必须坚持的边界：

- 不新建 page-local routine store
- 不让诊断依赖前端拼装假状态
- 继续复用 Runtime Center detail drawer / drilldown 体系

验收标准：

- operator 不翻日志也能知道 routine 为什么不可用
- routine 可以从 Runtime Center 直接跳到 evidence / workflow run / session detail

### 6.4 `V6-D` 资源锁细化

目标：

- 避免多个 agent 在浏览器环境里“看起来都能跑，实际互相打架”

本批次必须解决：

- 将当前 lease 从“会话级大锁”细化为“资源槽位锁”
- 最少覆盖：
  - profile 级
  - session 级
  - account/domain 级
  - page/tab 级
  - artifact/下载目录级
- 定义锁冲突策略：
  - queue
  - fail-fast
  - guarded handoff
  - operator confirm
- 将资源锁冲突纳入 `RoutineDiagnosis` 和 `Runtime Center`

必须与现有主链对齐：

- 锁状态仍通过 `EnvironmentService` 与 Runtime Center 暴露
- 不允许 routine 私自维护一套内存锁表成为第二真相源

验收标准：

- 同一浏览器 profile/session 下的两个 routine 冲突会被显式识别
- operator 能看到冲突是谁造成的、卡在哪个资源槽
- orphan lock 能继续复用当前 recovery/reap 机制处理

### 6.5 `V6-E` 固定 SOP 编排层（`n8n`）

目标：

- 在 browser routine 稳定后，正式补齐固定 SOP 编排层，让低判断、重复型工作流脱离大模型实时决策

本批次必须解决：

- 由总控明确区分固定 SOP 与灵活工作流
- 为固定 SOP 定义统一 `adapter` 边界
- `n8n` 只承接 webhook、schedule、API 串联、固定条件分支
- 固定 SOP 运行结果仍要落回 `WorkflowRunRecord / EvidenceRecord / Runtime Center`
- `n8n` 触发浏览器执行时，实际浏览器动作仍由 `browser routine` 完成
- `n8n` 的失败、超时、审批、异常升级继续走 `CoPaw` 治理主链

明确禁止：

- 把 `n8n` 当成 workflow/routine 的配置真相源
- 让 `n8n` 自己持有唯一执行历史
- 让 `n8n` 直接承担浏览器 UI 操作主链
- 让 `n8n` 决定跨职业协同或灵活业务判断
- 让 operator 必须跳出 Runtime Center 才能看懂执行结果

验收标准：

- 至少一类固定 SOP 已能通过 `n8n` 稳定运行，例如日报、差评跟进或固定巡检
- `n8n` 运行不会替代 `WorkflowRun`、`DecisionRequest`、`EvidenceRecord`
- 灵活判断与跨职业协调仍留在总控和 agent 主链

### 6.6 `V6-F` 最后才是桌面级 muscle memory

目标：

- 在浏览器 routine 与资源锁体系稳定后，才把 muscle memory 扩到桌面客户端和本地应用

本批次必须解决：

- 复用 `ExecutionRoutineRecord / RoutineRunRecord / RoutineDiagnosis` 的共性模型
- 定义桌面环境的 session/handle/窗口锁语义
- 定义桌面失败分类：窗口丢失、焦点漂移、分辨率变化、权限弹窗、人工接管中断

明确限制：

- 桌面执行是 `V6` 的最后批次，不得反向绑架浏览器主线
- 第一个桌面版本只做少量高价值场景，不做“全桌面通吃”

验收标准：

- 桌面 routine 仍使用统一 evidence/governance/runtime-center 结果面
- 桌面 muscle memory 没有拉出平行状态系统

---

## 7. Runtime Center 应该最终看见什么

`V6` 完成后，前端不应只看见“某个 workflow 成功/失败”，还应能直接看见 routine 层的运行事实。

最小可见对象：

- 当前有哪些 routine
- 每个 routine 属于哪个 agent / capability / environment
- 最近一次 replay 是否成功
- 最近一次失败是什么类型
- 是否回退到了 LLM / kernel task / decision confirm
- 当前锁被谁持有
- 依赖的 browser session/profile 是否健康
- 最近成功证据与最近失败证据

最小操作入口：

- 查看 routine detail
- 手动 replay
- 查看最近回退
- 查看锁冲突
- 强制释放孤儿锁
- 标记 `degraded / disabled / retired`

---

## 8. 与 workflow、industry、capability 的接线要求

### 8.1 与 workflow 的关系

- workflow step 可以引用 routine
- workflow 运行过程中生成的新稳定 leaf path 可以建议沉淀为 routine
- routine 失败时可以回退到 workflow step 的 canonical task path
- 固定 SOP 可以映射到外部编排层，但 workflow 真相仍留在 `WorkflowTemplate / WorkflowRun`

### 8.2 与行业团队的关系

- routine 不是每个行业都复制一份默认模板
- 可以有全局 routine，也可以有 industry-scoped routine
- 角色/agent 的 `allowed_capabilities` 与环境约束仍是 routine 可用性的前置门
- 总控应正式声明哪些工作流是固定 SOP，哪些保留给灵活判断
- 当跨职业问题出现时，总控必须继续负责派单、回收证据、汇总结论，而不是把协同逻辑写死进 `n8n`

### 8.3 与 capability 的关系

- routine 不是第四套能力语义
- routine 必须挂在某个 capability 或 capability family 之下
- capability 描述“能做什么”，routine 描述“在这个环境里通常怎么稳定做”

### 8.4 与 `n8n` 的关系

- `n8n` 是固定 SOP 编排层，不是浏览器/桌面执行层
- 有 API 的固定流程可由 `n8n` 直接编排
- 需要 UI 操作的固定流程，可由 `n8n` 触发 `CoPaw` 的 browser routine
- `n8n` 不应直接承载灵活回复、跨职业判断或总控策略

---

## 9. 数据体积与记忆控制原则

`V6` 会引入操作记忆，但不能把数据体积做炸。

必须坚持：

- routine 只存结构化动作契约、前置条件、成功签名、失败分类、checkpoint 引用、锁策略
- 长截图、长日志、DOM、视频、原始下载文件继续放 `Evidence / Artifact / Replay` 体系
- routine record 默认只保留最近有效统计、最近失败摘要、最近验证结果，不做无限全文堆积
- 可按 `last_verified_at / success_rate / recent_failure_count` 触发压缩或退役，而不是无限增长

建议的控制策略：

- raw artifacts 用 retention/TTL
- routine 只保留结构化索引和少量近期摘要
- 最近有效动作、近期失败、禁止重复动作写成 compact metadata，而不是持续附加长 prompt 文本

---

## 10. 外部能力与开源依赖策略

`V6` 可以复用开源能力，但不应该直接把项目主链外包出去。

推荐策略：

- 浏览器执行继续以现有 `browser-local` / Playwright 栈为主
- `n8n` 只在 `V6-E` 作为固定 SOP 编排层
- 桌面层后续再按场景评估 Windows UI Automation / 其他宿主能力

明确不做：

- 直接引入一个外部开源 workflow/RPA 项目作为新的真相源
- 因为“接得快”就让外部项目接管状态、证据、治理或 operator 诊断

---

## 11. 测试与验收矩阵

`V6` 每个批次至少考虑 4 类验证：

### 11.1 单元测试

- routine object normalize / replay policy / fallback policy / drift classify
- lock scope resolve / conflict strategy

### 11.2 集成测试

- routine + browser runtime
- routine + environment lease/replay
- routine + workflow step reference
- routine + decision/governance fallback

### 11.3 端到端测试

- 浏览器 routine 录制/回放
- replay 失败后进入 fallback
- Runtime Center routine diagnosis 可见
- 资源锁冲突的 operator 处理链

### 11.4 真实世界 smoke

- browser profile/session attach
- login checkpoint 恢复
- orphan lock recovery
- 固定 SOP 编排层的 timeout / failure / evidence 回流

---

## 12. `V6` 完成时的交付标准

`V6` 不能只算“写了 routine 代码”，至少要满足以下结果：

- 浏览器 routine 已是正式对象，不再只是隐含在即时 browser tool 调用里
- routine replay / failure fallback 稳定进入统一 kernel/evidence/decision 主链
- Runtime Center 能直接解释 routine 为什么成功、为什么失败、为什么被锁住
- 资源锁细化到能支撑多 agent 同机浏览器执行
- 固定 SOP 即使进入 `n8n`，真相仍留在 `CoPaw`，`n8n` 只是固定编排层
- 桌面级 muscle memory 没有把系统重新拉回平行状态和私有执行器

一句话总结：

> `V5` 让系统拥有更成熟的执行表面；`V6` 要把“固定 SOP / 灵活判断 / 浏览器肌肉记忆 / 总控跨职业协调”四层关系正式写清，并让浏览器层真正长出可复用的肌肉记忆。
