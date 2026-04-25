# Knowledge Activation Layer Design

## Goal

在不新增第二真相源、不回退成 session-first memory 的前提下，为 CoPaw 增加一层“神经元式”知识激活层，让行业长期运行中沉淀下来的战略、事实、经验、报告和证据，不再只是被动存放，而是能在当前 query / task / work context / industry context 下被局部激活、关系扩散、证据回收和排序输出。

一句话目标：

`把现有 truth-first memory 从“能存、能召回”升级为“能联想、能激活、能指导下一步动作”。`

## Problem

CoPaw 当前已经具备正式知识沉淀链，但还缺少一个明确的激活层。

当前已经有：

- `StrategyMemoryRecord`：长期战略与执行约束
- `KnowledgeChunkRecord`：正式知识块
- `MemoryFactIndexRecord`：从知识、报告、evidence、routine 等派生出的事实索引
- `MemoryEntityViewRecord / MemoryOpinionViewRecord / MemoryProfileViewRecord / MemoryEpisodeViewRecord`：反射后的视图
- `MemoryRecallService`：truth-first recall

当前还缺：

- 一个把这些对象组织成“局部知识网络”的正式层
- 一个根据当前上下文激活一组节点并沿关系扩散的统一算法
- 一个结构化输出，告诉主脑/执行位“现在最该想起什么、为什么、下一步怎么做”

## Existing Foundations In Code

本设计直接建立在以下现有代码之上：

- 战略层：
  - `src/copaw/state/strategy_memory_service.py`
  - `src/copaw/state/models_reporting.py`
- 知识层：
  - `src/copaw/state/knowledge_service.py`
  - `src/copaw/state/models_knowledge.py`
- 事实索引与关系提取：
  - `src/copaw/memory/derived_index_service.py`
  - `src/copaw/state/models_memory.py`
- 反射编译层：
  - `src/copaw/memory/reflection_service.py`
- 召回层：
  - `src/copaw/memory/recall_service.py`
- 沉淀入口：
  - `src/copaw/memory/retain_service.py`
  - `src/copaw/state/agent_experience_service.py`
  - `src/copaw/industry/service_report_closure.py`
  - `src/copaw/state/reporting_service.py`

这意味着：

- 本设计不是从零开始
- 本设计不引入新数据库为第一真相
- 本设计是现有 memory/reporting/strategy 层之上的派生激活层

## Design Principles

### 1. 激活层不是新的真相源

正式真相继续来自：

- state
- evidence
- strategy memory
- knowledge chunks
- reports

激活层只做：

- 节点组织
- 关系扩散
- 激活排序
- 结构化输出

### 2. 节点不是关键词

“神经元”不应等于“关键词命中”。

在 CoPaw 里，一个神经元应代表一个知识节点，例如：

- 战略策略
- 已确认事实
- 实体概念
- 观点/偏好/约束
- 连续执行片段
- 当前画像

关键词只是触发器，不是知识本体。

### 3. scope-first 激活优先于全局搜索

激活顺序必须优先围绕当前正式 scope：

`work_context > task > agent > industry > global`

这与现有 truth-first recall 一致，不能被纯文本语义搜索覆盖。

### 4. 激活层服务主脑与执行位，不直接服务 UI 花活

这层的第一服务对象是：

- main brain planning / runtime context
- execution runtime
- report synthesis
- follow-up backlog / replan

前端可视化是后续收益，不是第一目标。

## Canonical Truth Sources

本设计正式承认以下对象是激活层的上游真相：

### Strategic sources

- `StrategyMemoryRecord`

### Fact sources

- `KnowledgeChunkRecord`
- `AgentReportRecord`
- `ReportRecord`
- `RoutineRunRecord`
- `EvidenceRecord`

### Derived factual/index sources

- `MemoryFactIndexRecord`

### Compiled memory views

- `MemoryProfileViewRecord`
- `MemoryEpisodeViewRecord`
- `MemoryEntityViewRecord`
- `MemoryOpinionViewRecord`
- `MemoryRelationViewRecord`

## Knowledge Neuron Types

第一版建议只引入 6 类 neuron。

### 1. `strategy`

来源：

- `StrategyMemoryRecord`

作用：

- 提供长期 mission / north_star / priorities / execution_constraints / evidence_requirements / delegation_policy

### 2. `fact`

来源：

- `MemoryFactIndexRecord`

