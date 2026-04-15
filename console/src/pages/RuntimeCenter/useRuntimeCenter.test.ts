// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  RuntimeCenterSurfaceCard,
  RuntimeCenterSurfaceResponse,
  RuntimeCenterSurfaceInfo,
  RuntimeMainBrainBuddySummary,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import {
  resetRuntimeCenterSurfaceCache,
  useRuntimeCenter,
} from "./useRuntimeCenter";

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

const mockBuddySummary: RuntimeMainBrainBuddySummary = {
  buddy_name: "Nova",
  lifecycle_state: "named",
  presence_state: "available",
  mood_state: "warm",
  evolution_stage: "bonded",
  growth_level: 4,
  intimacy: 24,
  affinity: 19,
  current_goal_summary: "建立独立创作与内容事业的长期成长路径",
  current_task_summary: "今天先写出第一篇真正能代表自己的作品",
  why_now_summary: "这是让长期方向不再停留在想象里的最小推进。",
  single_next_action_summary: "现在先打开文档，写下标题和三条核心观点。",
  companion_strategy_summary: "先接住情绪，再把任务缩成一个最小动作。",
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
  buddy_summary: mockBuddySummary,
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
const requestRuntimeBusinessAgentsMock = vi.fn();
const requestRuntimeRecordMock = vi.fn();
const readBuddyProfileIdMock = vi.fn();
let runtimeEventHandler:
  | ((event: { event_name: string; payload: Record<string, unknown> }) => void)
  | null = null;

function createDeferredPromise<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

vi.mock("../../runtime/runtimeSurfaceClient", () => ({
  normalizeRuntimePath: vi.fn((path: string) => path),
  requestRuntimeSurface: (...args: unknown[]) => requestRuntimeSurfaceMock(...args),
  requestRuntimeBusinessAgents: (...args: unknown[]) =>
    requestRuntimeBusinessAgentsMock(...args),
  requestRuntimeRecord: (...args: unknown[]) => requestRuntimeRecordMock(...args),
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
    resetRuntimeCenterSurfaceCache();
    readBuddyProfileIdMock.mockReturnValue("profile-bound");
    requestRuntimeSurfaceMock.mockResolvedValue(mockSurface());
    requestRuntimeBusinessAgentsMock.mockResolvedValue([]);
    requestRuntimeRecordMock.mockReset();
  });

  it("loads cards first and hydrates main-brain in a follow-up request", async () => {
    let resolveSurface!: (value: RuntimeCenterSurfaceResponse) => void;
    requestRuntimeSurfaceMock.mockReturnValue(
      new Promise<RuntimeCenterSurfaceResponse>((resolve) => {
        resolveSurface = resolve;
      }),
    );
    const { result } = renderHook(() => useRuntimeCenter());

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(1);
    expect(requestRuntimeSurfaceMock).toHaveBeenCalledWith({
      sections: ["cards"],
    });
    expect(requestRuntimeBusinessAgentsMock).not.toHaveBeenCalled();

    await act(async () => {
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
      await Promise.resolve();
    });

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(result.current.data).toEqual(
      expect.objectContaining({ surface: mockOverview.surface }),
    );
    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(2, {
      sections: ["main_brain"],
    });
    expect(result.current.mainBrainData).toEqual(mockMainBrain);
    expect(result.current.buddySummary).toEqual(mockBuddySummary);
    expect(result.current.mainBrainUnavailable).toBe(false);
    expect(result.current.mainBrainError).toBeNull();
    expect(result.current.businessAgents).toEqual([
      expect.objectContaining({
        agent_id: "agent-ops-1",
        role_name: "Closer",
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
    expect(result.current.buddySummary).toBeNull();
    expect(result.current.mainBrainUnavailable).toBe(true);
    expect(result.current.mainBrainError).toBeNull();
    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(1, {
      sections: ["cards"],
    });
    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(2, {
      sections: ["main_brain"],
    });
  });

  it("filters retired goals, schedules, and main-brain overview cards while returning business agents from the canonical surface", async () => {
    requestRuntimeSurfaceMock.mockResolvedValue(
      mockSurface({
        cards: [
          {
            key: "goals",
            title: "Retired Work Items",
            source: "retired-work-item-service",
            status: "state-service",
            count: 1,
            summary: "retired work items",
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
    expect(result.current.businessAgents.map((agent) => agent.agent_id)).toEqual(["agent-ops-2"]);
    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
    expect(requestRuntimeBusinessAgentsMock).not.toHaveBeenCalled();
  });

  it("requests runtime surface without a browser-side buddy binding override", async () => {
    readBuddyProfileIdMock.mockReturnValue(null);

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(1, {
      sections: ["cards"],
    });
    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(2, {
      sections: ["main_brain"],
    });
    expect(readBuddyProfileIdMock).not.toHaveBeenCalled();
  });

  it("refreshes only the main-brain section on assignment events", async () => {
    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);

    vi.useFakeTimers();
    await act(async () => {
      runtimeEventHandler?.({
        event_name: "assignment.updated",
        payload: { assignment_id: "assignment-1" },
      });
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(3);
    expect(requestRuntimeSurfaceMock).toHaveBeenLastCalledWith({
      sections: ["main_brain"],
    });
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
    await act(async () => {
      runtimeEventHandler?.({
        event_name: "runtime.heartbeat",
        payload: {},
      });
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
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

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);

    vi.useFakeTimers();
    await act(async () => {
      runtimeEventHandler?.({
        event_name: "agent.updated",
        payload: { agent_id: "agent-ops-2" },
      });
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(3);
    expect(requestRuntimeSurfaceMock).toHaveBeenLastCalledWith({
      sections: ["cards"],
    });
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

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);

    vi.useFakeTimers();
    await act(async () => {
      runtimeEventHandler?.({
        event_name: "agent.updated",
        payload: { agent_id: "agent-ops-2" },
      });
      runtimeEventHandler?.({
        event_name: "assignment.updated",
        payload: { assignment_id: "assignment-1" },
      });
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(3);
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
    await act(async () => {
      runtimeEventHandler?.({
        event_name: "tool.updated",
        payload: { tool_id: "browser" },
      });
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(requestRuntimeSurfaceMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("reuses the last surface snapshot on remount while refreshing in the background", async () => {
    const { result, unmount } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    unmount();

    requestRuntimeSurfaceMock.mockResolvedValueOnce(
      mockSurface({
        generated_at: "2026-03-29T10:00:00Z",
        cards: [
          createAgentsCard({
            id: "agent-ops-9",
            title: "Closer Nine",
            kind: "agent",
            status: "active",
            owner: "Closer",
            summary: "Follow up retained deals",
            actions: {},
            meta: {},
          }),
        ],
      }),
    );

    const remounted = renderHook(() => useRuntimeCenter());

    expect(remounted.result.current.loading).toBe(false);
    expect(remounted.result.current.refreshing).toBe(true);
    expect(remounted.result.current.data?.generated_at).toBe(mockOverview.generated_at);

    await waitFor(() => remounted.result.current.refreshing === false);

    expect(remounted.result.current.data?.generated_at).toBe("2026-03-29T10:00:00Z");
    expect(remounted.result.current.businessAgents.map((agent) => agent.agent_id)).toEqual([
      "agent-ops-9",
    ]);
  });

  it("does not let a stale surface request override a newer reload result", async () => {
    const initialSurface = createDeferredPromise<RuntimeCenterSurfaceResponse>();
    const refreshedSurface = createDeferredPromise<RuntimeCenterSurfaceResponse>();
    requestRuntimeSurfaceMock
      .mockReturnValueOnce(initialSurface.promise)
      .mockReturnValueOnce(refreshedSurface.promise);

    const { result } = renderHook(() => useRuntimeCenter());

    expect(requestRuntimeSurfaceMock).toHaveBeenNthCalledWith(1, {
      sections: ["cards"],
    });

    await act(async () => {
      void result.current.reload();
      await Promise.resolve();
    });

    expect(requestRuntimeSurfaceMock.mock.calls[1]).toEqual([]);

    await act(async () => {
      refreshedSurface.resolve(
        mockSurface({
          generated_at: "2026-03-29T10:00:00Z",
          cards: [
            createAgentsCard({
              id: "agent-new",
              title: "Fresh Agent",
              kind: "agent",
              status: "active",
              owner: "Closer",
              summary: "Newer surface",
              actions: {},
              meta: {},
            }),
          ],
        }),
      );
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.data?.generated_at).toBe("2026-03-29T10:00:00Z");
      expect(result.current.businessAgents.map((agent) => agent.agent_id)).toEqual([
        "agent-new",
      ]);
    });

    await act(async () => {
      initialSurface.resolve(
        mockSurface({
          generated_at: "2026-03-29T09:00:00Z",
          cards: [
            createAgentsCard({
              id: "agent-old",
              title: "Old Agent",
              kind: "agent",
              status: "active",
              owner: "Closer",
              summary: "Older surface",
              actions: {},
              meta: {},
            }),
          ],
        }),
      );
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.data?.generated_at).toBe("2026-03-29T10:00:00Z");
      expect(result.current.businessAgents.map((agent) => agent.agent_id)).toEqual([
        "agent-new",
      ]);
    });
  });

  it("does not let a stale detail request override the latest opened detail", async () => {
    const detailA = createDeferredPromise<Record<string, unknown>>();
    const detailB = createDeferredPromise<Record<string, unknown>>();
    requestRuntimeRecordMock.mockImplementation((route: string) => {
      if (route === "/runtime-center/details/a") {
        return detailA.promise;
      }
      if (route === "/runtime-center/details/b") {
        return detailB.promise;
      }
      throw new Error(`Unexpected detail route: ${route}`);
    });

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(
      () =>
        !result.current.loading &&
        !result.current.mainBrainLoading &&
        !result.current.businessAgentsLoading,
    );

    await act(async () => {
      void result.current.openDetail("/runtime-center/details/a", "Detail A");
      void result.current.openDetail("/runtime-center/details/b", "Detail B");
      await Promise.resolve();
    });

    await act(async () => {
      detailB.resolve({ detail_id: "b", label: "New detail" });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.detail?.route).toBe("/runtime-center/details/b");
      expect(result.current.detail?.title).toBe("Detail B");
      expect(result.current.detail?.payload).toEqual(
        expect.objectContaining({ detail_id: "b" }),
      );
    });

    await act(async () => {
      detailA.resolve({ detail_id: "a", label: "Old detail" });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.detail?.route).toBe("/runtime-center/details/b");
      expect(result.current.detail?.title).toBe("Detail B");
      expect(result.current.detail?.payload).toEqual(
        expect.objectContaining({ detail_id: "b" }),
      );
    });
  });
});
