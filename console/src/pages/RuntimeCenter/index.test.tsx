// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RuntimeCenterPage from "./index";

const mockNavigate = vi.fn();
const mockOpenDetail = vi.fn();
const useRuntimeCenterMock = vi.fn();

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
  };
});

vi.mock("./useRuntimeCenter", () => ({
  useRuntimeCenter: () => useRuntimeCenterMock(),
}));

function createRuntimeCenterState() {
  return {
    data: {
      generated_at: "2026-04-12T09:00:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service",
        note: "shared runtime surface",
      },
      cards: [
        {
          key: "tasks",
          title: "Tasks",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "active tasks",
          entries: [],
          meta: {},
        },
      ],
    },
    loading: false,
    refreshing: false,
    error: null,
    buddySummary: {
      buddy_name: "伙伴",
      lifecycle_state: "active",
      presence_state: "online",
      mood_state: "steady",
      evolution_stage: "协作期",
      growth_level: 3,
      intimacy: 72,
      affinity: 75,
      current_goal_summary: "把本周推进收口成清晰结果",
      current_task_summary: "先看主脑汇总，再决定是否插手",
      why_now_summary: "今天已经有新汇报回流，需要主脑收口",
      single_next_action_summary: "先看待处理事项",
      companion_strategy_summary: "主脑先汇总，再只把必须你拍板的事推给你",
    },
    mainBrainData: {
      generated_at: "2026-04-12T09:05:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service",
        note: "shared runtime surface",
      },
      strategy: {
        title: "稳定推进本周核心任务",
        summary: "主脑负责统筹安排、盯进度、收结果。",
      },
      carrier: {
        industry_instance_id: "industry-1",
        label: "Northwind",
        route: "/api/runtime-center/industry/industry-1",
      },
      lanes: [],
      cycles: [],
      backlog: [
        {
          backlog_item_id: "backlog-1",
          title: "补齐今日交付说明",
          summary: "先把关键说明补齐，再推下一步。",
        },
      ],
      current_cycle: {
        title: "今日推进",
        summary: "把今天的工作收成能看懂的结果",
      },
      main_brain_planning: {},
      assignments: [
        {
          assignment_id: "assignment-1",
          owner_agent_id: "agent-ops-1",
          title: "整理交付证据",
          summary: "把今天的交付结果整理成用户能看的说明。",
          status: "running",
        },
      ],
      reports: [
        {
          report_id: "report-1",
          owner_agent_id: "agent-ops-1",
          headline: "交付整理进行中",
          summary: "已完成一半，还差最后确认。",
          result: "running",
          needs_followup: true,
          updated_at: "2026-04-12T08:40:00Z",
        },
      ],
      report_cognition: {
        needs_replan: true,
        replan_reasons: ["还有一个待你决定的确认项。"],
        next_action: {
          title: "先处理待确认事项",
          summary: "主脑先把待确认项拿到你面前。",
        },
      },
      environment: {
        staffing: { pending_confirmation_count: 1 },
        human_assist: { blocked_count: 0 },
      },
      governance: {
        pending_decisions: 1,
        pending_patches: 0,
        summary: "还有一个确认项未处理。",
      },
      recovery: {},
      automation: {},
      evidence: {
        count: 2,
        summary: "今天新增 2 条证据。",
        route: null,
        entries: [],
        meta: {},
      },
      decisions: {
        count: 1,
        summary: "一个待处理决策",
        route: null,
        entries: [
          {
            id: "decision-1",
            title: "是否现在发给用户",
            summary: "先确认是否立刻发送。",
            created_at: "2026-04-12T08:45:00Z",
            status: "pending",
          },
        ],
        meta: {},
      },
      patches: {
        count: 0,
        summary: "",
        route: null,
        entries: [],
        meta: {},
      },
      signals: {},
      meta: { control_chain: [] },
      cockpit: null,
    },
    mainBrainLoading: false,
    mainBrainError: null,
    mainBrainUnavailable: false,
    businessAgents: [
      {
        agent_id: "agent-ops-1",
        name: "小运营",
        role_name: "运营",
        role_summary: "负责整理交付内容、跟进结果、回传进度。",
        agent_class: "business",
        status: "running",
        current_focus: "整理交付证据",
        industry_role_id: "ops-seat",
      },
    ],
    businessAgentsLoading: false,
    businessAgentsError: null,
    busyActionId: null,
    detail: null,
    detailLoading: false,
    detailError: null,
    reload: vi.fn(),
    invokeAction: vi.fn(),
    openDetail: mockOpenDetail,
    closeDetail: vi.fn(),
  };
}