作用：

- 承载从 knowledge/report/evidence/routine 等派生出的稳定事实

### 3. `entity`

来源：

- `MemoryEntityViewRecord`

作用：

- 表示行业概念、渠道、角色、客户群、失败原因、环境对象等实体

### 4. `opinion`

来源：

- `MemoryOpinionViewRecord`

作用：

- 表示 preference / requirement / caution / recommendation 这类观点性知识

### 5. `profile`

来源：

- `MemoryProfileViewRecord`

作用：

- 表示当前 scope 的稳定画像、当前焦点、偏好、约束、当前 operating context

### 6. `episode`

来源：

- `MemoryEpisodeViewRecord`

作用：

- 表示一段连续执行过程的结构化经验片段

## Proposed Object Shapes

### `KnowledgeNeuron`

```python
class KnowledgeNeuron(BaseModel):
    neuron_id: str
    kind: Literal["strategy", "fact", "entity", "opinion", "profile", "episode"]

    scope_type: str
    scope_id: str
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None

    title: str
    summary: str = ""
    content_excerpt: str = ""

    entity_keys: list[str] = []
    opinion_keys: list[str] = []
    tags: list[str] = []

    source_refs: list[str] = []
    evidence_refs: list[str] = []

    confidence: float = 0.0
    quality_score: float = 0.0
    freshness_score: float = 0.0
    activation_score: float = 0.0

    metadata: dict[str, Any] = {}
```

### `ActivationInput`

```python
class ActivationInput(BaseModel):
    query_text: str

    work_context_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    industry_instance_id: str | None = None

    owner_agent_id: str | None = None
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str | None = None
    current_phase: str | None = None

    include_strategy: bool = True
    include_reports: bool = True
    limit: int = 12
```

### `ActivationResult`

```python
class ActivationResult(BaseModel):
    query: str
    scope_type: str
    scope_id: str

    seed_terms: list[str] = []
    activated_neurons: list[KnowledgeNeuron] = []
    contradictions: list[KnowledgeNeuron] = []

    support_refs: list[str] = []
    evidence_refs: list[str] = []
    strategy_refs: list[str] = []

    top_entities: list[str] = []
    top_opinions: list[str] = []
    top_constraints: list[str] = []
    top_next_actions: list[str] = []

    metadata: dict[str, Any] = {}
```

## Relationship Model

`2026-04-01` phase 4 update: the optional persisted relation slice has now landed as a
minimal `memory_relation_views` table plus a rebuildable relation-view repository/read
surface. This does not change the core rule here: relation edges remain derived from
canonical truth and can be rebuilt from existing fact/entity/opinion sources.

第一版不强求新增持久化 graph table，而是先把现有隐式关系正式化为派生关系。

建议支持 8 类关系：

- `mentions`
- `supports`
- `contradicts`
- `related_to`
- `belongs_to_scope`
- `supersedes`
- `derived_from`
- `leads_to`

当前已存在的关系基础：

- `entity_keys`
- `opinion_keys`
- `supporting_refs`
- `contradicting_refs`
- `related_entities`
- `supersedes_entry_id`
- `source_refs`

因此第一版应做的是：

- 正式消费这些关系
- 不急着上图数据库

## Activation Signals

激活信号建议来自 5 类输入：

### 1. Text signal

来自：

- `query_text`
- tokenized phrases
- intent keywords

### 2. Scope signal

来自：

- `work_context_id`
- `task_id`
- `agent_id`
- `industry_instance_id`

这是最强信号。

### 3. Runtime signal

来自：

- `owner_agent_id`
- `capability_ref`
- `environment_ref`
- `risk_level`
- `current_phase`

### 4. Time signal

来自：

- `source_updated_at`
- `updated_at`
- 近期 reports / recent experience

### 5. Evidence signal

来自：

- `evidence_refs`
- `confidence`
- `quality_score`

## Activation Pipeline

第一版建议固定成 6 步：

### Step 1: Resolve scope

优先顺序：

`work_context > task > agent > industry > global`

### Step 2: Build seed set

从以下内容生成种子：

- 文本 token
- 当前 capability
- 当前环境
- 当前 owner
- 当前阶段
- 最近失败/成功信号

### Step 3: Activate primary neurons

优先激活：

- `entity`
- `opinion`
- `profile`
- `strategy`

### Step 4: Spread across relations

沿现有关系扩散到：

