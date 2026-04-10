# Buddy Onboarding Collaboration Contract Cutover Design

日期：`2026-04-10`

作者：Codex

---

## 1. 问题定义

当前 Buddy 建档第二步仍然是“AI 连续追问 -> 收窄方向 -> 生成候选主方向”。

这条链在代码里的真实形态是：

- 前端第二步页面：[`console/src/pages/BuddyOnboarding/index.tsx`](/D:/word/copaw/console/src/pages/BuddyOnboarding/index.tsx)
- 前门路由：
  - [`src/copaw/app/routers/buddy_routes.py`](/D:/word/copaw/src/copaw/app/routers/buddy_routes.py)
  - `POST /buddy/onboarding/clarify`
  - `POST /buddy/onboarding/clarify/start`
- 运行时 session 真相：
  - [`src/copaw/state/repositories_buddy.py`](/D:/word/copaw/src/copaw/state/repositories_buddy.py)
  - `BuddyOnboardingSessionRecord.question_count / tightened / next_question / transcript`
- AI 推理器：
  - [`src/copaw/kernel/buddy_onboarding_reasoner.py`](/D:/word/copaw/src/copaw/kernel/buddy_onboarding_reasoner.py)
  - 当前强制输出 `next_question / candidate_directions / recommended_direction / final_goal / why_it_matters / backlog_items`

这套设计的问题不在于“有 AI”，而在于第二步收集的真相偏了：

- 它在继续深挖抽象目标
- 但当前系统真正需要的，是“超级伙伴应该怎么为用户工作”的合作契约
- 结果会让用户体感更像被采访，而不是在定义一个长期自治伙伴

---

## 2. 目标

本次 cutover 的目标不是推翻 Buddy 后续主链，而是把第二步从“AI 追问目标”改成“合作契约定义”，并确保后续 runtime 真会持续读取它。

本次设计必须满足：

1. 不破坏现有 Buddy 后续正式主链
   - `HumanProfile -> GrowthTarget -> BuddyDomainCapabilityRecord -> IndustryInstance`
2. 不把合作契约硬塞进 `final_goal` 或 `why_it_matters`
3. 不新增第二套一级对象真相源
4. 建档完成后，主脑 persona、execution-core identity、治理默认值、汇报偏好可以真实读取该契约
5. 因系统尚未上线，本次采用 hard-cut，不保留旧 clarify 语义兼容壳

---

## 3. 非目标

本次不做以下事情：

- 不把主脑改成执行器
- 不重做 Buddy 全部成长系统
- 不重做 `GrowthTarget / BuddyDomainCapability / IndustryInstance` 对象
- 不新增一个 repo 级“大合作契约引擎”
- 不把第二步继续做成半 AI 半表单的混合采访模式

---

## 4. 核心判断

### 4.1 哪些东西必须保持不变

后续系统已经真实依赖以下正式对象：

- [`src/copaw/state/models_buddy.py`](/D:/word/copaw/src/copaw/state/models_buddy.py)
  - `HumanProfile`
  - `GrowthTarget`
  - `CompanionRelationship`
  - `BuddyDomainCapabilityRecord`
- [`src/copaw/kernel/buddy_onboarding_service.py`](/D:/word/copaw/src/copaw/kernel/buddy_onboarding_service.py)
  - `_build_buddy_industry_profile(...)`
  - `_ensure_growth_scaffold(...)`
- `IndustryInstance.profile_payload`
- `IndustryInstance.execution_core_identity_payload`

所以后续正式目标链必须继续保留：

- `primary_direction`
- `final_goal`
- `why_it_matters`
- `backlog_items`

### 4.2 哪些东西必须改

第二步当前的这些字段和语义不再适合保留：

- `question_count`
- `tightened`
- `next_question`
- `transcript`
- `/buddy/onboarding/clarify*`

它们会把“合作契约定义”继续绑死成“AI 问答澄清”，这是后续最容易越改越乱的根源。

### 4.3 合作契约放在哪里最稳

合作契约的长期归宿应当是：

- `CompanionRelationship`

原因：

