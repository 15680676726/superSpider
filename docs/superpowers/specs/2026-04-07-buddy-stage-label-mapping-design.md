# Buddy Stage Label Mapping Design

> Superseded on `2026-04-07` by [2026-04-07-buddy-domain-capability-stage-design.md](/D:/word/copaw/docs/superpowers/specs/2026-04-07-buddy-domain-capability-stage-design.md). This document captured an earlier UI-only relabeling direction and is no longer the active design for Buddy stage semantics.

## 0. Purpose

This spec defines a UI-only relabeling for Buddy growth stages so the human-facing experience uses a Digimon-style progression vocabulary without changing the underlying runtime truth model.

The target is:

- keep `growth.evolution_stage` as the canonical internal field
- keep `presentation.current_form` unchanged as a presentation field
- replace the displayed Chinese stage labels with a clearer staged progression
- rename the Buddy panel copy from "当前形态" to "当前阶段" so the UI matches the new mental model

This spec does not introduce a new truth source and does not change backend enums.

---

## 1. Core Judgment

This request should be implemented as a presentation-layer mapping only.

It should not be implemented as:

- a backend enum migration
- a data model rename
- a truth-surface split between new and old stage semantics

Reason:

- the current backend model is stable enough to serve UI needs
- `presentation.current_form` currently resolves from `evolution_stage`
- changing internal enums would create broad churn with little product value for this request

---

## 2. Approved Mapping

The existing canonical internal stages remain:

- `seed`
- `bonded`
- `capable`
- `seasoned`
- `signature`

The approved human-facing label mapping becomes:

- `seed` -> `幼年期`
- `bonded` -> `成长期`
- `capable` -> `成熟期`
- `seasoned` -> `完全体`
- `signature` -> `究极体`

Unknown or empty values should continue to fall back to `成长中`.

---

## 3. UI Copy Adjustment

Where the Buddy surface currently says `当前形态`, it should be renamed to `当前阶段`.

This copy change is intentionally limited to the Buddy stage presentation context. It does not require renaming the backend `current_form` field in this round.

---

## 4. Scope

This round should update only the surfaces that already consume the shared Buddy stage presenter:

- Chat Buddy companion
- Chat Buddy panel
- Runtime Center Buddy summary
- tests that assert the old labels

The implementation should prefer changing the shared label presenter so all dependent surfaces stay aligned.

---

## 5. Out Of Scope

This round must not:

- rename `evolution_stage`
- rename `current_form`
- change Buddy growth thresholds
- change Buddy rarity labels
- change Buddy animation rules
- split stage and form into two independent concepts

Those can be revisited later if the product decides that stage and form should diverge.

---

## 6. Verification

Minimum verification for this change:

- unit tests for stage label mapping
- unit tests for any snapshot/status text using the mapped labels
- targeted frontend test run for Buddy presentation consumers

---

## 7. Files Expected To Change

Likely files:

- `console/src/pages/Chat/buddyPresentation.ts`
- `console/src/pages/Chat/BuddyPanel.tsx`
- `console/src/pages/Chat/buddyPresentation.test.ts`

Potential consumer verification:

- `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