- related entities
- supporting / contradicting refs
- source refs
- scope-related facts

### Step 5: Rehydrate truth anchors

把激活结果重新挂回正式真相：

- evidence
- knowledge chunks
- reports
- strategy memory

### Step 6: Produce operator/runtime output

给主脑或执行位返回：

- 当前最相关的节点
- 为什么被激活
- 支撑证据
- 冲突点
- 当前约束
- 推荐下一步动作

## Scoring Model

第一版建议使用简单加权模型：

`activation_score = scope + semantic + recency + confidence + quality + evidence_density - contradiction_penalty`

建议权重：

- `scope_match`: 35%
- `semantic_match`: 25%
- `confidence`: 15%
- `quality_score`: 10%
- `recency`: 10%
- `evidence_density`: 5%

额外规则：

- `expires_at` 已过则强降权
- `is_latest=False` 降权
- `contradicting_refs` 多则降权

## How Knowledge Enters The Layer

行业知识沉淀进入激活层，建议按现有正式入口推进：

### 1. Agent report write-back

`AgentReportRecord`
-> `MemoryRetainService.retain_agent_report()`
-> `KnowledgeChunk + MemoryFactIndex`
-> `MemoryReflectionService`
-> activation layer candidate

### 2. Chat writeback

`chat writeback`
-> `retain_chat_writeback()`
-> `memory:industry:*` 或 `memory:work_context:*`
-> `FactIndex + Profile/Opinion`

### 3. Routine / execution outcome

`RoutineRunRecord / execution outcome`
-> `retain_routine_run()`
-> `FactIndex`

### 4. Evidence

`EvidenceRecord`
-> `retain_evidence()`
-> `FactIndex`

### 5. Agent experience

`AgentExperienceMemoryService.remember_outcome()`
-> `memory:agent:* / memory:task:*`
-> `KnowledgeChunk`

### 6. Strategy

`StrategyMemoryRecord`
-> strategy neuron

## Recommended New Layer

第一版建议只新增：

- `src/copaw/memory/activation_models.py`
- `src/copaw/memory/activation_service.py`

不要在第一版新增新的正式存储表作为真相源。

第一版 `MemoryActivationService` 直接消费现有：

- `StrategyMemoryRecord`
- `MemoryFactIndexRecord`
- `MemoryEntityViewRecord`
- `MemoryOpinionViewRecord`
- `MemoryProfileViewRecord`
- `MemoryEpisodeViewRecord`
- `KnowledgeChunkRecord`
- `ReportRecord`

## Phase 1 Landed Boundary

`2026-04-01` phase 1 landed scope:

- `src/copaw/memory/activation_models.py` defines:
  - `KnowledgeNeuron`
  - `ActivationInput`
  - `ActivationResult`
- `src/copaw/memory/activation_service.py` provides the first derived activation service
- runtime bootstrap now instantiates and binds `memory_activation_service`
- `KernelQueryExecutionService` prompt retrieval can consume activation results
- `GoalService` compiler context can consume activation-derived memory items/refs

Current hard boundary:

- activation remains derived from existing truth sources
- no graph persistence table was introduced
- no new canonical memory source was introduced
- report synthesis / backlog replan remained follow-up phases at this stage

## Phase 2 Landed Boundary

`2026-04-01` phase 2 landed scope:

- `report_synthesis.py` can now accept activation-derived input and emit activation summaries into synthesis/replan surfaces
- `service_report_closure.py` now carries activation-derived constraints, next actions, and support refs into follow-up backlog metadata
- `service_lifecycle.py` now preserves activation metadata into the existing `synthesis -> follow-up backlog -> assignment` chain
- `service_runtime_views.py` now exposes `synthesis.activation` on current-cycle runtime payloads when replan continuity points to that synthesis context
- industry runtime wiring now makes `memory_activation_service` available to `IndustryService` via runtime bindings / explicit injection
- `activation_service.activate_for_query(...)` now pulls scoped `entity/opinion` derived views in addition to fact recall
- `service_lifecycle.py` now reuses one activation result across prediction cycle review, report synthesis, and cycle planner input
- `PlanningStrategyConstraints` / `CyclePlanningDecision.metadata` now preserve `graph_focus_entities` and `graph_focus_opinions` as planner sidecar input/output
- follow-up backlog and materialized assignment continuity now also carry `activation_top_entities` / `activation_top_opinions`

