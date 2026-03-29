import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import type { ActiveModelsInfo } from "../../api/types/provider";
import type { MediaSourceSpec } from "../../api/modules/media";
import { CHAT_RUNTIME_TEXT, normalizeThreadId } from "./chatPageHelpers";
import { normalizeRuntimeMediaSources } from "./runtimeTransportMedia";
import {
  extractRuntimeHealthNotice,
  hasRuntimeStartedResponding,
  localizeRuntimeChunk,
  localizeRuntimeError,
  type RuntimeHealthNotice,
  type RuntimeWaitState,
} from "./runtimeDiagnostics";

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

interface CreateRuntimeTransportArgs {
  runtimeWindow: RuntimeWindowContext;
  requestedThreadId: string | null;
  optionsBaseUrl: string | undefined;
  getThreadMeta: () => Record<string, unknown>;
  getPendingMediaSources: () => MediaSourceSpec[];
  clearPendingMediaDrafts: () => void;
  refreshThreadMediaAnalyses: (threadId?: string | null) => Promise<void> | void;
  getSelectedMediaAnalysisIds: () => string[];
  setRuntimeHealthNotice: (notice: RuntimeHealthNotice | null) => void;
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void;
  setShowModelPrompt: (show: boolean) => void;
  dispatchGovernanceDirty?: () => void;
  dispatchHumanAssistDirty?: () => void;
}

type QueuedHumanAssistSubmission = {
  threadId: string;
};

interface ParseRuntimeResponseChunkArgs {
  setRuntimeHealthNotice: (notice: RuntimeHealthNotice | null) => void;
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void;
  dispatchGovernanceDirty?: () => void;
  dispatchHumanAssistDirty?: () => void;
}

const ACTIVE_MODELS_CACHE_TTL_MS = 30_000;
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

