# Buddy Stage Label Mapping Implementation Plan

> Superseded on `2026-04-07` by the capability-based Buddy domain-stage design. This plan described a UI-only relabeling path and should not be used for implementation.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Buddy's human-facing stage labels with `幼年期 / 成长期 / 成熟期 / 完全体 / 究极体` and rename the Buddy panel copy from `当前形态` to `当前阶段` without changing backend enums.

**Architecture:** Keep `growth.evolution_stage` and `presentation.current_form` as the existing truth/model fields. Route all UI changes through the shared presenter in `console/src/pages/Chat/buddyPresentation.ts` so Chat and Runtime Center stay aligned, then update the Buddy panel copy to match the new stage mental model.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, Testing Library

---

## File Structure

- `console/src/pages/Chat/buddyPresentation.ts`
  Responsibility: shared Buddy label presenter for stage, presence, mood, and display snapshot text.
- `console/src/pages/Chat/buddyPresentation.test.ts`
  Responsibility: unit coverage for stage label mapping, compact status line, and snapshot fallbacks.
- `console/src/pages/Chat/BuddyPanel.tsx`
  Responsibility: Buddy detail panel copy for the stage presentation row.
- `console/src/pages/Chat/BuddyPanel.test.tsx`
  Responsibility: UI coverage for the Buddy panel relationship and stage-facing copy.
- `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
  Responsibility: consumes the shared stage presenter indirectly; verify no direct copy change needed.

### Task 1: Update Shared Buddy Stage Labels

**Files:**
- Modify: `console/src/pages/Chat/buddyPresentation.ts`
- Modify: `console/src/pages/Chat/buddyPresentation.test.ts`
- Verify consumer: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`

- [ ] **Step 1: Write the failing test**

```ts
it("maps buddy stages into Digimon-style labels", () => {
  expect(presentBuddyStageLabel("seed")).toBe("幼年期");
  expect(presentBuddyStageLabel("bonded")).toBe("成长期");
  expect(presentBuddyStageLabel("capable")).toBe("成熟期");
  expect(presentBuddyStageLabel("seasoned")).toBe("完全体");
  expect(presentBuddyStageLabel("signature")).toBe("究极体");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console run test -- src/pages/Chat/buddyPresentation.test.ts`

Expected: FAIL because the old labels still return `初生 / 结伴 / 得力 / 成熟 / 标志形态`.

- [ ] **Step 3: Write minimal implementation**

```ts
export function presentBuddyStageLabel(stage?: string | null): string {
  switch ((stage || "").trim()) {
    case "seed":
      return "幼年期";
    case "bonded":
      return "成长期";
    case "capable":
      return "成熟期";
    case "seasoned":
      return "完全体";
    case "signature":
      return "究极体";
    default:
      return "成长中";
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix console run test -- src/pages/Chat/buddyPresentation.test.ts`

Expected: PASS, including the compact status line and snapshot fallback expectations updated to the new labels.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Chat/buddyPresentation.ts console/src/pages/Chat/buddyPresentation.test.ts
git commit -m "feat: relabel buddy stage presentation"
```

### Task 2: Rename Buddy Panel Copy To Current Stage

**Files:**
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
expect(screen.getByText(/当前阶段：/)).toBeInTheDocument();
expect(screen.queryByText(/当前形态：/)).not.toBeInTheDocument();
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console run test -- src/pages/Chat/BuddyPanel.test.tsx`

Expected: FAIL because the panel still renders `当前形态：`.

- [ ] **Step 3: Write minimal implementation**

```tsx
<Paragraph style={{ marginBottom: 0 }}>
  当前阶段：{snapshot.stageLabel}
  {" / "}
  {evolution?.rarityLabel ?? surface.presentation.rarity}
</Paragraph>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix console run test -- src/pages/Chat/BuddyPanel.test.tsx`

Expected: PASS with the new copy rendered.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Chat/BuddyPanel.tsx console/src/pages/Chat/BuddyPanel.test.tsx
git commit -m "feat: rename buddy panel stage copy"
```

### Task 3: Focused Frontend Verification

**Files:**
- Verify: `console/src/pages/Chat/buddyPresentation.test.ts`
- Verify: `console/src/pages/Chat/BuddyPanel.test.tsx`
- Verify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: Run the focused regression suite**

Run: `npm --prefix console run test -- src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

Expected: PASS with Runtime Center continuing to consume the new shared stage labels.

- [ ] **Step 2: Inspect for stray old labels**

Run: `rg -n "初生|结伴|得力|标志形态|当前形态" console/src/pages/Chat console/src/pages/RuntimeCenter`

Expected: no remaining user-facing hits for the retired stage labels in the touched surfaces, aside from unrelated historical tests or fixtures if any.

- [ ] **Step 3: Commit**

```bash
git add console/src/pages/Chat/buddyPresentation.ts console/src/pages/Chat/buddyPresentation.test.ts console/src/pages/Chat/BuddyPanel.tsx console/src/pages/Chat/BuddyPanel.test.tsx
git commit -m "test: verify buddy stage label mapping surfaces"
```
