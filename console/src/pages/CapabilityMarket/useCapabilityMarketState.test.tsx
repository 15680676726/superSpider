// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { Form } from "antd";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    default: {
      ...actual.default,
      getCapabilityMarketOverview: vi.fn(),
      searchCapabilityMarketProjects: vi.fn(),
      searchCapabilityMarketMcpCatalog: vi.fn(),
      listCapabilityMarketInstallTemplates: vi.fn(),
      searchCapabilityMarketCuratedCatalog: vi.fn(),
    },
  };
});

import api from "../../api";
import { useCapabilityMarketState } from "./useCapabilityMarketState";

const mockedGetOverview = vi.mocked(api.getCapabilityMarketOverview);
const mockedSearchProjects = vi.mocked(api.searchCapabilityMarketProjects);
const mockedSearchMcpCatalog = vi.mocked(api.searchCapabilityMarketMcpCatalog);
const mockedListTemplates = vi.mocked(api.listCapabilityMarketInstallTemplates);
const mockedSearchCurated = vi.mocked(api.searchCapabilityMarketCuratedCatalog);

describe("useCapabilityMarketState", () => {
  afterEach(() => {
    mockedGetOverview.mockReset();
    mockedSearchProjects.mockReset();
    mockedSearchMcpCatalog.mockReset();
    mockedListTemplates.mockReset();
    mockedSearchCurated.mockReset();
  });

  it("loads and refreshes market surfaces through the extracted page-state hook", async () => {
    mockedGetOverview.mockResolvedValue({ installed: [], mcp_clients: [] } as never);
    mockedSearchProjects.mockResolvedValue([] as never);
    mockedSearchMcpCatalog.mockResolvedValue({
      items: [],
      categories: [{ key: "all", label: "全部" }],
      next_cursor: null,
    } as never);
    mockedListTemplates.mockResolvedValue([] as never);
    mockedSearchCurated.mockResolvedValue({ items: [] } as never);

    const { result } = renderHook(() => {
      const [templateForm] = Form.useForm<Record<string, unknown>>();
      const [mcpForm] = Form.useForm<Record<string, any>>();
      const [searchParams, setSearchParams] = useState(new URLSearchParams());
      return useCapabilityMarketState({
        templateForm,
        mcpForm,
        searchParams,
        setSearchParams,
      });
    });

    await waitFor(() => {
      expect(result.current.overview).not.toBeNull();
      expect(result.current.templates).toEqual([]);
    });

    const initialOverviewCalls = mockedGetOverview.mock.calls.length;
    const initialTemplateCalls = mockedListTemplates.mock.calls.length;

    await act(async () => {
      await result.current.handleRefreshAll();
    });

    await waitFor(() => {
      expect(mockedGetOverview.mock.calls.length).toBeGreaterThan(initialOverviewCalls);
      expect(mockedSearchProjects).toHaveBeenCalled();
      expect(mockedListTemplates.mock.calls.length).toBeGreaterThan(initialTemplateCalls);
    });
  });

  it("uses a readable Chinese fallback label for the MCP category list", async () => {
    mockedGetOverview.mockResolvedValue({ installed: [], mcp_clients: [] } as never);
    mockedSearchProjects.mockResolvedValue([] as never);
    mockedSearchMcpCatalog.mockResolvedValue({
      items: [],
      categories: [],
      next_cursor: null,
    } as never);
    mockedListTemplates.mockResolvedValue([] as never);
    mockedSearchCurated.mockResolvedValue({ items: [] } as never);

    const { result } = renderHook(() => {
      const [templateForm] = Form.useForm<Record<string, unknown>>();
      const [mcpForm] = Form.useForm<Record<string, any>>();
      const [searchParams, setSearchParams] = useState(new URLSearchParams());
      return useCapabilityMarketState({
        templateForm,
        mcpForm,
        searchParams,
        setSearchParams,
      });
    });

    await waitFor(() => {
      expect(result.current.mcpCategoryOptions).toEqual([{ key: "all", label: "全部" }]);
    });
  });
});
