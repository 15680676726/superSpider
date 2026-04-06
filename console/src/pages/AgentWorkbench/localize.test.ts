import { describe, expect, it } from "vitest";

import { localizeWorkbenchText } from "./localize";

describe("AgentWorkbench localize", () => {
  it("uses current focus wording for legacy goal-focused runtime copy", () => {
    expect(localizeWorkbenchText("Focus on the goal: Ship phase split.")).toBe(
      "当前焦点：Ship phase split。",
    );
  });

  it("uses focus wording for daily control review prompts", () => {
    expect(
      localizeWorkbenchText(
        "Run the daily control review for Ops Core. Goal: Stabilize runtime delivery",
      ),
    ).toBe("请执行 Ops Core 的每日中枢复盘。焦点事项：Stabilize runtime delivery");
  });
});
