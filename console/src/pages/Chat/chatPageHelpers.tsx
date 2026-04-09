import { resolveRuntimeChatEntryPath } from "../../utils/runtimeChat";

const CHAT_RUNTIME_TEXT = {
  modelNotConfigured: "未配置大模型",
  unknownAgent: "未知智能体",
} as const;

function countPendingChatApprovals(
  governanceStatus:
    | {
        pending_decisions?: number | null;
        proposed_patches?: number | null;
        pending_patches?: number | null;
      }
    | null
    | undefined,
): number {
  if (!governanceStatus) {
    return 0;
  }
  return (
    (governanceStatus.pending_decisions ?? 0) +
    (governanceStatus.proposed_patches ?? 0)
  );
}

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
  buddySessionId,
  requestedBuddyProfileId,
  activeThreadId,
}: {
  requestedThreadId: string | null;
  buddySessionId: string | null;
  requestedBuddyProfileId: string | null;
  activeThreadId: string | null | undefined;
}): string | null {
  if (requestedThreadId || buddySessionId || requestedBuddyProfileId) {
    return null;
  }
  const recoveryTarget = resolveRuntimeChatEntryPath(activeThreadId);
  return recoveryTarget === "/chat" ? null : recoveryTarget;
}

function shouldAutoRefreshRuntimeThread({
  threadId,
  threadMeta,
  threadBootstrapError,
}: {
  threadId: string | null;
  threadMeta: Record<string, unknown>;
  threadBootstrapError?: string | null;
}): boolean {
  if (typeof threadBootstrapError === "string" && threadBootstrapError.trim()) {
    return false;
  }
  if (!isFormalRuntimeThreadId(threadId)) {
    return false;
  }
  const sessionKind =
    typeof threadMeta.session_kind === "string" ? threadMeta.session_kind.trim() : "";
  return !sessionKind || sessionKind === "industry-control-thread";
}

export {
  CHAT_RUNTIME_TEXT,
  countPendingChatApprovals,
  normalizeThreadId,
  normalizeThreadMeta,
  isFormalRuntimeThreadId,
  parseIndustryThreadId,
  resolveChatRouteRecoveryTarget,
  shouldAutoRefreshRuntimeThread,
};
