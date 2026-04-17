# Universal External Information Collection Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地一条所有职业 agent 都能调用的“通用外部信息收集底座”，让主脑可规划、普通职业可轻查、`researcher` 可承接重研究，并把结果正式回写到 research/evidence/work truth。

**Architecture:** 在现有 `ResearchSessionRecord / ResearchSessionRoundRecord / EvidenceRecord / EnvironmentMount / SessionMount` 主链上新增一层 `source_collection` 编排层。稳定模型收口为 `discover / read / interact / capture` 四类 collection action；`search / web_page / github / artifact` 只作为 phase-1 adapters 落地。现有 `BaiduPageResearchService` 不删除，但从“整个研究系统 owner”降为 provider adapter 的一部分，由新的通用 orchestration service 统一调度、归并、写证据和写回。

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, React + TypeScript + Vitest

---

## File Map

**Core source-collection contracts and orchestration**

- Create: `src/copaw/research/source_collection/__init__.py`
- Create: `src/copaw/research/source_collection/contracts.py`
- Create: `src/copaw/research/source_collection/routing.py`
- Create: `src/copaw/research/source_collection/synthesis.py`
- Create: `src/copaw/research/source_collection/writeback.py`
- Create: `src/copaw/research/source_collection/service.py`
- Create: `src/copaw/research/source_collection/adapters/__init__.py`
- Create: `src/copaw/research/source_collection/adapters/search.py`
- Create: `src/copaw/research/source_collection/adapters/web_page.py`
- Create: `src/copaw/research/source_collection/adapters/github.py`
- Create: `src/copaw/research/source_collection/adapters/artifact.py`
- Create: `tests/research/test_source_collection_contracts.py`
- Create: `tests/research/test_source_collection_routing.py`
- Create: `tests/research/test_source_collection_synthesis.py`
- Create: `tests/research/test_source_collection_service.py`

**Existing research service demotion / reuse**

- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `src/copaw/research/baidu_page_contract.py`
- Modify: `src/copaw/research/models.py`
- Modify: `src/copaw/research/__init__.py`
- Test: `tests/research/test_baidu_page_contract.py`
- Test: `tests/research/test_baidu_page_research_service.py`

**State and writeback integration**

- Modify: `src/copaw/state/models_research.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_research.py`
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Create: `tests/research/test_research_writeback_flow.py`
- Create: `tests/research/test_research_knowledge_ingestion.py`

**Main-brain / agent / schedule wiring**

- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Modify: `src/copaw/app/crons/executor.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Test: `tests/kernel/test_main_brain_research_followup.py`
- Create: `tests/kernel/test_source_collection_agent_entry.py`
- Test: `tests/app/test_research_session_live_contract.py`

**Runtime Center / API**

- Modify: `src/copaw/app/routers/runtime_center_routes_research.py`
- Modify: `src/copaw/app/routers/runtime_center_dependencies.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Create: `tests/app/test_runtime_center_research_surface.py`

**Frontend**

- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/researchHelpers.ts`

**Docs**

- Modify: `implementation_plan.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `TASK_STATUS.md`

---

## Task 1: Introduce Universal Source-Collection Typed Contracts

**Files:**
- Create: `src/copaw/research/source_collection/contracts.py`
- Create: `tests/research/test_source_collection_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_research_brief_contract_round_trip():
    brief = ResearchBrief(
        requester_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
        goal="补齐小说世界观资料",
        question="当前题材下最关键的世界观设定约束是什么",
        why_needed="避免后续剧情设定漂移",
        done_when="得到 3 到 5 条可直接继续写作的连续性约束",
        writeback_target={"kind": "work_context", "id": "ctx-1"},
        collection_mode_hint="auto",
    )
    assert brief.collection_mode_hint == "auto"
```

```python
def test_collected_source_supports_open_taxonomy_and_collection_action():
    source = CollectedSource(
        source_kind="repo",
        collection_action="read",
        source_ref="https://github.com/example/project",
        title="example/project",
    )
    assert source.source_kind == "repo"
    assert source.collection_action == "read"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_contracts.py -q`

Expected: FAIL with missing module / missing contract classes

- [ ] **Step 3: Implement minimal contracts**

```python
class ResearchBrief(BaseModel):
    requester_agent_id: str
    supervisor_agent_id: str | None = None
    goal: str
    question: str
    why_needed: str
    done_when: str
    writeback_target: dict[str, Any]
    urgency: str = "normal"
    collection_mode_hint: Literal["light", "heavy", "auto"] = "auto"
```

```python
class CollectedSource(BaseModel):
    source_kind: str
    collection_action: Literal["discover", "read", "interact", "capture"]
    source_ref: str
    title: str = ""
```

