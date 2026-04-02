// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import type {
  RuntimeCenterSurfaceInfo,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import { useRuntimeCenter } from "./useRuntimeCenter";

const surface: RuntimeCenterSurfaceInfo = {
  version: "runtime-center-v1",
  mode: "operator-surface",
  status: "state-service",
  read_only: true,
  source: "state_query_service",
  note: "Shared surface",
};

const mockOverview = {
  generated_at: "2026-03-29T09:00:00Z",
  surface,
  cards: [],
};

const mockMainBrain: RuntimeMainBrainResponse = {
  generated_at: "2026-03-29T09:00:00Z",
  surface,
  strategy: {},
  carrier: {},
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
  meta: {},
};

const requestRuntimeOverviewMock = vi.fn();
const requestRuntimeMainBrainMock = vi.fn();
const requestRuntimeBusinessAgentsMock = vi.fn();

vi.mock("../../runtime/runtimeSurfaceClient", () => ({
  normalizeRuntimePath: vi.fn((path: string) => path),
  requestRuntimeOverview: () => requestRuntimeOverviewMock(),
  requestRuntimeRecord: vi.fn(),
  requestRuntimeBusinessAgents: () => requestRuntimeBusinessAgentsMock(),
  requestRuntimeMainBrain: () => requestRuntimeMainBrainMock(),
}));

vi.mock("../../runtime/eventBus", () => ({
  subscribe: vi.fn(() => () => {}),
}));

describe("useRuntimeCenter", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    requestRuntimeBusinessAgentsMock.mockResolvedValue([]);
  });

  it("loads both overview and dedicated main-brain payloads", async () => {
    requestRuntimeOverviewMock.mockResolvedValue({
      ...mockOverview,
      cards: [
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "main brain",
          entries: [],
          meta: {},
        },
      ],
    });
    requestRuntimeMainBrainMock.mockResolvedValue(mockMainBrain);
    requestRuntimeBusinessAgentsMock.mockResolvedValue([
      {
        agent_id: "copaw-agent-runner",
        name: "Spider Mesh",
      },
      {
        agent_id: "agent-ops-1",
        name: "Closer Nine",
      },
    ]);

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.data).toEqual(
      expect.objectContaining({ surface: mockOverview.surface }),
    );
    expect(result.current.mainBrainData).toEqual(mockMainBrain);
    expect(result.current.mainBrainUnavailable).toBe(false);
    expect(result.current.mainBrainError).toBeNull();
    expect(result.current.data?.cards.some((card) => card.key === "main-brain")).toBe(false);
    expect(result.current.businessAgents).toEqual([
      expect.objectContaining({
        agent_id: "agent-ops-1",
      }),
    ]);
    expect(result.current.businessAgentsError).toBeNull();
  });

  it("falls back when the dedicated payload is unavailable (404)", async () => {
    requestRuntimeOverviewMock.mockResolvedValue(mockOverview);
    requestRuntimeMainBrainMock.mockRejectedValue(
      new ApiError({
        status: 404,
        statusText: "Not Found",
      }),
    );

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.mainBrainData).toBeNull();
    expect(result.current.mainBrainUnavailable).toBe(true);
    expect(result.current.mainBrainError).toBeNull();
  });

  it("filters retired goals, schedules, and main-brain overview cards while returning business agents", async () => {
    requestRuntimeOverviewMock.mockResolvedValue({
      ...mockOverview,
      cards: [
        {
          key: "goals",
          title: "Goals",
          source: "goal-service",
          status: "state-service",
          count: 1,
          summary: "legacy goals",
          entries: [],
          meta: {},
        },
        {
          key: "schedules",
          title: "Schedules",
          source: "schedule-service",
          status: "state-service",
          count: 1,
          summary: "legacy schedules",
          entries: [],
          meta: {},
        },
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state-service",
          status: "state-service",
          count: 1,
          summary: "main brain",
          entries: [],
          meta: {},
        },
        {
          key: "tasks",
          title: "Tasks",
          source: "task-service",
          status: "state-service",
          count: 1,
          summary: "active tasks",
          entries: [],
          meta: {},
        },
      ],
    });
    requestRuntimeMainBrainMock.mockResolvedValue(mockMainBrain);
    requestRuntimeBusinessAgentsMock.mockResolvedValue([
      {
        agent_id: "agent-ops-2",
        name: "Closer Nine",
      },
    ]);

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.data?.cards.map((card) => card.key)).toEqual(["tasks"]);
    expect(result.current.businessAgents.map((agent) => agent.agent_id)).toEqual([
      "agent-ops-2",
    ]);
  });
});
