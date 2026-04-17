export type ChannelKey = string;

export const CHANNEL_LABELS: Record<string, string> = {
  imessage: "iMessage",
  discord: "Discord",
  dingtalk: "DingTalk",
  feishu: "Feishu",
  qq: "QQ",
  telegram: "Telegram",
  weixin_ilink: "微信个人（iLink）",
  mqtt: "MQTT",
  console: "Console",
  voice: "Twilio",
};

export function getChannelLabel(key: string): string {
  if (CHANNEL_LABELS[key]) {
    return CHANNEL_LABELS[key];
  }
  return key
    .split(/[_-]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
