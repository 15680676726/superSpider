# V5 执行表面升级计划

本文件定义 `V4` 完成之后的下一正式阶段。

它不重开 `V1 / V2 / V3 / V4`，而是在当前真实代码基线上，把系统从“已经具备自动化、预测、治理对象”继续升级为“执行表面更完整、诊断更深入、扩展接入更正式、浏览器与工作流更像产品而不是工具集合”的版本。

如果与以下文档冲突，优先级依次为：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. `implementation_plan.md`
5. 本文件 `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`

---

## 1. 为什么是 `V5`，不是重做 `V4`

当前仓库已经不是“还没做 workflow/capability/prediction”的阶段。

截至 `2026-03-14`，以下内容已经是现状，不是草案：

- `Capability Market` canonical 产品面已存在
- `MCP template install` 与 install-return workflow resume 已存在
- `WorkflowTemplateRecord / WorkflowPresetRecord / WorkflowRunRecord` 已进入统一 `state`
- `/workflow-templates` 前端页、preview、launch、preset、cancel、assignment-gap 与 budget diagnostics 已存在
- actor/agent 级 capability governance 已存在
- `Predictions / Reports / Performance / Runtime Center` 的结果面已存在
- recovery / replay / approval / review / actor mailbox / checkpoint 主链已存在

所以这一步不该伪装成“继续补 V4 欠账”，而应该明确登记为：

> `V5 = 执行表面升级 + 运行治理深化 + 扩展契约正式化 + 工作流运行壳硬化 + operator 诊断面收口`

一句话说，`V4` 解决的是“系统已经能跑、能装、能编排、能预测”；`V5` 要解决的是“它是否像一个成熟的长期执行产品，而不是几条强主链上叠着分散工具面”。

---

## 2. 当前现实基线

`V5` 只能建立在当前仓库已经落地的真实主链之上：

### 2.1 能力安装与治理基线

- 后端已有 `Capability Market` canonical surface：
  - `/api/capability-market/capabilities*`
  - `/api/capability-market/install-templates`
- 前端已有 `/capability-market`
- install template 已支持：
  - install
  - enable existing
  - target agent assignment
  - workflow resume payload 回流
- actor/agent capability 写面与 governed 写面已存在：
  - `/api/runtime-center/actors/{agent_id}/capabilities*`
  - `/api/runtime-center/agents/{agent_id}/capabilities*`

### 2.2 Workflow 基线

- 已有正式 workflow 对象：
  - `WorkflowTemplateRecord`
  - `WorkflowPresetRecord`
  - `WorkflowRunRecord`
- 已有正式接口：
  - `/api/workflow-templates*`
  - `/api/workflow-runs*`
- `WorkflowTemplatePreview` 已返回：
  - `steps`
  - `owner_role_candidates`
  - `required_capability_ids`
  - `assignment_gap_capability_ids`
  - `budget_status_by_agent`
  - `launch_blockers`
- `Workflow Template Center` 已不是一次性占位页，而是正式运行入口

### 2.3 Runtime / Governance / Recovery 基线

- `Runtime Center` 已承接 decision review/approve/reject、recovery、automation、overview
- `DecisionRequest`、actor mailbox、checkpoint、resume/retry/cancel 已存在
- startup recovery、replay execute、session lease force release 已进入正式主链
- 当前风险模型仍保持单一：
  - `auto`
  - `guarded`
  - `confirm`

### 2.4 当前缺口不是“有没有对象”，而是“产品表面是否完整”

当前真正缺的主要是：

1. 浏览器还更像 capability/tool，不像完整产品面
2. 治理有底座，但还没完整产品化成“执行策略面”
3. `skills / integrations / MCP` 已有发现与安装面，但还没有 manifest/schema/lifecycle contract
4. workflow 已有模板与运行对象，但还没完全长成 deterministic/resume/operator-debug runtime shell
5. diagnose / example run / error drilldown 仍分散，不是统一 operator 面

---

## 3. 借鉴什么，不借鉴什么

`V5` 可以吸收 `OpenClaw` 一类产品的强项，但必须服从当前仓库的单一内核与统一能力语义。

### 3.1 必须借鉴的 5 条主线

#### 3.1.1 把浏览器从“工具”升级成“产品面”

不是只继续加 `click/type`。

要补的是：

