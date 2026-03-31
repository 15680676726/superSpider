// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useCallback as reactUseCallback } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IndustryPage from "./index";
import { INDUSTRY_TEXT } from "./pageHelpers";

const mockNavigate = vi.fn();
const useIndustryPageStateMock = vi.fn();

(globalThis as { useCallback?: typeof reactUseCallback }).useCallback = reactUseCallback;

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
  };
});

vi.mock("./useIndustryPageState", () => ({
  useIndustryPageState: (...args: unknown[]) => useIndustryPageStateMock(...args),
}));

afterEach(() => {
  cleanup();
  mockNavigate.mockReset();
  useIndustryPageStateMock.mockReset();
});

function createPageState(overrides: Record<string, unknown> = {}) {
  const baseState = {
    allTeams: [
      {
        instance_id: "industry-1",
        bootstrap_kind: "industry-v1",
        label: "Demo Industry",
        summary: "Demo summary",
        owner_scope: "industry-demo",
        profile: {
          schema_version: "industry-profile-v1",
          industry: "demo",
          target_customers: [],
          channels: [],
          goals: [],
          constraints: [],
          experience_mode: "operator-guided",
          operator_requirements: [],
        },
        team: {
          schema_version: "industry-team-blueprint-v1",
          team_id: "team-1",
          label: "Demo Team",
          summary: "Demo Team",
          agents: [],
        },
        status: "active",
        updated_at: "2026-03-26T08:00:00Z",
        stats: {},
        routes: {},
      },
    ],
    bootstrapLoading: false,
    briefMediaBusy: false,
    briefMediaItems: [],
    briefMediaLink: "",
    briefModalOpen: false,
    briefUploadInputRef: { current: null },
    deletingInstanceId: null,
    detail: {
      instance_id: "industry-1",
      bootstrap_kind: "industry-v1",
      label: "Demo Industry",
      summary: "Demo summary",
      owner_scope: "industry-demo",
      profile: {
        schema_version: "industry-profile-v1",
        industry: "demo",
        target_customers: [],
        channels: [],
        goals: [],
        constraints: [],
        experience_mode: "operator-guided",
        operator_requirements: [],
      },
      team: {
        schema_version: "industry-team-blueprint-v1",
        team_id: "team-1",
        label: "Demo Team",
        summary: "Demo Team",
        agents: [],
      },
      status: "active",
      updated_at: "2026-03-26T08:00:00Z",
      stats: {
        agent_count: 3,
        goal_count: 9,
        schedule_count: 4,
        lane_count: 5,
        backlog_count: 6,
        assignment_count: 7,
      },
      routes: {},
      focus_selection: null,
      goals: [],
      agents: [],
      schedules: [],
      lanes: [],
      backlog: [],
      staffing: {
        pending_proposals: [],
        temporary_seats: [],
      },
      current_cycle: null,
      cycles: [],
      assignments: [],
      agent_reports: [],
      tasks: [],
      decisions: [],
      evidence: [],
      patches: [],
      growth: [],
      proposals: [],
      reports: {
        daily: {
          window: "daily",
          since: "2026-03-26T00:00:00Z",
          until: "2026-03-26T23:59:59Z",
          evidence_count: 0,
          proposal_count: 0,
          patch_count: 0,
          applied_patch_count: 0,
          growth_count: 0,
          decision_count: 0,
          recent_evidence: [],
          highlights: [],
        },
        weekly: {
          window: "weekly",
          since: "2026-03-20T00:00:00Z",
          until: "2026-03-26T23:59:59Z",
          evidence_count: 0,
          proposal_count: 0,
          patch_count: 0,
          applied_patch_count: 0,
          growth_count: 0,
          decision_count: 0,
          recent_evidence: [],
          highlights: [],
        },
      },
      media_analyses: [],
    },
    draftAgents: [],
    draftCounts: { roles: 0, goals: 0, schedules: 0 },
    draftGenerationSummary: "",
    draftGoals: [],
    draftSchedules: [],
    draftTeamLabel: "",
    draftTeamSummary: "",
    error: null,
    handleAddBriefMediaLink: vi.fn(),
    handleAddCustomInstallItem: vi.fn(),
    handleBootstrap: vi.fn(),
    handleBriefMediaModeChange: vi.fn(),
    handleBriefUploadChange: vi.fn(),
    handleChangeRecommendationReviewAcknowledgement: vi.fn(),
    handleChangeRecommendationTargets: vi.fn(),
    handleDeleteInstance: vi.fn(),
    handleClearRuntimeFocus: vi.fn(),
    handleOpenAgentReportChat: vi.fn(),
    handleOpenExecutionCoreChat: vi.fn(),
    handlePatchInstallPlanItem: vi.fn(),
    handlePreview: vi.fn(),
    handleRemoveBriefMediaItem: vi.fn(),
    handleRemoveInstallPlanItem: vi.fn(),
    handleSelectAssignmentFocus: vi.fn(),
    handleSelectBacklogFocus: vi.fn(),
    handleToggleRecommendation: vi.fn(),
    hasCapabilityPlanning: false,
    installPlan: [],
    installPlanByRecommendationId: {},
    isEditing: false,
    isEditingExistingTeam: false,
    loadInstanceIntoDraft: vi.fn(),
    loadInstances: vi.fn(),
    loadingDetail: false,
    loadingInstances: false,
    preview: null,
    previewLoading: false,
    recommendationById: {},
    recommendationDisplayGroups: [],
    recommendationWarnings: [],
    retiredInstances: [],
    roleOptions: [],
    selectedExecutionCoreRole: null,
    selectedInstanceId: "industry-1",
    selectedSummary: null,
    setBriefMediaLink: vi.fn(),
    setBriefModalOpen: vi.fn(),
    setDraftSourceInstanceId: vi.fn(),
    setError: vi.fn(),
    setPreview: vi.fn(),
    setSelectedInstanceId: vi.fn(),
    watchedExperienceMode: "operator-guided",
  } as const;

  const nextDetail =
    overrides.detail && typeof overrides.detail === "object"
      ? {
          ...baseState.detail,
          ...(overrides.detail as object),
        }
      : baseState.detail;

  return {
    ...baseState,
    ...overrides,
    detail: nextDetail,
  } as const;
}

