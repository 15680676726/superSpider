import { describe, expect, it } from "vitest";

import {
  buildHumanAssistDetailPresentation,
  firstNonEmptyString,
  normalizeTaskSummary,
} from "./chatHumanAssistPresentation";

describe("chatHumanAssistPresentation", () => {
  it("normalizes runtime human-assist task summary only when required fields are present", () => {
    expect(
      normalizeTaskSummary({
        id: "task-1",
        title: "Upload receipt",
        chat_thread_id: "thread-1",
        route: "/api/runtime-center/human-assist-tasks/task-1",
        status: "issued",
      }),
    ).toMatchObject({
      id: "task-1",
      title: "Upload receipt",
      chat_thread_id: "thread-1",
      status: "issued",
    });

    expect(
      normalizeTaskSummary({
        id: "task-1",
        title: "Upload receipt",
      }),
    ).toBeNull();
  });

  it("picks the first non-empty string candidate", () => {
    expect(firstNonEmptyString(null, " ", "thread-1", "thread-2")).toBe(
      "thread-1",
    );
    expect(firstNonEmptyString(undefined, "", " ")).toBeNull();
  });

  it("builds detail presentation from acceptance spec and reward payload", () => {
    const detail = buildHumanAssistDetailPresentation({
      task: {
        id: "task-1",
        title: "Upload receipt",
        status: "issued",
        summary: "Need host evidence",
        required_action: "Upload screenshot",
        acceptance_spec: {
          hard_anchors: ["receipt"],
          result_anchors: ["uploaded"],
          negative_anchors: ["missing"],
        },
        reward_preview: {
          granted: false,
          xp: 2,
        },
        reward_result: {
          granted: true,
          xp: 1,
        },
      },
    } as never);

    expect(detail.hardAnchors).toEqual(["receipt"]);
    expect(detail.resultAnchors).toEqual(["uploaded"]);
    expect(detail.negativeAnchors).toEqual(["missing"]);
    expect(detail.rewardPreview).toEqual([["xp", "2"]]);
    expect(detail.rewardResult).toEqual([["xp", "1"]]);
    expect(detail.summary).toBe("Need host evidence");
    expect(detail.action).toBe("Upload screenshot");
  });
});
