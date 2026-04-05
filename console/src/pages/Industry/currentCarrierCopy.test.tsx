// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useCallback as reactUseCallback } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IndustryPage from "./index";

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
  window.localStorage.clear();
});

function createPageState(overrides: Record<string, unknown> = {}) {
  return {
    allTeams: [],
    applyCarrierLoading: false,
    briefMediaBusy: false,
    briefMediaItems: [],
    briefMediaLink: "",
    briefModalOpen: false,
    briefUploadInputRef: { current: null },
    deletingInstanceId: null,
    detail: {
      instance_id: "buddy:profile-1",
      bootstrap_kind: "industry-v1",
      label: "Buddy Carrier",
      summary: "Demo summary",
      owner_scope: "buddy:profile-1",
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
        team_id: "team-buddy",
        label: "Buddy Carrier",
        summary: "Execution carrier",
        agents: [],
      },
      status: "active",
      updated_at: "2026-03-26T08:00:00Z",
      stats: {},
      routes: {},
      focus_selection: null,
      goals: [],
      agents: [],
      schedules: [],
      lanes: [],
      backlog: [],
      staffing: { pending_proposals: [], temporary_seats: [] },
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
    draftTeamLabel: "Buddy Carrier",
    draftTeamSummary: "Execution carrier",
    error: null,
    handleAddBriefMediaLink: vi.fn(),
    handleAddCustomInstallItem: vi.fn(),
    handleApplyCarrierAdjustment: vi.fn(),
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
    instances: [],
    isEditing: true,
    isEditingExistingTeam: true,
    loadDetail: vi.fn(),
    loadInstanceIntoDraft: vi.fn(),
    loadInstances: vi.fn(),
    loadingDetail: false,
    loadingInstances: false,
    preview: {
      can_activate: true,
      draft: {
        team: {
          label: "Buddy Carrier",
          summary: "Execution carrier",
        },
      },
      media_warnings: [],
      media_analyses: [],
      recommendation_pack: null,
      readiness_checks: [],
    },
    previewLoading: false,
    protectedCarrierInstanceId: "buddy:profile-1",
    recommendationById: new Map(),
    recommendationDisplayGroups: [],
    recommendationSections: [],
    recommendationWarnings: [],
    retiredInstances: [],
    roleOptions: [],
    selectedExecutionCoreRole: null,
    selectedInstanceId: "buddy:profile-1",
    selectedSummary: {
      instance_id: "buddy:profile-1",
      label: "Buddy Carrier",
      owner_scope: "buddy:profile-1",
      team: {
        schema_version: "industry-team-blueprint-v1",
        team_id: "team-buddy",
        label: "Buddy Carrier",
        summary: "Execution carrier",
        agents: [],
      },
    },
    setBriefMediaLink: vi.fn(),
    setBriefModalOpen: vi.fn(),
    setDraftSourceInstanceId: vi.fn(),
    setError: vi.fn(),
    setInstallPlan: vi.fn(),
    setPreview: vi.fn(),
    setSelectedInstanceId: vi.fn(),
    watchedExperienceMode: "operator-guided",
    ...overrides,
  };
}

describe("IndustryPage current carrier copy", () => {
  it("shows carrier copy instead of legacy team copy while editing the current carrier", () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-1");
    useIndustryPageStateMock.mockReturnValue(createPageState());

    render(<IndustryPage />);

    expect(screen.getByRole("button", { name: "应用执行载体调整" })).toBeInTheDocument();
    expect(screen.getByText("载体名称")).toBeInTheDocument();
    expect(screen.getByText("执行位角色")).toBeInTheDocument();
    expect(screen.queryByText("团队名称")).toBeNull();
    expect(screen.queryByText("团队角色")).toBeNull();
    expect(screen.queryByText("创建并启动团队")).toBeNull();
    expect(screen.queryByText("更新团队")).toBeNull();
  });
});