- 浏览器 profile 列表与选择
- 现有浏览器接管与隔离会话切换
- 登录接管/登录状态诊断
- host 模式与 sandbox 模式切换
- 浏览器诊断页
- 浏览器会话证据与回放锚点

对当前仓库的落点：

- 继续走 `capabilities + environments + evidence` 主链
- 不新造平行浏览器执行器
- 浏览器应成为 `Capability Market + Runtime Center + Workflow Template Center` 共同可见的正式运行表面

#### 3.1.2 把治理从“风险级别”升级成“执行策略面”

当前 `auto / guarded / confirm` 不能改，但其上层产品面需要补齐：

- per-agent allowlist
- per-host policy
- approval pending 队列
- chat approval forwarding
- install/update 期间的策略继承
- host 可达性、能力握手与执行前置条件

对当前仓库的落点：

- 继续复用 `DecisionRequestRecord` 与 Runtime Center decisions
- 不允许每个页面再造自己的审批逻辑

#### 3.1.3 把扩展接入做成正式 contract

不是继续依赖散的 skill 文档和手工表单。

要补的是：

- manifest
- config schema
- install/update/enable/disable/rollback lifecycle
- config UI 自动生成
- capability exposure contract
- diagnosis contract
- example run contract

对当前仓库的落点：

- 产品层仍可保留 `Skills / Integrations / MCP`
- 内部仍统一归入 `CapabilityMount`
- 配置不能绕开治理和证据

#### 3.1.4 把 workflow 做成更强的运行壳

当前已有 workflow template/run，但还需要更强的：

- deterministic step execution view
- checkpoint / resume / replay
- operator handoff
- step-level evidence drilldown
- blocked reason taxonomy
- restart 后的稳定续跑

对当前仓库的落点：

- 继续复用 `GoalService + Kernel + EnvironmentService + Evidence`
- 不允许另起一套 workflow executor DSL

#### 3.1.5 把 operator 调试面做透

系统现在已经能跑很多链路，但“出问题时你到底能不能快速知道卡在哪”还不够。

要补的是：

- diagnose
- example run
- error drilldown
- trace/evidence/source 直链
- dependency/host/auth/config readiness 检查

对当前仓库的落点：

- 优先收口到 `Capability Market / Workflow Templates / Runtime Center`
- 不要把诊断继续埋在日志和零散 toast 里

### 3.2 必须吸收的 4 条支撑线

#### 3.2.1 host/node pairing + capability handshake

适用场景：

- desktop/browser host
- remote integration host
- runtime attach points

需要让 operator 看见：

- 谁能执行
- 挂在哪台 host
- 缺什么前置条件
- 当前是否 ready

#### 3.2.2 integration doctor

每个安装项不只要“已安装”，还要能回答：

- 配置是否完整
- 网络是否可达
- 登录/鉴权是否有效
- 示例运行是否通过
- 最近失败原因是什么

#### 3.2.3 error taxonomy + drilldown

必须有稳定的错误类别，而不是只回一段模糊字符串。

至少要区分：

- config invalid
- auth missing
- auth expired
- host unavailable
- dependency missing
- capability denied
- approval pending
- upstream timeout
- runtime exception

#### 3.2.4 install/update/rollback lifecycle

当前 install 已有主链，但 lifecycle 还不完整。

`V5` 要补：

- update
- rollback
- version/manifest compare
- migration note
- post-install doctor

### 3.3 明确不借鉴的 5 件事

- 不引入第二套运行内核或外部 workflow DSL
- 不重新把能力语义拆回第四套对象
- 不默认劫持用户真实浏览器 profile
- 不默认扩大 host/browser/network 权限边界
- 不把原始配置编辑器伪装成完整集成产品面

---

## 4. 多 Agent Workflow 的正式口径

这个问题必须在 `V5` 中写死，否则后面还会不断绕偏。

### 4.1 不是“每个 agent 一条 workflow”

默认模式不应该是：

- 销售 agent 一条 flow
- 研究 agent 一条 flow
- 写手 agent 一条 flow

然后彼此并排各跑各的。

这会把产品层重新打碎成很多“agent 私有脚本”。

### 4.2 正确口径是“一个 WorkflowRun 跨多个 agent/角色”

顶层产品对象应该是：

- 一个 `WorkflowTemplate`
- materialize 成一个 `WorkflowRun`
- `WorkflowRun` 下面包含多个 step
- 每个 step 根据候选角色、能力、策略、host 和当前可用 actor 做路由

