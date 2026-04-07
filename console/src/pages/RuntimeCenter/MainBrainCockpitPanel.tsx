import { Alert, Button, Card, Descriptions, Skeleton, Space, Tag, Typography } from "antd";
import {
  Activity,
  Bot,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  presentBuddyMoodLabel,
  presentBuddyStageLabel,
} from "../Chat/buddyPresentation";

import { surfaceTagColor } from "./viewHelpers";
import styles from "./index.module.less";
import {
  MAIN_BRAIN_COCKPIT_TEXT,
  RUNTIME_CENTER_TEXT,
  formatCnTimestamp,
  formatMainBrainSignalLabel,
  formatRuntimeFieldLabel,
  formatRuntimeSourceList,
  formatRuntimeStatus,
  formatRuntimeSurfaceNote,
  localizeRuntimeText,
} from "./text";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
import { isRecord } from "./runtimeDetailPrimitives";
import {
  recordList,
  renderCognitionBlock,
  renderCompactRecordList,
  renderOperatorBlock,
  renderTraceBlock,
} from "./mainBrainCockpitSections";
import {
  type RuntimeCockpitSignal,
} from "./runtimeIndustrySections";
import type {
  RuntimeMainBrainBuddySummary,
  RuntimeMainBrainEnvironment,
  RuntimeMainBrainQueryRuntimeEntropy,
  RuntimeMainBrainRecord,
  RuntimeMainBrainResponse,
  RuntimeMainBrainSection,
} from "../../api/modules/runtimeCenter";

type MainBrainCockpitPanelProps = {
  data: RuntimeCenterOverviewPayload | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  buddySummary: RuntimeMainBrainBuddySummary | null;
  mainBrainData: RuntimeMainBrainResponse | null;
  mainBrainLoading: boolean;
  mainBrainError: string | null;
  mainBrainUnavailable: boolean;
  onRefresh: () => void;
  onOpenRoute: (route: string, title: string) => void;
};

const SIGNAL_ICONS: Record<string, ReactNode> = {
  carrier: <Activity size={18} color="#1B4FD8" />,
  strategy: <Waypoints size={18} color="#C9A84C" />,
  lanes: <Waypoints size={18} color="#1B4FD8" />,
  backlog: <Waypoints size={18} color="#1B4FD8" />,
  current_cycle: <RotateCcw size={18} color="#C9A84C" />,
  assignments: <Bot size={18} color="#10b981" />,
  exception_absorption: <ShieldAlert size={18} color="#f97316" />,
  agent_reports: <Bot size={18} color="#10b981" />,
  report_cognition: <ShieldAlert size={18} color="#f97316" />,
  environment: <ShieldCheck size={18} color="#10b981" />,
  governance: <ShieldAlert size={18} color="#f43f5e" />,
  automation: <RotateCcw size={18} color="#1B4FD8" />,
  recovery: <RefreshCw size={18} color="#C9A84C" />,
  evidence: <Activity size={18} color="#1B4FD8" />,
  decisions: <ShieldAlert size={18} color="#f43f5e" />,
  patches: <RotateCcw size={18} color="#f97316" />,
};

const { Text } = Typography;

function stringOrNumber(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function toneFromStatus(value: unknown): RuntimeCockpitSignal["tone"] {
  if (typeof value !== "string") {
    return "default";
  }
  const normalized = value.trim().toLowerCase();
  if (
    ["state-service", "success", "ready", "active", "clear", "proceed", "ok"].some(
      (token) => normalized.includes(token),
    )
  ) {
    return "success";
  }
  if (
    ["degraded", "warning", "caution", "pending"].some((token) =>
      normalized.includes(token),
    )
  ) {
    return "warning";
  }
  if (
    ["blocked", "error", "danger", "retry"].some((token) =>
      normalized.includes(token),
    )
  ) {
    return "danger";
  }
  return "default";
}

function cardStatusFromValue(value: unknown): "state-service" | "degraded" | "unavailable" {
  if (typeof value !== "string") {
    return "unavailable";
  }
  const normalized = value.trim().toLowerCase();
  if (
    ["state-service", "success", "ready", "active", "clear", "proceed", "ok", "available"].some(
      (token) => normalized.includes(token),
    )
  ) {
    return "state-service";
  }
  if (
    ["degraded", "warning", "caution", "pending", "blocked", "error", "danger", "retry"].some(
      (token) => normalized.includes(token),
    )
  ) {
    return "degraded";
  }
  return "unavailable";
}

function detailFromSignal(record: RuntimeMainBrainRecord): string | null {
  const value = firstString(
    record.detail,
    record.note,
    record.summary,
    record.description,
    record.reason,
    record.status,
  );
  return value ? localizeRuntimeText(value) : null;
}

function routeFromSignal(record: RuntimeMainBrainRecord): string | null {
  return (
    stringOrNumber(record.route) ??
    stringOrNumber(record.route_title) ??
    stringOrNumber(record.routeTitle)
  );
}

function routeTitleFromSignal(record: RuntimeMainBrainRecord): string | null {
  return stringOrNumber(record.route_title) ?? stringOrNumber(record.routeTitle);
}

function valueFromSignal(record: RuntimeMainBrainRecord): string {
  const value =
    firstString(
      record.value,
      record.count,
      record.title,
      record.summary,
      record.label,
      record.status,
      record.total,
    ) ?? RUNTIME_CENTER_TEXT.emptyValue;
  return value === RUNTIME_CENTER_TEXT.emptyValue
    ? value
    : localizeRuntimeText(value);
}

function convertDedicatedSignal(
  key: string,
  data: unknown,
): RuntimeCockpitSignal {
  const record = isRecord(data) ? (data as RuntimeMainBrainRecord) : {};
  const tone =
    typeof record.tone === "string"
      ? (record.tone as RuntimeCockpitSignal["tone"])
      : toneFromStatus(record.status ?? record.summary ?? record.value);
  return {
    key,
    label: formatMainBrainSignalLabel(key),
    value: valueFromSignal(record),
    detail: detailFromSignal(record),
    route: routeFromSignal(record),
    routeTitle: routeTitleFromSignal(record),
    tone,
  };
}

function buildDedicatedSignals(payload: RuntimeMainBrainResponse | null): RuntimeCockpitSignal[] {
  if (!payload?.signals) {
    return [];
  }
  return Object.entries(payload.signals).map(([key, value]) =>
    convertDedicatedSignal(key, value),
  );
}

function buildDedicatedChainSignals(
  payload: RuntimeMainBrainResponse | null,
): RuntimeCockpitSignal[] | null {
  const chain = payload?.meta.control_chain;
  if (!chain || chain.length === 0) {
    return null;
  }
  const signals = chain.map((item) => convertDedicatedSignal(item.key, item));
  return signals.length > 0 ? signals : null;
}

function signalToneColor(signal: RuntimeCockpitSignal): string {
  switch (signal.tone) {
    case "success":
      return "success";
    case "warning":
      return "warning";
    case "danger":
      return "error";
    default:
      return "default";
  }
}

function signalIcon(signal: RuntimeCockpitSignal): ReactNode {
  return SIGNAL_ICONS[signal.key] ?? <Activity size={18} color="#1B4FD8" />;
}

function renderSignalCard(
  signal: RuntimeCockpitSignal,
  onOpenRoute: (route: string, title: string) => void,
) {
  return (
    <Card key={signal.key} className={styles.metricCard} style={{ padding: "12px" }}>
      <div className={styles.metricIcon}>{signalIcon(signal)}</div>
      <div className={styles.metricLabel}>{signal.label}</div>
      <div className={styles.metricValueSmall}>{signal.value}</div>
      {signal.detail ? (
        <div className={styles.selectionSummary}>{signal.detail}</div>
      ) : null}
      <Space size={8} wrap style={{ marginTop: 12 }}>
        <Tag color={signalToneColor(signal)}>{signal.label}</Tag>
        {signal.route ? (
          <Button
            size="small"
            aria-label={`打开${signal.label}详情`}
            onClick={() => {
              onOpenRoute(signal.route!, signal.routeTitle || signal.label);
            }}
          >
            打开详情
          </Button>
        ) : null}
      </Space>
    </Card>
  );
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
    if (isRecord(value)) {
      const nested = firstString(
        value.title,
        value.name,
        value.label,
        value.summary,
        value.value,
        value.status,
        value.count,
        value.total,
      );
      if (nested) {
        return nested;
      }
    }
  }
  return null;
}

