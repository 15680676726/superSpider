# Buddy Onboarding Collaboration Contract Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Buddy onboarding step 2 from clarify-question interviewing to a formal collaboration-contract flow, while keeping the downstream formal chain (`HumanProfile -> GrowthTarget -> BuddyDomainCapabilityRecord -> IndustryInstance`) intact and making runtime/persona actually read the confirmed contract.

**Architecture:** Apply a hard cut. `BuddyOnboardingSessionRecord` becomes a contract-draft carrier instead of a question transcript, `CompanionRelationship` becomes the long-term truth object for collaboration rules, and `BuddyOnboardingReasoner` changes from interviewer to compiler. Frontend, API, projection, and runtime prompt surfaces all move off `clarify` semantics together so no parallel truth remains.

**Tech Stack:** Python, FastAPI, SQLite, Pydantic, React, TypeScript, Ant Design, pytest, Vitest

---

## Preflight Guardrails

- Current workspace already contains unrelated dirty edits in several Buddy/runtime files. Do not mix this cutover into those changes.
- Execute this plan only from a clean branch/worktree, or first preserve unrelated local edits elsewhere.
- This is a hard-cut task. Do not add compatibility shims for:
  - `/buddy/onboarding/clarify`
  - `/buddy/onboarding/clarify/start`
  - `question_count`
  - `tightened`
  - `next_question`
  - `transcript`
- Do not move collaboration contract into `GrowthTarget.final_goal` or `GrowthTarget.why_it_matters`.
- Do not turn the main brain into a leaf executor. This cutover only changes Buddy onboarding front-door truth and runtime read contracts.

## File Structure

- `src/copaw/state/models_buddy.py`
  Responsibility: extend `CompanionRelationship` with explicit collaboration-contract truth fields.
- `src/copaw/state/repositories_buddy.py`
  Responsibility: redefine `BuddyOnboardingSessionRecord` around contract draft fields, persist/read draft contract plus confirmed relationship fields, and remove clarify-era persistence.
- `src/copaw/state/store.py`
  Responsibility: migrate Buddy onboarding / relationship SQLite tables for the hard-cut schema.
- `tests/state/test_buddy_models.py`
  Responsibility: model validation/serialization coverage for the new relationship/session contract fields.
- `tests/state/test_state_store_migration.py`
  Responsibility: migration coverage for old Buddy databases missing the new collaboration fields.
- `src/copaw/kernel/buddy_onboarding_reasoner.py`
  Responsibility: compile directions/goals/backlog from `HumanProfile + collaboration_contract`, not from interview turns.
- `src/copaw/kernel/buddy_onboarding_service.py`
  Responsibility: start/save contract draft, invoke the compiler, confirm direction, persist `CompanionRelationship`, and project contract into `IndustryInstance.execution_core_identity_payload`.
- `src/copaw/app/routers/buddy_routes.py`
  Responsibility: delete clarify endpoints and expose contract endpoints with the new request/response schema.
- `tests/kernel/test_buddy_onboarding_service.py`
  Responsibility: backend behavior for contract start/submit, direction preview/confirm, and persisted relationship/runtime payload truth.
- `tests/app/test_buddy_routes.py`
  Responsibility: API contract coverage for `/buddy/onboarding/contract*`, preview, and confirm flows.
- `src/copaw/kernel/buddy_projection_service.py`
  Responsibility: project draft contract during onboarding and confirmed contract after confirmation.
- `src/copaw/kernel/buddy_persona_prompt.py`
  Responsibility: include confirmed collaboration rules in Buddy persona generation.
- `src/copaw/kernel/query_execution_prompt.py`
  Responsibility: include confirmed collaboration rules from `execution_core_identity_payload` in execution runtime prompts.
- `src/copaw/kernel/buddy_runtime_focus.py`
  Responsibility: keep runtime-facing Buddy focus summaries aligned with the new contract-readable surfaces if the current focus block reads onboarding truth.
- `tests/kernel/test_buddy_projection_service.py`
  Responsibility: projection coverage for onboarding/relationship contract surfaces.
- `tests/kernel/test_main_brain_runtime_context_buddy_prompt.py`
  Responsibility: runtime prompt coverage for contract fields after confirmation.