- `HumanProfile` 负责人的底稿，不适合放系统合作方式
- `GrowthTarget` 负责方向和目标，不适合混入角色/权限/汇报偏好
- `BuddyOnboardingSessionRecord` 只是过渡态，不是长期运行真相
- `CompanionRelationship` 本来就表示稳定的伙伴关系偏好，是最合适的正式对象边界

结论：

- 合作契约长期写入 `CompanionRelationship`
- onboarding 第二步只保存 contract draft
- confirm 后再写入正式关系真相

---

## 5. 设计方案

### 5.1 第二步改成固定合作契约表单

第二步不再使用 AI 连续追问。

前端改为固定结构化输入，建议字段如下：

1. `service_intent`
   - 文案：`你希望我为你做什么？`
   - 类型：长文本
   - 作用：这是真正的主问题

2. `collaboration_role`
   - 文案：`你希望我主要扮演什么角色？`
   - 推荐选项：
     - `orchestrator`：总指挥 / 统筹推进
     - `executor`：执行推进者
     - `advisor`：顾问
     - `companion`：陪跑伙伴

3. `autonomy_level`
   - 文案：`我可以主动到什么程度？`
   - 推荐选项：
     - `reactive`：只在你明确提出时推进
     - `proactive`：可以主动提醒、规划、推动
     - `low-risk-autonomous`：低风险事项可自动推进

4. `confirm_boundaries`
   - 文案：`哪些事情必须先经过你确认？`
   - 多选，稳定枚举值：
     - `external-send`
     - `spend-money`
     - `destructive-change`
     - `high-risk-action`

5. `report_style`
   - 文案：`你希望我怎么汇报？`
   - 推荐选项：
     - `chat-first`
     - `result-first`
     - `daily-summary`
     - `milestone-summary`

6. `collaboration_notes`
   - 文案：`还有什么你希望我记住的合作方式？`
   - 类型：可选长文本

### 5.2 第三步改成“确认主方向 + 确认合作方式”

第三步不再只确认“候选大方向”。

第三步确认页应同时展示：

- 推荐主方向 `recommended_direction`
- 归纳后的最终目标 `final_goal`
- 为什么现在值得做 `why_it_matters`
- 第一批 backlog items
- 合作契约摘要
  - 你希望我做什么
  - 我是什么角色
  - 主动级别
  - 默认汇报方式
  - 默认确认边界

这样用户确认的就不是一条抽象方向，而是一个完整的“长期合作初始化包”。

---

## 6. 真相模型调整

### 6.1 `BuddyOnboardingSessionRecord` hard-cut

当前对象：[`src/copaw/state/repositories_buddy.py`](/D:/word/copaw/src/copaw/state/repositories_buddy.py)

本次应 hard-cut 删除或退役以下字段：

- `question_count`
- `tightened`
- `next_question`
- `transcript`

新增 contract-draft 字段：

- `service_intent: str`
- `collaboration_role: str`
- `autonomy_level: str`
- `confirm_boundaries: list[str]`
- `report_style: str`
- `collaboration_notes: str`

保留以下下游仍需要的字段：

- `candidate_directions`
- `recommended_direction`
- `selected_direction`
- `draft_direction`
- `draft_final_goal`
- `draft_why_it_matters`
- `draft_backlog_items`

### 6.2 `CompanionRelationship` 新增正式字段

当前对象：[`src/copaw/state/models_buddy.py`](/D:/word/copaw/src/copaw/state/models_buddy.py)

新增正式字段：

- `service_intent: str = ""`
- `collaboration_role: str = "orchestrator"`
- `autonomy_level: str = "proactive"`
- `confirm_boundaries: list[str] = []`
- `report_style: str = "result-first"`
- `collaboration_notes: str = ""`

说明：

- 这里不用 `metadata`，改用显式字段
- 原因是这些偏好是稳定、长期、会被多个运行时表面读取的正式真相
- 若塞进 `metadata`，后续会演变成 prompt 私货和读面脏解析

### 6.3 `GrowthTarget` 保持职责纯净

`GrowthTarget` 不新增合作契约字段。

继续只承载：

- `primary_direction`
- `final_goal`
- `why_it_matters`
- `current_cycle_label`