```python
class ResearchFinding(BaseModel):
    finding_type: str
    summary: str
    supporting_source_refs: list[str] = Field(default_factory=list)
```

```python
class ResearchAdapterResult(BaseModel):
    adapter_kind: str
    collection_action: Literal["discover", "read", "interact", "capture"]
    status: Literal["succeeded", "partial", "blocked", "failed"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_contracts.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/source_collection/contracts.py tests/research/test_source_collection_contracts.py
git commit -m "feat: add source collection contracts"
```

---

## Task 2: Add Routing And Synthesis Core

**Files:**
- Create: `src/copaw/research/source_collection/routing.py`
- Create: `src/copaw/research/source_collection/synthesis.py`
- Create: `tests/research/test_source_collection_routing.py`
- Create: `tests/research/test_source_collection_synthesis.py`

- [ ] **Step 1: Write the failing routing tests**

```python
def test_route_collection_mode_marks_single_page_lookup_as_light():
    brief = ResearchBrief(...)
    decision = route_collection_mode(brief, requested_sources=["web_page"])
    assert decision.mode == "light"
```

```python
def test_route_collection_mode_marks_multi_source_comparison_as_heavy():
    brief = ResearchBrief(...)
    decision = route_collection_mode(brief, requested_sources=["search", "github", "web_page"])
    assert decision.mode == "heavy"
```

- [ ] **Step 2: Write the failing synthesis tests**

```python
def test_synthesize_findings_dedupes_duplicate_sources():
    merged = synthesize_collection_results([...])
    assert len(merged.collected_sources) == 1
```

```python
def test_synthesize_findings_marks_conflicts_and_gaps():
    merged = synthesize_collection_results([...])
    assert merged.findings
    assert merged.conflicts
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_routing.py tests/research/test_source_collection_synthesis.py -q`

Expected: FAIL with missing functions / missing result models

- [ ] **Step 4: Implement minimal routing and synthesis**

```python
def route_collection_mode(brief: ResearchBrief, requested_sources: list[str]) -> CollectionRouteDecision: ...
```

```python
def synthesize_collection_results(results: list[ResearchAdapterResult]) -> SynthesizedCollectionResult: ...
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_routing.py tests/research/test_source_collection_synthesis.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/research/source_collection/routing.py src/copaw/research/source_collection/synthesis.py tests/research/test_source_collection_routing.py tests/research/test_source_collection_synthesis.py
git commit -m "feat: add source collection routing and synthesis"
```

---

## Task 3: Build The Universal Source-Collection Service Skeleton

**Files:**
- Create: `src/copaw/research/source_collection/service.py`
- Create: `src/copaw/research/source_collection/__init__.py`
- Create: `tests/research/test_source_collection_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
def test_service_runs_light_collection_inline():
    result = service.collect(brief=brief, owner_agent_id="writer-agent")
    assert result.route.mode == "light"
```

```python
def test_service_routes_heavy_collection_to_researcher():
    result = service.collect(brief=brief, owner_agent_id="writer-agent")
    assert result.route.mode == "heavy"
    assert result.route.execution_agent_id == "industry-researcher-demo"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_service.py -q`

Expected: FAIL with missing service

- [ ] **Step 3: Implement the minimal orchestration owner**

```python
class SourceCollectionService:
    def collect(self, *, brief: ResearchBrief, owner_agent_id: str, ...) -> SourceCollectionRunResult: ...
```

The minimal owner should:

- normalize the brief
- call routing
- invoke selected adapters
- call synthesis
- return one unified result envelope

- [ ] **Step 4: Run service tests**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_service.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/source_collection/__init__.py src/copaw/research/source_collection/service.py tests/research/test_source_collection_service.py
git commit -m "feat: add source collection orchestration service"
```

---

## Task 4: Demote Baidu Research Into A Provider Adapter

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `src/copaw/research/baidu_page_contract.py`
- Modify: `src/copaw/research/models.py`
- Modify: `src/copaw/research/__init__.py`
- Test: `tests/research/test_baidu_page_contract.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Write the failing adapter-shape regression tests**

```python
def test_baidu_service_returns_adapter_result_shape():
    result = service.run_session(session_id)
    assert result.findings is not None
    assert result.collected_sources
```

```python
def test_baidu_service_can_be_called_via_source_collection_service():
    result = source_collection_service.collect(...)
    assert any(item.adapter_kind == "search" for item in result.adapter_results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py -q`

Expected: FAIL because current service is still provider-shaped and not mapped into the shared adapter result

- [ ] **Step 3: Refactor Baidu service behind adapter boundaries**

Introduce a provider-facing adapter entry such as:

```python
def collect_via_baidu_page(... ) -> ResearchAdapterResult: ...
```

Keep these existing capabilities:

- session creation
- multi-round loop
- link deepening
- waiting-login handling
- summary extraction

