# 2026-04-10 Frontend Main Flow Reset Design

## Why This Exists

The current frontend feels slow, jumpy, and overcomplicated because the main user path is no longer simple:

- onboarding and chat responsibilities are mixed together
- the chat page does too many unrelated things
- the right fixed panel loads at the wrong times and can affect the main page
- route switches trigger extra work instead of just changing the visible page

This design resets the frontend back to a simple main flow:

- no profile: show onboarding
- profile exists: show chat
- the shell stays stable
- each area only does its own job

## Goals

1. Make the main user path obvious and stable.
2. Remove repeated jumps, repeated loading, and repeated form filling.
3. Make chat behave like a chat page, not a control center.
4. Keep the right fixed panel as a passive companion area.
5. Make page switching feel like changing pages, not restarting the app.

## Non-Goals

- Do not redesign the onboarding question content.
- Do not redesign the current right-panel content in this pass.
- Do not rebuild the entire frontend from scratch.

## Global Rules

The frontend should follow these rules everywhere:

- First entry loads the shell once.
- After that, left navigation and right fixed panel stay in place.
- Only the middle content area changes with the route.
- Clicking a page should only load that page and that page's data.
- A page must not trigger unrelated page work.
- A slow side area must not block the main page.
- A failed side area must not break the main page.

## Main Flow

The product should have one direct main flow:

- no profile -> onboarding
- profile exists -> chat

There should be no extra landing page, middle page, or transition page in front of that flow.

## Onboarding Page

The onboarding page keeps its current content, but the flow changes.

### Responsibilities

The onboarding page is only responsible for creating the profile correctly.

### Rules

- Keep the current onboarding content unchanged.
- Use 3 steps.
- Move buddy naming into step 3.
- Auto-save after each step.
- Allow the user to go back to earlier steps and edit.
- After step 3, show a `开始聊天` button.
- Clicking `开始聊天` should keep the user on the onboarding page while creation finishes.
- Only jump to chat after creation is truly successful.
- Do not force the user to refill completed content after refresh.
- Do not show duplicate modules or conflicting states.

### User Promise

The user fills it once, confirms once, and then enters chat cleanly.

## Chat Page

The chat page should return to being just a chat page.

### Responsibilities

- show message history
- send new messages
- show a simple progress line above the latest reply
- offer one `查看详情` entry

### Rules

- If the user has a profile, chat should open.
- The only normal reason not to open chat is that the user has not created the profile yet.
- Naming must not happen in chat anymore.
- Chat must not contain extra recommendation cards, extra blockers, or unrelated control logic.
- Chat should show its frame and message area immediately instead of blocking on unrelated work.

## Right Fixed Panel

The right fixed panel remains a viewing area, not a main work area.

### Rules

- Hide it before onboarding is completed.
- Once onboarding is completed, keep it visible across the app.
- Keep its current content for now.
- Let the main page render first.
- The panel may load later.
- If the panel fails, the main page still works.
- Refresh panel data every 5 minutes.
- Also allow refresh after the user sends a message or after a reply completes.
- Keep the existing avatar animation behavior.

## Route Switching And Loading

Route switching should feel like turning a page, not restarting the app.

### Rules

- Load the shell once.
- Keep left and right stable.
- Only replace the middle content area on route changes.
- Remove the current behavior where switching one page also prepares many unrelated pages.
- Each page should fetch only its own required data.
- Show the page frame first even if data is still loading.
- Avoid full-page blank flashes during route changes.

## Error Handling Rules

User-facing rules should be simple:

- no profile: go to onboarding
- profile exists: open chat
- a side panel problem must not break the main area
- internal partial states are system bugs, not user-facing states

This means the frontend should stop exposing internal half-finished states as if they were valid destinations.

## Delivery Order

This reset should be implemented in the following order:

1. Fix the onboarding -> chat main path.
2. Fix the right fixed panel timing and refresh behavior.
3. Remove route-level overloading and unnecessary preload behavior.
4. Clean up repeated judgments, repeated state branches, and leftover jump logic.

## Testing Focus

The key checks for this reset are:

- onboarding content survives refresh
- step back editing works
- naming happens in onboarding step 3
- `开始聊天` waits on the current page and only jumps after success
- chat opens directly after successful onboarding
- chat no longer asks for naming
- right fixed panel stays hidden before onboarding and visible after onboarding
- right fixed panel failure does not break the main area
- route switching only changes the middle content area
- switching one page no longer triggers whole-app preload behavior

## Expected Result

After this reset:

- the app has one clear front door
- onboarding is stable and finishable
- chat feels like chat again
- the right side is supportive, not disruptive
- page switching becomes simple and smooth
