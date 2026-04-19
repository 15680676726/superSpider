# Active Surface State Graph, Capability Twin, And Reward Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 browser/document/desktop shared surface substrate 升级成正式的 `Surface State Graph -> Probe -> Transition -> Capability Twin -> Reward Ranking` 主链，同时严格回映到现有 `EnvironmentMount / SessionMount / RuntimeFrame / EvidenceRecord / StrategyMemory / Assignment`，不新增第二真相源。

**Architecture:** 保留现有 `observe / execute / reobserve / guided owner / evidence` 基线，不重写三类 surface 底座。先补统一 graph 编译与 runtime projection，再补 probe/diff/evidence，然后补 twin/playbook 正式对象与写链，接着统一 prompt/read-chain 和 Runtime Center / Knowledge 读面，最后再跑 gated live smoke 与 soak。

**Tech Stack:** Python, Pydantic, sqlite state repositories, pytest, FastAPI runtime-center routers, existing learning service, React, TypeScript, vitest.

---

## File Structure Map

### Surface Execution

- Create: `src/copaw/environments/surface_execution/graph_models.py`
- Create: `src/copaw/environments/surface_execution/graph_compiler.py`
- Create: `src/copaw/environments/surface_execution/probe_engine.py`
- Create: `src/copaw/environments/surface_execution/transition_miner.py`
- Modify: `src/copaw/environments/surface_execution/__init__.py`
- Modify: `src/copaw/environments/surface_execution/owner.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/contracts.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/contracts.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`

### State / Learning

- Create: `src/copaw/state/models_surface_learning.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_surface_learning.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/state/repositories/sqlite_tasks.py`
- Create: `src/copaw/learning/surface_capability_service.py`
- Create: `src/copaw/learning/surface_reward_service.py`
- Modify: `src/copaw/learning/models.py`
- Modify: `src/copaw/learning/service.py`

### Evidence / Kernel / Runtime Read Chain

