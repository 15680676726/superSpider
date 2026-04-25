# PHASE1_EXECUTION_PLAN.md

本文件用于把 `COPAW_CARRIER_UPGRADE_MASTERPLAN.md` 中的 `Phase 1` 细化为可执行任务。

`Phase 1` 的主题是：

> 统一状态与证据基线

其目标不是一次做完整体新架构，而是为后续 `CapabilityMount / EnvironmentMount / SRK / Patch` 打下统一真相源和统一证据的基础。

---

## 1. Phase 1 目标

### 1.1 主要目标

- 建立新的 `state` 基础层
- 建立新的 `evidence` 基础层
- 明确 `config` 与 `state` 的职责边界
- 让至少一条主链开始写入统一 store

### 1.2 非目标

本阶段不追求完成以下事项：

- 不完成完整 SRK 内核
- 不完成完整能力统一
- 不完成完整环境挂载系统
- 不完成完整控制台重构
- 不完成语义编译层

---

## 2. 成功标准

本阶段完成的判定标准：

- 已存在统一运行 store（建议 `SQLite`）
- 已定义最小核心对象模型
- 至少一条运行主链能够写入新 store
- 已引入最小 `EvidenceLedger`
- 已经明确哪些旧 JSON 进入冻结或迁移状态
- 不再新增新的平行运行真相文件

---

## 3. 推荐新增目录

建议在 `src/copaw/` 下新增：

```text
state/
  __init__.py
  models.py
  store.py
  repositories/
  migrations/

evidence/
  __init__.py
  models.py
  ledger.py
  artifacts.py
```

---

## 4. 本阶段要落地的核心对象

### 4.1 `state.models`

优先定义以下对象：

- `GoalRecord`
- `TaskRecord`
- `TaskRuntimeRecord`
- `RuntimeFrameRecord`
- `DecisionRequestRecord`

### 4.2 `evidence.models`

优先定义以下对象：

- `EvidenceRecord`
- `ArtifactRecord`
- `ReplayPointer`

### 4.3 第一阶段对象最小字段建议

#### `TaskRecord`

- `id`
- `goal_id`
- `title`
- `kind`
- `status`
- `owner_role`
- `created_at`
- `updated_at`

#### `TaskRuntimeRecord`

- `task_id`
- `current_phase`
- `last_error`
- `last_result_summary`
- `risk_level`
- `active_environment_id`
- `updated_at`

#### `RuntimeFrameRecord`

- `task_id`
- `goal_summary`
- `owner`
- `constraints_summary`
- `current_risk`
- `evidence_summary`
- `updated_at`

#### `EvidenceRecord`

- `id`
- `task_id`
- `actor`
- `environment_ref`
- `capability_ref`
- `risk_level`
- `action_summary`
- `result_summary`
- `artifact_ref`
- `replay_ref`
- `created_at`

---

## 5. 实施任务拆解

## 5.1 Task Group A：建立 state 基础设施

### A1. 新建 `state` 模块骨架

- 创建 `src/copaw/state/__init__.py`
- 创建 `src/copaw/state/models.py`
- 创建 `src/copaw/state/store.py`
- 创建 `src/copaw/state/repositories/`
- 创建 `src/copaw/state/migrations/`

### A2. 选择存储方案

推荐优先使用：

- `SQLite`

原因：

- 本地优先
- 易迁移
- 易调试
- 易做事务边界
- 足够承载 Phase 1 ~ Phase 4

### A3. 建立最小仓储接口

优先定义：

- `TaskRepository`
- `TaskRuntimeRepository`
- `RuntimeFrameRepository`

---

## 5.2 Task Group B：建立 evidence 基础设施

### B1. 新建 `evidence` 模块骨架

- 创建 `src/copaw/evidence/__init__.py`
- 创建 `src/copaw/evidence/models.py`
- 创建 `src/copaw/evidence/ledger.py`
- 创建 `src/copaw/evidence/artifacts.py`

### B2. 实现最小 `EvidenceLedger`

要求：

- 支持新增证据
- 支持按 task 查询证据
- 支持关联 artifact 与 replay 指针