- `tests/kernel/test_main_brain_chat_service.py`
  Responsibility: Buddy persona prompt coverage for confirmed collaboration rules.
- `console/src/api/modules/buddy.ts`
  Responsibility: rename/remove clarify-era types and expose typed contract endpoints/responses.
- `console/src/runtime/buddyFlow.ts`
  Responsibility: keep Buddy entry-flow types aligned with the new onboarding states.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Responsibility: replace question-based step 2 UI with fixed collaboration-contract form and step 3 confirmation summary.
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  Responsibility: UI coverage for the contract form flow and removed clarify wording.
- `console/src/runtime/buddyFlow.test.ts`
  Responsibility: entry-flow regression coverage without question-count/next-question assumptions.
- `console/src/api/modules/buddy.test.ts`
  Responsibility: frontend API typing/endpoint regression for the contract routes.
- `TASK_STATUS.md`
  Responsibility: record the hard-cut from clarify-interview to collaboration-contract onboarding.
- `DATA_MODEL_DRAFT.md`
  Responsibility: document `CompanionRelationship` as the formal collaboration-contract truth and clarify that onboarding session only carries draft contract state.
- `API_TRANSITION_MAP.md`
  Responsibility: record `/buddy/onboarding/contract*` as the active ingress and note clarify route retirement.

## Recommended Commit Slices

1. `feat: hard-cut buddy onboarding state to collaboration contract`
2. `feat: switch buddy onboarding backend from clarify to contract compile`
3. `feat: wire buddy runtime surfaces to collaboration contract`
4. `feat: replace buddy onboarding frontend clarify flow`
5. `docs: sync buddy collaboration contract cutover`

---

### Task 1: Hard-Cut Buddy State Truth To Contract Draft + Relationship Contract

**Files:**
- Modify: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/state/repositories_buddy.py`
- Modify: `src/copaw/state/store.py`
- Modify: `tests/state/test_buddy_models.py`
- Modify: `tests/state/test_state_store_migration.py`

- [ ] **Step 1: Write the failing state/model tests**

Add coverage like:

```python
def test_companion_relationship_accepts_collaboration_contract_fields() -> None:
    record = CompanionRelationship(
        profile_id="profile-1",
        service_intent="帮我长期推进独立设计工作室",
        collaboration_role="orchestrator",
        autonomy_level="low-risk-autonomous",
        confirm_boundaries=["spend-money", "external-send"],
        report_style="milestone-summary",
        collaboration_notes="先给结论，再给风险。",
    )
    assert record.report_style == "milestone-summary"


def test_buddy_onboarding_session_record_uses_contract_draft_fields() -> None:
    session = BuddyOnboardingSessionRecord(
        session_id="session-1",
        profile_id="profile-1",
        status="direction-ready",
        service_intent="帮我把品牌站做起来",
        collaboration_role="executor",
        autonomy_level="proactive",
        confirm_boundaries=["destructive-change"],
        report_style="result-first",
    )
    assert session.service_intent == "帮我把品牌站做起来"
```

Also add migration assertions that new columns exist and removed clarify-only columns are no longer referenced by repository serialization.

- [ ] **Step 2: Run the focused state suites and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/state/test_buddy_models.py tests/state/test_state_store_migration.py -q
```

Expected: FAIL because relationship/session models and store schema still depend on clarify-era fields.

- [ ] **Step 3: Implement the minimal state/schema cutover**

Update `CompanionRelationship` to add:

```python
service_intent: str = ""
collaboration_role: str = "orchestrator"
autonomy_level: str = "proactive"
confirm_boundaries: list[str] = Field(default_factory=list)
report_style: str = "result-first"
collaboration_notes: str = ""
```

Update `BuddyOnboardingSessionRecord` to remove:

```python
question_count
tightened
next_question
transcript
```

and add:

```python
service_intent: str = ""
collaboration_role: str = "orchestrator"
autonomy_level: str = "proactive"
confirm_boundaries: list[str] = Field(default_factory=list)
report_style: str = "result-first"
collaboration_notes: str = ""
```

Repository/store rules:
- persist `confirm_boundaries` as JSON
- preserve existing direction draft fields
- migrate old DBs without leaving repository code referencing removed clarify columns
- do not create a second contract truth source in a `metadata` blob

