# Buddy Industry Direction Truth Design

## 0. Purpose

This spec fixes one concrete truth-boundary bug in the Buddy onboarding chain:

- the human's current profile is currently being written into the formal industry carrier profile slot
- the main brain's formal direction should instead come from the confirmed direction and final goal

The target is not a broader Buddy redesign.

The target is:

- keep `HumanProfile` as the canonical record of the human's current reality
- keep `IndustryProfile` as the canonical record of the execution carrier's formal direction
- stop writing current human facts into `IndustryInstanceRecord.profile_payload`
- make Buddy-generated carriers safe for the existing industry/runtime/strategy read chain

---

## 1. Problem Statement

Today `BuddyOnboardingService._ensure_growth_scaffold(...)` writes this into
`IndustryInstanceRecord.profile_payload`:

- `profession`
- `current_stage`
- `goal_intention`
- `interests`
- `strengths`
- `constraints`

That payload is not a valid `IndustryProfile`.

But the industry runtime and strategy services already treat
`IndustryInstanceRecord.profile_payload` as a formal `IndustryProfile` and read it through:

- `IndustryRuntimeViews._build_instance_detail(...)`
- `IndustryStrategyService._materialize_execution_core_identity(...)`
- other industry read paths that call `IndustryProfile.model_validate(record.profile_payload)`

So the current implementation corrupts the formal industry truth slot and can break downstream reads.

---

## 2. Core Judgment

The human's current reality and the main brain's formal direction are different objects.

They must stay split:

- `HumanProfile`
  - what the human is today
  - current profession
  - current stage
  - interests / strengths / constraints
  - goal intention
- `GrowthTarget`
  - chosen primary direction
  - final goal
  - why it matters
- `IndustryProfile`
  - the formal execution-carrier direction used by industry/runtime/strategy chains

Buddy onboarding may use `HumanProfile` to decide the direction.

But once the user confirms a direction, the generated carrier must write a formal
`IndustryProfile`, not a human snapshot.

---

## 3. Target Behavior

### 3.1 Backend truth boundary

After `confirm_primary_direction(...)`:

- `HumanProfile` remains unchanged as the canonical human snapshot
- `GrowthTarget.primary_direction` and `GrowthTarget.final_goal` remain the canonical chosen direction
- `IndustryInstanceRecord.profile_payload` must become a valid `IndustryProfile`

That `IndustryProfile` should be direction-oriented:

- `industry`
  - derived from `primary_direction`
- `goals`
  - includes `final_goal`
- `constraints`
  - may include human constraints only as execution constraints, not as identity truth
- `notes`
  - may summarize the Buddy bootstrap context

The exact text can stay minimal.
The important part is that the payload is valid, formal, and direction-first.

### 3.2 Execution identity alignment

`execution_core_identity_payload` should keep carrying the formal direction facts:

- `primary_direction`
- `final_goal`

It must stay aligned with the `IndustryProfile` that was written into the carrier.

### 3.3 Frontend mindshare

The current carrier / industry adjustment UI must not reinforce the wrong mental model.

For Buddy-created carriers, the UI should communicate:

- this field is the formal direction / execution direction
- it is not simply the user's current profession or current industry

This does not require a front-end redesign.
It only requires removing the misleading coupling.

---

## 4. Non-Goals

This spec does not:

- redesign Buddy onboarding questions
- change the candidate-direction heuristic
- introduce a new profile schema
- create a parallel Buddy-only industry truth model
- rewrite the broader industry bootstrap flow

---

## 5. Implementation Shape

### 5.1 Backend

Add a small helper in `src/copaw/kernel/buddy_onboarding_service.py` that builds a minimal formal `IndustryProfile` from:

- `HumanProfile`
- `GrowthTarget`

Then use that helper inside `_ensure_growth_scaffold(...)` when writing
`IndustryInstanceRecord.profile_payload`.

Recommended output shape:

- `industry`: normalized `primary_direction`
- `goals`: `[final_goal]`
- `constraints`: normalized copy of `HumanProfile.constraints`
- `notes`: short Buddy bootstrap summary mentioning the human context

### 5.2 Tests

Lock the contract with targeted backend tests:

- Buddy confirmation writes a `profile_payload` that `IndustryProfile.model_validate(...)` accepts
- the resulting profile's `industry` is direction-based
- the resulting profile's `goals` contains `final_goal`
- current human snapshot fields are no longer written into `profile_payload`

Add one focused frontend test only if needed to protect the UI mental model.

---

## 6. Why This Is The Right Cut

This fix follows the existing architecture instead of adding more exceptions:

- no new truth source
- no new compatibility layer
- no special Buddy-only runtime read path
- no parallel industry profile semantics

It simply restores the formal contract that the rest of the industry/runtime system already assumes.

---

## 7. Acceptance Criteria

This work is complete when:

1. `BuddyOnboardingService.confirm_primary_direction(...)` produces an industry carrier whose `profile_payload` validates as `IndustryProfile`
2. the generated `IndustryProfile` is direction-first rather than human-snapshot-first
3. existing industry/runtime/strategy reads no longer depend on invalid Buddy profile payloads
4. the relevant tests fail before the change and pass after the change
5. the front-end current carrier mindshare no longer implies that the main brain's formal direction equals the user's current profession
