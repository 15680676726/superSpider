# Buddy Stage Points And Gating Design

Date: `2026-04-08`

## Goal

Replace the current Buddy stage progression from a structure-heavy capability-score curve to a simpler, harder-to-cheat points model:

- points come from real closed-loop work
- stage upgrades require both points and gate conditions
- stage downgrade is allowed, but only one level at a time

The product goal is to stop Buddy from feeling like it can jump from early-stage growth to high stage too quickly just because bootstrap scaffolding exists.

---

## Current Problem

The current stage model already reads formal runtime truth, but its early-stage pacing is too loose:

- onboarding bootstrap immediately creates lane/backlog/cycle/assignment structure
- that structure already contributes a large `strategy_score`
- the first few completed actions can push Buddy through early stages too quickly

So the current model is truthful enough for a V1 runtime signal, but not strict enough for a Digimon-like long-term progression fantasy.

---

## Design Choice

Use:

- `points + promotion gates + one-level demotion`

Do not use:

- task difficulty grading
- per-agent scoring
- per-subtask scoring
- hidden weighted formulas as the primary stage rule

Rationale:

- the user-facing rule stays easy to explain
- the backend still has formal gates, so the system cannot be trivially farmed
- the model stays small enough for the current Buddy feature scope

---

## Formal Scoring Unit

The formal scoring unit is:

- `1` real task closure = `2` points

For this feature, "real task closure" should map to:

- one formally settled `Assignment`
- with a completed result
- with a `report`
- and with at least minimal `evidence`

Not counted separately:

- chat turns
- internal child tasks
- number of participating agents
- raw tool calls

If multiple agents collaborate on one assignment and that assignment closes successfully, Buddy still earns only one closure's points.

---

## Stage Thresholds

Canonical stage thresholds:

- `seed` / `幼年期`: `0-18` points
- `bonded` / `成长期`: `20-38` points
- `capable` / `成熟期`: `40-98` points
- `seasoned` / `完全体`: `100-198` points
- `signature` / `究极体`: `200+` points

Equivalent closure counts:

- `成长期`: `10` closures
- `成熟期`: `20` closures
- `完全体`: `50` closures
- `究极体`: `100+` closures

---

## Promotion Gates

Points alone are not enough. Promotion requires both the threshold and the gate.

### `幼年期 -> 成长期`

Requirement:

- reach `20` points

No extra gate beyond valid scoring truth.

### `成长期 -> 成熟期`

Requirement:

- reach `40` points
- have at least `1` real closed loop

Meaning:

- Buddy has moved beyond setup and produced at least one real completion.

### `成熟期 -> 完全体`

Requirement:

- reach `100` points
- show stable progress across at least `3` distinct settled cycles

Meaning:

- Buddy is not just closing isolated work
- it can sustain execution across time instead of spiking once

### `完全体 -> 究极体`

Requirement:

- reach `200` points
- have at least `10` independent成果
- recent `30` settled assignments completion rate `>= 92%`
- recent `30` settled assignments execution error rate `<= 3%`

Meaning:

- Buddy is no longer just productive
- it is independently reliable, low-error, and repeatably useful

---

## Metric Definitions

### Independent成果

Count only outputs that:

- are tied to formal closed-loop work
- have result + report + evidence
- are reusable, operator-visible, or outcome-bearing

Examples:

- reusable document/result artifact
- visible strategy/result output
- a completed work product that can be referred to later

Do not count:

- empty completion shells
- duplicate low-value outputs
- internal execution noise

### Completion Rate

Window:

- recent `30` settled assignments

Formula:

- `completed / settled`

### Execution Error Rate

Window:

- recent `30` settled assignments

Formula:

- assignments ending in system-execution failure / settled

This should capture actual execution failure rather than business rejection or scope change.

---

## Demotion Rule

Demotion is allowed, but heavily constrained.

Rules:

- only one level can be lost at a time
- no chained multi-level drop in one evaluation
- downgrade should only happen when the current stage's maintenance condition is no longer met

Recommended maintenance behavior:

- `成长期` maintenance: keep accumulating valid closures; otherwise remain stable
- `成熟期` maintenance: must still show real closure activity
- `完全体` maintenance: must still show cross-cycle stable progress
- `究极体` maintenance: must continue to satisfy the reliability bar approximately, not just the lifetime points bar

Recommended downgrade trigger:

- evaluate on formal cycle/report settlement points
- if current-stage maintenance fails over the recent evaluation window, drop one level

This keeps progression hard but avoids chaotic stage flicker.

---

## Runtime Update Rule

### Points

Update when:

- a valid real closure is settled

### Stage

Promotion check:

- when a new valid closure settles

Demotion check:

- on formal cycle/report settlement evaluation

This keeps the scoring simple while making downgrades deliberate rather than noisy.

---

## Data Model Direction

Keep `BuddyDomainCapabilityRecord` as the single truth object for domain-stage state.

Recommended additions:

- `capability_points`
- `settled_closure_count`
- `independent_outcome_count`
- `recent_completion_rate`
- `recent_execution_error_rate`
- `distinct_settled_cycle_count`
- optional stage-evaluation metadata for downgrade guardrails

The old `capability_score` can remain temporarily as:

- compatibility/read-model metadata
- secondary analytics signal

But it should no longer be the canonical stage promotion rule once this design lands.

---

## Product Contract

User-facing explanation should become:

- every real closed loop gives Buddy `2` points
- higher stages require both enough points and proof of stronger capability
- late stages are about stability, reliability, and reusable output, not just raw task count

This keeps the progression understandable without exposing internal runtime complexity.

---

## Non-Goals

This design does not introduce:

- task difficulty scoring
- manual operator difficulty review
- per-agent growth contribution weighting
- a second parallel Buddy growth truth source

---

## Recommendation

Adopt this design as the next Buddy stage progression rule.

It is simpler than the current composite scoring model, stricter in pacing, and much closer to the intended product fantasy:

- early growth is slower
- mid growth requires proven closed loops
- late growth requires long-run execution quality