describe("RuntimeCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defaults to main brain and hides legacy top-level admin tabs", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());

    render(<RuntimeCenterPage />);

    expect(screen.getByRole("button", { name: /伙伴 主脑/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "审批" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "治理" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "恢复" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "自动化" })).not.toBeInTheDocument();
  });

  it("switches to the selected professional agent panel", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());

    render(<RuntimeCenterPage />);

    fireEvent.click(screen.getByRole("button", { name: /小运营 运营/i }));

    expect(screen.getByRole("tab", { name: "简介" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日报" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "统计" })).toBeInTheDocument();
    expect(screen.getByText("主要负责工作")).toBeInTheDocument();
    expect(screen.getByText("负责整理交付内容、跟进结果、回传进度。")).toBeInTheDocument();
  });

  it("surfaces latest evidence artifact and replay counts in the main-brain summary", () => {
    const state: any = createRuntimeCenterState();
    state.mainBrainData.evidence = {
      count: 2,
      summary: "今天新增 2 条证据。",
      route: "/api/runtime-center/evidence/evidence-1",
      entries: [
        {
          id: "evidence-1",
          title: "Write report file",
          summary: "已将运营日报写成实际文件。",
          created_at: "2026-04-12T08:55:00Z",
          route: "/api/runtime-center/evidence/evidence-1",
          meta: {
            artifact_count: 2,
            replay_count: 1,
          },
        },
      ],
      meta: {},
    };
    useRuntimeCenterMock.mockReturnValue(state);

    render(<RuntimeCenterPage />);

    expect(screen.getByText("最新证据")).toBeInTheDocument();
    expect(screen.getByText("已将运营日报写成实际文件。")).toBeInTheDocument();
    expect(screen.getByText("产物 2 | 回放 1")).toBeInTheDocument();
  });

  it("uses detail-only latest evidence copy in the main-brain summary", () => {
    const state: any = createRuntimeCenterState();
    state.mainBrainData.evidence = {
      count: 1,
      summary: "今天新增 1 条证据。",
      route: "/api/runtime-center/evidence/evidence-2",
      entries: [
        {
          id: "evidence-2",
          detail: "实际文件已经落到工作区。",
          created_at: "2026-04-12T08:58:00Z",
          route: "/api/runtime-center/evidence/evidence-2",
        },
      ],
      meta: {},
    };
    useRuntimeCenterMock.mockReturnValue(state);

    render(<RuntimeCenterPage />);

    expect(screen.getByText("最新证据")).toBeInTheDocument();
    expect(screen.getByText("实际文件已经落到工作区。")).toBeInTheDocument();
  });

  it("falls back to section-level evidence artifact and replay counts", () => {
    const state: any = createRuntimeCenterState();
    state.mainBrainData.evidence = {
      count: 2,
      summary: "今天新增 2 条证据。",
      route: "/api/runtime-center/evidence/evidence-3",
      entries: [],
      meta: {
        artifact_count: 2,
        replay_count: 1,
      },
    };
    useRuntimeCenterMock.mockReturnValue(state);

    render(<RuntimeCenterPage />);

    expect(screen.getByText("最新证据")).toBeInTheDocument();
    expect(screen.getByText("今天新增 2 条证据。")).toBeInTheDocument();
    expect(screen.getByText("产物 2 | 回放 1")).toBeInTheDocument();
  });

  it("prefers backend cockpit content when the formal cockpit payload is present", () => {
    const state: any = createRuntimeCenterState();
    state.mainBrainData.cockpit = {
      main_brain: {
        card: {
          id: "main-brain",
          name: "伙伴",
          role: "主脑",
          status: "reviewing",
          progress: 86,
          needs_attention: true,
          is_main_brain: true,
        },
        summary_fields: [{ label: "职责", value: "后端正式主脑摘要" }],
        morning_report: {
          title: "早报",
          items: ["后端正式主脑早报"],
        },
        evening_report: null,
        trend: [],
        trace: [
          {
            timestamp: "2026-04-16T09:20:00Z",
            level: "warn",
            message: "后端正式主脑追溯",
            route: "/api/runtime-center/decisions/decision-1",
          },
        ],
        approvals: [],
        stage_summary: null,
      },
      agents: [
        {
          agent_id: "agent-ops-1",
          card: {
            id: "agent-ops-1",
            name: "后端运营",
            role: "运营",
            status: "running",
            progress: 92,
            needs_attention: false,
          },
          summary_fields: [{ label: "职责", value: "后端正式运营摘要" }],
          morning_report: {
            title: "早报",
            items: ["后端正式运营早报"],
          },
          evening_report: null,
          trend: [],
          trace: [
            {
              timestamp: "2026-04-16T09:10:00Z",
              level: "info",
              message: "后端正式运营追溯",
            },
          ],
        },
      ],
    };
    useRuntimeCenterMock.mockReturnValue(state);

    render(<RuntimeCenterPage />);

    expect(screen.getByText("后端正式主脑摘要")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "追溯" }));
    expect(screen.getByText("后端正式主脑追溯")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /后端运营 运营/i }));

    expect(screen.getByText("后端正式运营摘要")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "追溯" }));
    expect(screen.getByText("后端正式运营追溯")).toBeInTheDocument();
  });

  it("uses the latest legacy agent assignment in summary and morning report when cockpit payload is absent", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-12T10:00:00Z"));
    try {
      const state: any = createRuntimeCenterState();
      state.businessAgents[0].current_focus = null;
      state.mainBrainData.assignments = [
        {
          assignment_id: "assignment-older",
          owner_agent_id: "agent-ops-1",
          title: "旧派工标题",
          summary: "旧派工摘要",
          status: "running",
          updated_at: "2026-04-12T08:00:00Z",
        },
        {
          assignment_id: "assignment-latest",
          owner_agent_id: "agent-ops-1",
          title: "新派工标题",
          summary: "最新派工摘要",
          status: "running",
          updated_at: "2026-04-12T09:30:00Z",
        },
      ];
      state.mainBrainData.reports = [];
      useRuntimeCenterMock.mockReturnValue(state);

      render(<RuntimeCenterPage />);

      fireEvent.click(screen.getByRole("button", { name: /小运营 运营/i }));
      expect(screen.getByText("最新派工摘要")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("tab", { name: "日报" }));
      expect(screen.getByText("最新派工摘要")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("uses the latest legacy main-brain report in the evening report when cockpit payload is absent", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-12T20:00:00Z"));
    try {
      const state: any = createRuntimeCenterState();
      state.mainBrainData.reports = [
        {
          report_id: "report-older",
          owner_agent_id: "agent-ops-1",
          headline: "较早汇报",
          summary: "较早汇报摘要",
          result: "running",
          updated_at: "2026-04-12T08:40:00Z",
        },
        {
          report_id: "report-latest",
          owner_agent_id: "agent-ops-1",
          headline: "最新汇报",
          summary: "最新汇报摘要",
          result: "completed",
          updated_at: "2026-04-12T09:40:00Z",
        },
      ];
      useRuntimeCenterMock.mockReturnValue(state);

      render(<RuntimeCenterPage />);

      fireEvent.click(screen.getByRole("tab", { name: "日报" }));
      expect(screen.getByText("最新汇报")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
