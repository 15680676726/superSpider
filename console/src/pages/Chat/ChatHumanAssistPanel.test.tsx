// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
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
  title: "去工商局提交营业执照材料",
  summary: "这一步必须由你亲自到现场完成，系统无法替你出面办理。",
  required_action: "请你去工商局窗口提交材料，然后在聊天里告诉我办理结果或上传回执。",
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
      协作值: 2,
      同调经验: 1,
    },
    reward_result: {
      granted: true,
      协作值: 2,
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
      label: "待你完成",
      color: "blue",
    });
    expect(resolveHumanAssistStatusPresentation("need_more_evidence")).toEqual({
      label: "待补证",
      color: "warning",
    });
    expect(resolveHumanAssistStatusPresentation("handoff_blocked")).toEqual({
      label: "恢复受阻",
      color: "warning",
    });
    expect(resolveHumanAssistStatusPresentation("accepted")).toEqual({
      label: "已通过",
      color: "success",
    });
  });

  it("does not render an exception strip when there is no active human-assist task", async () => {
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(null as never);

    const { container } = render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{}}
      />,
    );

    await waitFor(() => {
      expect(mockedGetCurrentRuntimeHumanAssistTask).toHaveBeenCalledWith(
        "industry-chat:industry-1:execution-core",
      );
    });

    expect(screen.queryByText("伙伴提醒")).toBeNull();
    expect(screen.queryByRole("button", { name: "查看协作记录" })).toBeNull();
    expect(container.firstChild).toBeNull();
  });

  it("renders the current exception task from thread meta and refreshes current state", async () => {
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(currentTask as never);
    mockedListRuntimeHumanAssistTasks.mockResolvedValue([currentTask] as never);
    mockedGetRuntimeHumanAssistTaskDetail.mockResolvedValue(detailPayload as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    expect(screen.getByText("伙伴提醒")).toBeTruthy();
    expect(screen.getByText("去工商局提交营业执照材料")).toBeTruthy();
    expect(screen.getByText("待你完成")).toBeTruthy();

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

    expect(screen.getByText("恢复受阻")).toBeTruthy();
    expect(screen.queryByText("handoff_blocked")).toBeNull();
  });

  it.each([
    ["resume_queued", "已验收"],
    ["need_more_evidence", "待补证"],
    ["closed", "已关闭"],
  ])("renders a readable status label for %s", async (status, label) => {
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
  });

  it("loads collaboration history and detail when opening the record modal", async () => {
    mockedGetCurrentRuntimeHumanAssistTask.mockResolvedValue(currentTask as never);
    mockedListRuntimeHumanAssistTasks.mockResolvedValue([currentTask] as never);
    mockedGetRuntimeHumanAssistTaskDetail.mockResolvedValue(detailPayload as never);

    render(
      <ChatHumanAssistPanel
        activeChatThreadId="industry-chat:industry-1:execution-core"
        threadMeta={{ human_assist_task: currentTask }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看协作记录" }));

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

    expect(screen.getAllByText("去工商局提交营业执照材料").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("这一步必须由你亲自到现场完成，系统无法替你出面办理。")
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("请你去工商局窗口提交材料，然后在聊天里告诉我办理结果或上传回执。")
        .length,
    ).toBeGreaterThan(0);
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

    fireEvent.click(screen.getByRole("button", { name: "我已在聊天里完成" }));

    expect(queueSpy).toHaveBeenCalledWith(
      "industry-chat:industry-1:execution-core",
    );
  });

  it("removes the strip when a human assist dirty event clears the active task", async () => {
    mockedGetCurrentRuntimeHumanAssistTask
      .mockResolvedValueOnce(currentTask as never)
      .mockResolvedValueOnce(null as never);

    const { container } = render(
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

    expect(screen.queryByText("伙伴提醒")).toBeNull();
    expect(screen.queryByText("当前无待协作任务")).toBeNull();
    expect(container.firstChild).toBeNull();
  });

  it("preserves full text for truncated chat rows via title attributes", async () => {
    const longTitle =
      "这是一个特别长的现实动作标题，用来验证聊天页异常协作条在被截断时仍然可以通过悬浮看到完整内容";
    const longSummary =
      "这是一个特别长的现实动作摘要，用来验证摘要行在宽度不足时不会继续撑破布局，并且仍然保留完整文本。";
    const longAction =
      "这是一个特别长的宿主动作说明，用来验证详情区与异常协作条都能在截断后保留完整文本提示。";
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

    fireEvent.click(screen.getByRole("button", { name: "查看协作记录" }));

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
