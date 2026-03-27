import { describe, expect, it } from "vitest";

import { presentRecommendationActionKind } from "./index";

describe("presentRecommendationActionKind", () => {
  it("hides legacy goal dispatch jargon from the operator surface", () => {
    expect(presentRecommendationActionKind("system:dispatch_goal")).toBe(
      "编入执行链",
    );
    expect(presentRecommendationActionKind("system:dispatch_active_goals")).toBe(
      "编入执行链",
    );
    expect(presentRecommendationActionKind("system:apply_role")).toBe(
      "system:apply_role",
    );
  });
});
