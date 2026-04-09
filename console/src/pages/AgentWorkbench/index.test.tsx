// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage from "./index";

const mockNavigate = vi.fn();
const mockSetSearchParams = vi.fn();
const useAgentWorkbenchMock = vi.fn();
let mockSearchParams = new URLSearchParams();

if (!window.matchMedia) {
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
}

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

vi.mock("./useAgentWorkbench", () => ({
  useAgentWorkbench: (...args: unknown[]) => useAgentWorkbenchMock(...args),
}));

vi.mock("./AgentReports", () => ({
  AgentDailyReport: ({ agentId }: { agentId: string | null }) => (
    <div>{`daily:${agentId ?? "none"}`}</div>
  ),
  AgentWeeklyReport: ({ agentId }: { agentId: string | null }) => (
    <div>{`weekly:${agentId ?? "none"}`}</div>
  ),
  AgentGrowthTrajectory: () => <div>performance-panel</div>,
}));

vi.mock("./WorkspaceTab", () => ({
  default: ({ agent }: { agent: { agent_id: string } | null }) => (
    <div>{`workspace:${agent?.agent_id ?? "none"}`}</div>
  ),
}));

vi.mock("./V7ExecutionSeatPanel", () => ({
  default: ({ agent }: { agent: { agent_id: string } }) => (
    <div>{`seat-panel:${agent.agent_id}`}</div>
  ),
}));

vi.mock("../../utils/runtimeChat", () => ({
  buildAgentChatBinding: vi.fn(),
  openRuntimeChat: vi.fn(),
}));

vi.mock("./pageSections", () => ({
  TAB_KEYS: new Set([
    "daily",
    "weekly",
    "profile",
    "performance",
    "evidence",
    "workbench",
    "workspace",
    "growth",
  ]),
  isExecutionCoreAgent: (agent: { agent_id?: string | null }) =>
    agent?.agent_id === "copaw-agent-runner",
  statusColor: () => "blue",
  ProfileCard: ({ agent }: { agent: { agent_id: string; name: string } }) => (
    <div>{`profile:${agent.agent_id}:${agent.name}`}</div>
  ),
  CapabilityGovernancePanel: ({
    agent,
  }: {
    agent: { agent_id: string };
  }) => <div>{`governance:${agent.agent_id}`}</div>,
  ActorRuntimePanel: ({
    detail,
  }: {
    detail: { agent?: { agent_id?: string } } | null;
  }) => <div>{`runtime:${detail?.agent?.agent_id ?? "none"}`}</div>,
  EvidencePanel: ({
    evidence,
  }: {
    evidence: Array<{ id: string }>;
  }) => <div>{`evidence:${evidence.map((item) => item.id).join(",")}`}</div>,
}));

function createAgent(agentId: string, name: string, agentClass: "system" | "business") {
  return {
    agent_id: agentId,
    name,
    role_name: agentClass === "system" ? "主脑" : "Researcher",
    role_summary: "",
    agent_class: agentClass,
    employment_mode: "career" as const,
    activation_mode: "persistent" as const,
    suspendable: true,
    reports_to: agentClass === "system" ? null : "copaw-agent-runner",
    mission: agentClass === "system" ? "Plan" : "Execute",
    status: "active",
    risk_level: "auto",
    current_focus_kind: "assignment",
    current_focus_id: `assignment-${agentId}`,
    current_focus: `focus-${agentId}`,
    current_task_id: null,
    industry_instance_id: "industry-1",
    industry_role_id: agentId === "copaw-agent-runner" ? "execution-core" : `role-${agentId}`,
    environment_summary: "",
    environment_constraints: [],
    evidence_expectations: [],
    today_output_summary: "",
    latest_evidence_summary: "",
    capabilities: [],
    updated_at: null,
  };
}

const mainBrainAgent = createAgent("copaw-agent-runner", "超级伙伴主脑", "system");
const seatAgent = createAgent("agent-seat-1", "Research Operator", "business");
const secondSeatAgent = createAgent("agent-seat-2", "Writer Operator", "business");