- Modify: `src/copaw/evidence/models.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `src/copaw/evidence/serialization.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`

### Frontend

- Modify: `console/src/runtime/runtimeSurfaceClient.ts`
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

### Tests

- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`
- Modify: `tests/evidence/test_ledger.py`
- Modify: `tests/state/test_state_store_migration.py`
- Modify: `tests/state/test_sqlite_repositories.py`
- Modify: `tests/state/test_surface_learning_repository.py`
- Modify: `tests/kernel/test_memory_recall_integration.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify or Create: `tests/kernel/test_main_brain_scope_snapshot_service.py`
- Modify: `tests/app/test_learning_api.py`
- Modify: `tests/app/test_runtime_center_knowledge_api.py`
- Modify: `tests/app/test_runtime_center_memory_api.py`
- Modify or Create: `tests/app/test_runtime_center_surface_learning_api.py`
- Modify: `tests/app/test_phase2_read_surface_unification.py`
- Modify or Create: `tests/app/test_surface_graph_live_smoke.py`
- Modify or Create: `tests/app/test_surface_graph_soak.py`

### Docs / Status

- Modify: `TASK_STATUS.md`
- Modify: `UNIFIED_ACCEPTANCE_STANDARD.md`

## Implementation Guardrails

- Round-1 不新建独立 live graph sqlite 表；live graph 只允许挂在 `SessionMount.metadata["surface_live_projection"]`。
- 历史 graph 只允许落在 `RuntimeFrameRecord.surface_projection`，sqlite 列名固定为 `surface_projection_json`。
- `BrowserObservation / DocumentObservation / DesktopObservation` 都要补同名字段：`surface_graph`。
- `BrowserExecutionResult / DocumentExecutionResult / DesktopExecutionResult` 都要补同名字段：`before_graph`、`after_graph`。
- `EvidenceRecord` 这轮固定新增 3 种 kind：
  - `surface-probe`
  - `surface-transition`
  - `surface-discovery`
- `surface-discovery` 只在“首次发现新 region / control group / capability candidate”时写入，不允许每次 observe 都刷一条。
- `transition -> twin/playbook merge` 第一轮固定为同步、限界、进程内写链；先不引入队列和第二套 learning runtime。
- `RewardProfile` 这轮只能作为派生读模型存在，禁止顺手新建独立表。
- `reward ranking` 第一轮必须接到：
  - `query execution prompt`
  - `main brain scope snapshot`
  - `Runtime Center / Knowledge`
- `runtime_center_payloads.py` 是 Runtime Center / Knowledge 的统一序列化边界；不要在多个 router 各自拼自己的 surface payload。
- 首页只显示摘要，不允许把完整 graph 原始 payload 直接塞进主脑驾驶舱。
- 计划里的 live / soak 命令必须是仓库真实存在的 pytest 文件；禁止再写不存在的脚本命令。

## Dependency Order

1. 先冻结 graph / runtime / evidence / twin / playbook / reward 的正式字段名和落位。
2. 再改 observation / execution contracts。
3. 再改 `RuntimeFrameRecord / SessionMount` 投影和 store migration。
4. 再补 `probe / discovery / transition` 证据链。
5. 再补 twin / playbook 正式对象、repository、bootstrap 读投影。
6. 再把 `transition -> twin/playbook -> reward` 写链接起来，并加 dirty-mark。
7. 再统一 prompt/read-chain、Runtime Center、Knowledge 后端聚合。
8. 最后再补前端可见化和 stale response 防护。
9. 所有读写链收口后，最后才跑 gated live smoke 和 soak。

### Task 1: 锁定三类 Surface Graph 基线合同

**Files:**
- Create: `src/copaw/environments/surface_execution/graph_models.py`
- Create: `src/copaw/environments/surface_execution/graph_compiler.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/document/contracts.py`
- Modify: `src/copaw/environments/surface_execution/desktop/contracts.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`

- [ ] **Step 1: 写 browser graph 失败测试**

锁定：

- `BrowserObservation.surface_graph`
- `BrowserExecutionResult.before_graph`
- `BrowserExecutionResult.after_graph`

- [ ] **Step 2: 写 document / desktop graph 失败测试**

锁定：

- `DocumentObservation.surface_graph`
- `DesktopObservation.surface_graph`
- 对应 execution result 的 `before_graph / after_graph`

- [ ] **Step 3: 固定最小 `SurfaceGraphSnapshot` 字段**

三类 surface 都必须编译出统一结构，至少包含：

- `surface_kind`
- `regions`
- `controls`
- `results`
- `blockers`
- `entities`
- `relations`
- `confidence`

- [ ] **Step 4: 跑失败测试，确认当前还没有 graph 编译层**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k graph_snapshot -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k graph_snapshot -q
```

Expected: FAIL，因为当前只返回各自 observation，没有统一 graph projection。

- [ ] **Step 5: 新增 graph 模型与最小 compiler**

实现：

- `SurfaceGraphNode`
- `SurfaceGraphEdge`
- `SurfaceGraphSnapshot`
- `compile_browser_observation_to_graph(...)`
- `compile_document_observation_to_graph(...)`
- `compile_desktop_observation_to_graph(...)`

- [ ] **Step 6: 把 graph 字段接进三类 observation / execution result 合同**

字段名必须完全统一：

- `surface_graph`
- `before_graph`
- `after_graph`

- [ ] **Step 7: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py -k graph_snapshot -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/copaw/environments/surface_execution/graph_models.py src/copaw/environments/surface_execution/graph_compiler.py src/copaw/environments/surface_execution/browser/contracts.py src/copaw/environments/surface_execution/document/contracts.py src/copaw/environments/surface_execution/desktop/contracts.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py
git commit -m "feat: add surface graph baseline contracts"
```

### Task 2: 固定 Runtime Projection 合同和状态迁移

**Files:**
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/environments/surface_execution/__init__.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_tasks.py`
- Modify: `tests/state/test_state_store_migration.py`
- Modify: `tests/state/test_sqlite_repositories.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`

