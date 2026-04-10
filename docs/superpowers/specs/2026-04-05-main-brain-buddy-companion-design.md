# CoPaw Main-Brain Buddy Companion Design

## 0. Purpose

This spec defines how `CoPaw` should introduce a buddy-style companion without creating:

- a second main brain
- a second truth source
- a toy pet system detached from runtime truth

The target is not to copy `cc`'s buddy product shape.

The target is:

- keep the main brain as the only strategic center
- make the main brain visible as one long-term human companion
- let chat become the primary relationship surface
- let Buddy express growth, warmth, and continuity without replacing formal runtime truth

This spec is product-and-architecture guidance for the companion layer.

It does not replace:

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- the formal runtime truth chain already centered on
  `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`

---

## 1. Core Judgment

`Buddy` should not be implemented as:

- a separate agent
- a pet plugin
- a second chat persona
- a config-only visual toy

`Buddy` should be implemented as:

> the main brain's only external personality shell and companion expression layer

That means:

- this is an upgrade on top of the existing main-brain/runtime/human-assist foundation, not a greenfield replacement
- the main brain remains the only strategic authority
- Buddy is the only front-facing voice the human primarily interacts with
- specialist seats remain backstage execution members
- Buddy translates formal runtime truth into a long-term human relationship

---

## 2. Product Position

### 2.1 Buddy's Product Role

Buddy is a fusion of:

- growth coach
- life/task manager
- long-term companion

But the front-stage tone is not "manager."

It is:

- like an old friend
- emotionally receptive first
- task-guiding second
- planning-capable underneath

### 2.2 The Human Default View

The default human view should stay intentionally simple.

By default, Buddy should show only:

- the final goal
- the current task

The human should not be forced to see:

- the entire plan tree
- future task queues
- internal execution decomposition
- specialist seat internals

If the human asks "why now?" or "what comes next?", Buddy may progressively reveal more.

### 2.3 Core Interaction Principle

Buddy should answer current work in this order:

1. what the final goal is
2. what the current task is
3. why this task must be done now rather than later
4. what single next action the human should take

The human should feel accompanied, not managed by a dashboard.

---

## 3. Formal Boundary

### 3.1 Hard Rules

The following must remain true:

- the main brain itself does not get replaced
- Buddy has no independent long-term mission
- Buddy has no independent planning chain
- Buddy has no independent truth store
- Buddy does not bypass the main brain
- Buddy does not compete with specialist seats for front-stage ownership

### 3.2 What Buddy May Influence

Buddy may influence:

- presentation
- tone
- companionship style
- intervention strength
- visible growth and appearance

Buddy must not directly rewrite:

- formal risk decisions
- formal execution truth
- governance rules
- main-brain strategic truth

### 3.3 Execution Seat Relation

The formal relation should be:

- specialist seats do the work
- human-assist/current-task objects remain formal runtime truth
- results flow back through the main brain
- Buddy speaks to the human about those results
- the source seat may be labeled, but should not take over the front-stage voice

This means the human-facing task experience should move toward:

- chat-led task delivery
- chat-led acceptance / evidence submission
- chat-led recovery and pull-back

and away from:

- a standalone front-stage task module as the primary human interaction surface

The intended human feeling is:

> one companion is guiding me while a backstage team works with it

not:

> I am juggling multiple speaking agents

---

## 4. Truth And Memory Model

Buddy does not get a separate memory system.

Instead, the main brain's formal human-facing memory should be strengthened and then projected through Buddy.

### 4.1 Required Human-Facing Main-Brain Memory Layers

Recommended layers:

1. `HumanProfile`
   - identity background
   - current life/career stage
   - interests
   - strengths
   - constraints
   - stable preferences

2. `GrowthTarget`
   - the human's final goal
   - why that goal matters
   - current growth cycle / stage

3. `CurrentFocus`
   - the one current task
   - why it should be done now
   - what it unlocks
   - current blockers

4. `CompanionRelationship`
   - preferred encouragement style
   - reminders that work
   - reminders that fail
   - recurring avoidance patterns
   - companionship history signals

