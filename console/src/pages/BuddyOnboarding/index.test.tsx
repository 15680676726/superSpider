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
    confirmBuddyDirection: vi.fn(),
  },
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
    apiMock.confirmBuddyDirection.mockResolvedValue({
      session: {
        session_id: "session-1",
        profile_id: "profile-1",
        status: "confirmed",
        question_count: 9,
        candidate_directions: [
          "寤虹珛鐙珛鍒涗綔涓庡唴瀹逛簨涓氱殑闀挎湡鎴愰暱璺緞",
        ],
        recommended_direction: "寤虹珛鐙珛鍒涗綔涓庡唴瀹逛簨涓氱殑闀挎湡鎴愰暱璺緞",
        selected_direction: "寤虹珛鐙珛鍒涗綔涓庡唴瀹逛簨涓氱殑闀挎湡鎴愰暱璺緞",
      },
      growth_target: {
        primary_direction: "建立独立创作与内容事业的长期成长路径",
      },
      relationship: { encouragement_style: "old-friend" },
      execution_carrier: {
        instance_id: "buddy:profile-1",
        label: "Alex 的成长载体",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
      },
    });
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
      expect(apiMock.confirmBuddyDirection).toHaveBeenCalled();
    });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("buddy-direction-confirmed")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("buddy-direction-enter-chat"));

    expect(navigateMock).toHaveBeenCalledWith(
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
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith();
    });
    expect(navigateMock).toHaveBeenCalledWith(
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
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith();
    });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByText("Buddy 初次建档")).toBeInTheDocument();
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
      expect(apiMock.getBuddySurface).toHaveBeenCalledWith();
    });
    expect(navigateMock).toHaveBeenCalledWith(
      "/chat?buddy_session=session-needs-name&buddy_profile=profile-needs-name",
      { replace: true },
    );
  });
});