### 6.4 `IndustryInstance.execution_core_identity_payload` 扩充

当前下游已经会读取：

- [`src/copaw/kernel/query_execution_prompt.py`](/D:/word/copaw/src/copaw/kernel/query_execution_prompt.py)
  - `identity_label`
  - `industry_summary`
  - `operating_mode`
  - `thinking_axes`
  - `delegation_policy`
  - `direct_execution_policy`

因此确认方向时，Buddy onboarding 应把合作契约投影为：

- `identity_label`
- `operating_mode`
- `operator_service_intent`
- `collaboration_role`
- `autonomy_level`
- `report_style`
- `confirm_boundaries`
- `delegation_policy`
- `direct_execution_policy`

这是运行时读取面，不是第二套真相源。
真正正式真相仍然是 `CompanionRelationship + GrowthTarget`。

---

## 7. AI 编译边界

### 7.1 AI 还保留，但角色改变

AI 不再是“采访者”，改成“编译器”。

输入：

- `HumanProfile`
- 第二步固定合作契约表单

输出：

- `candidate_directions`
- `recommended_direction`
- `final_goal`
- `why_it_matters`
- `backlog_items`

### 7.2 `BuddyOnboardingReasoner` hard-cut

当前文件：[`src/copaw/kernel/buddy_onboarding_reasoner.py`](/D:/word/copaw/src/copaw/kernel/buddy_onboarding_reasoner.py)

需要 hard-cut 删除：

- `next_question` 强约束
- `finished=false 时必须继续提问`
- 以 `question_count / tightened / transcript` 为核心输入的问答推理模式

新的 reasoner 输入应改成：

- `profile`
- `collaboration_contract`

新的 reasoner 输出应改成：

- `candidate_directions`
- `recommended_direction`
- `final_goal`
- `why_it_matters`
- `backlog_items`

不再输出：

- `next_question`

---

## 8. 前后端切面调整

### 8.1 API hard-cut

当前路由：[`src/copaw/app/routers/buddy_routes.py`](/D:/word/copaw/src/copaw/app/routers/buddy_routes.py)

删除：

- `POST /buddy/onboarding/clarify`
- `POST /buddy/onboarding/clarify/start`

新增：

- `POST /buddy/onboarding/contract`
- `POST /buddy/onboarding/contract/start`

请求体改为：

- `session_id`
- `service_intent`
- `collaboration_role`
- `autonomy_level`
- `confirm_boundaries`
- `report_style`
- `collaboration_notes`

### 8.2 Buddy surface projection

`GET /buddy/surface` 无需新增顶级 `contract` 对象。

直接通过：

- `relationship`
- `onboarding`
- `execution_carrier`

三块投影即可。

其中：

- onboarding 阶段展示 draft contract
- confirmed 后 relationship 展示正式 contract

### 8.3 Buddy 页面步骤调整

前端页面：[`console/src/pages/BuddyOnboarding/index.tsx`](/D:/word/copaw/console/src/pages/BuddyOnboarding/index.tsx)

步骤改为：

1. `身份建档`
2. `合作方式`
3. `确认主方向`

删除所有“第 N / 9 问”“继续追问”“AI 正在深挖你的方向”的叙述。

---

## 9. 运行时读取链

为了保证“填了以后系统真的照做”，至少需要接上这几条读取链：

### 9.1 Buddy persona prompt

当前文件：[`src/copaw/kernel/buddy_persona_prompt.py`](/D:/word/copaw/src/copaw/kernel/buddy_persona_prompt.py)

新增读取：

- `relationship.service_intent`
- `relationship.collaboration_role`
- `relationship.autonomy_level`
- `relationship.report_style`
- `relationship.confirm_boundaries`
- `relationship.collaboration_notes`

作用：

- Buddy 对外表达方式不再只围绕“目标/当前任务”
- 还会围绕“我们怎样合作”

### 9.2 execution-core identity prompt

当前文件：[`src/copaw/kernel/query_execution_prompt.py`](/D:/word/copaw/src/copaw/kernel/query_execution_prompt.py)