- [ ] **Step 4: Re-run the focused state suites and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/state/test_buddy_models.py tests/state/test_state_store_migration.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the state hard-cut**

```bash
git add src/copaw/state/models_buddy.py src/copaw/state/repositories_buddy.py src/copaw/state/store.py tests/state/test_buddy_models.py tests/state/test_state_store_migration.py
git commit -m "feat: hard-cut buddy onboarding state to collaboration contract"
```

---

### Task 2: Replace Interview Reasoner With Contract Compiler

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_reasoner.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] **Step 1: Write the failing compiler-contract tests**

Add/replace coverage so the backend contract is anchored on:

```python
def test_contract_compiler_returns_direction_goal_and_backlog_without_next_question(tmp_path) -> None: ...
def test_contract_compiler_input_is_profile_plus_collaboration_contract(tmp_path) -> None: ...
```

Lock one explicit negative assertion:

```python
assert "next_question" not in result.model_dump()
```

- [ ] **Step 2: Run the focused backend suite and verify it fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_onboarding_service.py -q
```

Expected: FAIL because the reasoner still expects transcript/question_count and emits clarify output.

- [ ] **Step 3: Refactor `BuddyOnboardingReasoner`**

Hard-cut these inputs:

```python
transcript
question_count
tightened
```

Hard-cut these outputs:

```python
next_question
finished
```

Replace them with a compile contract shaped like:

```python
class BuddyOnboardingCompilePayload(BaseModel):
    candidate_directions: list[str]
    recommended_direction: str
    final_goal: str
    why_it_matters: str
    backlog_items: list[str]
```

Compiler rules:
- input = `HumanProfile + collaboration_contract`
- output remains direction/goal/backlog only
- AI is a compiler, not an interviewer
- do not reintroduce hidden “need one more question” behavior

- [ ] **Step 4: Re-run the focused backend suite and verify it passes**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_onboarding_service.py -q
```

Expected: PASS for the compiler contract portions that no longer depend on clarify semantics.

---

### Task 3: Hard-Cut Backend Routes And Service Flow To Contract Endpoints

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Modify: `tests/app/test_buddy_routes.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Rewrite the failing backend/API tests around contract endpoints**

Replace clarify expectations with contract expectations such as:

```python
def test_start_contract_operation_returns_direction_ready_snapshot(tmp_path) -> None: ...
def test_submit_contract_returns_directions_goal_and_backlog(tmp_path) -> None: ...
def test_confirm_primary_direction_persists_companion_relationship_contract(tmp_path) -> None: ...
def test_confirm_primary_direction_projects_contract_into_execution_core_identity_payload(tmp_path) -> None: ...
```

Route tests should hit:

```python
POST /buddy/onboarding/contract
POST /buddy/onboarding/contract/start
POST /buddy/onboarding/direction-transition-preview
POST /buddy/onboarding/confirm-direction
```

and must stop asserting:

```python
payload["question_count"]
payload["next_question"]
```

- [ ] **Step 2: Run the focused backend/API suites and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q
```

Expected: FAIL because service/router still expose `/clarify*` and clarify-era payload fields.

- [ ] **Step 3: Refactor `BuddyOnboardingService`**

Introduce explicit service entrypoints such as:

```python
start_contract_compile(...)
submit_contract(...)
```

Behavior rules:
- starting/submitting contract stores the draft contract on `BuddyOnboardingSessionRecord`
- compiler output fills `candidate_directions`, `recommended_direction`, `draft_final_goal`, `draft_why_it_matters`, `draft_backlog_items`
- direction confirmation persists:
  - `GrowthTarget.primary_direction`
  - `GrowthTarget.final_goal`
  - `GrowthTarget.why_it_matters`
  - `CompanionRelationship` collaboration fields
- confirmation also updates `IndustryInstance.execution_core_identity_payload` with:
  - `operator_service_intent`
  - `collaboration_role`
  - `autonomy_level`
  - `report_style`
  - `confirm_boundaries`
  - derived `operating_mode`
  - derived `delegation_policy`
  - derived `direct_execution_policy`

Do not:
- put contract fields into `GrowthTarget`
- add compatibility readers for old clarify session truth
- leave router/service names saying `clarify`

