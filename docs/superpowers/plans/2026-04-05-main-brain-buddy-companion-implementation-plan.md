# Main-Brain Buddy Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old industry-first first-entry and plain chat shell with a Buddy-first companion system where Buddy is the main brain's only external personality shell, chat is the primary companionship surface, and Buddy growth/evolution stays derived from formal runtime truth.

**Architecture:** Introduce a human-first onboarding chain, formal Buddy projection/read-model services, and a chat-first front-end shell that consumes Buddy presentation and growth projections. Keep canonical truth in main-brain/state objects, derive Buddy presentation/growth from that truth, and retire first-entry reliance on the old `industry-profile-v1` mindset.

**Tech Stack:** FastAPI, Pydantic, Python state/kernel services, React + TypeScript + Ant Design, Less, pytest, frontend unit tests

---

## File Structure

### New backend units

- `src/copaw/state/models_buddy.py`
  - Human-facing truth/projection schemas for `HumanProfile`, `GrowthTarget`, `CompanionRelationship`, `BuddyPresentation`, `BuddyGrowthProjection`
- `src/copaw/state/repositories_buddy.py`
  - persistence seams for human profile / relationship / direction-confirmation data
- `src/copaw/kernel/buddy_onboarding_service.py`
  - onboarding identity intake, clarification turn handling, candidate direction generation, primary direction confirmation
- `src/copaw/kernel/buddy_projection_service.py`
  - derive Buddy presentation/growth payload from formal truth
- `src/copaw/app/routers/buddy_routes.py`
  - onboarding and Buddy read/mutation API front-door

### Existing backend files to modify

- `src/copaw/state/__init__.py`
  - export new buddy-related models/services
- `src/copaw/state/store.py`
  - add persistence tables/columns for onboarding truth that belongs in formal state
- `src/copaw/app/runtime_service_graph.py`
  - wire buddy onboarding/projection services
- `src/copaw/app/routers/__init__.py`
  - register new Buddy routes
- `src/copaw/app/routers/industry.py`
  - remove old first-entry assumptions from primary UI path, keep industry bootstrap as downstream scaffold only
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - optionally expose compact Buddy cockpit summary for main-brain page if shared there

### New frontend units

- `console/src/api/modules/buddy.ts`
  - onboarding + buddy surface API client
- `console/src/pages/BuddyOnboarding/index.tsx`
  - first-entry identity form + clarification flow
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  - onboarding UI tests
- `console/src/pages/Chat/BuddyCompanion.tsx`
  - small always-visible companion shell
- `console/src/pages/Chat/BuddyPanel.tsx`
  - expanded Buddy sheet with Identity / Relationship / Growth / Capability / Current Bond Context
- `console/src/pages/Chat/buddyPresentation.ts`
  - chat-side Buddy presentation helpers and state mapping
- `console/src/pages/Chat/buddyPresentation.test.ts`
  - presentation helper tests

### Existing frontend files to modify

- `console/src/pages/Industry/index.tsx`
  - remove first-entry ownership from old industry bootstrap path
- `console/src/pages/Chat/index.tsx`
  - add Buddy shell and expanded panel entry points
- `console/src/pages/Chat/pagePresentation.tsx`
  - integrate Buddy read-model into current chat runtime presentation
- `console/src/pages/Chat/index.module.less`
  - style Buddy companion shell and expanded panel
- `console/src/routes/*` or current route config file
  - make Buddy onboarding the default first-entry route
- `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
  - add compact Buddy cockpit summary without making Runtime Center the primary relationship surface

### Tests to add or extend

- `tests/kernel/test_buddy_onboarding_service.py`
- `tests/kernel/test_buddy_projection_service.py`
- `tests/app/test_buddy_routes.py`
- `tests/app/test_buddy_cutover.py`
- `console/src/api/modules/buddy.test.ts`
- `console/src/pages/Chat/BuddyPanel.test.tsx`
- `console/src/pages/Chat/BuddyCompanion.test.tsx`
- `console/src/pages/BuddyOnboarding/index.test.tsx`

---

### Task 1: Land Formal Buddy Truth And Projection Models

**Files:**
- Create: `src/copaw/state/models_buddy.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/store.py`
- Test: `tests/state/test_buddy_models.py`

- [ ] **Step 1: Write the failing model/state test**

```python
def test_buddy_models_round_trip_required_fields() -> None:
    profile = HumanProfile(
        profile_id="hp-1",
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="Build a long-term creative career",
    )
    assert profile.display_name == "Alex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/state/test_buddy_models.py -q`
