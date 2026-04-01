# Knowledge Activation Layer Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first shippable slice of the Knowledge Activation Layer by introducing activation-layer models and service logic on top of the existing memory/strategy/reporting truth chain, then wire it into the first two real consumers: query prompt retrieval and goal compiler memory context.

**Architecture:** This plan intentionally covers only the first executable slice of the Knowledge Activation Layer spec. It does not try to solve all consumers at once. Phase 1 adds a derived activation service on top of existing `StrategyMemoryRecord`, `KnowledgeChunkRecord`, `MemoryFactIndexRecord`, and reflection views, wires it through runtime bootstrap, and uses it in the current prompt/planning path without introducing a second truth source or a graph database.

**Tech Stack:** Python 3.11, Pydantic, SQLite-backed repositories, existing CoPaw memory/state services, Pytest.

---

## Scope Check

The full spec spans multiple downstream consumers:

- main-brain runtime context
- execution runtime
- report synthesis
- follow-up backlog generation
- Runtime Center visualization

This plan covers only **Phase 1**:

1. activation models
2. activation service
3. bootstrap wiring
4. query prompt integration
5. goal compiler integration

Future plans are required for:

- report synthesis activation
- backlog/replan activation
- Runtime Center activation views
- optional graph persistence

## Execution Environment

Run this plan in a dedicated worktree.

Suggested commands:

```powershell
git worktree add .worktrees\knowledge-activation-phase1 -b feat/knowledge-activation-phase1
cd .worktrees\knowledge-activation-phase1
pip install -e .
```

## File Map

### New files

- `src/copaw/memory/activation_models.py`
  - Defines `KnowledgeNeuron`, `ActivationInput`, and `ActivationResult`.
- `src/copaw/memory/activation_service.py`
  - Builds/activates neurons from existing strategy/fact/view records and returns `ActivationResult`.
- `tests/memory/test_activation_models.py`
  - Unit tests for activation-layer model validation and defaults.
- `tests/memory/test_activation_service.py`
  - Unit tests for neuron materialization, scope-first activation, relation spreading, and scoring.

### Existing files to modify

- `src/copaw/memory/__init__.py`
  - Export activation-layer types and service.
- `src/copaw/app/runtime_bootstrap_query.py`
  - Instantiate `MemoryActivationService` and extend the returned query-service tuple.
- `src/copaw/app/runtime_bootstrap_models.py`
  - Add `memory_activation_service` to the runtime bootstrap model.
- `src/copaw/app/runtime_service_graph.py`
  - Thread the new activation service through bootstrap assembly and warmup if needed.
- `src/copaw/app/runtime_state_bindings.py`
  - Bind `memory_activation_service` onto `app.state`.
- `src/copaw/kernel/query_execution_prompt.py`
  - Consume activation results before or alongside existing truth-first recall.
- `src/copaw/goals/service_core.py`
  - Hold the activation-service dependency.
- `src/copaw/goals/service_compiler.py`
  - Feed activation results into compiler context assembly.
- `tests/app/test_runtime_bootstrap_helpers.py`
  - Verify bootstrap/query-service wiring includes the activation service.
- `tests/app/test_runtime_bootstrap_split.py`
  - Verify runtime bootstrap stays split and the new service is threaded correctly.
- `tests/kernel/test_memory_recall_integration.py`
  - Extend current memory-retrieval integration tests to cover activation-layer behavior.
- `tests/app/test_goals_api.py`
  - Verify goal compiler responses surface activation-derived memory context when wired.
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
  - Update with any final naming/field adjustments discovered during implementation.

## Task 1: Add Failing Tests for Activation Models

**Files:**
- Create: `tests/memory/test_activation_models.py`
- Create: `src/copaw/memory/activation_models.py`

- [ ] **Step 1: Write the failing tests**

```python
from copaw.memory.activation_models import ActivationInput, ActivationResult, KnowledgeNeuron


def test_knowledge_neuron_defaults_and_required_fields():
    neuron = KnowledgeNeuron(
        neuron_id="entity:industry-1:outbound",
        kind="entity",
        scope_type="industry",
        scope_id="industry-1",
        title="Outbound",
    )
    assert neuron.kind == "entity"
    assert neuron.activation_score == 0.0
    assert neuron.entity_keys == []


def test_activation_input_accepts_runtime_scope_signals():
    payload = ActivationInput(
        query_text="review outbound execution failure",
        work_context_id="ctx-1",
        task_id="task-1",
        capability_ref="tool:execute_shell_command",
    )
    assert payload.work_context_id == "ctx-1"
    assert payload.limit == 12


def test_activation_result_can_hold_neurons_and_support_refs():
    result = ActivationResult(
        query="review outbound execution failure",
        scope_type="work_context",
        scope_id="ctx-1",
    )
    assert result.activated_neurons == []
    assert result.support_refs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/memory/test_activation_models.py -v
```

