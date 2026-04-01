// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatCommitConfirmationCard } from "./ChatCommitConfirmationCard";
import {
  createInitialRuntimeSidecarState,
  reduceRuntimeSidecarEvent,
} from "./runtimeSidecarEvents";

describe("ChatCommitConfirmationCard", () => {
  it("renders confirm_required in the same chat window and exposes approve/reject actions", () => {
    const state = reduceRuntimeSidecarEvent(
      createInitialRuntimeSidecarState(
        "industry-chat:industry-1:execution-core",
      ),
      {
        event: "confirm_required",
        payload: {
          decision_id: "decision-1",
          summary: "Approve the governed browser action.",
        },
      },
      100,
    );
    const onApprove = vi.fn();
    const onReject = vi.fn();

    render(
      <ChatCommitConfirmationCard
        state={state}
        approveBusy={false}
        rejectBusy={false}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByText("待确认")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /批\s*准/ }));
    fireEvent.click(screen.getByRole("button", { name: /拒\s*绝/ }));

    expect(onApprove).toHaveBeenCalledWith(["decision-1"]);
    expect(onReject).toHaveBeenCalledWith(["decision-1"]);
  });

  it("renders committed and failure states in-thread without confirmation buttons", () => {
    const committedState = reduceRuntimeSidecarEvent(
      createInitialRuntimeSidecarState(
        "industry-chat:industry-1:execution-core",
      ),
      {
        event: "committed",
        payload: {
          summary: "Backlog item committed.",
        },
      },
      200,
    );

    const { rerender } = render(
      <ChatCommitConfirmationCard
        state={committedState}
        approveBusy={false}
        rejectBusy={false}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("已提交")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /批\s*准/ })).toBeNull();

    const deniedState = reduceRuntimeSidecarEvent(
      committedState,
      {
        event: "commit_failed",
        payload: {
          reason: "governance_denied",
          summary: "Governance denied the action.",
        },
      },
      201,
    );

    rerender(
      <ChatCommitConfirmationCard
        state={deniedState}
        approveBusy={false}
        rejectBusy={false}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getAllByText("治理拒绝").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /批\s*准/ })).toBeNull();
  });
});
