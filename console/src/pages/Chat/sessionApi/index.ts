import type {
  IAgentScopeRuntimeWebUIMessage,
  IAgentScopeRuntimeWebUISession,
  IAgentScopeRuntimeWebUISessionAPI,
} from "@agentscope-ai/chat";
import api, {
  type RuntimeConversation,
  type RuntimeConversationMessage as Message,
} from "../../../api";
import { isApiError } from "../../../api/errors";
import { localizeRuntimeError } from "../runtimeDiagnostics";

interface CustomWindow extends Window {
  currentThreadId?: string;
  currentUserId?: string;
  currentChannel?: string;
  currentThreadMeta?: Record<string, unknown>;
}

declare const window: CustomWindow;

interface ContentItem {
  type: string;
  text?: string;
  [key: string]: unknown;
}

interface OutputMessage extends Omit<Message, "role"> {
  role: string;
  metadata: null;
  sequence_number?: number;
}

type RuntimeBubbleStatus = "finished" | "generating" | "interrupted" | "error";

interface ExtendedSession extends IAgentScopeRuntimeWebUISession {
  threadId: string;
  userId: string;
  channel: string;
  meta: Record<string, unknown>;
}

const IN_PROGRESS_MESSAGE_STATUSES = new Set(["created", "queued", "in_progress"]);
const TERMINAL_RESPONSE_STATUSES = new Set([
  "completed",
  "failed",
  "canceled",
  "rejected",
  "incomplete",
]);

export interface BoundThreadPayload {
  name: string;
  threadId: string;
  userId: string;
  channel?: string;
  meta?: Record<string, unknown>;
}

function buildSeedSessionFromBinding(
  payload: BoundThreadPayload,
): ExtendedSession | null {
  const threadId = normalizeThreadId(payload.threadId);
  if (!threadId) {
    return null;
  }
  const meta = normalizeMeta(payload.meta);
  return {
    id: threadId,
    name:
      (typeof payload.name === "string" && payload.name.trim()) ||
      threadId,
    threadId,
    userId:
      (typeof payload.userId === "string" && payload.userId.trim()) ||
      "default",
    channel:
      (typeof payload.channel === "string" && payload.channel.trim()) ||
      "console",
    messages: [],
    meta: {
      ...meta,
      runtime_session_id:
        typeof meta.runtime_session_id === "string" && meta.runtime_session_id.trim()
          ? meta.runtime_session_id
          : threadId,
    },
  };
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

function normalizeMeta(meta: unknown): Record<string, unknown> {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
    return {};
  }
  return meta as Record<string, unknown>;
}

function buildConversationMeta(conversation: RuntimeConversation): Record<string, unknown> {
  const meta = normalizeMeta(conversation.meta);
  return {
    ...meta,
    runtime_session_id:
      typeof meta.runtime_session_id === "string" && meta.runtime_session_id.trim()
        ? meta.runtime_session_id
        : conversation.session_id,
  };
}


function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function extractTextFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return String(content || "");
  return (content as ContentItem[])
    .filter((item) => item.type === "text")
    .map((item) => item.text || "")
    .filter(Boolean)
    .join("\n");
}

function toOutputMessage(msg: Message): OutputMessage {
  let role = msg.role;
  if (msg.type === "plugin_call_output" && role === "system") {
    role = "tool";
  }
  const nextMessage: OutputMessage = {
    ...msg,
    role,
    metadata: null,
  };
  if (nextMessage.type === "error") {
    const localized = localizeRuntimeError(nextMessage.code, nextMessage.message);
    return {
      ...nextMessage,
      code: localized.title,
      message: localized.description,
    };
  }
  return nextMessage;
}

function buildUserCard(msg: Message): IAgentScopeRuntimeWebUIMessage {
  const text = extractTextFromContent(msg.content);
  const status =
    typeof msg.status === "string" && msg.status.trim().length > 0
      ? msg.status.trim()
      : "completed";
  return {
    id: (msg.id as string) || generateId(),
    role: "user",
    cards: [
      {
        code: "AgentScopeRuntimeRequestCard",
        data: {
          input: [
            {
              role: "user",
              type: "message",
              content: [{ type: "text", text, status }],
            },
          ],
        },
      },
    ],
  };
}

