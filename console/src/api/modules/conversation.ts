import { request } from "../request";
import type { RuntimeConversation } from "../types";

export const conversationApi = {
  getRuntimeConversation: (conversationId: string) =>
    request<RuntimeConversation>(
      `/runtime-center/conversations/${encodeURIComponent(conversationId)}`,
    ),
};
