# Buddy Domain Capability Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Buddy's relationship-driven stage logic with an active-domain capability truth model, add explicit same-domain vs cross-domain confirmation, and align Buddy onboarding/chat/runtime surfaces with that capability stage.

**Architecture:** Keep `HumanProfile` and `CompanionRelationship` as Buddy's global identity and relationship truth. Introduce a new persisted `BuddyDomainCapabilityRecord` per domain, make `BuddyOnboardingService` preview and confirm domain inheritance explicitly, and project the active domain capability into `BuddySurfacePayload`/Runtime Center while leaving intimacy, affinity, mood, and presence in the relationship/presentation layer.

**Tech Stack:** Python, SQLite, Pydantic, FastAPI, React, TypeScript, Ant Design, pytest, Vitest

---

## File Structure

- `src/copaw/kernel/buddy_domain_capability.py`
  Responsibility: pure helpers for domain-key normalization, capability-score calculation, stage-band mapping, progress-to-next-stage, and transition suggestion.
- `tests/kernel/test_buddy_domain_capability.py`
  Responsibility: pure rule coverage for score bands and same-domain / archived-domain / new-domain suggestion behavior.
- `src/copaw/state/models_buddy.py`
  Responsibility: formal Buddy state and projections, including `BuddyDomainCapabilityRecord` plus any capability-facing projection fields.
- `src/copaw/state/models.py`
  Responsibility: re-export Buddy state/projection models from the canonical state model barrel.
- `src/copaw/state/__init__.py`
  Responsibility: export the new Buddy domain capability model through the state package public surface.
- `src/copaw/state/repositories_buddy.py`
  Responsibility: SQLite persistence and lookup helpers for active/archived Buddy domain capability records.
- `src/copaw/state/store.py`
  Responsibility: create and migrate the `buddy_domain_capabilities` table and related indexes.
- `tests/state/test_buddy_models.py`
  Responsibility: model round-trip coverage and base table-presence assertions.
- `tests/state/test_buddy_domain_capability_repository.py`
  Responsibility: repository round-trip coverage for active/archive/restore behavior.
- `tests/state/test_state_store_migration.py`
  Responsibility: legacy SQLite upgrade coverage for the new table/schema version.
- `src/copaw/kernel/buddy_onboarding_service.py`
  Responsibility: target-change preview + explicit inheritance confirmation + activation/archive of domain capability records.
- `tests/kernel/test_buddy_onboarding_service.py`
  Responsibility: onboarding flow coverage for same-domain extension, archived-domain restore, and fresh-domain reset.
- `src/copaw/app/routers/buddy_routes.py`
  Responsibility: HTTP contracts for direction-transition preview and explicit confirmation payloads.
- `tests/app/test_buddy_routes.py`
  Responsibility: route-level contract coverage for preview + confirm APIs.
- `src/copaw/kernel/buddy_projection_service.py`
  Responsibility: derive Buddy surface and cockpit summary from the active domain capability record, not relationship experience.
- `tests/kernel/test_buddy_projection_service.py`
  Responsibility: projection coverage that locks stage/progress to active domain capability truth.
- `tests/app/test_buddy_cutover.py`
  Responsibility: end-to-end Buddy surface and Runtime Center alignment after the projection truth changes.
- `console/src/api/modules/buddy.ts`
  Responsibility: frontend API contracts for transition preview, explicit confirmation, and the expanded Buddy surface payload.
- `console/src/api/modules/buddy.test.ts`
  Responsibility: client contract coverage for the new Buddy preview/confirm endpoints.
- `console/src/api/modules/runtimeCenter.ts`
  Responsibility: frontend typing for Runtime Center's Buddy summary fields if capability score/domain label are added.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Responsibility: selected-direction preview, human confirmation of capability inheritance, and final confirm submission.
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  Responsibility: UI coverage for keep-active, restore-archived, and start-new flows.
- `console/src/pages/Chat/buddyEvolution.ts`
  Responsibility: frontend stage fallback driven by capability score/stage truth instead of companion experience.