function presentRecoveryAbsorptionActionKind(value: unknown): string | null {
  const normalized = firstString(value)?.toLowerCase();
  if (!normalized) {
    return null;
  }
  switch (normalized) {
    case "human-assist":
      return "人协动作";
    case "replan":
      return "正式重规划";
    default:
      return normalized;
  }
}

function presentRecoveryAbsorptionMaterialized(value: unknown): string | null {
  if (typeof value !== "boolean") {
    return null;
  }
  return value ? "已物化" : "未物化";
}

function presentRecoveryReplanDecisionKind(value: unknown): string | null {
  const normalized = firstString(value)?.toLowerCase();
  if (!normalized) {
    return null;
  }
  switch (normalized) {
    case "cycle_rebalance":
      return "周期重平衡";
    case "lane_reweight":
      return "泳道再权衡";
    case "follow_up_backlog":
      return "转后续待办";
    default:
      return normalized;
  }
}

function extractTimestamp(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (isRecord(value)) {
    return firstString(
      value.next_cycle_due_at,
      value.deadline_at,
      value.deadline,
      value.due_at,
      value.until,
      value.ends_at,
      value.end_at,
      value.updated_at,
      value.created_at,
    );
  }
  return null;
}

function extractRecordTimestamp(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (isRecord(value)) {
    return firstString(
      value.completed_at,
      value.recorded_at,
      value.decided_at,
      value.applied_at,
      value.closed_at,
      value.resolved_at,
      value.finished_at,
      value.verified_at,
      value.submitted_at,
      value.started_at,
      value.updated_at,
      value.created_at,
      value.generated_at,
    );
  }
  return null;
}

function utcDayKey(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString().slice(0, 10);
}

function sliceRecordsForGeneratedDay(
  records: RuntimeMainBrainRecord[],
  generatedAt: string | null,
): { records: RuntimeMainBrainRecord[]; hasTimestampEvidence: boolean } {
  const anchorDay = utcDayKey(generatedAt);
  if (!anchorDay) {
    return { records: [], hasTimestampEvidence: false };
  }
  let hasTimestampEvidence = false;
  const scopedRecords = records.filter((record) => {
    const recordDay = utcDayKey(extractRecordTimestamp(record));
    if (!recordDay) {
      return false;
    }
    hasTimestampEvidence = true;
    return recordDay === anchorDay;
  });
  return { records: scopedRecords, hasTimestampEvidence };
}

function scopeTraceSectionToGeneratedDay(
  section: RuntimeMainBrainSection | null,
  generatedAt: string | null,
  emptySummary: string,
): RuntimeMainBrainSection | null {
  if (!section) {
    return null;
  }
  const entries = recordList(section.entries);
  const scoped = sliceRecordsForGeneratedDay(entries, generatedAt);
  if (scoped.records.length === 0) {
    return {
      ...section,
      count: 0,
      summary: emptySummary,
      entries: [],
    };
  }
  return {
    ...section,
    count: scoped.records.length,
    entries: scoped.records,
  };
}

function formatUtcMinute(value: string | null): string {
  if (!value) {
    return RUNTIME_CENTER_TEXT.emptyValue;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  // Stable formatting for operator top bar (avoid locale + timezone drift in tests).
  return `${parsed.toISOString().slice(0, 16).replace("T", " ")}Z`;
}

function formatContinuityState(value: unknown): string | null {
  const normalized = firstString(value)?.toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === "ready") return "已就绪";
  if (normalized === "guarded") return "受守护";
  if (normalized === "blocked") return "受阻";
  return firstString(value);
}

function extractFocusCount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (!isRecord(value)) {
    return null;
  }
  const numeric =
    (typeof value.focus_count === "number" ? value.focus_count : null) ??
    (typeof value.current_focus_count === "number" ? value.current_focus_count : null) ??
    (typeof value.focuses_count === "number" ? value.focuses_count : null);
  if (typeof numeric === "number" && Number.isFinite(numeric)) {
    return numeric;
  }
  for (const key of ["current_focuses", "focus_lane_ids", "focuses"] as const) {
    const list = value[key];
    if (Array.isArray(list)) {
      return list.length;
    }
  }
  return null;
}

