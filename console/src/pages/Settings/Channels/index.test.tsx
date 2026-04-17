// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiMock, messageMock } = vi.hoisted(() => ({
  apiMock: {
    listChannels: vi.fn(),
    listChannelTypes: vi.fn(),
    updateChannelConfig: vi.fn(),
    createWeixinILinkLoginQr: vi.fn(),
    getWeixinILinkLoginStatus: vi.fn(),
    rebindWeixinILinkLogin: vi.fn(),
  },
  messageMock: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("../../../api", () => ({
  default: apiMock,
}));

vi.mock("@/ui", async () => {
  const actual = await vi.importActual<typeof import("@/ui")>("@/ui");
  return {
    ...actual,
    message: messageMock,
  };
});

import ChannelsPage from "./index";

describe("ChannelsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiMock.listChannels.mockResolvedValue({
      console: {
        enabled: true,
        bot_prefix: "",
        isBuiltin: true,
      },
      weixin_ilink: {
        enabled: true,
        bot_prefix: "[BOT]",
        bot_token: "",
        bot_token_file: "~/.qwenpaw/weixin_bot_token",
        base_url: "",
        media_dir: "~/.qwenpaw/media",
        dm_policy: "open",
        group_policy: "open",
        group_reply_mode: "mention_or_prefix",
        group_allowlist: [],
        proactive_targets: [],
        isBuiltin: true,
      },
    });
    apiMock.listChannelTypes.mockResolvedValue(["console", "weixin_ilink"]);
    apiMock.getWeixinILinkLoginStatus.mockResolvedValue({
      login_status: "waiting_scan",
      polling_status: "stopped",
      token_source: "",
      last_qr_issued_at: "2026-04-17T18:00:00Z",
      last_update_id: null,
      last_receive_at: null,
      last_send_at: null,
      last_error: "",
      qrcode: "qr-initial",
      qrcode_img_content: "https://open.weixin.qq.com/qrcode/qr-initial",
      bot_token: "",
      base_url: "",
      ilink_bot_id: "",
      ilink_user_id: "",
    });
    apiMock.createWeixinILinkLoginQr.mockResolvedValue({
      login_status: "waiting_scan",
      polling_status: "stopped",
      token_source: "",
      last_qr_issued_at: "2026-04-17T18:01:00Z",
      last_update_id: null,
      last_receive_at: null,
      last_send_at: null,
      last_error: "",
      qrcode: "qr-new",
      qrcode_img_content: "https://open.weixin.qq.com/qrcode/qr-new",
      bot_token: "",
      base_url: "",
      ilink_bot_id: "",
      ilink_user_id: "",
    });
    apiMock.rebindWeixinILinkLogin.mockResolvedValue({
      login_status: "auth_expired",
      polling_status: "stopped",
      token_source: "",
      last_qr_issued_at: null,
      last_update_id: null,
      last_receive_at: null,
      last_send_at: null,
      last_error: "rebind_requested",
      qrcode: "",
      qrcode_img_content: "",
      bot_token: "",
      base_url: "",
      ilink_bot_id: "",
      ilink_user_id: "",
    });
  });

  it("loads weixin ilink runtime status when opening the card and can request a fresh login qr", async () => {
    render(<ChannelsPage />);

    await waitFor(() => {
      expect(screen.getByText("微信个人（iLink）")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("微信个人（iLink）"));

    await waitFor(() => {
      expect(apiMock.getWeixinILinkLoginStatus).toHaveBeenCalledTimes(1);
      expect(screen.getByText("当前二维码：qr-initial")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "获取登录二维码" }));

    await waitFor(() => {
      expect(apiMock.createWeixinILinkLoginQr).toHaveBeenCalledTimes(1);
      expect(screen.getByText("当前二维码：qr-new")).toBeInTheDocument();
    });
  });
});