- [ ] **Step 1: 写 migration 失败测试，锁定 `runtime_frames.surface_projection_json`**

- [ ] **Step 2: 写 repository round-trip 失败测试，锁定 `RuntimeFrameRecord.surface_projection`**

必须证明：

- `surface_projection` 能写入
- `surface_projection` 能读回
- 迁移后的老库默认值安全

- [ ] **Step 3: 写 service 失败测试，证明执行前后结果都带 graph 快照**

失败测试要锁定：

- `before_observation` 对应 `before_graph`
- `after_observation` 对应 `after_graph`
- `RuntimeFrameRecord.surface_projection` 持有结构化 graph 摘要
- `SessionMount.metadata["surface_live_projection"]` 持有 live graph 摘要

- [ ] **Step 4: 跑失败测试**

Run:

```bash
python -m pytest tests/state/test_state_store_migration.py -k runtime_frame_surface_projection -q
python -m pytest tests/state/test_sqlite_repositories.py -k runtime_frame_surface_projection -q
python -m pytest tests/environments/test_browser_surface_execution.py -k before_after_graph -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k before_after_graph -q
```

Expected: FAIL，因为当前 schema / repo / service 都没有正式 graph projection。

- [ ] **Step 5: 给 `RuntimeFrameRecord` 增加正式字段**

字段固定为：

- Python: `surface_projection: dict[str, Any]`
- SQLite: `surface_projection_json`

- [ ] **Step 6: 更新 store schema、migration、repository 接口和 sqlite 实现**

这一小步必须同时改：

- `state/store.py`
- `state/repositories/base.py`
- `state/repositories/sqlite_tasks.py`

- [ ] **Step 7: 在三类 surface service 内接 live projection**

实现要求：

- 执行前后都编译 graph
- graph 不单独造第二张 runtime 表
- 历史 graph 只走 `RuntimeFrameRecord.surface_projection`
- live graph 只走 `SessionMount.metadata["surface_live_projection"]`

- [ ] **Step 8: 跑 focused regression**

Run:

```bash
python -m pytest tests/state/test_state_store_migration.py tests/state/test_sqlite_repositories.py -k runtime_frame_surface_projection -q
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py -k "graph or before_after_graph" -q
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/environments/surface_execution/__init__.py src/copaw/state/models_goals_tasks.py src/copaw/state/store.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_tasks.py tests/state/test_state_store_migration.py tests/state/test_sqlite_repositories.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py
git commit -m "feat: project surface graph into runtime execution flow"
```

### Task 3: 落正式 Probe Engine，并把探测与发现写成统一 Evidence

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

- [ ] **Step 1: 先写 browser 失败测试，锁定“低置信关键节点必须先 probe”**

失败测试必须证明：

- graph 中关键 `control / result / blocker` 置信度低时，不能直接进入正式业务 act
- 会优先触发 `scroll / expand / hover / focus / open-dropdown / refresh-local-region`
- probe 完成后必须自动 reobserve，再给上层新的 graph

- [ ] **Step 2: 再写 document / desktop 失败测试，锁定三类 surface 共用 probe 合同**

失败测试必须证明：

- 文档和桌面也走统一 `ProbeEngine`
- 不允许 browser 一套、document 一套、desktop 一套各自写私有判断
- probe 返回结构里必须包含 `probe_action`、`target_region`、`reason`

- [ ] **Step 3: 写 evidence 失败测试，锁定 `surface-probe` 和 `surface-discovery`**

失败测试要锁定：

- `surface-probe` payload 至少包含 `before_graph`、`after_graph`、`probe_action`、`target_region`、`resolved_uncertainty`
- `surface-discovery` payload 至少包含 `discovery_kind`、`discovery_fingerprint`、`region_ref`、`candidate_capability`
- 同一 session 内同一 discovery fingerprint 不得重复落账