继续从 `execution_core_identity_payload` 读取：

- `operating_mode`
- `delegation_policy`
- `direct_execution_policy`
- `report_style`
- `confirm_boundaries`

作用：

- 主脑在 runtime 中真实按合作契约执行
- 而不是只在建档时看过一次

### 9.3 Buddy surface / cockpit

当前文件：

- [`src/copaw/kernel/buddy_projection_service.py`](/D:/word/copaw/src/copaw/kernel/buddy_projection_service.py)
- [`src/copaw/kernel/buddy_runtime_focus.py`](/D:/word/copaw/src/copaw/kernel/buddy_runtime_focus.py)

作用：

- 让 UI 可见“当前合作模式”
- 避免前台看不到真实契约，只剩方向/任务

---

## 10. 删除纪律

因系统尚未上线，本次采用 hard-cut，不保留旧 clarify 兼容壳。

本次应删：

- `clarify` 前端步骤文案
- `clarify` API 路由
- `BuddyOnboardingSessionRecord.question_count / tightened / next_question / transcript`
- reasoner 中的“继续提问”合同

本次不删：

- `candidate_directions`
- `recommended_direction`
- `GrowthTarget`
- `BuddyDomainCapabilityRecord`
- `confirm-direction` 主链

---

## 11. 为什么这条路最稳

这条方案稳，是因为它遵守了 4 条边界：

1. 人的底稿归 `HumanProfile`
2. 合作偏好归 `CompanionRelationship`
3. 长期方向归 `GrowthTarget`
4. 运行时投影归 `execution_core_identity_payload`

这样以后再改：

- 第二步字段
- 主脑风格
- 主动等级
- 汇报偏好
- 默认确认边界

都还能继续演进，不会和目标对象混成一团。

---

## 12. 文件改动范围

预期涉及文件：

- 前端
  - [`console/src/pages/BuddyOnboarding/index.tsx`](/D:/word/copaw/console/src/pages/BuddyOnboarding/index.tsx)
  - [`console/src/api/modules/buddy.ts`](/D:/word/copaw/console/src/api/modules/buddy.ts)
  - [`console/src/pages/BuddyOnboarding/index.test.tsx`](/D:/word/copaw/console/src/pages/BuddyOnboarding/index.test.tsx)

- 后端路由
  - [`src/copaw/app/routers/buddy_routes.py`](/D:/word/copaw/src/copaw/app/routers/buddy_routes.py)

- 状态模型 / 仓储
  - [`src/copaw/state/models_buddy.py`](/D:/word/copaw/src/copaw/state/models_buddy.py)
  - [`src/copaw/state/repositories_buddy.py`](/D:/word/copaw/src/copaw/state/repositories_buddy.py)
  - [`src/copaw/state/store.py`](/D:/word/copaw/src/copaw/state/store.py)

- onboarding 主链
  - [`src/copaw/kernel/buddy_onboarding_service.py`](/D:/word/copaw/src/copaw/kernel/buddy_onboarding_service.py)
  - [`src/copaw/kernel/buddy_onboarding_reasoner.py`](/D:/word/copaw/src/copaw/kernel/buddy_onboarding_reasoner.py)
  - [`src/copaw/kernel/buddy_projection_service.py`](/D:/word/copaw/src/copaw/kernel/buddy_projection_service.py)
  - [`src/copaw/kernel/buddy_persona_prompt.py`](/D:/word/copaw/src/copaw/kernel/buddy_persona_prompt.py)
  - [`src/copaw/kernel/query_execution_prompt.py`](/D:/word/copaw/src/copaw/kernel/query_execution_prompt.py)

---

## 13. 最终建议

本次应执行：

- hard-cut 第二步语义
- 第二步改为固定合作契约表单
- 合作契约正式落到 `CompanionRelationship`
- AI 退到“编译合作契约 -> 方向与 backlog”
- 后续通过 `execution_core_identity_payload + persona prompt` 持续读取

本次不应执行：

- 保留旧 clarify 语义
- 把合作契约塞进 `GrowthTarget`
- 只改页面不改运行时读取链
- 新增一个独立的大型合作契约对象体系