- [ ] **Step 4: Refactor `buddy_routes.py`**

Delete:

```python
POST /buddy/onboarding/clarify
POST /buddy/onboarding/clarify/start
```

Add:

```python
POST /buddy/onboarding/contract
POST /buddy/onboarding/contract/start
```

Router contract rules:
- request body only carries contract fields plus `session_id`
- long-running async operation kind becomes `contract`, not `clarify`
- preview/confirm routes stay, but their response payloads must come from contract-compiled draft truth

- [ ] **Step 5: Re-run the focused backend/API suites and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q
```

Expected: PASS

- [ ] **Step 6: Commit the backend cutover**

```bash
git add src/copaw/kernel/buddy_onboarding_reasoner.py src/copaw/kernel/buddy_onboarding_service.py src/copaw/app/routers/buddy_routes.py tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py
git commit -m "feat: switch buddy onboarding backend from clarify to contract compile"
```

---

### Task 4: Make Runtime/Projection Surfaces Actually Read The Confirmed Contract

**Files:**
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/kernel/buddy_persona_prompt.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/buddy_runtime_focus.py`
- Modify: `tests/kernel/test_buddy_projection_service.py`
- Modify: `tests/kernel/test_main_brain_runtime_context_buddy_prompt.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing projection/prompt tests**

Add coverage like:

```python
def test_buddy_surface_exposes_contract_draft_during_onboarding(tmp_path) -> None: ...
def test_buddy_surface_reads_confirmed_relationship_contract_after_confirmation(tmp_path) -> None: ...
def test_buddy_persona_prompt_includes_service_intent_and_report_style(tmp_path) -> None: ...
def test_execution_prompt_reads_confirm_boundaries_and_operating_mode(tmp_path) -> None: ...
```

- [ ] **Step 2: Run the focused projection/runtime suites and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_projection_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_main_brain_chat_service.py -q
```

Expected: FAIL because projection and prompt code still read question-based onboarding truth or ignore contract fields entirely.

- [ ] **Step 3: Implement runtime/projection read-through**

Projection rules:
- onboarding stage reads draft contract from `BuddyOnboardingSessionRecord`
- confirmed stage reads formal contract from `CompanionRelationship`
- no new top-level `contract` object in `/buddy/surface`; keep the contract nested in existing `onboarding` / `relationship` surfaces

Prompt rules:
- `buddy_persona_prompt.py` reads relationship collaboration fields directly
- `query_execution_prompt.py` reads only the execution-core identity payload projection
- `buddy_runtime_focus.py` should not reconstruct contract truth from stale onboarding/question data

- [ ] **Step 4: Re-run the focused projection/runtime suites and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/kernel/test_buddy_projection_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_main_brain_chat_service.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the runtime/projection cutover**

```bash
git add src/copaw/kernel/buddy_projection_service.py src/copaw/kernel/buddy_persona_prompt.py src/copaw/kernel/query_execution_prompt.py src/copaw/kernel/buddy_runtime_focus.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: wire buddy runtime surfaces to collaboration contract"
```

---

### Task 5: Replace Frontend Clarify Flow With Fixed Collaboration Contract Form