function normalizeOutputStatus(message: OutputMessage): string {
  return typeof message.status === "string" && message.status
    ? message.status
    : "completed";
}

function resolveResponseStatus(outputMessages: OutputMessage[]): string {
  const explicitStatuses = outputMessages
    .map((message) =>
      typeof message.status === "string" && message.status
        ? message.status
        : null,
    )
    .filter((status): status is string => Boolean(status));
  const statuses = explicitStatuses.length > 0 ? explicitStatuses : ["completed"];
  const lastStatus = statuses[statuses.length - 1] || "completed";

  if (lastStatus === "failed") {
    return "failed";
  }
  if (lastStatus === "rejected") {
    return "rejected";
  }
  if (lastStatus === "canceled") {
    return "canceled";
  }
  if (lastStatus === "incomplete") {
    return "incomplete";
  }
  if (["created", "queued", "in_progress"].includes(lastStatus)) {
    return "in_progress";
  }
  return lastStatus;
}

function toBubbleStatus(status: string): RuntimeBubbleStatus {
  if (status === "failed") {
    return "error";
  }
  if (["rejected", "canceled", "incomplete"].includes(status)) {
    return "interrupted";
  }
  if (["created", "queued", "in_progress"].includes(status)) {
    return "generating";
  }
  return "finished";
}

function normalizeTerminalResponseStatus(status: string | null | undefined): string | null {
  if (typeof status !== "string" || !status.trim()) {
    return null;
  }
  const normalized = status.trim().toLowerCase();
  return TERMINAL_RESPONSE_STATUSES.has(normalized) ? normalized : null;
}

function settleTerminalResponseData(
  value: unknown,
  terminalStatus: string,
  completedAt: number,
): unknown {
  if (!value || typeof value !== "object") {
    return value;
  }
  const record = value as Record<string, unknown>;
  let changed = false;
  const next: Record<string, unknown> = { ...record };

  if (
    typeof next.status === "string" &&
    IN_PROGRESS_MESSAGE_STATUSES.has(next.status.trim().toLowerCase())
  ) {
    next.status = terminalStatus;
    changed = true;
  }

  if (Array.isArray(next.output)) {
    let outputChanged = false;
    const nextOutput = next.output.map((item) => {
      if (!item || typeof item !== "object") {
        return item;
      }
      const outputRecord = item as Record<string, unknown>;
      if (
        typeof outputRecord.status === "string" &&
        IN_PROGRESS_MESSAGE_STATUSES.has(outputRecord.status.trim().toLowerCase())
      ) {
        outputChanged = true;
        return {
          ...outputRecord,
          status: terminalStatus,
        };
      }
      return item;
    });
    if (outputChanged) {
      next.output = nextOutput;
      changed = true;
    }
  }

  const looksLikeResponseCard =
    next.object === "response" ||
    Array.isArray(next.output) ||
    typeof next.status === "string";
  if (looksLikeResponseCard && next.completed_at == null) {
    next.completed_at = completedAt;
    changed = true;
  }

  return changed ? next : value;
}

