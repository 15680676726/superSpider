// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const runtimeEvent = vi.hoisted(() => ({
  handler: null as ((event: { event_name: string }) => void) | null,
}));

const routerMocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  location: {
    pathname: "/chat",
    search: "?threadId=industry-chat%3Aindustry-1%3Aexecution-core",
    key: "chat-route",
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

const composerSpy = vi.hoisted(() => ({
  renderKeys: [] as string[],
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

vi.mock("../../runtime/eventBus", () => ({
  subscribe: vi.fn(
    (_pattern: string, handler: (event: { event_name: string }) => void) => {
      runtimeEvent.handler = handler;
      return () => {
        runtimeEvent.handler = null;
      };
    },
  ),
}));

vi.mock("./sessionApi", () => ({
  default: sessionApiMock,
}));

vi.mock("./useRuntimeBinding", () => ({
  useRuntimeBinding: vi.fn(() => ({
    activeAgentId: null,
    activeChatThreadId: "industry-chat:industry-1:execution-core",
    activeIndustryId: "industry-1",
    activeIndustryRoleId: "execution-core",
    requestedThreadLooksBound: true,
  })),
}));

vi.mock("./useChatRuntimeState", () => ({
  useChatRuntimeState: vi.fn(() => ({
    hasBoundAgentContext: true,
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
  ChatComposerAdapter: ({ chatUiKey }: { chatUiKey: string }) => {
    composerSpy.renderKeys.push(chatUiKey);
    return <div data-testid="composer-key">{chatUiKey}</div>;
  },
}));

import ChatPage from "./index";

type RuntimeWindow = Window & {
  currentThreadId?: string;
  currentThreadMeta?: Record<string, unknown>;
};

describe("ChatPage background refresh", () => {
  beforeEach(() => {
    vi.useRealTimers();
    runtimeEvent.handler = null;
    composerSpy.renderKeys = [];
    routerMocks.navigate.mockReset();
    sessionApiMock.getActiveThreadId.mockReset();
    sessionApiMock.setPreferredThreadId.mockReset();
    sessionApiMock.clearBoundThreadContext.mockReset();
    sessionApiMock.getSession.mockReset();
    sessionApiMock.getActiveThreadId.mockReturnValue(null);
    sessionApiMock.getSession.mockResolvedValue({
      meta: {
        session_kind: "industry-control-thread",
        industry_instance_id: "industry-1",
        industry_role_id: "execution-core",
      },
    });
    (window as RuntimeWindow).currentThreadId = "";
    (window as RuntimeWindow).currentThreadMeta = {};
  });

  it("keeps the composer key stable during background thread refreshes", async () => {
    render(<ChatPage />);

    expect(screen.getByTestId("composer-key")).toHaveTextContent(
      "industry-chat:industry-1:execution-core",
    );

    await act(async () => {
      runtimeEvent.handler?.({ event_name: "assignment.updated" });
      await new Promise((resolve) => window.setTimeout(resolve, 450));
    });

    expect(screen.getByTestId("composer-key")).toHaveTextContent(
      "industry-chat:industry-1:execution-core",
    );
    expect(new Set(composerSpy.renderKeys)).toEqual(
      new Set(["industry-chat:industry-1:execution-core"]),
    );
  });
});
