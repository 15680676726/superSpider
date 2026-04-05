// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  RuntimeCenterSurfaceCard,
  RuntimeCenterSurfaceResponse,
  RuntimeCenterSurfaceInfo,
  RuntimeMainBrainBuddySummary,
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

function createAgentsCard(
  ...entries: RuntimeCenterSurfaceCard["entries"]
): RuntimeCenterSurfaceCard {
  return {
    key: "agents",
    title: "Agents",
    source: "agent_profile_service",
    status: "state-service" as const,
    count: entries.length,
    summary: "agent roster",
    entries,
    meta: {},
  };
}

const mockMainBrain: RuntimeMainBrainResponse = {
  generated_at: "2026-03-29T09:00:00Z",
  surface,
  main_brain_planning: {},
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
  meta: { control_chain: [] },
};

const mockSurface = (
  overrides?: Partial<RuntimeCenterSurfaceResponse>,
): RuntimeCenterSurfaceResponse => ({
  generated_at: mockOverview.generated_at,
  surface,
  cards: mockOverview.cards,
  main_brain: mockMainBrain,
  ...overrides,
});

const requestRuntimeSurfaceMock = vi.fn();
const requestRuntimeBuddySummaryMock = vi.fn();
const readBuddyProfileIdMock = vi.fn();
let runtimeEventHandler:
  | ((event: { event_name: string; payload: Record<string, unknown> }) => void)
  | null = null;

const mockBuddySummary: RuntimeMainBrainBuddySummary = {
  buddy_name: "Nova",
  lifecycle_state: "named",
  presence_state: "available",
  mood_state: "warm",
  evolution_stage: "bonded",
  growth_level: 4,
  intimacy: 24,
  affinity: 19,
  current_goal_summary: "Build an independent creator-business growth path",
  current_task_summary: "Write the first meaningful piece today",
  why_now_summary: "This is the smallest move that keeps momentum real.",
};

vi.mock("../../runtime/runtimeSurfaceClient", () => ({
  normalizeRuntimePath: vi.fn((path: string) => path),
  requestRuntimeSurface: (...args: unknown[]) => requestRuntimeSurfaceMock(...args),
  requestRuntimeBuddySummary: (...args: unknown[]) =>
    requestRuntimeBuddySummaryMock(...args),
  requestRuntimeRecord: vi.fn(),
}));

vi.mock("../../runtime/buddyProfileBinding", () => ({
  readBuddyProfileId: () => readBuddyProfileIdMock(),
}));

vi.mock("../../runtime/eventBus", () => ({
  subscribe: vi.fn((_topic: string, handler: typeof runtimeEventHandler) => {
    runtimeEventHandler = handler;
    return () => {
      runtimeEventHandler = null;
    };
  }),
}));

