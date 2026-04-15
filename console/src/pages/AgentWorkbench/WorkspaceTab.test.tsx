// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import WorkspaceTab from "./WorkspaceTab";

vi.mock("../../api/modules/workspace", () => ({
  workspaceApi: {
    downloadWorkspace: vi.fn(),
    uploadFile: vi.fn(),
  },
}));

vi.mock("../Agent/Workspace/components", () => ({
  FileEditor: () => <div>file-editor</div>,
  FileListPanel: () => <div>file-list</div>,
  useAgentsData: () => ({
    files: [],
    selectedFile: null,
    dailyMemories: [],
    expandedMemory: null,
    fileContent: "",
    loading: false,
    workspacePath: null,
    hasChanges: false,
    setFileContent: vi.fn(),
    fetchFiles: vi.fn(),
    handleFileClick: vi.fn(),
    handleDailyMemoryClick: vi.fn(),
    handleSave: vi.fn(),
    handleReset: vi.fn(),
  }),
}));

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("WorkspaceTab", () => {
  it("renders environment artifacts from canonical artifact_type payloads", () => {
    render(
      <WorkspaceTab
        agent={
          {
            agent_id: "agent-seat-1",
            name: "Research Operator",
          } as never
        }
        agentDetail={
          {
            environments: [],
            workspace: {
              current_environment_id: "env-1",
              current_environment_ref: "session:web:main",
              files_supported: false,
              current_environment: {
                id: "env-1",
                kind: "workspace",
                display_name: "Workspace runtime",
                ref: "session:web:main",
                status: "active",
                route: "/api/runtime-center/environments/env-1",
                artifacts: [
                  {
                    artifact_id: "artifact-file-1",
                    artifact_type: "file",
                    result_summary: "运营日报文件",
                    storage_uri: "file:///tmp/report.md",
                  },
                ],
                stats: {
                  artifact_count: 1,
                },
              },
            },
          } as never
        }
        loading={false}
        error={null}
      />,
    );

    expect(screen.getByText("文件")).toBeTruthy();
    expect(screen.getByText("运营日报文件")).toBeTruthy();
    expect(screen.getByText("file:///tmp/report.md")).toBeTruthy();
    expect(screen.queryByText("artifact-file-1")).toBeNull();
  });

  it("prefers replay and artifact summaries over raw ids when type labels are absent", () => {
    render(
      <WorkspaceTab
        agent={
          {
            agent_id: "agent-seat-1",
            name: "Research Operator",
          } as never
        }
        agentDetail={
          {
            environments: [],
            workspace: {
              current_environment_id: "env-1",
              current_environment_ref: "session:web:main",
              files_supported: false,
              current_environment: {
                id: "env-1",
                kind: "workspace",
                display_name: "Workspace runtime",
                ref: "session:web:main",
                status: "active",
                route: "/api/runtime-center/environments/env-1",
                replays: [
                  {
                    replay_id: "replay-123",
                    action_summary: "浏览器执行回放",
                    storage_uri: "replay://trace-1",
                  },
                ],
                artifacts: [
                  {
                    artifact_id: "artifact-123",
                    result_summary: "Captured invoice PDF",
                    storage_uri: "file:///tmp/invoice.pdf",
                  },
                ],
              },
            },
          } as never
        }
        loading={false}
        error={null}
      />,
    );

    expect(screen.getByText("浏览器执行回放")).toBeTruthy();
    expect(screen.getByText("Captured invoice PDF")).toBeTruthy();
    expect(screen.queryByText("replay-123")).toBeNull();
    expect(screen.queryByText("artifact-123")).toBeNull();
  });
});
