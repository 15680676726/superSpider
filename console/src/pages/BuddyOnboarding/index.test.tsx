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
    nameBuddy: vi.fn(),
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

  it("submits identity directly and shows the next clarification question", async () => {
    apiMock.submitBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
        profession: "Writer",
        current_stage: "restart",
        interests: [],
        strengths: [],
        constraints: [],
        goal_intention: "Write and publish a real novel.",
      },
      question_count: 1,
      next_question: "What kind of story do you want to publish first?",
      finished: false,
    });

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
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalledWith(
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

  it("moves from clarification to naming and only opens chat after naming finishes", async () => {
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
      );
    apiMock.answerBuddyClarification.mockResolvedValue({
      session_id: "session-1",
      question_count: 2,
      tightened: false,
      finished: true,
      next_question: "",
      candidate_directions: [
        "Build a durable writing lane.",
        "Build an audience growth lane.",
      ],
      recommended_direction: "Build a durable writing lane.",
    });
    apiMock.confirmBuddyDirection.mockResolvedValue({
      session: {
        session_id: "session-1",
        profile_id: "profile-1",
        status: "confirmed",
        question_count: 2,
        candidate_directions: ["Build a durable writing lane."],
        recommended_direction: "Build a durable writing lane.",
        selected_direction: "Build a durable writing lane.",
      },
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "Build a durable writing lane.",
        final_goal: "Publish the first real novel.",
        why_it_matters: "Turn writing into real proof-of-work.",
        current_cycle_label: "First publishing cycle",
      },
      relationship: {
        relationship_id: "rel-1",
        profile_id: "profile-1",
        buddy_name: "",
        encouragement_style: "old-friend",
      },
      domain_capability: null,
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
    });
    apiMock.nameBuddy.mockResolvedValue({
      buddy_name: "Nova",
      profile_id: "profile-1",
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
      expect(apiMock.answerBuddyClarification).toHaveBeenCalledWith({
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
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalledWith({
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
    expect(screen.getByTestId("buddy-name-input")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("buddy-name-input"), {
      target: { value: "Nova" },
    });
    fireEvent.click(screen.getByTestId("buddy-start-chat"));

    await waitFor(() => {
      expect(apiMock.nameBuddy).toHaveBeenCalledWith({
        session_id: "session-1",
        buddy_name: "Nova",
      });
    });

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

  it("does not keep the clarification card visible after the surface enters naming state", async () => {
    apiMock.getBuddySurface.mockResolvedValueOnce(
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
        growth: {
          profile_id: "profile-1",
          domain_id: "domain-writing",
          domain_key: "domain-writing",
          domain_label: "Writing",
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
        growth_target: {
          target_id: "target-1",
          profile_id: "profile-1",
          primary_direction: "Build a durable writing lane.",
          final_goal: "Publish the first real novel.",
          why_it_matters: "Turn writing into proof-of-work.",
          current_cycle_label: "Cycle 1",
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

    render(<BuddyOnboardingPage />);

    expect(await screen.findByTestId("buddy-name-input")).toBeInTheDocument();
    expect(runtimeChatMock.openRuntimeChat).not.toHaveBeenCalled();
    expect(
      screen.queryByText("再回答我几句，我帮你把方向收得更准"),
    ).not.toBeInTheDocument();
  });

  it("returns to direction confirmation when the surface has no active domain carrier", async () => {
    apiMock.getBuddySurface.mockResolvedValueOnce(
      buildSurface({
        onboarding: {
          session_id: "session-1",
          status: "confirmed",
          operation_id: "op-confirm-1",
          operation_kind: "confirm",
          operation_status: "failed",
          operation_error: "boom after target",
          question_count: 2,
          tightened: false,
          next_question: "",
          candidate_directions: ["Build a durable writing lane."],
          recommended_direction: "Build a durable writing lane.",
          selected_direction: "Build a durable writing lane.",
          requires_direction_confirmation: true,
          requires_naming: false,
          completed: false,
        },
        growth_target: {
          target_id: "target-1",
          profile_id: "profile-1",
          primary_direction: "Build a durable writing lane.",
          final_goal: "Publish the first real novel.",
          why_it_matters: "Turn writing into proof-of-work.",
          current_cycle_label: "Cycle 1",
        },
        execution_carrier: null,
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
      }),
    );

    render(<BuddyOnboardingPage />);

    expect(await screen.findByTestId("buddy-direction-confirm")).toBeInTheDocument();
    expect(screen.queryByTestId("buddy-direction-confirmed")).not.toBeInTheDocument();
    expect(screen.queryByTestId("buddy-direction-enter-chat")).not.toBeInTheDocument();
  });

  it("keeps confirmed naming inside onboarding until the user names the buddy and starts chat", async () => {
    apiMock.getBuddySurface.mockResolvedValueOnce(
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
          why_it_matters: "Turn writing into proof-of-work.",
          current_cycle_label: "Cycle 1",
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
    apiMock.nameBuddy.mockResolvedValue({
      buddy_name: "Nova",
      profile_id: "profile-1",
    });

    render(<BuddyOnboardingPage />);

    expect(await screen.findByTestId("buddy-name-input")).toBeInTheDocument();
    expect(runtimeChatMock.openRuntimeChat).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("buddy-name-input"), {
      target: { value: "Nova" },
    });
    fireEvent.click(screen.getByTestId("buddy-start-chat"));

    await waitFor(() => {
      expect(apiMock.nameBuddy).toHaveBeenCalledWith({
        session_id: "session-1",
        buddy_name: "Nova",
      });
    });
    await waitFor(() => {
      expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledTimes(1);
    });
  });

  it("lets the user return from direction step to identity form without losing filled values", async () => {
    apiMock.submitBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
        profession: "Writer",
        current_stage: "restart",
        interests: [],
        strengths: [],
        constraints: [],
        goal_intention: "Write and publish a real novel.",
      },
      question_count: 1,
      next_question: "What kind of story do you want to publish first?",
      finished: false,
    });

    render(<BuddyOnboardingPage />);

    fireEvent.change(await screen.findByTestId("buddy-identity-display-name"), {
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

    expect(
      await screen.findByText("What kind of story do you want to publish first?"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-step-back"));

    expect(await screen.findByTestId("buddy-identity-form")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Alex")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Writer")).toBeInTheDocument();
    expect(screen.getByDisplayValue("restart")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Write and publish a real novel.")).toBeInTheDocument();
  });

  it("returns from naming step to direction confirmation instead of staying stuck on naming", async () => {
    apiMock.submitBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
        profession: "Writer",
        current_stage: "restart",
        interests: [],
        strengths: [],
        constraints: [],
        goal_intention: "Write and publish a real novel.",
      },
      question_count: 1,
      next_question: "What kind of story do you want to publish first?",
      finished: false,
    });
    apiMock.answerBuddyClarification.mockResolvedValue({
      session_id: "session-1",
      question_count: 2,
      next_question: "",
      finished: true,
      tightened: false,
      candidate_directions: [
        "Build a durable writing lane.",
        "Launch a small publishing business.",
      ],
      recommended_direction: "Build a durable writing lane.",
    });
    apiMock.confirmBuddyDirection.mockResolvedValue({
      session: {
        session_id: "session-1",
        profile_id: "profile-1",
        status: "confirmed",
        question_count: 2,
        candidate_directions: ["Build a durable writing lane."],
        recommended_direction: "Build a durable writing lane.",
        selected_direction: "Build a durable writing lane.",
      },
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-1",
        primary_direction: "Build a durable writing lane.",
        why_now: "Turn writing into steady output.",
        success_picture: "Publish consistently.",
        first_checkpoint: "Finish a working draft.",
        first_loop_cycle_goal: "Write each week.",
        support_mode: "co-planning",
        progress_score: 0,
        confidence_score: 0.6,
      },
      execution_carrier: {
        carrier_id: "carrier-1",
        label: "Alex growth carrier",
        current_domain_id: "domain-writing",
        active_control_thread_id: "industry-chat:buddy:profile-1:domain-writing:execution-core",
        team_generated: true,
      },
    });

    render(<BuddyOnboardingPage />);

    fireEvent.change(await screen.findByTestId("buddy-identity-display-name"), {
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

    expect(
      await screen.findByText("What kind of story do you want to publish first?"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("buddy-clarification-answer"), {
      target: { value: "I want a consistent writing lane first." },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    expect(await screen.findByTestId("buddy-direction-confirm")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));
    expect(await screen.findByTestId("buddy-transition-confirm")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));
    expect(await screen.findByTestId("buddy-name-input")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-step-back"));

    expect(await screen.findByTestId("buddy-transition-confirm")).toBeInTheDocument();
    expect(screen.queryByTestId("buddy-name-input")).not.toBeInTheDocument();
  });
});
