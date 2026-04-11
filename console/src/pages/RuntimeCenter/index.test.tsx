// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RuntimeCenterPage from "./index";

const mockNavigate = vi.fn();
const mockReload = vi.fn();
const mockOpenDetail = vi.fn();
const useRuntimeCenterMock = vi.fn();
const useRuntimeCenterAdminStateMock = vi.fn();
let mockSearchParams = new URLSearchParams();
const mockSetSearchParams = vi.fn();

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
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  };
});

vi.mock("./useRuntimeCenter", () => ({
  useRuntimeCenter: () => useRuntimeCenterMock(),
}));

vi.mock("./useRuntimeCenterAdminState", () => ({
  useRuntimeCenterAdminState: (...args: unknown[]) =>
    useRuntimeCenterAdminStateMock(...args),
}));

function createRuntimeCenterState() {
  return {
    data: {
      generated_at: "2026-03-29T09:00:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service,governance_service",
        note: "Shared runtime surface",
        services: ["state_query_service", "governance_service"],
      },
      cards: [
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "Legacy generic main-brain overview card",
          entries: [],
          meta: {},
        },
        {
          key: "tasks",
          title: "Tasks",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "active tasks",
          entries: [
            {
              id: "task-1",
              title: "整理交付证据",
              kind: "task",
              status: "active",
              owner: "运营执行位",
              summary: "把今天新增结果整理成可回看材料。",
              updated_at: "2026-03-29T08:45:00Z",
              route: "/api/runtime-center/tasks/task-1",
              actions: {},
              meta: {
                queue_depth: 2,
                runtime_status: "active",
              },
            },
          ],
          meta: {},
        },
      ],
    },
    loading: false,
    refreshing: false,
    error: null,
    buddySummary: null,
    mainBrainData: {
      generated_at: "2026-03-29T09:05:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service,governance_service",
        note: "Shared runtime surface",
      },
      strategy: {
        title: "Northwind field operations strategy",
        summary: "Keep the staffed handoff loop stable and evidence-backed.",
      },
      carrier: {
        industry_instance_id: "industry-1",
        label: "Northwind Ops",
        route: "/api/runtime-center/industry/industry-1",
      },
      lanes: [],
      cycles: [],
      backlog: [],
      current_cycle: null,
      assignments: [],
      reports: [],
      report_cognition: {},
      environment: {},
      governance: {},
      recovery: {},
      automation: {},
      evidence: { count: 0, summary: "", route: null, entries: [], meta: {} },
      decisions: { count: 0, summary: "", route: null, entries: [], meta: {} },
      patches: { count: 0, summary: "", route: null, entries: [], meta: {} },
      signals: {},
      meta: { control_chain: [] },
    },
    mainBrainLoading: false,
    mainBrainError: null,
    mainBrainUnavailable: false,
    businessAgents: [
      {
        agent_id: "agent-ops-1",
        name: "运营执行位",
        role_name: "运营",
        role_summary: "负责跟进外部交付与证据整理。",
        agent_class: "business",
        status: "active",
        current_focus: "整理交付阻塞与证据",
        industry_role_id: "ops-seat",
      },
    ],
    businessAgentsLoading: false,
    businessAgentsError: null,
    busyActionId: null,
    detail: null,
    detailLoading: false,
    detailError: null,
    reload: mockReload,
    invokeAction: vi.fn(),
    openDetail: mockOpenDetail,
    closeDetail: vi.fn(),
  };
}

function createAdminState() {
  return {
    governanceStatus: null,
    governanceLoading: false,
    governanceError: null,
    governanceBusyKey: null,
    capabilityOptimizationOverview: null,
    capabilityOptimizationLoading: false,
    capabilityOptimizationError: null,
    capabilityOptimizationBusyId: null,
    recoverySummary: null,
    selfCheck: null,
    recoveryLoading: false,
    recoveryError: null,
    recoveryBusyKey: null,
    operatorActor: "runtime-center",
    setOperatorActor: vi.fn(),
    governanceResolution: "approved",
    setGovernanceResolution: vi.fn(),
    emergencyReason: "",
    setEmergencyReason: vi.fn(),
    resumeReason: "",
    setResumeReason: vi.fn(),
    executeApprovedDecisions: true,
    setExecuteApprovedDecisions: vi.fn(),
    selectedDecisionIds: [],
    setSelectedDecisionIds: vi.fn(),
    selectedPatchIds: [],
    setSelectedPatchIds: vi.fn(),
    handleDecisionBatch: vi.fn(),
    handlePatchBatch: vi.fn(),
    handleCapabilityOptimizationExecute: vi.fn(),
    handleEmergencyStop: vi.fn(),
    handleResumeRuntime: vi.fn(),
    handleRecoveryRefresh: vi.fn(),
    handleSelfCheck: vi.fn(),
    refreshActiveTabData: vi.fn(),
  };
}

describe("RuntimeCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it("does not render the legacy generic main-brain overview card", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    expect(
      screen.queryByText("Legacy generic main-brain overview card"),
    ).toBeNull();
  });

  it("keeps cards visible while main-brain is still loading", () => {
    useRuntimeCenterMock.mockReturnValue({
      ...createRuntimeCenterState(),
      mainBrainData: null,
      mainBrainLoading: true,
      mainBrainUnavailable: false,
    });
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    expect(screen.getByText("整理交付证据")).toBeTruthy();
    expect(screen.getAllByRole("button").length).toBeGreaterThan(0);
  });
});
