export interface RuntimeActorRecord {
  agent_id: string;
  actor_key: string;
  actor_fingerprint?: string | null;
  actor_class?: string | null;
  desired_state: string;
  runtime_status: string;
  activation_mode?: string | null;
  persistent?: boolean;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
  display_name?: string | null;
  role_name?: string | null;
  current_task_id?: string | null;
  current_mailbox_id?: string | null;
  current_environment_id?: string | null;
  queue_depth?: number;
  last_started_at?: string | null;
  last_heartbeat_at?: string | null;
  last_stopped_at?: string | null;
  last_error_summary?: string | null;
  last_result_summary?: string | null;
  last_checkpoint_id?: string | null;
  metadata?: Record<string, unknown>;
  routes?: Record<string, string>;
}

export interface RuntimeActorMailboxItem {
  id: string;
  agent_id: string;
  task_id?: string | null;
  source_agent_id?: string | null;
  title?: string | null;
  summary?: string | null;
  status: string;
  capability_ref?: string | null;
  result_summary?: string | null;
  error_summary?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  route?: string | null;
}

export interface RuntimeActorCheckpointItem {
  id: string;
  agent_id: string;
  mailbox_id?: string | null;
  task_id?: string | null;
  checkpoint_kind?: string | null;
  status: string;
  phase?: string | null;
  summary?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RuntimeActorDetailPayload {
  runtime: RuntimeActorRecord;
  mailbox: RuntimeActorMailboxItem[];
  checkpoints: RuntimeActorCheckpointItem[];
  focus?: RuntimeActorFocusPayload | null;
  teammates?: Array<Record<string, unknown>>;
  stats?: Record<string, unknown>;
}

export interface RuntimeActorTaskReview {
  headline?: string | null;
  objective?: string | null;
  execution_state?: string | null;
  current_stage?: string | null;
  blocked_reason?: string | null;
  stuck_reason?: string | null;
  owner_agent_id?: string | null;
  owner_agent_name?: string | null;
  trigger_source?: string | null;
  trigger_actor?: string | null;
  trigger_reason?: string | null;
  latest_result_summary?: string | null;
  latest_evidence_summary?: string | null;
  next_step?: string | null;
  risks?: string[] | null;
  review_route?: string | null;
}

export interface RuntimeActorFocusPayload {
  task_id?: string | null;
  route?: string | null;
  review?: RuntimeActorTaskReview | null;
}

interface ActorPulseSnapshot {
  taskId: string | null;
  mailboxId: string | null;
  checkpointId: string | null;
  queueDepth: number;
  errorSummary: string | null;
  resultSummary: string | null;
  heartbeatAt: string | null;
  stableSince: number;
}

export interface ActorPulseSignal {
  level: "good" | "watch" | "danger";
  label: string;
  detail: string;
}

export interface ActorPulseItem {
  agentId: string;
  title: string;
  roleName: string | null;
  actorClass: string | null;
  runtimeStatus: string;
  desiredState: string;
  queueDepth: number;
  currentTaskId: string | null;
  currentAssignmentId: string | null;
  currentAssignmentStatus: string | null;
  currentMailboxId: string | null;
  currentEnvironmentId: string | null;
  currentGoal: string | null;
  currentWorkTitle: string | null;
  currentWorkSummary: string | null;
  executionState: string | null;
  currentStage: string | null;
  blockedReason: string | null;
  stuckReason: string | null;
  nextStep: string | null;
  triggerSource: string | null;
  triggerActor: string | null;
  triggerReason: string | null;
  currentOwnerName: string | null;
  latestEvidenceSummary: string | null;
  primaryRisk: string | null;
  latestCheckpointSummary: string | null;
  latestResultSummary: string | null;
  latestErrorSummary: string | null;
  lastHeartbeatAt: string | null;
  lastStartedAt: string | null;
  lastCheckpointId: string | null;
  detailRoute: string;
  signals: ActorPulseSignal[];
  activeMailboxRoute: string | null;
}

const ACTIVE_RUNTIME_STATUSES = new Set([
  "executing",
  "claimed",
  "queued",
  "running",
  "waiting",
  "blocked",
  "paused",
]);

const BUSY_MAILBOX_STATUSES = new Set([
  "queued",
  "leased",
  "running",
  "retry-wait",
  "blocked",
]);

const ACTIVE_CHECKPOINT_STATUSES = new Set(["ready"]);
const ACTIVE_ASSIGNMENT_STATUSES = new Set([
  "planned",
  "queued",
  "running",
  "waiting-report",
]);

interface RuntimeAssignmentSnapshot {
  id: string | null;
  title: string | null;
  summary: string | null;
  status: string | null;
}

function textOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function firstListText(value: unknown): string | null {
  if (!Array.isArray(value)) {
    return null;
  }
  for (const item of value) {
    const resolved = textOrNull(item);
    if (resolved) {
      return resolved;
    }
  }
  return null;
}

function resolveRuntimeAssignment(
  runtime: RuntimeActorRecord,
): RuntimeAssignmentSnapshot {
  const metadata = runtime.metadata as Record<string, unknown> | undefined;
  return {
    id: textOrNull(metadata?.current_assignment_id),
    title: textOrNull(metadata?.current_assignment_title),
    summary: textOrNull(metadata?.current_assignment_summary),
    status: textOrNull(metadata?.current_assignment_status),
  };
}

function hasActiveRuntimeAssignment(runtime: RuntimeActorRecord): boolean {
  const assignment = resolveRuntimeAssignment(runtime);
  return Boolean(
    assignment.id ||
      (assignment.status && ACTIVE_ASSIGNMENT_STATUSES.has(assignment.status)),
  );
}

function parseTime(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function pickActiveMailbox(
  detail: RuntimeActorDetailPayload,
): RuntimeActorMailboxItem | null {
  const runtime = detail.runtime;
  return (
    detail.mailbox.find(
      (item) =>
        item.id === runtime.current_mailbox_id &&
        BUSY_MAILBOX_STATUSES.has(item.status),
    ) ||
    detail.mailbox.find((item) => BUSY_MAILBOX_STATUSES.has(item.status)) ||
    null
  );
}

function pickLatestCheckpoint(
  detail: RuntimeActorDetailPayload,
): RuntimeActorCheckpointItem | null {
  const runtime = detail.runtime;
  return (
    detail.checkpoints.find(
      (item) =>
        item.id === runtime.last_checkpoint_id &&
        ACTIVE_CHECKPOINT_STATUSES.has(item.status),
    ) ||
    detail.checkpoints.find((item) =>
      ACTIVE_CHECKPOINT_STATUSES.has(item.status),
    ) ||
    null
  );
}

function repeatedError(detail: RuntimeActorDetailPayload): string | null {
  const counts = new Map<string, number>();
  for (const item of detail.mailbox.slice(0, 8)) {
    const key = textOrNull(item.error_summary);
    if (!key) {
      continue;
    }
    counts.set(key, (counts.get(key) || 0) + 1);
    if ((counts.get(key) || 0) >= 2) {
      return key;
    }
  }
  return null;
}

function buildSignals(
  detail: RuntimeActorDetailPayload,
  snapshot: ActorPulseSnapshot,
  previous: ActorPulseSnapshot | null,
  nowMs: number,
): ActorPulseSignal[] {
  const runtime = detail.runtime;
  const activeMailbox = pickActiveMailbox(detail);
  const checkpoint = pickLatestCheckpoint(detail);
  const assignment = resolveRuntimeAssignment(runtime);
  const signals: ActorPulseSignal[] = [];
  const heartbeatAt = parseTime(runtime.last_heartbeat_at);
  const heartbeatAgeMs = heartbeatAt === null ? null : Math.max(0, nowMs - heartbeatAt);
  const noProgressMs = nowMs - snapshot.stableSince;
  const sameCheckpoint =
    previous !== null &&
    previous.taskId === snapshot.taskId &&
    previous.mailboxId === snapshot.mailboxId &&
    previous.checkpointId === snapshot.checkpointId &&
    previous.errorSummary === snapshot.errorSummary &&
    previous.resultSummary === snapshot.resultSummary &&
    previous.queueDepth === snapshot.queueDepth;

  if (runtime.desired_state === "paused" || runtime.runtime_status === "paused") {
    signals.push({
      level: "watch",
      label: "已暂停",
      detail: "该执行位当前处于暂停态，不会继续处理新的 mailbox 任务。",
    });
    return signals;
  }

  if (runtime.runtime_status === "blocked" || activeMailbox?.status === "blocked") {
    signals.push({
      level: "watch",
      label: "等待确认",
      detail:
        textOrNull(runtime.last_error_summary) ||
        textOrNull(activeMailbox?.error_summary) ||
        textOrNull(checkpoint?.summary) ||
        "任务被治理或确认流拦住，正在等待外部确认。",
    });
  }

  if (heartbeatAgeMs !== null && heartbeatAgeMs > 3 * 60 * 1000 && snapshot.taskId) {
    signals.push({
      level: "danger",
      label: "心跳过久未更新",
      detail: "当前仍挂着任务，但最近 3 分钟没有新的运行心跳，疑似卡住。",
    });
  }

  const loopedError = repeatedError(detail);
  if (loopedError) {
    signals.push({
      level: "danger",
      label: "重复报错",
      detail: `最近多次出现同一错误：${loopedError}`,
    });
  }

  if (snapshot.errorSummary && noProgressMs > 90 * 1000 && sameCheckpoint) {
    signals.push({
      level: "danger",
      label: "报错后无进展",
      detail: "最近一次错误后超过 90 秒没有看到新的检查点、结果或队列变化。",
    });
  }

  if (snapshot.taskId && noProgressMs > 2 * 60 * 1000 && sameCheckpoint && !snapshot.errorSummary) {
    signals.push({
      level: "watch",
      label: "疑似空转",
      detail: "当前任务超过 2 分钟没有新的检查点、结果或队列变化，建议检查是否在做无效重复动作。",
    });
  }

  if (signals.length === 0 && (snapshot.taskId || snapshot.queueDepth > 0)) {
    const checkpointSummary =
      textOrNull(checkpoint?.summary) ||
      textOrNull(runtime.last_result_summary) ||
      textOrNull(activeMailbox?.summary);
    if (runtime.runtime_status === "claimed" || activeMailbox?.status === "leased") {
      signals.push({
        level: "good",
        label: "已认领",
        detail: checkpointSummary || "当前任务已经被执行位认领，正在拉起正式执行。",
      });
    } else if (
      runtime.runtime_status === "queued" ||
      activeMailbox?.status === "queued" ||
      activeMailbox?.status === "retry-wait" ||
      snapshot.queueDepth > 0
    ) {
      signals.push({
        level: "watch",
        label: "排队中",
        detail: checkpointSummary || "当前任务已经入队，但还没有被 mailbox claim，不应视为正在执行。",
      });
    } else {
      signals.push({
        level: "good",
        label: "执行中",
        detail: checkpointSummary || "当前执行位正在推进任务，暂未发现明显卡死或空转信号。",
      });
    }
  }

  if (
    signals.length === 0 &&
    assignment.id &&
    assignment.status &&
    ACTIVE_ASSIGNMENT_STATUSES.has(assignment.status)
  ) {
    signals.push({
      level: "watch",
      label: assignment.status === "waiting-report" ? "待回报" : "已分配",
      detail:
        assignment.summary ||
        assignment.title ||
        "主脑已经把当前派单挂到这个执行位，但还没有 mailbox claim，不应显示成正在干活。",
    });
  }

  if (signals.length === 0) {
    signals.push({
      level: "good",
      label: "空闲",
      detail: "当前没有挂着执行中的任务或排队邮箱项。",
    });
  }

  return signals;
}

export function isInterestingActor(runtime: RuntimeActorRecord): boolean {
  return Boolean(
    runtime.queue_depth ||
      textOrNull(runtime.current_task_id) ||
      ACTIVE_RUNTIME_STATUSES.has(runtime.runtime_status) ||
      hasActiveRuntimeAssignment(runtime) ||
      textOrNull(runtime.last_error_summary),
  );
}

export function compareActorPriority(
  left: RuntimeActorRecord,
  right: RuntimeActorRecord,
): number {
  const leftBusy =
    Number(Boolean(left.current_task_id)) +
    (left.queue_depth || 0) +
    Number(hasActiveRuntimeAssignment(left)) +
    Number(ACTIVE_RUNTIME_STATUSES.has(left.runtime_status));
  const rightBusy =
    Number(Boolean(right.current_task_id)) +
    (right.queue_depth || 0) +
    Number(hasActiveRuntimeAssignment(right)) +
    Number(ACTIVE_RUNTIME_STATUSES.has(right.runtime_status));
  if (leftBusy !== rightBusy) {
    return rightBusy - leftBusy;
  }
  const leftHeartbeat = parseTime(left.last_heartbeat_at) || 0;
  const rightHeartbeat = parseTime(right.last_heartbeat_at) || 0;
  if (leftHeartbeat !== rightHeartbeat) {
    return rightHeartbeat - leftHeartbeat;
  }
  return (right.last_started_at || "").localeCompare(left.last_started_at || "");
}

export function buildActorPulseItems(
  details: RuntimeActorDetailPayload[],
  previousSnapshots: Map<string, ActorPulseSnapshot>,
  nowMs: number,
): {
  items: ActorPulseItem[];
  snapshots: Map<string, ActorPulseSnapshot>;
} {
  const nextSnapshots = new Map<string, ActorPulseSnapshot>();
  const items = details
    .map((detail) => {
      const runtime = detail.runtime;
      const activeMailbox = pickActiveMailbox(detail);
      const checkpoint = pickLatestCheckpoint(detail);
      const focusReview = detail.focus?.review ?? null;
      const assignment = resolveRuntimeAssignment(runtime);
      const previous = previousSnapshots.get(runtime.agent_id) || null;
      const snapshotBase = {
        taskId:
          textOrNull(detail.focus?.task_id) ||
          textOrNull(runtime.current_task_id) ||
          textOrNull(activeMailbox?.task_id),
        mailboxId: textOrNull(runtime.current_mailbox_id) || textOrNull(activeMailbox?.id),
        checkpointId: textOrNull(runtime.last_checkpoint_id) || textOrNull(checkpoint?.id),
        queueDepth: Number(runtime.queue_depth || 0),
        errorSummary:
          textOrNull(runtime.last_error_summary) ||
          textOrNull(activeMailbox?.error_summary),
        resultSummary:
          textOrNull(runtime.last_result_summary) ||
          textOrNull(activeMailbox?.result_summary) ||
          textOrNull(checkpoint?.summary),
        heartbeatAt: textOrNull(runtime.last_heartbeat_at),
      };
      const snapshot: ActorPulseSnapshot =
        previous &&
        previous.taskId === snapshotBase.taskId &&
        previous.mailboxId === snapshotBase.mailboxId &&
        previous.checkpointId === snapshotBase.checkpointId &&
        previous.queueDepth === snapshotBase.queueDepth &&
        previous.errorSummary === snapshotBase.errorSummary &&
        previous.resultSummary === snapshotBase.resultSummary
          ? { ...snapshotBase, stableSince: previous.stableSince }
          : { ...snapshotBase, stableSince: nowMs };
      nextSnapshots.set(runtime.agent_id, snapshot);

      const metadata = runtime.metadata || {};
      const currentGoal =
        textOrNull(metadata.current_focus) ||
        textOrNull(metadata.goal_title) ||
        textOrNull(focusReview?.objective) ||
        assignment.title ||
        textOrNull(metadata.current_focus_id) ||
        textOrNull(metadata.goal_id);
      const item: ActorPulseItem = {
        agentId: runtime.agent_id,
        title:
          textOrNull(runtime.display_name) ||
          textOrNull((metadata as Record<string, unknown>).name) ||
          runtime.agent_id,
        roleName: textOrNull(runtime.role_name),
        actorClass: textOrNull(runtime.actor_class),
        runtimeStatus: runtime.runtime_status || "idle",
        desiredState: runtime.desired_state || "active",
        queueDepth: Number(runtime.queue_depth || 0),
        currentTaskId: snapshot.taskId,
        currentAssignmentId: assignment.id,
        currentAssignmentStatus: assignment.status,
        currentMailboxId: snapshot.mailboxId,
        currentEnvironmentId: textOrNull(runtime.current_environment_id),
        currentGoal,
        currentWorkTitle:
          textOrNull(focusReview?.objective) ||
          assignment.title ||
          textOrNull(activeMailbox?.title) ||
          textOrNull(activeMailbox?.summary) ||
          snapshot.taskId,
        currentWorkSummary:
          textOrNull(focusReview?.headline) ||
          assignment.summary ||
          textOrNull(activeMailbox?.summary) ||
          textOrNull(checkpoint?.summary) ||
          textOrNull(focusReview?.latest_result_summary) ||
          textOrNull(runtime.last_result_summary) ||
          textOrNull(runtime.last_error_summary),
        executionState: textOrNull(focusReview?.execution_state),
        currentStage: textOrNull(focusReview?.current_stage),
        blockedReason: textOrNull(focusReview?.blocked_reason),
        stuckReason: textOrNull(focusReview?.stuck_reason),
        nextStep: textOrNull(focusReview?.next_step),
        triggerSource: textOrNull(focusReview?.trigger_source),
        triggerActor: textOrNull(focusReview?.trigger_actor),
        triggerReason: textOrNull(focusReview?.trigger_reason),
        currentOwnerName: textOrNull(focusReview?.owner_agent_name),
        latestEvidenceSummary: textOrNull(focusReview?.latest_evidence_summary),
        primaryRisk: firstListText(focusReview?.risks),
        latestCheckpointSummary:
          textOrNull(checkpoint?.summary) ||
          textOrNull(checkpoint?.phase) ||
          null,
        latestResultSummary: textOrNull(runtime.last_result_summary),
        latestErrorSummary: textOrNull(runtime.last_error_summary),
        lastHeartbeatAt: textOrNull(runtime.last_heartbeat_at),
        lastStartedAt: textOrNull(runtime.last_started_at),
        lastCheckpointId: textOrNull(runtime.last_checkpoint_id),
        detailRoute:
          textOrNull(runtime.routes?.detail) ||
          `/api/runtime-center/actors/${encodeURIComponent(runtime.agent_id)}`,
        signals: buildSignals(detail, snapshot, previous, nowMs),
        activeMailboxRoute: textOrNull(activeMailbox?.route),
      };
      return item;
    })
    .sort((left, right) => {
      const score = (item: ActorPulseItem) => {
        const severity = item.signals.some((signal) => signal.level === "danger")
          ? 3
          : item.signals.some((signal) => signal.level === "watch")
            ? 2
            : item.currentTaskId || item.queueDepth > 0
              ? 1
              : 0;
        return severity * 1000 + item.queueDepth * 10 + Number(Boolean(item.currentTaskId));
      };
      return score(right) - score(left);
    });
  return { items, snapshots: nextSnapshots };
}