### 4.2 Memory Types

The companion-facing memory should be understood in three semantic layers:

- fact memory
- process memory
- relationship memory

Fact memory answers:

- who the human is

Process memory answers:

- where the human is going
- what is currently stuck

Relationship memory answers:

- how Buddy should accompany this person

### 4.3 Update Rules

These layers should not update at the same frequency.

- fact memory: low-frequency
- process memory: high-frequency
- relationship memory: cautious, pattern-based, not one-off emotional overfitting

This is important so Buddy becomes steadily more personal without becoming erratic.

---

## 5. Buddy Growth Model

Buddy should have explicit, game-like visible growth.

This is a feature, not a bug.

However, the growth values must remain derived from formal interaction and runtime truth rather than becoming a fake standalone mini-game.

### 5.1 Visible Growth Attributes

First-version visible attributes should include:

- intimacy
- affinity
- growth level
- companion experience
- knowledge value
- skill value
- completed support runs
- total communication count
- pleasant interaction score
- maturity / form / rarity

### 5.2 Growth Dimensions

Buddy's growth should be modeled across four dimensions:

1. `Relationship`
   - intimacy
   - affinity
   - communication continuity
   - pleasant interaction quality
   - support effectiveness

2. `Cognition`
   - knowledge depth
   - understanding of the human
   - target comprehension
   - memory stability

3. `Execution`
   - completed assistance count
   - completed support loops
   - continuity of accompaniment
   - replan / adjustment reliability

4. `PersonaExpression`
   - tone
   - proactive style
   - support style
   - visual evolution

### 5.3 Influence Level

These growth dimensions should have a medium influence on:

- how Buddy speaks
- how often Buddy initiates
- how strongly Buddy support-intervenes
- how Buddy visually evolves

But they must not have a medium influence on:

- hard governance truth
- formal safety constraints
- the correctness of risk posture

### 5.4 Evolution Principle

Buddy must evolve.

It should not stay visually and behaviorally static forever.

Evolution should happen in two layers:

1. `Visual evolution`
   - appearance parts
   - form maturity
   - sprite richness
   - rarity expression
   - accessory/status changes

2. `Expression evolution`
   - tone maturity
   - better emotional reception
   - more personalized support
   - more effective recovery pull-back

### 5.5 Formal Buddy State Families

Buddy should expose explicit visible states.

These states should remain derived from formal runtime truth and interaction truth rather than becoming an arbitrary pet simulation.

Recommended state families:

1. `LifecycleState`
   - `unborn`
   - `born-unnamed`
   - `named`
   - `bonded`
   - `evolving`

2. `PresenceState`
   - `idle`
   - `attentive`
   - `focused`
   - `supporting`
   - `pulling-back`
   - `celebrating`
   - `resting`

3. `MoodState`
   - `calm`
   - `warm`
   - `concerned`
   - `playful`
   - `proud`
   - `determined`

Rules:

- `LifecycleState` changes slowly
- `PresenceState` changes with current runtime and chat situation
- `MoodState` is an expression layer, not a second emotional truth database

### 5.6 Evolution Stages

Buddy should have visible evolution stages rather than a flat endless stat increase.

First-version recommended evolution stages:

1. `Seed Form`
   - first-born companion shell
   - simpler sprite
   - fewer accessories
   - lighter emotional expression

2. `Bonded Form`
   - stronger visual identity
   - clearer eye/hat/accessory distinction
   - more stable companionship tone

3. `Capable Form`
   - visibly more mature shell
   - richer idle/focus expressions
   - stronger execution-confidence feeling

4. `Seasoned Form`
   - stronger rarity/form signature
   - more personalized support presence
   - visibly experienced partner feeling

5. `Signature Form`
   - highest first-version evolution target
   - strongest personal identity expression
   - richest sprite/detail set
   - strongest sense that this companion has grown with this human

Rules:

- visual evolution should not depend on random cosmetic unlocks alone
- it should be driven by relationship, cognition, execution continuity, and support effectiveness
- rarity/form changes should feel earned by long-term companionship

