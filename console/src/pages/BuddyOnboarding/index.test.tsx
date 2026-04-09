// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetBuddyProfileBindingForTests } from "../../runtime/buddyProfileBinding";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddySurface: vi.fn(),
    submitBuddyIdentity: vi.fn(),
    answerBuddyClarification: vi.fn(),
    previewBuddyDirectionTransition: vi.fn(),
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

describe("BuddyOnboardingPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    resetBuddyProfileBindingForTests();
    apiMock.getBuddySurface.mockRejectedValue({ status: 404 });
    apiMock.submitBuddyIdentity.mockResolvedValue({
      session_id: "session-1",
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
      },
      question_count: 1,
      next_question: "你最想真正改变的人生部分是什么？",
      finished: false,
    });
    apiMock.answerBuddyClarification.mockResolvedValue({
      session_id: "session-1",
      question_count: 9,
      tightened: true,
      finished: true,
      next_question: "",
      candidate_directions: [
        "建立独立创作与内容事业的长期成长路径",
        "建立稳定、自主、长期向上的人生成长主方向",
      ],
      recommended_direction: "建立独立创作与内容事业的长期成长路径",
    });
    apiMock.previewBuddyDirectionTransition.mockResolvedValue({
      session_id: "session-1",
      selected_direction: "寤虹珛鐙珛鍒涗綔涓庡唴瀹逛簨涓氱殑闀挎湡鎴愰暱璺緞",
      selected_domain_key: "writing",
      suggestion_kind: "start-new-domain",
      recommended_action: "start-new",
      reason_summary: "start new",
      archived_matches: [],
      current_domain: null,
    });
    apiMock.confirmBuddyDirection.mockResolvedValue({
      session: {
        session_id: "session-1",
        profile_id: "profile-1",
        status: "confirmed",
        question_count: 9,
        candidate_directions: [
          "建立独立创作与内容事业的长期成长路径",
        ],
        recommended_direction: "建立独立创作与内容事业的长期成长路径",
        selected_direction: "建立独立创作与内容事业的长期成长路径",
      },
      growth_target: {
        primary_direction: "建立独立创作与内容事业的长期成长路径",
      },
      relationship: { encouragement_style: "old-friend" },
      execution_carrier: {
        instance_id: "buddy:profile-1:domain-writing",
        label: "Alex 的成长载体",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id: "industry-chat:buddy:profile-1:domain-writing:execution-core",
        control_thread_id: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      },
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

  it("shows a visible completion state after direction confirmation before routing into chat naming flow", async () => {
    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("你希望我怎么称呼你？"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByPlaceholderText("你现在主要在做什么？"), {
      target: { value: "设计师" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：探索期、转型期、重建期、稳定增长期"), {
      target: { value: "转型期" },
    });
    fireEvent.change(screen.getByPlaceholderText("先说你隐约想改变什么，模糊也没有关系。"), {
      target: { value: "我想建立真正长期的方向。" },
    });

    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("用最真实的话回答我，不用写得很工整。"), {
      target: { value: "我想拥有杠杆和独立性。" },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(apiMock.answerBuddyClarification).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("buddy-direction-recommendation")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/建立独立创作与内容事业的长期成长路径/));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(apiMock.previewBuddyDirectionTransition).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "session-1",
          selected_direction: expect.stringContaining("建立独立创作"),
        }),
      );
    });
    expect(apiMock.confirmBuddyDirection).not.toHaveBeenCalled();
    expect(screen.getByTestId("buddy-transition-choice-panel")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-transition-scope-note")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));

    await waitFor(() => {
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "session-1",
          selected_direction: expect.stringContaining("建立独立创作"),
          capability_action: "start-new",
        }),
      );
    });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("buddy-direction-confirmed")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-direction-enter-chat"));

    await waitFor(() => {
      expect(runtimeChatMock.buildBuddyExecutionCarrierChatBinding).toHaveBeenCalledWith({
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
    expect(navigateMock).not.toHaveBeenCalledWith(
      "/chat?buddy_session=session-1&buddy_profile=profile-1",
      { replace: true },
    );
  });

  it("reuses an already bound buddy profile before showing onboarding", async () => {
    apiMock.getBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-existing",
        display_name: "Existing",
      },
      execution_carrier: {
        instance_id: "buddy:profile-existing",
        label: "Existing 的成长载体",
        owner_scope: "profile-existing",
        current_cycle_id: "cycle-existing",
        team_generated: true,
        thread_id: "industry-chat:buddy:profile-existing:execution-core",
        control_thread_id: "industry-chat:buddy:profile-existing:execution-core",
        chat_binding: {
          thread_id: "industry-chat:buddy:profile-existing:execution-core",
          control_thread_id: "industry-chat:buddy:profile-existing:execution-core",
          channel: "console",
          binding_kind: "buddy-execution-carrier",
        },
      },
      growth: {
        growth_level: 1,
        intimacy: 0,
        affinity: 0,
        knowledge_value: 0,
        skill_value: 0,
        pleasant_interaction_score: 0,
        communication_count: 0,
        companion_experience: 0,
        completed_support_runs: 0,
        completed_assisted_closures: 0,
        evolution_stage: "seed",
        progress_to_next_stage: 0,
      },
      presentation: {
        profile_id: "profile-existing",
        buddy_name: "小澜",
        lifecycle_state: "bonded",
        presence_state: "available",
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
        session_id: "session-existing",
        status: "named",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: [
          "建立独立创作与内容事业的长期成长路径",
        ],
        recommended_direction: "建立独立创作与内容事业的长期成长路径",
        selected_direction: "建立独立创作与内容事业的长期成长路径",
        requires_direction_confirmation: false,
        requires_naming: false,
        completed: true,
      },
    });
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-existing");

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-existing");
    });
    expect(runtimeChatMock.buildBuddyExecutionCarrierChatBinding).toHaveBeenCalledWith({
      sessionId: null,
      profileId: "profile-existing",
      profileDisplayName: "Existing",
      executionCarrier: expect.objectContaining({
        instance_id: "buddy:profile-existing",
        owner_scope: "profile-existing",
        current_cycle_id: "cycle-existing",
      }),
      entrySource: "buddy-onboarding-resume",
    });
    expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
      expect.any(Object),
      navigateMock,
      expect.objectContaining({
        shouldNavigate: expect.any(Function),
      }),
    );
    expect(navigateMock).not.toHaveBeenCalledWith(
      "/chat?buddy_profile=profile-existing",
      { replace: true },
    );
  });

  it("does not skip onboarding when the bound buddy profile is still incomplete", async () => {
    apiMock.getBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-incomplete",
        display_name: "半完成",
        profession: "运营",
        current_stage: "探索期",
        interests: [],
        strengths: [],
        constraints: [],
        goal_intention: "我想找到自己的方向。",
      },
      growth_target: null,
      relationship: null,
      growth: {
        growth_level: 1,
        intimacy: 0,
        affinity: 0,
        knowledge_value: 0,
        skill_value: 0,
        pleasant_interaction_score: 0,
        communication_count: 0,
        companion_experience: 0,
        completed_support_runs: 0,
        completed_assisted_closures: 0,
        evolution_stage: "seed",
        progress_to_next_stage: 0,
      },
      presentation: {
        profile_id: "profile-incomplete",
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
      onboarding: {
        session_id: "session-incomplete",
        status: "clarifying",
        question_count: 4,
        tightened: false,
        next_question: "你最不想继续重复的旧状态是什么？",
        candidate_directions: [],
        recommended_direction: "",
        selected_direction: "",
        requires_direction_confirmation: false,
        requires_naming: false,
        completed: false,
      },
    });
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-incomplete");

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-incomplete");
    });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByText("超级伙伴初次建档")).toBeInTheDocument();
    expect(
      screen.getByText("你最不想继续重复的旧状态是什么？"),
    ).toBeInTheDocument();
  });

  it("routes incomplete-but-confirmed buddy profiles into chat naming flow", async () => {
    apiMock.getBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-needs-name",
        display_name: "待命名",
        profession: "运营",
        current_stage: "探索期",
        interests: [],
        strengths: [],
        constraints: [],
        goal_intention: "我想找到自己的方向。",
      },
      growth_target: {
        target_id: "target-1",
        profile_id: "profile-needs-name",
        primary_direction: "建立稳定、自主、长期向上的人生成长主方向",
        final_goal: "帮助待命名建立真正属于自己的长期成长方向与自主掌控感",
        why_it_matters: "因为这条方向会改变接下来几年的人生轨迹。",
        current_cycle_label: "Cycle 1",
      },
      relationship: {
        relationship_id: "relationship-1",
        profile_id: "profile-needs-name",
        buddy_name: "",
        encouragement_style: "old-friend",
      },
      execution_carrier: {
        instance_id: "buddy:profile-needs-name",
        label: "待命名 的成长载体",
        owner_scope: "profile-needs-name",
        current_cycle_id: "cycle-needs-name",
        team_generated: true,
        thread_id: "industry-chat:buddy:profile-needs-name:execution-core",
        control_thread_id: "industry-chat:buddy:profile-needs-name:execution-core",
        chat_binding: {
          thread_id: "industry-chat:buddy:profile-needs-name:execution-core",
          control_thread_id: "industry-chat:buddy:profile-needs-name:execution-core",
          channel: "console",
          binding_kind: "buddy-execution-carrier",
        },
      },
      growth: {
        growth_level: 1,
        intimacy: 0,
        affinity: 0,
        knowledge_value: 0,
        skill_value: 0,
        pleasant_interaction_score: 0,
        communication_count: 0,
        companion_experience: 0,
        completed_support_runs: 0,
        completed_assisted_closures: 0,
        evolution_stage: "seed",
        progress_to_next_stage: 0,
      },
      presentation: {
        profile_id: "profile-needs-name",
        buddy_name: "你的伙伴",
        lifecycle_state: "born-unnamed",
        presence_state: "attentive",
        mood_state: "warm",
        current_form: "seed",
        rarity: "common",
        current_goal_summary: "建立稳定、自主、长期向上的人生成长主方向",
        current_task_summary: "",
        why_now_summary: "",
        single_next_action_summary: "",
        companion_strategy_summary: "",
      },
      onboarding: {
        session_id: "session-needs-name",
        status: "confirmed",
        question_count: 9,
        tightened: true,
        next_question: "",
        candidate_directions: [
          "建立稳定、自主、长期向上的人生成长主方向",
        ],
        recommended_direction: "建立稳定、自主、长期向上的人生成长主方向",
        selected_direction: "建立稳定、自主、长期向上的人生成长主方向",
        requires_direction_confirmation: false,
        requires_naming: true,
        completed: false,
      },
    });
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-needs-name");

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-needs-name");
    });
    expect(runtimeChatMock.buildBuddyExecutionCarrierChatBinding).toHaveBeenCalledWith({
      sessionId: "session-needs-name",
      profileId: "profile-needs-name",
      profileDisplayName: "待命名",
      executionCarrier: expect.objectContaining({
        instance_id: "buddy:profile-needs-name",
        owner_scope: "profile-needs-name",
        current_cycle_id: "cycle-needs-name",
      }),
      entrySource: "buddy-onboarding-resume",
    });
    expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      }),
      navigateMock,
      expect.objectContaining({
        shouldNavigate: expect.any(Function),
      }),
    );
    expect(navigateMock).not.toHaveBeenCalledWith(
      "/chat?buddy_session=session-needs-name&buddy_profile=profile-needs-name",
      { replace: true },
    );
  });

  it("shows a clean fallback error when entering chat from the execution carrier fails", async () => {
    runtimeChatMock.openRuntimeChat.mockRejectedValue(new Error("runtime unavailable"));

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("你希望我怎么称呼你？"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByPlaceholderText("你现在主要在做什么？"), {
      target: { value: "设计师" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：探索期、转型期、重建期、稳定增长期"), {
      target: { value: "转型期" },
    });
    fireEvent.change(screen.getByPlaceholderText("先说你隐约想改变什么，模糊也没有关系。"), {
      target: { value: "我想建立真正长期的方向。" },
    });
    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("用最真实的话回答我，不用写得很工整。"), {
      target: { value: "我想拥有杠杆和独立性。" },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(apiMock.answerBuddyClarification).toHaveBeenCalled();
    });

    fireEvent.click(
      screen.getByLabelText(/建立独立创作与内容事业的长期成长路径/),
    );
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(apiMock.previewBuddyDirectionTransition).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "session-1",
          selected_direction: expect.stringContaining("建立独立创作"),
        }),
      );
    });
    expect(apiMock.confirmBuddyDirection).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));

    await waitFor(() => {
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "session-1",
          selected_direction: expect.stringContaining("建立独立创作"),
          capability_action: "start-new",
        }),
      );
    });

    fireEvent.click(screen.getByTestId("buddy-direction-enter-chat"));

    await waitFor(() => {
      expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalled();
    });
    expect(screen.getByText("runtime unavailable")).toBeInTheDocument();
  });

  it("lets the user explicitly keep the active domain capability", async () => {
    apiMock.previewBuddyDirectionTransition.mockResolvedValueOnce({
      session_id: "session-1",
      selected_direction: "股票赚 100 万",
      selected_domain_key: "stocks",
      suggestion_kind: "same-domain",
      recommended_action: "keep-active",
      reason_summary: "same domain",
      current_domain: {
        domain_id: "domain-stock",
        domain_key: "stocks",
        domain_label: "股票",
        status: "active",
        capability_points: 38,
        capability_score: 38,
        evolution_stage: "bonded",
      },
      archived_matches: [
        {
          domain_id: "domain-writing",
          domain_key: "writing",
          domain_label: "写作",
          status: "archived",
          capability_points: 26,
          capability_score: 26,
          evolution_stage: "bonded",
        },
      ],
    });

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("你希望我怎么称呼你？"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByPlaceholderText("你现在主要在做什么？"), {
      target: { value: "交易员" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：探索期、转型期、重建期、稳定增长期"), {
      target: { value: "放大期" },
    });
    fireEvent.change(screen.getByPlaceholderText("先说你隐约想改变什么，模糊也没有关系。"), {
      target: { value: "我想把股票体系做大。" },
    });
    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalled();
    });

    apiMock.answerBuddyClarification.mockResolvedValueOnce({
      session_id: "session-1",
      question_count: 9,
      tightened: true,
      finished: true,
      next_question: "",
      candidate_directions: ["股票赚 100 万"],
      recommended_direction: "股票赚 100 万",
    });

    fireEvent.change(screen.getByPlaceholderText("用最真实的话回答我，不用写得很工整。"), {
      target: { value: "我想在原有股票体系上做更大的目标。" },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(screen.getByLabelText("股票赚 100 万")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("股票赚 100 万"));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("buddy-transition-choice-panel")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText("继续当前领域能力"));
    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));

    await waitFor(() => {
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalledWith(
        expect.objectContaining({
          capability_action: "keep-active",
          target_domain_id: undefined,
        }),
      );
    });
  });

  it("lets the user explicitly restore an archived domain capability", async () => {
    apiMock.previewBuddyDirectionTransition.mockResolvedValueOnce({
      session_id: "session-1",
      selected_direction: "写作副业变现",
      selected_domain_key: "writing",
      suggestion_kind: "switch-to-archived-domain",
      recommended_action: "restore-archived",
      reason_summary: "restore archived",
      current_domain: {
        domain_id: "domain-stock",
        domain_key: "stocks",
        domain_label: "股票",
        status: "active",
        capability_points: 41,
        capability_score: 41,
        evolution_stage: "capable",
      },
      archived_matches: [
        {
          domain_id: "domain-writing",
          domain_key: "writing",
          domain_label: "写作",
          status: "archived",
          capability_points: 52,
          capability_score: 52,
          evolution_stage: "capable",
        },
      ],
    });

    render(<BuddyOnboardingPage />);

    await waitFor(() => {
      expect(apiMock.getBuddySurface).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText("你希望我怎么称呼你？"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByPlaceholderText("你现在主要在做什么？"), {
      target: { value: "写作者" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：探索期、转型期、重建期、稳定增长期"), {
      target: { value: "重启期" },
    });
    fireEvent.change(screen.getByPlaceholderText("先说你隐约想改变什么，模糊也没有关系。"), {
      target: { value: "我想回到写作这条线。" },
    });
    fireEvent.submit(screen.getByTestId("buddy-identity-form"));

    await waitFor(() => {
      expect(apiMock.submitBuddyIdentity).toHaveBeenCalled();
    });

    apiMock.answerBuddyClarification.mockResolvedValueOnce({
      session_id: "session-1",
      question_count: 9,
      tightened: true,
      finished: true,
      next_question: "",
      candidate_directions: ["写作副业变现"],
      recommended_direction: "写作副业变现",
    });

    fireEvent.change(screen.getByPlaceholderText("用最真实的话回答我，不用写得很工整。"), {
      target: { value: "我想把旧写作能力重新接回来。" },
    });
    fireEvent.click(screen.getByTestId("buddy-clarification-submit"));

    await waitFor(() => {
      expect(screen.getByLabelText("写作副业变现")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("写作副业变现"));
    fireEvent.click(screen.getByTestId("buddy-direction-confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("buddy-transition-choice-panel")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText("恢复历史领域能力"));
    fireEvent.click(screen.getByTestId("buddy-transition-confirm"));

    await waitFor(() => {
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalledWith(
        expect.objectContaining({
          capability_action: "restore-archived",
          target_domain_id: "domain-writing",
        }),
      );
    });
  });
});
