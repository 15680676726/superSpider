export type RuntimeSidecarEventName =
  | "turn_reply_done"
  | "commit_started"
  | "confirm_required"
  | "committed"
  | "commit_failed"
  | "commit_deferred";

export type RuntimeSidecarEvent = {
  event: RuntimeSidecarEventName;
  payload: Record<string, unknown>;
};

export type RuntimeCommitStatusKind =
  | "started"
  | "confirm_required"
  | "committed"
  | "governance_denied"
  | "environment_unavailable"
  | "failed"
  | "deferred";

export type RuntimeCommitStatus = {
  kind: RuntimeCommitStatusKind;
  event: RuntimeSidecarEventName;
  title: string;
  summary: string | null;
  reason: string | null;
  decisionIds: string[];
  controlThreadId: string | null;
  updatedAt: number;
  payload: Record<string, unknown>;
};

export type RuntimeSidecarState = {
  controlThreadId: string | null;
  currentCommitStatus: RuntimeCommitStatus | null;
  history: RuntimeCommitStatus[];
  lastReplyDoneAt: number | null;
};

const SIDECAR_EVENTS = new Set<RuntimeSidecarEventName>([
  "turn_reply_done",
  "commit_started",
  "confirm_required",
  "committed",
  "commit_failed",
  "commit_deferred",
]);

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function collectDecisionIds(payload: Record<string, unknown>): string[] {
  const ids = new Set<string>();
  const decisionId = asNonEmptyString(payload.decision_id);
  if (decisionId) {
    ids.add(decisionId);
  }
  const decisionIds = Array.isArray(payload.decision_ids)
    ? payload.decision_ids
    : [];
  for (const item of decisionIds) {
    const normalized = asNonEmptyString(item);
    if (normalized) {
      ids.add(normalized);
    }
  }
  return Array.from(ids);
}

function resolveControlThreadId(
  currentControlThreadId: string | null,
  payload: Record<string, unknown>,
): string | null {
  const explicitControlThreadId = asNonEmptyString(payload.control_thread_id);
  if (explicitControlThreadId) {
    return explicitControlThreadId;
  }
  const threadId = asNonEmptyString(payload.thread_id);
  if (threadId && !threadId.startsWith("task-chat:")) {
    return threadId;
  }
  return currentControlThreadId;
}

function resolveCommitStatusKind(
  event: RuntimeSidecarEventName,
  payload: Record<string, unknown>,
): RuntimeCommitStatusKind | null {
  if (event === "turn_reply_done") {
    return null;
  }
  if (event === "commit_started") {
    return "started";
  }
  if (event === "confirm_required") {
    return "confirm_required";
  }
  if (event === "committed") {
    return "committed";
  }
  if (event === "commit_deferred") {
    return "deferred";
  }
  const reason = asNonEmptyString(payload.reason) ?? asNonEmptyString(payload.outcome);
  if (reason === "governance_denied") {
    return "governance_denied";
  }
  if (reason === "environment_unavailable") {
    return "environment_unavailable";
  }
  return "failed";
}

function resolveCommitStatusTitle(kind: RuntimeCommitStatusKind): string {
  switch (kind) {
    case "started":
      return "提交处理中";
    case "confirm_required":
      return "待确认";
    case "committed":
      return "已提交";
    case "governance_denied":
      return "治理拒绝";
    case "environment_unavailable":
      return "环境不可用";
    case "deferred":
      return "已批准，等待提交";
    case "failed":
    default:
      return "提交失败";
  }
}

function trimHistory(history: RuntimeCommitStatus[]): RuntimeCommitStatus[] {
  return history.slice(-6);
}

export function createInitialRuntimeSidecarState(
  controlThreadId: string | null = null,
): RuntimeSidecarState {
  return {
    controlThreadId,
    currentCommitStatus: null,
    history: [],
    lastReplyDoneAt: null,
  };
}

export function parseRuntimeSidecarEvent(
  value: unknown,
  controlThreadId: string | null = null,
): RuntimeSidecarEvent | null {
  const record = asRecord(value);
  if (!record || record.object === "response") {
    return null;
  }
  const event = asNonEmptyString(record.event);
  if (!event || !SIDECAR_EVENTS.has(event as RuntimeSidecarEventName)) {
    return null;
  }
  const payload = asRecord(record.payload) ?? {};
  const resolvedControlThreadId =
    resolveControlThreadId(controlThreadId, payload) ?? controlThreadId;
  if (resolvedControlThreadId && !payload.control_thread_id) {
    payload.control_thread_id = resolvedControlThreadId;
  }
  return {
    event: event as RuntimeSidecarEventName,
    payload,
  };
}

export function reduceRuntimeSidecarEvent(
  state: RuntimeSidecarState,
  sidecarEvent: RuntimeSidecarEvent,
  now: number = Date.now(),
): RuntimeSidecarState {
  if (sidecarEvent.event === "turn_reply_done") {
    return {
      ...state,
      lastReplyDoneAt: now,
    };
  }

  const controlThreadId = resolveControlThreadId(
    state.controlThreadId,
    sidecarEvent.payload,
  );
  const kind = resolveCommitStatusKind(sidecarEvent.event, sidecarEvent.payload);
  if (!kind) {
    return state;
  }

  const status: RuntimeCommitStatus = {
    kind,
    event: sidecarEvent.event,
    title: resolveCommitStatusTitle(kind),
    summary:
      asNonEmptyString(sidecarEvent.payload.summary) ??
      asNonEmptyString(sidecarEvent.payload.message),
    reason:
      asNonEmptyString(sidecarEvent.payload.reason) ??
      asNonEmptyString(sidecarEvent.payload.outcome),
    decisionIds: collectDecisionIds(sidecarEvent.payload),
    controlThreadId,
    updatedAt: now,
    payload: { ...sidecarEvent.payload },
  };

  return {
    controlThreadId,
    currentCommitStatus: status,
    history: trimHistory([...state.history, status]),
    lastReplyDoneAt: state.lastReplyDoneAt,
  };
}
