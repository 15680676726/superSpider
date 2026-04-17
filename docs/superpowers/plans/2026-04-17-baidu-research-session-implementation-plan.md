# Baidu Research Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 researcher 增加正式的百度多轮研究会话能力，让手动触发、主脑追问、监控任务触发三类入口都能走同一条“多轮问答 + 网页深挖 + 文档下载 + 主脑汇报 + 分层沉淀”主链。

**Architecture:** 新增 `ResearchSessionRecord / ResearchSessionRoundRecord` 两个正式对象，并以集中式 `BaiduPageResearchService` 作为唯一 owner。聊天、主脑追问和监控任务只负责创建研究会话；真正的浏览器执行、轮次决策、链接/文档深挖、report 产出与结果分流全部由 research service 收口，继续复用现有 `tool:browser_use / AgentReport / knowledge / memory / evidence` 主链，不引入第二真相源。

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, React + TypeScript + Ant Design + Vitest

**Trigger Contract:** researcher 不是通用自动巡检器。它只能由以下三类正式入口启动：

- 用户直接要求研究
- 主脑围绕当前目标创建研究 brief
- 主脑或用户已建立带明确目标的 monitoring brief，由 schedule/cron 负责定时唤醒

没有正式 brief，就不创建 research session。

**Execution note (`2026-04-17`):** 浏览器 runtime 跨 loop / Windows selector policy 启动问题已修复；`BaiduPageResearchService` 现在默认会把 researcher 的百度登录态持久化到 `WORKING_DIR/state/research_browser_storage/<owner_agent_id>.json`。当前 live 真边界已经从“浏览器起不来”收口为“真实百度页面还需要用户先登录”。

---

## File Map

**Backend truth / persistence**

- Create: `src/copaw/state/models_research.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_research.py`
- Test: `tests/state/test_state_store_migration.py`
- Create: `tests/state/test_research_repositories.py`

**Backend research service**

- Create: `src/copaw/research/models.py`
- Create: `src/copaw/research/baidu_page_contract.py`
- Create: `src/copaw/research/baidu_page_research_service.py`
- Create: `src/copaw/research/__init__.py`
- Test: `tests/research/test_baidu_page_contract.py`
- Test: `tests/research/test_baidu_page_research_service.py`

**Backend runtime wiring**

- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`

**Backend integration**

- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/industry/compiler.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_reports.py`
- Create: `src/copaw/app/routers/runtime_center_routes_research.py`
- Modify: `src/copaw/app/routers/__init__.py`

**Knowledge / memory / report integration**

- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Test: `tests/memory/test_knowledge_writeback_service.py`
- Create: `tests/research/test_research_knowledge_ingestion.py`

**Frontend**

- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Create: `console/src/pages/RuntimeCenter/researchHelpers.ts`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

**Docs / validation**

- Modify: `implementation_plan.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `TASK_STATUS.md`
- Create: `tests/app/test_research_session_api.py`
- Create: `tests/app/test_research_session_live_contract.py`

---

## Task 1: Persist Formal Research Session Truth

**Files:**
- Create: `src/copaw/state/models_research.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories/base.py`
- Create: `src/copaw/state/repositories/sqlite_research.py`
- Test: `tests/state/test_state_store_migration.py`
- Create: `tests/state/test_research_repositories.py`

- [ ] **Step 1: Write the failing repository tests**

```python
def test_research_session_repository_round_trip(tmp_path):
    session = ResearchSessionRecord(
        id="research-session-1",
        provider="baidu-page",
        owner_agent_id="industry-researcher-demo",
        trigger_source="user-direct",
        goal="梳理紫微斗数核心术语和主流流派差异",
        status="queued",
    )
    saved = repo.upsert_research_session(session)
    assert saved.goal.startswith("梳理紫微斗数")
```

```python
def test_research_round_repository_round_trip(tmp_path):
    round_record = ResearchSessionRoundRecord(
        id="research-round-1",
        session_id="research-session-1",
        round_index=1,
        question="紫微斗数有哪些核心术语？",
        decision="continue",
    )
    saved = repo.upsert_research_round(round_record)
    assert saved.round_index == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_research_repositories.py -q`
Expected: FAIL with missing models / repository methods / schema

- [ ] **Step 3: Add the new models and SQLite schema**

```python
class ResearchSessionRecord(UpdatedRecord):
    provider: str
    owner_agent_id: str
    trigger_source: str
    goal: str
    status: Literal["queued", "running", "waiting-login", "deepening", "summarizing", "completed", "failed", "cancelled"]
