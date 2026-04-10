// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  resetBuddyProfileBindingForTests,
  writeBuddyProfileId,
} from "../../runtime/buddyProfileBinding";

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getBuddySurface: vi.fn(),
  },
}));

vi.mock("../../api", () => ({
  api: apiMock,
  default: apiMock,
}));

vi.mock("../../pages/Chat/buddyAvatar", () => ({
  BUDDY_ANIMATION_INTERVAL_MS: 1000000,
  buildBuddyAvatarView: vi.fn(() => ({
    frameIndex: 0,
    species: "seed",
    speciesLabel: "种子形态",
    rarityStars: "★",
    shiny: false,
    lines: [" /\\\\ ", "(o.o)"],
  })),
  renderBuddyFace: vi.fn(() => "^_^"),
}));

vi.mock("../../pages/Chat/buddyEvolution", () => ({
  resolveBuddyEvolutionView: vi.fn(() => ({
    stage: "seed",
    rarityLabel: "普通",
    accentTone: "purple",
  })),
}));

vi.mock("../../pages/Chat/buddyPresentation", () => ({
  resolveBuddyDisplaySnapshot: vi.fn(() => ({
    buddyName: "测试伙伴",
    stage: "seed",
    stageLabel: "萌芽",
    moodLabel: "平静",
    presenceLabel: "待命",
    encouragementStyleLabel: "朋友式",
    companionStrategySummary: "",
    capabilityPoints: 0,
    settledClosureCount: 0,
    progressToNextStage: 0,
    independentOutcomeCount: 0,
    distinctSettledCycleCount: 0,
    recentCompletionRate: 0,
    recentExecutionErrorRate: 0,
    finalGoalSummary: "暂无",
    currentTaskSummary: "暂无",
    whyNowSummary: "暂无",
    singleNextActionSummary: "暂无",
  })),
}));

import RightPanel from "./index";

function makeSurface() {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "测试伙伴",
    },
    growth: {
      intimacy: 0,
      affinity: 0,
      evolution_stage: "seed",
      capability_points: 0,
      capability_score: 0,
      companion_experience: 0,
      strategy_score: 0,
      execution_score: 0,
      evidence_score: 0,
      stability_score: 0,
    },
    presentation: {
      current_form: "seed",
      presence_state: "available",
      rarity: "common",
    },
  };
}

describe("RightPanel", () => {
  function setVisibilityState(value: DocumentVisibilityState) {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => value,
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    resetBuddyProfileBindingForTests();
    setVisibilityState("visible");
    apiMock.getBuddySurface.mockResolvedValue(makeSurface());
  });

  afterEach(() => {
    cleanup();
  });

  it("does not render on buddy onboarding before a buddy is bound", async () => {
    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
    });

    expect(screen.queryByText("伙伴详情")).not.toBeInTheDocument();
  });

  it("does not render on chat before a buddy is bound", async () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
    });

    expect(screen.queryByText("伙伴详情")).not.toBeInTheDocument();
  });

  it("loads the bound buddy on buddy onboarding when a profile is already stored", async () => {
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    });

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
  });

  it("shows the panel after the active thread publishes a buddy profile id", async () => {
    render(
      <MemoryRouter
        initialEntries={["/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core"]}
      >
        <RightPanel />
      </MemoryRouter>,
    );

    expect(screen.queryByText("测试伙伴")).not.toBeInTheDocument();

    window.dispatchEvent(
      new CustomEvent("copaw:thread-context", {
        detail: {
          meta: {
            buddy_profile_id: "profile-1",
          },
        },
      }),
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    });

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
  });

  it("shows the panel immediately when the buddy profile is written on the same route", async () => {
    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    expect(screen.queryByText("测试伙伴")).not.toBeInTheDocument();

    writeBuddyProfileId("profile-1");

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    });

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
  });

  it("renders sprites with a larger left-aligned monospace block", async () => {
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();

    const sprite = document.querySelector('[class*="spriteAscii"]') as HTMLElement | null;
    expect(sprite).not.toBeNull();
    expect(sprite?.style.fontSize).toBe("16px");
    expect(sprite ? getComputedStyle(sprite).alignItems : "").toBe("flex-start");
  });

  it("starts the buddy tick timer only on active chat routes", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        setIntervalSpy.mock.calls.some((call) => call[1] === 1000000),
      ).toBe(true);
    });
  });

  it("starts the buddy tick timer on non-chat routes when the panel is visible", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/settings/system"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        setIntervalSpy.mock.calls.some((call) => call[1] === 1000000),
      ).toBe(true);
    });
  });

  it("refreshes buddy data every five minutes after a buddy is bound", async () => {
    writeBuddyProfileId("profile-1");
    const setIntervalSpy = vi.spyOn(window, "setInterval");

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    });

    expect(
      setIntervalSpy.mock.calls.some((call) => call[1] === 300000),
    ).toBe(true);
  });

  it("does not start the buddy tick timer when the document is hidden", async () => {
    const setIntervalSpy = vi
      .spyOn(window, "setInterval")
      .mockReturnValue(4242 as unknown as ReturnType<typeof setInterval>);
    setVisibilityState("hidden");
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });
    expect(setIntervalSpy).not.toHaveBeenCalledWith(expect.any(Function), 1000000);
  });

  it("clears the buddy tick timer when the panel collapses", async () => {
    const buddyTimerId = 4242 as unknown as ReturnType<typeof setInterval>;
    vi.spyOn(window, "setInterval").mockReturnValue(buddyTimerId);
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    writeBuddyProfileId("profile-1");

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.click(screen.getAllByRole("button")[0]!);

    expect(clearIntervalSpy).toHaveBeenCalledWith(buddyTimerId);
  });
});
