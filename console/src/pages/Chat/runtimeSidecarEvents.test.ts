import { describe, expect, it } from "vitest";

import {
  createInitialRuntimeSidecarState,
  hydrateRuntimeSidecarState,
  parseRuntimeSidecarEvent,
  reduceRuntimeSidecarEvent,
} from "./runtimeSidecarEvents";

const FAILED_TITLE = "\u63d0\u4ea4\u5931\u8d25";

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
    expect(failed.currentCommitStatus?.title).toContain(FAILED_TITLE);
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

  it("hydrates persisted main-brain commit meta through the reducer path", () => {
    const state = hydrateRuntimeSidecarState(
      {
        status: "confirm_required",
        control_thread_id: "industry-chat:industry-1:execution-core",
        session_id: "industry-chat:industry-1:execution-core",
        summary: "Approve the governed browser action.",
        payload: {
          decision_id: "decision-1",
        },
      },
      "industry-chat:industry-1:execution-core",
      400,
    );

    expect(state.controlThreadId).toBe("industry-chat:industry-1:execution-core");
    expect(state.currentCommitStatus?.kind).toBe("confirm_required");
    expect(state.currentCommitStatus?.summary).toBe(
      "Approve the governed browser action.",
    );
    expect(state.currentCommitStatus?.decisionIds).toEqual(["decision-1"]);
    expect(state.history).toHaveLength(1);
  });

  it("parses compatible sidecar envelopes without the canonical wrapper", () => {
    const parsed = parseRuntimeSidecarEvent(
      {
        sidecar_event: "committed",
        control_thread_id: "industry-chat:industry-1:execution-core",
        thread_id: "industry-chat:industry-1:execution-core",
        summary: "Backlog item committed.",
        payload: {
          record_id: "backlog-1",
        },
      },
      "industry-chat:industry-1:execution-core",
    );

    expect(parsed).toEqual({
      event: "committed",
      payload: {
        control_thread_id: "industry-chat:industry-1:execution-core",
        thread_id: "industry-chat:industry-1:execution-core",
        summary: "Backlog item committed.",
        record_id: "backlog-1",
      },
    });
  });

  it("captures intent shell payload from turn_reply_done sidecars", () => {
    const initialState = createInitialRuntimeSidecarState(
      "industry-chat:industry-1:execution-core",
    );

    const nextState = reduceRuntimeSidecarEvent(
      initialState,
      {
        event: "turn_reply_done",
        payload: {
          intent_shell: {
            mode_hint: "plan",
            label: "PLAN",
            summary: "Use a compact planning shell for this reply.",
            hint:
              "Goal, constraints, affected scope/files, checklist, acceptance criteria, verification steps.",
            trigger_source: "keyword",
            matched_text: "计划",
            confidence: 0.95,
          },
        },
      },
      500,
    );

    expect(nextState.lastReplyDoneAt).toBe(500);
    expect(nextState.currentIntentShell).toEqual({
      mode: "plan",
      label: "PLAN",
      summary: "Use a compact planning shell for this reply.",
      hint:
        "Goal, constraints, affected scope/files, checklist, acceptance criteria, verification steps.",
      triggerSource: "keyword",
      matchedText: "计划",
      confidence: 0.95,
      updatedAt: 500,
      payload: {
        mode_hint: "plan",
        label: "PLAN",
        summary: "Use a compact planning shell for this reply.",
        hint:
          "Goal, constraints, affected scope/files, checklist, acceptance criteria, verification steps.",
        trigger_source: "keyword",
        matched_text: "计划",
        confidence: 0.95,
      },
    });
  });
});
