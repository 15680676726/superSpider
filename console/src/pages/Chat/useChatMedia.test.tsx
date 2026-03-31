// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>(
    "../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      ingestMedia: vi.fn(),
      listMediaAnalyses: vi.fn(),
      resolveMediaLink: vi.fn(),
    },
  };
});

import api from "../../api";
import { useChatMedia } from "./useChatMedia";

const mockedListMediaAnalyses = vi.mocked(api.listMediaAnalyses);

describe("useChatMedia", () => {
  afterEach(() => {
    mockedListMediaAnalyses.mockReset();
  });

  it("loads completed analyses for the active thread and syncs selected ids", async () => {
    mockedListMediaAnalyses.mockResolvedValue([
      {
        analysis_id: "analysis-1",
        status: "completed",
        summary: "Quarterly report",
      },
    ] as never);

    const { result } = renderHook(() =>
      useChatMedia({
        activeChatThreadId: "thread-1",
        activeWorkContextId: null,
      }),
    );

    await waitFor(() => {
      expect(result.current.mediaAnalyses).toHaveLength(1);
    });

    expect(result.current.selectedMediaAnalysisIds).toEqual(["analysis-1"]);
    expect(result.current.selectedMediaAnalysisIdsRef.current).toEqual([
      "analysis-1",
    ]);
    expect(mockedListMediaAnalyses).toHaveBeenCalledWith({
      entry_point: "chat",
      limit: 60,
      status: "completed",
      thread_id: "thread-1",
      work_context_id: undefined,
    });
  });

  it("keeps media continuity by querying the shared work context when available", async () => {
    mockedListMediaAnalyses.mockResolvedValue([
      {
        analysis_id: "analysis-ctx-1",
        status: "completed",
        summary: "Resumed work-context material",
      },
    ] as never);

    const { result } = renderHook(() =>
      useChatMedia({
        activeChatThreadId: "thread-resumed",
        activeWorkContextId: "ctx-media-ops",
      }),
    );

    await waitFor(() => {
      expect(result.current.mediaAnalyses).toHaveLength(1);
    });

    expect(mockedListMediaAnalyses).toHaveBeenCalledWith({
      entry_point: "chat",
      limit: 60,
      status: "completed",
      thread_id: "thread-resumed",
      work_context_id: "ctx-media-ops",
    });
  });
});
