// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportsPage from "./index";

const requestMock = vi.fn();

vi.mock("../../api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

describe("ReportsPage", () => {
  it("does not render legacy goal counts in the report activity strip", async () => {
    requestMock.mockResolvedValueOnce([
      {
        id: "report-1",
        title: "Daily report",
        summary: "Runtime summary",
        window: "daily",
        highlights: [],
        evidence_count: 4,
        proposal_count: 1,
        patch_count: 1,
        applied_patch_count: 0,
        decision_count: 2,
        prediction_count: 0,
        recommendation_count: 0,
        review_count: 0,
        auto_execution_count: 0,
        task_count: 3,
        goal_count: 2,
        agent_count: 5,
        task_status_counts: {
          running: 1,
        },
        metrics: [],
        since: "2026-03-26T08:00:00Z",
        until: "2026-03-26T12:00:00Z",
      },
    ]);

    render(<ReportsPage />);

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("/runtime-center/reports");
    });

    expect(await screen.findByText("任务 3")).toBeTruthy();
    expect(screen.queryByText("目标 2")).toBeNull();
  });
});
