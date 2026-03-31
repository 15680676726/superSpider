// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const loadMock = vi.fn();
const refreshActiveModelsMock = vi.fn();
const subscribeMock = vi.fn();

vi.mock("../../../stores", () => ({
  useModelStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      providers: [],
      activeModels: null,
      loading: false,
      error: null,
      load: loadMock,
      refreshActiveModels: refreshActiveModelsMock,
    }),
}));

vi.mock("../../../runtime/eventBus", () => ({
  subscribe: (...args: unknown[]) => subscribeMock(...args),
}));

import { useProviders } from "./useProviders";

describe("useProviders", () => {
  beforeEach(() => {
    loadMock.mockReset();
    refreshActiveModelsMock.mockReset();
    subscribeMock.mockReset();
    subscribeMock.mockReturnValue(() => {});
    loadMock.mockResolvedValue(undefined);
    refreshActiveModelsMock.mockResolvedValue(undefined);
  });

  it("uses a full reload even for silent refreshes", async () => {
    const { result } = renderHook(() => useProviders());

    expect(loadMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.fetchAll(false);
    });

    expect(loadMock).toHaveBeenCalledTimes(2);
    expect(refreshActiveModelsMock).not.toHaveBeenCalled();
  });
});