Expected: FAIL with missing module or missing classes.

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    entity_keys: list[str] = Field(default_factory=list)
    opinion_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0
    freshness_score: float = 0.0
    activation_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class ActivationResult(BaseModel):
    query: str
    scope_type: str
    scope_id: str
    seed_terms: list[str] = Field(default_factory=list)
    activated_neurons: list[KnowledgeNeuron] = Field(default_factory=list)
    contradictions: list[KnowledgeNeuron] = Field(default_factory=list)
    support_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    strategy_refs: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    top_opinions: list[str] = Field(default_factory=list)
    top_constraints: list[str] = Field(default_factory=list)
    top_next_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/memory/test_activation_models.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/memory/test_activation_models.py src/copaw/memory/activation_models.py
git commit -m "feat: add activation layer models"
```

## Task 2: Add Failing Tests for Activation Service Neuron Materialization

**Files:**
- Create: `tests/memory/test_activation_service.py`
- Create: `src/copaw/memory/activation_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from copaw.memory.activation_models import ActivationInput
from copaw.memory.activation_service import MemoryActivationService


def test_activation_service_materializes_entity_and_opinion_neurons():
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(),
        strategy_memory_service=SimpleNamespace(),
    )
    result = service.activate(
        ActivationInput(
            query_text="outbound approval is blocked",
            work_context_id="ctx-1",
        ),
        fact_entries=[
            SimpleNamespace(
                id="fact-1",
                source_type="knowledge_chunk",
                source_ref="chunk-1",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Outbound approval blocked",
                summary="Approval is blocked pending evidence review.",
                content_excerpt="Approval is blocked pending evidence review.",
                entity_keys=["outbound", "approval"],
                opinion_keys=["approval:caution:evidence-review"],
                tags=["latest"],
                evidence_refs=["evidence-1"],
                confidence=0.9,
                quality_score=0.8,
                source_updated_at=None,
                metadata={},
            )
        ],
        entity_views=[],
        opinion_views=[],
        profile_view=None,
        episode_views=[],
        strategy_payload=None,
    )
    neuron_ids = {item.neuron_id for item in result.activated_neurons}
    assert "fact-1" in neuron_ids


def test_activation_service_prefers_work_context_scope_over_industry_scope():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k materializes -v
```

Expected: FAIL with missing module or missing `activate`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from .activation_models import ActivationInput, ActivationResult, KnowledgeNeuron


class MemoryActivationService:
    def __init__(self, *, derived_index_service, strategy_memory_service=None) -> None:
        self._derived_index_service = derived_index_service
        self._strategy_memory_service = strategy_memory_service

    def activate(
        self,
        activation_input: ActivationInput,
        *,
        fact_entries,
        entity_views,
        opinion_views,
        profile_view,
        episode_views,
        strategy_payload,
    ) -> ActivationResult:
        neurons = [
            KnowledgeNeuron(
                neuron_id=entry.id,
                kind="fact",
                scope_type=entry.scope_type,
                scope_id=entry.scope_id,
                title=entry.title,
                summary=entry.summary,
                content_excerpt=entry.content_excerpt,
                entity_keys=list(entry.entity_keys),
                opinion_keys=list(entry.opinion_keys),
                tags=list(entry.tags),
                source_refs=[entry.source_ref],
                evidence_refs=list(entry.evidence_refs),
                confidence=entry.confidence,
                quality_score=entry.quality_score,
            )
            for entry in fact_entries
        ]
        return ActivationResult(
            query=activation_input.query_text,
            scope_type="work_context" if activation_input.work_context_id else "global",
            scope_id=activation_input.work_context_id or "runtime",
            activated_neurons=neurons[: activation_input.limit],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k materializes -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/memory/test_activation_service.py src/copaw/memory/activation_service.py
git commit -m "feat: add activation neuron materialization"
```

## Task 3: Add Failing Tests for Activation Scoring and Relation Spread

**Files:**
- Modify: `tests/memory/test_activation_service.py`
- Modify: `src/copaw/memory/activation_service.py`

- [ ] **Step 1: Add the failing tests**

```python
def test_activation_service_scores_scope_match_higher_than_global_fallback():
    ...
    assert result.activated_neurons[0].scope_id == "ctx-1"


def test_activation_service_collects_support_and_contradiction_refs():
    ...
    assert "evidence-1" in result.evidence_refs
    assert result.support_refs
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k "scores_scope_match or support_and_contradiction" -v
```