- `console/src/pages/Chat/buddyEvolution.test.ts`
  Responsibility: stage-band coverage for capability score thresholds.
- `console/src/pages/Chat/buddyPresentation.ts`
  Responsibility: shared human-facing labels for Buddy stage/presence/mood and active-domain display snapshots.
- `console/src/pages/Chat/buddyPresentation.test.ts`
  Responsibility: label mapping and snapshot fallback coverage.
- `console/src/pages/Chat/BuddyCompanion.tsx`
  Responsibility: compact chat companion card showing active-domain stage/capability context.
- `console/src/pages/Chat/BuddyCompanion.test.tsx`
  Responsibility: compact Buddy card coverage for stage label and capability metadata.
- `console/src/pages/Chat/BuddyPanel.tsx`
  Responsibility: detail drawer copy and metrics for `当前阶段`, `能力分`, and capability breakdown.
- `console/src/pages/Chat/BuddyPanel.test.tsx`
  Responsibility: Buddy detail panel coverage for capability-stage semantics.
- `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
  Responsibility: Runtime Center Buddy summary copy aligned to active-domain capability rather than relationship-only growth.
- `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
  Responsibility: runtime Buddy summary regression coverage.
- `DATA_MODEL_DRAFT.md`
  Responsibility: formalize `BuddyDomainCapabilityRecord` and its relationship to `HumanProfile`, `GrowthTarget`, and `CompanionRelationship`.
- `TASK_STATUS.md`
  Responsibility: record the migration and current verification state.
- `FRONTEND_UPGRADE_PLAN.md`
  Responsibility: update Buddy UI semantics from relationship-stage wording to capability-stage wording.
- `RUNTIME_CENTER_UI_SPEC.md`
  Responsibility: update the Buddy compact summary contract to show active-domain capability progress.
- `AGENT_VISIBLE_MODEL.md`
  Responsibility: lock Buddy's visible stage semantics as main-brain domain capability, not task phase.

---

### Task 1: Lock Pure Domain Capability Rules

**Files:**
- Create: `src/copaw/kernel/buddy_domain_capability.py`
- Create: `tests/kernel/test_buddy_domain_capability.py`

- [ ] **Step 1: Write the failing pure-rule tests**

```python
def test_capability_stage_from_score_uses_five_domain_bands() -> None:
    assert capability_stage_from_score(0) == "seed"
    assert capability_stage_from_score(20) == "bonded"
    assert capability_stage_from_score(40) == "capable"
    assert capability_stage_from_score(60) == "seasoned"
    assert capability_stage_from_score(80) == "signature"


def test_preview_domain_transition_prefers_same_domain_then_archived_match() -> None:
    preview = preview_domain_transition(
        selected_direction="股票赚 100 万",
        active_record=active_stock_record,
        archived_records=[archived_writing_record],
    )
    assert preview.suggestion_kind == "same-domain"
    assert preview.recommended_action == "keep-active"
```

- [ ] **Step 2: Run the targeted rule suite to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py -q`
Expected: FAIL because the helper module does not exist yet.

- [ ] **Step 3: Implement the pure helper module**

Create helpers with one responsibility each:

```python
def capability_stage_from_score(score: int) -> BuddyEvolutionStage: ...
def progress_to_next_capability_stage(score: int) -> int: ...
def derive_buddy_domain_key(direction: str) -> str: ...
def preview_domain_transition(...) -> BuddyDomainTransitionPreview: ...
```

Rules to lock:
- stage bands: `0-19`, `20-39`, `40-59`, `60-79`, `80-100`
- returned stages remain internal enum values `seed/bonded/capable/seasoned/signature`
- domain preview uses normalized domain keys and archived-match detection only as a suggestion layer
- helper never mutates persistence state

- [ ] **Step 4: Run the targeted rule suite to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py -q`
Expected: PASS

---

### Task 2: Persist Buddy Domain Capability Records