### 5.7 Attribute Derivation Rules

Buddy's visible attributes should be projection values with stable derivation rules.

Recommended first-version derivation rules:

- `intimacy`
  - driven by communication continuity, completed support loops, reflection continuity, and companionship duration
- `affinity`
  - driven by how often the human accepts Buddy's pull-back/replan help and whether current focus stays aligned with the primary direction
- `growth level`
  - driven by total relationship, cognition, and execution growth score
- `companion experience`
  - driven by accumulated meaningful interaction and completed support activity
- `knowledge value`
  - driven by profile completeness, target understanding, recall quality, and successful explanation/support history
- `skill value`
  - driven by completed support runs, completed execution closures, and replan reliability
- `pleasant interaction score`
  - driven by rolling positive interaction quality rather than one-off emotional spikes

Rules:

- values should be smoothed and rolling, not wildly oscillating per turn
- values should be explainable from formal truth
- no value should silently override safety, governance, or risk posture

---

## 6. Interaction Model

### 6.1 Primary Surface

The main interaction surface for Buddy should be the chat page.

This is the primary relationship arena.

Buddy should not mainly live as a dashboard widget.

### 6.2 Chat-First Rule

The chat page should become:

- Buddy's home field
- the primary companionship surface
- the primary intervention surface

The runtime/main-brain page should instead serve as:

- Buddy's longer-horizon cockpit
- the summary surface for final goal and current task
- the place for reviewing growth status and longer continuity

Human collaboration tasks should follow the same rule:

- they may remain formal task objects backstage
- but they should primarily reach the human through Buddy in chat
- standalone task pages or strips should become supporting read/detail surfaces, not the primary relationship surface

### 6.3 Support Intervention Style

When the human stalls, avoids, drifts, or drops continuity, Buddy should use:

- strong support mode

This means Buddy should not only remind.

It should:

- first receive the emotion
- then identify the drift or stall
- then explain why the current task matters now
- then reconstruct exactly one next step

The tone should feel like a trusted old friend, not a system warning.

### 6.4 Default Trigger Families

First-version support triggers should be limited to:

- current task stagnation
- obvious drift from final goal
- important completion milestone
- daily/weekly reflection checkpoint

This keeps Buddy meaningfully present without turning it into spam.

### 6.5 Visible State Transitions

The state system should support clear transition logic.

Recommended examples:

- `born-unnamed -> named`
  - triggered when the human gives Buddy its first real name in chat
- `attentive -> focused`
  - triggered when the human is actively working on the current task
- `focused -> supporting`
  - triggered when Buddy is guiding a concrete current-step action
- `supporting -> pulling-back`
  - triggered when drift, avoidance, or stagnation crosses support thresholds
- `pulling-back -> celebrating`
  - triggered when the human completes the recovered current task or key milestone
- any high-activity state -> `resting`
  - triggered after meaningful closure or when the human intentionally disengages for a period

Rules:

- transitions must be driven by runtime truth or interaction truth
- transitions should not flicker excessively
- the human should be able to feel the difference between idle presence, focused accompaniment, and strong support mode

---

## 7. Frontend Surface Design

### 7.1 Chat Page

The chat page should become the primary Buddy stage.

Recommended structure:

- normal conversation area remains the main interaction surface
- a small always-visible Buddy companion stays present
- clicking Buddy expands a larger presentation and attribute panel

The expanded panel should show:

- appearance / current form
- intimacy / affinity / level
- knowledge / skill values
- support statistics
- communication statistics
- current mood / growth phase

The interaction should stay chat-centered rather than button-centered.

### 7.2 Main-Brain Page

The current main-brain page should become Buddy's cockpit rather than Buddy's primary stage.

It should focus on:

- final goal
- current task
- why now
- major continuity / growth status
- review and long-horizon summary

It should not attempt to compete with chat as the primary emotional surface.

### 7.3 Human Default Display Rule

Across front-stage Buddy surfaces, the default should stay:

- final goal
- current task

Everything more complex remains behind progressive reveal.

