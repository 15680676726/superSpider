// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetBuddyProfileBindingForTests } from "../../runtime/buddyProfileBinding";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddySurface: vi.fn(),
    startBuddyIdentity: vi.fn(),
    submitBuddyIdentity: vi.fn(),
    startBuddyClarification: vi.fn(),
    answerBuddyClarification: vi.fn(),
    previewBuddyDirectionTransition: vi.fn(),
    startBuddyConfirmDirection: vi.fn(),
    confirmBuddyDirection: vi.fn(),
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

vi.mock("../../api", () => ({
  default: apiMock,
  isApiError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in (error as Record<string, unknown>),
}));

vi.mock("../../utils/runtimeChat", () => runtimeChatMock);

import BuddyOnboardingPage from "./index";

function buildSurface(
  overrides: Partial<Record<string, unknown>> = {},
): Record<string, unknown> {
  const profile = {
    profile_id: "profile-1",
    display_name: "Alex",
    profession: "Writer",
    current_stage: "restart",
    interests: ["writing"],
    strengths: ["consistency"],
    constraints: ["time"],
    goal_intention: "Write and publish a real novel.",
    ...(overrides.profile as Record<string, unknown> | undefined),
  };
  const onboarding = {
    session_id: "session-1",
    status: "clarifying",
    operation_id: "",
    operation_kind: "",
    operation_status: "idle",
    operation_error: "",
    question_count: 1,
    tightened: false,
    next_question: "What kind of story do you want to publish first?",
    candidate_directions: [],
    recommended_direction: "",
    selected_direction: "",
    requires_direction_confirmation: false,
    requires_naming: false,
    completed: false,
    ...(overrides.onboarding as Record<string, unknown> | undefined),
  };
  return {
    profile,
    growth_target: overrides.growth_target ?? null,
    relationship:
      overrides.relationship ??
      ({
        relationship_id: "rel-1",
        profile_id: profile.profile_id,
        buddy_name: "",
        encouragement_style: "old-friend",
      } satisfies Record<string, unknown>),
    execution_carrier: overrides.execution_carrier ?? null,
    presentation:
      overrides.presentation ??
      ({
        profile_id: profile.profile_id,
        buddy_name: "Alex",
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
      } satisfies Record<string, unknown>),
    growth:
      overrides.growth ??
      ({
        profile_id: profile.profile_id,
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
      } satisfies Record<string, unknown>),
    onboarding,
  };
}

