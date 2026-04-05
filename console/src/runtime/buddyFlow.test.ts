import { describe, expect, it } from "vitest";

import type { BuddySurfaceResponse } from "../api/modules/buddy";
import {
  BUDDY_IDENTITY_CENTER_ROUTE,
  resolveBuddyEntryDecision,
  resolveBuddyNamingState,
} from "./buddyFlow";

function makeSurface(
  overrides?: Partial<BuddySurfaceResponse>,
): BuddySurfaceResponse {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "Mina",
      profession: "运营",
      current_stage: "探索期",
      interests: [],
      strengths: [],
      constraints: [],
      goal_intention: "找到长期方向",
    },
    growth_target: null,
    relationship: null,
    presentation: {
      profile_id: "profile-1",
      buddy_name: "你的伙伴",
      lifecycle_state: "born-unnamed",
      presence_state: "attentive",
      mood_state: "warm",
      current_form: "seed",
      rarity: "common",
      current_goal_summary: "",
      current_task_summary: "",
      why_now_summary: "",
      single_next_action_summary: "",
      companion_strategy_summary: "",
    },
    growth: {
      profile_id: "profile-1",
      intimacy: 0,
      affinity: 0,
      growth_level: 1,
      companion_experience: 0,
      knowledge_value: 0,
      skill_value: 0,
      pleasant_interaction_score: 0,
      communication_count: 0,
      completed_support_runs: 0,
      completed_assisted_closures: 0,
      evolution_stage: "seed",
      progress_to_next_stage: 0,
    },
    onboarding: {
      session_id: "session-1",
      status: "clarifying",
      question_count: 2,
      tightened: false,
      next_question: "下一问",
      candidate_directions: [],
      recommended_direction: "",
      selected_direction: "",
      requires_direction_confirmation: false,
      requires_naming: false,
      completed: false,
    },
    ...overrides,
  };
}

describe("buddyFlow", () => {
  it("pins the identity center to buddy onboarding", () => {
    expect(BUDDY_IDENTITY_CENTER_ROUTE).toBe("/buddy-onboarding");
  });

  it("keeps incomplete buddy profiles inside onboarding", () => {
    const decision = resolveBuddyEntryDecision(makeSurface());

    expect(decision.mode).toBe("resume-onboarding");
    expect(decision.sessionId).toBe("session-1");
  });

  it("routes confirmed-but-unnamed buddies into chat naming", () => {
    const surface = makeSurface({
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "建立稳定、自主、长期向上的人生成长主方向",
        final_goal: "建立长期成长主方向",
        why_it_matters: "因为这会改变接下来几年。",
        current_cycle_label: "Cycle 1",
      },
      onboarding: {
        session_id: "session-1",
        status: "confirmed",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: ["建立稳定、自主、长期向上的人生成长主方向"],
        recommended_direction: "建立稳定、自主、长期向上的人生成长主方向",
        selected_direction: "建立稳定、自主、长期向上的人生成长主方向",
        requires_direction_confirmation: false,
        requires_naming: true,
        completed: false,
      },
    });

    const decision = resolveBuddyEntryDecision(surface);
    const naming = resolveBuddyNamingState(surface, null);

    expect(decision.mode).toBe("chat-needs-naming");
    expect(naming.needsNaming).toBe(true);
    expect(naming.sessionId).toBe("session-1");
  });

  it("lets completed buddies enter chat without naming gate", () => {
    const surface = makeSurface({
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "建立稳定、自主、长期向上的人生成长主方向",
        final_goal: "建立长期成长主方向",
        why_it_matters: "因为这会改变接下来几年。",
        current_cycle_label: "Cycle 1",
      },
      relationship: {
        relationship_id: "relationship-1",
        profile_id: "profile-1",
        buddy_name: "小澜",
        encouragement_style: "old-friend",
      },
      presentation: {
        profile_id: "profile-1",
        buddy_name: "小澜",
        lifecycle_state: "bonded",
        presence_state: "attentive",
        mood_state: "warm",
        current_form: "seed",
        rarity: "common",
        current_goal_summary: "",
        current_task_summary: "",
        why_now_summary: "",
        single_next_action_summary: "",
        companion_strategy_summary: "",
      },
      onboarding: {
        session_id: "session-1",
        status: "named",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: ["建立稳定、自主、长期向上的人生成长主方向"],
        recommended_direction: "建立稳定、自主、长期向上的人生成长主方向",
        selected_direction: "建立稳定、自主、长期向上的人生成长主方向",
        requires_direction_confirmation: false,
        requires_naming: false,
        completed: true,
      },
    });

    const decision = resolveBuddyEntryDecision(surface);
    const naming = resolveBuddyNamingState(surface, null);

    expect(decision.mode).toBe("chat-ready");
    expect(naming.needsNaming).toBe(false);
  });
});
