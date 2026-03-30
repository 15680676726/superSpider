# Autonomy Terminal-State Program

## Summary

This program turns the current autonomy baseline into a terminal-state product shape. The key change in operating model is to stop treating "done for this repo slice" and "future maturity expansion" as the same thing. Each domain gets:

1. a hard "currently closed" boundary
2. a hard terminal-state standard
3. code, UI/read-surface, and verification that all use the same truth

The work is executed sequentially, not as one mixed patch set.

## Program Order

1. `Full Host Digital Twin`
2. `single-industry` real-world closure
3. main-brain cockpit / `Unified Runtime Chain`
4. wide regression and long-run `live smoke`

## Terminal-State Intent

### 1. Full Host Digital Twin

The system must use one canonical host truth for seat ownership, selected session, handoff, recovery, resume, and host switch. `workflow`, `cron`, `fixed-SOP`, `Runtime Center`, and industry runtime must all consume the same host contract. Browser, desktop, and document execution positions must all be first-class host-aware surfaces rather than side channels.

### 2. single-industry real-world closure

A single industry instance must run for multiple cycles without silently dropping runtime truth. `staffing + handoff + human assist + report + synthesis + replan` must behave like one long-running execution loop, not separate demos.

### 3. Main-brain cockpit

The frontend must become a real cockpit, not a detail reader. `carrier / strategy / lane / cycle / assignment / report / environment / evidence / decision / patch` must all be visible and related inside one runtime center, and operators must be able to follow the runtime truth directly from the UI.

### 4. Wide regression and live smoke

The final product state must be proven by wide regression and longer-running smoke. Recovery points, reentry, host switch, handoff, scheduling recovery, evidence replay, and continuity across multiple execution surfaces must be repeatedly verifiable.

## Execution Strategy

The terminal-state program is decomposed into one sub-project per domain. Each sub-project must reach:

- test-first implementation of the missing behaviors
- fresh focused regressions
- a widened smoke proving the new closure
- updated status/docs only after the above are green

## First Approved Sub-Project

The first terminal-state slice is `Full Host Digital Twin`.

Current baseline:

- canonical selected seat/session already exists
- workflow/cron/fixed-SOP already prefer canonical selected seat/session
- host-switch smoke already exists for desktop/browser-oriented flows

Still-missing terminal-state behavior to close next:

- explicit `document` execution surface is not yet a first-class host-aware consumer in workflow/fixed-SOP
- host-aware smoke is still short-run; it does not yet prove longer continuity across document-aware execution

That first sub-project becomes the immediate implementation plan.