Expected: FAIL with import/model missing errors

- [ ] **Step 3: Write the minimal buddy state models**

```python
class HumanProfile(BaseModel): ...
class GrowthTarget(BaseModel): ...
class CompanionRelationship(BaseModel): ...
class BuddyPresentation(BaseModel): ...
class BuddyGrowthProjection(BaseModel): ...
```

- [ ] **Step 4: Add store schema support**

Add minimal persisted structures for:
- human profile truth
- growth target truth
- companion relationship truth

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/state/test_buddy_models.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/models_buddy.py src/copaw/state/__init__.py src/copaw/state/store.py tests/state/test_buddy_models.py
git commit -m "feat: add buddy truth and projection models"
```

### Task 2: Build Buddy Onboarding Backend

**Files:**
- Create: `src/copaw/kernel/buddy_onboarding_service.py`
- Create: `src/copaw/app/routers/buddy_routes.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/app/test_buddy_routes.py`

- [ ] **Step 1: Write the failing onboarding service test**

```python
async def test_buddy_onboarding_caps_clarification_questions() -> None:
    service = BuddyOnboardingService(...)
    result = await service.answer_clarification_turn(
        session_id="s-1",
        user_id="u-1",
        answer="I still feel lost",
        existing_question_count=9,
    )
    assert result.finished is True
```

- [ ] **Step 2: Run service test to verify it fails**

Run: `python -m pytest tests/kernel/test_buddy_onboarding_service.py -q`
Expected: FAIL with service missing

- [ ] **Step 3: Implement onboarding service**

Minimum behavior:
- accept basic identity payload
- generate clarification questions
- cap at 9 questions
- tighten after 5
- converge to 2-3 candidate directions
- require confirmation of exactly one primary direction

- [ ] **Step 4: Write failing route tests**

```python
def test_create_identity_profile_returns_session_token(client):
    response = client.post("/api/buddy/onboarding/identity", json={...})
    assert response.status_code == 200
```

- [ ] **Step 5: Implement routes**

Add route families for:
- identity submit
- clarification turn
- candidate directions read
- primary direction confirm
- first-chat buddy naming

- [ ] **Step 6: Run targeted backend tests**

Run: `python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/kernel/buddy_onboarding_service.py src/copaw/app/routers/buddy_routes.py src/copaw/app/runtime_service_graph.py src/copaw/app/routers/__init__.py tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_routes.py
git commit -m "feat: add buddy onboarding backend"
```

### Task 3: Build Buddy Projection Service

**Files:**
- Create: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/kernel/test_buddy_projection_service.py`
- Test: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write the failing projection test**

```python
def test_buddy_projection_derives_growth_from_formal_truth() -> None:
    projection = BuddyProjectionService(...).build_chat_surface(...)
    assert projection.growth.intimacy >= 0
    assert projection.presentation.current_task_summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/kernel/test_buddy_projection_service.py -q`
Expected: FAIL with service missing

- [ ] **Step 3: Implement projection service**

Implement derivation from:
- human profile
- primary direction / final goal
- current focus
- relationship signals
- assignment/report/interaction counts

- [ ] **Step 4: Add compact cockpit summary seam**

Expose a small Buddy summary for runtime center/main-brain cockpit without turning Runtime Center into the primary Buddy surface.

- [ ] **Step 5: Run targeted tests**

Run: `python -m pytest tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/buddy_projection_service.py src/copaw/app/runtime_service_graph.py src/copaw/app/routers/runtime_center_routes_core.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_cutover.py
git commit -m "feat: add buddy projection service"
```

### Task 4: Replace First Entry With Buddy Onboarding

**Files:**
- Modify: `console/src/pages/Industry/index.tsx`
- Create: `console/src/pages/BuddyOnboarding/index.tsx`
- Create: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Create: `console/src/api/modules/buddy.ts`
- Test: `console/src/api/modules/buddy.test.ts`
- Modify: current frontend route registration file(s)

- [ ] **Step 1: Write the failing onboarding page test**

```tsx
it("shows buddy identity form instead of old industry-first brief as default entry", async () => {
  render(<BuddyOnboardingPage />);
  expect(screen.getByLabelText("姓名")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console run test -- src/pages/BuddyOnboarding/index.test.tsx`
