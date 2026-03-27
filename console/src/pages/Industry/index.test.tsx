// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import IndustryPage from "./index";
import { INDUSTRY_TEXT } from "./pageHelpers";

const mockNavigate = vi.fn();
const useIndustryPageStateMock = vi.fn();

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

function createPageState() {
  return {
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
    handleOpenExecutionCoreChat: vi.fn(),
    handlePatchInstallPlanItem: vi.fn(),
    handlePreview: vi.fn(),
    handleRemoveBriefMediaItem: vi.fn(),
    handleRemoveInstallPlanItem: vi.fn(),
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
});