**Files:**
- Modify: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories_buddy.py`
- Modify: `src/copaw/state/store.py`
- Modify: `tests/state/test_buddy_models.py`
- Create: `tests/state/test_buddy_domain_capability_repository.py`
- Modify: `tests/state/test_state_store_migration.py`

- [ ] **Step 1: Write the failing state-model and repository tests**

```python
def test_buddy_domain_capability_record_round_trips_required_fields() -> None:
    record = BuddyDomainCapabilityRecord(
        domain_id="domain-stock",
        profile_id="hp-1",
        domain_key="stocks",
        domain_label="股票",
        status="active",
        capability_score=62,
        evolution_stage="seasoned",
    )
    assert record.domain_label == "股票"


def test_repository_restores_archived_domain_without_deleting_old_progress(tmp_path) -> None:
    ...
    assert restored.status == "active"
    assert restored.capability_score == 72
```

- [ ] **Step 2: Run the focused state suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: FAIL because the model, repository, and SQLite table do not exist yet.

- [ ] **Step 3: Add the new model, exports, schema, and repository methods**

Persist a formal record similar to:

```python
class BuddyDomainCapabilityRecord(UpdatedRecord):
    domain_id: str
    profile_id: str
    domain_key: str
    domain_label: str
    status: Literal["active", "archived"] = "active"
    strategy_score: int = Field(default=0, ge=0, le=25)
    execution_score: int = Field(default=0, ge=0, le=35)
    evidence_score: int = Field(default=0, ge=0, le=20)
    stability_score: int = Field(default=0, ge=0, le=20)
    capability_score: int = Field(default=0, ge=0, le=100)
    evolution_stage: BuddyEvolutionStage = "seed"
```

Repository methods to add:
- `get_active_domain_capability(profile_id)`
- `list_domain_capabilities(profile_id, include_archived=True)`
- `get_domain_capability(domain_id)`
- `find_domain_capabilities_by_key(profile_id, domain_key)`
- `upsert_domain_capability(record)`
- `archive_active_domain_capabilities(profile_id, except_domain_id=None)`

Schema work:
- add `buddy_domain_capabilities` table + indexes
- bump `STATE_SCHEMA_VERSION`
- make `initialize()` idempotent for existing Buddy DBs

- [ ] **Step 4: Run the focused state suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: PASS

---

### Task 3: Add Explicit Domain-Transition Preview And Confirmation

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Modify: `tests/app/test_buddy_routes.py`

- [ ] **Step 1: Write the failing onboarding service tests**

Lock three behaviors:

```python
def test_confirm_primary_direction_keeps_stage_for_same_domain_extension(tmp_path) -> None: ...
def test_confirm_primary_direction_archives_old_domain_and_starts_new_one(tmp_path) -> None: ...
def test_confirm_primary_direction_restores_matching_archived_domain(tmp_path) -> None: ...
```

- [ ] **Step 2: Write the failing route-contract test**

Add route coverage for:

```python
preview = client.post(
    "/buddy/onboarding/direction-transition-preview",
    json={"session_id": session_id, "selected_direction": "股票赚 100 万"},
)
assert preview.json()["recommended_action"] == "keep-active"

confirm = client.post(
    "/buddy/onboarding/confirm-direction",
    json={
        "session_id": session_id,
        "selected_direction": "股票赚 100 万",
        "capability_action": "keep-active",
        "target_domain_id": None,
    },
)
```

- [ ] **Step 3: Run the targeted backend flow suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py -q`
Expected: FAIL because preview/explicit confirmation is not wired yet.

- [ ] **Step 4: Implement preview + explicit confirm behavior**

Add a preview result that includes:
- `suggestion_kind`: `same-domain | switch-to-archived-domain | start-new-domain`
- `recommended_action`: `keep-active | restore-archived | start-new`
- `current_domain`
- `archived_matches`
- `reason_summary`

Then change confirmation input to require:

```python
class BuddyConfirmDirectionRequest(BaseModel):
    session_id: str
    selected_direction: str
    capability_action: Literal["keep-active", "restore-archived", "start-new"]
    target_domain_id: str | None = None
```

