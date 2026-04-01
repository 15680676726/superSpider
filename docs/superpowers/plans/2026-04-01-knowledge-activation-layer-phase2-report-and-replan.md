# Knowledge Activation Layer Phase 2 Report And Replan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Knowledge Activation Layer into industry report synthesis and follow-up backlog/replan generation so main-brain closure can use activation-derived constraints, contradictions, and next-action signals instead of relying only on raw report/evidence summaries.

**Architecture:** This plan covers the second executable slice of the Knowledge Activation Layer. It keeps activation derived, reuses the existing report synthesis and report-closure pipeline, and injects activation output into synthesis/replan decisioning and backlog materialization. It does not yet add Runtime Center activation views or persisted graph relations; those remain later phases.

**Tech Stack:** Python 3.11, Pydantic, SQLite-backed state repositories, existing CoPaw industry/reporting/memory services, Pytest.

---

## Scope Check

The remaining activation-layer roadmap has at least three independent downstream areas:

- report synthesis + backlog/replan
- Runtime Center activation visualization
- optional persisted relation graph

This plan covers only **Phase 2**:

1. activation-aware report synthesis
2. activation-aware report-closure backlog writeback
3. activation-aware current-cycle/replan payload propagation

Future plans are still required for:

- Runtime Center activation views
- optional graph persistence

## Execution Environment

Run this plan in the existing dedicated worktree for this feature branch:

```powershell
cd D:\word\copaw\.worktrees\knowledge-activation-phase1
```

## File Map

### Existing files to modify

- `src/copaw/industry/report_synthesis.py`
  - Add activation-aware inputs and synthesis fields without changing current truth sources.
- `src/copaw/industry/service_report_closure.py`
  - Feed activation-derived signals into follow-up backlog/replan metadata carry-over.
- `src/copaw/industry/service_runtime_views.py`
  - Preserve activation-derived replan context in runtime/current-cycle read payloads.
- `src/copaw/industry/service_lifecycle.py`
  - Pass activation service/signals into report-closure and cycle synthesis flow.
- `src/copaw/app/runtime_bootstrap_domains.py`
  - Wire `memory_activation_service` into `IndustryService` runtime bindings if needed.
- `src/copaw/industry/service_context.py`
  - Extend runtime bindings model only if industry service needs a clean activation hook.
- `tests/industry/test_report_synthesis.py`
  - Add activation-aware synthesis tests.
- `tests/app/industry_api_parts/runtime_updates.py`
  - Add integration tests proving activation flows into cycle synthesis and focused runtime.
- `tests/app/industry_api_parts/bootstrap_lifecycle.py`
  - Add integration tests for activation-aware follow-up backlog materialization.
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
  - Update landed boundaries after Phase 2.

## Task 1: Add Failing Tests for Activation-Aware Report Synthesis

**Files:**
- Modify: `tests/industry/test_report_synthesis.py`
- Modify: `src/copaw/industry/report_synthesis.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_synthesize_reports_includes_activation_constraints_in_replan_surface():
    ...
    synthesis = synthesize_reports([report], activation_result=activation)
    assert synthesis["activation"]["top_constraints"]
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_surfaces_activation_contradictions():
    ...
    synthesis = synthesize_reports([report], activation_result=activation)
    assert synthesis["activation"]["contradiction_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/industry/test_report_synthesis.py -k activation -v
```

Expected: FAIL because report synthesis does not yet accept or emit activation-derived context.

- [ ] **Step 3: Write minimal implementation**

```python
def synthesize_reports(
    reports: Sequence[AgentReportRecord],
    *,
    activation_result: object | None = None,
) -> dict[str, Any]:
    ...
    if activation_result is not None:
        payload["activation"] = {
            "top_constraints": list(getattr(activation_result, "top_constraints", []) or []),
            "top_next_actions": list(getattr(activation_result, "top_next_actions", []) or []),
            "contradiction_count": len(list(getattr(activation_result, "contradictions", []) or [])),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/industry/test_report_synthesis.py -k activation -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/industry/test_report_synthesis.py src/copaw/industry/report_synthesis.py
git commit -m "feat: add activation-aware report synthesis"
```

