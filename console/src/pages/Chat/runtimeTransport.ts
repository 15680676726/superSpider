import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import type { MediaSourceSpec } from "../../api/modules/media";
import type { ActiveModelsInfo } from "../../api/types/provider";
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

interface LinkedAbortController {
  signal: AbortSignal;
  cleanup: () => void;
}

interface SessionAbortState {
  cancelRequested: boolean;
  controller: AbortController;
  networkStarted: boolean;
}

const ACTIVE_MODELS_CACHE_TTL_MS = 30_000;

const RUNTIME_BIZ_PARAM_ALLOWLIST = new Set<string>([
  "requested_actions",
  "media_inputs",
  "media_analysis_ids",
  "control_thread_id",
  "work_context_id",
  "context_key",
  "industry_instance_id",
  "industry_label",
  "industry_role_id",
  "industry_role_name",
  "entry_source",
  "owner_scope",
  "session_kind",
  "agent_id",
  "agent_name",
  "interaction_mode",
  "environment_ref",
  "thread_id",
  "session_id",
  "user_id",
  "channel",
]);

function sanitizeRuntimeBizParams(
  value: unknown,
): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const sanitized: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (!RUNTIME_BIZ_PARAM_ALLOWLIST.has(key)) {
      continue;
    }
    sanitized[key] = item;
  }
  return Object.keys(sanitized).length > 0 ? sanitized : undefined;
}

function trimRuntimeRequestBody(
  value: Record<string, unknown>,
): Record<string, unknown> {
  const trimmed: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (item === undefined || item === null) {
      continue;
    }
    if (typeof item === "string" && item.trim().length === 0) {
      continue;
    }
    if (
      Array.isArray(item) &&
      item.length === 0 &&
      (key === "requested_actions" ||
        key === "media_analysis_ids" ||
        key === "media_inputs")
    ) {
      continue;
    }
    trimmed[key] = item;
  }
  return trimmed;
}

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

function isAbortRuntimeError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === "AbortError";
  }
  return (
    error instanceof Error &&
    (error.name === "AbortError" ||
      error.message.toLowerCase().includes("aborted"))
  );
}

function linkAbortSignals(
  upstreamSignal: AbortSignal | null | undefined,
  controller: AbortController,
): LinkedAbortController {
  if (!upstreamSignal) {
    return {
      signal: controller.signal,
      cleanup: () => {},
    };
  }

  if (upstreamSignal.aborted) {
    controller.abort();
    return {
      signal: controller.signal,
      cleanup: () => {},
    };
  }

  const forwardAbort = () => controller.abort();
  upstreamSignal.addEventListener("abort", forwardAbort, { once: true });
  return {
    signal: controller.signal,
    cleanup: () => upstreamSignal.removeEventListener("abort", forwardAbort),
  };
}

function createAbortRuntimeError(signal: AbortSignal): Error {
  if (signal.reason instanceof Error && signal.reason.name !== "AbortError") {
    return signal.reason;
  }
  return new DOMException("The operation was aborted.", "AbortError");
}

