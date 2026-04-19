# Active Surface State Graph, Capability Twin, And Reward Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 browser/document/desktop shared surface substrate 升级成正式的 `Surface State Graph -> Probe -> Transition -> Capability Twin -> Reward Ranking` 主链，同时严格回映到现有 `EnvironmentMount / SessionMount / RuntimeFrame / EvidenceRecord / StrategyMemory / Assignment`，不新增第二真相源。

**Architecture:** 保留现有 `observe / execute / reobserve / guided owner / evidence` 基线，不重写三类 surface 底座。先补统一 graph 编译与 runtime projection，再补 probe/diff/evidence，然后再把 capability twin 与 reward ranking 接到 learning/state 和正式读链，最后再补 Runtime Center 与 Knowledge 的可见化和长链验收。

**Tech Stack:** Python, Pydantic, sqlite state repositories, pytest, FastAPI runtime-center routers, existing learning service, React, TypeScript, vitest.

---

## File Structure Map

- Create: `src/copaw/environments/surface_execution/graph_models.py`
- Create: `src/copaw/environments/surface_execution/graph_compiler.py`
- Create: `src/copaw/environments/surface_execution/probe_engine.py`
- Create: `src/copaw/environments/surface_execution/transition_miner.py`
- Modify: `src/copaw/environments/surface_execution/__init__.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/contracts.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/contracts.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/environments/surface_execution/owner.py`
- Create: `src/copaw/state/models_surface_learning.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_surface_learning.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/state/repositories/sqlite_tasks.py`
- Modify: `src/copaw/evidence/models.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `src/copaw/evidence/serialization.py`
- Create: `src/copaw/learning/surface_capability_service.py`
- Create: `src/copaw/learning/surface_reward_service.py`
- Modify: `src/copaw/learning/models.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `console/src/runtime/runtimeSurfaceClient.ts`
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_document_desktop_surface_execution.py`
- Test: `tests/evidence/test_ledger.py`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/test_runtime_center_knowledge_api.py`
- Test: `tests/app/test_phase2_read_surface_unification.py`

### Task 1: 锁定三类 Surface Graph 基线合同

**Files:**
- Create: `src/copaw/environments/surface_execution/graph_models.py`
- Create: `src/copaw/environments/surface_execution/graph_compiler.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/document/contracts.py`
- Modify: `src/copaw/environments/surface_execution/desktop/contracts.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`

- [ ] **Step 1: 写 browser/document/desktop 最小 graph 输出失败测试**

测试要固定三类 surface 都能把当前 observation 编译成统一 `SurfaceGraphSnapshot`，至少包含：

- `surface_kind`
- `regions`
- `controls`
- `results`
- `blockers`
- `entities`
- `relations`
- `confidence`

- [ ] **Step 2: 跑失败测试确认当前还没有 graph 编译层**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k graph_snapshot -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k graph_snapshot -q
```

Expected: FAIL，因为当前只返回各自 observation，没有统一 graph projection。

- [ ] **Step 3: 新增 graph 模型与最小 compiler**

实现：

- `SurfaceGraphNode`
- `SurfaceGraphEdge`
- `SurfaceGraphSnapshot`
- `compile_browser_observation_to_graph(...)`
- `compile_document_observation_to_graph(...)`
- `compile_desktop_observation_to_graph(...)`

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py -k graph_snapshot -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/graph_models.py src/copaw/environments/surface_execution/graph_compiler.py src/copaw/environments/surface_execution/browser/contracts.py src/copaw/environments/surface_execution/document/contracts.py src/copaw/environments/surface_execution/desktop/contracts.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py
git commit -m "feat: add surface graph baseline contracts"
```

### Task 2: 把 Graph 基线接进三类 Surface Service 和 Runtime Projection

**Files:**
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/environments/surface_execution/__init__.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Modify: `src/copaw/state/repositories/sqlite_tasks.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`

- [ ] **Step 1: 写失败测试，证明执行前后结果都带 graph 快照**

失败测试要固定：

- `before_observation` 对应 `before_graph`
- `after_observation` 对应 `after_graph`
- `RuntimeFrameRecord` 能持有 graph projection 引用或结构摘要

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k before_after_graph -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k before_after_graph -q
```

Expected: FAIL，因为当前 service 没有 graph projection。

- [ ] **Step 3: 在 service 内接 graph 编译与 runtime projection**

实现要求：

- 执行前后都编译 graph
- graph 不单独造第二张 runtime 表
- 先挂在 `RuntimeFrameRecord` 的正式 projection / summary 路径上
- 必要时给 `SessionMount.metadata` 增加当前 live graph 摘要

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py -k "graph or before_after_graph" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/environments/surface_execution/__init__.py src/copaw/state/models_goals_tasks.py src/copaw/state/repositories/sqlite_tasks.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py
git commit -m "feat: project surface graph into runtime execution flow"
```