## Task 2: Add Failing Tests for Activation-Aware Follow-Up Backlog Materialization

**Files:**
- Modify: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Modify: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/industry/service_lifecycle.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_report_closure_carries_activation_constraints_into_followup_backlog(...):
    ...
    assert backlog_item.metadata["activation_top_constraints"]
    assert backlog_item.metadata["activation_top_next_actions"]


def test_report_closure_carries_activation_refs_into_followup_backlog(...):
    ...
    assert backlog_item.metadata["activation_support_refs"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k activation_followup -v
```

Expected: FAIL because report-closure metadata does not yet carry activation signals.

- [ ] **Step 3: Write minimal implementation**

```python
def record_report_synthesis_backlog(...):
    ...
    if isinstance(synthesis.get("activation"), dict):
        metadata.update({
            "activation_top_constraints": synthesis["activation"].get("top_constraints", []),
            "activation_top_next_actions": synthesis["activation"].get("top_next_actions", []),
            "activation_support_refs": synthesis["activation"].get("support_refs", []),
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k activation_followup -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/app/industry_api_parts/bootstrap_lifecycle.py src/copaw/industry/service_report_closure.py src/copaw/industry/service_lifecycle.py
git commit -m "feat: carry activation metadata into followup backlog"
```

## Task 3: Add Failing Tests for Activation-Aware Current-Cycle Runtime Surface

**Files:**
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Modify: `src/copaw/industry/service_runtime_views.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_updates_expose_activation_summary_on_current_cycle_surface(...):
    ...
    assert detail.current_cycle["synthesis"]["activation"]["top_constraints"]


def test_runtime_updates_keep_replan_focus_and_activation_summary_together(...):
    ...
    assert payload["main_chain"]["nodes"]
    assert payload["current_cycle"]["synthesis"]["activation"]["contradiction_count"] >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/industry_api_parts/runtime_updates.py -k activation_summary -v
```

Expected: FAIL because runtime view payloads do not yet surface activation-derived synthesis context.

- [ ] **Step 3: Write minimal implementation**

```python
current_cycle_payload["synthesis"]["activation"] = synthesis.get("activation", {})
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/industry_api_parts/runtime_updates.py -k activation_summary -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/app/industry_api_parts/runtime_updates.py src/copaw/industry/service_runtime_views.py
git commit -m "feat: expose activation summary on cycle runtime surfaces"
```

## Task 4: Wire Activation Service into Industry Runtime Path

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service.py`
- Modify: `tests/app/test_industry_service_wiring.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_industry_service_runtime_bindings_wire_memory_activation_service(...):
    ...
    assert industry_service._memory_activation_service is memory_activation_service
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_industry_service_wiring.py -k memory_activation_service -v
```

Expected: FAIL because industry runtime bindings do not yet thread the activation service.

- [ ] **Step 3: Write minimal implementation**

```python
# runtime_bootstrap_domains.py
industry_service = IndustryService(..., memory_activation_service=memory_activation_service, ...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_industry_service_wiring.py -k memory_activation_service -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/runtime_bootstrap_domains.py src/copaw/industry/service_context.py src/copaw/industry/service.py tests/app/test_industry_service_wiring.py
git commit -m "feat: wire activation service into industry runtime"
```

## Task 5: Run Phase 2 Regression and Update Docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Run the regression suite**

Run:

```powershell
python -m pytest tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_industry_service_wiring.py -v
```

Expected: PASS

- [ ] **Step 2: Update the docs**

```markdown
- report synthesis can now consume activation-derived constraints and contradictions
- follow-up backlog materialization now carries activation metadata
- current-cycle runtime surfaces now expose activation summaries
```

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "docs: record knowledge activation phase2"
```

## Done Definition

Phase 2 is complete only when all of the following are true:

- report synthesis accepts activation-derived input
- report-closure backlog materialization carries activation metadata
- current-cycle runtime surfaces expose activation summaries
- industry runtime wiring can provide activation service to report/replan flow
- the regression suite in Task 5 is green

## Follow-Up Planning Gate

Do not start the next activation phase from this branch until this plan is green.

Write follow-up plans for:

1. Runtime Center activation views
2. optional persisted relation graph