function raceWithAbort<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) {
    return Promise.reject(createAbortRuntimeError(signal));
  }

  return new Promise<T>((resolve, reject) => {
    const handleAbort = () => {
      signal.removeEventListener("abort", handleAbort);
      reject(createAbortRuntimeError(signal));
    };

    signal.addEventListener("abort", handleAbort, { once: true });
    promise.then(
      (value) => {
        signal.removeEventListener("abort", handleAbort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener("abort", handleAbort);
        reject(error);
      },
    );
  });
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
    if (
      ["completed", "failed", "canceled", "rejected", "incomplete"].includes(
        status,
      )
    ) {
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
  cancelSession: (sessionId: string) => void;
} {
  const activeModelsCache = {
    fetchedAt: 0,
    value: null as ActiveModelsInfo | null,
  };
  const sessionAbortControllers = new Map<string, SessionAbortState>();

  const customFetch = async (data: RuntimeWebUiFetchData): Promise<Response> => {
    const threadMeta = getThreadMeta();
    const lastMessage = data.input[data.input.length - 1];
    const sessionContext = resolveRuntimeSessionContext({
      runtimeWindow,
      requestedThreadId,
      threadMeta,
      session: lastMessage?.session,
    });
    const requestSessionId = firstNonEmptyString(
      sessionContext.sessionId,
      sessionContext.currentThreadId,
    );
    const localAbortController = new AbortController();
    const linkedAbortController = linkAbortSignals(
      data.signal,
      localAbortController,
    );
    const sessionAbortState: SessionAbortState = {
      cancelRequested: false,
      controller: localAbortController,
      networkStarted: false,
    };

    if (requestSessionId) {
      sessionAbortControllers.set(requestSessionId, sessionAbortState);
    }

    try {
      let activeModels: ActiveModelsInfo | null = null;
      try {
        const cached = activeModelsCache;
        if (
          cached.value &&
          Date.now() - cached.fetchedAt < ACTIVE_MODELS_CACHE_TTL_MS
        ) {
          activeModels = cached.value;
        } else {
          activeModels = await raceWithAbort(
            providerApi.getActiveModels(),
            localAbortController.signal,
          );
          activeModelsCache.fetchedAt = Date.now();
          activeModelsCache.value = activeModels;
        }

        const resolvedSlot = activeModels?.resolved_llm || activeModels?.active_llm;
        if (!resolvedSlot?.provider_id || !resolvedSlot?.model) {
          return handleModelError(setRuntimeWaitState, setShowModelPrompt);
        }

        beginRuntimeWait(activeModels, setRuntimeHealthNotice, setRuntimeWaitState);
      } catch (error) {
        if (isAbortRuntimeError(error)) {
          setRuntimeWaitState(null);
          setRuntimeHealthNotice(null);
          throw error;
        }

        activeModelsCache.fetchedAt = 0;
        activeModelsCache.value = null;
        console.error("Failed to check model configuration:", error);
        return handleModelError(setRuntimeWaitState, setShowModelPrompt);
      }

      const requestBody = trimRuntimeRequestBody(
        buildRuntimeChatRequest({
          data: {
            ...data,
            biz_params: sanitizeRuntimeBizParams(data.biz_params),
          },
          runtimeWindow,
          requestedThreadId,
          threadMeta,
          pendingMediaSources: getPendingMediaSources(),
          selectedMediaAnalysisIds: getSelectedMediaAnalysisIds(),
        }),
      );

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
        const responsePromise = fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(requestBody),
          signal: linkedAbortController.signal,
        });
        sessionAbortState.networkStarted = true;
        if (
          sessionAbortState.cancelRequested &&
          !localAbortController.signal.aborted
        ) {
          queueMicrotask(() => {
            localAbortController.abort();
          });
        }
        response = await responsePromise;
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
        if (isAbortRuntimeError(error)) {
          setRuntimeHealthNotice(null);
          throw error;
        }

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
            const resolvedSlot =
              activeModels?.resolved_llm || activeModels?.active_llm;
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
    } finally {
      linkedAbortController.cleanup();
      if (
        requestSessionId &&
        sessionAbortControllers.get(requestSessionId) === sessionAbortState
      ) {
        sessionAbortControllers.delete(requestSessionId);
      }
    }
  };

  const responseParser = (rawChunk: string): unknown =>
    parseRuntimeResponseChunk(rawChunk, {
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      dispatchGovernanceDirty,
      dispatchHumanAssistDirty,
    });

  const cancelSession = (sessionId: string): void => {
    const normalizedSessionId = sessionId.trim();
    if (!normalizedSessionId) {
      return;
    }
    const sessionAbortState = sessionAbortControllers.get(normalizedSessionId);
    if (sessionAbortState) {
      sessionAbortState.cancelRequested = true;
      if (sessionAbortState.networkStarted) {
        sessionAbortState.controller.abort();
      }
    }
    setRuntimeWaitState(null);
    setRuntimeHealthNotice(null);
  };

  return {
    fetch: customFetch,
    responseParser,
    cancelSession,
  };
}
