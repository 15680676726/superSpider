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

export type RuntimeIntentShellMode = "plan" | "review" | "resume" | "verify";

export type RuntimeIntentShellSurface = {
  mode: RuntimeIntentShellMode;
  label: string;
  summary: string | null;
  hint: string | null;
  triggerSource: string | null;
  matchedText: string | null;
  confidence: number | null;
  triggerSourceLabel: string | null;
  matchedTextLabel: string | null;
  confidenceLabel: string | null;
  metaSummary: string | null;
  updatedAt: number;
  payload: Record<string, unknown>;
};

export type RuntimeSidecarState = {
  controlThreadId: string | null;
  currentCommitStatus: RuntimeCommitStatus | null;
  currentIntentShell: RuntimeIntentShellSurface | null;
  history: RuntimeCommitStatus[];
  lastReplyDoneAt: number | null;
  lastTerminalResponseAt: number | null;
};

const SIDECAR_EVENTS = new Set<RuntimeSidecarEventName>([
  "turn_reply_done",
  "commit_started",
  "confirm_required",
  "committed",
  "commit_failed",
  "commit_deferred",
]);

const PERSISTED_COMMIT_STATUS_TO_EVENT: Record<string, RuntimeSidecarEventName> = {
  confirm_required: "confirm_required",
  committed: "committed",
  commit_failed: "commit_failed",
  governance_denied: "commit_failed",
  commit_deferred: "commit_deferred",
};

const COMMIT_STATUS_TITLES: Record<RuntimeCommitStatusKind, string> = {
  started: "\u63d0\u4ea4\u5904\u7406\u4e2d",
  confirm_required: "\u5f85\u786e\u8ba4",
  committed: "\u5df2\u63d0\u4ea4",
  governance_denied: "\u6cbb\u7406\u62d2\u7edd",
  environment_unavailable: "\u73af\u5883\u4e0d\u53ef\u7528",
  failed: "\u63d0\u4ea4\u5931\u8d25",
  deferred: "\u5f85\u8c03\u5ea6",
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function compactPayload(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => {
      if (value === null || value === undefined) {
        return false;
      }
      if (typeof value === "string") {
        return value.trim().length > 0;
      }
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return true;
    }),
  );
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

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveIntentShellTriggerSourceLabel(
  triggerSource: string | null,
): string | null {
  if (!triggerSource) {
    return null;
  }
  if (triggerSource === "request") {
    return "\u6765\u6e90\uff1a\u663e\u5f0f\u6a21\u5f0f";
  }
  if (triggerSource === "keyword") {
    return "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d";
  }
  if (triggerSource === "attached") {
    return "\u6765\u6e90\uff1a\u9644\u5e26\u4e0a\u4e0b\u6587";
  }
  return "\u6765\u6e90\uff1a\u6a21\u5f0f\u89e6\u53d1";
}

function resolveIntentShellMatchedTextLabel(
  matchedText: string | null,
): string | null {
  return matchedText ? `\u547d\u4e2d\uff1a${matchedText}` : null;
}

function resolveIntentShellConfidenceLabel(
  confidence: number | null,
): string | null {
  if (typeof confidence !== "number") {
    return null;
  }
  const percent = Math.max(0, Math.min(100, Math.round(confidence * 100)));
  return `\u7f6e\u4fe1\u5ea6 ${percent}%`;
}

function joinIntentShellParts(parts: Array<string | null>): string | null {
  const values = parts.filter(
    (part): part is string => typeof part === "string" && part.trim().length > 0,
  );
  return values.length > 0 ? values.join(" \u00b7 ") : null;
}

