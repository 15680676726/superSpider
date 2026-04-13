# Critical Tracks Supported Scope Matrix

> **For agentic workers:** Use this matrix before claiming any of the four critical acceptance tracks are "fully closed". If a scenario falls outside the supported scope below, it does not count toward sign-off for the current track.

**Goal:** Define the honest supported-scope boundary for the four critical acceptance tracks so "full closure" means "full closure within the declared product contract", not "everything imaginable now works".

**Architecture:** This matrix sits under the system real acceptance checklist and the four-track acceptance script. It narrows what can be honestly signed off today and prevents code-strong slices from being overstated as universal platform guarantees.

**Tech Stack:** FastAPI backend, console frontend, Runtime Center, Industry, Chat, capability market, donor/runtime subsystem.

---

## 1. How To Read This Matrix

This matrix does not reduce the acceptance bar.

It clarifies what the current bar is allowed to cover.

A track may only be marked fully accepted when:

- the scenario is inside the supported scope below
- the matching acceptance script has been executed
- the evidence bundle is complete

If the scenario is outside scope, write:

- `out of current supported scope`

Do not write:

- `accepted anyway`
- `probably covered`
- `implicitly included`

---

## 2. Scope Matrix

| Track | What can be honestly signed today | Required front doors / read surfaces | Explicitly out of scope |
| --- | --- | --- | --- |
| Track D: Capability Install -> Real Use | Formal capability install/use within the currently supported donor contract. This includes market-backed skill path, GitHub Python project donor under the current `Python + GitHub + isolated-venv` contract, and formal runtime/service donor under the current runtime contract. Current live-verified examples include `project:black` and `runtime:openspace`. | Capability Market, Runtime Center capability surface, target seat/effective capability surface, real execution result surface | Arbitrary donor, arbitrary language, arbitrary build system, arbitrary repository layout, arbitrary protocol, universal typed action discovery from any random donor |
| Track H: Frontend Truth Consistency | Truth consistency across the current primary operator surfaces for one shared formal chain. Current acceptance scope is: Chat, Runtime Center, Industry, Agent Workbench, and the Buddy/RightPanel companion summary where relevant to the same chain. | Chat, Runtime Center, Industry, Agent Workbench, RightPanel/Buddy summary | Every page in the frontend, cosmetic wording uniformity across all UI, legacy hidden surfaces, historical routes already retired from the main IA |
| Track K: Temporal Grounding | Real runtime time grounding for the current operator-facing chain: chat front door, runtime-facing summaries, and schedule/workflow-facing summaries that consume the same formal runtime time basis. | Chat front door, Runtime Center summaries, schedule/workflow-facing summaries, any visible time-derived explanation surface | Every natural-language phrasing in every locale, every external channel integration, every downstream report surface not currently connected to the same grounded time basis |
| Track L: Failure Injection / Fail-Closed | Fail-closed verification for the five declared acceptance families in a safe acceptance environment: model timeout, tool/runtime failure, missing capability attachment, handoff/resume interruption, environment continuity break. | Chat, Runtime Center, relevant recovery/governance/read surfaces, formal evidence/report/recovery truth | Broad chaos testing, infra-wide outages, unrelated provider/network disasters, uncontrolled production-only failure modes without a safe injection path |

---

## 3. Track-by-Track Notes

### 3.1 Track D

What counts:

- install truth is durable
- target seat/runtime can truly use the capability
- next execution turn actually uses it

What does not count:

- "it appears in inventory"
- "it installed but no seat ever used it"
- "we think other donors like it will probably work"

### 3.2 Track H

What counts:

- the same formal chain tells the same story across the primary runtime surfaces

What does not count:

- one page looked correct in isolation
- unit tests exist for several pages but no one compared the same live chain
- the frontend feels better overall, so everything must now be consistent

### 3.3 Track K

What counts:

- real current date / weekday / Beijing time
- real relative-day interpretation
- same time basis after refresh/re-entry

What does not count:

- a time tool exists somewhere
- prompts include a date string somewhere
- one isolated test proved one append-only prompt path

### 3.4 Track L

What counts:

- injected failure is visible
- chain stops cleanly
- no fake success appears
- durable truth exists for replay/recovery

What does not count:

- internal exception happened but the operator never saw it
- a test failed somewhere but the acceptance path was never exercised
- "it probably would fail closed" without a recorded failure bundle

---

## 4. Final Rule

This matrix defines the largest honest claim allowed today.

If later product scope grows, update this matrix first.
Only then may the matching acceptance track claim a larger "full closure" surface.
