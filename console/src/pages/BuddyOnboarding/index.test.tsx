// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetBuddyProfileBindingForTests } from "../../runtime/buddyProfileBinding";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddyEntry: vi.fn(),
    getBuddySurface: vi.fn(),
    submitBuddyIdentity: vi.fn(),
    submitBuddyContract: vi.fn(),
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

describe("BuddyOnboardingPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
    resetBuddyProfileBindingForTests();
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "start-onboarding",
      profile_id: null,
      session_id: null,
    });
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

  it("submits identity and renders a fixed collaboration contract form", async () => {
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
      status: "contract-draft",
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
    expect(await screen.findByTestId("buddy-contract-form")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-contract-service-intent")).toBeInTheDocument();
    expect(screen.queryByTestId("buddy-clarification-submit")).not.toBeInTheDocument();
  });

  it("submits contract, shows contract summary, and opens runtime chat after naming", async () => {
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
      status: "contract-draft",
    });
    apiMock.submitBuddyContract.mockResolvedValue({
      session_id: "session-1",
      status: "contract-ready",
      service_intent: "Help me build a durable writing rhythm.",
      collaboration_role: "orchestrator",
      autonomy_level: "guarded-proactive",
      confirm_boundaries: ["external spend"],
      report_style: "decision-first",
      collaboration_notes: "Keep reports concise.",
      candidate_directions: [
        "Build a durable writing lane.",
        "Launch a small publishing business.",
      ],
      recommended_direction: "Build a durable writing lane.",
      final_goal: "Publish the first real novel.",
      why_it_matters: "Turn writing into real proof-of-work.",
      backlog_items: [
        {
          lane_hint: "growth-focus",
          title: "Lock the publishing rhythm",
          summary: "Choose the first cadence.",
          priority: 3,
          source_key: "publishing-rhythm",
        },
      ],
    });
    apiMock.startBuddyConfirmDirection.mockResolvedValue({
      session_id: "session-1",
      profile_id: "profile-1",
      operation_id: "op-confirm-1",
      operation_kind: "confirm",
      operation_status: "running",
    });
    apiMock.getBuddySurface.mockResolvedValue({
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
          service_intent: "Help me build a durable writing rhythm.",
          collaboration_role: "orchestrator",
          autonomy_level: "guarded-proactive",
          confirm_boundaries: ["external spend"],
          report_style: "decision-first",
          collaboration_notes: "Keep reports concise.",
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
        presentation: {
          profile_id: "profile-1",
          buddy_name: "",
          lifecycle_state: "active",
          presence_state: "present",
          mood_state: "focused",
          current_form: "carrier",
          rarity: "common",
          current_goal_summary: "Publish the first real novel.",
          current_task_summary: "Lock the first publishing rhythm.",
          why_now_summary: "Turn writing into real proof-of-work.",
          single_next_action_summary: "Choose the first cadence.",
          companion_strategy_summary: "Push one durable writing lane.",
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
          status: "confirmed",
          operation_id: "op-confirm-1",
          operation_kind: "confirm",
          operation_status: "succeeded",
          operation_error: "",
          service_intent: "Help me build a durable writing rhythm.",
          collaboration_role: "orchestrator",
          autonomy_level: "guarded-proactive",
          confirm_boundaries: ["external spend"],
          report_style: "decision-first",
          collaboration_notes: "Keep reports concise.",
          candidate_directions: ["Build a durable writing lane."],
          recommended_direction: "Build a durable writing lane.",
          selected_direction: "Build a durable writing lane.",
          requires_direction_confirmation: false,
          requires_naming: true,
          completed: false,
        },
      });
    apiMock.nameBuddy.mockResolvedValue({
      buddy_name: "Nova",
      profile_id: "profile-1",
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

    expect(await screen.findByTestId("buddy-contract-form")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("buddy-contract-service-intent"), {
      target: { value: "Help me build a durable writing rhythm." },
    });
    fireEvent.click(screen.getByTestId("buddy-contract-submit"));

    await waitFor(() => {
      expect(apiMock.submitBuddyContract).toHaveBeenCalledWith({
        session_id: "session-1",
        service_intent: "Help me build a durable writing rhythm.",
        collaboration_role: "orchestrator",
        autonomy_level: "proactive",
        confirm_boundaries: [],
        report_style: "result-first",
        collaboration_notes: "",
      });
    });
    expect(await screen.findByTestId("buddy-contract-summary")).toBeInTheDocument();
    expect(screen.getByText("Publish the first real novel.")).toBeInTheDocument();

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
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    });
    expect(await screen.findByTestId("buddy-name-input")).toBeInTheDocument();

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
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "chat-ready",
      profile_id: "profile-existing",
      session_id: null,
      profile_display_name: "Existing",
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
    });

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith("profile-existing");
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

  it("shows backend preview detail when the selected alternate direction needs additional handling", async () => {
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
      status: "contract-draft",
    });
    apiMock.submitBuddyContract.mockResolvedValue({
      session_id: "session-1",
      status: "contract-ready",
      service_intent: "Help me build a durable writing rhythm.",
      collaboration_role: "orchestrator",
      autonomy_level: "guarded-proactive",
      confirm_boundaries: ["external spend"],
      report_style: "decision-first",
      collaboration_notes: "Keep reports concise.",
      candidate_directions: [
        "Build a durable writing lane.",
        "Launch a small publishing business.",
      ],
      recommended_direction: "Build a durable writing lane.",
      final_goal: "Publish the first real novel.",
      why_it_matters: "Turn writing into real proof-of-work.",
      backlog_items: [
        {
          lane_hint: "growth-focus",
          title: "Lock the publishing rhythm",
          summary: "Choose the first cadence.",
          priority: 3,
          source_key: "publishing-rhythm",
        },
      ],
    });
    apiMock.previewBuddyDirectionTransition.mockRejectedValue({
      status: 400,
      detail: "当前所选主方向需要重新编译协作合同后才能确认。",
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

    expect(await screen.findByTestId("buddy-contract-form")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("buddy-contract-service-intent"), {
      target: { value: "Help me build a durable writing rhythm." },
    });
    fireEvent.click(screen.getByTestId("buddy-contract-submit"));

    expect(await screen.findByTestId("buddy-contract-summary")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Launch a small publishing business."));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    expect(
      await screen.findByText("当前所选主方向需要重新编译协作合同后才能确认。"),
    ).toBeInTheDocument();
  });
});