export function formatRuntimeIntentShellSidebarHint(
  shell: Pick<RuntimeIntentShellSurface, "label" | "summary" | "metaSummary"> | null,
): string | null {
  if (!shell) {
    return null;
  }
  return (
    joinIntentShellParts([
      shell.summary ?? `Mode: ${shell.label}`,
      shell.metaSummary,
    ]) ??
    shell.summary ??
    `Mode: ${shell.label}`
  );
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
  const reason =
    asNonEmptyString(payload.reason) ?? asNonEmptyString(payload.outcome);
  if (reason === "governance_denied") {
    return "governance_denied";
  }
  if (reason === "environment_unavailable") {
    return "environment_unavailable";
  }
  return "failed";
}

function resolveCommitStatusTitle(kind: RuntimeCommitStatusKind): string {
  return COMMIT_STATUS_TITLES[kind];
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => asNonEmptyString(item))
    .filter((item): item is string => typeof item === "string");
}

export function resolveDeferredCommitPresentation(payload: Record<string, unknown>): {
  title: string;
  summary: string | null;
} {
  const summary =
    asNonEmptyString(payload.summary) ?? asNonEmptyString(payload.message);
  const delegationState = asNonEmptyString(payload.delegation_state);
  const reason = asNonEmptyString(payload.reason) ?? asNonEmptyString(payload.outcome);
  const seatResolutionKind = asNonEmptyString(payload.seat_resolution_kind);
  const proposalStatus = asNonEmptyString(payload.proposal_status);
  const materializedAssignmentIds = asStringArray(payload.materialized_assignment_ids);
  const createdBacklogIds = asStringArray(payload.created_backlog_ids);

  if (
    delegationState === "waiting_confirm" ||
    delegationState === "waiting-confirm" ||
    reason === "waiting_confirm" ||
    reason === "confirm_required" ||
    proposalStatus === "waiting_confirm" ||
    proposalStatus === "waiting-confirm"
  ) {
    return {
      title: "\u5f85\u786e\u8ba4",
      summary,
    };
  }

  if (
    delegationState === "pending_staffing" ||
    delegationState === "routing-pending" ||
    reason === "pending_staffing" ||
    seatResolutionKind === "routing-pending"
  ) {
    return {
      title: "\u5f85\u8865\u4f4d",
      summary,
    };
  }

  if (
    delegationState === "materialized" ||
    materializedAssignmentIds.length > 0
  ) {
    return {
      title: "\u5df2\u751f\u6210\u4efb\u52a1",
      summary,
    };
  }

  if (delegationState === "recorded" || createdBacklogIds.length > 0) {
    return {
      title: "\u5df2\u8bb0\u5f55",
      summary,
    };
  }

  return {
    title: resolveCommitStatusTitle("deferred"),
    summary,
  };
}

function trimHistory(history: RuntimeCommitStatus[]): RuntimeCommitStatus[] {
  return history.slice(-6);
}

function buildRuntimeSidecarPayload(
  record: Record<string, unknown>,
  status: string | null,
): Record<string, unknown> {
  const payload = { ...(asRecord(record.payload) ?? {}) };
  const extras: Record<string, unknown> = {
    control_thread_id: record.control_thread_id,
    thread_id: record.thread_id,
    session_id: record.session_id,
    summary: record.summary,
    reason:
      record.reason ??
      (status === "governance_denied" ? "governance_denied" : undefined),
    message: record.message,
    decision_id: record.decision_id,
    decision_ids: record.decision_ids,
    record_id: record.record_id,
    action_type: record.action_type,
    risk_level: record.risk_level,
    work_context_id: record.work_context_id,
    commit_key: record.commit_key,
    recovery_options: record.recovery_options,
    idempotent_replay: record.idempotent_replay,
    delegation_state: record.delegation_state,
    created_backlog_ids: record.created_backlog_ids,
    materialized_assignment_ids: record.materialized_assignment_ids,
    materialized_cycle_id: record.materialized_cycle_id,
    seat_resolution_kind: record.seat_resolution_kind,
    proposal_status: record.proposal_status,
  };
  for (const [key, value] of Object.entries(extras)) {
    if (value !== undefined) {
      payload[key] = value;
    }
  }
  return compactPayload(payload);
}