**Files:**
- Modify: `console/src/api/modules/buddy.ts`
- Modify: `console/src/api/modules/buddy.test.ts`
- Modify: `console/src/runtime/buddyFlow.ts`
- Modify: `console/src/runtime/buddyFlow.test.ts`
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`

- [ ] **Step 1: Rewrite the failing frontend tests**

Lock the new UX contract:

```tsx
it("renders a fixed collaboration contract form instead of question-by-question clarify copy", async () => ...)
it("submits onboarding step 2 to /buddy/onboarding/contract and opens direction confirmation", async () => ...)
it("shows contract summary in step 3 instead of question count and next question", async () => ...)
```

API tests should stop asserting `BuddyClarificationResponse` and instead cover types/functions like:

```ts
submitBuddyOnboardingContract(...)
startBuddyOnboardingContract(...)
```

- [ ] **Step 2: Run the focused frontend suites and verify they fail**

Run:

```powershell
npm --prefix console run test -- src/api/modules/buddy.test.ts src/runtime/buddyFlow.test.ts src/pages/BuddyOnboarding/index.test.tsx
```

Expected: FAIL because frontend types and page copy still use clarify/question semantics.

- [ ] **Step 3: Refactor frontend types and page flow**

API/type rules:
- remove `BuddyClarificationResponse`
- rename async operation payloads from `clarify` to `contract`
- replace question fields with contract fields

Page rules:
- step labels become:
  1. `身份建档`
  2. `合作方式`
  3. `确认主方向`
- remove all “第 N / 9 问”“继续追问”“深挖方向” copy
- step 2 uses fixed fields:
  - `service_intent`
  - `collaboration_role`
  - `autonomy_level`
  - `confirm_boundaries`
  - `report_style`
  - `collaboration_notes`
- step 3 shows:
  - recommended direction
  - final goal
  - why it matters
  - first backlog items
  - collaboration contract summary

Flow rules:
- do not add a hybrid “some fixed fields + one more AI question” mode
- do not keep invisible fallback mapping from `question_count`/`next_question`

- [ ] **Step 4: Re-run the focused frontend suites and verify they pass**

Run:

```powershell
npm --prefix console run test -- src/api/modules/buddy.test.ts src/runtime/buddyFlow.test.ts src/pages/BuddyOnboarding/index.test.tsx
```

Expected: PASS

- [ ] **Step 5: Build the console**

Run:

```powershell
npm --prefix console run build
```

Expected: successful TypeScript + Vite build

- [ ] **Step 6: Commit the frontend cutover**

```bash
git add console/src/api/modules/buddy.ts console/src/api/modules/buddy.test.ts console/src/runtime/buddyFlow.ts console/src/runtime/buddyFlow.test.ts console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx
git commit -m "feat: replace buddy onboarding frontend clarify flow"
```

---

### Task 6: Sync Architecture Docs And Run End-To-End Verification

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Update the architecture/status docs**

Document:
- `CompanionRelationship` is now the formal collaboration-contract truth
- `BuddyOnboardingSessionRecord` carries only draft contract + direction compile output
- `/buddy/onboarding/contract*` replaced `/buddy/onboarding/clarify*`
- runtime/persona now read confirmed contract continuously

- [ ] **Step 2: Run the full focused backend verification**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/state/test_buddy_models.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/kernel/test_main_brain_chat_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q
```

Expected: PASS

- [ ] **Step 3: Run the full focused frontend verification**

Run:

```powershell
npm --prefix console run test -- src/api/modules/buddy.test.ts src/runtime/buddyFlow.test.ts src/pages/BuddyOnboarding/index.test.tsx
npm --prefix console run build
```

Expected: PASS

- [ ] **Step 4: Do one manual smoke through the real flow**

Verify in the running app:
- create profile
- complete step 2 with contract form
- confirm direction on step 3
- open Buddy chat/runtime carrier
- confirm Buddy surface and runtime copy reflect the chosen collaboration mode

Manual acceptance checklist:
- no question-counter wording remains
- no `clarify` request is sent by the page
- confirmed contract is visible after refresh
- runtime behavior reads contract without requiring onboarding page state

- [ ] **Step 5: Commit the docs and verification finish**

```bash
git add TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md
git commit -m "docs: sync buddy collaboration contract cutover"
```

---

## Final Acceptance Criteria

- Step 2 of Buddy onboarding is a fixed collaboration-contract form, not a question loop.
- No backend route, frontend API function, runtime state, or UI copy still depends on `/clarify*`, `question_count`, `next_question`, or `transcript`.
- `CompanionRelationship` stores the long-term collaboration contract truth.
- `GrowthTarget` remains focused on direction/goal truth only.
- `BuddyOnboardingReasoner` compiles from `HumanProfile + collaboration_contract`.
- `IndustryInstance.execution_core_identity_payload` carries the runtime projection of the confirmed contract.
- Buddy persona prompt and execution runtime prompt both read the confirmed contract continuously.
- `/buddy/surface` shows draft contract during onboarding and formal relationship contract after confirmation.
- Focused backend tests pass.
- Focused frontend tests pass.
- `npm --prefix console run build` passes.
- Manual smoke confirms the system follows the contract after onboarding instead of only showing it once.
