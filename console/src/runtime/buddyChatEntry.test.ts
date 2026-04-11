// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiMock, navigateMock } = vi.hoisted(() => ({
  apiMock: {
    getBuddySurface: vi.fn(),
  },
  navigateMock: vi.fn(),
}));

const runtimeChatMock = vi.hoisted(() => ({
  buildBuddyExecutionCarrierChatBinding: vi.fn(),
  openRuntimeChat: vi.fn(),
}));

const buddyFlowMock = vi.hoisted(() => ({
  resolveBuddyEntryDecision: vi.fn(),
}));

const buddyProfileBindingMock = vi.hoisted(() => ({
  writeBuddyProfileId: vi.fn(),
}));

vi.mock("../api", () => ({
  default: apiMock,
}));

vi.mock("../utils/runtimeChat", () => runtimeChatMock);

vi.mock("./buddyFlow", () => buddyFlowMock);

vi.mock("./buddyProfileBinding", () => buddyProfileBindingMock);

import { resumeBuddyChatFromProfile } from "./buddyChatEntry";

describe("resumeBuddyChatFromProfile", () => {
  beforeEach(() => {
    apiMock.getBuddySurface.mockReset();
    navigateMock.mockReset();
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReset();
    runtimeChatMock.openRuntimeChat.mockReset();
    buddyFlowMock.resolveBuddyEntryDecision.mockReset();
    buddyProfileBindingMock.writeBuddyProfileId.mockReset();
  });

  it("opens the buddy chat directly when the profile is ready", async () => {
    apiMock.getBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
      },
      onboarding: {
        session_id: "session-1",
      },
      execution_carrier: {
        instance_id: "carrier-1",
      },
    });
    buddyFlowMock.resolveBuddyEntryDecision.mockReturnValue({
      mode: "chat-ready",
    });
    runtimeChatMock.buildBuddyExecutionCarrierChatBinding.mockReturnValue({
      name: "Nova",
      threadId: "industry-chat:carrier-1:execution-core",
      userId: "buddy:profile-1",
    });
    runtimeChatMock.openRuntimeChat.mockResolvedValue(undefined);

    await resumeBuddyChatFromProfile({
      profileId: "profile-1",
      navigate: navigateMock,
      entrySource: "chat-page",
    });

    expect(apiMock.getBuddySurface).toHaveBeenCalledWith("profile-1");
    expect(buddyProfileBindingMock.writeBuddyProfileId).toHaveBeenCalledWith(
      "profile-1",
    );
    expect(
      runtimeChatMock.buildBuddyExecutionCarrierChatBinding,
    ).toHaveBeenCalledWith({
      sessionId: "session-1",
      profileId: "profile-1",
      profileDisplayName: "Alex",
      executionCarrier: {
        instance_id: "carrier-1",
      },
      entrySource: "chat-page",
    });
    expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledWith(
      {
        name: "Nova",
        threadId: "industry-chat:carrier-1:execution-core",
        userId: "buddy:profile-1",
      },
      navigateMock,
      { replace: true, shouldNavigate: undefined },
    );
    expect(navigateMock).not.toHaveBeenCalledWith("/", { replace: true });
    expect(navigateMock).not.toHaveBeenCalledWith("/buddy-onboarding", {
      replace: true,
    });
  });

  it("sends the user to onboarding when the profile is not chat-ready", async () => {
    apiMock.getBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-1",
        display_name: "Alex",
      },
      onboarding: {
        session_id: "session-1",
      },
      execution_carrier: null,
    });
    buddyFlowMock.resolveBuddyEntryDecision.mockReturnValue({
      mode: "onboarding",
    });

    await resumeBuddyChatFromProfile({
      profileId: "profile-1",
      navigate: navigateMock,
      entrySource: "chat-page",
    });

    expect(navigateMock).toHaveBeenCalledWith("/buddy-onboarding", {
      replace: true,
    });
    expect(runtimeChatMock.openRuntimeChat).not.toHaveBeenCalled();
  });
});