describe("useRuntimeCenter", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    runtimeEventHandler = null;
    readBuddyProfileIdMock.mockReturnValue("profile-bound");
    requestRuntimeSurfaceMock.mockResolvedValue(mockSurface());
    requestRuntimeBuddySummaryMock.mockResolvedValue(mockBuddySummary);
  });

  it("loads canonical surface once and derives business agents from overview cards", async () => {
    let resolveSurface!: (value: RuntimeCenterSurfaceResponse) => void;
    requestRuntimeSurfaceMock.mockReturnValue(
      new Promise<RuntimeCenterSurfaceResponse>((resolve) => {
        resolveSurface = resolve;
      }),
    );

    const { result } = renderHook(() => useRuntimeCenter());

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);
    expect(requestRuntimeBuddySummaryMock).toHaveBeenCalledWith("profile-bound");

    resolveSurface(
      mockSurface({
        cards: [
          createAgentsCard(
            {
              id: "copaw-agent-runner",
              title: "Spider Mesh",
              kind: "agent",
              status: "active",
              owner: "Execution Core",
              summary: "System seat",
              actions: {},
              meta: {},
            },
            {
              id: "agent-ops-1",
              title: "Closer Nine",
              kind: "agent",
              status: "active",
              owner: "Closer",
              summary: "Closing backlog",
              actions: {},
              meta: {
                current_focus_kind: "assignment",
                current_focus_id: "assignment-1",
                current_focus: "Close pipeline backlog",
              },
            },
          ),
        ],
      }),
    );

    await waitFor(() => !result.current.loading);

    expect(result.current.data).toEqual(
      expect.objectContaining({ surface: mockOverview.surface }),
    );
    expect(result.current.mainBrainData).toEqual(mockMainBrain);
    expect(result.current.buddySummary).toEqual(mockBuddySummary);
    expect(result.current.mainBrainUnavailable).toBe(false);
    expect(result.current.mainBrainError).toBeNull();
    expect(result.current.businessAgents).toEqual([
      expect.objectContaining({
        agent_id: "agent-ops-1",
        current_focus_kind: "assignment",
        current_focus_id: "assignment-1",
        current_focus: "Close pipeline backlog",
      }),
    ]);
    expect(result.current.businessAgentsError).toBeNull();
  });

  it("marks main-brain surface unavailable when canonical surface omits it", async () => {
    requestRuntimeSurfaceMock.mockResolvedValue(mockSurface({ main_brain: null }));

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.mainBrainData).toBeNull();
    expect(result.current.buddySummary).toEqual(mockBuddySummary);
    expect(result.current.mainBrainUnavailable).toBe(true);
    expect(result.current.mainBrainError).toBeNull();
  });

  it("filters retired goals, schedules, and main-brain overview cards while returning business agents from overview", async () => {
    requestRuntimeSurfaceMock.mockResolvedValue(
      mockSurface({
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
        createAgentsCard({
          id: "agent-ops-2",
          title: "Closer Nine",
          kind: "agent",
          status: "active",
          owner: "Closer",
          summary: "Working backlog",
          actions: {},
          meta: {
            current_focus_kind: "backlog_item",
            current_focus_id: "backlog-2",
            current_focus: "Follow up warm leads",
          },
        }),
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
      }),
    );

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.data?.cards.map((card) => card.key)).toEqual(["agents", "tasks"]);
    expect(result.current.businessAgents.map((agent) => agent.agent_id)).toEqual([
      "agent-ops-2",
    ]);
    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);
    expect(requestRuntimeBuddySummaryMock).toHaveBeenCalledTimes(1);
  });

  it("requests buddy summary with null profile when no binding exists", async () => {
    readBuddyProfileIdMock.mockReturnValue(null);

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeBuddySummaryMock).toHaveBeenCalledWith(null);
  });

  it("refreshes only the main-brain section on assignment events", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);

    vi.useFakeTimers();
    runtimeEventHandler?.({
      event_name: "assignment.updated",
      payload: { assignment_id: "assignment-1" },
    });
    await vi.advanceTimersByTimeAsync(300);

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
    expect(requestRuntimeSurfaceMock).toHaveBeenLastCalledWith({
      sections: ["main_brain"],
    });
    expect(requestRuntimeBuddySummaryMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("ignores heartbeat events instead of reloading the full surface", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    vi.useFakeTimers();
    runtimeEventHandler?.({
      event_name: "runtime.heartbeat",
      payload: {},
    });
    await vi.advanceTimersByTimeAsync(300);

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("refreshes only the cards section on agent events", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);

    vi.useFakeTimers();
    runtimeEventHandler?.({
      event_name: "agent.updated",
      payload: { agent_id: "agent-ops-2" },
    });
    await vi.advanceTimersByTimeAsync(300);

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
    expect(requestRuntimeSurfaceMock).toHaveBeenLastCalledWith({
      sections: ["cards"],
    });
    expect(requestRuntimeBuddySummaryMock).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("coalesces mixed runtime events into one canonical section refresh per debounce window", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);

    vi.useFakeTimers();
    runtimeEventHandler?.({
      event_name: "agent.updated",
      payload: { agent_id: "agent-ops-2" },
    });
    runtimeEventHandler?.({
      event_name: "assignment.updated",
      payload: { assignment_id: "assignment-1" },
    });
    await vi.advanceTimersByTimeAsync(300);

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
    expect(requestRuntimeSurfaceMock).toHaveBeenLastCalledWith({
      sections: ["cards", "main_brain"],
    });
    vi.useRealTimers();
  });

  it("ignores unknown runtime events instead of falling back to a full surface reload", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    vi.useFakeTimers();
    runtimeEventHandler?.({
      event_name: "tool.updated",
      payload: { tool_id: "browser" },
    });
    await vi.advanceTimersByTimeAsync(300);

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
