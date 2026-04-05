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
          summary: "Legacy generic main-brain overview card",
          entries: [],
          meta: {},
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
      backlog: [
        {
          backlog_item_id: "backlog-followup-1",
          title: "Resolve handoff return evidence gap",
          summary: "Dispatch a governed browser follow-up on the same control thread.",
          route: "/api/runtime-center/industry/industry-1?backlog_item_id=backlog-followup-1",
          status: "open",
        },
      ],
      current_cycle: {
        cycle_id: "cycle-12",
        title: "Cycle 12",
        status: "active",
        focus_count: 2,
        next_cycle_due_at: "2026-03-31T23:59:59Z",
      },
      assignments: [
        {
          assignment_id: "assignment-1",
          title: "Review handoff blockers",
          status: "active",
          route: "/api/runtime-center/industry/industry-1",
        },
      ],
      reports: [
        {
          report_id: "report-1",
          headline: "Need supervisor decision",
          summary: "Operator must compare the evidence gap before dispatching the next cycle.",
          status: "recorded",
          needs_followup: true,
          report_consumed: false,
          updated_at: "2026-03-29T08:30:00Z",
          route: "/api/runtime-center/industry/industry-1",
        },
      ],
      report_cognition: {
        next_action: {
          kind: "followup-backlog",
          title: "Resolve handoff return evidence gap",
          summary: "Dispatch a governed browser follow-up on the same control thread.",
        },
      },
      environment: {
        route: "/api/runtime-center/governance/status",
        summary: "Host twin ready on seat-b with multi-surface continuity.",
        host_twin_summary: {
          selected_seat_ref: "env:desktop:seat-b",
          recommended_scheduler_action: "proceed",
          continuity_state: "ready",
          active_app_family_keys: ["browser_backoffice", "office_document"],
        },
      },
      governance: {
        route: "/api/runtime-center/governance/status",
        status: "blocked",
        summary: "Human handoff is active and runtime dispatch is gated.",
        pending_decisions: 1,
        pending_patches: 2,
      },
      recovery: {
        route: "/api/runtime-center/recovery/latest",
        available: true,
        status: "ready",
        summary: "Recovered expired decisions and runtime leases during startup.",
      },
      automation: {
        route: "/api/runtime-center/schedules",
        status: "active",
        summary: "2 schedule(s) visible; heartbeat success every 6h.",
      },
      evidence: {
        count: 1,
        summary: "Evidence trace is ready.",
        route: "/api/runtime-center/evidence",
        entries: [{ id: "evidence-1", title: "Checkpoint evidence" }],
        meta: {},
      },
      decisions: {
        count: 1,
        summary: "One decision pending.",
        route: "/api/runtime-center/decisions",
        entries: [{ id: "decision-1", title: "Approve host return" }],
        meta: {},
      },
      patches: {
        count: 1,
        summary: "One patch pending.",
        route: "/api/runtime-center/learning/patches",
        entries: [{ id: "patch-1", title: "Apply continuity patch" }],
        meta: {},
      },
      signals: {
        carrier: {
          key: "carrier",
          value: "Northwind Ops",
        },
        strategy: {
          key: "strategy",
          value: "Northwind field operations strategy",
        },
      },
      meta: {
        control_chain: [],
      },
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
    governanceResolution: "已审阅",
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

  it("renders the execution-first homepage with daily brief before the agent strip", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    const briefTitle = screen.getAllByText("主脑今日运行简报")[0];
    const stripTitle = screen.getByText("主脑与职业智能体");

    expect(briefTitle.compareDocumentPosition(stripTitle)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(screen.getByText("今日目标")).toBeTruthy();
    expect(screen.getByText("已完成")).toBeTruthy();
    expect(screen.getByText("进行中")).toBeTruthy();
    expect(screen.getByText("当前阻塞")).toBeTruthy();
    expect(screen.getByText("待确认")).toBeTruthy();
    expect(screen.getByText("下一步")).toBeTruthy();
    expect(screen.getByRole("button", { name: /^主脑/ })).toBeTruthy();
    expect(screen.getByText("运营执行位")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /运营执行位/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/runtime-center?agent=agent-ops-1");
  });

  it("does not render the legacy generic main-brain overview card", () => {
    useRuntimeCenterMock.mockReturnValue(createRuntimeCenterState());
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    expect(
      screen.queryByText("Legacy generic main-brain overview card"),
    ).toBeNull();
  });

  it("does not render the main brain twice when the agent summary payload includes system identities", () => {
    useRuntimeCenterMock.mockReturnValue({
      ...createRuntimeCenterState(),
      businessAgents: [
        {
          agent_id: "copaw-agent-runner",
          name: "Spider Mesh",
          role_name: "主脑",
          agent_class: "system",
          status: "active",
          industry_role_id: "execution-core",
        },
        ...createRuntimeCenterState().businessAgents,
      ],
    });
    useRuntimeCenterAdminStateMock.mockReturnValue(createAdminState());

    render(<RuntimeCenterPage />);

    expect(screen.getAllByRole("button", { name: /^主脑/ })).toHaveLength(1);
    expect(screen.getByText("运营执行位")).toBeTruthy();
  });

  it("renders recovery self-check highlights when recovery tab is active", () => {
    mockSearchParams = new URLSearchParams("tab=recovery");
    useRuntimeCenterMock.mockReturnValue({
      ...createRuntimeCenterState(),
      data: {
        ...createRuntimeCenterState().data,
      },
    });
    useRuntimeCenterAdminStateMock.mockReturnValue({
      ...createAdminState(),
      recoverySummary: {
        reason: "startup",
      },
      selfCheck: {
        overall_status: "warn",
        checks: [
          {
            name: "workspace_drift",
            status: "warn",
            summary: "检测到工作区漂移",
            meta: {},
          },
          {
            name: "evidence_ledger",
            status: "pass",
            summary: "Evidence ledger online",
            meta: {},
          },
        ],
      },
    });

    render(<RuntimeCenterPage />);

    expect(screen.getByText("实时自检")).toBeTruthy();
  });
});
