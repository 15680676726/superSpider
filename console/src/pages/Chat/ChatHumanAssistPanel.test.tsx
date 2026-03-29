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
import {
  ChatHumanAssistPanel,
  resolveHumanAssistStatusPresentation,
} from "./ChatHumanAssistPanel";
import * as runtimeTransport from "./runtimeTransport";

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
    vi.restoreAllMocks();
  });

  it("maps human assist statuses to canonical readable label and color", () => {
    expect(resolveHumanAssistStatusPresentation("issued")).toEqual({
      label: "待提交",
      color: "blue",
    });
    expect(resolveHumanAssistStatusPresentation("need_more_evidence")).toEqual({
      label: "待补证",
      color: "warning",
    });
    expect(resolveHumanAssistStatusPresentation("handoff_blocked")).toEqual({
      label: "\u6062\u590d\u53d7\u963b",
      color: "warning",
    });
    expect(resolveHumanAssistStatusPresentation("accepted")).toEqual({
      label: "已通过",
      color: "success",
    });
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

  it("renders a readable label for handoff_blocked instead of the raw status code", async () => {
    const blockedTask = {
      ...currentTask,
      status: "handoff_blocked",
    };
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(blockedTask as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: blockedTask }}
      />,
    );

    expect(screen.getByText("\u6062\u590d\u53d7\u963b")).toBeTruthy();
    expect(screen.queryByText("handoff_blocked")).toBeNull();
  });

  it.each([
    ["resume_queued", "\u5df2\u9a8c\u6536"],
    ["need_more_evidence", "\u5f85\u8865\u8bc1"],
    ["closed", "\u5df2\u5173\u95ed"],
  ])(
    "renders a readable status label for %s",
    async (status, label) => {
      const task = {
        ...currentTask,
        status,
      };
      mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(task as never);

      render(
        <ChatHumanAssistPanel
          activeChatThreadId="industry-chat:industry-1:execution-core"
          threadMeta={{ human_assist_task: task }}
        />,
      );

      expect(screen.getByText(label)).toBeTruthy();
      expect(screen.queryByText(status)).toBeNull();
    },
  );

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

  it("arms the next chat message as a human assist submission", async () => {
    const queueSpy = vi.spyOn(
      runtimeTransport,
      "queueHumanAssistSubmissionForNextMessage",
    );
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(currentTask as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "提交任务" }));

    expect(queueSpy).toHaveBeenCalledWith(
      "industry-chat:industry-1:execution-core",
    );
  });

  it("refreshes the current task strip when a human assist dirty event clears the task", async () => {
    mockedGetCurrentRuntimeHumanAssistTask
      .mockResolvedValueOnce(currentTask as never)
      .mockResolvedValueOnce(null as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    await waitFor(() => {
      expect(mockedGetCurrentRuntimeHumanAssistTask).toHaveBeenCalledTimes(1);
    });

    window.dispatchEvent(new Event("copaw:human-assist-dirty"));

    await waitFor(() => {
      expect(mockedGetCurrentRuntimeHumanAssistTask).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText("当前无待协作任务")).toBeTruthy();
  });

  it("preserves full text for truncated chat rows via title attributes", async () => {
    const longTitle =
      "这是一个特别长的协作任务标题，用来验证聊天页行级元素在被截断时仍然可以通过悬浮看到完整内容";
    const longSummary =
      "这是一个特别长的协作任务摘要，用来验证摘要行在当前宽度不足时不会继续撑破布局，并且仍然保留完整文本。";
    const longAction =
      "这是一个特别长的宿主动作说明，用来验证详情区与任务条都能在截断后保留完整文本提示。";
    const longTask = {
      ...currentTask,
      title: longTitle,
      summary: longSummary,
      required_action: longAction,
    };
    const longDetail = {
      ...detailPayload,
      task: {
        ...detailPayload.task,
        title: longTitle,
        summary: longSummary,
        required_action: longAction,
      },
    };

    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(longTask as never);
    mockedListRuntimeHumanAssistTasks.mockResolvedValue([longTask] as never);
    mockedGetRuntimeHumanAssistTaskDetail.mockResolvedValue(longDetail as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: longTask }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "任务记录" }));

    await waitFor(() => {
      expect(mockedGetRuntimeHumanAssistTaskDetail).toHaveBeenCalledWith(
        "human-assist:task-1",
      );
    });

    expect(screen.getAllByTitle(longTitle).length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(longSummary).length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(longAction).length).toBeGreaterThan(0);
  });
});
