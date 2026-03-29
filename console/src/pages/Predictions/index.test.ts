import { describe, expect, it } from "vitest";

import {
  canCoordinateRecommendation,
  presentRecommendationActionKind,
} from "./index";

describe("presentRecommendationActionKind", () => {
  it("hides legacy goal dispatch jargon from the operator surface", () => {
    expect(presentRecommendationActionKind("system:dispatch_goal")).toBe(
      "内部编排",
    );
    expect(presentRecommendationActionKind("system:dispatch_active_goals")).toBe(
      "内部编排",
    );
    expect(presentRecommendationActionKind("manual:coordinate-main-brain")).toBe(
      "主脑协调",
    );
    expect(presentRecommendationActionKind("system:apply_role")).toBe(
      "system:apply_role",
    );
  });

  it("surfaces the main-brain handoff action from the coordinate route instead of executable state", () => {
    expect(
      canCoordinateRecommendation({
        recommendation: {
          executable: false,
        },
        routes: {
          coordinate:
            "/api/predictions/case-1/recommendations/recommendation-1/coordinate",
        },
      }),
    ).toBe(true);
    expect(
      canCoordinateRecommendation({
        recommendation: {
          executable: true,
        },
        routes: {},
      }),
    ).toBe(false);
  });
});