### 7.4 Expanded Buddy Panel Structure

When the human clicks the small Buddy companion on the chat page, the expanded panel should open as Buddy's main attribute sheet.

Recommended sections:

1. `Identity`
   - Buddy name
   - current form
   - rarity
   - current mood
   - current presence state

2. `Relationship`
   - intimacy
   - affinity
   - pleasant interaction score
   - communication continuity

3. `Growth`
   - level
   - companion experience
   - current evolution stage
   - progress to next evolution

4. `Capability`
   - knowledge value
   - skill value
   - completed support runs
   - completed assisted task closures

5. `Current Bond Context`
   - final goal
   - current task
   - why now
   - latest milestone or blocker

Rules:

- the expanded panel should still feel like meeting the companion, not opening an admin console
- growth and relationship values may be game-like, but the panel should not expose deep internal planning trees by default

### 7.5 Chat-First Interaction Actions

The expanded Buddy panel should keep the primary interaction chat-centered.

Recommended companion actions:

- `start with me`
- `I am stuck`
- `I do not want to do this`
- `help me rebuild the next step`
- `show how I have grown`

These actions should open or continue chat-led interaction flows rather than replacing chat with a separate button workflow.

---

## 8. Onboarding And Identity Formation

The current first-entry flow must not remain the old industry bootstrap mindset.

The new first-entry flow should become:

> human identity formation -> collaboration contract compile -> direction confirmation -> Buddy birth -> first chat naming

### 8.1 Core Judgment

The human's first psychological entry into CoPaw should no longer be:

- create an industry first
- create a team first
- fill a business bootstrap form first

It should instead be:

- establish who the human is
- understand where the human is in life/work
- capture what the human wants Buddy to do and how collaboration should work
- let Buddy emerge as the companion shell of the main brain

Execution-team/industry structure may still be generated afterward, but that should not be the first emotional entry point.

### 8.2 Step One: Basic Human Identity Form

The first screen should collect a compact human profile, such as:

- name
- profession
- current stage
- interests
- strengths
- current constraints or difficulties
- goal intention

This screen should feel like "the system is getting to know me," not like "I am configuring a work platform."

### 8.3 Step Two: Collaboration Contract Compile

After the basic form, the system should not immediately produce a plan.

It should collect a structured Buddy collaboration contract and compile it into candidate directions.

Hard rules:

- no clarification dialogue remains as canonical onboarding truth
- the source of truth must be explicit contract fields rather than transcript turns
- the system must still converge to a usable first result even if some fields are vague
- async UI is allowed, but the async path must still compile the same contract object rather than create a second interview flow

This contract compile may borrow from psychology-informed growth coaching or motivation clarification, but must not become:

- therapy
- diagnosis
- clinical labeling

Its role is:

- service-intent capture
- collaboration-role capture
- autonomy-boundary capture
- report-style capture
- realistic direction synthesis

### 8.4 Step Three: Candidate Directions And One Primary Direction

After contract compile, Buddy may present:

- `2-3` candidate long-horizon directions

But the human must confirm:

- exactly `1` primary direction

This primary direction must be large enough to matter.

It must not be a tiny wish, one-off errand, or trivial near-term desire.

Small wishes may still be useful clues, but they must be abstracted upward into a larger life direction before they can become formal mainline truth.

### 8.5 Step Four: Forced Convergence

Even when the human is vague, distracted, or slightly adversarial, Buddy must still converge by the question limit.

The onboarding flow must always produce at least:

- a temporary or confirmed primary direction
- an initial long-horizon outline
- a first phase focus
- a first current task

This prevents the system from degrading into endless onboarding loops.

### 8.6 Step Five: Buddy Birth And First Chat Naming

Once the primary direction and initial plan are created, the human should enter Buddy's main chat surface.

Inside the first real chat, Buddy should prompt the user to name the companion.

This naming should happen in the chat flow itself, not as a dry config field.

Rules:

- the user chooses the name freely
- the system does not need to pre-author the name
- before naming, Buddy may appear under a neutral temporary label such as "your companion"
- after naming, the main brain's external companion shell should consistently use that name