function settleMessageForTerminalResponse(
  message: IAgentScopeRuntimeWebUIMessage,
  terminalStatus: string,
  completedAt: number,
): IAgentScopeRuntimeWebUIMessage {
  const nextBubbleStatus = toBubbleStatus(terminalStatus);
  let changed = false;
  const nextMessage: IAgentScopeRuntimeWebUIMessage = { ...message };

  if (
    typeof nextMessage.msgStatus === "string" &&
    nextMessage.msgStatus.trim().toLowerCase() === "generating"
  ) {
    nextMessage.msgStatus = nextBubbleStatus;
    changed = true;
  }

  if (Array.isArray(message.cards)) {
    let cardsChanged = false;
    const nextCards = message.cards.map((card) => {
      if (!card || typeof card !== "object") {
        return card;
      }
      const typedCard = card as typeof card & { data?: unknown };
      const nextData = settleTerminalResponseData(
        typedCard.data,
        terminalStatus,
        completedAt,
      );
      if (nextData !== typedCard.data) {
        changed = true;
        cardsChanged = true;
        return {
          ...(card as unknown as Record<string, unknown>),
          data: nextData,
        } as typeof card;
      }
      return card;
    });
    if (cardsChanged) {
      nextMessage.cards = nextCards;
    }
  }

  return changed ? nextMessage : message;
}

function settleMessagesForTerminalResponse(
  messages: IAgentScopeRuntimeWebUIMessage[],
  terminalStatus: string,
  completedAt: number,
): IAgentScopeRuntimeWebUIMessage[] {
  let changed = false;
  const nextMessages = messages.map((message) => {
    const nextMessage = settleMessageForTerminalResponse(
      message,
      terminalStatus,
      completedAt,
    );
    if (nextMessage !== message) {
      changed = true;
    }
    return nextMessage;
  });
  return changed ? nextMessages : messages;
}

function resolveResponseError(outputMessages: OutputMessage[]): unknown {
  const failedMessage = outputMessages.find(
    (message) => normalizeOutputStatus(message) === "failed",
  );
  if (!failedMessage) {
    return null;
  }
  if (failedMessage.error) {
    const localized = localizeRuntimeError(
      (failedMessage.error as { code?: unknown }).code,
      (failedMessage.error as { message?: unknown }).message,
    );
    return {
      ...(failedMessage.error as Record<string, unknown>),
      code: localized.title,
      message: localized.description,
    };
  }
  if (typeof failedMessage.message === "string" && failedMessage.message) {
    const localized = localizeRuntimeError(
      typeof failedMessage.code === "string" && failedMessage.code
        ? failedMessage.code
        : "runtime_error",
      failedMessage.message,
    );
    return {
      code: localized.title,
      message: localized.description,
    };
  }
  return null;
}

function buildResponseCard(
  outputMessages: OutputMessage[],
): IAgentScopeRuntimeWebUIMessage {
  const now = Math.floor(Date.now() / 1000);
  const responseStatus = resolveResponseStatus(outputMessages);
  const bubbleStatus = toBubbleStatus(responseStatus);
  const maxSeq = outputMessages.reduce(
    (max: number, message: OutputMessage) =>
      Math.max(max, message.sequence_number || 0),
    0,
  );
  return {
    id: generateId(),
    role: "assistant",
    cards: [
      {
        code: "AgentScopeRuntimeResponseCard",
        data: {
          id: `response_${generateId()}`,
          output: outputMessages,
          object: "response",
          status: responseStatus,
          created_at: now,
          sequence_number: maxSeq + 1,
          error: resolveResponseError(outputMessages),
          completed_at: bubbleStatus === "generating" ? null : now,
          usage: null,
        },
      },
    ],
    msgStatus: bubbleStatus,
  };
}

function convertMessages(messages: Message[]): IAgentScopeRuntimeWebUIMessage[] {
  const result: IAgentScopeRuntimeWebUIMessage[] = [];
  let index = 0;

  while (index < messages.length) {
    const current = messages[index];
    if (current.role === "user") {
      result.push(buildUserCard(current));
      index += 1;
      continue;
    }

    const outputMessages: OutputMessage[] = [];
    while (index < messages.length && messages[index].role !== "user") {
      outputMessages.push(toOutputMessage(messages[index]));
      index += 1;
    }
    if (outputMessages.length > 0) {
      result.push(buildResponseCard(outputMessages));
    }
  }

  return result;
}

