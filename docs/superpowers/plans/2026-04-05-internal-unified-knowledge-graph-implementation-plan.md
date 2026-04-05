# Internal Unified Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CoPaw 现有 memory / activation / strategy / planning / execution evidence 收成统一内部知识图谱主链，并让主脑通过“任务子图”稳定消费它。

**Architecture:** 保留现有 truth-first memory、activation layer 和 formal planning chain，不新建第二套 truth；通过统一对象模型、统一关系模型、统一任务子图激活入口、统一执行后回写入口，把知识层从“结构化记忆增强”升级为“主脑可用的正式知识系统”。

**Tech Stack:** Python, Pydantic, existing `state/ memory/ compiler/ kernel/ industry/ app` services, pytest

---

## File Map

### Existing files that should remain canonical

- `src/copaw/memory/activation_service.py`
  - 当前 activation 主入口；后续应升级为任务子图激活前门
- `src/copaw/memory/activation_models.py`
  - 当前 activation 输入输出模型；后续扩成统一任务子图 contract
- `src/copaw/memory/derived_index_service.py`
  - 当前事实/实体/观点/关系派生层；后续承载统一关系派生与 rebuild seam
- `src/copaw/state/models_memory.py`
  - 当前 memory view / fact index 模型；后续补事件、约束、关系属性口径
- `src/copaw/state/strategy_memory_service.py`
  - 当前正式战略真相服务；后续作为执行认知图谱正式节点接线
- `src/copaw/industry/report_synthesis.py`
  - 当前报告综合；后续接知识回写
- `src/copaw/industry/service_report_closure.py`
  - 当前 report closeout；后续接知识回写与观点更新
- `src/copaw/compiler/planning/cycle_planner.py`
  - 当前 cycle planner；后续显式消费任务子图
- `src/copaw/compiler/planning/assignment_planner.py`
  - 当前 assignment planner；后续显式消费任务子图
- `src/copaw/kernel/main_brain_execution_planner.py`
  - 当前主脑执行规划入口；后续接统一激活前门
- `src/copaw/kernel/query_execution_runtime.py`
  - 当前 runtime 执行主链；后续接执行期图谱经验激活和 outcome 回写
- `src/copaw/app/routers/runtime_center_routes_memory.py`
  - 当前 memory read surface；后续补图谱读面
- `src/copaw/app/test_runtime_center_memory_api.py`
  - 读面验证

### New files to add

- `src/copaw/memory/knowledge_graph_models.py`
  - 统一内部知识图谱对象模型与关系属性模型
- `src/copaw/memory/knowledge_graph_service.py`
  - 统一知识图谱 façade；提供入图、激活、回写入口
- `src/copaw/memory/subgraph_activation_service.py`
  - 专门负责任务子图激活
- `src/copaw/memory/knowledge_writeback_service.py`
  - 专门负责 report / execution / discussion 回写
- `tests/memory/test_knowledge_graph_models.py`
- `tests/memory/test_subgraph_activation_service.py`
- `tests/memory/test_knowledge_writeback_service.py`
- `tests/compiler/test_planning_subgraph_integration.py`
- `tests/kernel/test_execution_knowledge_writeback.py`

### Existing docs to keep in sync

- `docs/superpowers/specs/2026-04-05-internal-unified-knowledge-graph-design.md`
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- `TASK_STATUS.md`

---

### Task 1: 定义统一知识图谱对象模型

**Files:**
- Create: `src/copaw/memory/knowledge_graph_models.py`
- Modify: `src/copaw/memory/activation_models.py`
- Modify: `src/copaw/state/models_memory.py`
- Test: `tests/memory/test_knowledge_graph_models.py`

- [ ] **Step 1: 写对象模型测试**

覆盖以下断言：

- 世界认知对象至少包含 `entity / event / fact / opinion / evidence / constraint`
- 关系对象包含 `relation_type / source_id / target_id / evidence_refs / confidence / scope / valid_from / valid_to / status`
- 执行认知对象支持挂接 `strategy / lane / backlog / cycle / assignment / report / capability / environment / runtime_outcome`
- 人类边界对象支持 `instruction / approval / rejection / discussion / consensus / preference`

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/memory/test_knowledge_graph_models.py -q`

- [ ] **Step 3: 实现最小对象模型**

在 `knowledge_graph_models.py` 中添加：

- 节点类型枚举
- 关系类型枚举
- 统一节点模型
- 统一关系模型
- 任务子图模型
- 回写变更模型

同时最小补充 `activation_models.py` / `models_memory.py` 的兼容投影。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/memory/test_knowledge_graph_models.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/memory/knowledge_graph_models.py src/copaw/memory/activation_models.py src/copaw/state/models_memory.py tests/memory/test_knowledge_graph_models.py
git commit -m "feat: add unified knowledge graph models"
```