function deriveUnconsumedReportCount(
  _payload: RuntimeCenterOverviewPayload | null,
  mainBrainPayload?: RuntimeMainBrainResponse | null,
): number | null {
  if (mainBrainPayload?.meta) {
    const agentReports = mainBrainPayload.meta.agent_reports;
    if (isRecord(agentReports)) {
      for (const key of [
        "unconsumed_count",
        "pending_count",
        "unconsumed_reports",
      ] as const) {
        const value = agentReports[key];
        if (typeof value === "number" && Number.isFinite(value)) {
          return value;
        }
      }
    }
  }
  if (!mainBrainPayload) {
    return null;
  }
  const unconsumed = mainBrainPayload.reports.filter((entry) => {
    if (entry.report_consumed === false || entry.consumed === false) {
      return true;
    }
    if (entry.processed === false || entry.unconsumed === true) {
      return true;
    }
    return false;
  });
  return unconsumed.length;
}

function coordinationFallback(value: RuntimeMainBrainEnvironment | null): string | null {
  if (!value) {
    return null;
  }
  const hostTwinSummary = value.host_twin_summary;
  if (!hostTwinSummary) {
    return null;
  }
  return firstString(
    hostTwinSummary.recommended_scheduler_action,
    hostTwinSummary.continuity_state,
    hostTwinSummary.active_app_family_keys,
  );
}

function buildDefaultSignalsFromPayload(
  payload: RuntimeMainBrainResponse | null,
): RuntimeCockpitSignal[] {
  if (!payload) {
    return [];
  }
  const fallbackSignals: Array<[string, RuntimeMainBrainRecord | null]> = [
    ["carrier", payload.carrier],
    ["strategy", payload.strategy],
    ["lanes", { count: payload.lanes.length, summary: String(payload.lanes.length) }],
    ["backlog", { count: payload.backlog.length, summary: String(payload.backlog.length) }],
    ["current_cycle", payload.current_cycle],
    [
      "assignments",
      { count: payload.assignments.length, summary: String(payload.assignments.length) },
    ],
    ["agent_reports", { count: payload.reports.length, summary: String(payload.reports.length) }],
    ["environment", payload.environment],
    ["governance", payload.governance],
    ["automation", payload.automation],
    ["recovery", payload.recovery],
    [
      "evidence",
      { count: payload.evidence.count, summary: payload.evidence.summary, route: payload.evidence.route },
    ],
    [
      "decisions",
      { count: payload.decisions.count, summary: payload.decisions.summary, route: payload.decisions.route },
    ],
    [
      "patches",
      { count: payload.patches.count, summary: payload.patches.summary, route: payload.patches.route },
    ],
  ];
  return fallbackSignals
    .filter(([, record]) => record !== null)
    .map(([key, record]) => convertDedicatedSignal(key, record));
}