But stop treating this service as the whole universal collection system.

- [ ] **Step 4: Run Baidu regressions**

Run: `PYTHONPATH=src python -m pytest tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py src/copaw/research/baidu_page_contract.py src/copaw/research/models.py src/copaw/research/__init__.py tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py
git commit -m "refactor: demote baidu research into source adapter"
```

---

## Task 5: Add Phase-1 Adapters For `web_page`, `github`, And `artifact`

**Files:**
- Create: `src/copaw/research/source_collection/adapters/search.py`
- Create: `src/copaw/research/source_collection/adapters/web_page.py`
- Create: `src/copaw/research/source_collection/adapters/github.py`
- Create: `src/copaw/research/source_collection/adapters/artifact.py`
- Create: `tests/research/test_source_collection_adapters.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
def test_web_page_adapter_reads_one_page_into_collected_source():
    result = adapter.collect(...)
    assert result.collection_action == "read"
```

```python
def test_github_adapter_reads_repo_page_as_repo_source():
    result = adapter.collect(...)
    assert result.collected_sources[0].source_kind == "repo"
```

```python
def test_artifact_adapter_records_downloaded_file():
    result = adapter.collect(...)
    assert result.collected_sources[0].source_kind == "artifact"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_adapters.py -q`

Expected: FAIL with missing adapters

- [ ] **Step 3: Implement minimal adapters**

Use existing chains where possible:

- `search.py`
  - wrap the Baidu/provider-backed discovery path first
- `web_page.py`
  - use existing browser/session execution primitives for page read
- `github.py`
  - use page-read first, not a separate heavy GitHub subsystem
- `artifact.py`
  - normalize downloads/attachments into collected-source + evidence output

- [ ] **Step 4: Run adapter tests**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_adapters.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/source_collection/adapters/__init__.py src/copaw/research/source_collection/adapters/search.py src/copaw/research/source_collection/adapters/web_page.py src/copaw/research/source_collection/adapters/github.py src/copaw/research/source_collection/adapters/artifact.py tests/research/test_source_collection_adapters.py
git commit -m "feat: add phase-one source collection adapters"
```

---

## Task 6: Extend Research Session Persistence And Writeback Payloads

**Files:**
- Modify: `src/copaw/state/models_research.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_research.py`
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Create: `tests/research/test_research_writeback_flow.py`
- Create: `tests/research/test_research_knowledge_ingestion.py`

- [ ] **Step 1: Write the failing persistence/writeback tests**

```python
def test_research_session_persists_brief_and_findings():
    session = repo.get_research_session("session-1")
    assert session.metadata["brief"]["goal"] == "..."
```

```python
def test_research_findings_write_back_into_knowledge_and_work_context():
    result = service.collect(...)
    assert result.writeback["knowledge"] == "applied"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_research_writeback_flow.py tests/research/test_research_knowledge_ingestion.py -q`

Expected: FAIL with missing payload fields / missing writeback

- [ ] **Step 3: Extend the research records and writeback logic**

Add formal payload slots for:

- brief
- collected sources
- findings
- conflicts/gaps summary
- writeback status

Do not introduce a second repository unless strictly needed.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src python -m pytest tests/research/test_research_writeback_flow.py tests/research/test_research_knowledge_ingestion.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_research.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_research.py src/copaw/state/knowledge_service.py src/copaw/memory/retain_service.py src/copaw/memory/knowledge_writeback_service.py tests/research/test_research_writeback_flow.py tests/research/test_research_knowledge_ingestion.py
git commit -m "feat: persist source collection findings and writeback"
```

---

## Task 7: Wire Main Brain, Agent Entry, And Monitoring Through One Front Door

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Modify: `src/copaw/app/crons/executor.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Test: `tests/kernel/test_main_brain_research_followup.py`
- Create: `tests/kernel/test_source_collection_agent_entry.py`
- Test: `tests/app/test_research_session_live_contract.py`

- [ ] **Step 1: Write the failing entry-point tests**

```python
def test_main_brain_research_trigger_uses_source_collection_service():
    response = service.chat(...)
    assert response.meta["research_session_id"]
```

```python
def test_profession_agent_can_request_light_collection_without_researcher_lock_in():
    result = dispatch_query(...)
    assert result["success"] is True
```

```python
def test_monitoring_brief_still_wakes_heavy_collection_path():
    executor.execute(job)
    assert started_sessions
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_research_followup.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_research_session_live_contract.py -q`

Expected: FAIL because triggers are still wired to the current direct provider flow

- [ ] **Step 3: Rewire all entry paths**

Required behavior:

- main-brain explicit research -> universal source collection service
- ordinary agent light lookup -> universal source collection service
- monitoring brief cron wake -> universal source collection service
- heavy route -> `researcher` by default

- [ ] **Step 4: Run entry-point regressions**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_research_followup.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_research_session_live_contract.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/query_execution_tools.py src/copaw/app/crons/executor.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_bootstrap_repositories.py tests/kernel/test_main_brain_research_followup.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_research_session_live_contract.py
git commit -m "feat: route research triggers through source collection service"
```

