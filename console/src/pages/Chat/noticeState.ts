export type ChatNoticeVariant = "loading" | "binding" | "blocked" | null;

type ResolveChatNoticeVariantArgs = {
  threadBootstrapPending: boolean;
  requestedThreadLooksBound: boolean;
  autoBindingPending: boolean;
  shouldRenderChatUi: boolean;
};

export function resolveChatNoticeVariant({
  threadBootstrapPending,
  requestedThreadLooksBound,
  autoBindingPending,
  shouldRenderChatUi,
}: ResolveChatNoticeVariantArgs): ChatNoticeVariant {
  if (threadBootstrapPending) {
    return "loading";
  }
  if ((requestedThreadLooksBound || autoBindingPending) && !shouldRenderChatUi) {
    return "binding";
  }
  if (!shouldRenderChatUi) {
    return "blocked";
  }
  return null;
}
