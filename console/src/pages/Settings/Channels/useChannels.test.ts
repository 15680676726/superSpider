// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../api")>(
    "../../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      listChannels: vi.fn(),
      listChannelTypes: vi.fn(),
    },
  };
});

import api from "../../../api";
import { useChannels } from "./useChannels";

const mockedListChannels = vi.mocked(api.listChannels);
const mockedListChannelTypes = vi.mocked(api.listChannelTypes);

describe("useChannels", () => {
  afterEach(() => {
    mockedListChannels.mockReset();
    mockedListChannelTypes.mockReset();
  });

  it("keeps weixin_ilink in the builtin order and exposes its builtin truth", async () => {
    mockedListChannels.mockResolvedValue({
      custom_bridge: {
        enabled: false,
        bot_prefix: "",
        isBuiltin: false,
      },
      weixin_ilink: {
        enabled: true,
        bot_prefix: "[BOT]",
        bot_token_file: "~/.qwenpaw/weixin_bot_token",
        isBuiltin: true,
      },
      console: {
        enabled: false,
        bot_prefix: "",
        isBuiltin: true,
      },
    } as never);
    mockedListChannelTypes.mockResolvedValue([
      "custom_bridge",
      "weixin_ilink",
      "console",
    ] as never);

    const { result } = renderHook(() => useChannels());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.orderedKeys).toEqual([
      "console",
      "weixin_ilink",
      "custom_bridge",
    ]);
    expect(result.current.isBuiltin("weixin_ilink")).toBe(true);
    expect(result.current.channels.weixin_ilink).toMatchObject({
      enabled: true,
      bot_token_file: "~/.qwenpaw/weixin_bot_token",
      isBuiltin: true,
    });
  });
});
