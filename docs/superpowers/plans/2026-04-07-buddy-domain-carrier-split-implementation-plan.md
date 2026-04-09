# Buddy Domain Carrier Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Buddy execution carriers by domain so cross-domain `start-new` truly resets the current domain, archived domains keep their own runtime history, and restore reactivates the original carrier/thread instead of reusing the old shared `buddy:{profile_id}` runtime truth.

**Architecture:** Bind each active `BuddyDomainCapabilityRecord` to exactly one domain-owned execution carrier (`IndustryInstanceRecord` + continuity ids). Refactor Buddy onboarding so `keep-active` reuses the current binding, `restore-archived` reactivates the archived binding, and `start-new` creates a fresh carrier while freezing the old one. Capability growth, Buddy projection, and chat binding must all follow the active record's bound carrier ids instead of deriving runtime truth from `buddy:{profile_id}`.

**Tech Stack:** Python, FastAPI, SQLite, Pydantic, React, TypeScript, Ant Design, pytest, Vitest

---

## File Structure

- `src/copaw/state/models_buddy.py`
  Responsibility: extend `BuddyDomainCapabilityRecord` with formal carrier-binding fields and any minimal domain-scope metadata used by the cutover.
- `src/copaw/state/repositories_buddy.py`
  Responsibility: persist/read the new carrier-binding fields, plus any lookup helpers needed for legacy backfill and archive/restore flows.
- `src/copaw/state/store.py`
  Responsibility: migrate `buddy_domain_capabilities` with new binding columns and preserve existing Buddy databases.
- `tests/state/test_buddy_models.py`
  Responsibility: model validation and serialization coverage for the new carrier-binding fields.
- `tests/state/test_buddy_domain_capability_repository.py`
  Responsibility: repository round-trip coverage for carrier-binding persistence and archive/restore behavior.
- `tests/state/test_state_store_migration.py`
  Responsibility: SQLite migration coverage for pre-split Buddy databases.
- `src/copaw/kernel/buddy_execution_carrier.py`
  Responsibility: canonical Buddy execution-carrier identity/building helpers so carrier ids and control-thread ids are derived from the bound domain record, not profile-only ids.
- `src/copaw/kernel/buddy_onboarding_service.py`
  Responsibility: domain-switch orchestration, legacy shared-carrier backfill, active/archived carrier freeze/reactivate behavior, and switch-only page semantics.
- `src/copaw/kernel/buddy_domain_capability_growth.py`
  Responsibility: read planning/evidence signals only from the active record's bound carrier.
- `src/copaw/kernel/buddy_projection_service.py`
  Responsibility: project the active domain's carrier binding into `/buddy/surface` and Runtime Center.
- `src/copaw/app/runtime_service_graph.py`
  Responsibility: keep the Buddy service graph wired to the updated onboarding/growth/projection seams.
- `tests/kernel/test_buddy_onboarding_service.py`
  Responsibility: backend behavior for keep-active, start-new, restore-archived, and legacy-carrier migration.
- `tests/kernel/test_buddy_projection_capability.py`
  Responsibility: capability growth/projection coverage after carrier split.
- `tests/app/test_buddy_routes.py`
  Responsibility: API contract coverage for preview/confirm after carrier ids become domain-owned.
- `tests/app/test_buddy_cutover.py`
  Responsibility: end-to-end Buddy surface/runtime summary regression for new-carrier, restore, and thread continuity behavior.
- `console/src/api/modules/buddy.ts`
  Responsibility: frontend contract typing for the returned carrier payload and any switch-only copy exposed by preview/confirm.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Responsibility: treat the page flow as hard switch only and continue using the returned bound carrier when entering chat.
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  Responsibility: UI coverage for switch-only wording and restore/new-carrier continuity.
- `console/src/runtime/buddyFlow.test.ts`
  Responsibility: entry-flow regression coverage without assuming a shared `buddy:{profile_id}` carrier identity.
- `DATA_MODEL_DRAFT.md`
  Responsibility: formalize `BuddyDomainCapabilityRecord -> IndustryInstanceRecord` binding and the split between chat expansion and page switching.
- `API_TRANSITION_MAP.md`
  Responsibility: document that `confirm-direction` now changes active carrier ownership, not only active domain capability.
- `TASK_STATUS.md`
  Responsibility: record the carrier split, cutover rules, and fresh verification evidence.
- `AGENT_VISIBLE_MODEL.md`
  Responsibility: update Buddy visible-model wording from `当前形态` residue to current-stage/current-domain carrier semantics.

---