Expected: FAIL with page/module missing

- [ ] **Step 3: Implement onboarding API client**

Add client calls for:
- identity submit
- clarification answer
- direction confirmation
- naming

- [ ] **Step 4: Implement Buddy onboarding page**

Required behaviors:
- basic identity form
- clarification question flow
- 9-question cap
- candidate directions display
- one-primary-direction confirmation

- [ ] **Step 5: Switch default first-entry route**

Make Buddy onboarding the default first human entry.
Keep old industry page reachable only as downstream execution/business setup where needed.

- [ ] **Step 6: Run frontend tests**

Run: `npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add console/src/api/modules/buddy.ts console/src/api/modules/buddy.test.ts console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx console/src/pages/Industry/index.tsx
git commit -m "feat: add buddy-first onboarding entry"
```

### Task 5: Land Chat-First Buddy Shell

**Files:**
- Create: `console/src/pages/Chat/BuddyCompanion.tsx`
- Create: `console/src/pages/Chat/BuddyCompanion.test.tsx`
- Create: `console/src/pages/Chat/BuddyPanel.tsx`
- Create: `console/src/pages/Chat/BuddyPanel.test.tsx`
- Create: `console/src/pages/Chat/buddyPresentation.ts`
- Create: `console/src/pages/Chat/buddyPresentation.test.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/pagePresentation.tsx`
- Modify: `console/src/pages/Chat/index.module.less`

- [ ] **Step 1: Write failing presentation helper test**

```ts
it("maps buddy projection into chat companion display fields", () => {
  const view = presentBuddyPanel({...});
  expect(view.sections.identity.title).toBeTruthy();
});
```

- [ ] **Step 2: Run helper test to verify it fails**

Run: `npm --prefix console run test -- src/pages/Chat/buddyPresentation.test.ts`
Expected: FAIL with module missing

- [ ] **Step 3: Implement presentation helpers**

Add mapping from backend `BuddyPresentation` + `BuddyGrowthProjection` into:
- small shell props
- expanded panel sections
- current state badge text

- [ ] **Step 4: Write failing UI tests**

```tsx
it("expands buddy panel when companion shell is clicked", async () => {
  render(<ChatPage ... />);
  await user.click(screen.getByTestId("buddy-shell"));
  expect(screen.getByText("亲密度")).toBeInTheDocument();
});
```

- [ ] **Step 5: Implement companion shell and panel**

Required UI:
- small always-visible Buddy shell
- click to expand
- sections for Identity / Relationship / Growth / Capability / Current Bond Context
- chat-first action affordances, not admin-console controls

- [ ] **Step 6: Run frontend Buddy chat tests**

Run: `npm --prefix console run test -- src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/buddyPresentation.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add console/src/pages/Chat/BuddyCompanion.tsx console/src/pages/Chat/BuddyCompanion.test.tsx console/src/pages/Chat/BuddyPanel.tsx console/src/pages/Chat/BuddyPanel.test.tsx console/src/pages/Chat/buddyPresentation.ts console/src/pages/Chat/buddyPresentation.test.ts console/src/pages/Chat/index.tsx console/src/pages/Chat/pagePresentation.tsx console/src/pages/Chat/index.module.less
git commit -m "feat: add chat-first buddy shell"
```

### Task 6: Add Buddy Naming In First Real Chat

**Files:**
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Test: `console/src/pages/Chat/BuddyPanel.test.tsx`
- Test: `tests/app/test_buddy_routes.py`

- [ ] **Step 1: Write failing naming-flow tests**

```tsx
it("prompts for buddy naming in first real chat when buddy is born but unnamed", async () => {
  render(<ChatPage ... />);
  expect(screen.getByText("请给你的伙伴起个名字")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix console run test -- src/pages/Chat/BuddyPanel.test.tsx`
Expected: FAIL with naming prompt missing

- [ ] **Step 3: Implement backend naming mutation**

Minimal behavior:
- accept free-form buddy name
- persist external companion name
- switch lifecycle state from `born-unnamed` to `named`

- [ ] **Step 4: Implement first-chat prompt wiring**

The naming prompt should happen in chat flow, not in a config form.

- [ ] **Step 5: Run route + UI tests**