Current hard boundary after phase 2:

- activation remains derived from existing truth sources
- no graph persistence table was introduced
- no new canonical memory source was introduced
- Runtime Center activation-specific visualization beyond current read surfaces had not landed yet

## Phase 3 Landed Boundary

`2026-04-01` phase 3 landed scope:

- `runtime_center_routes_memory.py` now exposes `GET /runtime-center/memory/activation`
- Runtime Center memory profile read surfaces can attach full activation payloads when `include_activation=true` and a `query` is supplied
- Runtime Center memory episode read surfaces can also attach activation payloads under the same opt-in contract
- `runtime_bootstrap_query.py` now wires `memory_activation_service` into `RuntimeCenterStateQueryService`
- `RuntimeCenterStateQueryService` now derives compact activation summaries for Runtime Center task list/detail payloads
- `runtime_center/models.py` now defines a conservative `RuntimeActivationSummary` read model for those task surfaces

Current hard boundary after phase 3:

- activation remains derived from existing truth sources
- no graph persistence table was introduced
- no new canonical memory source was introduced
- task list/detail surfaces only expose conservative activation summaries, not full activated neuron payloads
- Runtime Center activation visibility currently lands as route/read-surface payloads, not as a separate dedicated visualization system

## Phase 4 Landed Boundary

`2026-04-01` phase 4 landed scope:

- `models_memory.py` now defines `MemoryRelationViewRecord` as a persisted relation-view read model
- `state/store.py` now includes the SQLite-backed `memory_relation_views` table and indexes
- `state/repositories/sqlite_memory.py` now provides `SqliteMemoryRelationViewRepository`
- runtime bootstrap now wires `memory_relation_view_repository` into `DerivedMemoryIndexService`
- `DerivedMemoryIndexService` now exposes explicit `list_relation_views(...)` and `rebuild_relation_views(...)`
- `runtime_center_routes_memory.py` now exposes `GET /runtime-center/memory/relations`

Current hard boundary after phase 4:

- persisted relation views are still derived-only projections over existing `MemoryFactIndexRecord + MemoryEntityViewRecord + MemoryOpinionViewRecord`
- the persisted relation view is SQLite-backed inside the unified state store, but it is not a second truth source
- no graph database or graph-native execution write path was introduced
- Runtime Center currently gains a read surface for relations, not a separate graph-management system
- generic memory rebuild (`rebuild_all` / `POST /runtime-center/memory/rebuild`) does not yet auto-rebuild relation views; relation rebuild currently remains an explicit derived-index operation

## Integration Points

第一版建议接入这些消费面：

### Main brain runtime context

在 query/planning 前，为主脑补一份 activation result。

### Execution runtime

在执行位遇到：

- 当前任务卡住
- 同类错误重复出现
- 当前环境冲突

时优先激活对应知识节点。

### Report synthesis

在 report / replan 时，不只看 evidence 摘要，也看当前激活的长期规律。

### Follow-up backlog generation

从 activated opinions / constraints / contradictions 里提炼下一步 backlog 候选。

## What Not To Do

以下做法明确禁止：

1. 不把 activation layer 做成新的 canonical truth
2. 不把它做成“关键词命中 = 直接召回 chunk”的简单搜索壳
3. 不引入第二套 memory DB 做双写
4. 不用外部 session memory 替代 CoPaw 的 truth-first memory
5. 不把 graph activation 直接变成主脑最终决策，必须仍然挂回 evidence/state/strategy

## Relationship To External Session-Memory Patterns

外部会话记忆产品里有一些模式仍然值得参考，但位置很清楚：

适合吸收的模式：

- working memory
- session compaction
- consolidation
- interrupt / timeout / cleanup discipline

纯会话式知识组织不适合作为最终知识架构：

- 它更像记忆文件系统
- 不像正式行业知识图谱

因此：

- 知识最终组织：按 CoPaw 的 activation layer 做
- 知识提炼工程纪律：继续保持严格工程纪律

## Final Position

这套“神经元式知识层”在 CoPaw 里的正式定义应为：

**建立在 `StrategyMemory + KnowledgeChunk + FactIndex + Entity/Opinion/Profile/Episode Views` 之上的派生激活层，用于 scope-first 的知识节点激活、关系扩散、证据回收和召回排序。**

它不是新的真相源，而是主脑与执行位的“联想层”。
