// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  beforeEach(() => {
    vi.clearAllMocks();
    resetBuddyProfileBindingForTests();
    apiMock.getBuddySurface.mockResolvedValue(makeSurface());
  });

  afterEach(() => {
    cleanup();
  });

  it("stays empty on buddy onboarding before a buddy is bound", async () => {
    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
    });

    expect(screen.queryByText("测试伙伴")).not.toBeInTheDocument();
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

  it("renders sprites with a larger left-aligned monospace block", async () => {
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
});