- [ ] **Step 4: 跑失败测试，确认当前仓库确实还没这条链**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k "probe or discovery" -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k "probe or discovery" -q
python -m pytest tests/evidence/test_ledger.py -k "surface_probe or surface_discovery" -q
```

Expected: FAIL，因为当前还没有统一 probe engine，也没有 discovery dedupe 正式写链。

- [ ] **Step 5: 实现 `ProbeEngine` 最小正式结构**

最少实现：

- `ProbeDecision`
- `ProbeAction`
- `select_probe_actions(...)`
- `fingerprint_surface_discovery(...)`

要求：

- 三类 surface 共用同一套 decision 输出结构
- 只负责任何低风险“看清楚”动作，不替职业 agent 做业务决策

- [ ] **Step 6: 把 probe 接进三类 surface service**

接线要求：

- 先编译 `before_graph`
- 如果关键节点低置信，则先跑 probe
- probe 后必须 reobserve，并把新 graph 回填到 execution flow
- probe 过程不得绕开现有 evidence ledger

- [ ] **Step 7: 把 discovery 去重落到 evidence**

要求：

- `surface-discovery` 只在首次发现新的 region / control group / capability candidate 时写入
- dedupe key 至少包含 `session_id + surface_kind + discovery_fingerprint`
- 重复 observe 不允许每轮都刷 discovery 证据

- [ ] **Step 8: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py -k "probe or discovery or surface_probe" -q
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/copaw/environments/surface_execution/probe_engine.py src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/evidence/models.py src/copaw/evidence/ledger.py src/copaw/evidence/serialization.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py
git commit -m "feat: add probe engine and surface discovery evidence"
```

### Task 4: 落正式 Transition Miner，统一记录动作前后状态迁移

**Files:**
- Create: `src/copaw/environments/surface_execution/transition_miner.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/document/service.py`
- Modify: `src/copaw/environments/surface_execution/desktop/service.py`
- Modify: `src/copaw/evidence/models.py`
- Modify: `src/copaw/evidence/ledger.py`
- Modify: `src/copaw/evidence/serialization.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/environments/test_document_desktop_surface_execution.py`
- Modify: `tests/evidence/test_ledger.py`

- [ ] **Step 1: 写失败测试，锁定 act 后必须留下共享 diff 结构**

失败测试要锁定：

- `before_graph_ref`
- `after_graph_ref`
- `changed_nodes`
- `new_blockers`
- `resolved_blockers`
- `result_summary`
- `evidence_refs`

- [ ] **Step 2: 写 evidence 失败测试，锁定 `surface-transition` 序列化合同**

失败测试必须证明：

- `surface-transition` 不能只写“成功/失败”
- 必须能回读到动作导致的状态迁移摘要
- 三类 surface 共用同一套 payload 字段

- [ ] **Step 3: 跑失败测试**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py -k transition -q
python -m pytest tests/environments/test_document_desktop_surface_execution.py -k transition -q
python -m pytest tests/evidence/test_ledger.py -k surface_transition -q
```

Expected: FAIL，因为当前只有动作回读，没有正式 transition miner。

- [ ] **Step 4: 实现 `TransitionMiner`**

最少实现：

- `TransitionDelta`
- `mine_transition(...)`
- `summarize_transition(...)`

要求：

- diff 逻辑只基于 graph 节点/边比较
- 不允许为 browser/document/desktop 各写一套私有 diff 逻辑

- [ ] **Step 5: 把 transition evidence 接进执行链**

接线要求：

- 每次正式 act 后都要拿 `before_graph / after_graph` 产出 transition
- `surface-transition` 必须写到统一 ledger
- transition 结果要能反向挂到后续 twin/playbook merge

- [ ] **Step 6: 跑 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py -k "transition or diff or surface_transition" -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/environments/surface_execution/transition_miner.py src/copaw/environments/surface_execution/browser/service.py src/copaw/environments/surface_execution/document/service.py src/copaw/environments/surface_execution/desktop/service.py src/copaw/evidence/models.py src/copaw/evidence/ledger.py src/copaw/evidence/serialization.py tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py
git commit -m "feat: mine surface state transitions into evidence"
```

