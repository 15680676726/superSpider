// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetBuddyProfileBindingForTests } from "../runtime/buddyProfileBinding";

const { navigateMock, apiMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  apiMock: {
    getBuddyEntry: vi.fn(),
  },
}));

const runtimeChatMock = vi.hoisted(() => ({
  buildBuddyExecutionCarrierChatBinding: vi.fn(),
  openRuntimeChat: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../api", () => ({
  default: apiMock,
}));

vi.mock("../utils/runtimeChat", () => runtimeChatMock);

import EntryRedirect from "./entryRedirect";

type RuntimeWindow = Window & {
  currentThreadMeta?: Record<string, unknown>;
};

describe("EntryRedirect", () => {
  beforeEach(() => {
    resetBuddyProfileBindingForTests();
    (window as RuntimeWindow).currentThreadMeta = undefined;
    navigateMock.mockReset();
    apiMock.getBuddyEntry.mockReset();
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReset();
    runtimeChatMock.openRuntimeChat.mockReset();
  });

  it("asks the backend entry route before sending users without a saved buddy profile to onboarding", async () => {
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "start-onboarding",
      profile_id: null,
      session_id: null,
    });

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith(undefined);
      expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
        replace: true,
      });
    });
  });

  it("opens chat even when storage is empty if the backend resolves a singleton buddy", async () => {
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "chat-ready",
      profile_id: "profile-1",
      session_id: null,
      profile_display_name: "Alex",
      execution_carrier: {
        instance_id: "buddy:profile-1:domain-writing",
        label: "Writing carrier",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
        control_thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
      },
    });
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Nova",
      threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      userId: "buddy:profile-1",
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith(undefined);
      expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalled();
    });

    expect(window.localStorage.getItem("copaw.buddy_profile_id")).toBe("profile-1");
  });

  it("keeps unfinished buddy onboarding on the onboarding page", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-1");
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "resume-onboarding",
      profile_id: "profile-1",
      session_id: "session-1",
    });

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith("profile-1");
      expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
        replace: true,
      });
    });
  });

  it("falls back to the active thread buddy profile when storage is empty", async () => {
    (window as RuntimeWindow).currentThreadMeta = {
      buddy_profile_id: "profile-1",
    };
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "chat-ready",
      profile_id: "profile-1",
      session_id: null,
      profile_display_name: "Alex",
      execution_carrier: {
        instance_id: "buddy:profile-1:domain-writing",
        label: "Writing carrier",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
        control_thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
      },
    });
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Nova",
      threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      userId: "buddy:profile-1",
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith("profile-1");
    });
  });

  it("persists the thread buddy profile before returning to onboarding", async () => {
    (window as RuntimeWindow).currentThreadMeta = {
      buddy_profile_id: "profile-1",
    };
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "resume-onboarding",
      profile_id: "profile-1",
      session_id: "session-1",
    });

    render(<EntryRedirect />);

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith("profile-1");
      expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
        replace: true,
      });
    });

    expect(window.localStorage.getItem("copaw.buddy_profile_id")).toBe("profile-1");
  });

  it("opens chat directly when the buddy is already ready", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-1");
    apiMock.getBuddyEntry.mockResolvedValue({
      mode: "chat-ready",
      profile_id: "profile-1",
      session_id: null,
      profile_display_name: "Alex",
      execution_carrier: {
        instance_id: "buddy:profile-1:domain-writing",
        label: "Writing carrier",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
        control_thread_id:
          "industry-chat:buddy:profile-1:domain-writing:execution-core",
      },
    });
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Nova",
      threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
      userId: "buddy:profile-1",
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);

    render(<EntryRedirect />);

    expect(screen.getByText("正在为你打开伙伴主场…")).toBeInTheDocument();

    await waitFor(() => {
      expect(apiMock.getBuddyEntry).toHaveBeenCalledWith("profile-1");
      expect(runtimeChatMock.buildBuddyExecutionCarrierChatBinding).toHaveBeenCalledWith({
        sessionId: null,
        profileId: "profile-1",
        profileDisplayName: "Alex",
        executionCarrier: expect.objectContaining({
          instance_id: "buddy:profile-1:domain-writing",
        }),
        entrySource: "entry-redirect",
      });
      expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
        expect.objectContaining({
          threadId: "industry-chat:buddy:profile-1:domain-writing:execution-core",
        }),
        navigateMock,
        { shouldNavigate: expect.any(Function), replace: true },
      );
    });
  });
});