function resolveRuntimeChatUrl(baseUrl: string | undefined): string {
  const trimmed = typeof baseUrl === "string" ? baseUrl.trim() : "";
  if (!trimmed) {
    return getApiUrl("/runtime-center/chat/run");
  }
  return trimmed;
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

function beginRuntimeWait(
  activeModels: ActiveModelsInfo,
  setRuntimeHealthNotice: (notice: RuntimeHealthNotice | null) => void,
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void,
): void {
  const resolvedSlot = activeModels?.resolved_llm || activeModels?.active_llm;
  setRuntimeHealthNotice(null);
  setRuntimeWaitState({
    startedAt: Date.now(),
    activeLabel: resolvedSlot
      ? `${resolvedSlot.provider_id}/${resolvedSlot.model}`
      : CHAT_RUNTIME_TEXT.unknownAgent,
    fallbackCount:
      activeModels?.fallback_enabled === false
        ? 0
        : activeModels?.fallback_chain?.length || 0,
    resolutionReason: activeModels?.resolution_reason || null,
  });
}

function handleModelError(
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void,
  setShowModelPrompt: (show: boolean) => void,
): Response {
  setRuntimeWaitState(null);
  setShowModelPrompt(true);
  return new Response(
    JSON.stringify({
      error: CHAT_RUNTIME_TEXT.modelNotConfigured,
      message: CHAT_RUNTIME_TEXT.modelNotConfigured,
    }),
    {
      status: 400,
      headers: { "Content-Type": "application/json" },
    },
  );
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
    industry_instance_id: threadMeta.industry_instance_id || biz_params?.industry_instance_id,
    industry_label: threadMeta.industry_label || biz_params?.industry_label,
    industry_role_id: threadMeta.industry_role_id || biz_params?.industry_role_id,
    industry_role_name: threadMeta.industry_role_name || biz_params?.industry_role_name,
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

export function parseRuntimeResponseChunk(
  rawChunk: string,
  {
    setRuntimeHealthNotice,
    setRuntimeWaitState,
    dispatchGovernanceDirty,
    dispatchHumanAssistDirty,
  }: ParseRuntimeResponseChunkArgs,
): unknown {
  const parsed = localizeRuntimeChunk(JSON.parse(rawChunk));
  const healthNotice = extractRuntimeHealthNotice(parsed);
  if (healthNotice) {
    setRuntimeWaitState(null);
    setRuntimeHealthNotice(healthNotice);
    return parsed;
  }
  if (hasRuntimeStartedResponding(parsed)) {
    setRuntimeWaitState(null);
    setRuntimeHealthNotice(null);
    return parsed;
  }
  if (
    parsed &&
    typeof parsed === "object" &&
    (parsed as Record<string, unknown>).object === "response"
  ) {
    const status = String(
      (parsed as Record<string, unknown>).status || "",
    ).toLowerCase();
    if (["completed", "failed", "canceled"].includes(status)) {
      setRuntimeWaitState(null);
      dispatchGovernanceDirty?.();
      dispatchHumanAssistDirty?.();
    }
  }
  return parsed;
}

export function createRuntimeTransport({
  runtimeWindow,
  requestedThreadId,
  optionsBaseUrl,
  getThreadMeta,
  getPendingMediaSources,
  clearPendingMediaDrafts,
  refreshThreadMediaAnalyses,
  getSelectedMediaAnalysisIds,
  setRuntimeHealthNotice,
  setRuntimeWaitState,
  setShowModelPrompt,
  dispatchGovernanceDirty,
  dispatchHumanAssistDirty,
}: CreateRuntimeTransportArgs): {
  fetch: (data: RuntimeWebUiFetchData) => Promise<Response>;
  responseParser: (rawChunk: string) => unknown;
} {
  const activeModelsCache = {
    fetchedAt: 0,
    value: null as ActiveModelsInfo | null,
  };

  const customFetch = async (data: RuntimeWebUiFetchData): Promise<Response> => {
    let activeModels: ActiveModelsInfo | null = null;
    try {
      const cached = activeModelsCache;
      if (cached.value && Date.now() - cached.fetchedAt < ACTIVE_MODELS_CACHE_TTL_MS) {
        activeModels = cached.value;
      } else {
        activeModels = await providerApi.getActiveModels();
        activeModelsCache.fetchedAt = Date.now();
        activeModelsCache.value = activeModels;
      }
      const resolvedSlot = activeModels?.resolved_llm || activeModels?.active_llm;
      if (!resolvedSlot?.provider_id || !resolvedSlot?.model) {
        return handleModelError(setRuntimeWaitState, setShowModelPrompt);
      }
      beginRuntimeWait(activeModels, setRuntimeHealthNotice, setRuntimeWaitState);
    } catch (error) {
      activeModelsCache.fetchedAt = 0;
      activeModelsCache.value = null;
      console.error("Failed to check model configuration:", error);
      return handleModelError(setRuntimeWaitState, setShowModelPrompt);
    }

    const requestBody = buildRuntimeChatRequest({
      data,
      runtimeWindow,
      requestedThreadId,
      threadMeta: getThreadMeta(),
      pendingMediaSources: getPendingMediaSources(),
      selectedMediaAnalysisIds: getSelectedMediaAnalysisIds(),
    });

    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    const token = getApiToken();
    if (token) {
      (headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }

    const url = resolveRuntimeChatUrl(optionsBaseUrl);
    const requestThreadId =
      typeof requestBody.thread_id === "string" && requestBody.thread_id.trim()
        ? requestBody.thread_id.trim()
        : null;
    const mediaInputs = Array.isArray(requestBody.media_inputs)
      ? (requestBody.media_inputs as unknown[])
      : [];

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });
      if (response.ok) {
        if (mediaInputs.length > 0) {
          clearPendingMediaDrafts();
        }
        if (requestThreadId && mediaInputs.length > 0) {
          void refreshThreadMediaAnalyses(requestThreadId);
        }
      }
    } catch (error) {
      setRuntimeWaitState(null);
      const localized = localizeRuntimeError(
        "MODEL_CONNECTION_FAILED",
        error instanceof Error ? error.message : String(error),
      );
      setRuntimeHealthNotice({
        type: localized.type,
        title: localized.title,
        description: localized.description,
      });
      throw error;
    }

    if (!response.ok) {
      setRuntimeWaitState(null);
      const responseClone = response.clone();
      void responseClone
        .json()
        .then((payload) => {
          const record =
            payload && typeof payload === "object"
              ? (payload as Record<string, unknown>)
              : {};
          const localized = localizeRuntimeError(
            record.code || record.error || "RUNTIME_ERROR",
            record.message || record.detail || record.error,
          );
          setRuntimeHealthNotice({
            type: localized.type,
            title: localized.title,
            description: localized.description,
          });
        })
        .catch(() => {
          const resolvedSlot = activeModels?.resolved_llm || activeModels?.active_llm;
          setRuntimeHealthNotice({
            type: "error",
            title: "请求发送失败",
            description: resolvedSlot
              ? `请求已发送到 ${resolvedSlot.provider_id}/${resolvedSlot.model}，但服务端没有返回可用结果。`
              : "服务端没有返回可用结果。",
          });
        });
    }
    return response;
  };

  const responseParser = (rawChunk: string): unknown =>
    parseRuntimeResponseChunk(rawChunk, {
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      dispatchGovernanceDirty,
      dispatchHumanAssistDirty,
    });

  return {
    fetch: customFetch,
    responseParser,
  };
}
