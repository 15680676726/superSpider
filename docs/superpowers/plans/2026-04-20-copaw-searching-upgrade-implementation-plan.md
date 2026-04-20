# CoPaw Searching Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CoPaw 新增一层统一的 retrieval substrate，在不破坏现有 `SourceCollectionFrontdoorService -> SourceCollectionService -> ResearchSession / Evidence / report / writeback truth -> Runtime Center` 正式主链的前提下，把本地 repo、GitHub、Web 三源搜索统一升级。

**Architecture:** phase-1 不改 formal truth，不引入第二真相源。新增 `src/copaw/retrieval/` 作为可重建索引和检索策略层；现有 `SourceCollectionFrontdoorService` 继续负责 `light / heavy / execution_agent_id` 路由，`SourceCollectionService` 继续负责 formal collection 映射；`ResearchSessionRecord / ResearchSessionRoundRecord / Evidence / report / writeback truth` 继续作为唯一正式闭环。

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, React + TypeScript + Vitest

---

## Reality Sync (2026-04-20 audit)

- 现有正式前门不是单层 service，而是 `SourceCollectionFrontdoorService -> SourceCollectionService`
- 当前 `route_collection_mode()` 只负责 `light / heavy / execution_agent_id`，不是统一 search planner
- 当前 research formal truth 已经稳定落在：
  - `ResearchSessionRecord.brief / conflicts / writeback_truth`
  - `ResearchSessionRoundRecord.sources / findings / conflicts / gaps / writeback_truth`
- 当前 light path 已经会继续写：
  - `EvidenceRecord`
  - `AgentReportRecord`
  - `knowledge_service.ingest_research_session(...)`
  - `knowledge_writeback_service.build/apply_research_session_writeback(...)`
- 当前 Runtime Center research 读链来自：
  - `src/copaw/app/routers/runtime_center_routes_research.py`
  - `src/copaw/app/routers/runtime_center_payloads.py`
  并且是 `top-level formal field 优先，metadata fallback 次之`
- phase-1 不能回退：
  - `artifact-followup` lane
  - `collect_sources` tool entry
  - `BaiduPageResearchService` 现有 heavy owner 身份

---

## File Map

**New retrieval substrate**

- Create: `src/copaw/retrieval/__init__.py`
- Create: `src/copaw/retrieval/contracts.py`
- Create: `src/copaw/retrieval/planner.py`
- Create: `src/copaw/retrieval/ranking.py`
- Create: `src/copaw/retrieval/run.py`
- Create: `src/copaw/retrieval/facade.py`

**Local repo retrieval**

- Create: `src/copaw/retrieval/local_repo/__init__.py`
- Create: `src/copaw/retrieval/local_repo/index_models.py`
- Create: `src/copaw/retrieval/local_repo/index_store.py`
- Create: `src/copaw/retrieval/local_repo/chunker.py`
- Create: `src/copaw/retrieval/local_repo/exact_search.py`
- Create: `src/copaw/retrieval/local_repo/symbol_search.py`
- Create: `src/copaw/retrieval/local_repo/semantic_search.py`
- Create: `src/copaw/retrieval/local_repo/graph.py`

**GitHub retrieval**

- Create: `src/copaw/retrieval/github/__init__.py`
- Create: `src/copaw/retrieval/github/object_search.py`
- Create: `src/copaw/retrieval/github/code_search.py`
- Create: `src/copaw/retrieval/github/normalization.py`

**Web retrieval**

- Create: `src/copaw/retrieval/web/__init__.py`
- Create: `src/copaw/retrieval/web/discover.py`
- Create: `src/copaw/retrieval/web/read.py`
- Create: `src/copaw/retrieval/web/credibility.py`
- Create: `src/copaw/retrieval/web/freshness.py`

**Source collection integration**

- Modify: `src/copaw/research/source_collection/service.py`
- Modify: `src/copaw/research/source_collection/contracts.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`

**Runtime Center / API**

- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_research.py`

**Frontend Runtime Center**

- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/researchHelpers.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`

**Tests**

