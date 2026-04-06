import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../api/errors";

vi.mock("../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../api")>(
    "../../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      getRuntimeConversation: vi.fn(),
    },
  };
});

import api from "../../../api";
import sessionApi from "./index";

const mockedGetRuntimeConversation = vi.mocked(api.getRuntimeConversation);
const runtimeWindow = window as Window & {
  currentThreadId?: string;
};
const sessionApiInternals = sessionApi as unknown as {
  threadCacheTimeout: number;
};
const DEFAULT_THREAD_CACHE_TIMEOUT = sessionApiInternals.threadCacheTimeout;

function buildConversation(threadId: string, messages: Array<Record<string, unknown>>) {
  return {
    id: threadId,
    name: threadId,
    session_id: threadId,
    user_id: "copaw-agent-runner",
    channel: "console",
    meta: {},
    messages,
  };
}

async function cleanupThread(threadId?: string): Promise<void> {
  if (threadId) {
    await sessionApi.removeSession({ id: threadId });
  }
  sessionApi.setPreferredThreadId(null);
  sessionApi.clearBoundThreadContext();
  sessionApiInternals.threadCacheTimeout = DEFAULT_THREAD_CACHE_TIMEOUT;
}

describe("sessionApi.openBoundThread", () => {
  afterEach(async () => {
    mockedGetRuntimeConversation.mockReset();
    await cleanupThread("industry-chat:industry-v1-acme:execution-core");
    await cleanupThread("chat:transient");
  });

  it("throws a clean guidance message when no bound thread exists", async () => {
    await expect(sessionApi.createSession({})).rejects.toThrow(
      "运行聊天必须先进入主脑协作入口或伙伴主场。",
    );
  });

  it("falls back to the bound main-brain control thread when the conversation detail is still 404", async () => {
    mockedGetRuntimeConversation.mockRejectedValue(
      new ApiError({
        status: 404,
        statusText: "Not Found",
        detail: "name",
      }),
    );

    const session = await sessionApi.openBoundThread({
      name: "Acme Pets - Spider Mesh 主脑",
      threadId: "industry-chat:industry-v1-acme:execution-core",
      userId: "copaw-agent-runner",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
        industry_instance_id: "industry-v1-acme",
        control_thread_id: "industry-chat:industry-v1-acme:execution-core",
      },
    });

    expect(session.id).toBe("industry-chat:industry-v1-acme:execution-core");
    expect(session.threadId).toBe("industry-chat:industry-v1-acme:execution-core");
    expect(session.userId).toBe("copaw-agent-runner");
    expect(session.meta["session_kind"]).toBe("industry-control-thread");
    expect(runtimeWindow.currentThreadId).toBe(
      "industry-chat:industry-v1-acme:execution-core",
    );
    expect(mockedGetRuntimeConversation).toHaveBeenCalledTimes(2);
  });

  it("does not swallow unrelated non-main-brain thread 404 errors", async () => {
    mockedGetRuntimeConversation.mockRejectedValue(
      new ApiError({
        status: 404,
        statusText: "Not Found",
        detail: "thread missing",
      }),
    );

    await expect(
      sessionApi.openBoundThread({
        name: "Transient",
        threadId: "chat:transient",
        userId: "operator",
        channel: "console",
      }),
    ).rejects.toThrow("[404] thread missing");
  });

  it("keeps the richer in-memory transcript when the backend detail lags behind after remount", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValue(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "hello" }],
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    await sessionApi.openBoundThread({
      name: "Acme Pets - Spider Mesh 主脑",
      threadId,
      userId: "copaw-agent-runner",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
      },
    });

    await sessionApi.updateSession({
      id: threadId,
      messages: [
        { id: "local-user-1", role: "user", cards: [] },
        { id: "local-assistant-1", role: "assistant", cards: [], msgStatus: "finished" },
      ] as never[],
    });

    sessionApiInternals.threadCacheTimeout = 0;

    const restored = await sessionApi.getSession(threadId);

    expect(restored.messages).toHaveLength(2);
    expect(mockedGetRuntimeConversation).toHaveBeenCalledTimes(2);
  });

  it("refreshes stale terminal transcripts from backend before returning the session", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "第一轮" }],
        },
        {
          id: "backend-assistant-1",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "旧结果" }],
          sequence_number: 1,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    await sessionApi.openBoundThread({
      name: "Acme Pets - Spider Mesh 主脑",
      threadId,
      userId: "copaw-agent-runner",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
      },
    });

    await sessionApi.updateSession({
      id: threadId,
      messages: [
        { id: "local-user-1", role: "user", cards: [] },
        { id: "local-assistant-1", role: "assistant", cards: [], msgStatus: "finished" },
      ] as never[],
    });

    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "第一轮" }],
        },
        {
          id: "backend-assistant-1",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "旧结果" }],
          sequence_number: 1,
        },
        {
          id: "backend-user-2",
          role: "user",
          content: [{ type: "text", text: "第二轮" }],
        },
        {
          id: "backend-assistant-2",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "新结果" }],
          sequence_number: 2,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    sessionApiInternals.threadCacheTimeout = 0;

    const restored = await sessionApi.getSession(threadId);

    expect(restored.messages).toHaveLength(4);
    expect(restored.messages[3]?.msgStatus).toBe("finished");
  });

  it("refreshes stale sessions before returning the session list", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "第一轮" }],
        },
        {
          id: "backend-assistant-1",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "旧结果" }],
          sequence_number: 1,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    await sessionApi.openBoundThread({
      name: "Acme Pets - Spider Mesh 主脑",
      threadId,
      userId: "copaw-agent-runner",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
      },
    });

    await sessionApi.updateSession({
      id: threadId,
      messages: [
        { id: "local-user-1", role: "user", cards: [] },
        { id: "local-assistant-1", role: "assistant", cards: [], msgStatus: "finished" },
      ] as never[],
    });

    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "第一轮" }],
        },
        {
          id: "backend-assistant-1",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "旧结果" }],
          sequence_number: 1,
        },
        {
          id: "backend-user-2",
          role: "user",
          content: [{ type: "text", text: "第二轮" }],
        },
        {
          id: "backend-assistant-2",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "新结果" }],
          sequence_number: 2,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    sessionApiInternals.threadCacheTimeout = 0;

    const sessions = await sessionApi.getSessionList();
    const refreshed = sessions.find((item) => item.id === threadId);

    expect(refreshed?.messages).toHaveLength(4);
  });

  it("prefers backend terminal transcript over a longer local generating transcript", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "先开始" }],
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    await sessionApi.openBoundThread({
      name: "Acme Pets - Spider Mesh 主脑",
      threadId,
      userId: "copaw-agent-runner",
      channel: "console",
      meta: {
        session_kind: "industry-control-thread",
      },
    });

    await sessionApi.updateSession({
      id: threadId,
      messages: [
        { id: "local-user-1", role: "user", cards: [] },
        { id: "local-assistant-1", role: "assistant", cards: [], msgStatus: "generating" },
        { id: "local-assistant-2", role: "assistant", cards: [], msgStatus: "generating" },
      ] as never[],
    });

    mockedGetRuntimeConversation.mockResolvedValueOnce(
      buildConversation(threadId, [
        {
          id: "backend-user-1",
          role: "user",
          content: [{ type: "text", text: "先开始" }],
        },
        {
          id: "backend-assistant-1",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "已经结束" }],
          sequence_number: 1,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    sessionApiInternals.threadCacheTimeout = 0;

    const restored = await sessionApi.getSession(threadId);

    expect(restored.messages).toHaveLength(2);
    expect(restored.messages[1]?.msgStatus).toBe("finished");
  });

  it("prefers the terminal completed status over earlier in-progress chunks", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValue(
      buildConversation(threadId, [
        {
          id: "user-1",
          role: "user",
          content: [{ type: "text", text: "继续" }],
        },
        {
          id: "assistant-1",
          role: "assistant",
          type: "message",
          status: "in_progress",
          content: [{ type: "text", text: "正在处理" }],
          sequence_number: 1,
        },
        {
          id: "assistant-1-final",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "已经完成" }],
          sequence_number: 2,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    const session = await sessionApi.getSession(threadId);

    expect(session.messages).toHaveLength(2);
    expect(session.messages[1]?.msgStatus).toBe("finished");
  });

  it("marks persisted user messages as completed request cards", async () => {
    const threadId = "industry-chat:industry-v1-acme:execution-core";
    mockedGetRuntimeConversation.mockResolvedValue(
      buildConversation(threadId, [
        {
          id: "user-1",
          role: "user",
          content: [{ type: "text", text: "已经发出去的消息" }],
        },
        {
          id: "assistant-1-final",
          role: "assistant",
          type: "message",
          status: "completed",
          content: [{ type: "text", text: "收到" }],
          sequence_number: 1,
        },
      ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
    );

    const session = await sessionApi.getSession(threadId);
    const firstCard = session.messages[0]?.cards?.[0] as
      | {
          data?: {
            input?: Array<{
              content?: Array<{ status?: string }>;
            }>;
          };
        }
      | undefined;

    expect(firstCard?.data?.input?.[0]?.content?.[0]?.status).toBe("completed");
  });
});
