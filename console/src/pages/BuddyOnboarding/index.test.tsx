// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddySurface: vi.fn(),
    submitBuddyIdentity: vi.fn(),
    answerBuddyClarification: vi.fn(),
    confirmBuddyDirection: vi.fn(),
  },
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../../api", () => ({
  default: apiMock,
  isApiError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in (error as Record<string, unknown>),
}));

import BuddyOnboardingPage from "./index";

describe("BuddyOnboardingPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiMock.getBuddySurface.mockRejectedValue({ status: 404 });
    apiMock.submitBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
      },
      question_count: 1,
      next_question: "你最想真正改变的人生部分是什么？",
      finished: false,
    });
    apiMock.answerBuddyClarification.mockResolvedValue({
      session_id: "session-1",
      question_count: 9,
      tightened: true,
      finished: true,
      next_question: "",
      candidate_directions: [
        "Build an independent creator-business growth path",
        "Build a stable self-directed growth path with increasing autonomy",
      ],
      recommended_direction:
        "Build an independent creator-business growth path",
    });
    apiMock.confirmBuddyDirection.mockResolvedValue({
      session: { session_id: "session-1" },
      growth_target: {
        primary_direction: "Build an independent creator-business growth path",
      },
      relationship: { encouragement_style: "old-friend" },
    });
  });

  it("runs identity -> clarification -> direction confirmation and routes into chat naming flow", async () => {
    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("你希望我怎么称呼你"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByPlaceholderText("你现在主要在做什么"), {
      target: { value: "Designer" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：探索期、转型期、重建期、稳定增长期"), {
      target: { value: "transition" },
    });
    fireEvent.change(screen.getByPlaceholderText("先说你隐约想改变什么，模糊也没关系"), {
      target: { value: "I want to build a real long-term direction." },
    });

    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("用最真实的话回答我，不用写得很工整"), {
      target: { value: "I want leverage and independence." },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(apiMock.answerBuddyClarification).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("buddy-direction-recommendation")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/Build an independent creator-business growth path/i));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalled();
    });
    expect(navigateMock).toHaveBeenCalledWith(
      "/chat?buddy_session=session-1&buddy_needs_name=1",
      { replace: true },
    );
  });
});
