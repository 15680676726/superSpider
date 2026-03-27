// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";

import {
  buildRuntimeChatRequest,
  parseRuntimeResponseChunk,
} from "./runtimeTransport";

describe("runtimeTransport", () => {
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
});