The name is:

- Buddy's external companion name

The name is not:

- a second identity object
- a second main brain
- a second truth center

### 8.7 Primary Direction Relocation

The formal primary direction may change, but not casually.

It must not drift because of a random chat turn.

Direction changes should require a formal Buddy-led review or reorientation flow.

This preserves long-term continuity while still allowing real life change.

---

## 9. Donor Mapping From `cc`

### 8.1 What To Borrow

The following donor elements are worth borrowing from `cc`:

- sprite shell
- speech bubble shell
- idle / blink / pet / focus expression mechanics
- appearance bone system such as species / rarity / eye / hat / shiny / stats
- companion visual presence logic

Relevant donor files include:

- `cc/src/buddy/CompanionSprite.tsx`
- `cc/src/buddy/types.ts`
- `cc/src/buddy/companion.ts`
- `cc/src/buddy/useBuddyNotification.tsx`

### 8.2 What Not To Borrow

The following must not be copied as-is:

- `/buddy` command as product entry
- `companion_intro` as a second speaking persona contract
- `config.companion` as Buddy's primary truth source
- Buddy as a lightweight decorative plugin detached from main-brain truth

### 8.3 Donor Rule

The donor rule should be:

- borrow `cc`'s companion shell
- do not borrow `cc`'s companion product center

In CoPaw, Buddy must be integrated into the main-brain truth chain from day one.

---

## 10. Implementation-Facing Attribute Formulas

The first implementation should not treat Buddy growth values as decorative labels only.

They need stable, explainable formula families.

Exact weights may still be tuned in implementation, but the formula structure should be fixed up front.

### 10.1 Attribute Input Sources

Recommended source families:

- `interaction truth`
  - message count
  - conversation continuity
  - accepted support prompts
  - completed pull-back loops
- `planning/execution truth`
  - current-task completion count
  - milestone completion count
  - replan success count
  - support-driven recovery count
- `memory truth`
  - profile completeness
  - goal clarity
  - constraint clarity
  - relationship-preference stability

### 10.2 First-Version Formula Guidance

The following formulas should be used as implementation guidance.

1. `intimacy`
   - highest weight: continuity of interaction over time
   - medium weight: completed support loops
   - lower weight: raw message volume
   - penalty: prolonged disengagement without intentional pause

2. `affinity`
   - highest weight: how often Buddy's suggested current step is accepted
   - medium weight: how often Buddy's pull-back/replan guidance helps the human return to the primary direction
   - penalty: repeated rejection of alignment prompts without later recovery

3. `growth_level`
   - driven by aggregate growth score across relationship, cognition, and execution
   - should use thresholded stages rather than purely linear growth

4. `knowledge_value`
   - driven by profile completeness, current-goal comprehension, target explanation success, and memory stability
   - should not rise primarily from message count alone

5. `skill_value`
   - driven by completed support runs, completed assisted closures, and successful replans
   - should reward useful action and recovery, not verbosity

6. `pleasant_interaction_score`
   - should use a rolling window
   - should be smoothed to avoid one-turn spikes
   - should reflect whether interactions are received as helpful rather than merely frequent

### 10.3 Implementation Rules

- all values should be normalized to stable ranges
- all values should be recalculable from formal truth
- all values should support future rebalance without rewriting historical truth
- the implementation should store raw contributing facts separately from display scores when possible

---

## 11. Buddy Visual Asset And Evolution Mapping

The evolution system needs a concrete asset strategy.

This must not be left as "we will style it later."

### 11.1 Donor Asset Strategy

The first version should borrow from `cc` at the shell/mechanic level:

- sprite body shell
- facial expression shell
- idle / blink / focus / pet reaction mechanics
- part slots such as eye / accessory / rarity indicators

But CoPaw should not inherit:

- `/buddy` command entry
- config-owned companion state
- second-speaking-persona prompt logic

### 11.2 Recommended CoPaw Asset Taxonomy

The first implementation should define a dedicated Buddy asset namespace, for example:

- `base_form`
- `eyes`
- `mouth_or_emotion`
- `head_accessory`
- `aura_or_rarity_ring`
- `focus_effect`
- `support_effect`
- `celebration_effect`

Recommended directory shape:

- `console/src/assets/buddy/base/*`
- `console/src/assets/buddy/parts/*`
- `console/src/assets/buddy/effects/*`
- `console/src/assets/buddy/forms/*`

### 11.3 Stage-To-Asset Mapping

Each evolution stage should map to a stable visual bundle:

1. `Seed Form`
   - minimal shell
   - lighter emotion range
   - fewer accessory slots

2. `Bonded Form`
   - one stable accessory slot opens
   - stronger eye expression set
   - clearer rarity ring

3. `Capable Form`
   - richer idle/focus variants
   - stronger support-mode effect
   - clearer experienced-partner feel

4. `Seasoned Form`
   - mature form silhouette
   - higher-detail parts
   - stronger celebration/recovery effects

5. `Signature Form`
   - strongest visual identity
   - richest expression/effect pack
   - visually obvious long-term bond status

### 11.4 Asset Rules

- evolution should primarily change silhouette, detail richness, and emotional readability
- rarity should be readable but should not dominate companionship warmth
- visual upgrades should feel like partner growth, not loot unlock spam

---

## 12. Backend Objects And API Mapping

The Buddy design should not stay at the level of front-end flavor.

It needs explicit backend landing points.

### 12.1 Recommended Formal Projection Objects

The first implementation should introduce two explicit projection/read-model objects:

1. `BuddyPresentation`
   - buddy_name
   - lifecycle_state
   - presence_state
   - mood_state
   - current_form
   - rarity
   - small_sprite_ref
   - expanded_sprite_ref
   - active_effect_refs
   - current_support_prompt
   - current_goal_summary
   - current_task_summary
   - why_now_summary

2. `BuddyGrowthProjection`
   - intimacy
   - affinity
   - growth_level
   - companion_experience
   - knowledge_value
   - skill_value
   - pleasant_interaction_score
   - communication_count
   - completed_support_runs
   - completed_assisted_closures
   - evolution_stage
   - progress_to_next_stage

These should be projections, not canonical truth records.

### 12.2 Source Mapping

Recommended source-of-truth mapping:

- `HumanProfile`
  -> onboarding identity answers
- `GrowthTarget`
  -> confirmed primary direction + final-goal framing
- `CurrentFocus`
  -> current task + why-now explanation + blockers
- `CompanionRelationship`
  -> relationship preferences and stable accompaniment patterns
- `Assignment / AgentReport / runtime interaction history`
  -> support counts, completion counts, support effectiveness, continuity signals

### 12.3 Frontend Surface Mapping

Recommended first-version frontend consumers:

1. `Chat page`
   - consume `BuddyPresentation`
   - consume summary portions of `BuddyGrowthProjection`
   - show small companion + expanded buddy sheet

2. `Main-brain cockpit`
   - consume `final goal + current task + why now`
   - consume a compact Buddy growth summary rather than the full panel

3. `Onboarding flow`
   - create/confirm `HumanProfile`
   - create/confirm `GrowthTarget`
   - initialize `CompanionRelationship`
   - initialize Buddy projection state after naming

### 12.4 API Guidance

The first implementation should avoid scattering Buddy reads across many endpoints.

Recommended API shape:

- onboarding endpoints for:
  - basic identity submit
  - collaboration contract submit/start
  - direction transition preview
  - candidate-direction resolution
  - primary-direction confirmation
- Buddy read surface:
  - `chat buddy surface`
  - `main-brain buddy cockpit summary`
- Buddy mutation surface:
  - first-chat naming
  - future controlled rename flow

The Buddy front-end should not be forced to reconstruct itself by calling unrelated industry/bootstrap endpoints.

---

## 13. Migration Cutover From Old First Entry

The old first-entry flow is still industry/bootstrap-first.

This is not compatible with the Buddy design.

### 13.1 Current Old Entry