Expected: FAIL because scoring/spread logic is not implemented yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _score_fact(self, entry, activation_input: ActivationInput) -> float:
    score = 0.0
    if activation_input.work_context_id and entry.scope_type == "work_context" and entry.scope_id == activation_input.work_context_id:
        score += 35.0
    score += entry.confidence * 15.0
    score += entry.quality_score * 10.0
    return score
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/memory/test_activation_service.py -k "scores_scope_match or support_and_contradiction" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/memory/test_activation_service.py src/copaw/memory/activation_service.py
git commit -m "feat: add activation scoring and relation spread"
```

## Task 4: Wire `MemoryActivationService` into Runtime Bootstrap and App State

**Files:**
- Modify: `src/copaw/memory/__init__.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write the failing bootstrap tests**

```python
def test_build_runtime_query_services_returns_memory_activation_service(...):
    ...
    assert bootstrap.memory_activation_service is not None


def test_attach_runtime_state_binds_memory_activation_service(...):
    ...
    assert app.state.memory_activation_service is bootstrap.memory_activation_service
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_bootstrap_helpers.py -k activation_service -v
python -m pytest tests/app/test_runtime_bootstrap_split.py -k activation_service -v
```

Expected: FAIL because bootstrap models and bindings do not include the new service.

- [ ] **Step 3: Write minimal wiring**

```python
# runtime_bootstrap_query.py
memory_activation_service = MemoryActivationService(
    derived_index_service=derived_memory_index_service,
    strategy_memory_service=strategy_memory_service,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_bootstrap_helpers.py -k activation_service -v
python -m pytest tests/app/test_runtime_bootstrap_split.py -k activation_service -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/memory/__init__.py src/copaw/app/runtime_bootstrap_query.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_service_graph.py src/copaw/app/runtime_state_bindings.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py
git commit -m "feat: wire activation service into runtime bootstrap"
```

## Task 5: Integrate Activation into Query Prompt Retrieval

**Files:**
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Test: `tests/kernel/test_memory_recall_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_execution_prompt_uses_activation_result_before_recall_hits():
    ...
    assert any("Activation" in line for line in lines)


def test_query_execution_prompt_keeps_truth_first_scope_priority_with_activation():
    ...
    assert call["scope_type"] == "work_context"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_memory_recall_integration.py -k activation -v
```

Expected: FAIL because prompt retrieval does not consume activation output yet.

- [ ] **Step 3: Write minimal integration**

```python
activation_service = getattr(self, "_memory_activation_service", None)
if activation_service is not None:
    activation = activation_service.activate_for_query(...)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_memory_recall_integration.py -k activation -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/kernel/query_execution_prompt.py tests/kernel/test_memory_recall_integration.py
git commit -m "feat: add activation-aware query prompt retrieval"
```

## Task 6: Integrate Activation into Goal Compiler Memory Context

**Files:**
- Modify: `src/copaw/goals/service_core.py`
- Modify: `src/copaw/goals/service_compiler.py`
- Test: `tests/app/test_goals_api.py`
- Test: `tests/kernel/test_memory_recall_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_goal_service_compiler_uses_activation_hits_in_memory_context():
    ...
    assert context["activation_items"]
    assert context["activation_refs"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_memory_recall_integration.py -k goal_service_compiler_uses_activation -v
python -m pytest tests/app/test_goals_api.py -k activation_items -v
```

Expected: FAIL because the goal compiler does not include activation results yet.

- [ ] **Step 3: Write minimal integration**

```python
# service_core.py
self._memory_activation_service = memory_activation_service

# service_compiler.py
activation_service = getattr(self, "_memory_activation_service", None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_memory_recall_integration.py -k goal_service_compiler_uses_activation -v
python -m pytest tests/app/test_goals_api.py -k activation_items -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/goals/service_core.py src/copaw/goals/service_compiler.py tests/kernel/test_memory_recall_integration.py tests/app/test_goals_api.py
git commit -m "feat: add activation-aware goal compiler context"
```

## Task 7: Run Phase 1 Regression and Update Docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/memory/test_activation_models.py tests/memory/test_activation_service.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/kernel/test_memory_recall_integration.py tests/app/test_goals_api.py -v
```

Expected: PASS

- [ ] **Step 2: Update the design/status docs**

```markdown
- `MemoryActivationService` now exists as a derived activation layer.
- Query prompt retrieval and goal compiler context now consume activation results.
- Activation remains a derived layer on top of formal truth, not a new truth source.
```

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "docs: record knowledge activation phase1"
```

## Done Definition

Phase 1 is complete only when all of the following are true:

- activation models exist
- activation service can materialize and score neurons from existing truth sources
- runtime bootstrap exposes `memory_activation_service`
- query prompt retrieval can consume activation results
- goal compiler can consume activation results
- the regression suite in Task 7 is green

## Follow-Up Planning Gate

Do not start the next activation phase from this branch until this plan is green.

Write follow-up plans for:

1. report synthesis activation
2. backlog/replan activation
3. Runtime Center activation views
4. optional persisted relation graph