Run: `python -m pytest tests/app/test_buddy_routes.py -q`
Run: `npm --prefix console run test -- src/pages/Chat/BuddyPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/routers/buddy_routes.py console/src/pages/Chat/index.tsx console/src/pages/Chat/runtimeTransport.ts tests/app/test_buddy_routes.py console/src/pages/Chat/BuddyPanel.test.tsx
git commit -m "feat: add buddy first-chat naming"
```

### Task 7: Land Growth Calculation And Evolution Mapping

**Files:**
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Create: `console/src/pages/Chat/buddyEvolution.ts`
- Create: `console/src/pages/Chat/buddyEvolution.test.ts`
- Modify: `console/src/pages/Chat/BuddyCompanion.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`

- [ ] **Step 1: Write failing evolution tests**

```ts
it("maps growth thresholds into evolution stages", () => {
  expect(resolveBuddyEvolutionStage({ growthLevel: 5, intimacy: 80 })).toBe("bonded");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix console run test -- src/pages/Chat/buddyEvolution.test.ts`
Expected: FAIL with missing mapping

- [ ] **Step 3: Implement evolution mapping**

Map formal derived scores to:
- stage
- rarity
- form
- effect set

- [ ] **Step 4: Implement backend formula thresholds**

Land explainable, thresholded formulas for:
- intimacy
- affinity
- level
- knowledge
- skill
- pleasant interaction

- [ ] **Step 5: Run targeted tests**

Run: `python -m pytest tests/kernel/test_buddy_projection_service.py -q`
Run: `npm --prefix console run test -- src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/buddy_projection_service.py console/src/pages/Chat/buddyEvolution.ts console/src/pages/Chat/buddyEvolution.test.ts console/src/pages/Chat/BuddyCompanion.tsx console/src/pages/Chat/BuddyPanel.tsx
git commit -m "feat: add buddy growth and evolution mapping"
```

### Task 8: Align Main-Brain Cockpit And Remove Old First-Entry Primacy

**Files:**
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write failing cockpit summary test**

```tsx
it("shows compact buddy summary without replacing runtime cockpit truth", () => {
  render(<MainBrainCockpitPanel ... />);
  expect(screen.getByText("最终目标")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix console run test -- src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: FAIL with summary missing

- [ ] **Step 3: Implement compact Buddy cockpit summary**

Show:
- final goal
- current task
- why now
- compact growth/continuity summary

- [ ] **Step 4: Demote old industry-first entry**

Ensure old industry page is no longer the primary first human entry and reads as downstream business/execution setup where still needed.

- [ ] **Step 5: Run targeted tests**

Run: `python -m pytest tests/app/test_buddy_cutover.py -q`
Run: `npm --prefix console run test -- src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/Industry/index.tsx tests/app/test_buddy_cutover.py console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
git commit -m "feat: align main-brain cockpit with buddy system"
```

### Task 9: Full Verification And Documentation Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `FRONTEND_UPGRADE_PLAN.md`
- Modify: `RUNTIME_CENTER_UI_SPEC.md`
- Modify: `AGENT_VISIBLE_MODEL.md`
- Test: relevant backend and frontend suites

- [ ] **Step 1: Sync architecture docs**

Update documents so they reflect:
- Buddy-first onboarding
- chat-first Buddy surface
- cockpit alignment
- no second truth source

- [ ] **Step 2: Run backend verification**

Run:

```bash
python -m pytest tests/state/test_buddy_models.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q
```

Expected: PASS

- [ ] **Step 3: Run frontend verification**

Run:

```bash
npm --prefix console run test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/buddyEvolution.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm --prefix console run build
```

Expected: build succeeds

- [ ] **Step 5: Final commit**

```bash
git add TASK_STATUS.md FRONTEND_UPGRADE_PLAN.md RUNTIME_CENTER_UI_SPEC.md AGENT_VISIBLE_MODEL.md
git commit -m "docs: sync buddy companion rollout"
```

---

## Notes For Execution

- Do not create a second Buddy truth database.
- Do not let Buddy become a second speaking persona in prompts.
- Do not let the old industry bootstrap remain the default first human entry.
- Keep the human default read surface simple: final goal + current task.
- Prefer TDD per task; avoid batching many unverified edits together.
- Frequent commits are required because this rollout touches onboarding, chat, runtime cockpit, and formal truth seams.
