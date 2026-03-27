# PHASEB_EXECUTION_PLAN.md

本文件用于把 [implementation_plan.md](/D:/word/copaw/implementation_plan.md) 中的 `Phase B 行业初始化 MVP` 细化为可执行施工清单。

它不是新的总设计文档，而是：

- 行业初始化 MVP 的正式执行计划
- 后续每轮开发时的进度同步板
- Phase B 期间兼容代码、临时承载位、删旧条件的统一约束文档

优先级说明：

1. [AGENTS.md](/D:/word/copaw/AGENTS.md)
2. [COPAW_CARRIER_UPGRADE_MASTERPLAN.md](/D:/word/copaw/COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
3. [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
4. [implementation_plan.md](/D:/word/copaw/implementation_plan.md)
5. 本文件 `PHASEB_EXECUTION_PLAN.md`

如果本文件与以上文档冲突，以上文档优先。

---

## 1. Phase B 目标

`Phase B` 的主题是：

> 把“行业输入 -> 初始团队 -> 初始 goals -> 首轮 dispatch -> Runtime Center 可见 -> 后续 schedule/日报起点”做成稳定 MVP。

本阶段追求的不是完整行业自治系统，而是一个可持续迭代的产品化起点。

### 1.1 本阶段主要目标

- 固化行业输入 schema
- 固化 `TeamBlueprint / RoleBlueprint` 的最小产品模型
- 固化行业初始化到 goals/plan steps/compiler context 的编译路径
- 让行业实例在 Runtime Center 中成为可见的一等对象集合
- 提供最小可用启动入口，而不是只剩后端 API
- 补齐至少一条默认 schedule 与一版 evidence-driven 日报起点

### 1.2 本阶段非目标

本阶段不追求以下事项：

- 不做完整行业知识库治理系统
- 不做完整 capability market
- 不做复杂多团队/多层组织编排
- 不做深度跨进程环境恢复
- 不把 Manager/Researcher 做成新的平行运行主链

---

## 2. 当前基线

截至 `2026-03-11`，Phase B 不是从零开始。

已存在基线：

- 已有行业 bootstrap API：
  - [industry.py](/D:/word/copaw/src/copaw/app/routers/industry.py)
- 已有行业 bootstrap service：
  - [service.py](/D:/word/copaw/src/copaw/industry/service.py)
- 已可生成 `Industry Manager / Industry Researcher`
- 已可生成对应 goals 与 goal overrides
- 已可进入现有 `GoalService -> SemanticCompiler -> KernelDispatcher -> Runtime Center` 主链
- Runtime Center 已能显示 override-only agent：
  - [agent_profile_service.py](/D:/word/copaw/src/copaw/kernel/agent_profile_service.py)
- 已有基础测试：
  - [test_industry_api.py](/D:/word/copaw/tests/app/test_industry_api.py)

当前判断：

> Phase B 的核心工作不是“再造行业系统”，而是把现有行业 V1 稳定化、显式化、可见化，并补齐它的默认运行闭环。

---

## 3. 成功标准

Phase B 完成的判定标准：

- 用户可以输入行业画像并创建一个行业实例
- 系统可以稳定生成初始团队蓝图与角色蓝图
- 系统可以稳定生成初始 goals、plan steps、compiler context
- Runtime Center 可以直接看到该行业实例相关的 goal / task / agent / decision / evidence / schedule
- 至少有一条默认 schedule 能继续推进行业实例
- 至少有一版 evidence-driven 日报/状态摘要
- 没有新增平行真相源、平行内核、第四套能力语义
- 所有新增兼容代码和临时承载位都有明确删除条件

---

## 4. 开发与同步规则

Phase B 后续开发必须继续沿用当前仓库的“计划 -> 实装 -> 验收 -> 文档同步 -> 删旧准备”模式。

### 4.1 每完成一个 Task Group，至少同步 3 个地方

- [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
- [implementation_plan.md](/D:/word/copaw/implementation_plan.md)
- [DEPRECATION_LEDGER.md](/D:/word/copaw/DEPRECATION_LEDGER.md)

如果涉及对象模型或 API 边界变化，还必须同步：

- [DATA_MODEL_DRAFT.md](/D:/word/copaw/DATA_MODEL_DRAFT.md)
- [API_TRANSITION_MAP.md](/D:/word/copaw/API_TRANSITION_MAP.md)

### 4.2 每个 Task Group 都必须回答 4 个问题

1. 这次新增内容的单一真相源是什么
2. 是否经过统一 kernel
3. 是否引入了临时兼容承载位
4. 未来会删除或替换哪段旧逻辑

### 4.3 兼容与临时承载位规则

Phase B 允许极短期使用临时承载位，但必须显式标注：

- 为什么暂时这样做
- 替代目标对象是什么
- 删除条件是什么
- 删除预计落在哪个阶段

禁止事项：

- 不允许新增独立 industry JSON 真相源
- 不允许新增 industry manager 独立执行器
- 不允许新增独立 reporting store
- 不允许把静态日报冒充 evidence-driven 报告

---

## 5. 执行看板

状态枚举：

- `not_started`
- `in_progress`
- `completed`
- `blocked`

当前 Phase B 看板：

- `B1 行业输入对象稳定化`：`completed`
- `B2 团队蓝图/角色蓝图稳定化`：`completed`
- `B3 行业 goal seed 编译器拆分`：`completed`
- `B4 Runtime Center 行业 detail 可见化`：`completed`
- `B5 行业启动入口产品化`：`completed`
- `B6 默认 schedule 接入`：`completed`
- `B7 evidence-driven 日报起点`：`completed`
- `B8 角色授权与环境约束基础版`：`completed`
- `B9 最小前端工作台`：`completed`
- `B10 自动化测试矩阵`：`completed`
- `B11 文档同步与删旧准备`：`completed`
- `B12 MVP 验收`：`completed`

说明：

- `2026-03-11` 已完成 `B1` 到 `B12` 的当前 MVP 范围，并与 `PHASEA_PHASEB_PARALLEL_PLAN.md` 对齐完成最终收口
- 当前 Phase B 结论是“行业初始化 MVP 已正式落地”，而不是停留在“只有 bootstrap API”
- 后续与 Phase B 相关的工作应转入正式对象仓储、carrier 删除与更深真实世界覆盖，而不是重开本文件中的 MVP 待办

---

## 6. Task Group 细化

## 6.1 B1：行业输入对象稳定化

### 当前状态（2026-03-11）

- `completed`
- 已落地 `IndustryPreviewRequest -> IndustryProfile` 规范化路径
- 已把 `IndustryBootstrapRequest` 收敛为 `{ profile, draft, activation options }`，用于激活最终编辑后的行业草案
- 行业输入字段白名单、默认值与 list normalization 已集中到 `src/copaw/industry/models.py`

### 目标

- 把当前 bootstrap request 从“可用 payload”收敛为稳定行业输入模型

### 主要产出

- `IndustryProfile` 或等价正式对象
- 行业输入字段白名单
- 默认值、规范化、字段校验

### 推荐落点

- [models.py](/D:/word/copaw/src/copaw/industry/models.py)
- 必要时同步 [DATA_MODEL_DRAFT.md](/D:/word/copaw/DATA_MODEL_DRAFT.md)

### 验收标准

- 任意行业输入都能规范化
- 不再把随机业务字段散落写入 `compiler_context`

### 兼容与删旧说明

- `IndustryProfile` 已正式落地，但其持久化仍通过 `GoalOverrideRecord.compiler_context["industry_profile"]` 过渡承载
- 后续应在正式行业对象 read/write 模型落地后，移除对零散 `dict` carrier 的依赖

---

## 6.2 B2：团队蓝图与角色蓝图稳定化

### 当前状态（2026-03-11）

- `completed`
- 已落地 `IndustryRoleBlueprint / IndustryTeamBlueprint`
- Manager / Researcher 的默认能力范围、风险级别、环境约束与证据期望已进入正式蓝图对象

### 目标

- 把当前 manager/researcher 的生成逻辑升级为最小稳定产品模型

### 主要产出

- `TeamBlueprint`
- `RoleBlueprint`
- 角色默认能力范围
- 角色默认风险级别

### 推荐落点

- [models.py](/D:/word/copaw/src/copaw/industry/models.py)
- [service.py](/D:/word/copaw/src/copaw/industry/service.py)

### 验收标准

- 团队结构可重复生成
- Runtime Center 可以明确看见团队角色来源和职责摘要

### 兼容与删旧说明

- 当前 industry agent 可见性仍主要借助 `AgentProfileOverrideRecord`
- 蓝图对象已经正式化，但 Runtime Center 读面仍通过临时 carrier 投影；后续应收敛到一等团队/角色对象读面

---

## 6.3 B3：行业 goal seed 编译器拆分

### 当前状态（2026-03-11）

- `completed`
- 已新增 `src/copaw/industry/compiler.py`
- `IndustryBootstrapService` 已停止内嵌大段 seed/team/profile 构造逻辑，只保留 facade 组装职责

### 目标

- 把“行业 brief -> 初始 goals / plan steps / compiler context”的逻辑从 service 中拆成独立编译层

### 主要产出

- industry goal seed builder
- manager/researcher 各自的 seed 规则
- 稳定的 `goal_kind / plan_steps / compiler_context`

### 推荐落点

- 新增 `src/copaw/industry/compiler.py` 或同类模块
- 现有 [compiler.py](/D:/word/copaw/src/copaw/compiler/compiler.py) 继续只负责通用 task spec 编译

### 验收标准

- bootstrap service 不再承载大段 seed 规则
- seed 生成逻辑可单测

### 兼容与删旧说明

- `IndustryBootstrapService` 中旧的内联 seed 构造逻辑已完成删除
- 当前剩余兼容点不在编译器本身，而在 `GoalOverrideRecord.compiler_context` 与 `AgentProfileOverrideRecord` 这两个临时承载位

---

## 6.4 B4：Runtime Center 行业 detail 可见化

### 当前状态（2026-03-11）

- `completed`
- 已新增 `GET /api/industry/v1/instances`、`GET /api/industry/v1/instances/{instance_id}`、`GET /api/runtime-center/industry`、`GET /api/runtime-center/industry/{instance_id}`
- 行业 detail 现在会聚合 `goals / agents / schedules / tasks / decisions / evidence / patches / growth / proposals / reports`
- Goal detail 现在会显式暴露已关联的行业上下文，Runtime Center 与 Industry 页面都能直接 drill-down

### 目标

- 让行业实例在 Runtime Center 中不只是“两个 goal + 两个 agent”
- 至少能看见行业画像、团队蓝图、goal kind、初始计划来源

### 主要产出

- goal detail 增强字段
- agent detail 增强字段
- 行业实例来源与路由聚合

### 推荐落点

- [state_query.py](/D:/word/copaw/src/copaw/app/runtime_center/state_query.py)
- [runtime_center.py](/D:/word/copaw/src/copaw/app/routers/runtime_center.py)
- [service.py](/D:/word/copaw/src/copaw/goals/service.py)

### 验收标准

- Operator 打开 goal detail 就能知道它来自哪个行业、哪个角色、哪种引导目标

### 兼容与删旧说明

- 当前行业上下文主要挂在 `GoalOverrideRecord.compiler_context`
- 这是 Phase B 临时读面承载位，未来应迁移到一等行业/团队读模型

---

## 6.5 B5：行业启动入口产品化

### 当前状态（2026-03-11）

- `completed`
- 已新增 `console/src/pages/Industry/index.tsx`、`console/src/api/modules/industry.ts`
- 控制台已接入 `/industry` 路由与 `Industry Init` 侧栏入口
- operator 现在可以通过表单启动行业实例，并直接跳转 Runtime Center / Agent Workbench

### 目标

- 提供一个最小可操作入口，而不只是要求用户手动调用 API

### 主要产出

- 行业初始化表单或最小控制台入口
- 提交后跳转到对应 Runtime Center goal/agent 详情

### 推荐落点

- 现有 console / Runtime Center 前端模块
- 后端继续复用 [industry.py](/D:/word/copaw/src/copaw/app/routers/industry.py)

### 验收标准

- 普通 operator 不需要手工拼 JSON 就能启动一个行业实例

### 兼容与删旧说明

- 允许先做最小入口
- 禁止额外起一个独立行业控制台真相源

---

## 6.6 B6：默认 schedule 接入

### 当前状态（2026-03-11）

- `completed`
- `IndustryBootstrapService` 现在会生成默认 `IndustryScheduleSeed`
- schedule seed 通过既有 `StateBackedJobRepository` 与 `ScheduleRecord` 主链持久化，而不是行业模块自带调度器
- Runtime Center schedule detail 已可直接查看该默认节奏

### 目标

- 让行业实例不是一次性生成物，而是带最小持续节奏

### 主要产出

- 默认 schedule seed
- 至少一条“每日研究摘要”或“每日运营推进”默认节奏

### 推荐落点

- 行业 bootstrap service 只产出 schedule seed
- 真正 schedule 落地仍走现有 schedule/kernel 主链

### 验收标准

- 行业实例创建后可以看到至少一条默认 schedule
- 该 schedule 可以在 Runtime Center 中启动/暂停/恢复

### 兼容与删旧说明

- 禁止为行业模块单独造调度器
- 禁止把 schedule 仅作为前端文案保存

---

## 6.7 B7：evidence-driven 日报起点

### 当前状态（2026-03-11）

- `completed`
- 已落地 `IndustryReportSnapshot`，按 daily/weekly 聚合 `evidence / proposals / patches / growth / decisions`
- 行业 detail 与 Runtime Center industry detail 都会返回 evidence-driven 日报/周报摘要
- 报告结果可回溯到真实 task/evidence，而不是静态模板文案

### 目标

- 给 Phase B MVP 一版最小真实报告能力

### 主要产出

- 基于 `goal / task / evidence / growth` 的日报摘要
- 结果可追溯到真实 task/evidence

### 推荐落点

- Runtime Center query/service 层
- 前端只消费聚合结果

### 验收标准

- 日报不是静态模板
- 接口失败不能吞成“今天没数据”

### 兼容与删旧说明

- 当前若复用静态文案组件，必须显式标记为待删除
- Phase B 完成前至少移除“假日报”路径

---

## 6.8 B8：角色授权与环境约束基础版

### 当前状态（2026-03-11）

- `completed`
- 显式 `AgentProfileOverrideRecord.capabilities` allowlist 现在是行业角色授权的权威边界
- query execution prompt 已显式注入环境约束摘要与 mounted capability 预览
- Manager / Researcher 的基础环境约束与风险边界已写入角色蓝图

### 目标

- 为 Manager / Researcher 建立基础 capability allowlist 与默认环境约束

### 主要产出

- 角色默认 capability 范围
- 角色默认风险建议
- 环境约束摘要

### 推荐落点

- [agent_profile_service.py](/D:/word/copaw/src/copaw/kernel/agent_profile_service.py)
- capability/agent policy 相关服务

### 验收标准

- Manager 不再被默认视为无限能力拥有者
- Researcher 默认研究型执行偏 `guarded`

### 兼容与删旧说明

- 当前直接写 `AgentProfileOverrideRecord.capabilities` 仍是过渡手段
- 后续需要收敛到更正式的角色授权模型与独立 read model，但本阶段已经切断“默认无限能力”状态

---

## 6.9 B9：最小前端工作台

### 当前状态（2026-03-11）

- `completed`
- `/industry` 页面已经把“创建实例 -> 查看最近实例 -> 查看详情 -> 跳转 Runtime Center / Agent Workbench”串成同一路径
- 前端不再要求 operator 手工拼 bootstrap JSON 才能启动行业实例

### 目标

- 让行业实例从“能创建”进化到“能操作”

### 主要产出

- 行业实例创建入口
- 最近行业实例列表
- goal / agent / schedule 快捷跳转

### 验收标准

- 一个行业实例从创建、查看到启动首轮执行，可以在同一前端路径完成

---

## 6.10 B10：自动化测试矩阵

### 当前状态（2026-03-11）

- `completed`
- 已新增/更新 `tests/app/test_industry_api.py`、`tests/app/test_runtime_center_api.py`、`tests/environments/test_environment_registry.py`
- 已覆盖行业 bootstrap、instances/detail、runtime-center industry detail、default schedule、evidence-driven report、环境恢复与 replay 执行器路径
- 已通过全量 `pytest`（`289 passed, 1 skipped`）与前端 `console` build

### 目标

- 给 Phase B 建立独立回归链

### 必测项

- schema normalization
- bootstrap API
- goal detail/agent detail 行业字段
- schedule seed 与默认调度
- 日报聚合

### 推荐落点

- `tests/app/test_industry_api.py`
- `tests/app/test_runtime_center_api.py`
- `tests/environments/test_environment_registry.py`

### 验收标准

- Phase B 核心链路可以单独回归
- 已完成范围包括 schema normalization、bootstrap API、角色授权边界、industry detail、schedule seed、日报聚合与前端路径回归

---

## 6.11 B11：文档同步与删旧准备

### 当前状态（2026-03-11）

- `completed`
- 已同步 `TASK_STATUS.md`、`implementation_plan.md`、`PHASEA_PHASEB_PARALLEL_PLAN.md`、`DEPRECATION_LEDGER.md`、`DATA_MODEL_DRAFT.md`
- 已同步 `API_TRANSITION_MAP.md`
- 当前文档状态已与本轮代码现场和验收结果对齐

### 目标

- 保证 Phase B 的进度、临时承载位、删除条件都可追踪

### 每次至少要同步

- [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
- [implementation_plan.md](/D:/word/copaw/implementation_plan.md)
- [DEPRECATION_LEDGER.md](/D:/word/copaw/DEPRECATION_LEDGER.md)

### 完成标准

- 文档不会比代码现场更乐观
- 新兼容位都有删除条件

---

## 6.12 B12：MVP 验收

### 当前状态（2026-03-11）

- `completed`
- 已通过“bootstrap -> instances/detail -> runtime-center industry detail -> default schedule -> evidence-driven report”主链验收
- 验收同时确认未引入平行真相源、平行调度器或独立 reporting store

### 目标

- 对 Phase B 做一次从输入到运行的正式验收

### 验收链路

1. 输入行业画像
2. 生成团队蓝图
3. 生成 goals 与 plan steps
4. 在 Runtime Center 可见
5. 触发首轮 dispatch
6. 查看 evidence
7. 查看 schedule
8. 查看日报摘要

### 完成标准

- 上述链路全部通过
- 无平行真相源
- 无隐藏兼容双写

---

## 7. Phase B 临时承载位与删除条件

本节用于明确 Phase B 当前允许存在、但未来必须删除或替换的临时承载位。

### 7.1 `GoalOverrideRecord.compiler_context` 暂存行业画像与团队蓝图

- 当前状态：`active-temporary`
- 当前用途：承载 `industry_profile / team_blueprint / goal_kind`
- 为什么存在：当前还没有一等 `IndustryProfileRecord / TeamBlueprintRecord`
- 替代目标：正式行业对象与团队对象读写层
- 删除条件：
  - 行业画像与团队蓝图成为一等对象
  - Runtime Center 不再依赖 `goal override` 读取行业实例上下文

### 7.2 `AgentProfileOverrideRecord` 暂存生成型行业 agent

- 当前状态：`active-temporary`
- 当前用途：让 `industry-manager-* / industry-researcher-*` 成为可见 agent
- 为什么存在：当前还没有正式团队/角色注册表
- 替代目标：团队蓝图与角色蓝图的一等 registry/projection
- 删除条件：
  - `TeamBlueprint / RoleBlueprint` 进入正式 repository/service
  - agent 可见性不再依赖 profile override 注入

### 7.3 行业初始化入口暂时复用 Goal/Override 主链

- 当前状态：`accepted-bridge`
- 当前用途：快速让行业实例接上现有 kernel/state/evidence 主链
- 为什么存在：避免为行业产品线另起平行主链
- 替代目标：更正式的 industry repository / projection service；bootstrap compiler/service 本身已稳定
- 删除条件：
  - 行业画像、团队蓝图、角色蓝图进入正式 repository/service
  - detail/read model 不再依赖 override carrier 与 service 内联聚合

---

## 8. 推荐批次

推荐按 3 个批次推进：

### Batch 1

- B1
- B2
- B3
- B4

交付结果：

- `2026-03-11` 已完成 `B1/B2/B3/B4`
- 行业对象、团队蓝图、goal seed 编译链与 Runtime Center 行业 detail 已稳定

### Batch 2

- B5
- B6
- B8（已于 `2026-03-11` 随 `A3` 提前完成基础版，后续仅保留正式化收口）

交付结果：

- `2026-03-11` 已完成 `B5/B6`，且 `B8` 基础版保持稳定
- 可以从入口创建行业实例
- 可以带默认 schedule 持续推进
- 角色能力与环境约束有基础边界

### Batch 3

- B7
- B9
- B10
- B11
- B12

交付结果：

- `2026-03-11` 已完成 `B7/B9/B10/B11/B12`
- 有最小前端工作台
- 有真实日报
- 有自动化测试与正式验收

---

## 9. 当前建议

当前 `Phase B 行业初始化 MVP` 已完成；如果下一步继续施工，建议直接转入 `Phase C`：

1. 建立正式的 industry/team/role repository 与 projection service
2. 删除 `GoalOverrideRecord.compiler_context` 与 `AgentProfileOverrideRecord` 的长期承载地位
3. 继续扩大真实 provider/environment 覆盖，而不是重开 MVP 待办

原因：

- 当前 MVP 的 bootstrap、detail、schedule、reports、workbench 与验收已经全部落地
- 继续在本文件范围内反复打补丁，只会延长 carrier 的生命周期
- 下一阶段真正值得做的是正式对象化与删兼容，而不是再造一层 industry 平行系统
