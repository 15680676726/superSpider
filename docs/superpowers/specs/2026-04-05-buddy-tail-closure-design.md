# Buddy Tail Closure Design

## Goal

Close the last product-logic gaps in the Buddy-first chain so the system behaves like one coherent companion runtime:

- Buddy remains the only front-stage guide
- the human only sees the step they personally need to do now
- system-side execution stays backstage
- Industry becomes a current execution-carrier editor, not a second onboarding center

This design is a focused closure pass on top of the existing Buddy rollout. It does not replace the broader Buddy companion design.

---

## Confirmed Remaining Gaps

### 1. Current Buddy carrier can still be deleted into an orphan state

Right now the front-end still allows deleting the active `buddy:{profile_id}` execution carrier. Once deleted, the Buddy profile still exists, but there is no guaranteed product path that regenerates the carrier automatically. That leaves the system in a half-alive state:

- Buddy profile exists
- chat can still open
- current execution carrier is gone

This is not acceptable as a steady-state product behavior.

### 2. Buddy can expose system work as if it were the human's next step

The current Buddy focus resolver prefers assignment/backlog summaries from the execution carrier. That means Buddy may tell the human to do work that is actually a system-side execution item rather than a human-assist checkpoint.

This violates the current product rule:

- the system should do most of the work
- the human should only see the small part the system cannot do for them

### 3. Strong support growth is modeled but not truly driven by the formal chat chain

The relationship model includes `strong_pull_count`, but the formal chat path does not currently produce a real strong-support signal that increments it. This leaves the growth model partially decorative.

### 4. Direction confirmation does not visibly close the loop

After the user confirms the primary direction, the backend already generates the execution carrier and initial scaffold. But the frontend immediately jumps into chat, so the human does not see that the system actually completed:

- direction confirmation
- carrier creation
- initial scaffold generation

### 5. Industry is no longer the first entry, but still speaks in old bootstrap language

The top-level entry ownership has moved away from Industry, but the adjustment flow still looks like the old industry bootstrap form. That keeps a second mental model alive:

- one flow says "Buddy identity first"
- another still feels like "create the industry/team again"

The result is product drift rather than a clean hard cut.

---

## Product Rules For The Closure Pass

### Rule 1: Buddy and current carrier must not be separable by accident

The current Buddy-bound execution carrier is not a disposable list item. It is part of the live product chain.

Therefore:

- the active Buddy carrier must not be deletable from the normal Industry UI
- destructive reset must only happen through a dedicated future reset flow, not through normal carrier deletion

### Rule 2: Buddy's default "current task" is human-only

Buddy should first try to answer:

- what the human personally needs to do now

Only when no human-assist/current human checkpoint exists should Buddy fall back to a system-generated smallest-next-step summary.

Buddy must not present a backstage system assignment as if it were the human's required action unless that assignment has already been converted into a human-assist obligation.

### Rule 3: Strong support must be a formal runtime signal

Strong support is not just a tone label. It must be driven by explicit runtime/chat evidence, such as:

- the human saying they are stuck
- the human saying they do not want to do the task
- the human drifting into avoidance
- the system explicitly entering pull-back / rebuild-next-step mode

### Rule 4: Direction confirmation needs a visible completion state

The user must see a short but explicit completion step after direction confirmation:

- primary direction confirmed
- current execution carrier generated
- initial scaffold generated

Only after that should the flow move into chat naming / chat-first companionship.

### Rule 5: Industry becomes a carrier editor, not a second identity creator

Industry should only manage the current execution carrier and its operating constraints.

It should not feel like:

- creating identity again
- creating direction again
- recreating team genesis from scratch

Its language and fields should be narrowed to:

- current carrier summary
- current constraints
- operator guidance / preferences
- supporting materials
- execution adjustment inputs

---

## Proposed Closure Design

## 1. Protect The Active Buddy Carrier

The active carrier `buddy:{profile_id}` becomes protected in the normal Industry UI.

Closure behavior:

- show it normally
- allow editing it
- block deletion in normal UI
- explain that this is the current live execution carrier for the companion

No compatibility behavior is needed because the product is still pre-launch and test data has already been cleared.

## 2. Split Human Step From System Step In Buddy Projection

Buddy projection should resolve human-facing task state in this order:

1. active human-assist task for the bound profile
2. explicit current human checkpoint if later introduced
3. fallback minimal step derived from current carrier focus

This gives Buddy two distinct internal concepts:

- `human_current_task`
- `system_current_focus`

But only the human-facing one should drive the default front-stage Buddy summary.

The fallback still matters, because Buddy should not go blank when no human step is currently pending.

## 3. Formalize Strong-Support Triggers

The relationship/growth layer should increment strong support only when the runtime has evidence of actual pull-back behavior.

First-version trigger families:

- interaction text indicates stuck/avoidance/refusal
- interaction mode explicitly marks pull-back/rebuild
- future support actions from chat companion quick actions

This keeps growth grounded in formal interaction truth rather than ad-hoc UI-only counters.

## 4. Add A Short Completion Screen After Direction Confirmation

Direction confirmation should no longer jump straight into chat.

Instead:

1. confirm direction
2. receive `execution_carrier`
3. render a short completion state
4. continue to chat naming

The completion state should stay lightweight. It is not a dashboard. It only proves the loop has actually closed.

Recommended visible items:

- confirmed primary direction
- current carrier label
- first cycle/scaffold generated
- CTA: enter chat and name your companion

## 5. Reframe Industry As Carrier Adjustment

Industry should keep its runtime/detail value, but its edit surface must stop pretending to be first-time bootstrap.

First closure pass:

- rename edit copy to carrier-adjustment language
- remove or hide legacy bootstrap-only fields that do not fit personal companion execution
- keep only fields that genuinely adjust current carrier execution

This is a semantic hard cut, not a full Industry rewrite.

---

## Data/Behavior Impact

### Backend impact

- carrier deletion rules become profile-aware
- Buddy projection changes task-priority ordering
- interaction recording gains formal strong-support detection

### Frontend impact

- onboarding gets one extra completion state
- Industry loses the last traces of second-onboarding semantics
- current carrier deletion action is suppressed or blocked when it is the active Buddy carrier

### Runtime impact

- Buddy chat becomes more accurate about what the human should do
- growth signals become more trustworthy
- the product no longer allows an easy Buddy/carrier split-brain state

---

## Non-Goals

This closure pass does not:

- redesign the whole Buddy system
- redesign Runtime Center
- create a full reset-account lifecycle
- replace the entire Industry runtime surface

It only closes the remaining product-logic tails that still make the experience feel inconsistent.

---

## Acceptance

This closure pass is only considered complete if all of the following are true:

- the active Buddy execution carrier cannot be deleted from the normal Industry UI
- Buddy's default current task is the human's task, not the system's backstage task
- strong support growth increments through the formal chat/runtime path
- confirming the primary direction visibly shows that the carrier/scaffold was created
- Industry no longer reads like a second first-entry bootstrap surface

If any of those remain false, the Buddy-first chain is still not fully closed.
