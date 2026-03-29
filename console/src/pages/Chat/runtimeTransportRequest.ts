import type { MediaSourceSpec } from "../../api/modules/media";
import { normalizeThreadId } from "./chatPageHelpers";
import { normalizeRuntimeMediaSources } from "./runtimeTransportMedia";

export interface RuntimeWindowContext {
  currentChannel?: string;
  currentThreadId?: string;
  currentUserId?: string;
}

export interface RuntimeWebUiMessage {
  session?: {
    session_id?: string;
    user_id?: string;
    channel?: string;
  };
  [key: string]: unknown;
}

export interface RuntimeWebUiFetchData {
  input: RuntimeWebUiMessage[];
  biz_params?: Record<string, unknown>;
  signal?: AbortSignal;
}

export interface RuntimeSessionContext {
  currentThreadId: string | null;
  sessionId: string;
  userId: string;
  channel: string;
}

export interface RuntimeThreadContext {
  controlThreadId: string | null;
  workContextId: string | null;
  contextKey: string | null;
}

interface BuildRuntimeChatRequestArgs {
  data: RuntimeWebUiFetchData;
  runtimeWindow: RuntimeWindowContext;
  requestedThreadId: string | null;
  threadMeta: Record<string, unknown>;
  pendingMediaSources: MediaSourceSpec[];
  selectedMediaAnalysisIds: string[];
}

type QueuedHumanAssistSubmission = {
  threadId: string;
};

let queuedHumanAssistSubmission: QueuedHumanAssistSubmission | null = null;

export function queueHumanAssistSubmissionForNextMessage(threadId: string): void {
  const normalized = firstNonEmptyString(threadId);
  if (!normalized) {
    return;
  }
  queuedHumanAssistSubmission = {
    threadId: normalized,
  };
}

export function resetRuntimeTransportForTests(): void {
  queuedHumanAssistSubmission = null;
}

function consumeQueuedHumanAssistSubmission(threadId: string | null): string[] {
  if (!queuedHumanAssistSubmission) {
    return [];
  }
  if (!threadId || queuedHumanAssistSubmission.threadId !== threadId) {
    return [];
  }
  queuedHumanAssistSubmission = null;
  return ["submit_human_assist"];
}

export function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }
    const trimmed = value.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return null;
}

export function normalizeRuntimeStringList(values: unknown[]): string[] {
  const normalized = values
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
  return Array.from(new Set(normalized));
}

export function resolveRuntimeSessionContext({
  runtimeWindow,
  requestedThreadId,
  threadMeta,
  session,
}: {
  runtimeWindow: RuntimeWindowContext;
  requestedThreadId: string | null;
  threadMeta: Record<string, unknown>;
  session: RuntimeWebUiMessage["session"];
}): RuntimeSessionContext {
  const currentThreadId =
    normalizeThreadId(runtimeWindow.currentThreadId) ||
    requestedThreadId ||
    (typeof threadMeta.control_thread_id === "string" &&
    threadMeta.control_thread_id.trim()
      ? threadMeta.control_thread_id.trim()
      : null);
  return {
    currentThreadId,
    sessionId: currentThreadId || requestedThreadId || session?.session_id || "",
    userId: runtimeWindow.currentUserId || session?.user_id || "default",
    channel: runtimeWindow.currentChannel || session?.channel || "console",
  };
}

export function resolveRuntimeThreadContext({
  threadMeta,
  bizParams,
  sessionId,
}: {
  threadMeta: Record<string, unknown>;
  bizParams: Record<string, unknown>;
  sessionId: string;
}): RuntimeThreadContext {
  const controlThreadId = firstNonEmptyString(
    threadMeta.control_thread_id,
    typeof bizParams.control_thread_id === "string"
      ? bizParams.control_thread_id
      : null,
    sessionId.startsWith("industry-chat:") ? sessionId : null,
  );
  const workContextId = firstNonEmptyString(
    threadMeta.work_context_id,
    typeof bizParams.work_context_id === "string"
      ? bizParams.work_context_id
      : null,
  );
  const contextKey = firstNonEmptyString(
    threadMeta.context_key,
    typeof bizParams.context_key === "string" ? bizParams.context_key : null,
    controlThreadId ? `control-thread:${controlThreadId}` : null,
  );
  return {
    controlThreadId,
    workContextId,
    contextKey,
  };
}

export function buildRuntimeChatRequest({
  data,
  runtimeWindow,
  requestedThreadId,
  threadMeta,
  pendingMediaSources,
  selectedMediaAnalysisIds,
}: BuildRuntimeChatRequestArgs): Record<string, unknown> {
  const { input, biz_params } = data;
  const lastMessage = input[input.length - 1];
  const session = lastMessage?.session || {};
  const sessionContext = resolveRuntimeSessionContext({
    runtimeWindow,
    requestedThreadId,
    threadMeta,
    session,
  });
  const threadContext = resolveRuntimeThreadContext({
    threadMeta,
    bizParams:
      biz_params && typeof biz_params === "object"
        ? (biz_params as Record<string, unknown>)
        : {},
    sessionId: sessionContext.sessionId,
  });
  const requestedActions = normalizeRuntimeStringList([
    ...(Array.isArray(biz_params?.requested_actions)
      ? (biz_params.requested_actions as unknown[])
      : []),
    ...consumeQueuedHumanAssistSubmission(sessionContext.sessionId),
  ]);
  const mediaInputs = normalizeRuntimeMediaSources([
    ...(Array.isArray(biz_params?.media_inputs)
      ? (biz_params.media_inputs as unknown[])
      : []),
    ...pendingMediaSources,
  ]);
  const mediaAnalysisIds = normalizeRuntimeStringList([
    ...(Array.isArray(biz_params?.media_analysis_ids)
      ? (biz_params.media_analysis_ids as unknown[])
      : []),
    ...selectedMediaAnalysisIds,
  ]);

  return {
    input: input.slice(-1),
    session_id: sessionContext.sessionId,
    thread_id: sessionContext.currentThreadId || undefined,
    user_id: sessionContext.userId,
    channel: sessionContext.channel,
    stream: true,
    ...biz_params,
    interaction_mode: "auto",
    industry_instance_id:
      threadMeta.industry_instance_id || biz_params?.industry_instance_id,
    industry_label: threadMeta.industry_label || biz_params?.industry_label,
    industry_role_id: threadMeta.industry_role_id || biz_params?.industry_role_id,
    industry_role_name:
      threadMeta.industry_role_name || biz_params?.industry_role_name,
    entry_source: threadMeta.entry_source || biz_params?.entry_source || "chat",
    owner_scope: threadMeta.owner_scope || biz_params?.owner_scope,
    session_kind: threadMeta.session_kind || biz_params?.session_kind,
    agent_id: threadMeta.agent_id || biz_params?.agent_id,
    agent_name: threadMeta.agent_name || biz_params?.agent_name,
    control_thread_id: threadContext.controlThreadId || undefined,
    work_context_id: threadContext.workContextId || undefined,
    context_key: threadContext.contextKey || undefined,
    requested_actions: requestedActions.length > 0 ? requestedActions : undefined,
    media_analysis_ids: mediaAnalysisIds,
    media_inputs: mediaInputs,
  };
}