### Task 3: 落正式 Probe Engine，并把探测写成 Evidence

**Files:**
- Create: `src/copaw/environments/surface_execution/probe_engine.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/evidence/models.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `src/copaw/evidence/serialization.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`
- Modify: `tests/evidence/test_ledger.py`

- [ ] **Step 1: 写失败测试，锁定不确定区域必须先 probe**

失败测试要覆盖：

- graph 有低置信关键节点时，不直接业务 act
- 会先触发 `scroll / expand / hover / focus / open-dropdown` 这类低风险 probe
- probe 后会触发 reobserve

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k probe -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k probe -q
```

Expected: FAIL，因为当前没有统一 probe engine。

- [ ] **Step 3: 增加 probe evidence kind 与正式写链**

实现要求：

- evidence kind 新增 `surface-probe`
- 每次 probe 都要写明：
  - `before_graph`
  - `probe_action`
  - `target_region`
  - `reason`
  - `after_graph`
  - `resolved_uncertainty`

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py -k "probe or surface" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/probe_engine.py src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/evidence/models.py src/copaw/evidence/ledger.py src/copaw/evidence/serialization.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py
git commit -m "feat: add probe engine and surface probe evidence"
```

### Task 4: 落正式 Transition Miner，记录状态前后 diff

**Files:**
- Create: `src/copaw/environments/surface_execution/transition_miner.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/evidence/models.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`
- Modify: `tests/evidence/test_ledger.py`

- [ ] **Step 1: 写失败测试，证明 act 后会留下状态转移 diff**

测试要锁定：

- `before_graph_ref`
- `after_graph_ref`
- `changed_nodes`
- `new_blockers`
- `resolved_blockers`
- `result_summary`

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k transition -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k transition -q
```

Expected: FAIL，因为当前只做动作结果回读，没有正式 transition mining。

- [ ] **Step 3: 实现 transition miner 与 evidence sink**

实现要求：

- evidence kind 新增 `surface-transition`
- diff 逻辑复用 graph 节点/边比较，不另写 provider 私货
- 三类 surface 共用一套 transition record 生成逻辑

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py -k "transition or diff" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/transition_miner.py src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/evidence/models.py src/copaw/evidence/ledger.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py
git commit -m "feat: mine surface state transitions into evidence"
```

### Task 5: 落 Capability Twin 正式对象、Repository 和 Learning Service

**Files:**
- Create: `src/copaw/state/models_surface_learning.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_surface_learning.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Create: `src/copaw/learning/surface_capability_service.py`
- Modify: `src/copaw/learning/models.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `tests/app/test_learning_api.py`
- Create or Modify: `tests/state/test_surface_capability_twin_repository.py`

- [ ] **Step 1: 写失败测试，锁定 twin/playbook 正式持久化**

至少要有：

- `SurfaceCapabilityTwinRecord`
- `SurfacePlaybookRecord`
- scope 字段
- version / status
- evidence refs
- 历史版本查询

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/app/test_learning_api.py -k surface -q
python -m pytest tests/state/test_surface_capability_twin_repository.py -q
```

Expected: FAIL，因为当前 learning 层没有这组正式对象。

- [ ] **Step 3: 实现 twin/playbook repository 与 learning facade 接线**

实现要求：

- twin 属于正式长期知识，不混到 live runtime
- playbook 是 twin 的快读投影
- 不单独发明顶层 `RewardProfile` 表
- 复用 learning/state 正式对象和现有 learning facade

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/state/test_surface_capability_twin_repository.py tests/app/test_learning_api.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_surface_learning.py src/copaw/state/models.py src/copaw/state/store.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_surface_learning.py src/copaw/state/repositories/__init__.py src/copaw/state/repositories/sqlite.py src/copaw/learning/surface_capability_service.py src/copaw/learning/models.py src/copaw/learning/service.py tests/state/test_surface_capability_twin_repository.py tests/app/test_learning_api.py
git commit -m "feat: add formal surface capability twin storage and service"
```

### Task 6: 落 Reward Ranking，接正式目标链，不造第二套目标系统

**Files:**
- Create: `src/copaw/learning/surface_reward_service.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `tests/app/test_learning_api.py`
- Modify: `tests/app/test_phase2_read_surface_unification.py`

- [ ] **Step 1: 写失败测试，锁定 reward 读取正式目标源**

失败测试要证明 reward ranking 来自：

- `StrategyMemory`
- `OperatingLane`
- `Assignment`
- role/profession success criteria

而不是 provider 自己硬写优先级。

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/app/test_learning_api.py -k reward -q
python -m pytest tests/app/test_phase2_read_surface_unification.py -k reward -q
```

Expected: FAIL，因为当前没有正式 goal-conditioned ranking 服务。

- [ ] **Step 3: 实现 reward ranking 与读链**

实现要求：

- 输出当前推荐能力、预估收益、风险、成本、排序原因
- 只做正式目标派生，不新建第二套目标真相
- 可被 Runtime Center 和职业 agent prompt 消费

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/app/test_learning_api.py tests/app/test_phase2_read_surface_unification.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/learning/surface_reward_service.py src/copaw/learning/service.py src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/learning.py tests/app/test_learning_api.py tests/app/test_phase2_read_surface_unification.py
git commit -m "feat: rank surface capabilities by formal goal context"
```

