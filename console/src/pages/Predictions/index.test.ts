import { describe, expect, it } from "vitest";

import type { PredictionRecommendationRecord } from "../../api/modules/predictions";
import {
  canCoordinateRecommendation,
  presentRecommendationActionKind,
} from "./index";

function createRecommendationFixture(
  overrides?: Partial<PredictionRecommendationRecord>,
): PredictionRecommendationRecord {
  return {
    recommendation_id: "recommendation-1",
    case_id: "case-1",
    recommendation_type: "runtime",
    title: "Coordinate with main brain",
    summary: "Coordinate recommendation",
    priority: 1,
    confidence: 0.8,
    risk_level: "guarded",
    action_kind: "manual:coordinate-main-brain",
    executable: false,
    auto_eligible: false,
    auto_executed: false,
    status: "pending",
    target_goal_id: null,
    target_schedule_id: null,
    target_capability_ids: [],
    decision_request_id: null,
    execution_task_id: null,
    execution_evidence_id: null,
    outcome_summary: null,
    action_payload: {},
    metadata: {},
    created_at: "2026-03-28T00:00:00Z",
    updated_at: "2026-03-28T00:00:00Z",
    ...overrides,
  };
}

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
        recommendation: createRecommendationFixture({ executable: false }),
        routes: {
          coordinate:
            "/api/predictions/case-1/recommendations/recommendation-1/coordinate",
        },
      }),
    ).toBe(true);
    expect(
      canCoordinateRecommendation({
        recommendation: createRecommendationFixture({ executable: true }),
        routes: {},
      }),
    ).toBe(false);
  });
});
