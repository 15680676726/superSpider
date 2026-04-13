## 2026-04-10 Human Assist Strip Simplification

### Background
The current chat-page human-assist panel presents a workbench-style strip with two actions, a dense summary, and a modal that surfaces the same content again. The request is to make the primary chat view feel lighter and not like a dedicated workbench while keeping the detailed information accessible on demand.

### Goals
- Reduce the first-screen presence of the human-assist panel to a single reminder of the active task.
- Surface only a concise summary paired with one primary action that opens the existing detail modal.
- Keep the current modal and loading logic intact so we do not touch `Chat/index.tsx`, `ChatAccessGate.tsx`, or routing while still meeting the \"detail deferred\" requirement.

### Design
- **Strip appearance**: When an active human-assist task exists, keep the strip rendered but limit its content to:
  - The task title (or a fallback label) as a short prompt.
  - The human-assist status badge.
  - The task summary truncated via CSS, kept as descriptive hover text.
  - One primary `Button` labeled `查看记录` that simply opens the pre-existing modal.
- **Action behavior**: Clicking `查看记录` sets `taskListOpen` and reuses `loadTaskList`/`loadTaskDetail` as before. There is no inline \"我已经完成\" action in the strip anymore — the detailed modal still exposes additional context and metadata.
- **Modal**: No changes to the modal content; it continues to show the task list, details, and tags when opened.

### Data flow and lift
- `threadMeta.human_assist_task` seeds the strip as before; live refreshes still happen on focus and `copaw:human-assist-dirty`.
- `resolveHumanAssistStatusPresentation` remains to translate status codes for the badge.
- The only component-level change is removing the secondary button and leftover `armHumanAssistSubmission` logic so the strip consistently renders a single alert + action.

### Testing
- Update the existing `ChatHumanAssistPanel.test.tsx` expectations to reflect the new strip (no longer asserting the \"arm next message\" button or queue transport call).
- Keep coverage for: strip visibility when there is/there is not an active task, modal loading, and status label mapping.

### Out of scope
- No new routes, detail panels, or experience rewrites beyond the strip reduction.
