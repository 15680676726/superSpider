# n8n SOP Adapter 与 Workflow Hub 升级说明

`2026-03-26` superseded note:

- 目标架构已不再保留 `n8n` 或 `Workflow Hub`
- 本文件只作为一份“曾经落地过什么”的历史账本保留，不再代表当前目标方向
- 当前正式替代方案见：
  - `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
  - `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`

本文件用于登记本轮 `n8n` 升级已经落地的对象、后端路由、前端产品面与兼容删除条件。

它不替代：

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `TASK_STATUS.md`

如果与上述文档冲突，以上述文档为准；本文件负责记录这次专项升级的具体落地形态。

---

## 1. 本轮已完成什么

本轮已经完成 4 件事：

1. 把 `n8n` 的正式落位从 `RoutineService` 兼容分支提升为 `SOP Adapter`。
2. 在 `Capability Market` 里落地 `工作流` 产品入口，并放到 `精选中心` 后面。
3. 打通 `n8n -> CoPaw routine -> WorkflowRun / Evidence / AgentReport` 回流闭环。
4. 让 `CapabilityDiscoveryService` / `system:discover_capabilities` 能返回 `sop_templates`，供主脑匹配固定 SOP 模板。

本轮明确没有做，也不应做：

- 让 `n8n` 接管 browser / desktop UI 主执行链
- 让 `n8n` 成为第二执行中心或第二真相源
- 无治理地直接运行社区 workflow JSON
- 在行业 bootstrap 里无 operator 确认地自动创建 workflow binding

最后一条不是漏做，而是边界要求：workflow binding 必须显式声明行业实例、`owner_agent_id`、credential/webhook 和 doctor 结果，不能悄悄自动安装。

---

## 2. 正式边界

`n8n` 在 CoPaw 中只承担：

- 固定 SOP
- schedule / webhook / API 串联
- 固定条件分支
- 需要时回调 CoPaw 已有 routine

`n8n` 不承担：

- browser / desktop UI 执行主链
- 独立 workflow/routine 真相
- 独立 evidence / run history
- 主脑级跨执行位判断
- 风险治理与审批主链

CoPaw 继续承担：

- `WorkflowRunRecord`
- `ExecutionRoutineRecord`
- `RoutineRunRecord`
- `EvidenceRecord`
- `AgentReportRecord`
- `ReportRecord`

---

## 3. 已落地对象

当前统一 `state` 已正式落地：

- `SopAdapterTemplateRecord`
  - 固定 SOP 模板目录对象
  - 承接内置模板、社区导入模板、企业私有模板
- `SopAdapterBindingRecord`
  - 模板安装到具体行业实例 / workflow / owner agent 后的正式绑定对象

当前实际关键字段包括：

- `SopAdapterTemplateRecord`
  - `template_id`
  - `adapter_kind`
  - `name`
  - `summary`
  - `description`
  - `status`
  - `version`
  - `source_kind / source_ref / source_url`
  - `catalog_source_id / catalog_source_label`
  - `catalog_category_keys / catalog_category_labels`
  - `remote_template_ref`
  - `last_synced_at`
  - `owner_role_id / suggested_role_ids / allowed_role_ids`
  - `industry_tags / capability_tags`
  - `required_capability_ids / required_credential_keys`
  - `recommended_workflow_template_ids`
  - `risk_baseline`
  - `callback_contract / input_schema / output_schema`
  - `evidence_expectations / doctor_config / example_payload`
  - `governance_notes / metadata`
- `SopAdapterBindingRecord`
  - `binding_id`
  - `template_id`
  - `adapter_kind`
  - `binding_name`
  - `status`
  - `owner_scope / owner_agent_id`
  - `industry_instance_id / workflow_template_id`
  - `remote_workflow_ref`
  - `webhook_url / credential_ref`
  - `callback_mode / callback_endpoint`
  - `input_mapping / output_mapping`
  - `timeout_policy / retry_policy`
  - `risk_baseline`
  - `doctor_status / last_verified_at`
  - `metadata`

本轮没有新增第二套执行历史对象。执行真相继续复用：

- `WorkflowRunRecord`
- `ExecutionRoutineRecord`
- `RoutineRunRecord`
- `EvidenceRecord`
- `AgentReportRecord`
- `ReportRecord`

---

## 4. 已落地后端

当前正式服务：

- `SopAdapterService`
  - 内置 `n8n` 模板
  - 模板列表 / 搜索 / 导入 preview / 导入
  - binding 创建 / 更新 / 列表 / 详情
  - doctor
  - trigger
  - `n8n` callback
  - `WorkflowRun / Evidence / AgentReport` 回流

当前正式路由：

- `GET /api/sop-adapters/templates`
- `GET /api/sop-adapters/templates/{template_id}`
- `POST /api/sop-adapters/templates/import-preview`
- `POST /api/sop-adapters/templates/import`
- `POST /api/sop-adapters/templates/sync`
- `GET /api/sop-adapters/bindings`
- `POST /api/sop-adapters/bindings`
- `GET /api/sop-adapters/bindings/{binding_id}`
- `PUT /api/sop-adapters/bindings/{binding_id}`
- `POST /api/sop-adapters/bindings/{binding_id}/doctor`
- `POST /api/sop-adapters/bindings/{binding_id}/trigger`
- `POST /api/sop-callbacks/n8n/{binding_id}`

### 4.1 社区目录网络与镜像/代理

`n8n-official` 来源默认实时拉取 `api.n8n.io` 的社区模板目录；当远端不可达时会回退到本地缓存（若没有缓存则会报错）。

企业内网常见的 2 种落地方式：

1. 允许后端出网访问 `https://api.n8n.io`（最简单）。
2. 配置代理或内部镜像：把后端请求转到可达的代理/镜像地址。