Current old entry centers on:

- `IndustryPreviewRequest`
- `industry-profile-v1`
- industry/company/product/customer/goals bootstrap thinking

This should no longer be the first emotional or product entry for humans.

### 13.2 Cutover Rule

The cutover should become:

- human onboarding first
- collaboration contract compile second
- main direction confirmation third
- industry/team/execution scaffolding afterward

This is a cutover of first-entry ownership and front-stage expression, not a rewrite of the entire runtime.

Existing runtime truth that already works should be reused wherever possible.

### 13.3 Migration Table

Recommended cutover mapping:

1. `old industry form`
   -> replaced as first-entry human onboarding surface

2. `industry/company/product/target_customers/goals`
   -> no longer first-screen required fields for ordinary human entry

3. `industry bootstrap preview`
   -> retained only as downstream execution/business scaffold generator when needed

4. `experience_mode`
   -> may survive only if it meaningfully maps to Buddy/planning guidance mode

### 13.4 Compatibility Guidance

Migration should allow a short compatibility window, but with strict boundaries:

- old industry-first flow may remain temporarily for legacy operator/business routes
- new human-first Buddy onboarding must become the default first entry
- no long-term dual-first-entry truth should remain
- existing human-assist/task truth may remain backstage and canonical during the transition
- what must change is the front-stage human interaction contract, which should become Buddy/chat-first

### 13.5 Required Migration Tests

The implementation plan should include explicit tests for:

- first entry now landing on human/Buddy onboarding rather than industry bootstrap
- collaboration contract compile replacing clarification turns
- candidate directions returning 2-3 options
- exactly one primary direction being confirmed
- Buddy naming happening inside first real chat
- old clarify routes returning `404`
- old industry bootstrap not silently reclaiming primary-entry status

---

## 14. Non-Goals

This Buddy round should not:

- create a second main-brain object model
- create a second memory database
- turn CoPaw into a pet game
- let specialist seats become competing front-stage personas
- expose full internal planning trees by default
- replace formal runtime truth with config-only presentation state

---

## 15. Recommended Landing Sequence

### Phase 1: Buddy Onboarding Replacement

- replace the old first-entry mentality with human identity + collaboration-contract onboarding
- collect the basic human profile
- add the fixed collaboration contract form plus contract compile
- converge to candidate directions and one confirmed primary direction
- land first-chat Buddy naming

### Phase 2: Chat-First Buddy Surface

- make chat the primary Buddy home
- add the small companion presence
- add click-to-expand companion panel
- land first-version visual shell and base attributes

### Phase 3: Buddy Attribute Projection

- project visible growth/game stats from formal truth
- land intimacy / affinity / level / knowledge / skill / communication metrics
- keep all of them as derived projections, not a second truth store

### Phase 4: Buddy Evolution

- land visual evolution and expression evolution
- connect growth to relationship, cognition, execution, and support effectiveness

### Phase 5: Main-Brain Cockpit Alignment

- align the main-brain page as Buddy's cockpit
- keep it centered on final goal, current task, and continuity review

### Phase 6: Buddy State And Evolution Calibration

- land first-version lifecycle/presence/mood state transitions
- calibrate visible attribute derivation rules
- land first-version evolution stage mapping
- ensure visual and expression evolution remain derived from formal truth rather than free-floating game state

---

## 16. Acceptance Standard

This design is only considered properly landed if the following are true:

- Buddy is the main brain's only front-stage personality shell
- the first-entry flow forms the human identity before team/execution bootstrap takes over
- Buddy onboarding converges through the collaboration contract compile flow
- the human confirms exactly one primary direction
- Buddy is named inside the first real chat relationship flow
- Buddy does not create a second truth source
- chat is the primary companionship surface
- the human default view is still final goal + current task
- specialist seats remain backstage workers
- Buddy visually and behaviorally evolves over time
- visible growth values come from formal runtime/interaction truth rather than arbitrary game-only state

If any of those are false, the result has likely fallen back into either:

- decorative pet mode
- parallel persona mode
- or second-truth-source mode
