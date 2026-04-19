# Browser Substrate Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one shared browser substrate above CoPaw's existing browser channels/tools, then cut Baidu research input/readback/toggle logic over to it and delete the current provider-specific heuristics.

**Architecture:** Reuse the existing `browser_channel_policy -> surface_control_service -> browser_use -> evidence/state` spine. Add one shared browser substrate layer that owns observe/resolve/execute/readback/verify. Then demote `BaiduPageResearchService` back to research orchestration + page profile usage instead of private DOM heuristics.

**Tech Stack:** Python, pytest, existing CoPaw environment runtime, browser_use, SurfaceControlService, research session models.

---

## File Structure Map

- Create: `src/copaw/environments/surface_execution/browser/__init__.py`
- Create: `src/copaw/environments/surface_execution/browser/contracts.py`
- Create: `src/copaw/environments/surface_execution/browser/observer.py`
- Create: `src/copaw/environments/surface_execution/browser/resolver.py`
- Create: `src/copaw/environments/surface_execution/browser/verifier.py`
- Create: `src/copaw/environments/surface_execution/browser/service.py`
- Create: `tests/environments/test_browser_surface_execution.py`
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `tests/research/test_baidu_page_research_service.py`
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-17-universal-surface-execution-foundation-design.md`

## Task 1: Lock The Two Live Bugs Into Tests

**Files:**
- Modify: `tests/research/test_baidu_page_research_service.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Write the failing test for split action/readback targets**

Add a test that proves one target can be used for `type`, while a different DOM anchor must be used for readback.

```python
def test_submit_chat_question_uses_split_action_and_readback_targets():
    ...
    assert result["input_readback"]["matched"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/test_baidu_page_research_service.py -k "split_action_and_readback" -q`
Expected: FAIL because current service only trusts one temporary readback selector.

- [ ] **Step 3: Write the failing test for scoped deep-think resolution**

Add a test that proves the resolver must not match a full-page container; it must resolve a local toggle near the primary input/action bar.

```python
def test_read_baidu_deep_think_state_scopes_to_local_control_group():
    ...
    assert payload["selector"] == "[data-copaw-deep-think=\"1\"]"
    assert payload["label"] == "深度思考"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/research/test_baidu_page_research_service.py -k "deep_think_state_scopes" -q`
Expected: FAIL because current implementation can match a giant container.

- [ ] **Step 5: Commit red tests**

```bash
git add tests/research/test_baidu_page_research_service.py
git commit -m "test: lock browser substrate live regressions"
```

## Task 2: Create Shared Browser Contracts

**Files:**
- Create: `src/copaw/environments/surface_execution/browser/contracts.py`
- Create: `src/copaw/environments/surface_execution/browser/__init__.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write the failing contract test**

Add tests for the shared typed contracts:

- `BrowserObservation`
- `BrowserTargetCandidate`
- `BrowserExecutionStep`
- `BrowserExecutionResult`

```python
def test_browser_target_candidate_keeps_action_and_readback_separate():
    candidate = BrowserTargetCandidate(
        target_kind="input",
        action_ref="e1",
        readback_selector="#chat-textarea",
        element_kind="textarea",
        scope_anchor="composer",
        score=10,
        reason="primary composer textarea",
    )
    assert candidate.action_ref == "e1"
    assert candidate.readback_selector == "#chat-textarea"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "action_and_readback_separate" -q`
Expected: FAIL because contracts do not exist yet.

- [ ] **Step 3: Write minimal contract models**

Implement the pydantic/dataclass models in `contracts.py` and export them from `__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "action_and_readback_separate" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/__init__.py src/copaw/environments/surface_execution/browser/contracts.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: add browser substrate contracts"
```

## Task 3: Add Shared Observer / Resolver / Verifier

**Files:**
- Create: `src/copaw/environments/surface_execution/browser/observer.py`
- Create: `src/copaw/environments/surface_execution/browser/resolver.py`
- Create: `src/copaw/environments/surface_execution/browser/verifier.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write failing tests for shared observation/resolution**

Cover at least:

- snapshot ref extraction for primary input
- DOM readback selection for `textarea/input/contenteditable`
- scoped toggle lookup within a local control group
- refusal to match a full-page container as a toggle

```python
def test_resolver_prefers_primary_textarea_for_input_action():
    ...

def test_verifier_reads_textarea_value_from_readback_selector():
    ...

def test_resolver_rejects_page_wide_container_as_toggle():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -q`
Expected: FAIL because observer/resolver/verifier modules do not exist yet.

- [ ] **Step 3: Implement minimal observer/resolver/verifier**

Implement:

- observer that captures snapshot text plus optional DOM probe results
- resolver that returns typed `BrowserTargetCandidate`
- verifier that reads `.value` for `textarea/input` and `innerText/textContent` for contenteditable/generic nodes

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/observer.py src/copaw/environments/surface_execution/browser/resolver.py src/copaw/environments/surface_execution/browser/verifier.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: add shared browser observer resolver verifier"
```

## Task 4: Add Shared Browser Service

**Files:**
- Create: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write failing service tests**

Add tests that prove the shared service can:

- observe page state
- resolve a target slot
- execute via an injected browser runner
- read back and verify success

```python
def test_browser_surface_service_executes_type_with_split_readback():
    ...