function collectMessageStatuses(message: IAgentScopeRuntimeWebUIMessage): string[] {
  const statuses: string[] = [];
  if (typeof message.msgStatus === "string" && message.msgStatus.trim()) {
    statuses.push(message.msgStatus.trim().toLowerCase());
  }
  const cards = Array.isArray(message.cards) ? message.cards : [];
  for (const card of cards) {
    if (!card || typeof card !== "object") {
      continue;
    }
    const data = (card as {
      data?: {
        status?: unknown;
        input?: Array<{
          content?: Array<{ status?: unknown }>;
        }>;
      };
    }).data;
    if (typeof data?.status === "string" && data.status.trim()) {
      statuses.push(data.status.trim().toLowerCase());
    }
    const input = Array.isArray(data?.input) ? data.input : [];
    for (const item of input) {
      const content = Array.isArray(item?.content) ? item.content : [];
      for (const contentItem of content) {
        if (
          contentItem &&
          typeof contentItem === "object" &&
          typeof contentItem.status === "string" &&
          contentItem.status.trim()
        ) {
          statuses.push(contentItem.status.trim().toLowerCase());
        }
      }
    }
  }
  return statuses;
}

function hasInFlightMessages(messages: IAgentScopeRuntimeWebUIMessage[]): boolean {
  return messages.some((message) =>
    collectMessageStatuses(message).some(
      (status) =>
        status === "generating" || IN_PROGRESS_MESSAGE_STATUSES.has(status),
    ),
  );
}

function countUserMessages(messages: IAgentScopeRuntimeWebUIMessage[]): number {
  return messages.filter((message) => message.role === "user").length;
}

function shouldPreferFetchedMessages(
  existingMessages: IAgentScopeRuntimeWebUIMessage[],
  fetchedMessages: IAgentScopeRuntimeWebUIMessage[],
): boolean {
  if (existingMessages.length <= fetchedMessages.length) {
    return true;
  }

  const existingHasInFlight = hasInFlightMessages(existingMessages);
  const fetchedHasInFlight = hasInFlightMessages(fetchedMessages);
  if (!existingHasInFlight || fetchedHasInFlight) {
    return false;
  }

  if (countUserMessages(fetchedMessages) < countUserMessages(existingMessages)) {
    return false;
  }

  const lastFetchedMessage = fetchedMessages[fetchedMessages.length - 1];
  return Boolean(lastFetchedMessage && lastFetchedMessage.role === "assistant");
}

function conversationToSession(
  conversation: RuntimeConversation,
): ExtendedSession {
  return {
    id: conversation.id,
    name: conversation.name || conversation.id,
    threadId: conversation.id,
    userId: conversation.user_id,
    channel: conversation.channel,
    messages: convertMessages(conversation.messages || []),
    meta: buildConversationMeta(conversation),
  };
}

function buildFallbackSessionFromConversation(
  conversation: RuntimeConversation,
): ExtendedSession {
  return {
    id: conversation.id,
    name: conversation.name || conversation.id,
    threadId: conversation.id,
    userId: conversation.user_id,
    channel: conversation.channel,
    messages: [],
    meta: buildConversationMeta(conversation),
  };
}

class SessionApi implements IAgentScopeRuntimeWebUISessionAPI {
  private sessionList: IAgentScopeRuntimeWebUISession[] = [];
  private preferredThreadId: string | null = null;
  private threadCache: Map<
    string,
    { session: IAgentScopeRuntimeWebUISession; timestamp: number }
  > = new Map();
  private threadFetchPromises: Map<
    string,
    Promise<IAgentScopeRuntimeWebUISession>
  > = new Map();
  private threadCacheTimeout = 5000;

  private async fetchRuntimeConversationWithRetry(
    threadId: string,
  ): Promise<RuntimeConversation> {
    try {
      return await api.getRuntimeConversation(threadId);
    } catch (error) {
      if (!(isApiError(error) && error.isNotFound)) {
        throw error;
      }
    }
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    return api.getRuntimeConversation(threadId);
  }

