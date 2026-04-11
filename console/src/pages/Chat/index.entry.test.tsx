// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routerMocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  location: {
    pathname: "/chat",
    search: "",
    key: "chat-entry",
    hash: "",
    state: null,
  },
}));

const sessionApiMock = vi.hoisted(() => ({
  getActiveThreadId: vi.fn(),
  setPreferredThreadId: vi.fn(),
  clearBoundThreadContext: vi.fn(),
  getSession: vi.fn(),
}));

const buddyProfileBindingMock = vi.hoisted(() => ({
  readBuddyProfileId: vi.fn(),
}));

const buddyChatEntryMock = vi.hoisted(() => ({
  resumeBuddyChatFromProfile: vi.fn(),
}));

const runtimeBindingHookMock = vi.hoisted(() => ({
  useRuntimeBinding: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => routerMocks.navigate,
    useLocation: () => routerMocks.location,
  };
});

vi.mock("./sessionApi", () => ({
  default: sessionApiMock,
}));

vi.mock("../../runtime/buddyProfileBinding", async () => {
  const actual = await vi.importActual<
    typeof import("../../runtime/buddyProfileBinding")
  >("../../runtime/buddyProfileBinding");
  return {
    ...actual,
    ...buddyProfileBindingMock,
  };
});

vi.mock("../../runtime/buddyChatEntry", () => buddyChatEntryMock);

vi.mock("./useRuntimeBinding", () => ({
  useRuntimeBinding: runtimeBindingHookMock.useRuntimeBinding,
}));

vi.mock("./useChatRuntimeState", () => ({
  useChatRuntimeState: vi.fn(() => ({
    hasBoundAgentContext: false,
    hasSuggestedTeams: false,
    options: {},
    runtimeCommitState: {
      lastReplyDoneAt: null,
      lastTerminalResponseAt: null,
    },
    runtimeIntentShell: null,
  })),
}));

vi.mock("./useChatMedia", () => ({
  useChatMedia: vi.fn(() => ({
    clearMediaError: vi.fn(),
    clearPendingMediaDraftsRef: { current: null },
    handleAddMediaLink: vi.fn(),
    handleMediaUploadChange: vi.fn(),
    mediaAnalyses: [],
    mediaBusy: false,
    mediaError: null,
    mediaLinkValue: "",
    mediaPendingItems: [],
    pendingMediaSourcesRef: { current: [] },
    refreshThreadMediaAnalysesRef: { current: null },
    removePendingMedia: vi.fn(),
    selectedMediaAnalysisIds: [],
    selectedMediaAnalysisIdsRef: { current: [] },
    setMediaLinkValue: vi.fn(),
    toggleMediaAnalysis: vi.fn(),
    uploadMediaInputRef: { current: null },
  })),
}));

vi.mock("./ChatAccessGate", () => ({
  ChatAccessGate: () => null,
}));

vi.mock("./ChatIntentShellCard", () => ({
  ChatIntentShellCard: () => null,
}));

vi.mock("./ChatComposerAdapter", () => ({
  ChatComposerAdapter: () => null,
}));

import ChatPage from "./index";

describe("ChatPage entry routing", () => {
  beforeEach(() => {
    routerMocks.navigate.mockReset();
    routerMocks.location.search = "";
    sessionApiMock.getActiveThreadId.mockReset();
    sessionApiMock.setPreferredThreadId.mockReset();
    sessionApiMock.clearBoundThreadContext.mockReset();
    sessionApiMock.getSession.mockReset();
    buddyProfileBindingMock.readBuddyProfileId.mockReset();
    buddyChatEntryMock.resumeBuddyChatFromProfile.mockReset();

    sessionApiMock.getActiveThreadId.mockReturnValue(null);
    buddyProfileBindingMock.readBuddyProfileId.mockReturnValue("profile-1");
    buddyChatEntryMock.resumeBuddyChatFromProfile.mockResolvedValue("opened");
    runtimeBindingHookMock.useRuntimeBinding.mockReturnValue({
      activeAgentId: null,
      activeChatThreadId: null,
      activeIndustryId: null,
      activeIndustryRoleId: null,
      requestedThreadLooksBound: false,
    });
  });

  it("opens buddy chat directly from /chat when a buddy profile already exists", async () => {
    render(<ChatPage />);

    await waitFor(() => {
      expect(
        buddyChatEntryMock.resumeBuddyChatFromProfile,
      ).toHaveBeenCalledWith({
        profileId: "profile-1",
        navigate: routerMocks.navigate,
        entrySource: "chat-page",
        shouldNavigate: expect.any(Function),
      });
    });

    expect(routerMocks.navigate).not.toHaveBeenCalledWith("/", {
      replace: true,
    });
  });

  it("still asks the buddy entry flow when /chat has no local profile id", async () => {
    buddyProfileBindingMock.readBuddyProfileId.mockReturnValue(null);

    render(<ChatPage />);

    await waitFor(() => {
      expect(
        buddyChatEntryMock.resumeBuddyChatFromProfile,
      ).toHaveBeenCalledWith({
        profileId: null,
        navigate: routerMocks.navigate,
        entrySource: "chat-page",
        shouldNavigate: expect.any(Function),
      });
    });
  });

  it("does not clear bound thread context on a temporary session bootstrap miss", async () => {
    routerMocks.location.search =
      "?threadId=industry-chat%3Aindustry-v1-acme%3Aexecution-core";
    buddyProfileBindingMock.readBuddyProfileId.mockReturnValue(null);
    sessionApiMock.getSession.mockRejectedValue(new Error("temporary miss"));
    runtimeBindingHookMock.useRuntimeBinding.mockReturnValue({
      activeAgentId: "copaw-agent-runner",
      activeChatThreadId: "industry-chat:industry-v1-acme:execution-core",
      activeIndustryId: "industry-v1-acme",
      activeIndustryRoleId: "execution-core",
      requestedThreadLooksBound: true,
    });

    render(<ChatPage />);

    await waitFor(() => {
      expect(sessionApiMock.getSession).toHaveBeenCalledWith(
        "industry-chat:industry-v1-acme:execution-core",
      );
    });
    expect(sessionApiMock.clearBoundThreadContext).not.toHaveBeenCalledWith(
      "industry-chat:industry-v1-acme:execution-core",
    );
  });
});