```

```python
class ResearchSessionRoundRecord(UpdatedRecord):
    session_id: str
    round_index: int
    question: str
    response_summary: str | None = None
    decision: Literal["continue", "stop", "login_required", "failed"] = "continue"
```

- [ ] **Step 4: Run repository and migration tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_research_repositories.py tests/state/test_state_store_migration.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_research.py src/copaw/state/store.py src/copaw/state/models.py src/copaw/state/__init__.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_research.py tests/state/test_state_store_migration.py tests/state/test_research_repositories.py
git commit -m "feat: persist baidu research sessions"
```

---

## Task 2: Build Baidu Page Contract And Extraction Rules

**Files:**
- Create: `src/copaw/research/models.py`
- Create: `src/copaw/research/baidu_page_contract.py`
- Test: `tests/research/test_baidu_page_contract.py`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_baidu_page_contract_detects_logged_out_state():
    html = "<button>登录</button>"
    result = detect_login_state(html)
    assert result.state == "login-required"
```

```python
def test_baidu_page_contract_extracts_answer_and_links():
    html = """
    <main>
      <div class="answer">紫微斗数核心术语包括命宫、身宫、主星。</div>
      <a href="https://example.com/guide">参考资料</a>
    </main>
    """
    result = extract_answer_contract(html)
    assert "命宫" in result.answer_text
    assert result.links[0].url == "https://example.com/guide"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_page_contract.py -q`
Expected: FAIL with missing extraction contract

- [ ] **Step 3: Implement minimal contract and parser**

```python
class BaiduPageContractResult(BaseModel):
    login_state: Literal["ready", "login-required", "unknown"]
    answer_text: str = ""
    links: list[ResearchLink] = Field(default_factory=list)
```

```python
def detect_login_state(page_text: str) -> LoginStateResult: ...
def extract_answer_contract(snapshot_text: str) -> BaiduPageContractResult: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_page_contract.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/models.py src/copaw/research/baidu_page_contract.py tests/research/test_baidu_page_contract.py
git commit -m "feat: add baidu page contract parser"
```

---

## Task 3: Implement Multi-Round Baidu Research Session Service

**Files:**
- Create: `src/copaw/research/baidu_page_research_service.py`
- Create: `src/copaw/research/__init__.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
def test_research_service_creates_session_and_first_round(tmp_path):
    result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )
    assert result.session.status == "queued"
    assert result.session.goal == "梳理电商平台入门知识结构"
```

```python
def test_research_service_marks_waiting_login_when_baidu_not_logged_in(tmp_path):
    result = service.run_session("research-session-1")
    assert result.session.status == "waiting-login"
```

```python
def test_research_service_stops_after_two_rounds_without_new_findings(tmp_path):
    result = service.run_session("research-session-1")
    assert result.session.status == "completed"
    assert result.stop_reason == "no-new-findings"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_page_research_service.py -q`
Expected: FAIL with missing service

- [ ] **Step 3: Implement the service skeleton**

```python
class BaiduPageResearchService:
    def start_session(self, *, goal: str, trigger_source: str, owner_agent_id: str, ...): ...
    def run_session(self, session_id: str): ...
    def continue_session(self, session_id: str): ...
    def summarize_session(self, session_id: str): ...
```

- [ ] **Step 4: Add round loop and stop-condition logic**

```python
MAX_BAIDU_ROUNDS = 5
MAX_DEEP_LINKS = 3
MAX_DOWNLOADS = 2
MAX_NO_NEW_FINDINGS_STREAK = 2
```

- [ ] **Step 5: Run service tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_page_research_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py src/copaw/research/__init__.py tests/research/test_baidu_page_research_service.py
git commit -m "feat: add baidu multi-round research service"
```

---

## Task 4: Wire Browser Actions, Link Deepening, And Downloads Into Research Sessions

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `src/copaw/agents/tools/browser_control.py`
- Modify: `src/copaw/agents/tools/browser_control_actions_extended.py`
- Test: `tests/agents/test_browser_tool_evidence.py`
- Create: `tests/research/test_baidu_deepening_flow.py`

- [ ] **Step 1: Write the failing integration tests for deep links and downloads**

```python
def test_research_service_uses_browser_session_to_open_followup_link(tmp_path):
    result = service.run_session("research-session-1")
    assert result.deepened_links[0]["url"].startswith("https://")
```

```python
def test_research_service_records_downloaded_pdf_as_artifact(tmp_path):
    result = service.run_session("research-session-1")
    assert result.downloaded_artifacts
    assert result.downloaded_artifacts[0]["kind"] == "pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_deepening_flow.py -q`
Expected: FAIL because deepening and download orchestration is not wired

