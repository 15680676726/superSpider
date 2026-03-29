# Industry runtime cockpit cleanup

## Summary
Industry currently renders a legacy “detail mode” branch after the runtime cockpit. This branch is dead code, introduces TypeScript/wiring drift, and holds onto the old “goal-centric” detail surface that the Runtime Center and main industry page have already replaced. The build is blocked because the JSX ternary still contains `true ? … : …` for the cockpit branch. We will remove the legacy branch entirely so the page always renders the runtime cockpit surface and keep the helper/tests in sync.

## Constraints
1. Only the files listed in the ownership note may change.
2. The runtime cockpit must be the single visible surface when an industry detail exists; we cannot fall back to the legacy detail summary.
3. Any TypeScript nullability issues introduced by dropping the branch must be addressed.
4. Existing (but uncommitted) test fixes in the same files must remain usable after the refactor.

## Approaches
1. **Replace the ternary with a single `IndustryRuntimeCockpitPanel` render** (preferred). Drop the unused legacy UI entirely, rely on the shared `IndustryRuntimeCockpitPanel`, and ensure props are non-null before passing down. This eliminates the misleading `true ? … : …` branch and keeps the runtime cockpit as the canonical surface.
2. **Keep the legacy branch but guard it behind an explicit “detail mode” flag**. This keeps the old UI for debugging but still renders the runtime cockpit when the flag is off. Tests would need to explicitly toggle the flag. This increases surface area and keeps the dead code around.
3. **Move the legacy detail UI into a separate component and only render it when an explicit “show legacy” prop is true**. This modularizes the branch, but also preserves the legacy surface and the additional tests/props, so the build blocker might survive.

Recommendation: Option 1. The legacy surface is no longer part of the product; removing the branch avoids TypeScript noise and aligns with the runtime cockpit as the single entry point.

## Design
- Update `console/src/pages/Industry/index.tsx` so the ternary that renders the page now resolves to:
  - Loading spinner when `loadingDetail`.
  - Empty hint when no `detail`.
  - Direct `IndustryRuntimeCockpitPanel` render when a detail exists.
  - Remove the legacy layout under the “true ? … : …” branch entirely.
- Because `IndustryRuntimeCockpitPanel` now owns the full interaction surface, ensure all props (`detail`, callbacks) are typed as required and passed through unchanged. There is no additional null check inside the render now.
- Adjust the tests (`console/src/pages/Industry/index.test.tsx`) to interact only with the runtime cockpit UI (Focusing backlog/assignments, staffing, runtime chain). Ensure they no longer depend on the removed detail section.
- Keep the temporary cloning of `IndustryRuntimeCockpitPanel` helpers such as `forever` (typo?). Ensure the runtime panel handles optional fields safely (existing code already covers this) so there are no new TypeScript null assertions.
- Retain the updated tests in `console/src/pages/Predictions/index.test.ts`, `console/src/pages/RuntimeCenter/AutomationTab.test.tsx`, `console/src/utils/runtimeChat.test.ts`, and `console/src/pages/Industry/pageHelpers.test.ts`—they already reflect the cleaned surfaces and should remain untouched except for any integration corrections required after the main removal.

## Testing
1. `npm run test -- console/src/pages/Industry/index.test.tsx console/src/pages/Industry/pageHelpers.test.ts`
2. `npm run test -- console/src/pages/Predictions/index.test.ts`
3. `npm run test -- console/src/pages/RuntimeCenter/AutomationTab.test.tsx`
4. `npm run test -- console/src/utils/runtimeChat.test.ts`

> After this doc is approved we can implement the cleanup and re-run the listed tests to verify the build passes.