- Create: `tests/retrieval/test_retrieval_contracts.py`
- Create: `tests/retrieval/test_retrieval_planner.py`
- Create: `tests/retrieval/test_retrieval_ranking.py`
- Create: `tests/retrieval/test_local_repo_retrieval.py`
- Create: `tests/retrieval/test_github_retrieval.py`
- Create: `tests/retrieval/test_web_retrieval.py`
- Modify: `tests/research/test_source_collection_service.py`
- Modify: `tests/research/test_source_collection_adapters.py`
- Modify: `tests/kernel/test_source_collection_agent_entry.py`
- Modify: `tests/app/test_source_collection_frontdoor_service.py`
- Modify: `tests/app/test_runtime_center_research_surface.py`
- Create: `tests/app/test_searching_live_contract.py`
- Create: `tests/app/test_searching_soak_contract.py`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

**Docs**

- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `UNIFIED_ACCEPTANCE_STANDARD.md` only if acceptance wording must change; otherwise leave unchanged and cite existing levels in completion notes

---

## Task 1: Introduce Retrieval Contracts And Planner Skeleton

**Files:**
- Create: `src/copaw/retrieval/contracts.py`
- Create: `src/copaw/retrieval/planner.py`
- Create: `src/copaw/retrieval/ranking.py`
- Create: `tests/retrieval/test_retrieval_contracts.py`
- Create: `tests/retrieval/test_retrieval_planner.py`
- Create: `tests/retrieval/test_retrieval_ranking.py`

- [ ] **Step 1: Write failing contract tests**

```python
def test_retrieval_hit_supports_unified_multi_source_shape():
    hit = RetrievalHit(
        source_kind="local_repo",
        provider_kind="symbol",
        hit_kind="symbol",
        ref="src/copaw/app/runtime_bootstrap_domains.py",
        normalized_ref="src/copaw/app/runtime_bootstrap_domains.py",
        title="run_source_collection_frontdoor",
        snippet="def run_source_collection_frontdoor(...):",
        score=0.9,
        relevance_score=0.9,
        answerability_score=0.8,
        freshness_score=0.0,
        credibility_score=1.0,
        structural_score=0.95,
        why_matched="matched requested frontdoor symbol",
    )
    assert hit.source_kind == "local_repo"
```

```python
def test_planner_keeps_frontdoor_mode_separate_from_retrieval_mode():
    plan = build_retrieval_plan(
        intent="repo-trace",
        requested_sources=["local_repo"],
        latest_required=False,
    )
    assert plan.mode_sequence == ["symbol", "exact", "semantic"]
```

```python
def test_retrieval_run_tracks_selected_and_dropped_hits():
    run = RetrievalRun(
        query=RetrievalQuery(question="q", goal="g", intent="repo-trace"),
        plan=RetrievalPlan(intent="repo-trace", source_sequence=["local_repo"], mode_sequence=["symbol", "exact", "semantic"]),
        selected_hits=[],
        dropped_hits=[],
    )
    assert run.plan.intent == "repo-trace"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py -q`

Expected: FAIL with missing module / missing classes

- [ ] **Step 3: Implement minimal retrieval contracts**

```python
class RetrievalQuery(BaseModel):
    question: str
    goal: str
    intent: str
    requested_sources: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
```

```python
class RetrievalPlan(BaseModel):
    intent: str
    source_sequence: list[str]
    mode_sequence: list[str]
    allow_second_pass: bool = True
```

```python
class RetrievalRun(BaseModel):
    query: RetrievalQuery
    plan: RetrievalPlan
    selected_hits: list[RetrievalHit] = Field(default_factory=list)
    dropped_hits: list[RetrievalHit] = Field(default_factory=list)
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
```