### Task 5: 落 Capability Twin / Playbook 正式对象、Repository 和 Bootstrap 投影

**Files:**
- Create: `src/copaw/state/models_surface_learning.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_surface_learning.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `tests/state/test_state_store_migration.py`
- Modify: `tests/state/test_surface_learning_repository.py`

- [ ] **Step 1: 写 migration 失败测试，先锁定正式表和索引**

第一轮至少要锁定：

- `surface_capability_twins`
- `surface_playbooks`
- `scope_level + scope_id`
- `status`
- `version`
- `updated_at`

- [ ] **Step 2: 写 repository 失败测试，锁定 active / history / by-scope 读写**

失败测试必须证明：

- twin 能按 scope 查 active
- playbook 能按 scope 查 active
- superseded 历史版本还能回读
- 同 scope 激活新版本后，旧版本状态会被收口

- [ ] **Step 3: 写 bootstrap 失败测试，锁定运行时启动读面**

失败测试必须证明：

- `runtime_bootstrap_query.py` 能拿到 active twin / active playbook
- 返回结构中带 `scope_level`、`scope_id`、`version`、`updated_at`
- bootstrap 只给摘要投影，不直接把完整 graph 原始数据塞进去

- [ ] **Step 4: 跑失败测试**

Run:

```bash
python -m pytest tests/state/test_state_store_migration.py -k surface_learning -q
python -m pytest tests/state/test_surface_learning_repository.py -q
```

Expected: FAIL，因为当前还没有 twin/playbook 正式 schema 和 bootstrap 投影。

- [ ] **Step 5: 实现正式记录与 sqlite repository**

最少对象：

- `SurfaceCapabilityTwinRecord`
- `SurfacePlaybookRecord`

要求：

- twin 属于正式长期知识
- playbook 是 twin 的可执行快读投影
- `RewardProfile` 仍然只是派生读模型，禁止顺手建第三张奖励表

- [ ] **Step 6: 接 runtime bootstrap models / repositories / query**

要求：

- 启动链路能拿到 active twin/playbook 摘要
- bootstrap 输出要能被后续 prompt/read-chain 直接消费
- 这一步只做正式读投影，不做 reward ranking

- [ ] **Step 7: 跑 focused regression**

Run:

```bash
python -m pytest tests/state/test_state_store_migration.py tests/state/test_surface_learning_repository.py -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/copaw/state/models_surface_learning.py src/copaw/state/models.py src/copaw/state/__init__.py src/copaw/state/store.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_surface_learning.py src/copaw/state/repositories/__init__.py src/copaw/state/repositories/sqlite.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_bootstrap_repositories.py src/copaw/app/runtime_bootstrap_query.py tests/state/test_state_store_migration.py tests/state/test_surface_learning_repository.py
git commit -m "feat: add surface learning records and bootstrap projections"
```

### Task 6: 把 `transition -> twin/playbook -> reward` 写链正式串起来

**Files:**
- Create: `src/copaw/learning/surface_capability_service.py`
- Create: `src/copaw/learning/surface_reward_service.py`
- Modify: `src/copaw/learning/models.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Modify: `tests/app/test_learning_api.py`
- Modify: `tests/app/test_phase2_read_surface_unification.py`
- Modify or Create: `tests/kernel/test_main_brain_scope_snapshot_service.py`

- [ ] **Step 1: 写失败测试，锁定 transition/discovery 会同步刷新 twin/playbook**

失败测试必须证明：

- 新 `surface-transition` 会触发 twin merge
- 新 `surface-discovery` 会补充 capability candidate
- 同 scope 下新激活版本会 supersede 旧 active 版本

