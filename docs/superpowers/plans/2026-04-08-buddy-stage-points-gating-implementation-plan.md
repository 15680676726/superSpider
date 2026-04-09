# Buddy Stage Points Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Buddy's current capability-score-led stage progression with a simpler points-and-gates model where real closed loops give points, promotion requires explicit gates, and demotion can only happen one level at a time.

**Architecture:** Keep `BuddyDomainCapabilityRecord` as the single truth object. Add points- and gate-related fields onto that record, derive scoring only from formally settled assignment/report/evidence/cycle truth, and let stage promotion read `capability_points + gate conditions` instead of the old composite `capability_score`. Keep `capability_score` temporarily as compatibility/read-model metadata so existing UI surfaces do not hard-break during the cutover.

**Tech Stack:** Python, FastAPI, SQLite, Pydantic, React, TypeScript, pytest, Vitest

---

## File Structure

- `src/copaw/state/models_buddy.py`
  Responsibility: extend `BuddyDomainCapabilityRecord` and Buddy growth projection models with points/gates fields while keeping `capability_score` as compatibility metadata.
- `src/copaw/state/repositories_buddy.py`
  Responsibility: persist/read the new Buddy points/gates fields.
- `src/copaw/state/store.py`
  Responsibility: SQLite schema migration for new Buddy domain capability columns.
- `tests/state/test_buddy_models.py`
  Responsibility: model validation/serialization for new points/gates fields.
- `tests/state/test_buddy_domain_capability_repository.py`
  Responsibility: repository round-trip coverage for the new fields.
- `tests/state/test_state_store_migration.py`
  Responsibility: migration coverage for legacy Buddy databases.
- `src/copaw/kernel/buddy_domain_capability.py`
  Responsibility: replace the current stage-bands helper set with the new points thresholds, promotion-gate checks, and one-level demotion helper logic.
- `src/copaw/kernel/buddy_domain_capability_growth.py`
  Responsibility: stop using structure-heavy score progression as the canonical stage rule; instead calculate valid closures, points, outcome/gate metrics, completion rate, error rate, and stage transitions from formal settled truth.
- `src/copaw/kernel/buddy_projection_service.py`
  Responsibility: project the new points-based stage truth into Buddy surfaces while keeping compatibility fields populated.
- `tests/kernel/test_buddy_projection_service.py`
  Responsibility: projection coverage for points-led stage truth and compatibility fallback behavior.
- `tests/kernel/test_buddy_projection_capability.py`
  Responsibility: gate and stage progression coverage after closure/cycle/report truth changes.
- `tests/kernel/test_buddy_onboarding_service.py`
  Responsibility: ensure onboarding bootstrap no longer jumps stage purely from seeded structure.
- `tests/app/test_buddy_cutover.py`
  Responsibility: end-to-end Buddy API/runtime summary behavior under the new stage thresholds.
- `console/src/api/modules/buddy.ts`
  Responsibility: type the new Buddy points/gates projection fields.
- `console/src/pages/Chat/buddyEvolution.ts`
  Responsibility: make frontend stage resolution prioritize backend stage truth and points-based fallback bands instead of the old capability-score-first contract.
- `console/src/pages/Chat/buddyPresentation.ts`
  Responsibility: expose points-oriented display copy where needed.
- `console/src/pages/Chat/BuddyPanel.tsx`
  Responsibility: show Buddy points and gate-facing growth information instead of presenting capability score as the main growth rule.
- `console/src/pages/Chat/BuddyCompanion.tsx`
  Responsibility: keep summary display aligned with the new stage contract.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Responsibility: change preview/restore labels from “能力分” to points-oriented growth language where needed.
- `tests/pages` / `console` Buddy tests
  Responsibility: frontend regression coverage for points-led stage presentation.
- `DATA_MODEL_DRAFT.md`
  Responsibility: document points/gates as the canonical Buddy stage rule.
- `TASK_STATUS.md`
  Responsibility: record the cutover and fresh verification.

---

### Task 1: Persist Buddy Points And Gate Metrics