### Task 1: Persist Domain-Owned Carrier Bindings

**Files:**
- Modify: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/state/repositories_buddy.py`
- Modify: `src/copaw/state/store.py`
- Modify: `tests/state/test_buddy_models.py`
- Modify: `tests/state/test_buddy_domain_capability_repository.py`
- Modify: `tests/state/test_state_store_migration.py`

- [ ] **Step 1: Write the failing model/repository tests**

Add coverage like:

```python
def test_buddy_domain_capability_record_accepts_carrier_binding_fields() -> None:
    record = BuddyDomainCapabilityRecord(
        profile_id="profile-1",
        domain_key="writing",
        domain_label="写作",
        status="active",
        industry_instance_id="buddy:profile-1:domain-writing",
        control_thread_id="industry-chat:buddy:profile-1:domain-writing:execution-core",
    )
    assert record.industry_instance_id == "buddy:profile-1:domain-writing"


def test_domain_capability_repository_round_trips_bound_carrier_ids(tmp_path) -> None:
    ...
    assert stored.control_thread_id == original.control_thread_id
```

- [ ] **Step 2: Write the failing migration test**

Lock one legacy-db behavior:

```python
def test_state_store_migrates_buddy_domain_capabilities_with_null_carrier_binding(tmp_path) -> None:
    ...
    assert "industry_instance_id" in columns
    assert "control_thread_id" in columns
```

- [ ] **Step 3: Run the focused state suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: FAIL because the new binding fields/columns do not exist yet.

- [ ] **Step 4: Add the minimal state schema**

Extend `BuddyDomainCapabilityRecord` with:

```python
industry_instance_id: str = ""
control_thread_id: str = ""
domain_scope_summary: str = ""
domain_scope_tags: list[str] = Field(default_factory=list)
```

Rules:
- `industry_instance_id` and `control_thread_id` are the formal carrier binding for the domain
- `domain_scope_summary` / `domain_scope_tags` stay optional and must not create a second truth source
- existing records may start empty until the cutover backfill binds them

Repository/store work:
- add SQLite columns
- serialize `domain_scope_tags` as JSON
- keep migrations idempotent on existing Buddy DBs

- [ ] **Step 5: Run the focused state suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py -q`
Expected: PASS

---

### Task 2: Split Carrier Identity And Migrate Off `buddy:{profile_id}`

**Files:**
- Modify: `src/copaw/kernel/buddy_execution_carrier.py`
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Modify: `tests/app/test_buddy_routes.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write the failing backend behavior tests**

Add coverage for all three switch paths plus the legacy shim:

```python
def test_confirm_primary_direction_start_new_creates_fresh_domain_carrier(tmp_path) -> None: ...
def test_confirm_primary_direction_restore_archived_reuses_archived_carrier_binding(tmp_path) -> None: ...
def test_confirm_primary_direction_keep_active_preserves_same_carrier_binding(tmp_path) -> None: ...
def test_legacy_shared_buddy_carrier_is_backfilled_into_active_domain_binding(tmp_path) -> None: ...
```

Also update route/cutover expectations so they stop asserting:

```python
assert execution_carrier["instance_id"] == f"buddy:{profile_id}"
```

and instead assert:

```python
assert execution_carrier["instance_id"] == confirmation["domain_capability"]["industry_instance_id"]
```

- [ ] **Step 2: Run the focused backend suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
Expected: FAIL because onboarding still reuses `buddy:{profile_id}` and the cutover tests are still pinned to the old carrier id.

- [ ] **Step 3: Refactor carrier identity helpers**

Replace the profile-only carrier assumption with domain-owned helpers such as:

```python
def build_buddy_domain_instance_id(*, profile_id: str, domain_id: str) -> str: ...
def build_buddy_domain_control_thread_id(*, instance_id: str) -> str: ...
def build_buddy_execution_carrier_handoff(..., instance_id: str, control_thread_id: str | None = None) -> dict[str, object]: ...
```

Rules:
- do not derive runtime truth from `buddy:{profile_id}` anymore for new carriers
- one domain record must always resolve to one stable carrier id
- restore must reuse the archived record's stored ids

- [ ] **Step 4: Refactor `BuddyOnboardingService` switch flow**

Implement these behaviors:

```python
if capability_action == "keep-active":
    reuse bound carrier ids from the active record
elif capability_action == "restore-archived":
    reactivate archived record + archived carrier ids
elif capability_action == "start-new":
    archive current record/carrier and create a fresh bound carrier
