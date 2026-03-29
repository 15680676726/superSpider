import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import type { ActiveModelsInfo } from "../../api/types/provider";
import type { MediaSourceSpec } from "../../api/modules/media";
import { CHAT_RUNTIME_TEXT } from "./chatPageHelpers";
import {
  extractRuntimeHealthNotice,
  hasRuntimeStartedResponding,
  localizeRuntimeChunk,
  localizeRuntimeError,
  type RuntimeHealthNotice,
  type RuntimeWaitState,
} from "./runtimeDiagnostics";
import {
  buildRuntimeChatRequest as buildRuntimeChatRequestBody,
  firstNonEmptyString as firstNonEmptyStringHelper,
  normalizeRuntimeStringList as normalizeRuntimeStringListHelper,
  queueHumanAssistSubmissionForNextMessage as queueHumanAssistSubmissionForNextMessageHelper,
  resetRuntimeTransportForTests as resetRuntimeTransportForTestsHelper,
  resolveRuntimeSessionContext as resolveRuntimeSessionContextHelper,
  resolveRuntimeThreadContext as resolveRuntimeThreadContextHelper,
  type RuntimeWebUiFetchData,
  type RuntimeWindowContext,
} from "./runtimeTransportRequest";
export type {
  RuntimeSessionContext,
  RuntimeThreadContext,
  RuntimeWebUiFetchData,
  RuntimeWindowContext,
} from "./runtimeTransportRequest";

export const firstNonEmptyString = firstNonEmptyStringHelper;
export const normalizeRuntimeStringList = normalizeRuntimeStringListHelper;
export const resolveRuntimeSessionContext = resolveRuntimeSessionContextHelper;
export const resolveRuntimeThreadContext = resolveRuntimeThreadContextHelper;
export const queueHumanAssistSubmissionForNextMessage =
  queueHumanAssistSubmissionForNextMessageHelper;
export const resetRuntimeTransportForTests = resetRuntimeTransportForTestsHelper;
export const buildRuntimeChatRequest = buildRuntimeChatRequestBody;

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

interface ParseRuntimeResponseChunkArgs {
  setRuntimeHealthNotice: (notice: RuntimeHealthNotice | null) => void;
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void;
  dispatchGovernanceDirty?: () => void;
  dispatchHumanAssistDirty?: () => void;
}

const ACTIVE_MODELS_CACHE_TTL_MS = 30_000;

function resolveRuntimeChatUrl(baseUrl: string | undefined): string {
  const trimmed = typeof baseUrl === "string" ? baseUrl.trim() : "";
  if (!trimmed) {
    return getApiUrl("/runtime-center/chat/run");
  }
  return trimmed;
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