Implementation rules:
- same-domain: update `GrowthTarget`, keep active domain record
- restore-archived: archive current active record, reactivate chosen archived record
- start-new: archive current active record, create a new `BuddyDomainCapabilityRecord` seeded at `score=0`, `stage=seed`
- never delete archived domain records in this round

- [ ] **Step 5: Run the targeted backend flow suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py -q`
Expected: PASS

---

### Task 4: Project Buddy Surface From Active Domain Capability Truth

**Files:**
- Modify: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `tests/kernel/test_buddy_projection_service.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write the failing projection tests**

Lock the new projection semantics:

```python
def test_buddy_projection_reads_stage_from_active_domain_capability(tmp_path) -> None:
    payload = projection.build_chat_surface(profile_id=profile_id)
    assert payload.growth.evolution_stage == "seasoned"
    assert payload.growth.capability_score == 63
    assert payload.presentation.current_form == "seasoned"


def test_relationship_experience_no_longer_upgrades_stage_without_domain_progress(tmp_path) -> None:
    ...
    assert payload.growth.evolution_stage == "seed"
```

- [ ] **Step 2: Run the focused projection suite to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_cutover.py -q`
Expected: FAIL because projection still derives stage from `companion_experience`.

- [ ] **Step 3: Rebuild the projection around active domain capability**

Update `BuddyGrowthProjection` to expose active-domain capability fields such as:
- `domain_id`
- `domain_label`
- `capability_score`
- `strategy_score`
- `execution_score`
- `evidence_score`
- `stability_score`
- `evolution_stage`
- `progress_to_next_stage`

Keep relationship-only fields separate from stage drivers:
- `intimacy`
- `affinity`
- `pleasant_interaction_score`
- `communication_count`

Implementation rules:
- `current_form` mirrors the active-domain stage for now
- `build_cockpit_summary()` includes `domain_label` and `capability_score`
- if no active domain capability exists yet, surface falls back to a zeroed `seed` projection instead of relationship-derived promotion

- [ ] **Step 4: Run the focused projection suite to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

---

### Task 5: Update Frontend Contracts And Onboarding Confirmation UI

**Files:**
- Modify: `console/src/api/modules/buddy.ts`
- Modify: `console/src/api/modules/buddy.test.ts`
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`

- [ ] **Step 1: Write the failing frontend contract/UI tests**

Protect the new flow:

```tsx
await api.previewBuddyDirectionTransition({
  session_id: "session-1",
  selected_direction: "股票赚 100 万",
});

expect(screen.getByText(/系统建议：继续继承当前领域能力/)).toBeInTheDocument();
expect(screen.getByLabelText(/继续当前领域能力/)).toBeChecked();
```

- [ ] **Step 2: Run the targeted frontend onboarding suite to verify it fails**

Run: `npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx`
Expected: FAIL because the preview endpoint and explicit action fields do not exist on the client/UI.

- [ ] **Step 3: Implement the new Buddy onboarding flow**

Add client methods and types:

```ts
previewBuddyDirectionTransition(payload: {
  session_id: string;
  selected_direction: string;
})

confirmBuddyDirection(payload: {
  session_id: string;
  selected_direction: string;
  capability_action: "keep-active" | "restore-archived" | "start-new";
  target_domain_id?: string | null;
})
```

UI behavior to add:
- after choosing a direction, call preview before final confirmation
- show the system suggestion plus the human's final choice controls
- render archived matches when `recommended_action === "restore-archived"`
- only send confirm after the human explicitly chooses the action

- [ ] **Step 4: Run the targeted frontend onboarding suite to verify it passes**

Run: `npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx`
Expected: PASS

---

### Task 6: Align Chat And Runtime Buddy Presentation With Capability Stages

**Files:**
- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/pages/Chat/buddyEvolution.ts`
- Modify: `console/src/pages/Chat/buddyEvolution.test.ts`
- Modify: `console/src/pages/Chat/buddyPresentation.ts`
- Modify: `console/src/pages/Chat/buddyPresentation.test.ts`
- Modify: `console/src/pages/Chat/BuddyCompanion.tsx`
- Modify: `console/src/pages/Chat/BuddyCompanion.test.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.test.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Write the failing capability-presentation tests**