**Files:**
- Modify: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/state/repositories_buddy.py`
- Modify: `src/copaw/state/store.py`
- Modify: `tests/state/test_buddy_models.py`
- Modify: `tests/state/test_buddy_domain_capability_repository.py`
- Modify: `tests/state/test_state_store_migration.py`

- [ ] **Step 1: Write the failing state-model tests**

Add coverage like:

```python
def test_buddy_domain_capability_record_accepts_points_and_gate_metrics() -> None:
    record = BuddyDomainCapabilityRecord(
        profile_id="profile-1",
        domain_key="writing",
        domain_label="写作",
        capability_points=40,
        settled_closure_count=20,
        independent_outcome_count=2,
        recent_completion_rate=0.95,
        recent_execution_error_rate=0.02,
        distinct_settled_cycle_count=3,
    )
    assert record.capability_points == 40
```

- [ ] **Step 2: Write the failing repository/migration tests**

Add focused checks for the new SQLite fields:

```python
def test_domain_capability_repository_round_trips_points_fields(tmp_path) -> None: ...
def test_state_store_migrates_buddy_domain_capabilities_with_points_columns(tmp_path) -> None: ...
```

- [ ] **Step 3: Run the focused state tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: FAIL because the points/gate fields do not exist yet.

- [ ] **Step 4: Add the minimal state schema**

Extend `BuddyDomainCapabilityRecord` and Buddy growth projection payloads with:

```python
capability_points: int = Field(default=0, ge=0)
settled_closure_count: int = Field(default=0, ge=0)
independent_outcome_count: int = Field(default=0, ge=0)
recent_completion_rate: float = Field(default=0, ge=0, le=1)
recent_execution_error_rate: float = Field(default=0, ge=0, le=1)
distinct_settled_cycle_count: int = Field(default=0, ge=0)
demotion_cooldown_until: str | None = None
```

Rules:
- keep `capability_score` and its sub-scores for temporary compatibility
- do not create a second Buddy growth object
- persist all new fields in SQLite

- [ ] **Step 5: Run the focused state tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/models_buddy.py src/copaw/state/repositories_buddy.py src/copaw/state/store.py tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py
git commit -m "feat: persist buddy stage points fields"
```

---

### Task 2: Replace Stage Math With Points And Promotion Gates

**Files:**
- Modify: `src/copaw/kernel/buddy_domain_capability.py`
- Modify: `tests/kernel/test_buddy_projection_capability.py`

- [ ] **Step 1: Write the failing pure-logic tests**

Add tests for:

```python
def test_points_thresholds_map_to_expected_stages() -> None: ...
def test_mature_stage_requires_at_least_one_real_closure() -> None: ...
def test_seasoned_stage_requires_three_distinct_settled_cycles() -> None: ...
def test_signature_stage_requires_points_and_reliability_gates() -> None: ...
def test_demotion_can_only_drop_one_stage() -> None: ...
```

- [ ] **Step 2: Run the focused logic tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py -q`
Expected: FAIL because logic still uses the old score-band model.

- [ ] **Step 3: Rewrite the helper contract**

Replace the current stage helpers with:

```python
def stage_from_points(points: int) -> BuddyEvolutionStage: ...
def can_promote_to_stage(...): ...
def resolve_stage_transition(...): ...
def progress_to_next_stage(points: int) -> int: ...
```

Rules:
- thresholds use points: `20 / 40 / 100 / 200`
- `bonded` only needs threshold
- `capable` needs threshold + `>=1` real closure
- `seasoned` needs threshold + `>=3` distinct settled cycles
- `signature` needs threshold + `>=10` independent outcomes + completion/error bars
- demotion may only drop one stage at a time

- [ ] **Step 4: Run the focused logic tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/buddy_domain_capability.py tests/kernel/test_buddy_projection_capability.py
git commit -m "feat: add buddy stage points gates"
```

---

### Task 3: Rebuild Buddy Growth Refresh Around Real Closures

**Files:**
- Modify: `src/copaw/kernel/buddy_domain_capability_growth.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Modify: `tests/kernel/test_buddy_projection_capability.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write the failing regression tests**

Add coverage for the exact pacing problem:

