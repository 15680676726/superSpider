// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>(
    "../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      getCurrentRuntimeHumanAssistTask: vi.fn(),
      listRuntimeHumanAssistTasks: vi.fn(),
      getRuntimeHumanAssistTaskDetail: vi.fn(),
    },
  };
});

import api from "../../api";
import { ChatHumanAssistPanel } from "./ChatHumanAssistPanel";

const mockedGetCurrentRuntimeHumanAssistTask = vi.mocked(
  api.getCurrentRuntimeHumanAssistTask,
);
const mockedListRuntimeHumanAssistTasks = vi.mocked(
  api.listRuntimeHumanAssistTasks,
);
const mockedGetRuntimeHumanAssistTaskDetail = vi.mocked(
  api.getRuntimeHumanAssistTaskDetail,
);

const currentTask = {
  id: "human-assist:task-1",
  chat_thread_id: "industry-chat:industry-1:execution-core",
  title: "上传回执截图",
  summary: "需要宿主补一段支付回执证明。",
  required_action: "请在聊天里上传支付回执截图。",
  status: "issued",
  route: "/api/runtime-center/human-assist-tasks/human-assist:task-1",
  tasks_route:
    "/api/runtime-center/human-assist-tasks?chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core",
  current_route:
    "/api/runtime-center/human-assist-tasks/current?chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core",
};

const detailPayload = {
  task: {
    ...currentTask,
    acceptance_spec: {
      hard_anchors: ["receipt"],
      result_anchors: ["uploaded"],
      negative_anchors: ["missing"],
    },
    reward_preview: {
      "协作值": 2,
      "同调经验": 1,
    },
    reward_result: {
      granted: true,
      "协作值": 2,
    },
    issued_at: "2026-03-28T10:00:00+00:00",
    submitted_at: null,
  },
  routes: {
    self: "/api/runtime-center/human-assist-tasks/human-assist:task-1",
    list: currentTask.tasks_route,
    current: currentTask.current_route,
  },
};

describe("ChatHumanAssistPanel", () => {
  afterEach(() => {
    cleanup();
    mockedGetCurrentRuntimeHumanAssistTask.mockReset();
    mockedListRuntimeHumanAssistTasks.mockReset();
    mockedGetRuntimeHumanAssistTaskDetail.mockReset();
  });

  it("renders the current task strip from thread meta and refreshes current state", async () => {
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(currentTask as never);
    mockedListRuntimeHumanAssistTasks.mockResolvedValue([currentTask] as never);
    mockedGetRuntimeHumanAssistTaskDetail.mockResolvedValue(detailPayload as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    expect(screen.getByText("上传回执截图")).toBeTruthy();
    expect(screen.getByText("待提交")).toBeTruthy();

    await waitFor(() => {
      expect(mockedGetCurrentRuntimeHumanAssistTask).toHaveBeenCalledWith(
        "industry-chat:industry-1:execution-core",
      );
    });
  });

  it("loads task history and detail when opening the task list modal", async () => {
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(currentTask as never);
    mockedListRuntimeHumanAssistTasks.mockResolvedValue([currentTask] as never);
    mockedGetRuntimeHumanAssistTaskDetail.mockResolvedValue(detailPayload as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "任务记录" }));

    await waitFor(() => {
      expect(mockedListRuntimeHumanAssistTasks).toHaveBeenCalledWith({
        chat_thread_id: "industry-chat:industry-1:execution-core",
        limit: 50,
      });
    });
    await waitFor(() => {
      expect(mockedGetRuntimeHumanAssistTaskDetail).toHaveBeenCalledWith(
        "human-assist:task-1",
      );
    });

    expect(screen.getAllByText("上传回执截图").length).toBeGreaterThan(0);
    expect(screen.getByText("需要宿主补一段支付回执证明。")).toBeTruthy();
    expect(screen.getAllByText("请在聊天里上传支付回执截图。").length).toBeGreaterThan(0);
    expect(screen.getByText("receipt")).toBeTruthy();
    expect(screen.getByText("uploaded")).toBeTruthy();
  });
});