当前已支持的环境变量配置（可选）：

- `COPAW_N8N_TEMPLATE_CATALOG_BASE_URL`：社区目录镜像 base URL，默认 `https://api.n8n.io`
- `COPAW_N8N_TEMPLATE_CATALOG_PROXY`：显式 HTTP 代理（如 `http://127.0.0.1:7890`）。未设置时仍会遵循系统 `HTTP(S)_PROXY`
- `COPAW_N8N_TEMPLATE_CATALOG_TIMEOUT_MS`：请求超时，默认 `15000`

### 4.2 定时同步（cron，可选）

当远端偶发不稳定或企业环境需要“先落库再浏览”时，可以启用定时同步任务把官方目录周期性缓存到本地。

开启方式：设置环境变量 `COPAW_N8N_TEMPLATE_CATALOG_SYNC_CRON`（例如 `0 */6 * * *` 每 6 小时同步一次）。

同步任务会创建/更新一个固定 job（默认 id：`_n8n_template_catalog_sync`），通过 `system:sync_sop_adapter_templates` 拉取并写入本地缓存。

可选参数：

- `COPAW_N8N_TEMPLATE_CATALOG_SYNC_TIMEZONE`：默认 `UTC`
- `COPAW_N8N_TEMPLATE_CATALOG_SYNC_PAGE_SIZE`：默认 `100`（上限 100）
- `COPAW_N8N_TEMPLATE_CATALOG_SYNC_PAGES`：默认 `3`（一次同步多少页）
- `COPAW_N8N_TEMPLATE_CATALOG_SYNC_SOURCE_ID`：默认 `n8n-official`

当前 discovery 接线：

- `CapabilityDiscoveryService.discover()` 已返回 `sop_templates`
- `system:discover_capabilities` 已可把 `sop_templates` 暴露给主脑

---

## 5. 已落地前端

当前 canonical 产品面是：

- `Capability Market -> 精选中心 -> 工作流`
- 侧边栏入口：`运行 -> 模板与扩展 -> 社区工作流（n8n）`（等价于 `/capability-market?tab=workflows`）

当前页面规则：

- `工作流` 页签固定放在 `精选中心` 后面
- 工作流卡片复用精选中心卡片样式和浏览心智
- 页面直接消费真实 `sop-adapters` API，不再使用旧 workflow 模板假数据入口
- 支持按来源 / 分类 / 关键词 / 分页浏览社区目录，并可一键 `sync` 缓存当前页
- 支持搜索模板、打开详情、导入社区 workflow、保存 binding、执行 doctor、执行示例 trigger

当前绑定规则：

- operator 必须先选行业实例
- 再为每张工作流卡片显式选择对应 `owner_agent_id`
- 前端不允许自己猜 owner
- 没有选行业实例或没有选 agent 时，只允许看详情，不允许进入正式绑定/执行入口

`doctor` 的产品口径固定为：