export default function MainBrainCockpitPanel({
  data,
  loading,
  refreshing,
  buddySummary,
  mainBrainData,
  mainBrainLoading,
  mainBrainError,
  mainBrainUnavailable,
  onRefresh,
  onOpenRoute,
}: MainBrainCockpitPanelProps) {
  const dedicatedSignals = buildDedicatedSignals(mainBrainData);
  const signalCards =
    dedicatedSignals.length > 0
      ? dedicatedSignals
      : buildDefaultSignalsFromPayload(mainBrainData);
  const chainOrder = [
    "carrier",
    "strategy",
    "lanes",
    "backlog",
    "current_cycle",
    "assignments",
    "agent_reports",
    "environment",
    "evidence",
    "decisions",
    "patches",
  ];
  const fallbackChainSignals = chainOrder
    .map((key) => signalCards.find((signal) => signal.key === key) ?? null)
    .filter((signal): signal is RuntimeCockpitSignal => signal !== null);
  const dedicatedChainSignals = buildDedicatedChainSignals(mainBrainData);
  const chainSignals = dedicatedChainSignals ?? fallbackChainSignals;

  const carrierSignal = signalCards.find((signal) => signal.key === "carrier") ?? null;
  const strategySignal = signalCards.find((signal) => signal.key === "strategy") ?? null;
  const surface = mainBrainData?.surface;
  const generatedAt = mainBrainData?.generated_at;
  const errorMessage = mainBrainError;
  const cycleSignal = mainBrainData?.current_cycle ?? null;
  const cycleDeadline = formatUtcMinute(extractTimestamp(cycleSignal));
  const focusCountValue = extractFocusCount(cycleSignal);
  const focusCount =
    focusCountValue === null ? RUNTIME_CENTER_TEXT.emptyValue : String(focusCountValue);
  const unconsumedReportsValue = deriveUnconsumedReportCount(null, mainBrainData);
  const unconsumedReports =
    unconsumedReportsValue === null
      ? RUNTIME_CENTER_TEXT.emptyValue
      : String(unconsumedReportsValue);
  const governancePayload = mainBrainData?.governance ?? null;
  const queryRuntimeEntropy: RuntimeMainBrainQueryRuntimeEntropy | null =
    governancePayload?.query_runtime_entropy ?? null;
  const queryRuntimeEntropyState = queryRuntimeEntropy?.runtime_entropy ?? null;
  const queryRuntimeCompactionState = queryRuntimeEntropy?.compaction_state ?? null;
  const queryRuntimeBudget = queryRuntimeEntropy?.tool_result_budget ?? null;
  const queryRuntimeToolUseSummary = queryRuntimeEntropy?.tool_use_summary ?? null;
  const queryRuntimeArtifactRefs = Array.isArray(queryRuntimeToolUseSummary?.artifact_refs)
    ? queryRuntimeToolUseSummary.artifact_refs
        .map((value) => firstString(value))
        .filter((value): value is string => Boolean(value))
    : [];
  const queryRuntimeBudgetRemaining = firstString(
    queryRuntimeBudget?.remaining_budget,
    queryRuntimeBudget?.remaining,
    queryRuntimeBudget?.budget_remaining,
  );
  const queryRuntimeBudgetCapacity = firstString(
    queryRuntimeBudget?.message_budget,
    queryRuntimeBudget?.budget,
  );
  const queryRuntimeBudgetSummary =
    queryRuntimeBudgetRemaining && queryRuntimeBudgetCapacity
      ? `${queryRuntimeBudgetRemaining} / ${queryRuntimeBudgetCapacity}`
      : null;
  const queryRuntimeEntropySummary =
    firstString(
      queryRuntimeCompactionState?.summary,
      queryRuntimeToolUseSummary?.summary,
      queryRuntimeEntropyState?.carry_forward_contract,
      queryRuntimeEntropy?.status,
    ) ?? null;
  const recoveryPayload = mainBrainData?.recovery ?? null;
  const automationPayload = mainBrainData?.automation ?? null;
  const environmentPayload = mainBrainData?.environment ?? null;
  const reportCognitionPayload = mainBrainData?.report_cognition ?? null;
  const planningPayload = mainBrainData?.main_brain_planning ?? null;
  const planningStrategyConstraints = planningPayload?.strategy_constraints ?? null;
  const planningLatestCycleDecision = planningPayload?.latest_cycle_decision ?? null;
  const planningAssignmentPlan = planningPayload?.focused_assignment_plan ?? null;
  const planningReplan = planningPayload?.replan ?? null;
  const planningCycleShell = planningLatestCycleDecision?.planning_shell ?? null;
  const planningAssignmentShell = planningAssignmentPlan?.planning_shell ?? null;
  const planningReplanShell = planningReplan?.planning_shell ?? null;
  const planningPolicy = Array.isArray(planningStrategyConstraints?.planning_policy)
    ? planningStrategyConstraints.planning_policy
        .map((item) => firstString(item))
        .filter((item): item is string => Boolean(item))
        .join(", ")
    : null;
  const planningUncertaintyCount = Array.isArray(
    planningStrategyConstraints?.strategic_uncertainties,
  )
    ? planningStrategyConstraints.strategic_uncertainties.length
    : null;
  const planningLaneBudgetCount = Array.isArray(planningStrategyConstraints?.lane_budgets)
    ? planningStrategyConstraints.lane_budgets.length
    : null;
  const planningBacklogCount = Array.isArray(
    planningLatestCycleDecision?.selected_backlog_item_ids,
  )
    ? planningLatestCycleDecision.selected_backlog_item_ids.length
    : null;
  const planningAssignmentCount = Array.isArray(
    planningLatestCycleDecision?.selected_assignment_ids,
  )
    ? planningLatestCycleDecision.selected_assignment_ids.length
    : null;
  const planningCheckpointCount = Array.isArray(planningAssignmentPlan?.checkpoints)
    ? planningAssignmentPlan.checkpoints.length
    : null;
  const planningAcceptanceCount = Array.isArray(planningAssignmentPlan?.acceptance_criteria)
    ? planningAssignmentPlan.acceptance_criteria.length
    : null;
  const planningTriggerRuleCount = Array.isArray(planningReplan?.strategy_trigger_rules)
    ? planningReplan.strategy_trigger_rules.length
    : null;
  const planningUncertaintyRegister = planningReplan?.uncertainty_register ?? null;
  const planningUncertaintyRegisterSummary = planningUncertaintyRegister?.summary ?? null;
  const planningUncertaintyRegisterCount =
    firstString(planningUncertaintyRegisterSummary?.uncertainty_count) ??
    (Array.isArray(planningUncertaintyRegister?.items)
      ? String(planningUncertaintyRegister.items.length)
      : null);
  const assignmentRecords = recordList(mainBrainData?.assignments);
  const backlogRecords = recordList(mainBrainData?.backlog);
  const laneRecords = recordList(mainBrainData?.lanes);
  const currentCycleRecords = recordList(
    mainBrainData?.current_cycle ? [mainBrainData.current_cycle] : [],
  );
  const cycleSequenceRecords = recordList(mainBrainData?.cycles);
  const reportRecords = recordList(mainBrainData?.reports);
  const latestFindingRecords = recordList(reportCognitionPayload?.latest_findings);
  const conflictRecords = recordList(reportCognitionPayload?.conflicts);
  const holeRecords = recordList(reportCognitionPayload?.holes);
  const followupBacklogRecords = recordList(reportCognitionPayload?.followup_backlog);
  const unconsumedReportRecords = recordList(reportCognitionPayload?.unconsumed_reports);
  const needsFollowupReportRecords = recordList(reportCognitionPayload?.needs_followup_reports);
  const cognitionJudgment = reportCognitionPayload?.judgment ?? null;
  const cognitionNextAction = reportCognitionPayload?.next_action ?? null;
  const cognitionReasons = Array.isArray(reportCognitionPayload?.replan_reasons)
    ? (reportCognitionPayload?.replan_reasons as unknown[])
        .map((item) => firstString(item))
        .filter((item): item is string => item !== null)
    : [];
  const needsReplan = reportCognitionPayload?.needs_replan === true;
  const evidenceSection = mainBrainData?.evidence ?? null;
  const decisionsSection = mainBrainData?.decisions ?? null;
  const patchesSection = mainBrainData?.patches ?? null;
  const todayTraceEmptyCopy = "今天暂无新增记录。";
  const todayCompletedEmptyCopy = "今天暂无新完成记录。";
  const generatedDayAnchor = generatedAt ?? null;
  const scopedReportRecords = sliceRecordsForGeneratedDay(
    reportRecords,
    generatedDayAnchor,
  ).records;
  const scopedEvidenceSection = scopeTraceSectionToGeneratedDay(
    evidenceSection,
    generatedDayAnchor,
    todayTraceEmptyCopy,
  );
  const scopedDecisionsSection = scopeTraceSectionToGeneratedDay(
    decisionsSection,
    generatedDayAnchor,
    todayTraceEmptyCopy,
  );
  const scopedPatchesSection = scopeTraceSectionToGeneratedDay(
    patchesSection,
    generatedDayAnchor,
    todayTraceEmptyCopy,
  );
  const scopedDecisionRecords = recordList(scopedDecisionsSection?.entries);
  const scopedPatchRecords = recordList(scopedPatchesSection?.entries);
  const staffingPendingCount =
    typeof environmentPayload?.staffing?.pending_confirmation_count === "number"
      ? environmentPayload.staffing.pending_confirmation_count
      : 0;
  const humanAssistBlockedCount =
    typeof environmentPayload?.human_assist?.blocked_count === "number"
      ? environmentPayload.human_assist.blocked_count
      : 0;
  const todayGoalItems = [
    firstString(cycleSignal?.title, mainBrainData?.strategy?.title, strategySignal?.value),
    firstString(cycleSignal?.summary, mainBrainData?.strategy?.summary, strategySignal?.detail),
  ].filter((item): item is string => Boolean(item));
  const completedItems = [
    ...scopedReportRecords
      .slice(0, 2)
      .map((record) => firstString(record.title, record.headline, record.summary))
      .filter((item): item is string => Boolean(item)),
    scopedEvidenceSection && typeof scopedEvidenceSection.count === "number" && scopedEvidenceSection.count > 0
      ? `今日新增 ${scopedEvidenceSection.count} 条证据`
      : null,
  ].filter((item): item is string => Boolean(item));
  const inProgressItems = [
    ...assignmentRecords
      .slice(0, 2)
      .map((record) => firstString(record.title, record.summary))
      .filter((item): item is string => Boolean(item)),
    ...backlogRecords
      .slice(0, 1)
      .map((record) => firstString(record.title, record.summary))
      .filter((item): item is string => Boolean(item)),
  ];
  const blockedItems = [
    firstString(governancePayload?.summary),
    conflictRecords.length > 0 ? `存在 ${conflictRecords.length} 项冲突待主脑收口` : null,
    humanAssistBlockedCount > 0 ? `存在 ${humanAssistBlockedCount} 项人工协作阻塞` : null,
  ].filter((item): item is string => Boolean(item));
  const confirmItems = [
    ...scopedDecisionRecords
      .slice(0, 2)
      .map((record) => firstString(record.title, record.headline, record.summary))
      .filter((item): item is string => Boolean(item)),
    staffingPendingCount > 0 ? `待处理 ${staffingPendingCount} 项岗位/接手确认` : null,
    ...scopedPatchRecords
      .slice(0, 2)
      .map((record) => firstString(record.title, record.headline, record.summary))
      .filter((item): item is string => Boolean(item)),
  ].filter((item): item is string => Boolean(item));
  const nextStepMode =
    confirmItems.length > 0
      ? "等待确认"
      : blockedItems.length > 0 || humanAssistBlockedCount > 0
        ? "等待外部条件"
        : "自动执行";
  const nextStepTitle =
    firstString(cognitionNextAction?.title, followupBacklogRecords[0]?.title, backlogRecords[0]?.title) ||
    "继续推进当前周期";
  const nextStepSummary =
    firstString(
      cognitionNextAction?.summary,
      followupBacklogRecords[0]?.summary,
      backlogRecords[0]?.summary,
      coordinationFallback(environmentPayload),
    );
  const dailyBriefSections = [
    {
      key: "today-goal",
      label: "今日目标",
      items: todayGoalItems.length > 0 ? todayGoalItems : ["收口当前周期与主脑派工回流"],
    },
    {
      key: "completed",
      label: "已完成",
      items: completedItems.length > 0 ? completedItems : [todayCompletedEmptyCopy],
    },
    {
      key: "in-progress",
      label: "进行中",
      items: inProgressItems.length > 0 ? inProgressItems : ["今天暂无进行中的任务。"],
    },
    {
      key: "blocked",
      label: "当前阻塞",
      items: blockedItems.length > 0 ? blockedItems : ["今天暂无明显阻塞。"],
    },
    {
      key: "confirm",
      label: "待确认",
      items: confirmItems.length > 0 ? confirmItems : ["今天暂无待确认事项。"],
    },
    {
      key: "next-step",
      label: "下一步",
      items: [`${nextStepMode} · ${localizeRuntimeText(nextStepTitle)}`, nextStepSummary]
        .filter((item): item is string => Boolean(item)),
    },
  ];
  const industryRoute = firstString(mainBrainData?.carrier?.route);

  const isInitialLoading =
    (loading && !data) ||
    (mainBrainLoading && !mainBrainData && !mainBrainUnavailable);
  if (isInitialLoading) {
    return (
      <Card className="baize-card">
        <div className={styles.panelHeader}>
          <div>
            <h2 className={styles.cardTitle}>{MAIN_BRAIN_COCKPIT_TEXT.title}</h2>
            <p className={styles.cardSummary}>{MAIN_BRAIN_COCKPIT_TEXT.description}</p>
          </div>
        </div>
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  if (!mainBrainData) {
    return (
      <Card className="baize-card">
        <div className={styles.panelHeader}>
          <div>
            <h2 className={styles.cardTitle}>{MAIN_BRAIN_COCKPIT_TEXT.title}</h2>
            <p className={styles.cardSummary}>{MAIN_BRAIN_COCKPIT_TEXT.description}</p>
          </div>
          <Space size={8} wrap>
            <Button
              className="baize-btn baize-btn-primary"
              icon={<RefreshCw size={16} />}
              loading={refreshing || mainBrainLoading}
              onClick={() => {
                onRefresh();
              }}
            >
              刷新
            </Button>
          </Space>
        </div>
        <Alert
          type={errorMessage ? "error" : "info"}
          showIcon
          message={errorMessage ?? "主脑驾驶舱暂未接入正式读面。"}
          description="Runtime Center 当前只认 dedicated main-brain cockpit contract，不再从 overview 卡片回填主脑运行事实。"
        />
      </Card>
    );
  }

  return (
    <Card className="baize-card">
      <div className={styles.panelHeader}>
        <div>
          <div className={styles.cardTitleRow}>
            <h2 className={styles.cardTitle}>{MAIN_BRAIN_COCKPIT_TEXT.title}</h2>
            <Tag color={surfaceTagColor(surface?.status ?? "unavailable")}>
              {formatRuntimeStatus(surface?.status ?? "unavailable")}
            </Tag>
          </div>
          <p className={styles.cardSummary}>{MAIN_BRAIN_COCKPIT_TEXT.description}</p>
        </div>
        <Space size={8} wrap>
          <Button
            className="baize-btn baize-btn-primary"
            icon={<RefreshCw size={16} />}
            loading={refreshing}
            onClick={() => {
              onRefresh();
            }}
          >
            刷新
          </Button>
        </Space>
      </div>

      {errorMessage ? (
        <Alert
          showIcon
          type="error"
          message="主脑今日运行简报加载失败"
          description={errorMessage}
          style={{ marginBottom: 20 }}
        />
      ) : null}

      <Space wrap size={[8, 8]} style={{ marginBottom: 16 }}>
        {surface?.source ? <Tag>{formatRuntimeSourceList(surface.source)}</Tag> : null}
        {surface?.note ? <Tag>{formatRuntimeSurfaceNote(surface.note)}</Tag> : null}
        {generatedAt ? (
          <Tag>{RUNTIME_CENTER_TEXT.generatedAt(formatCnTimestamp(generatedAt))}</Tag>
        ) : null}
      </Space>

      <Card size="small" title="主脑今日运行简报" style={{ marginBottom: 16 }}>
        <div className={styles.briefGrid}>
          {dailyBriefSections.map((section) => (
            <div key={section.key} className={styles.briefCard}>
              <div className={styles.briefTitle}>{section.label}</div>
              <div className={styles.briefList}>
                {section.items.map((item, index) => (
                  <div key={`${section.key}:${index}`} className={styles.briefItem}>
                    {localizeRuntimeText(item)}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {buddySummary
        ? (() => {
            const summary = buddySummary;
            return (
              <Card size="small" title="伙伴摘要" style={{ marginBottom: 16 }}>
                <div className={styles.briefGrid}>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>{summary.buddy_name}</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(
                          `${presentBuddyStageLabel(summary.evolution_stage)} / 心情 ${presentBuddyMoodLabel(summary.mood_state)}`,
                        )}
                      </div>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(
                          `等级 ${summary.growth_level} / 亲密度 ${summary.intimacy} / 契合度 ${summary.affinity}`,
                        )}
                      </div>
                    </div>
                  </div>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>最终目标</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(summary.current_goal_summary)}
                      </div>
                    </div>
                  </div>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>当前任务</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(summary.current_task_summary)}
                      </div>
                    </div>
                  </div>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>为什么现在做</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(summary.why_now_summary)}
                      </div>
                    </div>
                  </div>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>唯一下一步</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(
                          summary.single_next_action_summary || "先把任务缩成一个最小动作。",
                        )}
                      </div>
                    </div>
                  </div>
                  <div className={styles.briefCard}>
                    <div className={styles.briefTitle}>陪伴策略</div>
                    <div className={styles.briefList}>
                      <div className={styles.briefItem}>
                        {localizeRuntimeText(
                          summary.companion_strategy_summary || "先接住情绪，再把任务缩成一个最小动作。",
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })()
        : null}

      <Descriptions
        size="small"
        bordered
        column={{ xs: 1, sm: 2, md: 3 }}
        style={{ marginBottom: 16 }}
        items={[
          {
            key: "carrier",
            label: carrierSignal?.label ?? formatRuntimeFieldLabel("carrier"),
            children: carrierSignal?.value ?? RUNTIME_CENTER_TEXT.emptyValue,
          },
          {
            key: "strategy",
            label: strategySignal?.label ?? formatRuntimeFieldLabel("strategy"),
            children: strategySignal?.value ?? RUNTIME_CENTER_TEXT.emptyValue,
          },
          {
            key: "cycle_deadline",
            label: formatRuntimeFieldLabel("cycle_deadline"),
            children: cycleDeadline,
          },
          {
            key: "focus_count",
            label: formatRuntimeFieldLabel("focus_count"),
            children: focusCount,
          },
          {
            key: "unconsumed_reports",
            label: formatRuntimeFieldLabel("unconsumed_reports"),
            children: unconsumedReports,
          },
        ]}
      />

      {chainSignals.length > 0 ? (
        <Card size="small" title="统一运行链" style={{ marginBottom: 16 }}>
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {chainSignals.map((signal) => (
              <div
                key={`chain:${signal.key}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                <Space size={[8, 8]} wrap>
                  <Tag color={signalToneColor(signal)}>{signal.label}</Tag>
                  <Text strong>{signal.value}</Text>
                  {signal.detail ? <Text type="secondary">{signal.detail}</Text> : null}
                </Space>
                {signal.route ? (
                  <Button
                    size="small"
                    aria-label={`打开${signal.label}链路详情`}
                    onClick={() => {
                      onOpenRoute(signal.route!, signal.routeTitle || signal.label);
                    }}
                  >
                    打开详情
                  </Button>
                ) : null}
              </div>
            ))}
          </Space>
        </Card>
      ) : null}

      {mainBrainData ? (
        <section className={styles.panelGrid}>
          <Card size="small" title="规划面" style={{ marginBottom: 16 }}>
            <div className={styles.metaGrid}>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>泳道</h3>
                    <p className={styles.selectionSummary}>
                      展示当前主脑持有的长期责任泳道。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(laneRecords, {
                  emptyLabel: "当前没有可见泳道。",
                  fallbackRoute: industryRoute,
                  fallbackRouteTitle: "泳道",
                  onOpenRoute,
                })}
              </div>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>当前周期</h3>
                    <p className={styles.selectionSummary}>
                      展示当前主脑周期与当前聚焦的推进窗口。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(currentCycleRecords, {
                  emptyLabel: "当前没有可见周期。",
                  fallbackRoute: industryRoute,
                  fallbackRouteTitle: "当前周期",
                  onOpenRoute,
                })}
              </div>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>周期序列</h3>
                    <p className={styles.selectionSummary}>
                      展示主脑当前还在跟踪的正式周期序列。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(
                  cycleSequenceRecords.length > 0
                    ? cycleSequenceRecords
                    : currentCycleRecords,
                  {
                    emptyLabel: "当前没有可见周期序列。",
                    fallbackRoute: industryRoute,
                    fallbackRouteTitle: "周期序列",
                    onOpenRoute,
                  },
                )}
              </div>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>待办</h3>
                    <p className={styles.selectionSummary}>
                      展示当前主脑仍需调度、物化或跟进的正式待办。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(backlogRecords, {
                  emptyLabel: "当前没有可见待办。",
                  fallbackRoute: industryRoute,
                  fallbackRouteTitle: "待办",
                  onOpenRoute,
                })}
              </div>
            </div>
          </Card>

          {planningPayload ? (
            <Card size="small" title="正式规划壳" style={{ marginBottom: 16 }}>
              <div className={styles.metaGrid}>
                <div className={styles.controlCard}>
                  <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                    <div>
                      <h3 className={styles.entryTitle}>策略约束</h3>
                      {firstString(planningPayload?.source) ? (
                        <p className={styles.selectionSummary}>
                          {firstString(planningPayload?.source)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {
                        key: "planning_policy",
                        label: "规划策略",
                        children: planningPolicy ?? RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "uncertainty_count",
                        label: "战略不确定项",
                        children:
                          planningUncertaintyCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningUncertaintyCount),
                      },
                      {
                        key: "lane_budget_count",
                        label: "赛道预算",
                        children:
                          planningLaneBudgetCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningLaneBudgetCount),
                      },
                    ]}
                  />
                </div>
                <div className={styles.controlCard}>
                  <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                    <div>
                      <h3 className={styles.entryTitle}>周期壳</h3>
                      {firstString(planningLatestCycleDecision?.summary) ? (
                        <p className={styles.selectionSummary}>
                          {firstString(planningLatestCycleDecision?.summary)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {
                        key: "cycle_backlog_count",
                        label: "选中待办",
                        children:
                          planningBacklogCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningBacklogCount),
                      },
                      {
                        key: "cycle_assignment_count",
                        label: "选中派工",
                        children:
                          planningAssignmentCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningAssignmentCount),
                      },
                      {
                        key: "cycle_resume_key",
                        label: "Resume key",
                        children:
                          firstString(planningCycleShell?.resume_key) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "cycle_fork_key",
                        label: "Fork key",
                        children:
                          firstString(planningCycleShell?.fork_key) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                    ]}
                  />
                  {firstString(planningCycleShell?.verify_reminder) ? (
                    <p className={styles.selectionSummary} style={{ marginTop: 12 }}>
                      {firstString(planningCycleShell?.verify_reminder)}
                    </p>
                  ) : null}
                </div>
                <div className={styles.controlCard}>
                  <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                    <div>
                      <h3 className={styles.entryTitle}>派工壳</h3>
                      {firstString(planningAssignmentPlan?.summary) ? (
                        <p className={styles.selectionSummary}>
                          {firstString(planningAssignmentPlan?.summary)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {
                        key: "assignment_checkpoint_count",
                        label: "检查点",
                        children:
                          planningCheckpointCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningCheckpointCount),
                      },
                      {
                        key: "assignment_acceptance_count",
                        label: "验收条件",
                        children:
                          planningAcceptanceCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningAcceptanceCount),
                      },
                      {
                        key: "assignment_resume_key",
                        label: "Resume key",
                        children:
                          firstString(planningAssignmentShell?.resume_key) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "assignment_fork_key",
                        label: "Fork key",
                        children:
                          firstString(planningAssignmentShell?.fork_key) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                    ]}
                  />
                  {firstString(planningAssignmentShell?.verify_reminder) ? (
                    <p className={styles.selectionSummary} style={{ marginTop: 12 }}>
                      {firstString(planningAssignmentShell?.verify_reminder)}
                    </p>
                  ) : null}
                </div>
                <div className={styles.controlCard}>
                  <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                    <div>
                      <div className={styles.cardTitleRow}>
                        <h3 className={styles.entryTitle}>重规划壳</h3>
                        {firstString(planningReplan?.status) ? (
                          <Tag color={surfaceTagColor(cardStatusFromValue(planningReplan?.status))}>
                            {firstString(planningReplan?.status)}
                          </Tag>
                        ) : null}
                      </div>
                      {firstString(planningReplan?.summary) ? (
                        <p className={styles.selectionSummary}>
                          {firstString(planningReplan?.summary)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {
                        key: "replan_decision_kind",
                        label: "决策类型",
                        children:
                          firstString(planningReplan?.decision_kind) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "replan_trigger_rule_count",
                        label: "触发规则",
                        children:
                          planningTriggerRuleCount === null
                            ? RUNTIME_CENTER_TEXT.emptyValue
                            : String(planningTriggerRuleCount),
                      },
                      {
                        key: "replan_uncertainty_count",
                        label: "不确定项登记",
                        children:
                          planningUncertaintyRegisterCount ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "replan_resume_key",
                        label: "Resume key",
                        children:
                          firstString(planningReplanShell?.resume_key) ??
                          RUNTIME_CENTER_TEXT.emptyValue,
                      },
                    ]}
                  />
                  {firstString(planningReplanShell?.verify_reminder) ? (
                    <p className={styles.selectionSummary} style={{ marginTop: 12 }}>
                      {firstString(planningReplanShell?.verify_reminder)}
                    </p>
                  ) : null}
                </div>
              </div>
            </Card>
          ) : null}

          {reportCognitionPayload ? (
            <Card size="small" title="汇报认知" style={{ marginBottom: 16 }}>
              <div className={styles.metaGrid}>
                <div className={styles.controlCard}>
                  <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                    <div>
                      <div className={styles.cardTitleRow}>
                        <h3 className={styles.entryTitle}>判断</h3>
                        <Tag color={needsReplan ? "error" : "success"}>
                          {needsReplan ? "需要重规划" : "已清晰"}
                        </Tag>
                      </div>
                      {firstString(cognitionJudgment?.summary) ? (
                        <p className={styles.selectionSummary}>
                          {firstString(cognitionJudgment?.summary)}
                        </p>
                      ) : null}
                    </div>
                    {firstString(cognitionJudgment?.route) ? (
                      <Button
                        size="small"
                        onClick={() => {
                          onOpenRoute(firstString(cognitionJudgment?.route)!, "汇报认知");
                        }}
                      >
                        打开详情
                      </Button>
                    ) : null}
                  </div>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {
                        key: "next_action",
                        label: "下一动作",
                        children:
                          firstString(
                            cognitionNextAction?.title,
                            cognitionNextAction?.kind,
                          ) ?? RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "unconsumed_reports",
                        label: "未消费汇报",
                        children:
                          String(unconsumedReportRecords.length) ?? RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "needs_followup_reports",
                        label: "待跟进汇报",
                        children:
                          String(needsFollowupReportRecords.length) ?? RUNTIME_CENTER_TEXT.emptyValue,
                      },
                      {
                        key: "followup_backlog",
                        label: "跟进待办",
                        children:
                          String(followupBacklogRecords.length) ?? RUNTIME_CENTER_TEXT.emptyValue,
                      },
                    ]}
                  />
                  {firstString(cognitionNextAction?.summary) ? (
                    <p className={styles.selectionSummary} style={{ marginTop: 12 }}>
                      {firstString(cognitionNextAction?.summary)}
                    </p>
                  ) : null}
                  {cognitionReasons.length > 0 ? (
                    <Space size={[8, 8]} wrap style={{ marginTop: 12 }}>
                      {cognitionReasons.map((reason) => (
                        <Tag key={reason} color="warning">
                          {reason}
                        </Tag>
                      ))}
                    </Space>
                  ) : null}
                </div>
                {renderCognitionBlock({
                  title: "最新发现",
                  records: latestFindingRecords,
                  emptyLabel: "当前没有可见的最新发现。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
                {renderCognitionBlock({
                  title: "冲突",
                  records: conflictRecords,
                  emptyLabel: "当前没有可见的汇报冲突。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
                {renderCognitionBlock({
                  title: "缺口",
                  records: holeRecords,
                  emptyLabel: "当前没有可见的汇报缺口。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
                {renderCognitionBlock({
                  title: "未消费汇报",
                  records: unconsumedReportRecords,
                  emptyLabel: "当前没有可见的未消费汇报。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
                {renderCognitionBlock({
                  title: "待跟进汇报",
                  records: needsFollowupReportRecords,
                  emptyLabel: "当前没有可见的待跟进汇报。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
                {renderCognitionBlock({
                  title: "跟进待办",
                  records: followupBacklogRecords,
                  emptyLabel: "当前没有可见的跟进待办。",
                  fallbackRoute: firstString(reportCognitionPayload?.route) ?? industryRoute,
                  onOpenRoute,
                })}
              </div>
            </Card>
          ) : null}

          <Card size="small" title="执行信封" style={{ marginBottom: 16 }}>
            <div className={styles.metaGrid}>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>派工</h3>
                    <p className={styles.selectionSummary}>
                      展示当前由主脑周期持有的执行信封。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(assignmentRecords, {
                  emptyLabel: "当前没有可见派工。",
                  fallbackRoute: industryRoute,
                  fallbackRouteTitle: "派工",
                  onOpenRoute,
                })}
              </div>
              <div className={styles.controlCard}>
                <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className={styles.entryTitle}>汇报</h3>
                    <p className={styles.selectionSummary}>
                      展示等待综合、跟进或重规划的结构化执行汇报。
                    </p>
                  </div>
                </div>
                {renderCompactRecordList(scopedReportRecords, {
                  emptyLabel: todayCompletedEmptyCopy,
                  fallbackRoute: industryRoute,
                  fallbackRouteTitle: "汇报",
                  onOpenRoute,
                })}
              </div>
            </div>
          </Card>

          <Card size="small" title="操作员闭环" style={{ marginBottom: 16 }}>
            <div className={styles.metaGrid}>
              {renderOperatorBlock({
                title: "运行治理",
                summary: firstString(governancePayload?.summary),
                status: governancePayload?.status,
                route: firstString(governancePayload?.route),
                routeTitle: "运行治理",
                details: [
                  ["待处理决策", firstString(governancePayload?.pending_decisions)],
                  ["待处理补丁", firstString(governancePayload?.pending_patches)],
                  ["已暂停计划", firstString(governancePayload?.paused_schedule_count)],
                  ["交接是否激活", firstString(governancePayload?.handoff_active)],
                ],
                onOpenRoute,
              })}
              {renderOperatorBlock({
                title: "Query runtime entropy",
                summary: queryRuntimeEntropySummary,
                status: firstString(queryRuntimeEntropy?.status, queryRuntimeEntropyState?.status),
                route: firstString(governancePayload?.route),
                routeTitle: "运行治理",
                details: [
                  ["状态", firstString(queryRuntimeEntropy?.status, queryRuntimeEntropyState?.status)],
                  [
                    "压缩模式",
                    firstString(
                      queryRuntimeCompactionState?.mode,
                      queryRuntimeCompactionState?.status,
                    ),
                  ],
                  ["预算余量", queryRuntimeBudgetSummary],
                  ["工具摘要", firstString(queryRuntimeToolUseSummary?.summary)],
                  [
                    "Artifacts",
                    queryRuntimeArtifactRefs.length > 0 ? queryRuntimeArtifactRefs.join(", ") : null,
                  ],
                ],
                onOpenRoute,
              })}
              {renderOperatorBlock({
                title: "恢复",
                summary: firstString(recoveryPayload?.summary),
                status: recoveryPayload?.status,
                route: firstString(recoveryPayload?.route),
                routeTitle: "恢复",
                details: [
                  ["待处理决策", firstString(recoveryPayload?.pending_decisions)],
                  ["活动计划", firstString(recoveryPayload?.active_schedules)],
                  ["恢复时间", firstString(recoveryPayload?.recovered_at)],
                  ["原因", firstString(recoveryPayload?.reason)],
                  ["吸收动作", presentRecoveryAbsorptionActionKind(recoveryPayload?.absorption_action_kind)],
                  ["动作摘要", firstString(recoveryPayload?.absorption_action_summary)],
                  ["动作结果", presentRecoveryAbsorptionMaterialized(recoveryPayload?.absorption_action_materialized)],
                  ["重规划类型", presentRecoveryReplanDecisionKind(recoveryPayload?.absorption_replan_decision_kind)],
                  ["人协任务", firstString(recoveryPayload?.absorption_human_task_id)],
                ],
                onOpenRoute,
              })}
              {renderOperatorBlock({
                title: "自动化",
                summary: firstString(automationPayload?.summary),
                status: automationPayload?.status,
                route: firstString(automationPayload?.route),
                routeTitle: "自动化",
                details: [
                  ["计划数", firstString(automationPayload?.schedule_count)],
                  [
                    "活动计划",
                    firstString(automationPayload?.active_schedule_count),
                  ],
                  [
                    "心跳",
                    firstString(automationPayload?.heartbeat?.status),
                  ],
                  [
                    "心跳间隔",
                    firstString(automationPayload?.heartbeat?.every),
                  ],
                ],
                onOpenRoute,
              })}
              {renderOperatorBlock({
                title: "环境",
                summary: firstString(environmentPayload?.summary),
                status: environmentPayload?.status,
                route: firstString(environmentPayload?.route),
                routeTitle: "环境",
                details: [
                  [
                    "已选席位",
                    firstString(environmentPayload?.host_twin_summary?.selected_seat_ref),
                  ],
                  [
                    "调度动作",
                    firstString(
                      environmentPayload?.host_twin_summary?.recommended_scheduler_action,
                    ),
                  ],
                  [
                    "连续性状态",
                    formatContinuityState(
                      environmentPayload?.host_twin_summary?.continuity_state,
                    ),
                  ],
                  [
                    "活动宿主族",
                    firstString(
                      Array.isArray(environmentPayload?.host_twin_summary?.active_app_family_keys)
                        ? environmentPayload.host_twin_summary.active_app_family_keys.join(", ")
                        : null,
                    ),
                  ],
                  [
                    "交接是否激活",
                    firstString(environmentPayload?.handoff?.active),
                  ],
                  [
                    "待确认补位",
                    firstString(environmentPayload?.staffing?.pending_confirmation_count),
                  ],
                  [
                    "人工协作阻塞",
                    firstString(environmentPayload?.human_assist?.blocked_count),
                  ],
                ],
                onOpenRoute,
              })}
            </div>
          </Card>

          <Card size="small" title="追踪闭环" style={{ marginBottom: 16 }}>
            <div className={styles.metaGrid}>
              {renderTraceBlock({
                title: "证据",
                section: scopedEvidenceSection,
                emptyLabel: todayTraceEmptyCopy,
                onOpenRoute,
              })}
              {renderTraceBlock({
                title: "决策",
                section: scopedDecisionsSection,
                emptyLabel: todayTraceEmptyCopy,
                onOpenRoute,
              })}
              {renderTraceBlock({
                title: "补丁",
                section: scopedPatchesSection,
                emptyLabel: todayTraceEmptyCopy,
                onOpenRoute,
              })}
            </div>
          </Card>
        </section>
      ) : null}

      <section className={styles.metrics}>
        {signalCards.map((signal) => renderSignalCard(signal, onOpenRoute))}
      </section>
    </Card>
  );
}
