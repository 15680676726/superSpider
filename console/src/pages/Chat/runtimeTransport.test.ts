// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { providerApi } from "../../api/modules/provider";

import {
  buildRuntimeChatRequest,
  createRuntimeTransport,
  normalizeRuntimeStringList,
  parseRuntimeResponseChunk,
  queueHumanAssistSubmissionForNextMessage,
  resolveRuntimeSessionContext,
  resolveRuntimeThreadContext,
  resetRuntimeTransportForTests,
} from "./runtimeTransport";

describe("runtimeTransport", () => {
  afterEach(() => {
    resetRuntimeTransportForTests();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("queues a one-shot human assist submit action for the matching thread", () => {
    queueHumanAssistSubmissionForNextMessage(
      "industry-chat:industry-1:execution-core",
    );

    const request = buildRuntimeChatRequest({
      data: {
        input: [
          {
            session: {
              session_id: "session-thread",
              user_id: "session-user",
              channel: "session-channel",
            },
          },
        ],
      },
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      threadMeta: {
        control_thread_id: "industry-chat:industry-1:execution-core",
      },
      pendingMediaSources: [],
      selectedMediaAnalysisIds: [],
    });

    expect(request.requested_actions).toEqual(["submit_human_assist"]);

    const nextRequest = buildRuntimeChatRequest({
      data: {
        input: [
          {
            session: {
              session_id: "session-thread",
              user_id: "session-user",
              channel: "session-channel",
            },
          },
        ],
      },
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      threadMeta: {
        control_thread_id: "industry-chat:industry-1:execution-core",
      },
      pendingMediaSources: [],
      selectedMediaAnalysisIds: [],
    });

    expect(nextRequest.requested_actions).toBeUndefined();
  });

  it("builds one canonical runtime chat request from session, thread meta, and media state", () => {
    const request = buildRuntimeChatRequest({
      data: {
        input: [
          {
            session: {
              session_id: "session-thread",
              user_id: "session-user",
              channel: "session-channel",
            },
          },
        ],
        biz_params: {
          media_inputs: [
            {
              source_kind: "url",
              url: "https://example.com/spec",
            },
          ],
          media_analysis_ids: ["analysis-1", "analysis-1"],
        },
      },
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      threadMeta: {
        industry_instance_id: "industry-1",
        industry_label: "零售行业",
        industry_role_id: "execution-core",
        industry_role_name: "执行中枢",
        control_thread_id: "industry-chat:industry-1:execution-core",
        owner_scope: "industry",
        session_kind: "industry-control-thread",
      },
      pendingMediaSources: [
        {
          source_kind: "upload",
          source_id: "artifact-1",
        },
        {
          source_kind: "upload",
          source_id: "artifact-1",
        },
      ],
      selectedMediaAnalysisIds: ["analysis-2"],
    });

    expect(request.thread_id).toBe("industry-chat:industry-1:execution-core");
    expect(request.session_id).toBe("industry-chat:industry-1:execution-core");
    expect(request.user_id).toBe("window-user");
    expect(request.channel).toBe("console");
    expect(request.control_thread_id).toBe(
      "industry-chat:industry-1:execution-core",
    );
    expect(request.context_key).toBe(
      "control-thread:industry-chat:industry-1:execution-core",
    );
    expect(request.media_analysis_ids).toEqual(["analysis-1", "analysis-2"]);
    expect(request.media_inputs).toEqual([
      {
        source_kind: "url",
        url: "https://example.com/spec",
      },
      {
        source_kind: "upload",
        source_id: "artifact-1",
      },
    ]);
    expect(request.industry_instance_id).toBe("industry-1");
    expect(request.industry_role_name).toBe("执行中枢");
    expect(request.interaction_mode).toBe("auto");
    expect(request.stream).toBe(true);
  });

  it("prefers bound thread agent identity over window user for canonical chat session keys", () => {
    const request = buildRuntimeChatRequest({
      data: {
        input: [
          {
            session: {
              session_id: "session-thread",
              user_id: "session-user",
              channel: "session-channel",
            },
          },
        ],
      },
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      threadMeta: {
        agent_id: "execution-core-agent",
        control_thread_id: "industry-chat:industry-1:execution-core",
      },
      pendingMediaSources: [],
      selectedMediaAnalysisIds: [],
    });

    expect(request.user_id).toBe("execution-core-agent");
  });

  it("normalizes runtime string arrays by trimming empties and deduping while keeping order", () => {
    expect(
      normalizeRuntimeStringList([
        " submit_human_assist ",
        "",
        null,
        "submit_human_assist",
        "create_report",
        "  ",
        "create_report",
      ]),
    ).toEqual(["submit_human_assist", "create_report"]);
  });

  it("resolves runtime session context from window/thread/session canonical precedence", () => {
    const context = resolveRuntimeSessionContext({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-2:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      threadMeta: {
        control_thread_id: "industry-chat:industry-2:execution-core",
      },
      session: {
        session_id: "session-thread",
        user_id: "session-user",
        channel: "session-channel",
      },
    });

    expect(context.currentThreadId).toBe("industry-chat:industry-2:execution-core");
    expect(context.sessionId).toBe("industry-chat:industry-2:execution-core");
    expect(context.userId).toBe("window-user");
    expect(context.channel).toBe("console");
  });

  it("resolves runtime thread context fields with control-thread fallback context key", () => {
    const context = resolveRuntimeThreadContext({
      threadMeta: {},
      bizParams: {},
      sessionId: "industry-chat:industry-3:execution-core",
    });

    expect(context.controlThreadId).toBe("industry-chat:industry-3:execution-core");
    expect(context.workContextId).toBeNull();
    expect(context.contextKey).toBe(
      "control-thread:industry-chat:industry-3:execution-core",
    );
  });

  it("sends queued human assist submissions through the real runtime transport and marks dirty on completion", async () => {
    queueHumanAssistSubmissionForNextMessage(
      "industry-chat:industry-1:execution-core",
    );
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            object: "response",
            status: "completed",
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );
    const dispatchHumanAssistDirty = vi.fn();
    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState: vi.fn(),
      dispatchHumanAssistDirty,
    });

    await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, fetchInit] = fetchSpy.mock.calls[0];
    const requestBody = JSON.parse(String(fetchInit?.body || "{}"));
    expect(requestBody.requested_actions).toEqual(["submit_human_assist"]);
    expect(requestBody.thread_id).toBe("industry-chat:industry-1:execution-core");
    transport.responseParser(
      JSON.stringify({
        object: "response",
        status: "completed",
      }),
    );
    expect(dispatchHumanAssistDirty).toHaveBeenCalledTimes(1);
  });

  it("keeps runtime transport payload minimal by dropping unrecognized heavy biz params and empty media arrays", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            object: "response",
            status: "completed",
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState: vi.fn(),
    });

    await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
      biz_params: {
        control_thread_id: "industry-chat:industry-1:execution-core",
        requested_actions: [],
        media_analysis_ids: [],
        media_inputs: [],
        heavy_debug_dump: {
          huge: "payload",
        },
      },
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, fetchInit] = fetchSpy.mock.calls[0];
    const requestBody = JSON.parse(String(fetchInit?.body || "{}"));
    expect(requestBody.heavy_debug_dump).toBeUndefined();
    expect(requestBody.media_analysis_ids).toBeUndefined();
    expect(requestBody.media_inputs).toBeUndefined();
    expect(requestBody.requested_actions).toBeUndefined();
  });

  it("checks active models before sending a runtime chat request", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    const getActiveModelsSpy = vi
      .spyOn(providerApi, "getActiveModels")
      .mockResolvedValue({
        resolved_llm: {
          provider_id: "test-provider",
          model: "test-model",
        },
      } as never);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            object: "response",
            status: "completed",
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    const setRuntimeWaitState = vi.fn();
    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState,
    });

    await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    expect(getActiveModelsSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(setRuntimeWaitState).toHaveBeenCalledWith(
      expect.objectContaining({
        activeLabel: "test-provider/test-model",
      }),
    );
  });

  it("always posts chat sends to the canonical runtime-center chat run endpoint", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            object: "response",
            status: "completed",
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: "https://override.example/api/runtime-center/chat/orchestrate",
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState: vi.fn(),
    });

    await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      "http://testserver/api/runtime-center/chat/run",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("does not surface a connection error when the runtime request is aborted by the client", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abortError);
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice,
      setRuntimeWaitState,
    });

    await expect(
      transport.fetch({
        input: [
          {
            session: {
              session_id: "session-thread",
              user_id: "session-user",
              channel: "session-channel",
            },
          },
        ],
        signal: AbortSignal.abort(),
      }),
    ).rejects.toThrow("The operation was aborted.");

    expect(setRuntimeWaitState).toHaveBeenCalledWith(null);
    expect(
      setRuntimeHealthNotice.mock.calls.every(([value]) => value == null),
    ).toBe(true);
  });

  it("cancels the matching in-flight runtime request", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();
    let aborted = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      const signal = init?.signal as AbortSignal;
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener(
          "abort",
          () => {
            aborted = true;
            reject(new DOMException("The operation was aborted.", "AbortError"));
          },
          { once: true },
        );
      });
    });

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice,
      setRuntimeWaitState,
    });

    const requestPromise = transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    transport.cancelSession("industry-chat:industry-1:execution-core");

    await expect(requestPromise).rejects.toThrow("The operation was aborted.");
    expect(aborted).toBe(true);
    expect(setRuntimeWaitState).toHaveBeenCalledWith(null);
    expect(
      setRuntimeHealthNotice.mock.calls.every(([value]) => value == null),
    ).toBe(true);
  });

  it("clears wait state and broadcasts governance refresh when a streamed response finishes", () => {
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();
    const dispatchGovernanceDirty = vi.fn();

    const parsed = parseRuntimeResponseChunk(
      JSON.stringify({
        object: "response",
        status: "completed",
      }),
      {
        setRuntimeHealthNotice,
        setRuntimeWaitState,
        dispatchGovernanceDirty,
      },
    );

    expect(parsed).toEqual({
      object: "response",
      status: "completed",
    });
    expect(setRuntimeWaitState).toHaveBeenCalledWith(null);
    expect(dispatchGovernanceDirty).toHaveBeenCalledTimes(1);
    expect(setRuntimeHealthNotice).not.toHaveBeenCalled();
  });

  it("treats rejected streamed responses as terminal and clears wait state", () => {
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();
    const dispatchGovernanceDirty = vi.fn();
    const dispatchHumanAssistDirty = vi.fn();

    const parsed = parseRuntimeResponseChunk(
      JSON.stringify({
        object: "response",
        status: "rejected",
      }),
      {
        setRuntimeHealthNotice,
        setRuntimeWaitState,
        dispatchGovernanceDirty,
        dispatchHumanAssistDirty,
      },
    );

    expect(parsed).toEqual({
      object: "response",
      status: "rejected",
    });
    expect(setRuntimeWaitState).toHaveBeenCalledWith(null);
    expect(dispatchGovernanceDirty).toHaveBeenCalledTimes(1);
    expect(dispatchHumanAssistDirty).toHaveBeenCalledTimes(1);
    expect(setRuntimeHealthNotice).not.toHaveBeenCalled();
  });

  it("cuts off chat-visible SSE at terminal response and consumes sidecar tail locally", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const dispatchGovernanceDirty = vi.fn();
    const dispatchHumanAssistDirty = vi.fn();
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        [
          'data: {"object":"message","type":"assistant","role":"assistant","status":"in_progress"}',
          "",
          'data: {"object":"response","status":"completed"}',
          "",
          'data: {"object":"runtime.sidecar","event":"turn_reply_done","payload":{"summary":"reply complete"}}',
          "",
          'data: {"object":"runtime.sidecar","event":"commit_started","payload":{"summary":"commit started"}}',
          "",
          'data: {"object":"runtime.sidecar","event":"committed","payload":{"summary":"committed ok"}}',
          "",
        ].join("\n"),
        {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
          },
        },
      ),
    );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      setShowModelPrompt: vi.fn(),
      dispatchGovernanceDirty,
      dispatchHumanAssistDirty,
    });

    const response = await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const bodyText = await response.text();
    expect(bodyText).toContain('"object":"response","status":"completed"');
    expect(bodyText).not.toContain("runtime.sidecar");
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(dispatchGovernanceDirty).toHaveBeenCalled();
    expect(dispatchHumanAssistDirty).toHaveBeenCalled();
  });

  it("surfaces commit_failed sidecar from the hidden tail as a runtime health notice", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const dispatchGovernanceDirty = vi.fn();
    const dispatchHumanAssistDirty = vi.fn();
    const setRuntimeHealthNotice = vi.fn();
    const setRuntimeWaitState = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        [
          'data: {"object":"response","status":"completed"}',
          "",
          'data: {"object":"runtime.sidecar","event":"commit_failed","payload":{"code":"MODEL_RUNTIME_FAILED","message":"db commit blew up"}}',
          "",
        ].join("\n"),
        {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
          },
        },
      ),
    );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      setShowModelPrompt: vi.fn(),
      dispatchGovernanceDirty,
      dispatchHumanAssistDirty,
    });

    const response = await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    const bodyText = await response.text();
    expect(bodyText).toContain('"object":"response","status":"completed"');
    expect(bodyText).not.toContain("commit_failed");
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(setRuntimeWaitState).toHaveBeenCalledWith(null);
    expect(setRuntimeHealthNotice).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "error",
        description: "db commit blew up",
      }),
    );
    expect(dispatchGovernanceDirty).toHaveBeenCalled();
    expect(dispatchHumanAssistDirty).toHaveBeenCalled();
  });

  it("maps hidden sidecar lifecycle events into visible runtime lifecycle state", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const setRuntimeLifecycleState = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        [
          'data: {"object":"response","status":"completed"}',
          "",
          'data: {"object":"runtime.sidecar","event":"turn_reply_done","payload":{"summary":"reply complete"}}',
          "",
          'data: {"object":"runtime.sidecar","event":"commit_started","payload":{"summary":"commit started"}}',
          "",
          'data: {"object":"runtime.sidecar","event":"confirm_required","payload":{"message":"Need operator approval"}}',
          "",
        ].join("\n"),
        {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
          },
        },
      ),
    );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState: vi.fn(),
      setRuntimeLifecycleState,
      setShowModelPrompt: vi.fn(),
      dispatchGovernanceDirty: vi.fn(),
      dispatchHumanAssistDirty: vi.fn(),
    });

    const response = await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    await response.text();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(setRuntimeLifecycleState).toHaveBeenCalledWith(
      expect.objectContaining({
        phase: "reply_done",
        tone: "busy",
      }),
    );
    expect(setRuntimeLifecycleState).toHaveBeenCalledWith(
      expect.objectContaining({
        phase: "commit_started",
        tone: "busy",
      }),
    );
    expect(setRuntimeLifecycleState).toHaveBeenCalledWith(
      expect.objectContaining({
        phase: "confirm_required",
        tone: "warning",
      }),
    );
  });

  it("keeps accepted reply_done and commit_failed as separate phases", () => {
    const setRuntimeLifecycleState = vi.fn();
    const setRuntimeWaitState = vi.fn();
    const setRuntimeHealthNotice = vi.fn();

    parseRuntimeResponseChunk(
      JSON.stringify({
        object: "runtime.sidecar",
        event: "accepted",
        payload: {
          status: "accepted",
          summary: "accepted boundary persisted",
        },
      }),
      {
        setRuntimeHealthNotice,
        setRuntimeLifecycleState,
        setRuntimeWaitState,
        dispatchGovernanceDirty: vi.fn(),
        dispatchHumanAssistDirty: vi.fn(),
      },
    );
    parseRuntimeResponseChunk(
      JSON.stringify({
        object: "runtime.sidecar",
        event: "turn_reply_done",
        payload: {
          summary: "reply complete",
        },
      }),
      {
        setRuntimeHealthNotice,
        setRuntimeLifecycleState,
        setRuntimeWaitState,
        dispatchGovernanceDirty: vi.fn(),
        dispatchHumanAssistDirty: vi.fn(),
      },
    );
    parseRuntimeResponseChunk(
      JSON.stringify({
        object: "runtime.sidecar",
        event: "commit_failed",
        payload: {
          code: "MODEL_RUNTIME_FAILED",
          message: "db commit blew up",
        },
      }),
      {
        setRuntimeHealthNotice,
        setRuntimeLifecycleState,
        setRuntimeWaitState,
        dispatchGovernanceDirty: vi.fn(),
        dispatchHumanAssistDirty: vi.fn(),
      },
    );

    expect(setRuntimeLifecycleState).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        phase: "accepted",
        tone: "busy",
      }),
    );
    expect(setRuntimeLifecycleState).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        phase: "reply_done",
        tone: "busy",
      }),
    );
    expect(setRuntimeLifecycleState).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        phase: "commit_failed",
        tone: "error",
      }),
    );
    expect(setRuntimeWaitState).toHaveBeenNthCalledWith(1, null);
    expect(setRuntimeWaitState).toHaveBeenNthCalledWith(2, null);
    expect(setRuntimeWaitState).toHaveBeenNthCalledWith(3, null);
    expect(setRuntimeHealthNotice).toHaveBeenLastCalledWith(
      expect.objectContaining({
        type: "error",
        description: "db commit blew up",
      }),
    );
  });

  it("forwards hidden sidecar tail events to the runtime sidecar callback", async () => {
    vi.stubGlobal("BASE_URL", "http://testserver");
    vi.spyOn(providerApi, "getActiveModels").mockResolvedValue({
      resolved_llm: {
        provider_id: "test-provider",
        model: "test-model",
      },
    } as never);
    const onRuntimeSidecarEvent = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        [
          'data: {"object":"response","status":"completed"}',
          "",
          'data: {"object":"runtime.sidecar","event":"turn_reply_done","payload":{"intent_shell":{"mode_hint":"plan"}}}',
          "",
          'data: {"object":"runtime.sidecar","event":"committed","payload":{"summary":"committed ok"}}',
          "",
        ].join("\n"),
        {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
          },
        },
      ),
    );

    const transport = createRuntimeTransport({
      runtimeWindow: {
        currentThreadId: "industry-chat:industry-1:execution-core",
        currentUserId: "window-user",
        currentChannel: "console",
      },
      requestedThreadId: "requested-thread",
      optionsBaseUrl: undefined,
      getThreadMeta: () => ({
        control_thread_id: "industry-chat:industry-1:execution-core",
      }),
      getPendingMediaSources: () => [],
      clearPendingMediaDrafts: vi.fn(),
      refreshThreadMediaAnalyses: vi.fn(),
      getSelectedMediaAnalysisIds: () => [],
      setRuntimeHealthNotice: vi.fn(),
      setRuntimeWaitState: vi.fn(),
      setShowModelPrompt: vi.fn(),
      onRuntimeSidecarEvent,
    });

    const response = await transport.fetch({
      input: [
        {
          session: {
            session_id: "session-thread",
            user_id: "session-user",
            channel: "session-channel",
          },
        },
      ],
    });

    await response.text();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(onRuntimeSidecarEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        object: "runtime.sidecar",
        event: "turn_reply_done",
      }),
    );
    expect(onRuntimeSidecarEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        object: "runtime.sidecar",
        event: "committed",
      }),
    );
  });

  it("surfaces compaction visibility details on reply_done lifecycle and sidecar callback", () => {
    const setRuntimeLifecycleState = vi.fn();
    const onRuntimeSidecarEvent = vi.fn();

    parseRuntimeResponseChunk(
      JSON.stringify({
        object: "runtime.sidecar",
        event: "turn_reply_done",
        payload: {
          summary: "reply complete",
          compaction_state: {
            mode: "microcompact",
            summary: "Compacted 2 oversized tool results.",
            spill_count: 1,
          },
          tool_result_budget: {
            message_budget: 2400,
            remaining_budget: 600,
          },
          tool_use_summary: {
            summary: "2 tool results compacted into artifact previews.",
            artifact_refs: ["artifact://tool-result-1"],
          },
        },
      }),
      {
        setRuntimeHealthNotice: vi.fn(),
        setRuntimeLifecycleState,
        setRuntimeWaitState: vi.fn(),
        dispatchGovernanceDirty: vi.fn(),
        dispatchHumanAssistDirty: vi.fn(),
        onRuntimeSidecarEvent,
      },
    );

    expect(onRuntimeSidecarEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        object: "runtime.sidecar",
        event: "turn_reply_done",
        payload: expect.objectContaining({
          compaction_state: expect.objectContaining({
            mode: "microcompact",
            spill_count: 1,
          }),
          tool_result_budget: expect.objectContaining({
            remaining_budget: 600,
          }),
          tool_use_summary: expect.objectContaining({
            summary: "2 tool results compacted into artifact previews.",
          }),
        }),
      }),
    );
    expect(setRuntimeLifecycleState).toHaveBeenCalledWith(
      expect.objectContaining({
        phase: "reply_done",
        description: expect.stringContaining(
          "2 tool results compacted into artifact previews.",
        ),
      }),
    );
  });
});
