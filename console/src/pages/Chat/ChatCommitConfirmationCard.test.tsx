// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatCommitConfirmationCard } from "./ChatCommitConfirmationCard";
import {
  createInitialRuntimeSidecarState,
  hydrateRuntimeSidecarState,
  reduceRuntimeSidecarEvent,
} from "./runtimeSidecarEvents";

const PENDING_TITLE = "\u5f85\u786e\u8ba4";
const COMMITTED_TITLE = "\u5df2\u63d0\u4ea4";
const DENIED_TITLE = "\u6cbb\u7406\u62d2\u7edd";

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

describe("ChatCommitConfirmationCard", () => {
  afterEach(() => {
    cleanup();
  });

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

    expect(screen.getByText(PENDING_TITLE)).toBeTruthy();
    expect(screen.getByText("Approve the governed browser action.")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: /\u6279\s*\u51c6/ }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /\u62d2\s*\u7edd/ }),
    );

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

    expect(screen.getByText(COMMITTED_TITLE)).toBeTruthy();
    expect(screen.getByText("Backlog item committed.")).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);

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

    expect(screen.getAllByText(DENIED_TITLE).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Governance denied the action.").length).toBeGreaterThan(0);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("renders a hydrated persisted confirm_required state after reload", () => {
    const state = hydrateRuntimeSidecarState(
      {
        status: "confirm_required",
        control_thread_id: "industry-chat:industry-1:execution-core",
        summary: "Approve the governed browser action.",
        payload: {
          decision_id: "decision-1",
        },
      },
      "industry-chat:industry-1:execution-core",
      300,
    );

    render(
      <ChatCommitConfirmationCard
        state={state}
        approveBusy={false}
        rejectBusy={false}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText(PENDING_TITLE)).toBeTruthy();
    expect(screen.getByText("Approve the governed browser action.")).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });
});
