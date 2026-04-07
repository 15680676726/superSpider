# Buddy Domain Capability Stage Design

## 0. Purpose

This spec defines Buddy's growth-stage model as a capability system tied to the human's current domain/direction, not as a relationship-only progression.

The target behavior is:

- Buddy keeps one global identity/profile
- Buddy keeps one global relationship layer
- Buddy capability progress is tracked per domain
- current displayed stage always comes from the active domain capability record
- switching to an unrelated domain feels like a rebirth in the current view
- previously learned domains are archived, not deleted, and can be restored later

This replaces the earlier idea of only relabeling the existing stage copy.

---

## 1. Core Judgment

Buddy stage must not mean:

- current task phase
- current chat mood
- global relationship warmth
- total conversation count

Buddy stage must mean:

> Buddy's current execution and guidance capability in the active domain

In practice, this means the stage represents how well the main-brain companion can:

- understand the current domain
- hold stable strategy in that domain
- decompose work into executable next actions
- drive work to actual closure
- accumulate reusable evidence and operating judgment

Relationship signals remain important, but they belong to the relationship layer rather than the capability-stage layer.

---

## 2. Object Boundary

Buddy should be modeled as two layers:

### 2.1 Global Buddy Layer

This layer remains profile-scoped and does not reset on domain switching.

It includes:

- `HumanProfile`
- `CompanionRelationship`
- Buddy naming
- encouragement style
- intimacy / affinity / mood / presence
- stable companionship memory

### 2.2 Domain Capability Layer

This layer is profile-owned but domain-specific.

It includes:

- one active domain capability record
- zero or more archived domain capability records
- capability score
- capability stage
- domain-specific knowledge / execution / evidence / stability progress

This means:

- global relationship does not reset
- current displayed stage depends only on the active domain capability record
- archived domains can be restored later

---

## 3. New Formal Object

Introduce a formal state object:

- `BuddyDomainCapabilityRecord`

Recommended fields:

- `domain_id`
- `profile_id`
- `domain_key`
- `domain_label`
- `status` = `active | archived`
- `strategy_score`
- `execution_score`
- `evidence_score`
- `stability_score`
- `capability_score`
- `evolution_stage`
- `knowledge_value`
- `skill_value`
- `completed_support_runs`
- `completed_assisted_closures`
- `evidence_count`
- `report_count`
- `last_activated_at`
- `last_progress_at`

Boundary:

- `GrowthTarget` continues to answer "what is the current target"
- `CompanionRelationship` continues to answer "how should Buddy accompany the human"
- `BuddyDomainCapabilityRecord` answers "how capable is Buddy in the active domain"

---

## 4. Stage Vocabulary

The user-facing stage labels remain:

- `幼年期`
- `成长期`
- `成熟期`
- `完全体`
- `究极体`

These are not mere cosmetic labels.

They now map to capability maturity in the active domain.

Suggested canonical internal stage mapping may still use the current enum values:

- `seed` -> `幼年期`
- `bonded` -> `成长期`
- `capable` -> `成熟期`
- `seasoned` -> `完全体`
- `signature` -> `究极体`

This spec does not require renaming internal enums in the first round.

---

## 5. Capability Score Model

Buddy stage should be derived from a domain capability score in the range `0-100`.

### 5.1 Score Components

- `strategy_score` `0-25`
  Measures whether the current domain has stable strategic grounding:
  active direction, formal cycle, planning surface, execution carrier, stable current chain.

- `execution_score` `0-35`
  Measures whether work actually gets pushed through:
  completed support runs, assisted closures, finished tasks, real outcome advancement.

- `evidence_score` `0-20`
  Measures whether the domain has real accumulated output:
  evidence, reports, observable deliverables, not only chat intent.

- `stability_score` `0-20`
  Measures whether the domain progress is durable and reusable:
  continuity across cycles, low restart churn, ability to keep advancing without collapse.

### 5.2 Stage Bands

- `0-19` -> `幼年期`
- `20-39` -> `成长期`
- `40-59` -> `成熟期`
- `60-79` -> `完全体`
- `80-100` -> `究极体`

### 5.3 Explicit Non-Drivers

The following must not directly determine capability stage:

- intimacy
- affinity
- communication count
- mood
- presence state

These remain relationship/presentation signals only.

---

## 6. Domain Switching Rules

Switching goals must become an explicit flow rather than an implicit overwrite.

### 6.1 Same-Domain Extension

Example:

- stock trading target grows from `10w` to `100w`

Rule:

- keep the active domain capability record
- update target difficulty and current target fields
- do not reset stage

### 6.2 Cross-Domain Switch

Example:

- stock trading -> writing

Rule:

- archive the current domain capability record
- switch to a matching archived domain if one exists
- otherwise create a fresh domain capability record at the initial stage

### 6.3 Restore Archived Domain

If the human later returns to a previous domain:

- restore that archived domain capability record
- make it active again
- recover its previous capability score and stage

Archived domain capability must be preserved, not deleted.

---

## 7. Same-Domain vs Cross-Domain Decision Policy

The system may suggest whether a target change looks like:

- `same-domain`
- `switch-to-archived-domain`
- `start-new-domain`

But the final choice must be confirmed by the human.

Allowed user actions:

- continue current domain capability
- switch to an archived domain capability
- start a brand-new domain capability

The system must not silently decide irreversible domain inheritance.

---

## 8. Service And Projection Changes

### 8.1 `BuddyOnboardingService`

`confirm_primary_direction(...)` must evolve from:

- only writing `GrowthTarget`

to:

- writing/updating `GrowthTarget`
- resolving domain-switch suggestion
- applying the user's confirmation
- activating or creating the correct domain capability record
- archiving previous active domain capability when needed

### 8.2 `BuddyProjectionService`

`build_chat_surface(...)` must evolve from:

- deriving stage mainly from relationship-heavy experience signals

to:

- reading the active `BuddyDomainCapabilityRecord`
- projecting stage from its `capability_score` / `evolution_stage`
- keeping relationship values separate

### 8.3 Frontend Surfaces

`Chat`, `BuddyPanel`, and `Runtime Center` must display:

- active domain stage
- active domain capability progress

They may still display relationship signals, but those must not be presented as stage drivers.

---

## 9. Current Gap

Current implementation does not yet satisfy this model.

Today:

- `GrowthTarget` is profile-scoped and overwritten by latest direction
- relationship state is preserved globally
- Buddy stage is still derived from relationship-heavy progress signals
- there is no formal archived/restorable domain capability object
- there is no explicit same-domain vs cross-domain confirmation flow

Therefore, the current system can accidentally make unrelated domains inherit the wrong stage.

---

## 10. Initial Rollout Guidance

The first rollout should prioritize correctness of the truth model over UI polish.

Recommended order:

1. Add `BuddyDomainCapabilityRecord`
2. Add repository + state persistence
3. Add domain-switch suggestion + explicit confirmation contract
4. Move projection-stage logic to active domain capability
5. Update frontend copy and display

Do not start by only changing labels.

---

## 11. Out Of Scope For This Round

- advanced semantic domain similarity engine
- automatic merging of two archived domains
- deleting archived domain capability records
- changing Buddy's mood/presence animation system
- deep redesign of runtime center layout

---

## 12. Supersession Note

This spec supersedes the earlier UI-only relabeling direction for Buddy stage presentation.