### Task 2: 把 activation 升级成统一任务子图激活前门

**Files:**
- Create: `src/copaw/memory/subgraph_activation_service.py`
- Modify: `src/copaw/memory/activation_service.py`
- Modify: `src/copaw/memory/derived_index_service.py`
- Modify: `src/copaw/state/strategy_memory_service.py`
- Test: `tests/memory/test_subgraph_activation_service.py`
- Test: `tests/memory/test_activation_service.py`

- [ ] **Step 1: 写失败测试**

覆盖以下场景：

- strategy + lane + backlog + assignment + capability + evidence 能激活成同一任务子图
- 子图激活遵守 `work_context > task > agent > industry > global`
- 只返回排序后的局部子图，不回全量节点

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py -q`

- [ ] **Step 3: 实现子图激活服务**

要求：

- `activation_service` 不再只是 recall 组装器，而是统一前门
- `subgraph_activation_service` 负责：
  - 种子抽取
  - 范围收敛
  - 关系扩散
  - 排序裁切
- `strategy_memory_service` 继续作为正式战略真相，不复制第二套战略 cache

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py tests/state/test_strategy_memory_contract.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/memory/subgraph_activation_service.py src/copaw/memory/activation_service.py src/copaw/memory/derived_index_service.py src/copaw/state/strategy_memory_service.py tests/memory/test_subgraph_activation_service.py tests/memory/test_activation_service.py
git commit -m "feat: add task subgraph activation front door"
```

### Task 3: 建立统一知识回写入口

**Files:**
- Create: `src/copaw/memory/knowledge_writeback_service.py`
- Modify: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/state/reporting_service.py`
- Test: `tests/memory/test_knowledge_writeback_service.py`
- Test: `tests/industry/test_report_synthesis.py`

- [ ] **Step 1: 写失败测试**

覆盖以下场景：

- report 能回写事实、观点、证据和关系更新
- execution outcome 能回写 failure / recovery pattern
- discussion / approval / rejection 能回写人类边界对象，而不是污染事实层

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/memory/test_knowledge_writeback_service.py tests/industry/test_report_synthesis.py -q`

- [ ] **Step 3: 实现最小回写服务**

要求：

- 回写入口统一，不允许 planner / report / runtime 各自私写
- 支持：
  - 新事实
  - 新事件
  - 新证据
  - 观点更新
  - 关系更新
  - failure / recovery 模式更新
- 未验证推断只能降级为 opinion，不得直接落 fact

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/memory/test_knowledge_writeback_service.py tests/industry/test_report_synthesis.py tests/state/test_reporting_service.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/memory/knowledge_writeback_service.py src/copaw/industry/report_synthesis.py src/copaw/industry/service_report_closure.py src/copaw/state/reporting_service.py tests/memory/test_knowledge_writeback_service.py tests/industry/test_report_synthesis.py
git commit -m "feat: add unified knowledge graph writeback"
```

### Task 4: 让 planner 明确消费任务子图

**Files:**
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Modify: `src/copaw/compiler/planning/assignment_planner.py`
- Modify: `src/copaw/kernel/main_brain_execution_planner.py`
- Test: `tests/compiler/test_planning_subgraph_integration.py`
- Test: `tests/compiler/test_strategy_compiler.py`

- [ ] **Step 1: 写失败测试**

覆盖以下场景：

- cycle planner 明确消费任务子图中的 strategy / lane / backlog / evidence / constraint
- assignment planner 能消费 capability / environment / failure pattern
- planner 不再只靠 prompt 文本和局部排序

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/compiler/test_planning_subgraph_integration.py tests/compiler/test_strategy_compiler.py -q`

- [ ] **Step 3: 实现最小接线**

要求：

