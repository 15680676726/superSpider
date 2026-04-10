import { resolveRuntimeChatEntryPath } from "../../utils/runtimeChat";

const CHAT_RUNTIME_TEXT = {
  modelNotConfigured: "未配置大模型",
  unknownAgent: "未知智能体",
} as const;

function normalizeThreadId(threadId: string | null | undefined): string | null {
  if (!threadId) {
    return null;
  }
  const trimmed = threadId.trim();
  if (!trimmed || trimmed === "undefined" || trimmed === "null") {
    return null;
  }
  return trimmed;
}

function normalizeThreadMeta(meta: unknown): Record<string, unknown> {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
    return {};
  }
  return meta as Record<string, unknown>;
}

function isFormalRuntimeThreadId(threadId: string | null): boolean {
  return Boolean(threadId?.startsWith("industry-chat:"));
}

function parseIndustryThreadId(
  threadId: string | null,
): { instanceId: string; roleId: string } | null {
  if (!threadId || !threadId.startsWith("industry-chat:")) {
    return null;
  }
  const remainder = threadId.slice("industry-chat:".length);
  const separatorIndex = remainder.lastIndexOf(":");
  if (separatorIndex <= 0 || separatorIndex >= remainder.length - 1) {
    return null;
  }
  const instanceId = remainder.slice(0, separatorIndex).trim();
  const roleId = remainder.slice(separatorIndex + 1).trim();
  if (!instanceId || !roleId) {
    return null;
  }
  return { instanceId, roleId };
}

function resolveChatRouteRecoveryTarget({
  requestedThreadId,
  activeThreadId,
}: {
  requestedThreadId: string | null;
  activeThreadId: string | null | undefined;
}): string | null {
  if (requestedThreadId) {
    return null;
  }
  const recoveryTarget = resolveRuntimeChatEntryPath(activeThreadId);
  return recoveryTarget === "/chat" ? null : recoveryTarget;
}

function resolveChatThreadBootstrapState({
  requestedThreadId,
  activeThreadId,
  activeThreadMeta,
}: {
  requestedThreadId: string | null;
  activeThreadId: string | null | undefined;
  activeThreadMeta: unknown;
}): {
  effectiveThreadId: string | null;
  initialThreadMeta: Record<string, unknown>;
  initialThreadBootstrapPending: boolean;
  initialAutoBindingPending: boolean;
  recoveryTarget: string | null;
} {
  const normalizedRequestedThreadId = normalizeThreadId(requestedThreadId);
  const normalizedActiveThreadId = normalizeThreadId(activeThreadId);
  const recoveryTarget = resolveChatRouteRecoveryTarget({
    requestedThreadId: normalizedRequestedThreadId,
    activeThreadId: normalizedActiveThreadId,
  });

  if (normalizedRequestedThreadId) {
    return {
      effectiveThreadId: normalizedRequestedThreadId,
      initialThreadMeta:
        normalizedActiveThreadId === normalizedRequestedThreadId
          ? normalizeThreadMeta(activeThreadMeta)
          : {},
      initialThreadBootstrapPending: true,
      initialAutoBindingPending: false,
      recoveryTarget: null,
    };
  }

  if (recoveryTarget && normalizedActiveThreadId) {
    return {
      effectiveThreadId: normalizedActiveThreadId,
      initialThreadMeta: normalizeThreadMeta(activeThreadMeta),
      initialThreadBootstrapPending: false,
      initialAutoBindingPending: false,
      recoveryTarget,
    };
  }

  return {
    effectiveThreadId: null,
    initialThreadMeta: {},
    initialThreadBootstrapPending: false,
    initialAutoBindingPending: false,
    recoveryTarget: null,
  };
}

export {
  CHAT_RUNTIME_TEXT,
  normalizeThreadId,
  normalizeThreadMeta,
  isFormalRuntimeThreadId,
  parseIndustryThreadId,
  resolveChatThreadBootstrapState,
  resolveChatRouteRecoveryTarget,
};
