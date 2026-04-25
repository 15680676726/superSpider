# CoPaw Native Fixed SOP Kernel and n8n Retirement Spec

## 1. Positioning

This document records a hard-cut architecture decision:

> `n8n`, external workflow hubs, and community workflow import are no longer part of CoPaw's target architecture. Fixed SOP must move inside CoPaw as a native minimal kernel.

This spec supplements, and does not replace:

- `AGENTS.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`

It must not create a second main chain. The formal operator write truth remains:

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

## 1.1 Relationship to the Other Three Documents

This document defines the automation-side hard cut, not the execution runtime.

Division of responsibility:

- this spec decides that `n8n / Workflow Hub` is retired and fixed SOP becomes native
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md` decides how browser/desktop/document execution works
- the two matching plan files define the actual build order

This spec must not silently absorb body-runtime responsibilities, and the body-runtime spec must not silently recreate a workflow-hub product.

## 2. Why `n8n` Must Be Retired

The old `n8n SOP Adapter / Workflow Hub` route solved one narrow problem, but it now blocks the actual product goal.

Problems with keeping it:

- it keeps fixed SOP outside CoPaw's primary runtime truth
- it forces a webhook/callback mental model where CoPaw should own the run directly
- it adds duplicated frontend IA (`社区工作流`, `Workflow Hub`) that does not belong to a runtime-first product
- it encourages catalog import and adapter management when the actual need is a tiny set of internal low-judgment SOPs
- it makes recovery, evidence, and governance harder to keep on the same execution path as body-based computer work

The next-generation gap is not "we lack another external workflow tool". The gap is that CoPaw still needs to own its own runtime, body leases, recovery, verification, and low-judgment automation path end to end.

## 3. Architecture Decision

The new rule is:

- `Agent Body Grid` owns browser, desktop, file, and document operation
- `Native Fixed SOP Kernel` owns only low-judgment fixed automation segments
- role workflows decide when work stays flexible and when it can enter a fixed SOP segment
- evidence, recovery, governance, and report truth all remain inside CoPaw

The intended layering is:

`Assignment -> Role Workflow -> (Native Fixed SOP Kernel | Body Scheduler) -> Body Lease -> Routine/Operator -> Evidence/Report`

Interpretation:

- a role workflow can choose a fixed SOP segment for repetitive, low-judgment work
- API-only fixed SOP can run without a body lease
- UI-mutating fixed SOP must dispatch back into CoPaw body runtime through `routine_call` or `capability_call`

## 3.1 Execution Order Dependency

The hard-cut dependency is:

1. retire `n8n / Workflow Hub` as a target architecture choice
2. define the native fixed SOP kernel boundary
3. let execution/runtime work proceed without old SOP adapter ambiguity

This means the fixed-SOP hard cut must be decided before the project can honestly claim the runtime model is unified.

## 4. Boundary

### 4.1 Allowed Uses

The native kernel is allowed to do only these classes of work:

- webhook-triggered fixed flows
- schedule-triggered fixed flows using existing cron infrastructure
- API fan-out / callback wait / result normalization
- low-judgment condition routing
- deterministic writeback/report handoff into the main chain

### 4.2 Disallowed Uses

The native kernel must not:

- become a second workflow truth source
- own browser/desktop/document execution loops
- become a community template marketplace
- import arbitrary external workflow JSON as a first-class product path
- bypass CoPaw evidence, recovery, governance, or report backflow
- take over flexible cross-role business judgment

## 5. Minimal Node Set

V1 must stay intentionally small.

Allowed node types:

- `trigger`
- `guard`
- `http_request`
- `capability_call`
- `routine_call`
- `wait_callback`
- `writeback`

Rules:

- retry, timeout, and branching policy are node/edge policies, not new node families
- there is no arbitrary code node
- there is no visual-programming marketplace requirement
- there is no "import foreign workflow and clean it up later" path

## 6. Formal Object Mapping

This spec must not introduce an external second truth. Fixed SOP stays inside CoPaw state and workflow objects.

| Native fixed SOP language | Formal object mapping |
| --- | --- |
| `FixedSopTemplate` | workflow-layer template object; may initially live beside or specialize `WorkflowTemplateRecord` |
| `FixedSopBinding` | workflow-layer binding/governance object bound to an industry/owner/runtime context |
| `FixedSopRun` | run anchor linked to workflow/runtime/evidence/report chain |
| `FixedSopNodeTrace` | execution trace embedded in `FixedSopRun` state and `EvidenceRecord`, not a second run-history system |

Canonical truth still stays in:

- `WorkflowRunRecord`
- `ExecutionRoutineRecord`
- `RoutineRunRecord`
- `EvidenceRecord`
- `DecisionRequest`
- `AgentReportRecord`

## 7. Backend and Frontend Retirement Scope

The following surfaces are planned retirement set and should not survive the hard cut.

Backend:

- `src/copaw/app/routers/sop_adapters.py`
- `src/copaw/sop_adapters/`
- `POST /api/sop-callbacks/n8n/{binding_id}`
- `ensure_n8n_template_catalog_sync_job(...)`
- `n8n`-tagged system capability wiring and callback handlers

Frontend:

- `console/src/api/modules/sopAdapters.ts`
- `console/src/pages/WorkflowTemplates/`
- `console/src/layouts/Sidebar.tsx` entry `社区工作流（n8n）`
- `console/src/layouts/Header.tsx` key `workflow-hub`
- retired frontend IA entry `Capability Market -> 工作流`
- any `n8n webhook` form, community template sync, or import-preview UI

Historical docs:

- `docs/archive/retired-architecture/N8N_SOP_ADAPTER_WORKFLOW_HUB_PLAN.md` remains only as a historical ledger

## 8. Target Product Surface

There should be no separate workflow-hub product after the cut.

The minimal operator surface is:

- `Runtime Center -> Automation -> Fixed SOP`

That surface only needs to expose:

- curated builtin fixed SOP templates
- bindings to runtime/industry/owner context
- latest run status
- evidence/report links
- guarded manual run when allowed

## 9. Migration Order

1. Freeze the decision in docs and status: `n8n` is retired.
2. Introduce native fixed SOP kernel objects and builtin template definitions.
3. Rewire workflow/learning/industry/runtime integrations to the native kernel.
4. Delete backend `sop_adapters` and `n8n` callback/catalog code.
5. Delete frontend workflow-hub surfaces and move the minimal SOP UI into `Runtime Center -> Automation`.
6. Verify that every remaining fixed SOP either stays API-only or dispatches UI work through body runtime.

## 10. Relation to Computer-Use Competitiveness

What is obsolete is the current implementation shape, not the upgrade direction.

The outdated parts are:

- tool-first success semantics
- external SOP sidecars
- duplicated product surfaces for automation vs runtime

The correct modernization path is:

- body-owned execution
- observe/act/verify/recover loops
- native fixed SOP for low-judgment automation
- single evidence/recovery/governance path

That is the path that moves CoPaw toward a real computer-use system instead of a glue layer around old tools.