- [ ] **Step 2: 写失败测试，锁定 reward ranking 只来自正式目标**

失败测试要证明 reward ranking 读取的是：

- `StrategyMemory`
- `OperatingLane`
- `Assignment`
- role/profession success criteria

而不是 surface provider 自己硬写优先级。

- [ ] **Step 3: 写失败测试，锁定写链会 dirty-mark 对应 scope snapshot**

失败测试必须证明：

- `transition -> twin activation -> reward refresh` 后，会调用 `mark_dirty(...)`
- dirty 的是对应 scope，不是把全局缓存乱清一遍
- 下一次 scope snapshot 构建会读到新版本，不是旧缓存

- [ ] **Step 4: 跑失败测试**

Run:

```bash
python -m pytest tests/app/test_learning_api.py -k "surface or reward" -q
python -m pytest tests/app/test_phase2_read_surface_unification.py -k reward -q
python -m pytest tests/kernel/test_main_brain_scope_snapshot_service.py -q
```

Expected: FAIL，因为当前写链还没有正式串到 twin/playbook/reward，也没有 cache dirty 约束测试。

- [ ] **Step 5: 实现 learning 写链**

最少实现：

- `merge_transition_into_twin(...)`
- `project_active_playbook(...)`
- `refresh_reward_ranking(...)`

要求：

- 第一轮只做同步、进程内写链
- 不引入新的队列、后台 runtime、独立 reward worker
- 失败时要 fail-closed，不允许半写半读

- [ ] **Step 6: 接 `mark_dirty(...)`**

要求：

- twin activation、playbook projection、reward refresh 完成后，立刻 dirty-mark 对应 scope
- scope 不明确时宁可显式降级为整会话 dirty，也不能静默不刷缓存

- [ ] **Step 7: 跑 focused regression**

Run:

```bash
python -m pytest tests/app/test_learning_api.py tests/app/test_phase2_read_surface_unification.py tests/kernel/test_main_brain_scope_snapshot_service.py -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/copaw/learning/surface_capability_service.py src/copaw/learning/surface_reward_service.py src/copaw/learning/models.py src/copaw/learning/service.py src/copaw/app/routers/learning.py src/copaw/kernel/main_brain_scope_snapshot_service.py tests/app/test_learning_api.py tests/app/test_phase2_read_surface_unification.py tests/kernel/test_main_brain_scope_snapshot_service.py
git commit -m "feat: wire surface transitions into twin playbook and reward refresh"
```

### Task 7: 把 prompt / scope snapshot / Runtime Center 后端读链统一改掉

