// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const stateMock = vi.fn();

vi.mock("./useCapabilityMarketState", () => ({
  useCapabilityMarketState: (...args: unknown[]) => stateMock(...args),
}));

import CapabilityMarketPage from "./index";

describe("CapabilityMarketPage", () => {
  const baseState = {
    activeTab: "install-templates",
    categoryCounts: { all: 0 },
    curatedCategory: "all",
    curatedError: null,
    curatedLoading: false,
    curatedPage: 1,
    curatedQuery: "",
    curatedRangeText: "暂无结果",
    curatedReviewAcknowledgements: {},
    filteredCuratedItems: [],
    pagedCuratedItems: [],
    handleRefreshAll: vi.fn(),
    installedCapabilities: [],
    installingCuratedId: null,
    loadCurated: vi.fn(),
    loadMcpCatalog: vi.fn(),
    loadProjects: vi.fn(),
    mcpCatalog: { items: [], categories: [], next_cursor: null },
    mcpCatalogLoading: false,
    mcpClients: [],
    mcpQuery: "",
    projectInstallKey: null,
    projectLoading: false,
    projectQuery: "",
    projectResults: [],
    requestedTemplateId: "browser-companion",
    selectedTemplate: {
      id: "browser-companion",
      name: "浏览器伴随体",
      install_kind: "builtin-runtime",
      ready: false,
      installed: false,
      config_schema: { fields: [] },
    },
    setCuratedCategory: vi.fn(),
    setCuratedPage: vi.fn(),
    setCuratedQuery: vi.fn(),
    setCuratedReviewAcknowledgements: vi.fn(),
    setInstallingCuratedId: vi.fn(),
    setMcpQuery: vi.fn(),
    setProjectQuery: vi.fn(),
    setTemplateActionKey: vi.fn(),
    setTemplateInstallSummary: vi.fn(),
    skills: [],
    templateActionKey: null,
    templateInstallSummary: null,
    templates: [
      {
        id: "browser-companion",
        name: "浏览器伴随体",
        install_kind: "builtin-runtime",
        ready: false,
        installed: false,
      },
    ],
    templatesLoading: false,
    updateSearchParams: vi.fn(),
  };

  beforeEach(() => {
    stateMock.mockReset();
    stateMock.mockReturnValue(baseState);
  });

  it("renders the new projects tab alongside the existing market tabs", () => {
    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: "项目" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "安装模板" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "MCP" })).toBeInTheDocument();
  });

  it("localizes the project search controls for regular users", () => {
    stateMock.mockReturnValue({
      ...baseState,
      activeTab: "projects",
    });

    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByPlaceholderText("输入 GitHub 仓库地址或搜索词"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /搜\s*索/ })).toBeInTheDocument();
  });

  it("shows stable local market counts in the page header instead of blank remote counters", () => {
    stateMock.mockReturnValue({
      ...baseState,
      installedCapabilities: [
        { id: "project:black", name: "Black", enabled: true },
        { id: "project:ruff", name: "Ruff", enabled: true },
      ],
      skills: [
        {
          name: "research",
          source: "customized",
          enabled: true,
          content: "# skill",
        },
      ],
      mcpClients: [{ key: "filesystem", name: "filesystem", enabled: true }],
      templates: [
        ...baseState.templates,
        {
          id: "desktop-companion",
          name: "桌面伴随体",
          install_kind: "builtin-runtime",
          ready: true,
          installed: true,
        },
      ],
    });

    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("已装能力")).toBeInTheDocument();
    expect(screen.getByText("可用技能")).toBeInTheDocument();
    expect(screen.getAllByText("安装模板").length).toBeGreaterThan(0);
    expect(screen.getByText("MCP 客户端")).toBeInTheDocument();
  });

  it("renders installed capabilities and skills from page state instead of hard-coded empty lists", () => {
    stateMock.mockReturnValue({
      ...baseState,
      activeTab: "installed",
      installedCapabilities: [
        { id: "project:black", name: "Black", enabled: true },
      ],
    });

    const { rerender } = render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Black")).toBeInTheDocument();

    stateMock.mockReturnValue({
      ...baseState,
      activeTab: "skills",
      skills: [
        {
          name: "research",
          source: "customized",
          enabled: true,
          content: "# skill",
        },
      ],
    });

    rerender(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("research")).toBeInTheDocument();
  });

  it("uses MCP catalog search when pressing Enter in the MCP tab", () => {
    const loadCurated = vi.fn();
    const loadMcpCatalog = vi.fn();
    stateMock.mockReturnValue({
      ...baseState,
      activeTab: "mcp",
      loadCurated,
      loadMcpCatalog,
      mcpQuery: "filesystem",
    });

    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    const input = screen.getByDisplayValue("filesystem");
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });

    expect(loadMcpCatalog).toHaveBeenCalled();
    expect(loadCurated).not.toHaveBeenCalled();
  });
});
