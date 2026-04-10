// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const stateMock = vi.fn();

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    default: {
      ...actual.default,
      installCapabilityMarketProject: vi.fn(),
      getCapabilityMarketProjectInstallJob: vi.fn(),
      getCapabilityMarketProjectInstallJobResult: vi.fn(),
    },
  };
});

vi.mock("./useCapabilityMarketState", () => ({
  useCapabilityMarketState: (...args: unknown[]) => stateMock(...args),
}));

import api from "../../api";
import CapabilityMarketPage from "./index";

const mockedInstallProject = vi.mocked(api.installCapabilityMarketProject);
const mockedGetProjectInstallJob = vi.mocked(api.getCapabilityMarketProjectInstallJob);
const mockedGetProjectInstallJobResult = vi.mocked(api.getCapabilityMarketProjectInstallJobResult);

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
    setProjectInstallKey: vi.fn(),
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
    mockedInstallProject.mockReset();
    mockedGetProjectInstallJob.mockReset();
    mockedGetProjectInstallJobResult.mockReset();
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

  it("shows donor install job acceptance instead of pretending the project is already ready", async () => {
    mockedInstallProject.mockResolvedValue({
      accepted: true,
      task_id: "ktask:project-install-1",
      status: "queued",
      phase: "executing",
      title: "Install project donor https://github.com/psf/black",
      source_url: "https://github.com/psf/black",
      capability_kind: "project-package",
      candidate_id: "candidate-black",
      progress_summary: "Project donor install job accepted.",
      routes: {
        status: "/api/capability-market/projects/install-jobs/ktask:project-install-1",
        result:
          "/api/capability-market/projects/install-jobs/ktask:project-install-1/result",
      },
    } as never);
    mockedGetProjectInstallJob.mockResolvedValue({
      task_id: "ktask:project-install-1",
      status: "running",
      phase: "executing",
      stage: "installing",
      title: "Install project donor https://github.com/psf/black",
      source_url: "https://github.com/psf/black",
      capability_kind: "project-package",
      candidate_id: "candidate-black",
      target_agent_id: null,
      progress_summary: "Starting external project donor install job.",
      error: null,
      installed_capability_ids: [],
      result: null,
      created_at: null,
      updated_at: null,
      routes: {
        status: "/api/capability-market/projects/install-jobs/ktask:project-install-1",
        result:
          "/api/capability-market/projects/install-jobs/ktask:project-install-1/result",
      },
    } as never);
    stateMock.mockReturnValue({
      ...baseState,
      activeTab: "projects",
      projectResults: [
        {
          display_name: "psf/black",
          summary: "Python formatter",
          source_kind: "github-repo",
          candidate_kind: "project",
          source_url: "https://github.com/psf/black",
          version: "main",
          capability_keys: ["formatting"],
          install_supported: true,
          metadata: {},
          routes: {},
        },
      ],
    });

    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /安\s*装/ }));

    expect(
      await screen.findByText("Project donor install job accepted."),
    ).toBeInTheDocument();
    expect(mockedGetProjectInstallJobResult).not.toHaveBeenCalled();
  });
});
