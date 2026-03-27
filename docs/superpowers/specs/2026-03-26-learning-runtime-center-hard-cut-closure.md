# Learning and Runtime Center Hard-Cut Closure Spec

## Goal

Close the remaining `P1-P3` hard-cut gap around the learning layer and the Runtime Center operator surface so the live system matches the new runtime-first architecture instead of carrying transitional god services.

## Scope

This spec covers three concrete closures only:

1. Split `src/copaw/learning/service.py` into a thin `LearningService` facade plus internal domain services.
2. Split `src/copaw/app/runtime_center/service.py` into a thin `RuntimeCenterQueryService` facade plus dedicated overview/card builders.
3. Thin the learning router/bootstrap wiring so app-layer code resolves a stable facade instead of re-embedding domain coupling everywhere.

## Non-Goals

- No new execution chain or truth source.
- No new public HTTP routes.
- No legacy migration for historical data.
- No broad feature expansion beyond the existing learning/runtime-center behavior.

## Architecture Decision

### 1. Learning layer

`LearningService` remains the only public app/runtime entry point, but it stops being the place where every proposal, patch, acquisition, onboarding, and growth flow lives directly.

The facade will own shared dependencies and runtime bindings, while internal services will own the domain logic:

- `LearningProposalService`
- `LearningPatchService`
- `LearningGrowthService`
- `LearningAcquisitionService`

Shared dependency/binding state must be explicit and reusable instead of spread through ad hoc setter side effects.

### 2. Runtime Center overview layer

`RuntimeCenterQueryService` remains the public query facade for `/runtime-center/overview`, but card construction and mapping logic move behind dedicated collaborators.

The overview surface must reflect the runtime-first operator chain. Transitional overview cards for `goals` and `schedules` are retired from the main overview payload.

The overview surface should focus on live operator domains such as:

- tasks
- work contexts
- routines
- industry
- agents
- predictions
- capabilities
- evidence
- governance
- decisions
- patches
- growth

### 3. App-layer thinning

The learning router should rely on a single resolver/helper boundary and avoid duplicating knowledge about internal learning structure.

Bootstrap wiring should set learning bindings through one explicit facade entry instead of continuing to grow setter sprawl as features expand.

## Expected Outcomes

- `LearningService` is no longer the direct implementation shell for every learning concern.
- `RuntimeCenterQueryService` becomes an orchestration facade instead of a giant card-construction container.
- Runtime Center overview stops presenting retired `goals` and `schedules` cards as first-class operator summary.
- Learning/router/bootstrap surfaces stay stable for callers while internal boundaries become clear.

## Acceptance Criteria

1. `src/copaw/learning/service.py` is materially smaller and delegates to internal domain services.
2. `src/copaw/app/runtime_center/service.py` is materially smaller and delegates to overview/card collaborators.
3. `/runtime-center/overview` no longer returns `goals` or `schedules` cards.
4. Existing learning and runtime-center API contracts continue to pass targeted regression tests.
5. `TASK_STATUS.md` records the hard-cut closure accurately.