def test_browser_surface_service_executes_scoped_toggle_click():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "browser_surface_service" -q`
Expected: FAIL because service does not exist yet.

- [ ] **Step 3: Implement minimal service**

The service should:

- accept a browser runner callable
- call observer
- call resolver
- execute one step
- call verifier
- return `BrowserExecutionResult`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "browser_surface_service" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/service.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: add shared browser substrate service"
```

## Task 5: Cut Baidu Input Flow Over To Shared Substrate

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `tests/research/test_baidu_page_research_service.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Keep only a Baidu page profile seam in the service**

Refactor `BaiduPageResearchService` so provider code describes page slots like:

- `primary_input`
- `submit_button`
- `reasoning_toggle_group`
- `answer_stream_region`

Do not let it keep its own general resolver/verifier logic.

- [ ] **Step 2: Replace `_resolve_chat_input_target(...)` and `_read_chat_input_readback(...)`**

Route both through the shared browser substrate service.

- [ ] **Step 3: Delete the temporary single-source readback rule**

Remove `[data-copaw-chat-input="1"]` as the sole canonical readback anchor.

- [ ] **Step 4: Run focused regression**

Run: `python -m pytest tests/research/test_baidu_page_research_service.py -k "split_action_and_readback or submit_chat_question" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py tests/research/test_baidu_page_research_service.py
git commit -m "refactor: cut baidu input flow over to shared browser substrate"
```

## Task 6: Cut Baidu Deep-Think Toggle Over To Shared Substrate

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `tests/research/test_baidu_page_research_service.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Replace `_read_baidu_deep_think_state(...)`**

Use the shared observer/resolver path with a local control-group profile.

- [ ] **Step 2: Replace `_ensure_baidu_deep_think_enabled(...)`**

Make it execute and verify through the shared browser substrate service instead of a free-form page scan.

- [ ] **Step 3: Delete the page-wide container match rule**

Remove full-page `button/label/span/div` scanning for the deep-think switch.

- [ ] **Step 4: Run focused regression**

Run: `python -m pytest tests/research/test_baidu_page_research_service.py -k "deep_think" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py tests/research/test_baidu_page_research_service.py
git commit -m "refactor: cut baidu deep think flow over to shared browser substrate"
```

## Task 7: Run Regression And Live Acceptance

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-17-universal-surface-execution-foundation-design.md`
- Test: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/research/test_baidu_page_research_service.py`
- Test: `tests/research/test_baidu_page_contract.py`
- Test: `scripts/live_external_information_chain_acceptance.py`

- [ ] **Step 1: Run default regression for the new shared substrate**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_page_contract.py -q`
Expected: PASS

- [ ] **Step 2: Run live acceptance**

Run: `python scripts/live_external_information_chain_acceptance.py --output tmp/live_external_information_chain_acceptance_result.json`
Expected:

- `main_brain` not falsely marked completed
- `cron_monitoring` not falsely marked completed
- `industry-researcher-live-demo` can keep one thread and complete when login/runtime are healthy

- [ ] **Step 3: If live fails, write one UTF-8 diagnostic artifact and stop**

Do not pile on more heuristics. Record the exact failure surface first.

- [ ] **Step 4: Update docs**

Record the browser substrate cutover status in:

- `TASK_STATUS.md`
- `docs/superpowers/specs/2026-04-17-universal-surface-execution-foundation-design.md`

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md docs/superpowers/specs/2026-04-17-universal-surface-execution-foundation-design.md tmp/live_external_information_chain_acceptance_result.json
git commit -m "docs: record browser substrate cutover acceptance"
```

## Task 8: Final Integration

**Files:**
- Modify: any touched files from previous tasks

- [ ] **Step 1: Run the full final verification set**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_page_contract.py -q
python scripts/live_external_information_chain_acceptance.py --output tmp/live_external_information_chain_acceptance_result.json
git diff --check
git status --short
```

Expected:

- pytest green
- live output matches actual status
- `git diff --check` clean
- only intended files modified

- [ ] **Step 2: Commit on main**

```bash
git add src/copaw/environments/surface_execution/browser src/copaw/research/baidu_page_research_service.py tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py tests/research/test_baidu_page_contract.py TASK_STATUS.md docs/superpowers/specs/2026-04-17-universal-surface-execution-foundation-design.md docs/superpowers/specs/2026-04-18-browser-substrate-pattern-audit-and-cutover-design.md docs/superpowers/plans/2026-04-18-browser-substrate-cutover-implementation-plan.md
git commit -m "feat: add shared browser substrate cutover"
```

- [ ] **Step 3: Push main**

```bash
git push origin main
```
