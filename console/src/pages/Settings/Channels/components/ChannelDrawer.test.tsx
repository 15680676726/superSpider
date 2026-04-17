// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { Form } from "@/ui";
import { describe, expect, it, vi } from "vitest";
import { ChannelDrawer } from "./ChannelDrawer";

vi.mock("@ant-design/icons", () => ({
  LinkOutlined: () => <span data-testid="link-outlined" />,
}));

function DrawerHarness() {
  const [form] = Form.useForm<Record<string, unknown>>();

  return (
    <ChannelDrawer
      open
      activeKey="weixin_ilink"
      activeLabel="微信个人（iLink）"
      form={form}
      saving={false}
      initialValues={{
        enabled: true,
        bot_prefix: "[BOT]",
        bot_token: "",
        bot_token_file: "~/.qwenpaw/weixin_bot_token",
        base_url: "",
        media_dir: "~/.qwenpaw/media",
        dm_policy: "open",
        group_policy: "open",
        group_reply_mode: "mention_or_prefix",
        group_allowlist: ["group-alpha"],
        proactive_targets: ["dm:user-alpha", "group:group-alpha"],
      }}
      isBuiltin
      onClose={() => undefined}
      onSubmit={() => undefined}
    />
  );
}

describe("ChannelDrawer", () => {
  it("renders weixin ilink login actions and dedicated fields inside the drawer", () => {
    render(<DrawerHarness />);

    expect(screen.getByText("微信个人（iLink） 设置")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "获取登录二维码" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "检查登录状态" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新扫码授权" })).toBeInTheDocument();
    expect(screen.getByText("Bot Token 文件")).toBeInTheDocument();
    expect(screen.getByText("群回复模式")).toBeInTheDocument();
    expect(screen.getByText("群白名单")).toBeInTheDocument();
    expect(screen.getByText("主动汇报目标")).toBeInTheDocument();
  });
});