```python
def test_onboarding_bootstrap_structure_does_not_promote_buddy_out_of_seed(tmp_path) -> None: ...
def test_one_valid_closure_adds_two_points(tmp_path) -> None: ...
def test_invalid_closure_without_report_or_evidence_does_not_add_points(tmp_path) -> None: ...
def test_signature_requires_reliability_metrics_not_just_points(tmp_path) -> None: ...
def test_failed_window_can_demote_only_one_stage(tmp_path) -> None: ...
```

- [ ] **Step 2: Run the focused backend tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: FAIL because growth still promotes mainly from structure-heavy score math.

- [ ] **Step 3: Rework growth collection**

Implement points-led growth refresh:

```python
valid_closures = settled assignments with completed result + report + evidence
capability_points = valid_closure_count * 2
settled_closure_count = valid_closure_count
distinct_settled_cycle_count = ...
independent_outcome_count = ...
recent_completion_rate = ...
recent_execution_error_rate = ...
evolution_stage = resolve_stage_transition(...)
```

Rules:
- do not count seeded backlog/lanes/cycle structure as points
- keep compatibility `capability_score` populated for now, but treat it as secondary metadata
- use a bounded recent window (`30` settled assignments) for completion/error metrics
- only allow one-level demotion in a single refresh

- [ ] **Step 4: Run the focused backend tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/buddy_domain_capability_growth.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py
git commit -m "feat: score buddy stage from real closures"
```

---

### Task 4: Project Points-Led Stage Truth To Buddy Surfaces

**Files:**
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `tests/kernel/test_buddy_projection_service.py`
- Modify: `console/src/api/modules/buddy.ts`
- Modify: `console/src/pages/Chat/buddyEvolution.ts`
- Modify: `console/src/pages/Chat/buddyPresentation.ts`
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`
- Modify: `console/src/pages/Chat/BuddyCompanion.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: relevant Buddy frontend tests

- [ ] **Step 1: Write the failing projection/frontend tests**

Add checks like:

```ts
it("shows buddy points as the primary growth meter", () => {})
it("does not derive high stage from capability score alone when backend stage says seed", () => {})
it("renders stage thresholds using points-oriented language", () => {})
```

And backend projection coverage:

```python
def test_buddy_surface_projects_capability_points_and_gate_metrics(tmp_path) -> None: ...
```

- [ ] **Step 2: Run the focused projection/UI tests to verify they fail**

Run:
- `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_service.py -q`
- `npm --prefix console test -- src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/BuddyOnboarding/index.test.tsx src/runtime/buddyFlow.test.ts`

Expected: FAIL because UI still centers `capability_score`.

- [ ] **Step 3: Update projection and display contracts**

Requirements:
- projection must expose `capability_points`, closure counts, cycle counts, completion/error metrics
- backend stage field remains canonical
- frontend fallback bands, if ever needed, must use points thresholds rather than the old score bands
- Buddy panel should present points as the main progress metric
- copy should stop implying that `能力分` is the primary growth truth

- [ ] **Step 4: Run the focused projection/UI tests to verify they pass**

Run:
- `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_service.py -q`
- `npm --prefix console test -- src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/BuddyOnboarding/index.test.tsx src/runtime/buddyFlow.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/buddy_projection_service.py tests/kernel/test_buddy_projection_service.py console/src/api/modules/buddy.ts console/src/pages/Chat/buddyEvolution.ts console/src/pages/Chat/buddyPresentation.ts console/src/pages/Chat/BuddyPanel.tsx console/src/pages/Chat/BuddyCompanion.tsx console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx console/src/runtime/buddyFlow.test.ts
git commit -m "feat: project buddy points-led stage surfaces"
```

---

### Task 5: Sync Docs And Run Full Verification

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Update architecture/status docs**

Record:
- Buddy stage truth is now `capability_points + promotion gates`
- `capability_score` is compatibility metadata, not the canonical progression rule
- one real closure gives `2` points
- `signature` requires high completion rate and low execution error rate

- [ ] **Step 2: Run the full Buddy backend regression set**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 3: Run the full Buddy frontend regression set**

Run: `npm --prefix console test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/runtime/buddyFlow.test.ts`
Expected: PASS

- [ ] **Step 4: Run the console build**

Run: `npm --prefix console run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add DATA_MODEL_DRAFT.md TASK_STATUS.md
git commit -m "docs: document buddy points stage progression"
```

