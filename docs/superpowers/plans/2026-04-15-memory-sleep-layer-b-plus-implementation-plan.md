# Memory Sleep Layer B+ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `truth-first` 共享记忆底座上正式落地 `B+` 睡眠整理层，补齐 dirty-scope、sleep job、digest/alias/merge/soft-rule/conflict 提案、主读链接线与 operator API。

**Architecture:** 这轮不新增第二套记忆真相源。新增的 sleep objects 全部作为 canonical `state / evidence / graph projection / strategy / formal memory` 上的派生层落库，由 `MemorySleepService` 统一负责 dirty-scope 管理、夜间整理执行、结果写入与主读层 overlay；`MemoryRecallService / MemorySurfaceService / Runtime Center memory routes` 只消费这套派生产物，不直接发明平行逻辑。

**Tech Stack:** Python, Pydantic, SQLite state store, FastAPI, pytest

## Current Landed Status

截至当前仓库状态，这份计划的 Task 1 ~ Task 3 已进入已落地状态，不再是纯待施工草案。

当前已经落地的内容：

- 正式状态对象除了初始 6 类 sleep artifact 外，已补到：
  - `IndustryMemoryProfileRecord`
  - `WorkContextMemoryOverlayRecord`
  - `MemoryStructureProposalRecord`
- `MemorySleepService` 已能为：
  - `industry` scope 生成 `IndustryMemoryProfileRecord`
  - `work_context` scope 生成 `WorkContextMemoryOverlayRecord`
  - `work_context` scope 生成 `MemoryStructureProposalRecord`
- Runtime Center 已新增正式读路由：
  - `GET /runtime-center/memory/sleep/industry-profiles`
  - `GET /runtime-center/memory/sleep/work-context-overlays`
  - `GET /runtime-center/memory/sleep/structure-proposals`
- Recall / profile 主读链已开始显式暴露：
  - `read_layer`
  - `overlay_id`
  - `industry_profile_id`
- `/runtime-center/memory/profiles*` 已和 `MemoryProfileService` 对齐，不再停留在旧的首条 summary 拼装逻辑

当前这份计划剩余的主要意义：

- 作为 B+ 实现范围与边界的施工清单
- 继续约束 Task 4 的聚合回归、相邻回归和 diff sanity

---

### Task 1: 落地 B+ 状态层对象、表结构与仓储

**Files:**
- Modify: `src/copaw/state/models_memory.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_memory_sleep.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Test: `tests/state/test_memory_sleep_repository.py`

- [ ] **Step 1: 写 failing repository tests**

覆盖：
- dirty scope 标记可持久化
- sleep job 可写入/查询
- digest / alias / merge / soft-rule / conflict proposal 可按 scope 查询
- active/superseded/pending 等状态读写正确

- [ ] **Step 2: 运行 repository tests，确认先失败**

Run: `python -m pytest tests/state/test_memory_sleep_repository.py -q -p no:cacheprovider`

- [ ] **Step 3: 实现状态层模型与 SQLite 仓储**

新增/补齐对象：
- `MemorySleepScopeStateRecord`
- `MemorySleepJobRecord`
- `MemoryScopeDigestRecord`
- `MemoryAliasMapRecord`
- `MemoryMergeResultRecord`
- `MemorySoftRuleRecord`
- `MemoryConflictProposalRecord`

并把它们接入：
- state exports
- runtime repositories
- SQLite schema

- [ ] **Step 4: 重新运行 repository tests，确认转绿**

Run: `python -m pytest tests/state/test_memory_sleep_repository.py -q -p no:cacheprovider`

### Task 2: 落地 MemorySleepService 与 dirty-scope 主链

**Files:**
- Create: `src/copaw/memory/sleep_service.py`
- Create: `src/copaw/memory/sleep_inference_service.py`
- Modify: `src/copaw/memory/__init__.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/state/strategy_memory_service.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/state/test_memory_sleep_service.py`

- [ ] **Step 1: 写 failing service tests**

覆盖：
- knowledge/strategy/retain 写入后会正确标记 dirty scope
- 手动运行 sleep job 会生成 digest / alias / merge / soft-rule / conflict proposal
- 低风险 soft-rule 会自动生效并保留回滚信息
- 再次运行同 scope 时会 supersede 旧 digest/job，并清理 dirty 标记
- 模型不可用时 deterministic fallback 仍能生成结构化结果

- [ ] **Step 2: 运行 service tests，确认先失败**

Run: `python -m pytest tests/state/test_memory_sleep_service.py -q -p no:cacheprovider`

- [ ] **Step 3: 实现 MemorySleepService / inference / dirty marker wiring**

要求：
- `industry / work_context` 为首轮正式 scope
- inference 优先尝试 active chat model structured output
- 模型失败时回落 deterministic compiler
- `run_sleep(...) / list_* / resolve_scope_overlay(...) / expand_alias_terms(...) / run_due_sleep_jobs(...) / run_idle_catchup(...)` 形成正式服务面

- [ ] **Step 4: 重新运行 service tests，确认转绿**

Run: `python -m pytest tests/state/test_memory_sleep_service.py -q -p no:cacheprovider`

### Task 3: 接 recall / surface / Runtime Center memory API 主读链

**Files:**
- Modify: `src/copaw/memory/recall_service.py`
- Modify: `src/copaw/memory/surface_service.py`
- Modify: `src/copaw/app/routers/runtime_center_dependencies.py`
- Modify: `src/copaw/app/routers/runtime_center_request_models.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Test: `tests/memory/test_surface_service.py`
- Test: `tests/state/test_memory_services.py`
- Test: `tests/app/test_runtime_center_memory_api.py`

- [ ] **Step 1: 写 failing read-chain/API tests**

覆盖：
- recall 会在 canonical profile 后优先返回 sleep digest / merge / soft-rule，再回落 raw text memory
- alias map 会扩展 recall query
- memory surface/profile 会优先显示 digest/current_constraints/current_focus
- `/runtime-center/memory/surface` 会返回 `sleep` block
- `/runtime-center/memory/sleep/*` 路由可查看 dirty scopes、jobs、digests、rules、conflicts，并可手动触发 run

- [ ] **Step 2: 运行 targeted tests，确认先失败**

Run: `python -m pytest tests/memory/test_surface_service.py tests/state/test_memory_services.py tests/app/test_runtime_center_memory_api.py -q -p no:cacheprovider`

- [ ] **Step 3: 实现读链接线与 operator API**

要求：
- 不改 raw canonical fact truth
- 只改 read priority / overlay / operator visibility
- API 明确区分 manual run 与 query surface

- [ ] **Step 4: 重新运行 targeted tests，确认转绿**

Run: `python -m pytest tests/memory/test_surface_service.py tests/state/test_memory_services.py tests/app/test_runtime_center_memory_api.py -q -p no:cacheprovider`

### Task 4: 聚合验证 B+ 闭环

**Files:**
- Verify only

- [ ] **Step 1: 跑 B+ focused aggregate verification**

Run: `python -m pytest tests/state/test_memory_sleep_repository.py tests/state/test_memory_sleep_service.py tests/memory/test_surface_service.py tests/state/test_memory_services.py tests/app/test_runtime_center_memory_api.py -q -p no:cacheprovider`

- [ ] **Step 2: 跑相邻 memory regression**

Run: `python -m pytest tests/memory/test_activation_service.py tests/memory/test_knowledge_graph_service.py tests/memory/test_knowledge_writeback_service.py tests/state/test_truth_first_memory_state.py tests/state/test_truth_first_memory_recall.py -q -p no:cacheprovider`

- [ ] **Step 3: 跑 diff sanity**

Run: `git diff --check`
