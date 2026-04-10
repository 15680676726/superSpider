import { describe, expect, it } from "vitest";

import type { BuddySurfaceResponse } from "../api/modules/buddy";
import {
  BUDDY_IDENTITY_CENTER_ROUTE,
  resolveBuddyEntryDecision,
} from "./buddyFlow";

function makeSurface(
  overrides?: Partial<BuddySurfaceResponse>,
): BuddySurfaceResponse {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "Mina",
      profession: "Operator",
      current_stage: "exploring",
      interests: [],
      strengths: [],
      constraints: [],
      goal_intention: "Find a durable direction",
    },
    growth_target: null,
    relationship: null,
    execution_carrier: null,
    presentation: {
      profile_id: "profile-1",
      buddy_name: "Your buddy",
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
      operation_id: "",
      operation_kind: "",
      operation_status: "idle",
      operation_error: "",
      question_count: 2,
      tightened: false,
      next_question: "What matters most right now?",
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

function makeCarrier() {
  return {
    instance_id: "buddy:profile-1:domain-writing",
    label: "Mina writing carrier",
    owner_scope: "profile-1",
    current_cycle_id: "cycle-1",
    team_generated: true,
    thread_id: "industry-chat:buddy:profile-1:domain-writing:execution-core",
    control_thread_id:
      "industry-chat:buddy:profile-1:domain-writing:execution-core",
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

  it("keeps confirmed-but-unnamed buddies inside onboarding", () => {
    const surface = makeSurface({
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "Build a durable writing lane.",
        final_goal: "Publish the first real novel.",
        why_it_matters: "Turn writing into proof of work.",
        current_cycle_label: "Cycle 1",
      },
      execution_carrier: makeCarrier(),
      onboarding: {
        session_id: "session-1",
        status: "confirmed",
        operation_id: "",
        operation_kind: "",
        operation_status: "idle",
        operation_error: "",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: ["Build a durable writing lane."],
        recommended_direction: "Build a durable writing lane.",
        selected_direction: "Build a durable writing lane.",
        requires_direction_confirmation: false,
        requires_naming: true,
        completed: false,
      },
    });

    const decision = resolveBuddyEntryDecision(surface);

    expect(decision.mode).toBe("resume-onboarding");
    expect(decision.sessionId).toBe("session-1");
  });

  it("keeps confirmed buddies inside onboarding until the carrier is bound", () => {
    const surface = makeSurface({
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "Build a durable writing lane.",
        final_goal: "Publish the first real novel.",
        why_it_matters: "Turn writing into proof of work.",
        current_cycle_label: "Cycle 1",
      },
      execution_carrier: null,
      onboarding: {
        session_id: "session-1",
        status: "confirmed",
        operation_id: "",
        operation_kind: "",
        operation_status: "failed",
        operation_error: "boom after target",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: ["Build a durable writing lane."],
        recommended_direction: "Build a durable writing lane.",
        selected_direction: "Build a durable writing lane.",
        requires_direction_confirmation: false,
        requires_naming: true,
        completed: false,
      },
    });

    const decision = resolveBuddyEntryDecision(surface);

    expect(decision.mode).toBe("resume-onboarding");
    expect(decision.sessionId).toBe("session-1");
  });

  it("lets completed buddies enter chat without naming gate", () => {
    const surface = makeSurface({
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "Build a durable writing lane.",
        final_goal: "Publish the first real novel.",
        why_it_matters: "Turn writing into proof of work.",
        current_cycle_label: "Cycle 1",
      },
      relationship: {
        relationship_id: "relationship-1",
        profile_id: "profile-1",
        buddy_name: "Nova",
        encouragement_style: "old-friend",
      },
      execution_carrier: makeCarrier(),
      presentation: {
        profile_id: "profile-1",
        buddy_name: "Nova",
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
        operation_id: "",
        operation_kind: "",
        operation_status: "idle",
        operation_error: "",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: ["Build a durable writing lane."],
        recommended_direction: "Build a durable writing lane.",
        selected_direction: "Build a durable writing lane.",
        requires_direction_confirmation: false,
        requires_naming: false,
        completed: true,
      },
    });

    const decision = resolveBuddyEntryDecision(surface);

    expect(decision.mode).toBe("chat-ready");
    expect(decision.sessionId).toBeNull();
  });
});