- 主脑规划前必须经过统一子图激活
- planner 输入中显式包含子图
- 不允许再在 planner 内部复制一套知识召回逻辑

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/compiler/test_planning_subgraph_integration.py tests/compiler/test_strategy_compiler.py tests/compiler/test_planning_models.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/compiler/planning/cycle_planner.py src/copaw/compiler/planning/assignment_planner.py src/copaw/kernel/main_brain_execution_planner.py tests/compiler/test_planning_subgraph_integration.py
git commit -m "feat: wire planning to task subgraphs"
```

### Task 5: 让 execution 明确消费和回写知识图谱

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/state/execution_feedback.py`
- Test: `tests/kernel/test_execution_knowledge_writeback.py`
- Test: `tests/kernel/test_runtime_outcome.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: 写失败测试**

覆盖以下场景：

- execution 前能取到 capability / environment / risk / historical failure/recovery 子图
- execution 结束后能把 outcome、failure pattern、recovery path 正式回写
- cancelled / failed / blocked / recovered 的写回语义可区分

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/kernel/test_execution_knowledge_writeback.py tests/kernel/test_runtime_outcome.py tests/kernel/test_query_execution_runtime.py -q`

- [ ] **Step 3: 实现最小接线**

要求：

- runtime 不再把执行经验只留在字符串 summary
- outcome 进入统一知识回写服务
- failure / recovery pattern 成为正式执行认知节点或关系

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/kernel/test_execution_knowledge_writeback.py tests/kernel/test_runtime_outcome.py tests/kernel/test_query_execution_runtime.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/kernel/query_execution_runtime.py src/copaw/kernel/runtime_outcome.py src/copaw/state/execution_feedback.py tests/kernel/test_execution_knowledge_writeback.py
git commit -m "feat: wire execution outcomes into knowledge graph"
```

### Task 6: 增加 Runtime Center 图谱读面

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/app/runtime_center/execution_runtime_projection.py`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/app/test_runtime_center_knowledge_api.py`

- [ ] **Step 1: 写失败测试**

覆盖以下场景：

- Runtime Center 能读当前任务子图摘要
- 能读关键实体/观点/证据/约束摘要
- 能读 execution failure / recovery pattern 摘要

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_knowledge_api.py -q`

- [ ] **Step 3: 实现最小读面**

要求：

- 读面只暴露正式 summary，不直接暴露内部所有原始节点
- 强调“当前任务子图”和“最近回写变化”
- 不引入第二套前端 memory 心智

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_knowledge_api.py -q`

- [ ] **Step 5: 提交**

```bash
git add src/copaw/app/routers/runtime_center_routes_memory.py src/copaw/app/runtime_center/execution_runtime_projection.py tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_knowledge_api.py
git commit -m "feat: expose runtime knowledge graph summaries"
```

### Task 7: 文档同步与总回归

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-05-internal-unified-knowledge-graph-design.md`
- Optional Modify: `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`

- [ ] **Step 1: 更新状态板**

补：

- 已完成哪些对象层改造
- 已完成哪些主链接线
- 当前剩余边界

- [ ] **Step 2: 回写设计文档的现实边界**

把实现后真正落地的：

- 节点
- 关系
- 激活入口
- 回写入口
- Runtime Center 读面

回写到设计文档。

- [ ] **Step 3: 跑 focused 回归**

Run:

```bash
python -m pytest tests/memory/test_knowledge_graph_models.py tests/memory/test_subgraph_activation_service.py tests/memory/test_knowledge_writeback_service.py tests/compiler/test_planning_subgraph_integration.py tests/kernel/test_execution_knowledge_writeback.py tests/app/test_runtime_center_memory_api.py tests/app/test_runtime_center_knowledge_api.py -q
```

- [ ] **Step 4: 跑相邻主链回归**

Run:

```bash
python -m pytest tests/state/test_strategy_memory_contract.py tests/state/test_truth_first_memory_contract.py tests/memory/test_activation_service.py tests/industry/test_report_synthesis.py tests/compiler/test_strategy_compiler.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_runtime_outcome.py -q
```

- [ ] **Step 5: 提交**

```bash
git add TASK_STATUS.md docs/superpowers/specs/2026-04-05-internal-unified-knowledge-graph-design.md docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md
git commit -m "docs: close unified knowledge graph implementation"
```

---

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7

Do not start Runtime Center read surfaces before the activation / writeback contracts are stable.

Do not expand external knowledge sources during this plan.

Do not introduce a second memory truth or a graph-database-first rewrite in this phase.

---

## Exit Criteria

This plan is complete only when:

- CoPaw has one explicit internal knowledge graph contract
- planner consumes task subgraphs
- execution writes outcomes back into the graph
- report synthesis writes structured knowledge back into the graph
- Runtime Center can show current task subgraph summaries
- old knowledge can be downgraded / replaced / contradicted rather than only accumulated