  private updateWindowVariables(session: ExtendedSession): void {
    window.currentThreadId = session.threadId || "";
    window.currentUserId = session.userId || "default";
    window.currentChannel = session.channel || "console";
    window.currentThreadMeta = session.meta || {};
    window.dispatchEvent(
      new CustomEvent("copaw:thread-context", {
        detail: {
          id: session.id,
          threadId: session.threadId,
          userId: session.userId,
          channel: session.channel,
          meta: session.meta || {},
        },
      }),
    );
  }

  clearBoundThreadContext(threadId?: string | null): void {
    const normalizedThreadId = normalizeThreadId(threadId);
    const currentThreadId = normalizeThreadId(window.currentThreadId);
    if (normalizedThreadId && currentThreadId && normalizedThreadId !== currentThreadId) {
      return;
    }
    window.currentThreadId = "";
    window.currentUserId = "";
    window.currentChannel = "";
    window.currentThreadMeta = {};
    window.dispatchEvent(
      new CustomEvent("copaw:thread-context", {
        detail: {
          id: "",
          threadId: "",
          userId: "",
          channel: "",
          meta: {},
        },
      }),
    );
  }

  setPreferredThreadId(threadId: string | null): void {
    const normalizedThreadId = normalizeThreadId(threadId);
    this.preferredThreadId = normalizedThreadId;
    if (!normalizedThreadId || this.sessionList.length === 0) {
      return;
    }
    this.sessionList = this.orderSessions(this.sessionList);
  }

  private orderSessions(
    sessions: IAgentScopeRuntimeWebUISession[],
  ): IAgentScopeRuntimeWebUISession[] {
    if (!this.preferredThreadId) {
      return [...sessions];
    }
    const next = [...sessions];
    const index = next.findIndex((item) => item.id === this.preferredThreadId);
    if (index <= 0) {
      return next;
    }
    const [preferred] = next.splice(index, 1);
    next.unshift(preferred);
    return next;
  }

  getActiveThreadId(): string | null {
    return normalizeThreadId(this.preferredThreadId || window.currentThreadId);
  }

  private findExistingSession(threadId: string): ExtendedSession | null {
    const existing = this.sessionList.find((item) => item.id === threadId);
    return existing ? (existing as ExtendedSession) : null;
  }

  private mergeFetchedSession(
    fetched: ExtendedSession,
    existing: ExtendedSession | null,
  ): ExtendedSession {
    if (!existing) {
      return fetched;
    }
    const existingMessages = Array.isArray(existing.messages) ? existing.messages : [];
    const fetchedMessages = Array.isArray(fetched.messages) ? fetched.messages : [];
    return {
      ...fetched,
      name: fetched.name || existing.name || fetched.id,
      userId: fetched.userId || existing.userId,
      channel: fetched.channel || existing.channel,
      meta: {
        ...(existing.meta || {}),
        ...(fetched.meta || {}),
      },
      messages: shouldPreferFetchedMessages(existingMessages, fetchedMessages)
        ? fetchedMessages
        : existingMessages,
    };
  }

  private replaceSession(session: ExtendedSession): void {
    const next = [...this.sessionList];
    const index = next.findIndex((item) => item.id === session.id);
    if (index >= 0) {
      next[index] = session;
    } else {
      next.unshift(session);
    }
    this.sessionList = this.orderSessions(next);
  }

  private cacheSession(session: ExtendedSession): void {
    this.replaceSession(session);
    this.threadCache.set(session.id, {
      session,
      timestamp: Date.now(),
    });
    this.updateWindowVariables(session);
  }

  private getCachedSession(threadId: string): ExtendedSession | null {
    const cached = this.threadCache.get(threadId);
    if (!cached) {
      return null;
    }
    if (Date.now() - cached.timestamp >= this.threadCacheTimeout) {
      this.threadCache.delete(threadId);
      return null;
    }
    return cached.session as ExtendedSession;
  }

  private shouldUseSeedSessionFallback(
    error: unknown,
    seedSession: ExtendedSession | null,
  ): boolean {
    if (!seedSession || !seedSession.threadId.startsWith("industry-chat:")) {
      return false;
    }
    if (!(error instanceof Error)) {
      return false;
    }
    const message = error.message.trim().toLowerCase();
    return message.startsWith("[404]");
  }

