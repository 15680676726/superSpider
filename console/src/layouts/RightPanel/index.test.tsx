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

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  resetBuddyProfileBindingForTests,
  writeBuddyProfileId,
} from "../../runtime/buddyProfileBinding";

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getBuddySurface: vi.fn(),
  },
}));

const { buddySummaryStoreMock } = vi.hoisted(() => {
  type Snapshot = {
    loading: boolean;
    error: string | null;
    surface: BuddySurfaceResponse | null;
  };

  const listeners = new Map<string, Set<(snapshot: Snapshot) => void>>();
  const snapshots = new Map<string, Snapshot>();

  const emptySnapshot = (): Snapshot => ({
    loading: false,
    error: null,
    surface: null,
  });

  return {
    buddySummaryStoreMock: {
      subscribeBuddySummary: vi.fn(
        (profileId: string, listener: (snapshot: Snapshot) => void) => {
          const nextListeners = listeners.get(profileId) ?? new Set();
          nextListeners.add(listener);
          listeners.set(profileId, nextListeners);
          listener(snapshots.get(profileId) ?? emptySnapshot());
          return () => {
            nextListeners.delete(listener);
          };
        },
      ),
      getBuddySummarySnapshot: vi.fn((profileId: string) => {
        return snapshots.get(profileId) ?? emptySnapshot();
      }),
      __setSnapshot(profileId: string, snapshot: Snapshot) {
        snapshots.set(profileId, snapshot);
      },
      __emit(profileId: string) {
        const snapshot = snapshots.get(profileId) ?? emptySnapshot();
        listeners.get(profileId)?.forEach((listener) => listener(snapshot));
      },
      __reset() {
        listeners.clear();
        snapshots.clear();
      },
    },
  };
});

vi.mock("../../api", () => ({
  api: apiMock,
  default: apiMock,
}));

vi.mock("../../runtime/buddySummaryStore", () => buddySummaryStoreMock);

vi.mock("../../pages/Chat/buddyAvatar", () => ({
  BUDDY_ANIMATION_INTERVAL_MS: 1000000,
  buildBuddyAvatarView: vi.fn(() => ({
    frameIndex: 0,
    species: "seed",
    speciesLabel: "种子形态",
    rarityStars: "☆",
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
    encouragementStyleLabel: "朋友",
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

function makeSurface(): BuddySurfaceResponse {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "测试伙伴",
      profession: "designer",
      current_stage: "seed",
      interests: [],
      strengths: [],
      constraints: [],
      goal_intention: "ship",
    },
    growth: {
      profile_id: "profile-1",
      intimacy: 0,
      affinity: 0,
      growth_level: 0,
      companion_experience: 0,
      capability_points: 0,
      capability_score: 0,
      strategy_score: 0,
      execution_score: 0,
      evidence_score: 0,
      stability_score: 0,
      knowledge_value: 0,
      skill_value: 0,
      pleasant_interaction_score: 0,
      communication_count: 0,
      completed_support_runs: 0,
      completed_assisted_closures: 0,
      evolution_stage: "seed",
      progress_to_next_stage: 0,
    },
    presentation: {
      profile_id: "profile-1",
      buddy_name: "测试伙伴",
      lifecycle_state: "named",
      presence_state: "available",
      mood_state: "steady",
      current_form: "seed",
      rarity: "common",
      current_goal_summary: "目标",
      current_task_summary: "任务",
      why_now_summary: "原因",
      single_next_action_summary: "下一步",
      companion_strategy_summary: "策略",
    },
    onboarding: {
      session_id: null,
      status: "completed",
      operation_id: "",
      operation_kind: "",
      operation_status: "",
      operation_error: "",
      service_intent: "",
      collaboration_role: "",
      autonomy_level: "",
      confirm_boundaries: [],
      report_style: "",
      collaboration_notes: "",
      candidate_directions: [],
      recommended_direction: "",
      selected_direction: "",
      requires_direction_confirmation: false,
      requires_naming: false,
      completed: true,
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

  function setStoreSurface(profileId = "profile-1") {
    buddySummaryStoreMock.__setSnapshot(profileId, {
      loading: false,
      error: null,
      surface: makeSurface(),
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    resetBuddyProfileBindingForTests();
    setVisibilityState("visible");
    apiMock.getBuddySurface.mockResolvedValue(makeSurface());
    buddySummaryStoreMock.__reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("does not render before a buddy is bound", async () => {
    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(buddySummaryStoreMock.subscribeBuddySummary).not.toHaveBeenCalled();
    });

    expect(screen.queryByText("伙伴详情")).not.toBeInTheDocument();
    expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
  });

  it("consumes the shared buddy summary store when a profile is already stored", async () => {
    writeBuddyProfileId("profile-1");
    setStoreSurface();

    render(
      <MemoryRouter initialEntries={["/buddy-onboarding"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(buddySummaryStoreMock.subscribeBuddySummary).toHaveBeenCalledWith(
        "profile-1",
        expect.any(Function),
      );
    });

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
    expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
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
      expect(buddySummaryStoreMock.subscribeBuddySummary).toHaveBeenCalledWith(
        "profile-1",
        expect.any(Function),
      );
    });

    setStoreSurface();
    buddySummaryStoreMock.__emit("profile-1");

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
    expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
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
      expect(buddySummaryStoreMock.subscribeBuddySummary).toHaveBeenCalledWith(
        "profile-1",
        expect.any(Function),
      );
    });

    setStoreSurface();
    buddySummaryStoreMock.__emit("profile-1");

    expect(await screen.findByText("测试伙伴")).toBeInTheDocument();
    expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
  });

  it("renders sprites with a larger left-aligned monospace block", async () => {
    writeBuddyProfileId("profile-1");
    setStoreSurface();

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
    setStoreSurface();

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
    setStoreSurface();

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

  it("does not start the buddy tick timer when the document is hidden", async () => {
    const setIntervalSpy = vi
      .spyOn(window, "setInterval")
      .mockReturnValue(4242 as unknown as ReturnType<typeof setInterval>);
    setVisibilityState("hidden");
    writeBuddyProfileId("profile-1");
    setStoreSurface();

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("测试伙伴")).toBeInTheDocument();
    });
    expect(setIntervalSpy).not.toHaveBeenCalledWith(expect.any(Function), 1000000);
  });

  it("clears the buddy tick timer when the panel collapses", async () => {
    const buddyTimerId = 4242 as unknown as ReturnType<typeof setInterval>;
    vi.spyOn(window, "setInterval").mockReturnValue(buddyTimerId);
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    writeBuddyProfileId("profile-1");
    setStoreSurface();

    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RightPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("测试伙伴")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button")[0]!);

    expect(clearIntervalSpy).toHaveBeenCalledWith(buddyTimerId);
  });
});
