import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import type { MediaSourceSpec } from "../../api/modules/media";
import type { ActiveModelsInfo } from "../../api/types/provider";
import {
  getCachedActiveModels,
  invalidateActiveModelsCache,
  resetActiveModelsCacheForTests,
  setCachedActiveModels,
} from "../../runtime/activeModelsCache";
import { CHAT_RUNTIME_TEXT } from "./chatPageHelpers";
import {
  extractRuntimeHealthNotice,
  hasRuntimeStartedResponding,
  localizeRuntimeChunk,
  localizeRuntimeError,
  type RuntimeHealthNotice,
  type RuntimeLifecycleState,
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
export function resetRuntimeTransportForTests(): void {
  resetRuntimeTransportForTestsHelper();
  resetActiveModelsCacheForTests();
  pendingActiveModelsRefresh = null;
}
export const buildRuntimeChatRequest = buildRuntimeChatRequestBody;

type RuntimeSidecarRecord = Record<string, unknown>;

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
  setRuntimeLifecycleState?: (
    state: RuntimeLifecycleState | null,
  ) => void;
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void;
  setShowModelPrompt?: (show: boolean) => void;
  dispatchGovernanceDirty?: () => void;
  dispatchHumanAssistDirty?: () => void;
  onRuntimeSidecarEvent?: (event: RuntimeSidecarRecord) => void;
  onRuntimeResponseTerminal?: (status: string) => void;
}

interface ParseRuntimeResponseChunkArgs {
  setRuntimeHealthNotice: (notice: RuntimeHealthNotice | null) => void;
  setRuntimeLifecycleState?: (
    state: RuntimeLifecycleState | null,
  ) => void;
  setRuntimeWaitState: (state: RuntimeWaitState | null) => void;
  dispatchGovernanceDirty?: () => void;
  dispatchHumanAssistDirty?: () => void;
  onRuntimeSidecarEvent?: (event: RuntimeSidecarRecord) => void;
  onRuntimeResponseTerminal?: (status: string) => void;
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

const TERMINAL_RUNTIME_RESPONSE_STATUSES = new Set([
  "completed",
  "failed",
  "canceled",
  "rejected",
  "incomplete",
]);

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
  "buddy_profile_id",
]);

let pendingActiveModelsRefresh: Promise<ActiveModelsInfo | null> | null = null;

function refreshActiveModelsCacheInBackground(): Promise<ActiveModelsInfo | null> {
  if (!pendingActiveModelsRefresh) {
    pendingActiveModelsRefresh = providerApi
      .getActiveModels()
      .then((activeModels) => {
        setCachedActiveModels(activeModels);
        return activeModels;
      })
      .catch((error) => {
        invalidateActiveModelsCache();
        throw error;
      })
      .finally(() => {
        pendingActiveModelsRefresh = null;
      });
  }
  return pendingActiveModelsRefresh;
}

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

function resolveRuntimeChatUrl(_baseUrl: string | undefined): string {
  return getApiUrl("/runtime-center/chat/run");
}

function beginRuntimeWait(
  activeModels: ActiveModelsInfo | null,
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
  setRuntimeLifecycleState:
    | ((state: RuntimeLifecycleState | null) => void)
    | undefined,
  setShowModelPrompt: ((show: boolean) => void) | undefined,
): Response {
  setRuntimeWaitState(null);
  setRuntimeLifecycleState?.(null);
  setShowModelPrompt?.(true);
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

function normalizeRuntimeSidecarEvent(
  event: Record<string, unknown> | null,
): RuntimeSidecarRecord | null {
  if (!event) {
    return null;
  }
  if (
    event.object === "runtime.sidecar" &&
    typeof event.event === "string" &&
    event.event.trim()
  ) {
    return {
      ...event,
      object: "runtime.sidecar",
      event: event.event.trim(),
    };
  }
  if (
    typeof event.sidecar_event === "string" &&
    event.sidecar_event.trim().length > 0
  ) {
    return {
      ...event,
      object: "runtime.sidecar",
      event: event.sidecar_event.trim(),
    };
  }
  return null;
}

function extractSsePayload(block: string): string | null {
  const lines = block
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith("data:"));
  if (lines.length === 0) {
    return null;
  }
  return lines.map((line) => line.slice(5).trimStart()).join("\n");
}