---

## Task 8: Expose Source Collection Truth In Runtime Center

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_research.py`
- Modify: `src/copaw/app/routers/runtime_center_dependencies.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Create: `tests/app/test_runtime_center_research_surface.py`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/researchHelpers.ts`

- [ ] **Step 1: Write the failing backend and frontend read-surface tests**

```python
def test_runtime_center_research_surface_returns_brief_findings_and_sources():
    payload = client.get("/runtime-center/research").json()
    assert "brief" in payload
    assert "findings" in payload
```

```ts
it("renders source collection findings instead of provider-only details", async () => {
  expect(screen.getByText(/findings/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run backend: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_research_surface.py -q`

Run frontend: `npm --prefix console run test -- console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

Expected: FAIL because the read surface still reflects the old provider-shaped model

- [ ] **Step 3: Update Runtime Center payloads and cockpit UI**

Expose at least:

- current brief
- current owner
- current sources
- current findings
- current conflicts/gaps
- writeback state

- [ ] **Step 4: Run read-surface tests**

Run backend: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_research_surface.py -q`

Run frontend: `npm --prefix console run test -- console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/routers/runtime_center_routes_research.py src/copaw/app/routers/runtime_center_dependencies.py src/copaw/app/routers/runtime_center_payloads.py tests/app/test_runtime_center_research_surface.py console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx console/src/pages/RuntimeCenter/researchHelpers.ts
git commit -m "feat: expose source collection truth in runtime center"
```

---

## Task 9: Sync Formal Docs And Run Focused Acceptance

**Files:**
- Modify: `implementation_plan.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Update docs**

Document these truth changes:

- all agents may invoke collection
- `researcher` is default heavy executor, not exclusive gate
- stable model is `discover / read / interact / capture`
- phase-1 adapters are `search / web_page / github / artifact`
- Baidu service is a provider adapter, not the universal collection system

- [ ] **Step 2: Run focused backend regression**

Run:

```bash
PYTHONPATH=src python -m pytest \
  tests/research/test_source_collection_contracts.py \
  tests/research/test_source_collection_routing.py \
  tests/research/test_source_collection_synthesis.py \
  tests/research/test_source_collection_service.py \
  tests/research/test_source_collection_adapters.py \
  tests/research/test_baidu_page_contract.py \
  tests/research/test_baidu_page_research_service.py \
  tests/research/test_research_writeback_flow.py \
  tests/research/test_research_knowledge_ingestion.py \
  tests/kernel/test_main_brain_research_followup.py \
  tests/kernel/test_source_collection_agent_entry.py \
  tests/app/test_research_session_live_contract.py \
  tests/app/test_runtime_center_research_surface.py -q
```

Expected: PASS

- [ ] **Step 3: Run focused frontend regression**

Run:

```bash
npm --prefix console run test -- \
  console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts \
  console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 4: Run one gated live smoke**

Run:

```bash
COPAW_RUN_BAIDU_RESEARCH_LIVE_SMOKE=1 PYTHONPATH=src python -m pytest tests/app/test_research_session_live_contract.py -q -rs
```

Expected:

- if browser + login preconditions are available: PASS
- otherwise: explicit SKIP with truthful reason

- [ ] **Step 5: Commit**

```bash
git add implementation_plan.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md TASK_STATUS.md
git commit -m "docs: sync universal source collection foundation"
```

---

## Recommended Commit Batches

1. `feat: add source collection contracts`
2. `feat: add source collection routing and synthesis`
3. `feat: add source collection orchestration service`
4. `refactor: demote baidu research into source adapter`
5. `feat: add phase-one source collection adapters`
6. `feat: persist source collection findings and writeback`
7. `feat: route research triggers through source collection service`
8. `feat: expose source collection truth in runtime center`
9. `docs: sync universal source collection foundation`

---

## Exit Criteria

Do not call this plan complete unless all of the following are true:

- all profession agents can formally request external-information collection
- the main brain can form/approve a `ResearchBrief`
- routing correctly splits `light` and `heavy`
- `researcher` is the default heavy executor, not the exclusive gate
- the stable collection action model is formalized:
  - `discover`
  - `read`
  - `interact`
  - `capture`
- phase-1 adapters are all wired:
  - `search`
  - `web_page`
  - `github`
  - `artifact`
- collection results formally write back into research/evidence/work truth
- Runtime Center can show collection truth
- live smoke truthfully passes or explicitly skips with a real prerequisite reason
