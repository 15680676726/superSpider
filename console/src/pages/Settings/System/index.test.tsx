// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SystemSettingsPage from "./index";

const { apiMock, requestMock } = vi.hoisted(() => ({
  apiMock: {
    getSystemOverview: vi.fn(),
    runSystemSelfCheck: vi.fn(),
    getProviderFallback: vi.fn(),
    listProviders: vi.fn(),
    downloadSystemBackup: vi.fn(),
    restoreSystemBackup: vi.fn(),
    setProviderFallback: vi.fn(),
  },
  requestMock: vi.fn(),
}));

vi.mock("../../../api", () => ({
  default: apiMock,
  request: (...args: unknown[]) => requestMock(...args),
}));

describe("SystemSettingsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiMock.getSystemOverview.mockResolvedValue({
      backup: {
        file_count: 3,
        total_size: 1024,
        root_path: "D:/word/copaw/workdir",
      },
      self_check: {
        state_db_path: "state/phase1.sqlite3",
        evidence_db_path: "evidence/phase1.sqlite3",
      },
      providers: {
        active_model: {
          provider_id: "openai",
          model: "gpt-5.4",
        },
      },
      runtime: {
        startup_recovery: {
          status: "ready",
          summary: "Recovered cleanly",
        },
        governance_route: "/runtime-center/governance/status",
        recovery_route: "/runtime-center/recovery/latest",
        events_route: "/runtime-center/events",
      },
    });
    apiMock.runSystemSelfCheck.mockResolvedValue({
      overall_status: "pass",
      checks: [
        {
          name: "working_dir",
          status: "pass",
          summary: "Working directory available",
          meta: {},
        },
        {
          name: "provider_fallback",
          status: "warn",
          summary: "Fallback is not configured",
          meta: {},
        },
        {
          name: "startup_recovery",
          status: "pass",
          summary: "Recovered cleanly",
          meta: {},
        },
        {
          name: "runtime_event_bus",
          status: "pass",
          summary: "Runtime event bus is wired",
          meta: {},
        },
      ],
    });
    apiMock.getProviderFallback.mockResolvedValue({
      enabled: false,
      candidates: [],
    });
    apiMock.listProviders.mockResolvedValue([
      {
        id: "openai",
        name: "OpenAI",
        models: [
          {
            id: "gpt-5.4",
            name: "GPT-5.4",
          },
        ],
      },
    ]);
  });

  it("keeps the page focused on maintenance and redirects runtime facts to the main-brain cockpit", async () => {
    render(<SystemSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("系统维护")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/主脑驾驶舱/).length).toBeGreaterThan(0);
    expect(screen.getByText("备份与恢复")).toBeInTheDocument();
    expect(screen.getByText("健康自检与维护")).toBeInTheDocument();
    expect(screen.getAllByText("提供商回退").length).toBeGreaterThan(0);

    expect(screen.queryByText("平台中枢")).not.toBeInTheDocument();
    expect(screen.queryByText("运行时链路")).not.toBeInTheDocument();
    expect(screen.queryByText("启动恢复与健康状态")).toBeNull();
    expect(screen.queryByText("Recovered cleanly")).toBeNull();
    expect(screen.queryByText("Runtime event bus is wired")).toBeNull();
    expect(requestMock).not.toHaveBeenCalled();
  });
});