function parseSseJsonBlock(block: string): Record<string, unknown> | null {
  const payload = extractSsePayload(block);
  if (!payload) {
    return null;
  }
  try {
    const parsed = JSON.parse(payload);
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function isTerminalRuntimeResponseEvent(
  event: Record<string, unknown> | null,
): boolean {
  if (!event || event.object !== "response") {
    return false;
  }
  const status = String(event.status || "").toLowerCase();
  return TERMINAL_RUNTIME_RESPONSE_STATUSES.has(status);
}

function buildRuntimeCompactionDetails(
  payload: Record<string, unknown>,
): string | null {
  const toolUseSummary =
    payload.tool_use_summary && typeof payload.tool_use_summary === "object"
      ? (payload.tool_use_summary as Record<string, unknown>)
      : null;
  const compactionState =
    payload.compaction_state && typeof payload.compaction_state === "object"
      ? (payload.compaction_state as Record<string, unknown>)
      : null;
  const toolResultBudget =
    payload.tool_result_budget && typeof payload.tool_result_budget === "object"
      ? (payload.tool_result_budget as Record<string, unknown>)
      : null;
  const summary =
    typeof toolUseSummary?.summary === "string" && toolUseSummary.summary.trim()
      ? toolUseSummary.summary.trim()
      : typeof compactionState?.summary === "string" &&
          compactionState.summary.trim()
        ? compactionState.summary.trim()
        : null;
  const spillCount =
    typeof compactionState?.spill_count === "number"
      ? compactionState.spill_count
      : null;
  const remainingBudget =
    typeof toolResultBudget?.remaining_budget === "number"
      ? toolResultBudget.remaining_budget
      : null;
  const parts = [summary];
  if (spillCount !== null) {
    parts.push(`spill:${spillCount}`);
  }
  if (remainingBudget !== null) {
    parts.push(`budget-left:${remainingBudget}`);
  }
  const filtered = parts.filter(
    (item): item is string => typeof item === "string" && item.trim().length > 0,
  );
  return filtered.length > 0 ? filtered.join(" ") : null;
}

function resolveRuntimeLifecycleState(
  eventName: string,
  event: RuntimeSidecarRecord,
): RuntimeLifecycleState | null {
  const payload =
    event.payload && typeof event.payload === "object"
      ? (event.payload as Record<string, unknown>)
      : {};
  const details =
    payload.details && typeof payload.details === "object"
      ? (payload.details as Record<string, unknown>)
      : {};
  const message =
    typeof details.message === "string" && details.message.trim().length > 0
      ? details.message.trim()
      : typeof payload.message === "string" && payload.message.trim().length > 0
        ? payload.message.trim()
        : typeof payload.summary === "string" && payload.summary.trim().length > 0
          ? payload.summary.trim()
          : null;
  switch (eventName) {
    case "accepted":
      return {
        phase: "accepted",
        title: "已接受",
        description: "请求已进入运行主链，等待主脑开始响应。",
        tone: "busy",
        updatedAt: Date.now(),
      };
    case "turn_reply_done":
      return {
        phase: "reply_done",
        title: "回复完成",
        description: "主脑回复已结束，正在处理提交尾巴。",
        tone: "busy",
        updatedAt: Date.now(),
      };
    case "commit_started":
      return {
        phase: "commit_started",
        title: "提交中",
        description: "主脑回复已结束，正在提交执行结果。",
        tone: "busy",
        updatedAt: Date.now(),
      };
    case "confirm_required":
      return {
        phase: "confirm_required",
        title: "待确认",
        description: message || "执行结果需要人工确认后才能继续提交。",
        tone: "warning",
        updatedAt: Date.now(),
      };
    case "committed":
      return {
        phase: "committed",
        title: "已提交",
        description: "执行结果已经写回运行主链。",
        tone: "success",
        updatedAt: Date.now(),
      };
    case "commit_failed": {
      const localized = localizeRuntimeError(
        details.raw_code ||
          details.code ||
          payload.code ||
          payload.reason ||
          "MODEL_RUNTIME_FAILED",
        message || "Execution commit failed.",
      );
      return {
        phase: "commit_failed",
        title: "提交失败",
        description: localized.description,
        tone: "error",
        updatedAt: Date.now(),
      };
    }
    default:
      return null;
  }
}

async function forEachSseBlock(
  stream: ReadableStream<Uint8Array>,
  onBlock: (block: string) => Promise<boolean> | boolean,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const pumpBuffer = async (): Promise<boolean> => {
    while (true) {
      const boundary = buffer.indexOf("\n\n");
      if (boundary < 0) {
        return true;
      }
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const shouldContinue = await onBlock(block);
      if (!shouldContinue) {
        return false;
      }
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        buffer = buffer.replace(/\r\n/g, "\n");
        if (buffer.trim().length > 0) {
          await onBlock(buffer);
        }
        return;
      }
      if (!value || value.byteLength <= 0) {
        continue;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      const shouldContinue = await pumpBuffer();
      if (!shouldContinue) {
        await reader.cancel();
        return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function consumeRuntimeSidecarEvent(
  event: RuntimeSidecarRecord,
  {
    setRuntimeHealthNotice,
    setRuntimeLifecycleState,
    setRuntimeWaitState,
    dispatchGovernanceDirty,
    dispatchHumanAssistDirty,
    onRuntimeSidecarEvent,
  }: ParseRuntimeResponseChunkArgs,
): void {
  const normalized = normalizeRuntimeSidecarEvent(event);
  if (!normalized) {
    return;
  }
  onRuntimeSidecarEvent?.(normalized);
  const eventName =
    typeof normalized.event === "string" ? normalized.event.trim() : "";
  if (!eventName) {
    return;
  }

  const payload =
    normalized.payload && typeof normalized.payload === "object"
      ? (normalized.payload as Record<string, unknown>)
      : {};
  const compactionDetails = buildRuntimeCompactionDetails(payload);
  const lifecycleStateBase = resolveRuntimeLifecycleState(eventName, normalized);
  const lifecycleState =
    lifecycleStateBase && compactionDetails
      ? {
          ...lifecycleStateBase,
          description: `${lifecycleStateBase.description} ${compactionDetails}`.trim(),
        }
      : lifecycleStateBase;
  if (eventName === "accepted" || eventName === "turn_reply_done") {
    setRuntimeWaitState(null);
    setRuntimeHealthNotice(null);
    setRuntimeLifecycleState?.(lifecycleState);
    if (eventName === "turn_reply_done") {
      dispatchGovernanceDirty?.();
      dispatchHumanAssistDirty?.();
    }
    return;
  }

  if (
    eventName === "commit_started" ||
    eventName === "committed" ||
    eventName === "confirm_required" ||
    eventName === "commit_failed"
  ) {
    setRuntimeWaitState(null);
    setRuntimeLifecycleState?.(lifecycleState);
    dispatchGovernanceDirty?.();
    dispatchHumanAssistDirty?.();
  }

  if (eventName === "commit_failed") {
    const details =
      payload.details && typeof payload.details === "object"
        ? (payload.details as Record<string, unknown>)
        : {};
    const localized = localizeRuntimeError(
      details.raw_code ||
        details.code ||
        payload.code ||
        payload.reason ||
        "MODEL_RUNTIME_FAILED",
      details.message ||
        payload.message ||
        payload.summary ||
        "Execution commit failed.",
    );
    setRuntimeHealthNotice({
      type: localized.type,
      title: localized.title,
      description: localized.description,
    });
  }
}

function splitRuntimeChatEventStream(
  response: Response,
  parserArgs: ParseRuntimeResponseChunkArgs,
): Response {
  const body = response.body;
  if (
    !body ||
    typeof ReadableStream === "undefined" ||
    typeof body.tee !== "function"
  ) {
    return response;
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("text/event-stream")) {
    return response;
  }

  const [visibleStream, sidecarStream] = body.tee();
  const headers = new Headers(response.headers);
  headers.delete("content-length");

  void forEachSseBlock(sidecarStream, async (block) => {
    const parsed = parseSseJsonBlock(block);
    const sidecarEvent = normalizeRuntimeSidecarEvent(parsed);
    if (sidecarEvent) {
      consumeRuntimeSidecarEvent(sidecarEvent, parserArgs);
    }
    return true;
  }).catch((error) => {
    console.warn("Failed to consume runtime sidecar tail:", error);
  });

  const encoder = new TextEncoder();
  const filtered = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;
      void forEachSseBlock(visibleStream, async (block) => {
        const parsed = parseSseJsonBlock(block);
        if (normalizeRuntimeSidecarEvent(parsed)) {
          return true;
        }
        controller.enqueue(encoder.encode(`${block}\n\n`));
        if (isTerminalRuntimeResponseEvent(parsed)) {
          closed = true;
          controller.close();
          return false;
        }
        return true;
      })
        .then(() => {
          if (!closed) {
            closed = true;
            controller.close();
          }
        })
        .catch((error) => {
          controller.error(error);
        });
    },
  });

  return new Response(filtered, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export function parseRuntimeResponseChunk(
  rawChunk: string,
  parserArgs: ParseRuntimeResponseChunkArgs,
): unknown {
  const parsed = localizeRuntimeChunk(JSON.parse(rawChunk));
  if (parsed && typeof parsed === "object") {
    const sidecarEvent = normalizeRuntimeSidecarEvent(
      parsed as Record<string, unknown>,
    );
    if (sidecarEvent) {
      consumeRuntimeSidecarEvent(sidecarEvent, parserArgs);
      return parsed;
    }
  }

  const healthNotice = extractRuntimeHealthNotice(parsed);
  if (healthNotice) {
    parserArgs.setRuntimeWaitState(null);
    parserArgs.setRuntimeLifecycleState?.(null);
    parserArgs.setRuntimeHealthNotice(healthNotice);
    return parsed;
  }

  if (hasRuntimeStartedResponding(parsed)) {
    parserArgs.setRuntimeWaitState(null);
    parserArgs.setRuntimeLifecycleState?.(null);
    parserArgs.setRuntimeHealthNotice(null);
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
    if (TERMINAL_RUNTIME_RESPONSE_STATUSES.has(status)) {
      parserArgs.setRuntimeWaitState(null);
      parserArgs.dispatchGovernanceDirty?.();
      parserArgs.dispatchHumanAssistDirty?.();
      parserArgs.onRuntimeResponseTerminal?.(status);
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
  setRuntimeLifecycleState,
  setRuntimeWaitState,
  setShowModelPrompt,
  dispatchGovernanceDirty,
  dispatchHumanAssistDirty,
  onRuntimeSidecarEvent,
  onRuntimeResponseTerminal,
}: CreateRuntimeTransportArgs): {
  fetch: (data: RuntimeWebUiFetchData) => Promise<Response>;
  responseParser: (rawChunk: string) => unknown;
  cancelSession: (sessionId: string) => void;
} {
  const sessionAbortControllers = new Map<string, SessionAbortState>();
  const parserArgs: ParseRuntimeResponseChunkArgs = {
    setRuntimeHealthNotice,
    setRuntimeLifecycleState,
    setRuntimeWaitState,
    dispatchGovernanceDirty,
    dispatchHumanAssistDirty,
    onRuntimeSidecarEvent,
    onRuntimeResponseTerminal,
  };

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
      const cached = getCachedActiveModels();
      if (cached) {
        activeModels = cached;
        const resolvedSlot = activeModels?.resolved_llm || activeModels?.active_llm;
        if (!resolvedSlot?.provider_id || !resolvedSlot?.model) {
          return handleModelError(
            setRuntimeWaitState,
            setRuntimeLifecycleState,
            setShowModelPrompt,
          );
        }
        setRuntimeLifecycleState?.(null);
        beginRuntimeWait(activeModels, setRuntimeHealthNotice, setRuntimeWaitState);
      } else {
        setRuntimeLifecycleState?.(null);
        beginRuntimeWait(null, setRuntimeHealthNotice, setRuntimeWaitState);
        void raceWithAbort(
          refreshActiveModelsCacheInBackground(),
          localAbortController.signal,
        ).catch((error) => {
          if (isAbortRuntimeError(error)) {
            return;
          }
          console.error("Failed to refresh model configuration:", error);
        });
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
        setRuntimeLifecycleState?.(null);
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
        setRuntimeLifecycleState?.(null);
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

      return splitRuntimeChatEventStream(response, parserArgs);
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
    parseRuntimeResponseChunk(rawChunk, parserArgs);

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
    setRuntimeLifecycleState?.(null);
    setRuntimeHealthNotice(null);
  };

  return {
    fetch: customFetch,
    responseParser,
    cancelSession,
  };
}