```python
class RetrievalHit(BaseModel):
    source_kind: str
    provider_kind: str
    hit_kind: str
    ref: str
    normalized_ref: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    relevance_score: float = 0.0
    answerability_score: float = 0.0
    freshness_score: float = 0.0
    credibility_score: float = 0.0
    structural_score: float = 0.0
    why_matched: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Implement minimal planner/ranking**

```python
def build_retrieval_plan(*, intent: str, requested_sources: list[str], latest_required: bool) -> RetrievalPlan:
    if intent == "repo-trace":
        return RetrievalPlan(intent=intent, source_sequence=["local_repo"], mode_sequence=["symbol", "exact", "semantic"])
    if intent == "external-latest":
        return RetrievalPlan(intent=intent, source_sequence=requested_sources or ["github", "web"], mode_sequence=["exact", "semantic"])
    return RetrievalPlan(intent=intent, source_sequence=requested_sources or ["web"], mode_sequence=["exact"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/retrieval/contracts.py src/copaw/retrieval/planner.py src/copaw/retrieval/ranking.py tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py
git commit -m "feat: add retrieval planner contracts"
```

---

## Task 2: Add Local Repo Exact And Symbol Retrieval

**Files:**
- Create: `src/copaw/retrieval/local_repo/index_models.py`
- Create: `src/copaw/retrieval/local_repo/index_store.py`
- Create: `src/copaw/retrieval/local_repo/exact_search.py`
- Create: `src/copaw/retrieval/local_repo/symbol_search.py`
- Create: `src/copaw/retrieval/local_repo/graph.py`
- Create: `tests/retrieval/test_local_repo_retrieval.py`

- [ ] **Step 1: Write failing local repo tests**

```python
def test_exact_search_finds_frontdoor_path():
    hits = search_local_repo_exact(workspace_root=REPO_ROOT, query="run_source_collection_frontdoor")
    assert any("runtime_bootstrap_domains.py" in hit.ref for hit in hits)
```

```python
def test_symbol_search_finds_runtime_center_serializer():
    hits = search_local_repo_symbols(workspace_root=REPO_ROOT, query="serialize_runtime_research_sources")
    assert any("runtime_center_payloads.py" in hit.ref for hit in hits)
```

```python
def test_repository_index_snapshot_and_symbol_record_keep_structural_fields():
    snapshot = RepositoryIndexSnapshot(workspace_root=str(REPO_ROOT), file_count=10, chunk_count=20, symbol_count=5)
    symbol = CodeSymbolRecord(
        symbol_name="serialize_runtime_research_sources",
        symbol_kind="function",
        file_path="src/copaw/app/routers/runtime_center_payloads.py",
        line=1,
        container_name="module",
        language="python",
        signature="serialize_runtime_research_sources(...)",
    )
    assert snapshot.symbol_count == 5
    assert symbol.symbol_kind == "function"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_local_repo_retrieval.py -q`

Expected: FAIL with missing search functions

- [ ] **Step 3: Implement minimal index models and file scan**

```python
class RepositoryIndexSnapshot(BaseModel):
    workspace_root: str
    file_count: int
    chunk_count: int = 0
    symbol_count: int = 0
```

```python
def list_repo_files(workspace_root: Path) -> list[Path]:
    return [path for path in workspace_root.rglob("*.py") if ".venv" not in path.parts]
```

- [ ] **Step 4: Implement exact and symbol search**

```python
def search_local_repo_exact(*, workspace_root: Path, query: str) -> list[RetrievalHit]:
    ...
```

```python
def search_local_repo_symbols(*, workspace_root: Path, query: str) -> list[RetrievalHit]:
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_local_repo_retrieval.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/retrieval/local_repo/index_models.py src/copaw/retrieval/local_repo/index_store.py src/copaw/retrieval/local_repo/exact_search.py src/copaw/retrieval/local_repo/symbol_search.py src/copaw/retrieval/local_repo/graph.py tests/retrieval/test_local_repo_retrieval.py
git commit -m "feat: add local repo exact and symbol retrieval"
```

---

## Task 3: Add Local Repo Semantic Retrieval And Unified Facade

**Files:**
- Create: `src/copaw/retrieval/local_repo/chunker.py`
- Create: `src/copaw/retrieval/local_repo/semantic_search.py`
- Create: `src/copaw/retrieval/run.py`
- Create: `src/copaw/retrieval/facade.py`
- Modify: `tests/retrieval/test_local_repo_retrieval.py`

- [ ] **Step 1: Write failing semantic retrieval test**

```python
def test_semantic_retrieval_finds_research_runtime_surface_context():
    run = run_retrieval(
        question="runtime center research surface reads which formal truth fields",
        goal="trace runtime center research payload",
        requested_sources=["local_repo"],
        workspace_root=REPO_ROOT,
    )
    assert any("runtime_center_payloads.py" in hit.ref for hit in run.selected_hits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_local_repo_retrieval.py -q -k semantic`

Expected: FAIL with missing semantic retrieval / facade

- [ ] **Step 3: Implement chunker and semantic fallback**

```python
def chunk_python_file(path: Path) -> list[CodeChunk]:
    ...
```

```python
def search_local_repo_semantic(*, workspace_root: Path, query: str) -> list[RetrievalHit]:
    ...
```

- [ ] **Step 4: Implement facade and retrieval run**

```python
def run_retrieval(... ) -> RetrievalRun:
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_local_repo_retrieval.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/retrieval/local_repo/chunker.py src/copaw/retrieval/local_repo/semantic_search.py src/copaw/retrieval/run.py src/copaw/retrieval/facade.py tests/retrieval/test_local_repo_retrieval.py
git commit -m "feat: add local repo semantic retrieval facade"
```

---

## Task 4: Add GitHub Retrieval Normalization

**Files:**
- Create: `src/copaw/retrieval/github/object_search.py`
- Create: `src/copaw/retrieval/github/code_search.py`
- Create: `src/copaw/retrieval/github/normalization.py`
- Create: `tests/retrieval/test_github_retrieval.py`

- [ ] **Step 1: Write failing GitHub retrieval tests**

```python
def test_normalize_repo_issue_pr_release_hits_into_unified_shape():
    hits = normalize_github_hits([...])
    assert hits[0].source_kind == "github"
    assert hits[0].provider_kind in {"object", "code"}
```

```python
def test_github_object_search_scores_release_more_fresh_than_old_issue():
    hits = search_github_objects(...)
    assert hits[0].freshness_score >= hits[-1].freshness_score
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_github_retrieval.py -q`

Expected: FAIL with missing GitHub retrieval modules

- [ ] **Step 3: Implement GitHub normalization and object search seam**

```python
def normalize_github_hit(payload: dict[str, Any]) -> RetrievalHit:
    ...
```

```python
def search_github_objects(... ) -> list[RetrievalHit]:
    ...
```

- [ ] **Step 4: Implement code/file seam**

```python
def search_github_code(... ) -> list[RetrievalHit]:
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_github_retrieval.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/retrieval/github/object_search.py src/copaw/retrieval/github/code_search.py src/copaw/retrieval/github/normalization.py tests/retrieval/test_github_retrieval.py
git commit -m "feat: add github retrieval substrate"
```

---

## Task 5: Add Web Retrieval Credibility And Freshness

**Files:**
- Create: `src/copaw/retrieval/web/discover.py`
- Create: `src/copaw/retrieval/web/read.py`
- Create: `src/copaw/retrieval/web/credibility.py`
- Create: `src/copaw/retrieval/web/freshness.py`
- Create: `tests/retrieval/test_web_retrieval.py`

- [ ] **Step 1: Write failing Web retrieval tests**

```python
def test_web_credibility_prefers_official_doc_domain():
    hits = rank_web_hits([...])
    assert hits[0].credibility_score > hits[-1].credibility_score
```

```python
def test_web_freshness_marks_latest_document_query():
    hits = search_web_discover(query="latest openai docs", latest_required=True)
    assert any(hit.freshness_score > 0 for hit in hits)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_web_retrieval.py -q`

Expected: FAIL with missing Web retrieval modules

- [ ] **Step 3: Implement discover/read provider seam**

```python
def search_web_discover(... ) -> list[RetrievalHit]:
    ...
```

```python
def read_web_result(... ) -> RetrievalHit:
    ...
```

- [ ] **Step 4: Implement credibility and freshness scoring**

```python
def credibility_score_for_url(url: str) -> float:
    ...
```

```python
def freshness_score_for_document(updated_at: datetime | None, latest_required: bool) -> float:
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/retrieval/test_web_retrieval.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/retrieval/web/discover.py src/copaw/retrieval/web/read.py src/copaw/retrieval/web/credibility.py src/copaw/retrieval/web/freshness.py tests/retrieval/test_web_retrieval.py
git commit -m "feat: add web retrieval credibility scoring"
```

---

## Task 6: Integrate Retrieval Facade Into Source Collection Frontdoor

**Files:**
- Modify: `src/copaw/research/source_collection/service.py`
- Modify: `src/copaw/research/source_collection/contracts.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Modify: `tests/research/test_source_collection_service.py`
- Modify: `tests/research/test_source_collection_adapters.py`
- Modify: `tests/kernel/test_source_collection_agent_entry.py`
- Modify: `tests/app/test_source_collection_frontdoor_service.py`

- [ ] **Step 1: Write failing source collection integration tests**

```python
def test_source_collection_service_maps_selected_hits_into_formal_sources_and_findings():
    result = service.collect(...)
    assert result.collected_sources
    assert result.findings
```

```python
def test_frontdoor_preserves_light_heavy_route_while_using_new_retrieval_plan():
    result = frontdoor.run_source_collection_frontdoor(...)
    assert result.route_mode == "light"
    assert result.collected_sources
```

```python
def test_artifact_followup_lane_still_maps_to_formal_artifact_source():
    result = service.collect(...)
    assert any(source.source_kind == "artifact" for source in result.collected_sources)
```

```python
def test_heavy_frontdoor_still_reuses_baidu_owner_for_followup_session():
    result = frontdoor.run_source_collection_frontdoor(...)
    assert result.route_mode == "heavy"
    assert result.session_id is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_source_collection_frontdoor_service.py -q`

Expected: FAIL with missing retrieval injection / missing enriched payload

- [ ] **Step 3: Inject retrieval facade into SourceCollectionService**

```python
class SourceCollectionService:
    def __init__(..., retrieval_facade: RetrievalFacade | None = None):
        ...
```

- [ ] **Step 4: Preserve frontdoor responsibilities**

Implement:
- `route_collection_mode()` stays unchanged for `light / heavy / execution_agent_id`
- retrieval planner runs inside the chosen lane
- `collect_sources` tool entry continues to call the frontdoor, not the retrieval layer directly

- [ ] **Step 5: Enrich round/session payload safely**

Persist:
- top-level `sources / findings / conflicts / gaps / writeback_truth` stay formal
- retrieval `plan / trace / selected_hits / dropped_hits / ranking_rationale / coverage_summary` go into round metadata first

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_source_collection_frontdoor_service.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/research/source_collection/service.py src/copaw/research/source_collection/contracts.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_bootstrap_models.py src/copaw/kernel/query_execution_tools.py tests/research/test_source_collection_service.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_source_collection_frontdoor_service.py
git commit -m "feat: wire retrieval substrate into source collection frontdoor"
```

---

## Task 7: Surface Retrieval Truth In Runtime Center And Frontend

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_research.py`
- Modify: `tests/app/test_runtime_center_research_surface.py`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/researchHelpers.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Write failing Runtime Center backend tests**

```python
def test_runtime_center_research_surface_exposes_retrieval_summary_and_selected_hits():
    response = client.get("/runtime-center/research")
    payload = response.json()
    assert payload["retrieval_summary"]["intent"] == "repo-trace"
    assert payload["selected_hits"]
    assert "coverage" in payload
    assert "dropped_hits" in payload
    assert "retrieval_trace" in payload
```

- [ ] **Step 2: Write failing frontend tests**

```tsx
it("renders retrieval summary, selected hits, and retrieval trace", async () => {
  render(<MainBrainCockpitPanel />)
  expect(await screen.findByText(/检索摘要/i)).toBeInTheDocument()
  expect(await screen.findByText(/命中结果/i)).toBeInTheDocument()
  expect(await screen.findByText(/检索轨迹/i)).toBeInTheDocument()
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_research_surface.py -q`

Run: `npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

Expected: FAIL with missing retrieval payload / UI sections

- [ ] **Step 4: Add retrieval payload serialization**

Expose in `/runtime-center/research`:
- `retrieval_summary`
- `selected_hits`
- `coverage`
- `dropped_hits`
- `retrieval_trace`

while keeping existing:
- `brief`
- `findings`
- `sources`
- `gaps`
- `conflicts`
- `writeback_truth`

- [ ] **Step 5: Render retrieval sections in frontend**

Implement readable Chinese labels for:
- intent
- source/mode
- why matched
- ranking / dropped reason
- gap/conflict summary

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_research_surface.py -q`

Run: `npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/app/routers/runtime_center_payloads.py src/copaw/app/routers/runtime_center_routes_research.py tests/app/test_runtime_center_research_surface.py console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/researchHelpers.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: surface retrieval trace in runtime center"
```

---

## Task 8: Acceptance Matrix, Docs, And Live Smoke

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Test: `tests/retrieval/test_retrieval_contracts.py`
- Test: `tests/retrieval/test_retrieval_planner.py`
- Test: `tests/retrieval/test_retrieval_ranking.py`
- Test: `tests/retrieval/test_local_repo_retrieval.py`
- Test: `tests/retrieval/test_github_retrieval.py`
- Test: `tests/retrieval/test_web_retrieval.py`
- Test: `tests/research/test_source_collection_service.py`
- Test: `tests/research/test_source_collection_adapters.py`
- Test: `tests/kernel/test_source_collection_agent_entry.py`
- Test: `tests/app/test_source_collection_frontdoor_service.py`
- Test: `tests/app/test_runtime_center_research_surface.py`
- Test: `tests/app/test_searching_live_contract.py`
- Test: `tests/app/test_searching_soak_contract.py`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Update architecture docs**

Document:
- retrieval substrate is rebuildable cache, not truth
- `SourceCollectionFrontdoorService / SourceCollectionService` split remains
- research formal truth still lives in `ResearchSession* / Evidence / report / writeback`
- formal closure still includes `knowledge_service.ingest_research_session(...)` and `knowledge_writeback_service.build/apply_research_session_writeback(...)`

- [ ] **Step 2: Run focused L1/L2 regression**

Run:

```bash
PYTHONPATH=src python -m pytest tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py tests/retrieval/test_local_repo_retrieval.py tests/retrieval/test_github_retrieval.py tests/retrieval/test_web_retrieval.py tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_source_collection_frontdoor_service.py tests/app/test_runtime_center_research_surface.py -q
```

Run:

```bash
npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 3: Run L3 smoke**

Run:

```bash
PYTHONPATH=src COPAW_RUN_SEARCHING_LIVE_SMOKE=1 python -m pytest tests/app/test_searching_live_contract.py -q -rs
```

Expected: PASS with explicit live-smoke record for:
- local repo trace question
- local repo field-write/read question
- GitHub repo/object question
- GitHub issue/PR conclusion question
- Web latest official-doc question
- Web conflict/credibility question
- frontdoor HTTP `/runtime-center/research` read-surface smoke

Record each result as `L3`, not as generic “passed”.

- [ ] **Step 4: Run L4 soak**

Run:

```bash
PYTHONPATH=src COPAW_RUN_SEARCHING_SOAK=1 python -m pytest tests/app/test_searching_soak_contract.py -q -rs
```

Expected: PASS for at least one soak covering:
- rebuild index
- repeat same query
- mixed source query
- refresh Runtime Center surface

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md
git commit -m "docs: record searching retrieval substrate rollout"
```

---

## Final Verification Gate

Before claiming completion, run:

```bash
PYTHONPATH=src python -m pytest tests/retrieval/test_retrieval_contracts.py tests/retrieval/test_retrieval_planner.py tests/retrieval/test_retrieval_ranking.py tests/retrieval/test_local_repo_retrieval.py tests/retrieval/test_github_retrieval.py tests/retrieval/test_web_retrieval.py tests/research/test_source_collection_service.py tests/research/test_source_collection_adapters.py tests/kernel/test_source_collection_agent_entry.py tests/app/test_source_collection_frontdoor_service.py tests/app/test_runtime_center_research_surface.py -q
```

```bash
npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Then run the recorded `L3` and `L4` commands and report them separately.

---

## Review Note

按 `writing-plans` 技能原流程，本应再跑一轮 plan-reviewer 子代理复核；但当前回合没有收到用户的显式多 agent / delegation 授权，所以这里不派 reviewer agent，改为由主会话基于已修正 spec 和当前代码现状做人工复核。