也就是说：

> workflow 是 run-centric，不是 agent-centric。

### 4.3 每个 step 决定“由谁来做”，不是每个 agent 先自带一条 flow

step 级最少应声明：

- `owner_role_candidates`
- `required_capability_ids`
- `execution_mode`
- 必要时声明 `host/session/policy` 约束

再由运行时决定：

- 这一步给哪个 agent
- 是总控核做控制步，还是 specialist 做叶子步
- 当前是否需要补安装、补审批、补 host attach

### 4.4 `execution-core` 在 workflow 里的定位

`execution-core` 默认负责：

- 进入 flow
- 编排
- 分派
- 监督
- 汇总
- 复核风险

默认不负责：

- 大量叶子执行
- 长串浏览器/桌面操作
- 每一步外部集成细操作

只有在以下情况才允许 fallback：

- 当前团队没有合适 specialist
- 动作极短链且低风险
- 只是临时兜底而不是常态

### 4.5 允许存在 agent-local micro-workflow，但它不是顶层产品面

可以有：

- 某个研究岗内部的采集-整理-汇报微流程
- 某个桌面执行岗内部的观察-点击-输入微流程

但这类东西应被视为 leaf 内部实现，不应该替代顶层 `WorkflowRun`。

### 4.6 最终产品规则

- 一个业务流程模板可以同时调用多个 agent
- 一个 agent 可以参与多个 workflow run
- 不是每个 agent 都必须绑定一个专属 workflow
- 只有在确实存在稳定、可复用、角色内聚的叶子流程时，才为该 agent 维护 micro-template

---

## 5. `V5` 需要新增或升级的对象

以下对象不是要求一次全量新建，而是要求在 `state/query/product` 层形成正式边界。

### 5.1 浏览器执行表面对象

- `BrowserProfileRecord`
- `BrowserSessionRecord`
- `BrowserExecutionPolicy`
- `BrowserLoginCheckpoint`
- `BrowserDoctorReport`

### 5.2 执行治理对象

- `ExecutionStrategyRecord`
- `HostPolicyRecord`
- `AgentExecutionPolicyRecord`
- `ApprovalForwardRecord`
- `CapabilityHandshakeRecord`

### 5.3 扩展接入对象

- `IntegrationManifestRecord`
- `IntegrationInstallRecord`
- `IntegrationConfigSchemaRecord`
- `IntegrationLifecycleEvent`
- `IntegrationDoctorReport`
- `IntegrationExampleRunRecord`

### 5.4 Workflow 运行壳对象

- `WorkflowCheckpointRecord`
- `WorkflowReplayRecord`
- `WorkflowOperatorEvent`
- `WorkflowRunDiagnosis`
- `WorkflowStepExecutionRecord`

### 5.5 统一错误口径

- `ExecutionErrorCode`
- `ExecutionErrorDetail`
- `IntegrationErrorDetail`

要求：

- 错误代码可被前端直接翻译与分组
- 错误详情能回链到 host、config、approval、upstream、evidence

---

## 6. `V5` 分期实施

`V5` 不应作为一个巨型模糊阶段推进，建议拆成 4 个连续批次。

### 6.1 `V5-A` 浏览器产品面

目标：

- 把浏览器从 capability/tool 提升为正式产品表面

本批最小范围：

- 新增浏览器 profile 列表与 attach/managed 模式
- 新增浏览器 session 读面与 ready 状态
- 新增登录状态/接管状态/doctor 结果
- 新增 host/sandbox 模式展示
- 让 workflow preview 能声明浏览器前置条件

优先落点：

- 后端：`capabilities/`、`environments/`、`app/routers/`
- 前端：`/capability-market`、`/workflow-templates`、`/runtime-center`

验收标准：

- operator 能看见当前有哪些浏览器执行面
- 能区分“未安装 / 已安装未就绪 / 已就绪 / 登录缺失 / host 不可达”
- workflow 在浏览器未 ready 时不会假装可启动

### 6.2 `V5-B` 执行策略治理面

目标：

- 让治理不只体现在 risk level，而是能落成操作层的执行策略面

本批最小范围：

- per-agent allowlist product view
- per-host policy product view
- approval pending 队列和 forwarding
- capability/host handshake readiness
- launch/install/update 时的策略继承与阻断说明

优先落点：

- 后端：`kernel/`、`capabilities/`、`state/`
- 前端：`Runtime Center`、`Agent Workbench`

