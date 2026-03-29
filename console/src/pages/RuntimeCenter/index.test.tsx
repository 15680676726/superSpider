// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RuntimeCenterPage from "./index";

const mockNavigate = vi.fn();
const mockOpenDetail = vi.fn();
const mockReload = vi.fn();
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
          summary: "Main brain cockpit",
          entries: [
            {
              id: "main-brain-1",
              title: "Main-Brain cockpit",
              kind: "runtime",
              status: "active",
              owner: null,
              summary: "Open the cockpit detail",
              updated_at: "2026-03-29T09:00:00Z",
              route: "/api/runtime-center/governance/status",
              actions: {},
              meta: {},
            },
          ],
          meta: {
            carrier: {
              status: "state-service",
              summary: "Carrier ready",
              route: "/api/runtime-center/governance/status",
            },
            strategy: {
              summary: "North star: weekly alignment",
            },
            lanes: {
              count: 4,
              summary: "4 lanes active",
            },
            current_cycle: {
              title: "Cycle 12",
              summary: "Weekly cadence",
              status: "active",
              next_cycle_due_at: "2026-03-31T23:59:59Z",
              focus_count: 9,
              route: "/api/runtime-center/industry/industry-1?cycle_id=cycle-12",
            },
            assignments: {
              count: 3,
              summary: "3 active assignments",
            },
            agent_reports: {
              count: 8,
              unconsumed_count: 5,
              summary: "8 agent reports",
            },
            evidence: {
              count: 5,
              summary: "5 evidence records",
            },
            decisions: {
              count: 1,
              summary: "1 decision pending",
            },
            patches: {
              count: 2,
              summary: "2 patches pending",
            },
            environment: {
              summary: "Host twin ready",
              detail: "Workspace bound",
              route: "/api/runtime-center/governance/status",
            },
          },
        },
        {
          key: "decisions",
          title: "决策",
          source: "governance_service",
          status: "state-service",
          count: 0,
          summary: "",
          entries: [],
          meta: {},
        },
        {
          key: "patches",
          title: "补丁",
          source: "learning_service",
          status: "state-service",
          count: 0,
          summary: "",
          entries: [],
          meta: {},
        },
      ],
    },
    loading: false,
    refreshing: false,
    error: null,
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
    governanceResolution: "鎵瑰噯",
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

  it("renders the main-brain cockpit surface before the legacy overview grid", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    expect(screen.getByText("Main-Brain Cockpit")).toBeTruthy();
    expect(screen.getAllByText("Carrier").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Strategy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current Cycle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Agent Reports").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cycle Deadline").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Focus Count").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unconsumed Reports").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2026-03-31 23:59Z").length).toBeGreaterThan(0);
    expect(screen.getAllByText("9").length).toBeGreaterThan(0);
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("North star: weekly alignment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cycle 12").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Workspace bound").length).toBeGreaterThan(0);
    expect(screen.queryByText("Current Goal")).toBeNull();

    fireEvent.click(screen.getByLabelText("Open Current Cycle detail"));

    expect(mockOpenDetail).toHaveBeenCalledWith(
      "/api/runtime-center/industry/industry-1?cycle_id=cycle-12",
      expect.any(String),
    );
  });

  it("renders recovery self-check highlights when recovery tab is active", () => {
    mockSearchParams = new URLSearchParams("tab=recovery");
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());
    useRuntimeCenterAdminStateMock.mockReturnValue({
      ...createAdminState(),
      recoverySummary: {
        reason: "startup",
        phase: "restore",
      },
      selfCheck: {
        overall_status: "active",
        checks: [
          {
            name: "carrier",
            status: "active",
            summary: "Carrier healthy",
            meta: {},
          },
          {
            name: "environment",
            status: "warning",
            summary: "Workspace drift detected",
            meta: { drift_count: 1 },
          },
        ],
      },
    });

    render(<RuntimeCenterPage />);

    expect(screen.getAllByText("Carrier healthy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Workspace drift detected").length).toBeGreaterThan(0);
  });
});