  private async resolveSessionSeed(threadId: string): Promise<ExtendedSession> {
    const cached = this.getCachedSession(threadId);
    if (cached) {
      return cached;
    }
    const existing = this.findExistingSession(threadId);
    if (existing) {
      return existing;
    }
    return (await this.getSession(threadId)) as ExtendedSession;
  }

  private requireBoundThreadId(): string {
    const threadId = normalizeThreadId(
      this.preferredThreadId || window.currentThreadId,
    );
    if (threadId) {
      return threadId;
    }
    throw new Error(
      "运行聊天必须先进入主脑协作入口或伙伴主场。",
    );
  }

  async getSessionList() {
    const threadId = normalizeThreadId(
      this.preferredThreadId || window.currentThreadId,
    );
    if (!threadId) {
      return [...this.sessionList];
    }
    await this.getSession(threadId);
    return [...this.sessionList];
  }

  async getSession(threadId: string) {
    const normalizedThreadId = normalizeThreadId(threadId);
    if (!normalizedThreadId) {
      // Return empty session when threadId is not provided
      // This happens when @agentscope-ai/chat component initializes with undefined currentSessionId
      return {
        id: "",
        name: "",
        messages: [],
      } as IAgentScopeRuntimeWebUISession;
    }

    const cached = this.getCachedSession(normalizedThreadId);
    if (cached) {
      this.updateWindowVariables(cached);
      return cached;
    }

    const existing = this.findExistingSession(normalizedThreadId);
    if (existing) {
      const existingMessages = Array.isArray(existing.messages) ? existing.messages : [];
      const refreshInProgress = this.threadFetchPromises.get(normalizedThreadId);
      if (refreshInProgress) {
        return refreshInProgress;
      }
      const refreshPromise = this.fetchSessionFromBackend(
        normalizedThreadId,
        existing,
      ).catch((error) => {
        console.warn(
          hasInFlightMessages(existingMessages)
            ? `Failed to refresh active runtime conversation ${normalizedThreadId}:`
            : `Failed to refresh stale runtime conversation ${normalizedThreadId}:`,
          error,
        );
        this.cacheSession(existing);
        return existing;
      });
      this.threadFetchPromises.set(normalizedThreadId, refreshPromise);
      try {
        return await refreshPromise;
      } finally {
        this.threadFetchPromises.delete(normalizedThreadId);
      }
    }

    const existingPromise = this.threadFetchPromises.get(normalizedThreadId);
    if (existingPromise) {
      return existingPromise;
    }

    const fetchPromise = this.fetchSessionFromBackend(normalizedThreadId);
    this.threadFetchPromises.set(normalizedThreadId, fetchPromise);

    try {
      return await fetchPromise;
    } finally {
      this.threadFetchPromises.delete(normalizedThreadId);
    }
  }

  markThreadResponseTerminal(threadId: string | null, status: string): void {
    const normalizedThreadId = normalizeThreadId(threadId);
    const normalizedStatus = normalizeTerminalResponseStatus(status);
    if (!normalizedThreadId || !normalizedStatus) {
      return;
    }

    const existing = this.findExistingSession(normalizedThreadId);
    if (!existing) {
      return;
    }

    const existingMessages = Array.isArray(existing.messages) ? existing.messages : [];
    const nextMessages = settleMessagesForTerminalResponse(
      existingMessages,
      normalizedStatus,
      Math.floor(Date.now() / 1000),
    );
    if (nextMessages === existingMessages) {
      return;
    }

    this.cacheSession({
      ...existing,
      messages: nextMessages,
    });
  }