### B3. 约束第一版证据写入点

优先从以下链路切入：

- 手动触发的一次任务执行
- shell / file / browser 中至少一种外部动作路径

---

## 5.3 Task Group C：定义 config 与 state 的边界

### C1. 写清职责边界

`config` 保留：

- 渠道声明式配置
- provider 声明式配置
- 默认策略配置
- feature flag / boot config

`state` 承担：

- 任务
- 运行态
- 生命周期
- 证据
- 任务上下文

### C2. 禁止新增的旧路径

在 Phase 1 期间，应避免新增以下类型代码：

- 再往新的 JSON 文件里写运行真相
- 再让 manager 长期私有持有核心状态且无持久化映射

---

## 5.4 Task Group D：选一条主链接入新 store

### D1. 选择最小切入链路

优先推荐：

- CLI / API 触发的一条单任务执行链

不建议一开始就接：

- 全渠道
- 全 cron
- 全环境挂载

### D2. 最小接入目标

该主链至少要做到：

- 创建 `TaskRecord`
- 创建或更新 `TaskRuntimeRecord`
- 在执行前后写入 `RuntimeFrameRecord`
- 在外部动作处写入 `EvidenceRecord`

---

## 5.5 Task Group E：冻结旧状态扩散

### E1. 标记旧模块状态

需要在 `DEPRECATION_LEDGER.md` 中把以下内容至少标为 `frozen` 或规划迁移：

- `jobs.json`
- `chats.json`
- `sessions/`
- 旧 runner 中直接依赖的状态路径

### E2. 停止新增平行写入

一旦 Phase 1 开始：

- 新功能不再新增新的状态 JSON
- 不再新增新的“临时 manager 私有状态”作为长期真相

---

## 6. 代码规范（Phase 1 专属）

### 6.1 新代码必须优先声明式建模

先定义对象，再写流程。

优先顺序：

1. `models`
2. `store / repository`
3. `service / ledger`
4. `adapter`

### 6.2 不要把旧业务逻辑直接复制进新层

如果旧逻辑脏且耦合，优先：

- 抽取必要行为
- 重建接口
- 通过 adapter 接入

不要把整块旧逻辑原样搬进 `state` 或 `evidence`。

### 6.3 兼容逻辑必须隔离

如果 Phase 1 需要兼容旧 JSON 或旧 manager：

- 请单独封装 adapter
- 不要把兼容细节散落到新 store 核心代码里

---

## 7. 测试计划

### 7.1 单元测试

优先覆盖：

- state models 校验
- repository 基本 CRUD
- evidence ledger 写入和查询

### 7.2 集成测试

优先覆盖：

- 一条最小执行链从任务创建到证据写入

### 7.3 回归约束

至少保证：

- 旧系统未被立即打挂
- 新链路可被单独验证

---

## 8. 风险点

本阶段最大的风险：

- 旧系统和新 store 形成长期双写
- 只建表不接主链，导致新层成为摆设
- state 和 evidence 边界不清
- 设计过大，迟迟不落地第一条主链

控制策略：

- 只选一条主链先打通
- 先建最小对象，不追求一次模型极其完整
- 严禁同时新增多套状态路径

---

## 9. 建议交付顺序

推荐执行顺序：

1. 建目录
2. 定模型
3. 定 store / repository
4. 定 evidence ledger
5. 选一条最小主链接入
6. 写测试
7. 更新 `DEPRECATION_LEDGER.md`
8. 更新 `ARCHITECTURE_DECISIONS.md`（如有边界调整）

---

## 10. Phase 1 完成后的出口条件

满足以下条件后，才可进入 `Phase 2`：

- 新 state store 已稳定存在
- 新 evidence ledger 已稳定存在
- 至少一条真实主链写入新 store
- 没有新增平行状态 JSON
- `config` 与 `state` 的边界已经写清并落实
- 遗留台账已更新

---

## 11. 预计工期

以单人主开发估算，`Phase 1` 建议工期：

- `1.5 ~ 2.5` 周

若本阶段同时承担额外旧系统维护与较多回归修复，工期可能延长到：

- `3` 周左右

