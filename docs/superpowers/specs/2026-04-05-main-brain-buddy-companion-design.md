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
- results flow back through the main brain
- Buddy speaks to the human about those results
- the source seat may be labeled, but should not take over the front-stage voice

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

---

## 8. Onboarding And Identity Formation

The current first-entry flow must not remain the old industry bootstrap mindset.

The new first-entry flow should become:

> human identity formation -> Buddy clarification -> direction confirmation -> Buddy birth -> first chat naming

### 8.1 Core Judgment

The human's first psychological entry into CoPaw should no longer be:

- create an industry first
- create a team first
- fill a business bootstrap form first

It should instead be:

- establish who the human is
- understand where the human is in life/work
- clarify what kind of larger direction is actually desired
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

### 8.3 Step Two: Buddy Clarification Dialogue

After the basic form, the system should not immediately produce a plan.

It should enter a Buddy-led clarification dialogue.

Hard rules:

- maximum of `9` questions
- if direction is still unclear after `5`, switch to tighter follow-up mode
- the system must not stay suspended forever waiting for perfect clarity
- the system must still converge to a usable first result

This clarification may borrow from psychology-informed growth coaching or motivation clarification, but must not become:

- therapy
- diagnosis
- clinical labeling

Its role is:

- direction clarification
- motive clarification
- blocker discovery
- value prioritization
- realistic first-step discovery

### 8.4 Step Three: Candidate Directions And One Primary Direction

After clarification, Buddy may present:

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

This prevents the system from degrading into endless clarification.

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

## 10. Non-Goals

This Buddy round should not:

- create a second main-brain object model
- create a second memory database
- turn CoPaw into a pet game
- let specialist seats become competing front-stage personas
- expose full internal planning trees by default
- replace formal runtime truth with config-only presentation state

---

## 11. Recommended Landing Sequence

### Phase 1: Buddy Onboarding Replacement

- replace the old first-entry mentality with human identity + clarification onboarding
- collect the basic human profile
- add Buddy clarification dialogue with the 9-question cap
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

---

## 12. Acceptance Standard

This design is only considered properly landed if the following are true:

- Buddy is the main brain's only front-stage personality shell
- the first-entry flow forms the human identity before team/execution bootstrap takes over
- Buddy clarification converges within the capped question flow
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