export function createInitialRuntimeSidecarState(
  controlThreadId: string | null = null,
): RuntimeSidecarState {
  return {
    controlThreadId,
    currentCommitStatus: null,
    currentIntentShell: null,
    history: [],
    lastReplyDoneAt: null,
    lastTerminalResponseAt: null,
  };
}

export function markRuntimeResponseTerminal(
  state: RuntimeSidecarState,
  now: number = Date.now(),
): RuntimeSidecarState {
  return {
    ...state,
    lastTerminalResponseAt: now,
  };
}

function resolveIntentShellSurface(
  payload: Record<string, unknown>,
  now: number,
): RuntimeIntentShellSurface | null {
  const shell = asRecord(payload.intent_shell);
  if (!shell) {
    return null;
  }
  const mode = asNonEmptyString(shell.mode_hint);
  if (
    mode !== "plan" &&
    mode !== "review" &&
    mode !== "resume" &&
    mode !== "verify"
  ) {
    return null;
  }
  const triggerSource = asNonEmptyString(shell.trigger_source);
  const matchedText = asNonEmptyString(shell.matched_text);
  const confidence = asNumber(shell.confidence);
  const triggerSourceLabel = resolveIntentShellTriggerSourceLabel(triggerSource);
  const matchedTextLabel = resolveIntentShellMatchedTextLabel(matchedText);
  const confidenceLabel = resolveIntentShellConfidenceLabel(confidence);
  return {
    mode,
    label: asNonEmptyString(shell.label) ?? mode.toUpperCase(),
    summary: asNonEmptyString(shell.summary),
    hint: asNonEmptyString(shell.hint),
    triggerSource,
    matchedText,
    confidence,
    triggerSourceLabel,
    matchedTextLabel,
    confidenceLabel,
    metaSummary: joinIntentShellParts([
      triggerSourceLabel,
      matchedTextLabel,
      confidenceLabel,
    ]),
    updatedAt: now,
    payload: compactPayload({ ...shell }),
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
  const status = asNonEmptyString(record.status);
  const event =
    asNonEmptyString(record.event ?? record.sidecar_event) ??
    (status ? PERSISTED_COMMIT_STATUS_TO_EVENT[status] : null);
  if (!event || !SIDECAR_EVENTS.has(event as RuntimeSidecarEventName)) {
    return null;
  }
  const payload = buildRuntimeSidecarPayload(record, status);
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
      currentIntentShell: resolveIntentShellSurface(sidecarEvent.payload, now),
      lastReplyDoneAt: now,
      lastTerminalResponseAt: state.lastTerminalResponseAt,
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
  const deferredPresentation =
    kind === "deferred"
      ? resolveDeferredCommitPresentation(sidecarEvent.payload)
      : null;

  const status: RuntimeCommitStatus = {
    kind,
    event: sidecarEvent.event,
    title: deferredPresentation?.title ?? resolveCommitStatusTitle(kind),
    summary:
      deferredPresentation?.summary ??
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
    currentIntentShell: state.currentIntentShell,
    history: trimHistory([...state.history, status]),
    lastReplyDoneAt: state.lastReplyDoneAt,
    lastTerminalResponseAt: state.lastTerminalResponseAt,
  };
}

export function hydrateRuntimeSidecarState(
  persistedCommit: unknown,
  controlThreadId: string | null = null,
  now: number = Date.now(),
): RuntimeSidecarState {
  const initialState = createInitialRuntimeSidecarState(controlThreadId);
  const sidecarEvent = parseRuntimeSidecarEvent(
    persistedCommit,
    controlThreadId,
  );
  if (!sidecarEvent) {
    return initialState;
  }
  const hydratedControlThreadId = resolveControlThreadId(
    controlThreadId,
    sidecarEvent.payload,
  );
  if (
    controlThreadId &&
    hydratedControlThreadId &&
    hydratedControlThreadId !== controlThreadId
  ) {
    return initialState;
  }
  return reduceRuntimeSidecarEvent(initialState, sidecarEvent, now);
}
