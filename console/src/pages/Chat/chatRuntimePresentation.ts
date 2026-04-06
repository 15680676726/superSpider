export type ChatWritebackTarget =
  | "strategy"
  | "lane"
  | "backlog"
  | "immediate-goal";

export function resolveChatUiKey({
  requestedThreadId,
  activeIndustryId,
  activeIndustryRoleId,
  activeAgentId,
}: {
  requestedThreadId: string | null;
  activeIndustryId: string | null;
  activeIndustryRoleId: string | null;
  activeAgentId: string | null;
}): string {
  if (requestedThreadId) return requestedThreadId;
  if (activeIndustryId && activeIndustryRoleId) {
    return `industry:${activeIndustryId}:${activeIndustryRoleId}`;
  }
  if (activeAgentId) return `agent:${activeAgentId}`;
  return "chat-runtime";
}

export function resolveChatUiVisibility({
  requestedThreadId,
  activeWindowThreadId,
  requestedThreadLooksBound,
  threadBootstrapError,
  hasBoundAgentContext,
  effectiveThreadPending,
  allowUnboundBuddyShell,
  disableComposer,
}: {
  requestedThreadId: string | null;
  activeWindowThreadId: string | null;
  requestedThreadLooksBound: boolean;
  threadBootstrapError: string | null;
  hasBoundAgentContext: boolean;
  effectiveThreadPending: boolean;
  allowUnboundBuddyShell: boolean;
  disableComposer: boolean;
}): {
  hasDirectBoundThreadContext: boolean;
  shouldRenderChatUi: boolean;
  shouldRenderChatComposer: boolean;
} {
  const hasDirectBoundThreadContext =
    requestedThreadLooksBound && !threadBootstrapError;
  const canRenderBoundChatUi =
    Boolean(requestedThreadId || activeWindowThreadId) &&
    (hasBoundAgentContext || hasDirectBoundThreadContext) &&
    !effectiveThreadPending;
  const shouldRenderChatComposer = canRenderBoundChatUi && !disableComposer;
  return {
    hasDirectBoundThreadContext,
    shouldRenderChatComposer,
    shouldRenderChatUi: canRenderBoundChatUi || allowUnboundBuddyShell,
  };
}

function normalizeWritebackTarget(raw: string): ChatWritebackTarget | null {
  const normalized = raw.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "strategy") return "strategy";
  if (normalized === "lane") return "lane";
  if (normalized === "backlog" || normalized === "backlog-item")
    return "backlog";
  if (
    normalized === "immediate-goal" ||
    normalized === "immediate_goal" ||
    normalized === "immediate goal" ||
    normalized === "goal"
  ) {
    return "immediate-goal";
  }
  return null;
}

function normalizeWritebackTargetList(value: unknown): ChatWritebackTarget[] {
  if (!Array.isArray(value)) return [];
  const out: ChatWritebackTarget[] = [];
  for (const item of value) {
    if (typeof item !== "string") continue;
    const t = normalizeWritebackTarget(item);
    if (t && !out.includes(t)) out.push(t);
  }
  return out;
}

export function normalizeWritebackTargetsFromThreadMeta(
  threadMeta: Record<string, unknown>,
): ChatWritebackTarget[] {
  const fromTargets = normalizeWritebackTargetList(
    threadMeta.chat_writeback_targets,
  );
  const fromClasses = normalizeWritebackTargetList(
    threadMeta.chat_writeback_classes,
  );
  const fromSingle =
    typeof threadMeta.chat_writeback_target === "string"
      ? normalizeWritebackTarget(threadMeta.chat_writeback_target)
      : null;

  const merged: ChatWritebackTarget[] = [];
  for (const t of [
    ...fromTargets,
    ...fromClasses,
    ...(fromSingle ? [fromSingle] : []),
  ]) {
    if (!merged.includes(t)) merged.push(t);
  }
  if (merged.length > 0 && !merged.includes("strategy")) {
    merged.unshift("strategy");
  }
  return merged;
}

export function inferWritebackTargetsFromFocus({
  sessionKind,
  focusKind,
}: {
  sessionKind: string;
  focusKind: string;
}): ChatWritebackTarget[] {
  const normalizedKind = focusKind.trim().toLowerCase();
  const mapped =
    normalizedKind === "lane"
      ? "lane"
      : normalizedKind === "backlog" || normalizedKind === "backlog-item"
        ? "backlog"
        : normalizedKind === "goal"
          ? "immediate-goal"
          : normalizedKind === "strategy"
            ? "strategy"
            : null;
  if (mapped) {
    return mapped === "strategy" ? ["strategy"] : ["strategy", mapped];
  }
  return sessionKind === "industry-control-thread" ? ["strategy"] : [];
}

export function presentSessionKindLabel(sessionKind: string): string {
  const normalized = sessionKind.trim().toLowerCase();
  if (normalized === "industry-control-thread") return "control-thread";
  if (normalized === "industry-agent-chat") return "execution-thread";
  if (normalized === "agent-chat") return "agent-thread";
  return sessionKind;
}
