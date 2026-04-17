import { request } from "../request";
import type {
  ChannelConfig,
  SingleChannelConfig,
  WeixinILinkLoginRuntimeState,
} from "../types";

export const channelApi = {
  listChannelTypes: () => request<string[]>("/config/channels/types"),

  listChannels: () => request<ChannelConfig>("/config/channels"),

  updateChannels: (body: ChannelConfig) =>
    request<ChannelConfig>("/config/channels", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getChannelConfig: (channelName: string) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
    ),

  updateChannelConfig: (channelName: string, body: SingleChannelConfig) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),

  createWeixinILinkLoginQr: () =>
    request<WeixinILinkLoginRuntimeState>("/config/channels/weixin_ilink/login/qr", {
      method: "POST",
    }),

  getWeixinILinkLoginStatus: () =>
    request<WeixinILinkLoginRuntimeState>(
      "/config/channels/weixin_ilink/login/status",
    ),

  rebindWeixinILinkLogin: () =>
    request<WeixinILinkLoginRuntimeState>(
      "/config/channels/weixin_ilink/login/rebind",
      {
        method: "POST",
      },
    ),
};
