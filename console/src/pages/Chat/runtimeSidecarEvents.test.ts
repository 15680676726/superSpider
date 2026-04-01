import { describe, expect, it } from "vitest";

import {
  createInitialRuntimeSidecarState,
  parseRuntimeSidecarEvent,
  reduceRuntimeSidecarEvent,
} from "./runtimeSidecarEvents";

describe("runtimeSidecarEvents", () => {
  it("reduces commit_started and commit_failed into current-thread status cards", () => {
    const initialState = createInitialRuntimeSidecarState(
      "industry-chat:industry-1:execution-core",
    );

    const started = reduceRuntimeSidecarEvent(
      initialState,
      {
        event: "commit_started",
        payload: {
          summary: "Submitting the backlog update.",
        },
      },
      100,
    );

    expect(started.currentCommitStatus?.kind).toBe("started");

    const failed = reduceRuntimeSidecarEvent(
      started,
      {
        event: "commit_failed",
        payload: {
          reason: "payload_invalid",
          summary: "The action payload was incomplete.",
        },
      },
      101,
    );

    expect(failed.currentCommitStatus?.kind).toBe("failed");
    expect(failed.currentCommitStatus?.title).toContain("提交失败");
    expect(failed.history).toHaveLength(2);
  });

  it("maps governance_denied and environment_unavailable into same-window states", () => {
    const initialState = createInitialRuntimeSidecarState(
      "industry-chat:industry-1:execution-core",
    );

    const denied = reduceRuntimeSidecarEvent(
      initialState,
      {
        event: "commit_failed",
        payload: {
          reason: "governance_denied",
          summary: "Governance denied the action.",
        },
      },
      200,
    );

    expect(denied.currentCommitStatus?.kind).toBe("governance_denied");

    const unavailable = reduceRuntimeSidecarEvent(
      denied,
      {
        event: "commit_failed",
        payload: {
          reason: "environment_unavailable",
          summary: "The desktop session is unavailable.",
        },
      },
      201,
    );

    expect(unavailable.currentCommitStatus?.kind).toBe(
      "environment_unavailable",
    );
  });

  it("keeps commit sidecar state on the current control thread instead of task-chat payloads", () => {
    const initialState = createInitialRuntimeSidecarState(
      "industry-chat:industry-1:execution-core",
    );

    const nextState = reduceRuntimeSidecarEvent(
      initialState,
      {
        event: "confirm_required",
        payload: {
          decision_id: "decision-1",
          control_thread_id: "industry-chat:industry-1:execution-core",
          thread_id: "task-chat:query:session:console:ops-user:req-1",
          summary: "Approve the governed browser action.",
        },
      },
      300,
    );

    expect(nextState.controlThreadId).toBe(
      "industry-chat:industry-1:execution-core",
    );
    expect(nextState.currentCommitStatus?.controlThreadId).toBe(
      "industry-chat:industry-1:execution-core",
    );
    expect(nextState.currentCommitStatus?.decisionIds).toEqual(["decision-1"]);
  });

  it("parses runtime sidecar events from the existing response path payload", () => {
    const parsed = parseRuntimeSidecarEvent(
      {
        object: "runtime.sidecar",
        event: "committed",
        payload: {
          summary: "Backlog item committed.",
        },
      },
      "industry-chat:industry-1:execution-core",
    );

    expect(parsed).toEqual({
      event: "committed",
      payload: {
        control_thread_id: "industry-chat:industry-1:execution-core",
        summary: "Backlog item committed.",
      },
    });
  });
});