Examples:

```ts
it("maps internal stages to 幼年期 / 成长期 / 成熟期 / 完全体 / 究极体", () => {
  expect(presentBuddyStageLabel("seed")).toBe("幼年期");
  expect(presentBuddyStageLabel("signature")).toBe("究极体");
});

it("shows 当前阶段 and 能力分 in the Buddy panel", () => {
  expect(screen.getByText(/当前阶段：成熟期/)).toBeInTheDocument();
  expect(screen.getByText(/能力分：48/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the targeted Buddy UI suites to verify they fail**

Run: `npm --prefix console run test -- src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: FAIL because the UI still uses old labels and relationship-driven fallback logic.

- [ ] **Step 3: Implement the capability-stage presentation**

Rules to apply:
- stage labels:
  - `seed -> 幼年期`
  - `bonded -> 成长期`
  - `capable -> 成熟期`
  - `seasoned -> 完全体`
  - `signature -> 究极体`
- `buddyEvolution.ts` falls back from `capability_score` or `evolution_stage`, not `companion_experience`
- `BuddyPanel` copy becomes `当前阶段`
- `BuddyPanel` growth block shows capability score/breakdown first; intimacy/affinity stay in the relationship block
- `BuddyCompanion` and Runtime Center compact summary mention active-domain capability progress instead of treating `等级/亲密度/契合度` as the primary stage line

- [ ] **Step 4: Run the targeted Buddy UI suites to verify they pass**

Run: `npm --prefix console run test -- src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

---

### Task 7: Sync Docs And Run Final Verification

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `TASK_STATUS.md`
- Modify: `FRONTEND_UPGRADE_PLAN.md`
- Modify: `RUNTIME_CENTER_UI_SPEC.md`
- Modify: `AGENT_VISIBLE_MODEL.md`
- Verify: `docs/superpowers/specs/2026-04-07-buddy-domain-capability-stage-design.md`

- [ ] **Step 1: Update the architecture and UI docs**

Document:
- `BuddyDomainCapabilityRecord` as the formal per-domain capability object
- Buddy stage as active-domain capability maturity, not relationship warmth
- same-domain vs cross-domain switch policy
- Runtime Center / Chat Buddy summary semantics

- [ ] **Step 2: Run the focused backend verification set**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 3: Run the focused frontend verification set**

Run: `npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

- [ ] **Step 4: Run the console build**

Run: `cmd /c npm --prefix console run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-07-buddy-domain-capability-stage-design.md docs/superpowers/plans/2026-04-07-buddy-domain-capability-stage-implementation-plan.md DATA_MODEL_DRAFT.md TASK_STATUS.md FRONTEND_UPGRADE_PLAN.md RUNTIME_CENTER_UI_SPEC.md AGENT_VISIBLE_MODEL.md src/copaw/kernel/buddy_domain_capability.py src/copaw/kernel/buddy_onboarding_service.py src/copaw/kernel/buddy_projection_service.py src/copaw/state/models_buddy.py src/copaw/state/models.py src/copaw/state/__init__.py src/copaw/state/repositories_buddy.py src/copaw/state/store.py src/copaw/app/routers/buddy_routes.py tests/kernel/test_buddy_domain_capability.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py console/src/api/modules/buddy.ts console/src/api/modules/buddy.test.ts console/src/api/modules/runtimeCenter.ts console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx console/src/pages/Chat/buddyEvolution.ts console/src/pages/Chat/buddyEvolution.test.ts console/src/pages/Chat/buddyPresentation.ts console/src/pages/Chat/buddyPresentation.test.ts console/src/pages/Chat/BuddyCompanion.tsx console/src/pages/Chat/BuddyCompanion.test.tsx console/src/pages/Chat/BuddyPanel.tsx console/src/pages/Chat/BuddyPanel.test.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: migrate buddy stage to domain capability truth"
```