**Files:**
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Modify: `tests/kernel/test_memory_recall_integration.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify or Create: `tests/app/test_runtime_center_surface_learning_api.py`
- Modify: `tests/app/test_runtime_center_knowledge_api.py`

- [ ] **Step 1: 写失败测试，锁定 query prompt 读取 active playbook / reward ranking**

失败测试必须证明：

- `query_execution_prompt.py` 会读取 active playbook 摘要
- 同一 scope 下读取 active reward ranking
- prompt 读链顺序一致，不再各自找私有 fallback

- [ ] **Step 2: 写失败测试，锁定 main-brain scope snapshot 读新版本而不是旧缓存**

失败测试必须证明：

- snapshot 第一次读到 version N
- 写链刷新后标脏
- 下一次 snapshot 必须读到 version N+1
- 不允许 stable cache hit 把旧 ranking / 旧 playbook 顶回来

- [ ] **Step 3: 写失败测试，锁定 Runtime Center / Knowledge 后端聚合合同**

至少要返回：

- live graph 摘要
- 最近 `surface-probe / surface-transition / surface-discovery`
- active twin 列表
- active playbook
- reward ranking
- `scope_level / scope_id / version / updated_at`

- [ ] **Step 4: 跑失败测试**

Run:

```bash
python -m pytest tests/kernel/test_memory_recall_integration.py -k "surface or playbook or reward" -q
python -m pytest tests/kernel/test_main_brain_chat_service.py -k "surface or snapshot or reward" -q
python -m pytest tests/app/test_runtime_center_surface_learning_api.py tests/app/test_runtime_center_knowledge_api.py -q
```

Expected: FAIL，因为当前 prompt / snapshot / Runtime Center 还没有统一吃这套正式读链。

- [ ] **Step 5: 实现后端统一读面**

要求：

- `runtime_center_payloads.py` 成为 Runtime Center / Knowledge 的统一序列化边界
- Runtime Center 首页只给摘要读面
- 不允许把完整 graph 原始 payload 直接下发给主脑驾驶舱

- [ ] **Step 6: 跑 focused regression**

Run:

```bash
python -m pytest tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_surface_learning_api.py tests/app/test_runtime_center_knowledge_api.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/kernel/query_execution_prompt.py src/copaw/kernel/main_brain_scope_snapshot_service.py src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/runtime_center_routes_knowledge.py src/copaw/app/routers/runtime_center_routes_memory.py src/copaw/app/routers/runtime_center_payloads.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_surface_learning_api.py tests/app/test_runtime_center_knowledge_api.py
git commit -m "feat: unify surface learning read chain across prompt and runtime center"
```

### Task 8: 补前端可见化读面，并加 stale response 防护

**Files:**
- Modify: `console/src/runtime/runtimeSurfaceClient.ts`
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: 写 Knowledge 页失败测试，锁定正式 surface 读面板块**

至少要显示：

- 当前 live graph 摘要
- 最近 probe / transition / discovery
- active capability twins
- active playbook
- reward ranking

- [ ] **Step 2: 写 Runtime Center hook 失败测试，锁定 stale response 不覆盖新版本**

失败测试必须证明：

- 两次请求乱序返回时，只保留最新 `version / updated_at / request_seq`
- 旧响应不能把新 twin / playbook / ranking 覆盖掉

- [ ] **Step 3: 写 MainBrainCockpitPanel 失败测试，锁定首页只显示摘要**

失败测试必须证明：

- 首页展示摘要、推荐能力、最近变化
- 不展示原始 graph payload 明细
- 没数据时只显示空态，不拼假数据

- [ ] **Step 4: 跑失败测试**

Run:

```bash
cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: FAIL，因为当前前端还没有完整的 surface learning 读面和 stale response 防护。

- [ ] **Step 5: 实现前端读模型与简化展示**

要求：

- `runtimeSurfaceClient.ts` 只消费正式后端聚合
- `useRuntimeCenter.ts` 要对比响应版本或时间戳，拒绝旧响应回灌
- Knowledge 页负责看全量读面
- MainBrainCockpit 只负责看摘要

- [ ] **Step 6: 跑 focused regression**

Run:

```bash
cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add console/src/runtime/runtimeSurfaceClient.ts console/src/pages/Knowledge/index.tsx console/src/pages/Knowledge/index.test.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: show surface learning summary in knowledge and runtime center"
```