function createWorkbenchState(overrides: Record<string, unknown> = {}) {
  return {
    agents: [mainBrainAgent, seatAgent, secondSeatAgent],
    selectedAgent: null,
    setSelectedAgent: vi.fn(),
    agentDetail: null,
    industryDetail: null,
    capabilityCatalog: [],
    evidence: [{ id: "dashboard-evidence" }],
    loading: false,
    agentDetailLoading: false,
    industryDetailLoading: false,
    capabilityCatalogLoading: false,
    dashboardError: null,
    agentDetailError: null,
    industryDetailError: null,
    capabilityActionKey: null,
    actorActionKey: null,
    refresh: vi.fn(),
    refreshAgentDetail: vi.fn(),
    submitGovernedCapabilityAssignment: vi.fn(),
    resolveCapabilityDecision: vi.fn(),
    pauseActorRuntime: vi.fn(),
    resumeActorRuntime: vi.fn(),
    retryActorMailboxRuntime: vi.fn(),
    cancelActorRuntime: vi.fn(),
    ...overrides,
  };
}

describe("AgentWorkbenchPage", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    useAgentWorkbenchMock.mockReset();
    mockSearchParams = new URLSearchParams();
  });

  it("defaults to the execution brief tabs and keeps the workbench context on a professional seat", () => {
    useAgentWorkbenchMock.mockReturnValue(createWorkbenchState());

    render(<AgentWorkbenchPage />);

    const tabLabels = screen
      .getAllByRole("tab")
      .map((tab) => (tab.textContent ?? "").trim());

    expect(tabLabels).toContain("今日简报");
    expect(tabLabels).toContain("周报");
    expect(tabLabels).toContain("简历");
    expect(tabLabels).toContain("绩效");
    expect(tabLabels).toContain("证据产物");
    expect(tabLabels).not.toContain("执行 / 回流");
    expect(tabLabels).not.toContain("环境 / 文件");
    expect(tabLabels).not.toContain("成长");
    expect(screen.getByText("daily:agent-seat-1")).toBeTruthy();
    expect(screen.queryByText("daily:copaw-agent-runner")).toBeNull();
    expect(screen.queryByText("profile:copaw-agent-runner:超级伙伴主脑")).toBeNull();
  });

  it("does not let selectedAgent keep the main brain in the execution-seat workbench", () => {
    useAgentWorkbenchMock.mockReturnValue(
      createWorkbenchState({
        selectedAgent: mainBrainAgent,
      }),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("daily:agent-seat-1")).toBeTruthy();
    expect(screen.queryByText("daily:copaw-agent-runner")).toBeNull();
    expect(screen.queryByText("profile:copaw-agent-runner:超级伙伴主脑")).toBeNull();
  });

  it("does not let agentDetail override the workbench back to the main brain", () => {
    useAgentWorkbenchMock.mockReturnValue(
      createWorkbenchState({
        selectedAgent: seatAgent,
        agentDetail: {
          agent: mainBrainAgent,
          evidence: [{ id: "main-brain-evidence" }],
        },
      }),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("daily:agent-seat-1")).toBeTruthy();
    expect(screen.queryByText("daily:copaw-agent-runner")).toBeNull();
    expect(screen.queryByText("profile:copaw-agent-runner:超级伙伴主脑")).toBeNull();
  });

  it("routes the main-brain card back to the cockpit instead of selecting it as a seat", () => {
    useAgentWorkbenchMock.mockReturnValue(createWorkbenchState());

    render(<AgentWorkbenchPage />);

    const mainBrainLabels = screen.getAllByText("超级伙伴主脑");
    fireEvent.click(mainBrainLabels[mainBrainLabels.length - 1]);

    expect(mockNavigate).toHaveBeenCalledWith("/runtime-center");
    expect(mockSetSearchParams).not.toHaveBeenCalled();
  });
});
