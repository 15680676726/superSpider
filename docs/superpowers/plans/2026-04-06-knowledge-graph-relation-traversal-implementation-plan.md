# Knowledge Graph Relation Traversal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 CoPaw 现有知识图谱产出关键关系路径，并让 planner / execution 真正消费这些路径来改变计划顺序和执行顺序。

**Architecture:** 保留现有 truth-first memory、TaskSubgraph、planning chain 和 execution chain，不引入第二套 memory truth。新增一层轻量的关系路径合同和 traversal policy，先在 activation 层产出路径包，再把路径包接进 planner 与 assignment execution contract。

**Tech Stack:** Python, Pydantic, pytest, existing `memory / compiler / kernel / app` modules

---

## File Map

### New files

- `src/copaw/memory/relation_traversal.py`
  - 关系分层、typed traversal policy、关键路径打包
- `tests/memory/test_relation_traversal.py`
  - 关系路径模型与策略单元测试

### Existing files to modify

- `src/copaw/memory/knowledge_graph_models.py`
  - 增加关系路径运行时对象
- `src/copaw/memory/activation_models.py`
  - 扩展 activation result / task subgraph 对路径包的承载
- `src/copaw/memory/activation_service.py`
  - 接 typed traversal，产出关键路径包
- `src/copaw/memory/subgraph_activation_service.py`
  - 把路径包投影进 subgraph metadata
- `src/copaw/compiler/planning/models.py`
  - 投影 task subgraph 路径包为 planner 可消费的 focus contract
- `src/copaw/compiler/planning/cycle_planner.py`
  - 根据 dependency/blocker/contradiction/support path 改变选题顺序
- `src/copaw/compiler/planning/assignment_planner.py`
  - 根据路径包生成更强的 checkpoints / sidecar plan / execution ordering hints
- `src/copaw/compiler/compiler.py`
  - 把 assignment sidecar path guidance 暴露进 compiled task seed / compiler payload
- `src/copaw/kernel/query_execution_confirmation.py`
  - 把 execution feedback prompt lines 扩成 path-aware execution hints

### Existing tests to extend

- `tests/memory/test_knowledge_graph_models.py`
- `tests/memory/test_subgraph_activation_service.py`
- `tests/memory/test_activation_service.py`
- `tests/compiler/test_planning_subgraph_integration.py`
- `tests/kernel/test_memory_recall_integration.py`
- `tests/kernel/query_execution_environment_parts/lifecycle.py`
- `tests/app/test_goals_api.py`
- `tests/app/industry_api_parts/bootstrap_lifecycle.py`

---

### Task 1: 定义关系路径运行时合同

**Files:**
- Create: `src/copaw/memory/relation_traversal.py`
- Modify: `src/copaw/memory/knowledge_graph_models.py`
- Modify: `src/copaw/memory/activation_models.py`
- Test: `tests/memory/test_relation_traversal.py`
- Test: `tests/memory/test_knowledge_graph_models.py`

- [ ] **Step 1: 写失败测试，覆盖路径对象和分层**

测试至少覆盖：
- `support / contradiction / dependency / blocker / recovery` 五类路径
- 单条路径包含 `path_type / score / node_ids / relation_ids / relation_kinds / summary / evidence_refs / source_refs`
- `TaskSubgraph` 能承载路径包但不把路径包变成正式 truth 对象

- [ ] **Step 2: 运行失败测试确认红灯**

Run: `python -m pytest tests/memory/test_relation_traversal.py tests/memory/test_knowledge_graph_models.py -q`

- [ ] **Step 3: 最小实现关系路径合同**

实现内容：
- 在 `knowledge_graph_models.py` 增加轻量路径模型
- 在 `relation_traversal.py` 定义 relation family、path type、policy helper
- 在 `activation_models.py` 增加 activation result / task subgraph 的路径字段

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/memory/test_relation_traversal.py tests/memory/test_knowledge_graph_models.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/memory/relation_traversal.py src/copaw/memory/knowledge_graph_models.py src/copaw/memory/activation_models.py tests/memory/test_relation_traversal.py tests/memory/test_knowledge_graph_models.py
git commit -m "feat: add relation traversal contracts"
```

### Task 2: 升级 activation 为 typed traversal

**Files:**
- Modify: `src/copaw/memory/activation_service.py`
- Modify: `src/copaw/memory/subgraph_activation_service.py`
- Test: `tests/memory/test_subgraph_activation_service.py`
- Test: `tests/memory/test_activation_service.py`
- Test: `tests/memory/test_relation_traversal.py`

- [ ] **Step 1: 写失败测试，覆盖路径推演**

测试至少覆盖：
- 相同 seed 下，不同 relation kind 会产出不同 path type
- `depends_on / blocks / contradicts / recovers_with / supports` 会真实影响排序
- subgraph metadata 会包含关键路径包，而不只是 `top_relations`

- [ ] **Step 2: 运行失败测试确认红灯**

Run: `python -m pytest tests/memory/test_relation_traversal.py tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py -q`

- [ ] **Step 3: 最小实现 typed traversal**

实现内容：
- activation 先 seed extraction，再 typed traversal，再 path packing
- traversal 优先级先执行关系，再判断关系，再因果关系，最后时间/结构关系
- 限制 hop、每类 path 数量、总输出预算

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/memory/test_relation_traversal.py tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/memory/activation_service.py src/copaw/memory/subgraph_activation_service.py tests/memory/test_relation_traversal.py tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py
git commit -m "feat: add typed relation traversal activation"
```