describe("IndustryPage", () => {
  it("does not render deprecated goal counts in runtime detail stats", () => {
    useIndustryPageStateMock.mockReturnValue(createPageState());

    render(<IndustryPage />);

    expect(screen.getByText("Demo Team")).toBeTruthy();
    expect(
      screen.queryAllByText((_, node) =>
        node?.tagName.toLowerCase() === "span"
        && String(node.textContent || "").includes(`${INDUSTRY_TEXT.metricGoals} 9`),
      ),
    ).toHaveLength(0);
  });

  it("renders focused runtime surfaces with staffing visibility and report drill-down actions", () => {
    const handleClearRuntimeFocus = vi.fn();
    const handleOpenAgentReportChat = vi.fn();
    const handleSelectAssignmentFocus = vi.fn();
    const handleSelectBacklogFocus = vi.fn();

    useIndustryPageStateMock.mockReturnValue(
      createPageState({
        detail: {
          execution: {
            status: "active",
            current_focus: "generic-focus",
            current_owner: "Spider Mesh 主脑",
            current_risk: "guarded",
            evidence_count: 0,
            updated_at: "2026-03-27T09:30:00Z",
          },
          focus_selection: {
            selection_kind: "assignment",
            assignment_id: "assignment-1",
            title: "Assignment 1",
            summary: "Focused runtime assignment",
          },
          lanes: [
            {
              lane_id: "lane-growth",
              lane_key: "growth",
              title: "增长获客",
              summary: "跟进新增线索与转化动作。",
              status: "active",
              priority: 3,
              metadata: {},
            },
            {
              lane_id: "lane-fulfillment",
              lane_key: "fulfillment",
              title: "交付履约",
              summary: "盯住本周交付节奏与风险。",
              status: "queued",
              priority: 2,
              metadata: {},
            },
          ],
          current_cycle: {
            cycle_id: "cycle-1",
            cycle_kind: "weekly",
            title: "本周增长与交付协调",
            summary: "优先稳住履约，再补获客节奏。",
            status: "active",
            focus_lane_ids: ["lane-growth"],
            backlog_item_ids: ["backlog-1", "backlog-2"],
            assignment_ids: ["assignment-1", "assignment-2"],
            report_ids: ["report-1"],
            synthesis: {
              latest_findings: [
                {
                  report_id: "report-1",
                  headline: "Weekly handoff",
                  summary: "Need follow-up from the main brain.",
                  findings: [],
                  uncertainties: [],
                  needs_followup: true,
                  followup_reason: "Awaiting explicit approval",
                },
              ],
              conflicts: [],
              holes: [
                {
                  hole_id: "hole-1",
                  kind: "follow-up",
                  summary: "Weekend variance still lacks a validated cause.",
                },
              ],
              recommended_actions: [
                {
                  action_id: "action-1",
                  action_type: "staffing-follow-up",
                  title: "Approve closer staffing",
                  summary: "Approve closer seating for live follow-up.",
                },
              ],
              needs_replan: true,
              control_core_contract: ["synthesize-before-reassign"],
            },
          },
          staffing: {
            active_gap: {
              kind: "career-seat-proposal",
              target_role_name: "Closer",
              requested_surfaces: ["industry", "runtime-center"],
              requires_confirmation: true,
              reason: "Need closer coverage for live follow-up.",
              status: "waiting-resource",
            },
            pending_proposals: [
              {
                kind: "career-seat-proposal",
                target_role_name: "Closer",
                requested_surfaces: [],
                requires_confirmation: false,
                decision_request_id: "decision-1",
                status: "pending",
              },
            ],
            temporary_seats: [
              {
                role_id: "role-temp-copy",
                role_name: "Temp Copywriter",
                agent_id: "agent-temp-copy",
                status: "active",
                current_assignment: {
                  title: "Draft launch assets",
                },
              },
            ],
            researcher: {
              role_id: "role-researcher",
              role_name: "Researcher",
              agent_id: "agent-researcher",
              status: "active",
              pending_signal_count: 3,
              waiting_for_main_brain: true,
              current_assignment: {
                title: "Track competitor moves",
              },
              latest_report: {
                headline: "Signal pack",
              },
            },
          },
          backlog: [
            {
              backlog_item_id: "backlog-1",
              title: "Backlog 1",
              status: "open",
              priority: 1,
              source_kind: "chat-writeback",
              evidence_ids: [],
              metadata: {},
              selected: true,
              summary: "Selected backlog item",
            },
            {
              backlog_item_id: "backlog-2",
              title: "Backlog 2",
              status: "queued",
              priority: 2,
              source_kind: "strategy-writeback",
              evidence_ids: [],
              metadata: {},
              summary: "Next backlog item",
            },
          ],
          assignments: [
            {
              assignment_id: "assignment-1",
              title: "Assignment 1",
              status: "running",
              evidence_ids: [],
              metadata: {},
              selected: true,
              summary: "Selected assignment",
            },
            {
              assignment_id: "assignment-2",
              title: "Assignment 2",
              status: "queued",
              evidence_ids: [],
              metadata: {},
              summary: "Queued assignment",
            },
          ],
          agent_reports: [
            {
              report_id: "report-1",
              headline: "Weekly handoff",
              summary: "Need follow-up from the main brain.",
              report_kind: "summary",
              status: "recorded",
              result: "follow-up-needed",
              findings: ["Lead list updated"],
              uncertainties: [],
              recommendation: "Review handoff and approve the next step.",
              needs_followup: true,
              followup_reason: "Awaiting explicit approval",
              risk_level: "guarded",
              evidence_ids: [],
              decision_ids: [],
              processed: true,
              metadata: {},
              work_context_id: "ctx-report-1",
              assignment_id: "assignment-1",
            },
          ],
        },
        handleClearRuntimeFocus,
        handleOpenAgentReportChat,
        handleSelectAssignmentFocus,
        handleSelectBacklogFocus,
      }),
    );

    render(<IndustryPage />);

    expect(screen.getAllByText("已聚焦派工").length).toBeGreaterThan(0);
    const cockpitCard = screen.getByText("运行驾驶舱")
      .closest(".ant-card") as HTMLElement | null;
    expect(cockpitCard).toBeTruthy();
    expect(
      within(cockpitCard as HTMLElement).getByText("Focused runtime assignment"),
    ).toBeTruthy();
    expect(
      within(cockpitCard as HTMLElement).queryByText("generic-focus"),
    ).toBeNull();
    expect(screen.getByText("补位闭环")).toBeTruthy();
    expect(screen.getByText("统一运行链")).toBeTruthy();
    expect(screen.getByText("工作泳道")).toBeTruthy();
    expect(screen.getAllByText("增长获客").length).toBeGreaterThan(0);
    expect(screen.getByText("交付履约")).toBeTruthy();
    expect(screen.getByText("待处理提案")).toBeTruthy();
    expect(screen.getByText("临时席位")).toBeTruthy();
    expect(screen.getByText("研究位")).toBeTruthy();
    expect(screen.getByText("Approve closer staffing")).toBeTruthy();
    expect(screen.getByText("synthesize-before-reassign")).toBeTruthy();
    expect(screen.getAllByText("已选中").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ctx-report-1").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "查看完整面板" }));
    expect(handleClearRuntimeFocus).toHaveBeenCalledTimes(1);

    const backlogItemCard = screen.getByText("Backlog 2")
      .closest(".ant-card") as HTMLElement | null;
    expect(backlogItemCard).toBeTruthy();
    fireEvent.click(
      within(backlogItemCard as HTMLElement).getByRole("button", {
        name: "聚焦待办",
      }),
    );
    expect(handleSelectBacklogFocus).toHaveBeenCalledWith("backlog-2");

    const assignmentItemCard = screen.getByText("Assignment 2")
      .closest(".ant-card") as HTMLElement | null;
    expect(assignmentItemCard).toBeTruthy();
    fireEvent.click(
      within(assignmentItemCard as HTMLElement).getByRole("button", {
        name: "聚焦派工",
      }),
    );
    expect(handleSelectAssignmentFocus).toHaveBeenCalledWith("assignment-2");

    const reportsCard = screen.getByText("智能体汇报")
      .closest(".ant-card") as HTMLElement | null;
    expect(reportsCard).toBeTruthy();
    fireEvent.click(
      within(reportsCard as HTMLElement).getByRole("button", {
        name: "打开汇报对话",
      }),
    );
    expect(handleOpenAgentReportChat).toHaveBeenCalledWith(
      expect.objectContaining({
        report_id: "report-1",
        work_context_id: "ctx-report-1",
      }),
    );
  }, 15000);

  it("surfaces a dedicated runtime cockpit with direct strategy and cycle signals", () => {
    useIndustryPageStateMock.mockReturnValue(
      createPageState({
        detail: {
          execution: {
            status: "active",
            current_focus: "运营中枢巡检",
            current_owner: "Spider Mesh 主脑",
            current_risk: "guarded",
            evidence_count: 12,
            latest_evidence_summary: "最新证据链已接入当前执行面板。",
            next_step: "Review the latest patch queue.",
            trigger_source: "chat",
            trigger_reason: "Operator requested a cockpit review.",
            updated_at: "2026-03-27T09:30:00Z",
          },
          execution_core_identity: {
            role_name: "Spider Mesh 主脑",
            operating_mode: "control-core",
            mission: "Keep the industry runtime aligned with live evidence.",
            thinking_axes: ["carrier", "strategy", "lane", "cycle"],
            delegation_policy: ["assign by lane", "escalate by risk"],
          },
          strategy_memory: {
            status: "active",
            north_star: "One runtime truth across carrier, strategy, lane, and cycle.",
            current_focuses: ["assignment", "report", "decision", "patch"],
            priority_order: ["lane", "cycle", "assignment", "report"],
          },
          execution_environment: {
            environment_summary: "desktop-windows",
            host_twin_summary: "Seat policy sticky",
            environment_constraints: ["desktop", "browser-session"],
            host_twin: {
              coordination: {
                selected_seat_ref: "seat-1",
              },
            },
          },
          reports: {
            daily: {
              window: "daily",
              since: "2026-03-27T00:00:00Z",
              until: "2026-03-27T23:59:59Z",
              evidence_count: 1,
              proposal_count: 0,
              patch_count: 0,
              applied_patch_count: 0,
              growth_count: 0,
              decision_count: 1,
              recent_evidence: [{ summary: "Evidence snapshot entry" }],
              highlights: ["Daily highlight"],
            },
            weekly: {
              window: "weekly",
              since: "2026-03-21T00:00:00Z",
              until: "2026-03-27T23:59:59Z",
              evidence_count: 0,
              proposal_count: 0,
              patch_count: 0,
              applied_patch_count: 0,
              growth_count: 0,
              decision_count: 0,
              recent_evidence: [],
              highlights: [],
            },
          },
          current_cycle: {
            cycle_id: "cycle-1",
            cycle_kind: "weekly",
            title: "本周运行循环",
            summary: "The cockpit should keep the long-run loop visible.",
            status: "active",
            focus_lane_ids: ["lane-growth"],
            backlog_item_ids: ["backlog-1"],
            assignment_ids: ["assignment-1"],
            report_ids: ["report-1"],
            synthesis: {
              latest_findings: [],
              conflicts: [],
              holes: [],
              recommended_actions: [],
              needs_replan: false,
              control_core_contract: [],
            },
          },
          lanes: [
            {
              lane_id: "lane-growth",
              lane_key: "growth",
              title: "增长获客",
              summary: "Keep the growth lane visible in the cockpit.",
              status: "active",
              priority: 3,
              metadata: {},
            },
          ],
          assignments: [
            {
              assignment_id: "assignment-1",
              title: "Assignment 1",
              status: "running",
              evidence_ids: ["evidence-1"],
              metadata: {},
            },
          ],
          agent_reports: [
            {
              report_id: "report-1",
              headline: "Runtime report",
              report_kind: "summary",
              status: "recorded",
              findings: ["Acknowledge the patch queue."],
              uncertainties: [],
              needs_followup: false,
              evidence_ids: ["evidence-1"],
              decision_ids: ["decision-1"],
              processed: true,
              metadata: {},
              work_context_id: "ctx-report-1",
            },
          ],
          decisions: [{ decision_id: "decision-1" }],
          evidence: [{ evidence_id: "evidence-1" }],
          patches: [{ patch_id: "patch-1" }],
        },
      }),
    );

    render(<IndustryPage />);

    expect(screen.getByText("运行驾驶舱")).toBeTruthy();
    expect(screen.getAllByText("运行焦点").length).toBeGreaterThan(0);
    expect(screen.getByText("统一运行链")).toBeTruthy();
    expect(screen.getAllByText("策略").length).toBeGreaterThan(0);
    expect(screen.getAllByText("泳道").length).toBeGreaterThan(0);
    expect(screen.getAllByText("周期").length).toBeGreaterThan(0);
    expect(screen.getAllByText("派工").length).toBeGreaterThan(0);
    expect(screen.getAllByText("汇报").length).toBeGreaterThan(0);
    expect(screen.getAllByText("证据").length).toBeGreaterThan(0);
    expect(screen.getAllByText("决策").length).toBeGreaterThan(0);
    expect(screen.getAllByText("补丁").length).toBeGreaterThan(0);
    expect(screen.getByText("执行环境")).toBeTruthy();
    expect(screen.getAllByText("Seat policy sticky").length).toBeGreaterThan(0);
    expect(screen.getByText("desktop")).toBeTruthy();
    expect(screen.getByText("汇报快照")).toBeTruthy();
    expect(screen.getByText("Evidence snapshot entry")).toBeTruthy();
  });
});
