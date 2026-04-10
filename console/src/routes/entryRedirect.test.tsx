// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetBuddyProfileBindingForTests } from "../runtime/buddyProfileBinding";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddySurface: vi.fn(),
  },
}));

const runtimeChatMock = vi.hoisted(() => ({
  buildBuddyExecutionCarrierChatBinding: vi.fn(),
  openRuntimeChat: vi.fn(),
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

vi.mock("../api", () => ({
  default: apiMock,
}));

vi.mock("../utils/runtimeChat", () => runtimeChatMock);

import EntryRedirect from "./entryRedirect";

function buildSurface(
  overrides: Partial<Record<string, unknown>> = {},
): Record<string, unknown> {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "Alex",
      profession: "Writer",
      current_stage: "restart",
      interests: ["writing"],
      strengths: ["consistency"],
      constraints: ["time"],
      goal_intention: "Write and publish a real novel.",
      ...(overrides.profile as Record<string, unknown> | undefined),
    },
    growth_target: overrides.growth_target ?? null,
    relationship: overrides.relationship ?? null,
    execution_carrier: overrides.execution_carrier ?? null,
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
      ...(overrides.presentation as Record<string, unknown> | undefined),
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
      ...(overrides.growth as Record<string, unknown> | undefined),
    },
    onboarding: {
      session_id: "session-1",
      status: "contract-draft",
      operation_id: "",
      operation_kind: "",
      operation_status: "idle",
      operation_error: "",
      service_intent: "",
      collaboration_role: "orchestrator",
      autonomy_level: "proactive",
      confirm_boundaries: [],
      report_style: "result-first",
      collaboration_notes: "",
      candidate_directions: [],
      recommended_direction: "",
      selected_direction: "",
      requires_direction_confirmation: false,
      requires_naming: false,
      completed: false,
      ...(overrides.onboarding as Record<string, unknown> | undefined),
    },
  };
}

describe("EntryRedirect", () => {
  beforeEach(() => {
    resetBuddyProfileBindingForTests();
    navigateMock.mockReset();
    apiMock.getBuddySurface.mockReset();
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReset();
    runtimeChatMock.openRuntimeChat.mockReset();
  });

  it("sends users without a saved buddy profile straight to onboarding", async () => {
    render(<EntryRedirect />);

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
        replace: true,
      });
    });
  });

  it("keeps unfinished buddy onboarding on the onboarding page", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-1");
    apiMock.getBuddySurface.mockResolvedValue(
      buildSurface({
        onboarding: {
          session_id: "session-1",
          status: "confirmed",
          operation_id: "",
          operation_kind: "",
          operation_status: "idle",
          operation_error: "",
          service_intent: "Help me build a durable writing lane.",
          collaboration_role: "orchestrator",
          autonomy_level: "guarded-proactive",
          confirm_boundaries: ["external spend"],
          report_style: "decision-first",
          collaboration_notes: "Keep it concise.",
          candidate_directions: ["Build a durable writing lane."],
          recommended_direction: "Build a durable writing lane.",
          selected_direction: "Build a durable writing lane.",
          requires_direction_confirmation: false,
          requires_naming: true,
          completed: false,
        },
        execution_carrier: {
          instance_id: "buddy:profile-1:domain-writing",
          label: "Writing carrier",
          owner_scope: "profile-1",
          current_cycle_id: "cycle-1",
          team_generated: true,
          thread_id:
            "industry-chat:buddy:profile-1:domain-writing:execution-core",
          control_thread_id:
            "industry-chat:buddy:profile-1:domain-writing:execution-core",
        },
      }),
    );

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
      expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
        replace: true,
      });
    });
  });

  it("opens chat directly when the buddy is already ready", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-1");
    apiMock.getBuddySurface.mockResolvedValue(
      buildSurface({
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
          service_intent: "Help me build a durable writing lane.",
          collaboration_role: "orchestrator",
          autonomy_level: "guarded-proactive",
          confirm_boundaries: ["external spend"],
          report_style: "decision-first",
          collaboration_notes: "Keep it concise.",
        },
        execution_carrier: {
          instance_id: "buddy:profile-1:domain-writing",
          label: "Writing carrier",
          owner_scope: "profile-1",
          current_cycle_id: "cycle-1",
          team_generated: true,
          thread_id:
            "industry-chat:buddy:profile-1:domain-writing:execution-core",
          control_thread_id:
            "industry-chat:buddy:profile-1:domain-writing:execution-core",
        },
        onboarding: {
          session_id: "session-1",
          status: "named",
          operation_id: "",
          operation_kind: "",
          operation_status: "idle",
          operation_error: "",
          service_intent: "Help me build a durable writing lane.",
          collaboration_role: "orchestrator",
          autonomy_level: "guarded-proactive",
          confirm_boundaries: ["external spend"],
          report_style: "decision-first",
          collaboration_notes: "Keep it concise.",
          candidate_directions: ["Build a durable writing lane."],
          recommended_direction: "Build a durable writing lane.",
          selected_direction: "Build a durable writing lane.",
          requires_direction_confirmation: false,
          requires_naming: false,
          completed: true,
        },
      }),
    );
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Nova",
      threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      userId: "buddy:profile-1",
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);

    render(<EntryRedirect />);

    expect(screen.getByText("正在为你打开伙伴主场…")).toBeInTheDocument();

    await waitFor(() => {
      expect(runtimeChatMock.buildBuddyExecutionCarrierChatBinding).toHaveBeenCalledWith({
        sessionId: "session-1",
        profileId: "profile-1",
        profileDisplayName: "Alex",
        executionCarrier: expect.objectContaining({
          instance_id: "buddy:profile-1:domain-writing",
        }),
        entrySource: "entry-redirect",
      });
      expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
        expect.objectContaining({
          threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
        }),
        navigateMock,
        { shouldNavigate: expect.any(Function) },
      );
    });
  });
});
