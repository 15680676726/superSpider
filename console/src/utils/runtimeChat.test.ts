// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

const { openBoundThreadMock } = vi.hoisted(() => ({
  openBoundThreadMock: vi.fn(),
}));

vi.mock("../pages/Chat/sessionApi", () => ({
  default: {
    openBoundThread: openBoundThreadMock,
  },
}));

import { openRuntimeChat } from "./runtimeChat";

describe("openRuntimeChat", () => {
  beforeEach(() => {
    openBoundThreadMock.mockReset();
    openBoundThreadMock.mockResolvedValue({
      id: "industry-chat:industry-1:execution-core",
    });
  });

  it("replaces browser history when the caller requests a redirect-style open", async () => {
    const navigate = vi.fn();

    await openRuntimeChat(
      {
        name: "执行中枢",
        threadId: "industry-chat:industry-1:execution-core",
        userId: "buddy:profile-1",
      },
      navigate,
      { replace: true },
    );

    expect(navigate).toHaveBeenCalledWith(
      "/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core",
      { replace: true },
    );
  });
});