### Task 7: 补 Runtime Center / Knowledge 正式读面

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `console/src/runtime/runtimeSurfaceClient.ts`
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Modify: `tests/app/test_runtime_center_knowledge_api.py`

- [ ] **Step 1: 写失败测试，锁定 UI 能看到统一 surface 学习读面**

最少要可见：

- 当前 live graph 摘要
- 最近 probe/transition evidence
- 当前 capability twin 列表
- 当前 reward ranking
- 当前 scope/version

- [ ] **Step 2: 跑失败测试**

Run:

```bash
python -m pytest tests/app/test_runtime_center_knowledge_api.py -k surface -q
cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: FAIL，因为当前读面还没有这套正式聚合。

- [ ] **Step 3: 实现后端聚合与前端简化展示**

要求：

- Runtime Center 读的是正式后端聚合，不拼假数据
- Knowledge 页展示 capability twin / playbook / reward ranking
- MainBrainCockpit 只展示摘要，不把 graph 原始细节塞满首页

- [ ] **Step 4: 跑 focused regression**

Run:

```bash
python -m pytest tests/app/test_runtime_center_knowledge_api.py -q
cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/runtime_center_routes_knowledge.py src/copaw/app/routers/runtime_center_routes_memory.py console/src/runtime/runtimeSurfaceClient.ts console/src/pages/Knowledge/index.tsx console/src/pages/Knowledge/index.test.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx tests/app/test_runtime_center_knowledge_api.py
git commit -m "feat: surface graph and twin read model for runtime center"
```

### Task 8: 跑分层验收并锁死诚实边界

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `UNIFIED_ACCEPTANCE_STANDARD.md`（仅当验收口径需要新增 surface 专项示例时）
- Test: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_document_desktop_surface_execution.py`
- Test: `tests/evidence/test_ledger.py`
- Test: `tests/state/test_surface_capability_twin_repository.py`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/test_runtime_center_knowledge_api.py`
- Test: `tests/app/test_phase2_read_surface_unification.py`

- [ ] **Step 1: 跑 L1/L2 回归**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py tests/state/test_surface_capability_twin_repository.py tests/app/test_learning_api.py tests/app/test_runtime_center_knowledge_api.py tests/app/test_phase2_read_surface_unification.py -q
```

Expected: PASS

- [ ] **Step 2: 跑 L3 live smoke**

至少要跑：

- 真浏览器页面 `observe -> probe -> act -> diff`
- 真文档结构改写和回读
- 真桌面窗口探索和 blocker 识别

Run:

```bash
python scripts/channel_live_smoke.py --scenario surface_graph_browser
python scripts/channel_live_smoke.py --scenario surface_graph_document
python scripts/channel_live_smoke.py --scenario surface_graph_desktop
```

Expected: PASS 或诚实标注宿主前提不满足

- [ ] **Step 3: 跑 L4 long soak**

至少要验证：

- 多轮 graph 不脏
- twin 不串 scope
- reward ranking 不被旧缓存覆盖
- 重启恢复后能续同一学习链

- [ ] **Step 4: 更新 `TASK_STATUS.md`**

必须写清：

- 哪些条目到 `L1`
- 哪些条目到 `L2`
- 哪些条目跑了 `L3`
- `L4` 是否跑完，没跑就明确写没跑

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md UNIFIED_ACCEPTANCE_STANDARD.md
git commit -m "docs: record surface graph capability twin acceptance status"
```

### Task 9: 真实收口标准

**Files:**
- Future acceptance gate only

- [ ] **Step 1: 不得把 graph compiler 说成整套完成**
- [ ] **Step 2: 不得把 probe/evidence 说成 capability twin 已完成**
- [ ] **Step 3: 不得把 L1/L2 说成任意职业真实长链都通过**
- [ ] **Step 4: 只有当 graph/probe/diff/twin/reward/UI/L3/L4 全部齐了，才能对外说这条 spec 完成**

---

## 当前诚实状态

- 这份 implementation plan 只定义施工顺序和文件落点。
- 当前仓库已完成的是：
  - shared browser/document/desktop substrate 基线
  - guided frontdoor 基线
  - 新 spec 文档
- 当前仓库还没完成的是：
  - `SurfaceGraphSnapshot` 正式 runtime projection
  - 统一 `Probe Engine`
  - 统一 `Transition Miner`
  - `SurfaceCapabilityTwinRecord / SurfacePlaybookRecord`
  - `Goal-Conditioned Reward Ranking`
  - 这整套链路的 `L3/L4` 真实验收
