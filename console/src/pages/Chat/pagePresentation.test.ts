import { describe, expect, it } from "vitest";

import { resolveThreadRuntimePresentation } from "./pagePresentation";

describe("pagePresentation", () => {
  it("derives thread, focus, and writeback labels/hints for runtime header chips", () => {
    expect(
      resolveThreadRuntimePresentation({
        currentFocus: "Ship phase split",
        sessionKind: "industry-control-thread",
        threadMeta: {
          chat_writeback_target_match_signals: [{ id: "s-1" }, { id: "s-2" }],
          chat_writeback_target_role_name: "execution-core",
          current_focus_id: "backlog-42",
          current_focus_kind: "backlog-item",
          owner_scope: "industry",
          thread_binding_kind: "control",
        },
      }),
    ).toEqual({
      focusHint: "kind=backlog-item | id=backlog-42",
      focusLabel: "焦点：Ship phase split",
      threadKindHint:
        "session_kind=industry-control-thread | thread_binding_kind=control | owner_scope=industry",
      threadKindLabel: "线程：控制线程",
      writebackHint: "inferred=strategy,backlog | role=execution-core | match_signals=2",
      writebackLabel: "写回：战略/待办",
    });
  });

  it("prefers explicit writeback targets from thread meta", () => {
    expect(
      resolveThreadRuntimePresentation({
        currentFocus: "",
        sessionKind: "industry-control-thread",
        threadMeta: {
          chat_writeback_targets: ["lane"],
          current_focus_id: "",
          current_focus_kind: "",
          owner_scope: "",
          thread_binding_kind: "",
        },
      }).writebackHint,
    ).toBe("targets=strategy,lane");
  });
});