- [ ] **Step 3: Implement bounded deepening**

```python
def _select_high_value_links(self, raw_links: list[ResearchLink]) -> list[ResearchLink]:
    return raw_links[:3]
```

```python
def _select_download_candidates(self, extracted_links: list[ResearchLink]) -> list[ResearchLink]:
    return [item for item in extracted_links if item.kind in {"pdf", "txt", "md", "csv", "xlsx"}][:2]
```

- [ ] **Step 4: Run deepening and browser evidence tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_baidu_deepening_flow.py tests/agents/test_browser_tool_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py src/copaw/agents/tools/browser_control.py src/copaw/agents/tools/browser_control_actions_extended.py tests/research/test_baidu_deepening_flow.py tests/agents/test_browser_tool_evidence.py
git commit -m "feat: add bounded baidu deepening and downloads"
```

---

## Task 5: Emit Formal Research Reports And Evidence

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Test: `tests/app/test_research_session_api.py`
- Create: `tests/research/test_research_report_writeback.py`

- [ ] **Step 1: Write the failing report writeback tests**

```python
def test_completed_research_session_generates_researcher_report(tmp_path):
    result = service.summarize_session("research-session-1")
    assert result.final_report_id is not None
```

```python
def test_research_report_includes_question_excerpt_links_and_provider(tmp_path):
    result = service.summarize_session("research-session-1")
    report = report_repo.get_report(result.final_report_id)
    assert report.metadata["provider"] == "baidu-page"
    assert report.metadata["citations"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_research_report_writeback.py -q`
Expected: FAIL because no formal report writeback exists

- [ ] **Step 3: Implement report and evidence emission**

```python
def _emit_research_report(self, session: ResearchSessionRecord, rounds: list[ResearchSessionRoundRecord]) -> str: ...
def _emit_research_evidence(self, session: ResearchSessionRecord, round_record: ResearchSessionRoundRecord) -> list[str]: ...
```

- [ ] **Step 4: Run report and API tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_research_report_writeback.py tests/app/test_research_session_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_bootstrap_models.py tests/research/test_research_report_writeback.py tests/app/test_research_session_api.py
git commit -m "feat: write research sessions back as formal reports"
```

---

## Task 6: Route Stable Findings Into Work Context Memory And Industry Knowledge

**Files:**
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Test: `tests/memory/test_knowledge_writeback_service.py`
- Create: `tests/research/test_research_knowledge_ingestion.py`

- [ ] **Step 1: Write the failing ingestion tests**

```python
def test_research_result_routes_project_specific_findings_to_work_context_memory(tmp_path):
    result = ingest_service.ingest_research_findings(...)
    assert result["work_context_chunk_ids"]
```

```python
def test_research_result_routes_stable_reusable_findings_to_industry_knowledge(tmp_path):
    result = ingest_service.ingest_research_findings(...)
    assert result["industry_document_id"].startswith("knowledge-doc:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_research_knowledge_ingestion.py -q`
Expected: FAIL because research findings are not yet classified and ingested

- [ ] **Step 3: Implement bounded classification and ingestion**

```python
def _classify_finding_scope(self, finding: dict[str, Any]) -> Literal["evidence-only", "work_context", "industry"]:
    ...
```

- [ ] **Step 4: Run ingestion and adjacent memory tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/research/test_research_knowledge_ingestion.py tests/memory/test_knowledge_writeback_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/knowledge_service.py src/copaw/memory/retain_service.py src/copaw/memory/knowledge_writeback_service.py tests/research/test_research_knowledge_ingestion.py tests/memory/test_knowledge_writeback_service.py
git commit -m "feat: classify research findings into memory and knowledge"
```

---

## Task 7: Connect Manual Trigger, Scheduled Trigger, And Main-Brain Followup

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/industry/compiler.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Create: `src/copaw/app/routers/runtime_center_routes_research.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Test: `tests/app/test_research_session_api.py`
- Create: `tests/kernel/test_main_brain_research_followup.py`
- Create: `tests/app/test_research_schedule_trigger.py`

- [ ] **Step 1: Write the failing trigger tests**

```python
def test_main_brain_can_start_research_session_when_external_info_is_missing(tmp_path):
    response = service.handle_user_turn("去查一下电商平台入门知识")
    assert response["research_session_id"]
```

```python
def test_researcher_schedule_can_create_baidu_research_session(tmp_path):
    result = cron_executor.run(...)
    assert result["research_session_id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/kernel/test_main_brain_research_followup.py tests/app/test_research_schedule_trigger.py tests/app/test_research_session_api.py -q`
Expected: FAIL because triggers do not yet route into research service

- [ ] **Step 3: Wire the three entry paths**

```python
def _should_delegate_to_research(self, turn_text: str, ... ) -> bool: ...
```

```python
metadata["research_provider"] = "baidu-page"
metadata["research_mode"] = "monitoring-brief"
```

- [ ] **Step 4: Run trigger tests**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/kernel/test_main_brain_research_followup.py tests/app/test_research_schedule_trigger.py tests/app/test_research_session_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py src/copaw/industry/compiler.py src/copaw/industry/service_strategy.py src/copaw/app/runtime_center/conversations.py src/copaw/app/routers/runtime_center_routes_research.py src/copaw/app/routers/__init__.py tests/kernel/test_main_brain_research_followup.py tests/app/test_research_schedule_trigger.py tests/app/test_research_session_api.py
git commit -m "feat: route user-direct monitoring and followup research triggers"
```

---

## Task 8: Expose Minimal Runtime Center Research Read Surface

**Files:**
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Create: `console/src/pages/RuntimeCenter/researchHelpers.ts`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
it("shows waiting-login when baidu research needs user login", () => {
  render(<MainBrainCockpitPanel ... />)
  expect(screen.getByText("待登录百度")).toBeInTheDocument()
})
```

```tsx
it("shows current research goal and round progress for researcher", () => {
  render(<MainBrainCockpitPanel ... />)
  expect(screen.getByText("当前研究目标")).toBeInTheDocument()
  expect(screen.getByText("第 2 轮")).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cmd /c npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: FAIL because runtime center does not yet expose research state

- [ ] **Step 3: Implement the minimal read surface**

```ts
export type ResearchSessionSummary = {
  id: string
  status: string
  goal: string
  roundCount: number
  waitingLogin: boolean
}
```

- [ ] **Step 4: Run frontend tests**

Run: `cmd /c npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/RuntimeCenter/index.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/researchHelpers.ts console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: expose research session state in runtime center"
```

---

## Task 9: Sync Core Docs With Live Truth

**Files:**
- Modify: `implementation_plan.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Add the new live truth to implementation docs**

Document:
- researcher now owns bounded `baidu-page` multi-round research sessions
- baidu answer is not formal truth
- session output flows into report / evidence / memory / knowledge

- [ ] **Step 2: Update the data model draft**

Document:
- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`
- routing into `AgentReport`, `KnowledgeChunkRecord`, and `EvidenceRecord`

- [ ] **Step 3: Update API transition map and task status**

Document:
- entry surfaces
- owner service
- runtime center read surface
- current verification status

- [ ] **Step 4: Commit**

```bash
git add implementation_plan.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md TASK_STATUS.md
git commit -m "docs: add baidu research session architecture and status"
```

---

## Task 10: Run Real Acceptance, Not Just Unit Tests

**Files:**
- Create: `tests/app/test_research_session_live_contract.py`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Write the bounded live smoke contract**

```python
def test_live_baidu_research_session_round_trip(...):
    # gated by env var and logged-in browser precondition
    ...
```

- [ ] **Step 2: Run focused non-live regressions first**

Run: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests/state/test_research_repositories.py tests/research/test_baidu_page_contract.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_deepening_flow.py tests/research/test_research_report_writeback.py tests/research/test_research_knowledge_ingestion.py tests/kernel/test_main_brain_research_followup.py tests/app/test_research_schedule_trigger.py tests/app/test_research_session_api.py -q`
Expected: PASS

- [ ] **Step 3: Run frontend regressions**

Run: `cmd /c npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

- [ ] **Step 4: Run gated live smoke with a real logged-in Baidu session**

Run: `PYTHONPATH=src $env:COPAW_RUN_BAIDU_RESEARCH_LIVE_SMOKE='1'; .\.venv\Scripts\python.exe -m pytest tests/app/test_research_session_live_contract.py -q`
Expected: PASS or explicit SKIP when login/runtime preconditions are unavailable

- [ ] **Step 5: Record results in `TASK_STATUS.md` and commit**

```bash
git add tests/app/test_research_session_live_contract.py TASK_STATUS.md
git commit -m "test: validate baidu research session acceptance flow"
```

---

## Notes For Execution

- Do not bypass the formal `AgentReport` chain. Every completed session must end in a report to the main brain.
- Do not write Baidu raw answers directly into long-term truth.
- Keep `BaiduPageResearchService` as the only owner of multi-round loop state. Chat, schedules, and main-brain followups are triggers only.
- Reuse existing browser truth and evidence surfaces instead of inventing a parallel browser runtime.
- Fail closed on `waiting-login`, page contract drift, and repeated no-new-findings streak.