```

Carrier lifecycle rules:
- freeze/archive the old carrier using existing industry lifecycle semantics that the runtime already understands
- do not invent a parallel carrier state system
- for legacy records with blank binding fields, bind the existing shared `buddy:{profile_id}` carrier once to the current active domain record and stop creating new shared carriers after that

- [ ] **Step 5: Run the focused backend suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

---

### Task 3: Isolate Capability Growth To The Active Domain Carrier

**Files:**
- Modify: `src/copaw/kernel/buddy_domain_capability_growth.py`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `tests/kernel/test_buddy_projection_capability.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write the failing leakage tests**

Lock the bug that motivated this work:

```python
def test_start_new_domain_does_not_inherit_old_carrier_evidence(tmp_path) -> None: ...
def test_restore_archived_domain_recovers_old_capability_score_from_its_bound_carrier(tmp_path) -> None: ...
def test_buddy_surface_returns_active_domain_execution_carrier_binding(tmp_path) -> None: ...
```

- [ ] **Step 2: Run the focused growth/projection suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: FAIL because growth still collects signals from `buddy:{profile_id}` instead of the active domain's bound carrier.

- [ ] **Step 3: Re-scope growth to the bound carrier**

Change the growth service from:

```python
instance_id = f"buddy:{profile_id}"
instance = get_instance(instance_id)
```

to:

```python
active = self._domain_capability_repository.get_active_domain_capability(profile_id)
instance = get_instance(active.industry_instance_id)
```

Rules:
- if the active record has no binding yet, attempt the one-time legacy backfill first
- only read lanes/backlog/cycles/assignments/reports from the bound `industry_instance_id`
- never aggregate archived carriers into the active score

- [ ] **Step 4: Re-scope Buddy projection to the bound carrier**

`BuddyProjectionService` must:
- build `execution_carrier` from the active record's stored `industry_instance_id` and `control_thread_id`
- keep Runtime Center/Chat summary aligned with the same active record
- stop manufacturing a profile-only carrier id

- [ ] **Step 5: Run the focused growth/projection suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

---

### Task 4: Keep The Page As Switch-Only And Preserve Restore Continuity

**Files:**
- Modify: `console/src/api/modules/buddy.ts`
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Modify: `console/src/runtime/buddyFlow.test.ts`

- [ ] **Step 1: Write the failing frontend tests**

Add UI/flow coverage that proves:

```tsx
it("treats the onboarding confirm flow as hard domain switching, not general expansion", () => {})
it("uses the restored execution carrier control_thread_id when returning to chat", () => {})
it("does not assume buddy:{profile_id} when resuming chat-ready flow", () => {})
```

- [ ] **Step 2: Run the focused frontend suite to verify it fails**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/runtime/buddyFlow.test.ts src/api/modules/buddy.test.ts`
Expected: FAIL because the current tests/copy still assume the old shared carrier identity and the page wording does not clearly frame this as a hard switch flow.

- [ ] **Step 3: Implement the minimal frontend cutover**

Requirements:
- keep the page flow focused on `keep-active / restore-archived / start-new`
- use the returned `execution_carrier` ids exactly as provided by the backend
- do not re-derive or assume `buddy:{profile_id}`
- clarify in copy that ordinary domain expansion happens in chat, while this page is for switching the current main domain

- [ ] **Step 4: Run the focused frontend suite to verify it passes**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/runtime/buddyFlow.test.ts src/api/modules/buddy.test.ts`
Expected: PASS

---

### Task 5: Sync Docs And Run Full Verification

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `TASK_STATUS.md`
- Modify: `AGENT_VISIBLE_MODEL.md`

- [ ] **Step 1: Update architecture/status docs**

Record:
- `BuddyDomainCapabilityRecord` now owns carrier binding
- page switch vs chat expansion split
- legacy shared `buddy:{profile_id}` carrier is no longer the canonical runtime identity for new domains

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
git add DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md TASK_STATUS.md AGENT_VISIBLE_MODEL.md src/copaw/state/models_buddy.py src/copaw/state/repositories_buddy.py src/copaw/state/store.py src/copaw/kernel/buddy_execution_carrier.py src/copaw/kernel/buddy_onboarding_service.py src/copaw/kernel/buddy_domain_capability_growth.py src/copaw/kernel/buddy_projection_service.py src/copaw/app/runtime_service_graph.py tests/state/test_buddy_models.py tests/state/test_buddy_domain_capability_repository.py tests/state/test_state_store_migration.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py console/src/api/modules/buddy.ts console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx console/src/runtime/buddyFlow.test.ts
git commit -m "feat: split buddy execution carriers by domain"
```