- 系统内置体检
- 不需要额外安装 doctor 组件
- 未通过体检的 binding 可以保存为草稿，但不能进入正式自动匹配和自动调度

---

## 6. 主脑如何匹配

主脑不直接匹配裸 `n8n` workflow JSON，而是匹配可治理模板。

当前匹配入口：

- `CapabilityDiscoveryService`
- `system:discover_capabilities`

当前匹配结果新增：

- `sop_templates`

主脑评估固定 SOP 时至少看：

- 是否低判断、低变化
- 是否 API / webhook / schedule first
- 是否已重复出现
- 是否已有稳定 credential
- 是否需要 callback 到已有 routine
- 风险是否适合固化
- 结果是否要进入正式报告面

主脑输出的是治理决策，不是私有执行结果：

- 保持灵活执行
- 选定某个 `sop template`
- 要求创建某个 `binding`
- 指定该 binding 绑定到哪个 `owner_agent_id`
- 指定是否回调既有 `routine`

---

## 7. 社区 Workflow 导入规则

允许导入来源：

- `n8n` 官方模板库
- allowlisted 社区模板源
- 企业私有模板库

不允许：

- 直接把未知来源 JSON 当正式 workflow 运行

最小导入流程：

1. 抓取模板元数据与原始 workflow 定义。
2. 归一化为 `SopAdapterTemplateRecord`。
3. 补齐 CoPaw 治理字段。
4. 在 `Capability Market -> 工作流` 中创建 binding。
5. 配置行业实例、`owner_agent_id`、credential/webhook。
6. 执行 doctor。
7. 再进入正式 trigger / callback / 回流链路。

原因是社区 workflow 默认不具备：

- 统一 credential contract
- 统一 callback contract
- 统一 evidence contract
- 统一 risk contract
- 统一 owner-agent assignment 语义

---

## 8. `n8n -> CoPaw -> n8n` 回流闭环

当 `n8n` workflow 需要 CoPaw 执行 UI 操作时：

1. `n8n` 调用 `POST /api/sop-callbacks/n8n/{binding_id}`。
2. callback payload 指向 `workflow_run_id / routine_id / input_payload / owner_agent_id`。
3. CoPaw 走正式 routine 主链执行。
4. 结果回写：
   - `RoutineRunRecord`
   - `EvidenceRecord`
   - `WorkflowRunRecord`
   - 必要时 `AgentReportRecord`
5. callback response 再把结构化结果返回给 `n8n` 继续后续节点。

失败、超时、审批、异常升级继续留在 CoPaw 主链，不交给 `n8n` 私下处理。

---

## 9. 与兼容层的关系

`RoutineService.engine_kind="n8n-sop"` 曾经只是一个受控待删兼容位，用来在迁移期承接 webhook trigger、timeout 和 response normalize。它从来都不是正式产品链路。

该兼容桥已于 `2026-03-21` 物理删除，现行正式链路是：

1. 主脑 / 行业 compile 产出 `sop_binding_id`
2. 运行时经 `system:trigger_sop_binding`
3. `SopAdapterService.trigger_binding(...)` 触发远端 workflow
4. 结果统一回写 `WorkflowRun / Evidence / AgentReport / Report`

删除完成情况：

- 已停止新增 `n8n-sop` routine 定义
- 既有固定 SOP 已迁移到 `SopAdapterTemplateRecord / SopAdapterBindingRecord`
- 业务与主脑不再直接引用 `engine_kind="n8n-sop"`
- `RoutineService` 内部 compat engine 分支与 `RoutineN8nService` 已删除
- legacy persisted `n8n-sop` routine 仅保留迁移错误提示，不再进入正式执行链

---

## 10. 验证

本轮已完成的关键验证包括：

- `SOP Adapter` API 回归测试
- `state` migration / repository 回归测试
- `system:discover_capabilities` 回归测试
- `console build`

专项验收标准是：

- 模板可以导入
- binding 可以保存和更新
- doctor 可以阻断缺失配置
- trigger 会写 evidence
- callback 会回写 `WorkflowRun / Evidence / AgentReport`
- 前端工作流入口必须要求显式选 agent

---

## 11. 一句话总结

`n8n` 在 CoPaw 中的正式形态已经收口为：

> 一个可导入、可绑定、可体检、可触发、可回流的固定 SOP 编排侧车；真正的 UI 执行仍由 CoPaw routine 主链负责。