### Task 3: 让 planner 显式消费关键路径

**Files:**
- Modify: `src/copaw/compiler/planning/models.py`
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Modify: `src/copaw/compiler/planning/assignment_planner.py`
- Test: `tests/compiler/test_planning_subgraph_integration.py`

- [ ] **Step 1: 写失败测试，覆盖 planning 被路径改变**

测试至少覆盖：
- dependency path 会让 cycle planner 优先选“先解前置”的 backlog
- contradiction path 会让 planner 优先走澄清 / 验证分支
- blocker path 会压低不该立刻推进的任务
- assignment planner 会把 recovery / blocker / dependency path 编译进 checkpoint 和 sidecar plan

- [ ] **Step 2: 运行失败测试确认红灯**

Run: `python -m pytest tests/compiler/test_planning_subgraph_integration.py -q`

- [ ] **Step 3: 最小实现 planner path consumption**

实现内容：
- `project_task_subgraph_to_planning_focus()` 输出 path-focused projection
- cycle planner 使用 path type 调整优先级和 relation evidence
- assignment planner 产出 path-driven checkpoints、checklist、execution ordering hints

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/compiler/test_planning_subgraph_integration.py tests/compiler/test_strategy_compiler.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/compiler/planning/models.py src/copaw/compiler/planning/cycle_planner.py src/copaw/compiler/planning/assignment_planner.py tests/compiler/test_planning_subgraph_integration.py
git commit -m "feat: wire planner to relation traversal paths"
```

### Task 4: 让 execution contract 消费路径提示和顺序约束

**Files:**
- Modify: `src/copaw/compiler/compiler.py`
- Modify: `src/copaw/kernel/query_execution_confirmation.py`
- Test: `tests/kernel/test_memory_recall_integration.py`
- Test: `tests/kernel/query_execution_environment_parts/lifecycle.py`
- Test: `tests/app/test_goals_api.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`

- [ ] **Step 1: 写失败测试，覆盖 execution path guidance**

测试至少覆盖：
- compiler payload / task_seed 会带出 path guidance，而不只带 relation ids
- execution prompt / feedback appendix 会显示前置依赖、阻塞链、恢复链提示
- assignment sidecar plan 在 API / bootstrap 主链中保持可见

- [ ] **Step 2: 运行失败测试确认红灯**

Run: `python -m pytest tests/kernel/test_memory_recall_integration.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/test_goals_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`

- [ ] **Step 3: 最小实现 execution 接线**

实现内容：
- `compiler.py` 把 path guidance 暴露进 compiled payload / task seed
- `query_execution_confirmation.py` 增加 path-aware execution hints
- 保持 execution 侧是“排序/提示/守护”，不绕过治理层

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/kernel/test_memory_recall_integration.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/test_goals_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/compiler/compiler.py src/copaw/kernel/query_execution_confirmation.py tests/kernel/test_memory_recall_integration.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/test_goals_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py
git commit -m "feat: expose relation path guidance to execution"
```

### Task 5: 文档收口与完整验收

**Files:**
- Modify: `docs/superpowers/specs/2026-04-06-knowledge-graph-relation-traversal-design.md`
- Modify: `docs/superpowers/plans/2026-04-06-knowledge-graph-relation-traversal-implementation-plan.md`

- [ ] **Step 1: 回写实现边界**

补充：
- 最终落地了哪些 path types
- planner / execution 实际消费到了哪一层
- 哪些被明确排除，没有引入第二套 truth

- [ ] **Step 2: 跑 focused 回归**

Run:

```bash
python -m pytest tests/memory/test_relation_traversal.py tests/memory/test_knowledge_graph_models.py tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py tests/compiler/test_planning_subgraph_integration.py tests/kernel/test_memory_recall_integration.py tests/kernel/query_execution_environment_parts/lifecycle.py -q
```

- [ ] **Step 3: 跑相邻主链回归**

Run:

```bash
python -m pytest tests/compiler/test_strategy_compiler.py tests/app/test_goals_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_runtime_center_api.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_execution_knowledge_writeback.py -q
```

- [ ] **Step 4: 跑知识图谱主链回归**

Run:

```bash
python -m pytest tests/memory/test_knowledge_graph_models.py tests/memory/test_relation_traversal.py tests/memory/test_subgraph_activation_service.py tests/memory/test_knowledge_writeback_service.py tests/compiler/test_planning_subgraph_integration.py tests/kernel/test_execution_knowledge_writeback.py tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_knowledge_api.py -q
```

- [ ] **Step 5: 提交**

```bash
git add docs/superpowers/specs/2026-04-06-knowledge-graph-relation-traversal-design.md docs/superpowers/plans/2026-04-06-knowledge-graph-relation-traversal-implementation-plan.md
git commit -m "docs: close relation traversal implementation"
```

---

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

Do not start planner/execution rewiring before the path contract and activation policy are stable.

Do not introduce any new persistence store during this plan.

Do not convert path packages into canonical truth objects.

---

## Exit Criteria

This plan is complete only when:

- activation can emit 5 typed key path families
- planner changes ordering because of emitted paths
- execution contract exposes path-based ordering hints and safeguards
- historical failure / recovery paths influence later execution
- no second memory truth or graph engine is introduced

