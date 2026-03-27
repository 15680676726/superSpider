import { describe, expect, it } from "vitest";
import { resolveChatNoticeVariant } from "./noticeState";

describe("resolveChatNoticeVariant", () => {
  it("shows loading while thread bootstrap is pending", () => {
    expect(
      resolveChatNoticeVariant({
        threadBootstrapPending: true,
        requestedThreadLooksBound: true,
        autoBindingPending: false,
        shouldRenderChatUi: false,
      }),
    ).toBe("loading");
  });

  it("shows binding notice while a bound thread is still resolving", () => {
    expect(
      resolveChatNoticeVariant({
        threadBootstrapPending: false,
        requestedThreadLooksBound: true,
        autoBindingPending: false,
        shouldRenderChatUi: false,
      }),
    ).toBe("binding");
  });

  it("shows blocked notice when chat is not renderable and not in binding flow", () => {
    expect(
      resolveChatNoticeVariant({
        threadBootstrapPending: false,
        requestedThreadLooksBound: false,
        autoBindingPending: false,
        shouldRenderChatUi: false,
      }),
    ).toBe("blocked");
  });

  it("does not render a notice after chat UI is ready", () => {
    expect(
      resolveChatNoticeVariant({
        threadBootstrapPending: false,
        requestedThreadLooksBound: true,
        autoBindingPending: false,
        shouldRenderChatUi: true,
      }),
    ).toBeNull();
  });
});
