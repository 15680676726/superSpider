import { request } from "../request";
import type { RuntimeConversation } from "../types";

export const conversationApi = {
  getRuntimeConversation: (
    conversationId: string,
    options?: {
      optionalMeta?: Array<"main_brain_commit" | "human_assist_task">;
    },
  ) => {
    const params = new URLSearchParams();
    if (options?.optionalMeta?.length) {
      params.set("optional_meta", options.optionalMeta.join(","));
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return request<RuntimeConversation>(
      `/runtime-center/conversations/${encodeURIComponent(conversationId)}${suffix}`,
    );
  },
};
