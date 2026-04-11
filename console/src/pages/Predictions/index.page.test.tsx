// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PredictionsPage from "./index";

const apiMock = vi.hoisted(() => ({
  listPredictions: vi.fn(),
  getPredictionCase: vi.fn(),
  coordinatePredictionRecommendation: vi.fn(),
  addPredictionReview: vi.fn(),
}));

vi.mock("../../api", () => ({
  default: apiMock,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

describe("PredictionsPage", () => {
  it("renders the case list before detail hydration finishes", async () => {
    apiMock.listPredictions.mockResolvedValue([
      {
        case: {
          case_id: "case-1",
          title: "Case Alpha",
          summary: "Check the main chain.",
          question: "What should move first?",
          case_kind: "cycle",
          status: "open",
          topic_type: "cycle-review",
          time_window_days: 1,
          updated_at: "2026-04-11T08:00:00Z",
          created_at: "2026-04-11T07:00:00Z",
          overall_confidence: 0.72,
          input_payload: {},
          metadata: {},
        },
        scenario_count: 1,
        signal_count: 2,
        recommendation_count: 1,
        review_count: 0,
        pending_decision_count: 0,
        routes: {},
      },
    ]);
    apiMock.getPredictionCase.mockReturnValue(new Promise(() => undefined));

    render(<PredictionsPage />);

    await waitFor(() => {
      expect(screen.queryAllByRole("listitem").length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(apiMock.getPredictionCase).toHaveBeenCalledWith("case-1");
    });
  });
});
