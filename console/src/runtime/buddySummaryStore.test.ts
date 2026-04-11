import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BuddySurfaceResponse } from "../api/modules/buddy";
import {
  BUDDY_SUMMARY_REFRESH_MS,
  getBuddySummarySnapshot,
  refreshBuddySummary,
  resetBuddySummaryStoreForTests,
  seedBuddySummary,
  subscribeBuddySummary,
} from "./buddySummaryStore";

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getBuddySurface: vi.fn(),
  },
}));

vi.mock("../api", () => ({
  api: apiMock,
  default: apiMock,
}));

function makeSurface(profileId = "profile-1"): BuddySurfaceResponse {
  return {
    profile: {
      profile_id: profileId,
      display_name: "测试伙伴",
      profession: "designer",
      current_stage: "seed",
      interests: [],
      strengths: [],
      constraints: [],
      goal_intention: "ship",
    },
    presentation: {
      profile_id: profileId,
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
    growth: {
      profile_id: profileId,
      intimacy: 1,
      affinity: 1,
      growth_level: 1,
      companion_experience: 0,
      capability_points: 0,
      capability_score: 0,
      knowledge_value: 0,
      skill_value: 0,
      pleasant_interaction_score: 0,
      communication_count: 0,
      completed_support_runs: 0,
      completed_assisted_closures: 0,
      evolution_stage: "seed",
      progress_to_next_stage: 0,
    },
    execution_carrier: {
      instance_id: `buddy:${profileId}:carrier`,
      label: "Carrier",
      owner_scope: profileId,
      current_cycle_id: "cycle-1",
      team_generated: true,
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

describe("buddySummaryStore", () => {
  async function flushMicrotasks(): Promise<void> {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    resetBuddySummaryStoreForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
    resetBuddySummaryStoreForTests();
  });

  it("caches buddy summary per profile id and dedupes concurrent subscribers", async () => {
    let resolveFetch!: (value: BuddySurfaceResponse | null) => void;
    apiMock.getBuddySurface.mockReturnValue(
      new Promise<BuddySurfaceResponse | null>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const firstListener = vi.fn();
    const secondListener = vi.fn();

    const unsubscribeFirst = subscribeBuddySummary("profile-1", firstListener);
    const unsubscribeSecond = subscribeBuddySummary("profile-1", secondListener);

    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(1);
    expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    expect(getBuddySummarySnapshot("profile-1")).toMatchObject({
      loading: true,
      surface: null,
    });

    resolveFetch(makeSurface("profile-1"));
    await flushMicrotasks();

    const snapshot = getBuddySummarySnapshot("profile-1");
    expect(snapshot.loading).toBe(false);
    expect(snapshot.surface?.profile.profile_id).toBe("profile-1");
    expect(firstListener).toHaveBeenCalled();
    expect(secondListener).toHaveBeenCalled();

    unsubscribeFirst();
    unsubscribeSecond();

    const thirdListener = vi.fn();
    const unsubscribeThird = subscribeBuddySummary("profile-1", thirdListener);
    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(1);
    expect(getBuddySummarySnapshot("profile-1").surface?.profile.profile_id).toBe(
      "profile-1",
    );
    unsubscribeThird();
  });

  it("keeps the existing snapshot when refresh fails on the five-minute cadence", async () => {
    apiMock.getBuddySurface
      .mockResolvedValueOnce(makeSurface("profile-2"))
      .mockRejectedValueOnce(new Error("refresh failed"));

    const listener = vi.fn();
    const unsubscribe = subscribeBuddySummary("profile-2", listener);

    await flushMicrotasks();

    expect(getBuddySummarySnapshot("profile-2").surface?.profile.profile_id).toBe(
      "profile-2",
    );

    await vi.advanceTimersByTimeAsync(BUDDY_SUMMARY_REFRESH_MS);
    await flushMicrotasks();

    const snapshot = getBuddySummarySnapshot("profile-2");
    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(2);
    expect(snapshot.surface?.profile.profile_id).toBe("profile-2");
    expect(snapshot.loading).toBe(false);
    expect(snapshot.error).toBe("refresh failed");

    unsubscribe();
  });

  it("lets callers seed fresh buddy truth without forcing a refetch", async () => {
    seedBuddySummary("profile-3", makeSurface("profile-3"));

    const listener = vi.fn();
    const unsubscribe = subscribeBuddySummary("profile-3", listener);

    expect(apiMock.getBuddySurface).not.toHaveBeenCalled();
    expect(getBuddySummarySnapshot("profile-3").surface?.profile.profile_id).toBe(
      "profile-3",
    );

    apiMock.getBuddySurface.mockResolvedValueOnce(makeSurface("profile-3"));
    await refreshBuddySummary("profile-3");
    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(1);

    unsubscribe();
  });
});
