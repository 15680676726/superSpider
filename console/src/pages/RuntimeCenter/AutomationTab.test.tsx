// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    default: {
      ...actual.default,
      listRuntimeSchedules: vi.fn(),
      getRuntimeSchedule: vi.fn(),
      getRuntimeHeartbeat: vi.fn(),
    },
  };
});

vi.mock("./FixedSopPanel", () => ({
  default: () => <div data-testid="fixed-sop-panel" />,
}));

import api from "../../api";
import AutomationTab from "./AutomationTab";

const mockedApi = api as typeof api & {
  listRuntimeSchedules: ReturnType<typeof vi.fn>;
  getRuntimeSchedule: ReturnType<typeof vi.fn>;
  getRuntimeHeartbeat: ReturnType<typeof vi.fn>;
};

describe("AutomationTab", () => {
  it("shows host binding summary and drift warnings from schedule host_meta", async () => {
    mockedApi.listRuntimeSchedules.mockResolvedValue([
      {
        id: "office-report",
        title: "Daily Office Report",
        status: "scheduled",
        owner: "agent:ops",
        cron: "0 9 * * *",
        enabled: true,
        task_type: "agent",
        updated_at: "2026-03-27T08:00:00Z",
        last_run_at: null,
        next_run_at: "2026-03-27T09:00:00Z",
        last_error: null,
        route: "/api/runtime-center/schedules/office-report",
        actions: {
          run: "/api/runtime-center/schedules/office-report/run",
          pause: "/api/runtime-center/schedules/office-report/pause",
          delete: "/api/runtime-center/schedules/office-report",
        },
        host_meta: {
          environment_ref: "env:office-doc",
          session_mount_id: "session-office-current",
          host_requirement: {
            app_family: "office_document",
          },
          host_snapshot: {
            environment_ref: "env:office-doc-drift",
            session_mount_id: "session-office-drift",
            coordination: {
              recommended_scheduler_action: "handoff",
            },
            scheduler_inputs: {
              environment_ref: "env:office-doc-drift",
              session_mount_id: "session-office-drift",
            },
          },
        },
      },
    ]);
    mockedApi.getRuntimeHeartbeat.mockResolvedValue({
      heartbeat: {
        enabled: false,
        every: "6h",
        target: "main",
      },
      runtime: {
        status: "paused",
        enabled: false,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
      },
    });

    render(
      <AutomationTab
        openDetail={vi.fn().mockResolvedValue(undefined)}
        onRuntimeChanged={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockedApi.listRuntimeSchedules).toHaveBeenCalledTimes(1);
      expect(mockedApi.getRuntimeSchedule).not.toHaveBeenCalled();
    });

    expect(await screen.findByText("env:office-doc")).toBeTruthy();
    expect(screen.getByText("session-office-current")).toBeTruthy();
    expect(screen.getByText("office_document")).toBeTruthy();
    expect(screen.getByText("宿主协同：handoff")).toBeTruthy();
    expect(screen.getByText("宿主绑定警告")).toBeTruthy();
    expect(screen.getByText("环境引用不一致")).toBeTruthy();
    expect(screen.getByText("会话挂载不一致")).toBeTruthy();
  });
});
