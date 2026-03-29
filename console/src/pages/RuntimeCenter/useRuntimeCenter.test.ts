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
  current_cycle: null,
  assignments: [],
  reports: [],
  environment: {},
  evidence: { count: 0, summary: "", route: null, entries: [], meta: {} },
  decisions: { count: 0, summary: "", route: null, entries: [], meta: {} },
  patches: { count: 0, summary: "", route: null, entries: [], meta: {} },
  signals: {},
  meta: {},
};

const requestRuntimeOverviewMock = vi.fn();
const requestRuntimeMainBrainMock = vi.fn();

vi.mock("../../runtime/runtimeSurfaceClient", () => ({
  normalizeRuntimePath: vi.fn((path: string) => path),
  requestRuntimeOverview: () => requestRuntimeOverviewMock(),
  requestRuntimeRecord: vi.fn(),
  requestRuntimeMainBrain: () => requestRuntimeMainBrainMock(),
}));

vi.mock("../../runtime/eventBus", () => ({
  subscribe: vi.fn(() => () => {}),
}));

describe("useRuntimeCenter", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("loads both overview and dedicated main-brain payloads", async () => {
    requestRuntimeOverviewMock.mockResolvedValue(mockOverview);
    requestRuntimeMainBrainMock.mockResolvedValue(mockMainBrain);

    const { result } = renderHook(() => useRuntimeCenter());

    await waitFor(() => !result.current.loading && !result.current.mainBrainLoading);

    expect(result.current.data).toEqual(expect.objectContaining({ surface: mockOverview.surface }));
    expect(result.current.mainBrainData).toEqual(mockMainBrain);
    expect(result.current.mainBrainUnavailable).toBe(false);
    expect(result.current.mainBrainError).toBeNull();
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

    await waitFor(() => !result.current.loading && !result.current.mainBrainLoading);

    expect(result.current.mainBrainData).toBeNull();
    expect(result.current.mainBrainUnavailable).toBe(true);
    expect(result.current.mainBrainError).toBeNull();
  });
});
