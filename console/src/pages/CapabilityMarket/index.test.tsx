// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("./useCapabilityMarketState", () => ({
  useCapabilityMarketState: vi.fn(() => ({
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
    handleRefreshAll: vi.fn(),
    installingCuratedId: null,
    loadCurated: vi.fn(),
    mcpCatalog: { items: [], categories: [], next_cursor: null },
    mcpCatalogLoading: false,
    mcpQuery: "",
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
    setTemplateActionKey: vi.fn(),
    setTemplateInstallSummary: vi.fn(),
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
  })),
}));

import CapabilityMarketPage from "./index";

describe("CapabilityMarketPage", () => {
  it("renders key capability market labels in readable Chinese", () => {
    render(
      <MemoryRouter>
        <CapabilityMarketPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("刷新")).toBeInTheDocument();
    expect(screen.getByText("安装模板")).toBeInTheDocument();
    expect(screen.getByText("模板")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "技能" })).toBeInTheDocument();
    expect(screen.getByText("待安装")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /安\s*装/ }).length).toBeGreaterThan(0);

    expect(screen.queryByText("鍒锋柊")).not.toBeInTheDocument();
    expect(screen.queryByText("瀹夎妯℃澘")).not.toBeInTheDocument();
    expect(screen.queryByText("妯℃澘")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Skills" })).not.toBeInTheDocument();
    expect(screen.queryByText("new")).not.toBeInTheDocument();
  });
});