验收标准：

- operator 能解释为什么某个 agent 当前不能执行某能力
- 审批请求能从 chat/workflow/install 统一转进 Runtime Center
- host/policy/approval 阻断都能落稳定错误码

### 6.3 `V5-C` 扩展契约与生命周期

目标：

- 把当前 `Skills / Integrations / MCP` 的安装配置体验升级成 manifest/schema/lifecycle 驱动

本批最小范围：

- `IntegrationManifest` 统一描述安装项
- schema 驱动配置 UI
- install/update/enable/disable/rollback lifecycle
- doctor/example run contract
- 安装后自动回写 capability exposure 与 ready 状态

优先落点：

- 后端：`capabilities/`、`compatibility/`、`app/routers/capability_market.py`
- 前端：`/capability-market`

验收标准：

- 新安装项不需要为每个配置面手写表单
- install/update/rollback 都有正式事件和结果面
- operator 能直接从产品页发 doctor/example run

### 6.4 `V5-D` Workflow 运行壳与 Operator Diagnose

目标：

- 把现有 workflow 模板中心升级成更强的运行壳和诊断面

本批最小范围：

- step execution timeline
- checkpoint/resume/replay
- workflow diagnosis drawer
- blocked reason taxonomy
- evidence/source/drilldown
- cross-page trace deep link

优先落点：

- 后端：`workflows/service.py`、workflow query surface、runtime query surfaces
- 前端：`/workflow-templates`、`/runtime-center`

验收标准：

- 任一 run 都能回答“卡在哪一步、为什么、由谁卡住、缺什么”
- restart 后 workflow 可继续从 checkpoint 恢复
- operator 不需要翻日志才能定位主阻断

---

## 7. 与当前仓库的具体映射

`V5` 不是绿地开发，以下模块应优先承接：

### 7.1 当前可直接扩展的后端锚点

- `src/copaw/app/routers/capability_market.py`
- `src/copaw/workflows/service.py`
- `src/copaw/capabilities/*`
- `src/copaw/environments/*`
- `src/copaw/kernel/*`
- `src/copaw/state/*`

### 7.2 当前可直接扩展的前端锚点

- `console/src/pages/CapabilityMarket/index.tsx`
- `console/src/pages/WorkflowTemplates/index.tsx`
- `console/src/pages/AgentWorkbench/index.tsx`
- `console/src/utils/workflowInstallFlow.ts`
- Runtime Center 相关页面与 query hooks

### 7.3 当前必须避免的误方向

- 不要再造一个“浏览器页面专属 store”
- 不要为 workflow diagnose 再造平行 run store
- 不要把 integration config 写回零散本地文件并绕过治理
- 不要让 workflow/product 页重新依赖前端拼装假状态

---

## 8. 验收矩阵

`V5` 完成时，至少要同时满足以下结果：

### 8.1 浏览器面

- 有 profile/session/doctor 可见面
- 有 attach/managed 策略
- 有 ready/not-ready 的稳定判定

### 8.2 治理面

- agent/host/policy/approval 都能被解释
- chat/workflow/install 的审批入口统一
- 不新增平行审批逻辑

### 8.3 扩展面

- manifest/schema/lifecycle 已成正式 contract
- install/update/rollback/doctor/example run 可产品化执行
- `Skills / Integrations / MCP` 继续只是产品分类，不再扩散内部语义

### 8.4 Workflow 面

- 单个 run 可跨多个 agent 执行
- step-level route/blocker/evidence 可见
- checkpoint/resume/replay 稳定

### 8.5 Operator 面

- 出错时能明确知道卡点、原因、依赖、host、审批状态
- 不需要依赖后端日志才能完成一线排障

### 8.6 删旧要求

- 新功能不回写旧 manager 私有状态
- 不新增新的 compat 扩散点
- 兼容逻辑必须登记删除条件

---

## 9. 一句话结论

`V5` 的本质不是“再补几个工具动作”，而是：

> 在已经完成 `V4` 的统一内核、统一能力、统一状态、统一证据基线上，把浏览器、治理、扩展接入、workflow 运行壳和 operator 诊断真正做成成熟产品表面。

同时，`Workflow` 的正式口径应固定为：

> 顶层是一个 `WorkflowRun` 跨多个 step 和多个 agent 的运行壳；agent 只是在 step 级被路由参与，不是默认“一人一条 workflow”。