  private async fetchSessionFromBackend(
    threadId: string,
    existingSession: ExtendedSession | null = null,
  ): Promise<IAgentScopeRuntimeWebUISession> {
    let conversation: RuntimeConversation;
    try {
      conversation = await this.fetchRuntimeConversationWithRetry(threadId);
    } catch (error) {
      if (isApiError(error)) {
        const normalizedDetail =
          typeof error.detail === "string" &&
          error.detail.trim() &&
          error.detail.trim().toLowerCase() !== "name"
            ? error.detail.trim()
            : `运行会话不存在或尚未就绪：${threadId}`;
        throw new Error(`[${error.status}] ${normalizedDetail}`);
      }
      throw error;
    }
    let session: ExtendedSession;
    try {
      session = conversationToSession(conversation);
    } catch (error) {
      console.error("Failed to convert runtime conversation:", error);
      session = buildFallbackSessionFromConversation(conversation);
    }
    session = this.mergeFetchedSession(session, existingSession);
    this.preferredThreadId = session.id;
    this.cacheSession(session);
    return session;
  }

  private mergeSessionUpdate(
    session: Partial<IAgentScopeRuntimeWebUISession>,
    existing: ExtendedSession,
  ): ExtendedSession {
    return {
      ...existing,
      id: existing.id,
      name: existing.name,
      threadId: existing.threadId,
      userId: existing.userId,
      channel: existing.channel,
      messages: session.messages || existing.messages || [],
      meta: existing.meta || {},
    };
  }

  async updateSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    const threadId = session.id || this.requireBoundThreadId();
    const existing = await this.resolveSessionSeed(threadId);
    const next = this.mergeSessionUpdate(session, existing);
    this.cacheSession(next);
    return [...this.sessionList];
  }

  async createSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    const threadId = this.requireBoundThreadId();
    const existing = await this.resolveSessionSeed(threadId);
    const next = this.mergeSessionUpdate(
      {
        ...session,
        id: threadId,
      },
      existing,
    );
    Object.assign(session as Partial<ExtendedSession>, next);
    this.cacheSession(next);
    return [...this.sessionList];
  }

  async openBoundThread(payload: BoundThreadPayload): Promise<ExtendedSession> {
    const threadId = normalizeThreadId(payload.threadId);
    const normalizedPayload = {
      ...payload,
      threadId: threadId || payload.threadId,
    };
    const seedSession = buildSeedSessionFromBinding(normalizedPayload);
    this.setPreferredThreadId(normalizedPayload.threadId);
    try {
      return (await this.getSession(normalizedPayload.threadId)) as ExtendedSession;
    } catch (error) {
      if (this.shouldUseSeedSessionFallback(error, seedSession)) {
        this.cacheSession(seedSession as ExtendedSession);
        return seedSession as ExtendedSession;
      }
      this.clearBoundThreadContext(normalizedPayload.threadId);
      this.threadCache.delete(normalizedPayload.threadId);
      this.sessionList = this.sessionList.filter(
        (item) => item.id !== normalizedPayload.threadId,
      );
      if (this.preferredThreadId === normalizedPayload.threadId) {
        this.preferredThreadId = null;
      }
      throw error;
    }
  }

  async removeSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    const threadId = normalizeThreadId(session.id);
    if (!threadId) {
      return [...this.sessionList];
    }

    this.sessionList = this.sessionList.filter((item) => item.id !== threadId);
    this.threadCache.delete(threadId);
    if (this.preferredThreadId === threadId) {
      this.preferredThreadId = this.sessionList[0]?.id || null;
    }
    if (normalizeThreadId(window.currentThreadId) === threadId) {
      const nextThreadId = normalizeThreadId(this.preferredThreadId);
      if (nextThreadId) {
        const replacement =
          this.getCachedSession(nextThreadId) ||
          (this.sessionList.find((item) => item.id === nextThreadId) as
            | ExtendedSession
            | undefined);
        if (replacement) {
          this.updateWindowVariables(replacement);
        } else {
          this.clearBoundThreadContext(threadId);
        }
      } else {
        this.clearBoundThreadContext(threadId);
      }
    }
    return [...this.sessionList];
  }
}

export default new SessionApi();
