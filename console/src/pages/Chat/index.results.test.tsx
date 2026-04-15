// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routerMocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  location: {
    pathname: "/chat",
    search: "?threadId=industry-chat%3Aindustry-1%3Aexecution-core",
    key: "chat-results",
    hash: "",
    state: null,
  },
}));

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
  default: {
    getActiveThreadId: vi.fn(() => null),
    setPreferredThreadId: vi.fn(),
    clearBoundThreadContext: vi.fn(),
    getSession: vi.fn(() =>
      Promise.resolve({
        meta: {
          session_kind: "industry-control-thread",
          industry_instance_id: "industry-1",
          industry_role_id: "execution-core",
        },
      }),
    ),
  },
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
      currentReplyResult: {
        title: "已生成 1 个结果",
        summary: "已保存 1 个结果文件。",
        resultCount: 1,
        artifactRefs: ["artifact://tool-result-1"],
        resultItems: [
          {
            ref: "artifact://tool-result-1",
            kind: "file",
            label: "文件",
            summary: "执行结果文件",
          },
        ],
        updatedAt: 501,
        payload: {},
      },
      lastReplyDoneAt: 501,
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
  ChatComposerAdapter: () => <div>composer</div>,
}));

vi.mock("../../runtime/buddyProfileBinding", async () => {
  const actual = await vi.importActual<
    typeof import("../../runtime/buddyProfileBinding")
  >("../../runtime/buddyProfileBinding");
  return {
    ...actual,
    readBuddyProfileId: vi.fn(() => null),
  };
});

vi.mock("../../runtime/buddyChatEntry", () => ({
  resumeBuddyChatFromProfile: vi.fn(),
}));

import ChatPage from "./index";

describe("ChatPage result visibility", () => {
  beforeEach(() => {
    routerMocks.navigate.mockReset();
  });

  it("surfaces user-facing result hints without exposing raw artifact refs", () => {
    render(<ChatPage />);

    expect(screen.getByText("已生成 1 个结果")).toBeTruthy();
    expect(screen.getByText("已保存 1 个结果文件。")).toBeTruthy();
    expect(screen.getByText("文件")).toBeTruthy();
    expect(screen.queryByText("artifact://tool-result-1")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "查看结果" }));
    expect(routerMocks.navigate).toHaveBeenCalledWith("/runtime-center");
  });
});