describe("BuddyOnboardingPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
    resetBuddyProfileBindingForTests();
    apiMock.getBuddySurface.mockRejectedValue({ status: 404 });
    apiMock.previewBuddyDirectionTransition.mockResolvedValue({
      session_id: "session-1",
      selected_direction: "Build a durable writing lane.",
      selected_domain_key: "build-a-durable-writing-lane",
      suggestion_kind: "start-new-domain",
      recommended_action: "start-new",
      reason_summary: "Start a new writing domain for this direction.",
      archived_matches: [],
      current_domain: null,
    });
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Alex growth carrier",
      threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      userId: "buddy:profile-1",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
        buddy_profile_id: "profile-1",
      },
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);
  });

  it("starts identity asynchronously and polls surface until the next question is ready", async () => {
    apiMock.startBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile_id: "profile-1",
      operation_id: "op-identity-1",
      operation_kind: "identity",
      operation_status: "running",
    });
    apiMock.getBuddySurface
      .mockRejectedValueOnce({ status: 404 })
      .mockResolvedValueOnce(
        buildSurface({
          onboarding: {
            session_id: "session-1",
            status: "clarifying",
            operation_id: "op-identity-1",
            operation_kind: "identity",
            operation_status: "succeeded",
            operation_error: "",
            question_count: 1,
            tightened: false,
            next_question: "What kind of story do you want to publish first?",
            candidate_directions: [],
            recommended_direction: "",
            selected_direction: "",
            requires_direction_confirmation: false,
            requires_naming: false,
            completed: false,
          },
        }),
      );

    render(<BuddyOnboardingPage />);

    const displayNameInput = await screen.findByTestId(
      "buddy-identity-display-name",
    );

    fireEvent.change(displayNameInput, {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByTestId("buddy-identity-profession"), {
      target: { value: "Writer" },
    });
    fireEvent.change(screen.getByTestId("buddy-identity-current-stage"), {
      target: { value: "restart" },
    });
    fireEvent.change(screen.getByTestId("buddy-identity-goal-intention"), {
      target: { value: "Write and publish a real novel." },
    });
    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.startBuddyIdentity).toHaveBeenCalledWith(
        expect.objectContaining({
          display_name: "Alex",
          profession: "Writer",
          current_stage: "restart",
          goal_intention: "Write and publish a real novel.",
        }),
      );
    });
    await waitFor(() => {
      expect(
        screen.getByText("What kind of story do you want to publish first?"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("buddy-clarification-submit"),
    ).toBeInTheDocument();
  });

  it("polls clarify and confirm operations, then opens runtime chat from the confirmed carrier", async () => {
    apiMock.getBuddySurface
      .mockResolvedValueOnce(
        buildSurface({
          profile: {
            profile_id: "profile-1",
            display_name: "Alex",
          },
          onboarding: {
            session_id: "session-1",
            status: "clarifying",
            operation_id: "",
            operation_kind: "",
            operation_status: "idle",
            operation_error: "",
            question_count: 1,
            tightened: false,
            next_question: "What kind of story do you want to publish first?",
            candidate_directions: [],
            recommended_direction: "",
            selected_direction: "",
            requires_direction_confirmation: false,
            requires_naming: false,
            completed: false,
          },
        }),
      )
      .mockResolvedValueOnce(
        buildSurface({
          onboarding: {
            session_id: "session-1",
            status: "direction-ready",
            operation_id: "op-clarify-1",
            operation_kind: "clarify",
            operation_status: "succeeded",
            operation_error: "",
            question_count: 2,
            tightened: false,
            next_question: "",
            candidate_directions: [
              "Build a durable writing lane.",
              "Build an audience growth lane.",
            ],
            recommended_direction: "Build a durable writing lane.",
            selected_direction: "",
            requires_direction_confirmation: true,
            requires_naming: false,
            completed: false,
          },
        }),
      )
      .mockResolvedValueOnce(
        buildSurface({
          onboarding: {
            session_id: "session-1",
            status: "confirmed",
            operation_id: "op-confirm-1",
            operation_kind: "confirm",
            operation_status: "succeeded",
            operation_error: "",
            question_count: 2,
            tightened: false,
            next_question: "",
            candidate_directions: ["Build a durable writing lane."],
            recommended_direction: "Build a durable writing lane.",
            selected_direction: "Build a durable writing lane.",
            requires_direction_confirmation: false,
            requires_naming: true,
            completed: false,
          },
          growth_target: {
            target_id: "target-1",
            profile_id: "profile-1",
            primary_direction: "Build a durable writing lane.",
            final_goal: "Publish the first real novel.",
            why_it_matters: "Turn writing into real proof-of-work.",
            current_cycle_label: "First publishing cycle",
          },
          execution_carrier: {
            instance_id: "buddy:profile-1:domain-writing",
            label: "Alex writing carrier",
            owner_scope: "profile-1",
            current_cycle_id: "cycle-1",
            team_generated: true,
            thread_id: "industry-chat:buddy:profile-1:domain-writing:execution-core",
            control_thread_id:
              "industry-chat:buddy:profile-1:domain-writing:execution-core",
          },
        }),
      );
    apiMock.startBuddyClarification.mockResolvedValue({
      session_id: "session-1",
      profile_id: "profile-1",
      operation_id: "op-clarify-1",
      operation_kind: "clarify",
      operation_status: "running",
    });
    apiMock.startBuddyConfirmDirection.mockResolvedValue({
      session_id: "session-1",
      profile_id: "profile-1",
      operation_id: "op-confirm-1",
      operation_kind: "confirm",
      operation_status: "running",
    });

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(
        screen.getByText("What kind of story do you want to publish first?"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("buddy-clarification-answer"), {
      target: { value: "I want to finish and publish a serious long-form novel." },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(apiMock.startBuddyClarification).toHaveBeenCalledWith({
        session_id: "session-1",
        answer: "I want to finish and publish a serious long-form novel.",
        existing_question_count: 1,
      });
    });
    await waitFor(() => {
      expect(
        screen.getByTestId("buddy-direction-recommendation"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("Build a durable writing lane."));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(apiMock.previewBuddyDirectionTransition).toHaveBeenCalledWith({
        session_id: "session-1",
        selected_direction: "Build a durable writing lane.",
      });
    });

    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));

    await waitFor(() => {
      expect(apiMock.startBuddyConfirmDirection).toHaveBeenCalledWith({
        session_id: "session-1",
        selected_direction: "Build a durable writing lane.",
        capability_action: "start-new",
        target_domain_id: undefined,
      });
    });
    await waitFor(() => {
      expect(
        screen.getByTestId("buddy-direction-confirmed"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("buddy-direction-enter-chat"));

    await waitFor(() => {
      expect(
        runtimeChatMock.buildBuddyExecutionCarrierChatBinding,
      ).toHaveBeenCalledWith({
        sessionId: "session-1",
        profileId: "profile-1",
        profileDisplayName: "Alex",
        executionCarrier: expect.objectContaining({
          instance_id: "buddy:profile-1:domain-writing",
        }),
      });
    });
    expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      }),
      navigateMock,
    );
  });

  it("reopens chat immediately when the bound buddy is already chat-ready", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-existing");
    apiMock.getBuddySurface.mockResolvedValueOnce(
      buildSurface({
        profile: {
          profile_id: "profile-existing",
          display_name: "Existing",
        },
        onboarding: {
          session_id: "session-existing",
          status: "named",
          operation_id: "",
          operation_kind: "",
          operation_status: "idle",
          operation_error: "",
          question_count: 2,
          tightened: false,
          next_question: "",
          candidate_directions: ["Build a durable writing lane."],
          recommended_direction: "Build a durable writing lane.",
          selected_direction: "Build a durable writing lane.",
          requires_direction_confirmation: false,
          requires_naming: false,
          completed: true,
        },
        growth_target: {
          target_id: "target-existing",
          profile_id: "profile-existing",
          primary_direction: "Build a durable writing lane.",
          final_goal: "Publish the first real novel.",
          why_it_matters: "Turn writing into proof-of-work.",
          current_cycle_label: "Cycle 1",
        },
        execution_carrier: {
          instance_id: "buddy:profile-existing:domain-writing",
          label: "Existing writing carrier",
          owner_scope: "profile-existing",
          current_cycle_id: "cycle-existing",
          team_generated: true,
          thread_id:
            "industry-chat:buddy:profile-existing:domain-writing:execution-core",
          control_thread_id:
            "industry-chat:buddy:profile-existing:domain-writing:execution-core",
        },
      }),
    );

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-existing");
    });
    await waitFor(() => {
      expect(
        runtimeChatMock.buildBuddyExecutionCarrierChatBinding,
      ).toHaveBeenCalledWith({
        sessionId: null,
        profileId: "profile-existing",
        profileDisplayName: "Existing",
        executionCarrier: expect.objectContaining({
          instance_id: "buddy:profile-existing:domain-writing",
        }),
        entrySource: "buddy-onboarding-resume",
      });
    });
    expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalled();
  });
});