### Task 9: 跑真实分层验收，并把诚实边界写死

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `UNIFIED_ACCEPTANCE_STANDARD.md`（仅当需要新增 surface 专项验收示例时）
- Modify or Create: `tests/app/test_surface_graph_live_smoke.py`
- Modify or Create: `tests/app/test_surface_graph_soak.py`
- Test: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_document_desktop_surface_execution.py`
- Test: `tests/evidence/test_ledger.py`
- Test: `tests/state/test_state_store_migration.py`
- Test: `tests/state/test_sqlite_repositories.py`
- Test: `tests/state/test_surface_learning_repository.py`
- Test: `tests/kernel/test_memory_recall_integration.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_scope_snapshot_service.py`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/test_runtime_center_knowledge_api.py`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/app/test_runtime_center_surface_learning_api.py`

- [ ] **Step 1: 先补 gated live/soak pytest 文件，不再写假命令**

要求：

- `tests/app/test_surface_graph_live_smoke.py` 只在 `COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE=1` 时运行
- `tests/app/test_surface_graph_soak.py` 只在 `COPAW_RUN_SURFACE_GRAPH_SOAK=1` 时运行
- 宿主前提不满足时要 `SKIP`，不能假装通过

- [ ] **Step 2: 跑 L1/L2 focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/environments/test_document_desktop_surface_execution.py tests/evidence/test_ledger.py tests/state/test_state_store_migration.py tests/state/test_sqlite_repositories.py tests/state/test_surface_learning_repository.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_main_brain_scope_snapshot_service.py tests/app/test_learning_api.py tests/app/test_runtime_center_knowledge_api.py tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_surface_learning_api.py tests/app/test_phase2_read_surface_unification.py -q
cmd /c npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 3: 跑 L3 live smoke**

必须至少覆盖：

- 真浏览器 `observe -> probe -> act -> diff`
- 真文档 `observe -> act -> reobserve`
- 真桌面 `observe -> blocker detect -> probe`

Run:

```bash
$env:COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE='1'; python -m pytest tests/app/test_surface_graph_live_smoke.py -q -rs
```

Expected: PASS，或者因为宿主条件不满足而被诚实 `SKIP`；不允许再写不存在的 `scripts/channel_live_smoke.py`

- [ ] **Step 4: 跑 L4 long soak**

必须至少覆盖：

- 多轮 graph 不脏
- twin 不串 scope
- reward ranking 不被旧缓存覆盖
- 重启恢复后还能续同一学习链

Run:

```bash
$env:COPAW_RUN_SURFACE_GRAPH_SOAK='1'; python -m pytest tests/app/test_surface_graph_soak.py -q -rs
```

Expected: PASS，或者被诚实 `SKIP` 并明确记录原因

- [ ] **Step 5: 更新 `TASK_STATUS.md`**

必须逐条写清：

- 哪些条目只到 `L1`
- 哪些条目到 `L2`
- 哪些条目跑了 `L3`
- 哪些条目跑了 `L4`
- 没跑 live/soak 的原因

- [ ] **Step 6: 如果需要，补 `UNIFIED_ACCEPTANCE_STANDARD.md` 的 surface 例子**

只补口径，不补宣传性表述。

- [ ] **Step 7: Commit**

```bash
git add TASK_STATUS.md UNIFIED_ACCEPTANCE_STANDARD.md tests/app/test_surface_graph_live_smoke.py tests/app/test_surface_graph_soak.py
git commit -m "test: add surface graph acceptance gates and status"
```

### Task 10: 真实收口标准

**Files:**
- Future acceptance gate only

- [ ] **Step 1: 不得把 graph compiler 说成整套完成**
- [ ] **Step 2: 不得把 probe/discovery/evidence 说成 capability twin 已完成**
- [ ] **Step 3: 不得把 twin/playbook 表建好说成 reward/read-chain 已完成**
- [ ] **Step 4: 不得把 L1/L2 说成任意职业真实长链都通过**
- [ ] **Step 5: 只有 graph/probe/diff/twin/reward/read-chain/UI/L3/L4 全部齐了，才能对外说这条 spec 完成**

---

## 当前诚实状态

- 这份 implementation plan 现在是施工蓝图，不是“代码已完成”声明。
- 当前仓库已完成的是：
  - shared browser/document/desktop substrate 基线
  - guided frontdoor 基线
  - 这份 spec / implementation plan 文档
- 当前仓库还没完成的是：
  - `SurfaceGraphSnapshot` 正式 runtime projection
  - 统一 `ProbeEngine`
  - 统一 `TransitionMiner`
  - `SurfaceCapabilityTwinRecord / SurfacePlaybookRecord`
  - goal-conditioned `reward ranking`
  - prompt / scope snapshot / Runtime Center 正式统一读链
  - 这整套链路的 `L3/L4` 真实验收
