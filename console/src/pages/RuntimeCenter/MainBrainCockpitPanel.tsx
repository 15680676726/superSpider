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
  buildRuntimeEnvironmentCockpitSignals,
} from "./runtimeEnvironmentSections";
import {
  buildRuntimeIndustryCockpitSignals,
  type RuntimeCockpitSignal,
} from "./runtimeIndustrySections";
import type { RuntimeMainBrainResponse } from "../../api/modules/runtimeCenter";

type MainBrainCockpitPanelProps = {
  data: RuntimeCenterOverviewPayload | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
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

function detailFromSignal(record: Record<string, unknown>): string | null {
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

function routeFromSignal(record: Record<string, unknown>): string | null {
  return (
    stringOrNumber(record.route) ??
    stringOrNumber(record.route_title) ??
    stringOrNumber(record.routeTitle)
  );
}

function routeTitleFromSignal(record: Record<string, unknown>): string | null {
  return stringOrNumber(record.route_title) ?? stringOrNumber(record.routeTitle);
}

function valueFromSignal(record: Record<string, unknown>): string {
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
  const record = isRecord(data) ? (data as Record<string, unknown>) : {};
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
  const chain = payload?.meta?.control_chain;
  if (!Array.isArray(chain) || chain.length === 0) {
    return null;
  }
  const signals = chain
    .map((item) => {
      if (!isRecord(item)) {
        return null;
      }
      const record = item as Record<string, unknown>;
      const key = typeof record.key === "string" && record.key ? record.key : null;
      if (!key) {
        return null;
      }
      return convertDedicatedSignal(key, record);
    })
    .filter((signal): signal is RuntimeCockpitSignal => signal !== null);
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

function overviewCardMeta(
  payload: RuntimeCenterOverviewPayload | null,
  cardKey: string,
): Record<string, unknown> {
  const card = payload?.cards?.find((entry) => entry.key === cardKey);
  return isRecord(card?.meta) ? card!.meta : {};
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
  payload: RuntimeCenterOverviewPayload | null,
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
  const mainBrainMeta = overviewCardMeta(payload, "main-brain");
  const reportsSignal = isRecord(mainBrainMeta.agent_reports) ? mainBrainMeta.agent_reports : null;
  if (reportsSignal) {
    for (const key of ["unconsumed_count", "unconsumed_reports", "pending_count"] as const) {
      const value = reportsSignal[key];
      if (typeof value === "number" && Number.isFinite(value)) {
        return value;
      }
    }
  }

  const reportCards = (payload?.cards ?? []).filter((card) =>
    ["agent_reports", "agent-reports", "reports"].includes(card.key),
  );
  if (reportCards.length === 0) {
    return null;
  }
  const entries = reportCards.flatMap((card) => card.entries ?? []);
  const unconsumed = entries.filter((entry) => {
    const meta = isRecord(entry.meta) ? entry.meta : {};
    if (meta.processed === false) {
      return true;
    }
    if (meta.report_consumed === false || meta.consumed === false) {
      return true;
    }
    if (meta.unconsumed === true) {
      return true;
    }
    return false;
  });
  return unconsumed.length;
}

function statusTagColor(value: unknown): string {
  return signalToneColor({
    key: "status",
    label: "status",
    value: "",
    tone: toneFromStatus(value),
  });
}

function recordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => isRecord(item));
}

function recordTitle(record: Record<string, unknown>, fallback: string): string {
  const value =
    firstString(
      record.title,
      record.headline,
      record.label,
      record.name,
      record.id,
      record.assignment_id,
      record.report_id,
    ) ?? fallback;
  return localizeRuntimeText(value);
}

function recordSummary(record: Record<string, unknown>): string | null {
  const value = firstString(
    record.summary,
    record.description,
    record.reason,
    record.note,
    record.recommendation,
  );
  return value ? localizeRuntimeText(value) : null;
}

function recordRoute(
  record: Record<string, unknown>,
  fallbackRoute: string | null,
): string | null {
  return firstString(record.route) ?? fallbackRoute;
}

function renderCompactRecordList(
  records: Record<string, unknown>[],
  options: {
    emptyLabel: string;
    fallbackRoute: string | null;
    fallbackRouteTitle: string;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { emptyLabel, fallbackRoute, fallbackRouteTitle, onOpenRoute } = options;
  if (records.length === 0) {
    return <Text type="secondary">{emptyLabel}</Text>;
  }
  return (
    <div className={styles.selectionList}>
      {records.map((record, index) => {
        const title = recordTitle(record, `Item ${index + 1}`);
        const summary = recordSummary(record);
        const status = firstString(record.status, record.runtime_status);
        const route = recordRoute(record, fallbackRoute);
        const needsFollowup = record.needs_followup === true;
        const processed = record.processed === true;
        return (
          <div key={`${title}:${index}`} className={styles.selectionRow}>
            <div className={styles.selectionBody}>
              <div className={styles.entryTitleRow}>
                {route ? (
                  <button
                    type="button"
                    className={styles.entryTitleButton}
                    onClick={() => {
                      onOpenRoute(route, title || fallbackRouteTitle);
                    }}
                  >
                    {title}
                  </button>
                ) : (
                  <div className={styles.entryTitle}>{title}</div>
                )}
                {status ? (
                  <Tag color={statusTagColor(status)}>{formatRuntimeStatus(status)}</Tag>
                ) : null}
                {needsFollowup ? <Tag color="warning">待跟进</Tag> : null}
                {processed ? <Tag color="success">已处理</Tag> : null}
              </div>
              {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function renderOperatorBlock(
  options: {
    title: string;
    summary: string | null;
    status: unknown;
    route: string | null;
    routeTitle: string;
    details: Array<[string, string | null]>;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, summary, status, route, routeTitle, details, onOpenRoute } = options;
  const detailItems = details
    .filter(([, value]) => value && value !== RUNTIME_CENTER_TEXT.emptyValue)
    .map(([label, value]) => ({
      key: label,
      label,
      children: value,
    }));

  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <div className={styles.cardTitleRow}>
            <h3 className={styles.entryTitle}>{title}</h3>
            {typeof status === "string" && status ? (
              <Tag color={statusTagColor(status)}>{formatRuntimeStatus(status)}</Tag>
            ) : null}
          </div>
          {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
        </div>
        {route ? (
          <Button
            size="small"
            onClick={() => {
              onOpenRoute(route, routeTitle);
            }}
          >
            打开详情
          </Button>
        ) : null}
      </div>
      {detailItems.length > 0 ? (
        <Descriptions size="small" column={1} items={detailItems} />
      ) : (
        <Text type="secondary">{RUNTIME_CENTER_TEXT.emptyValue}</Text>
      )}
    </div>
  );
}

function renderTraceBlock(
  options: {
    title: string;
    section: Record<string, unknown> | null;
    emptyLabel: string;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, section, emptyLabel, onOpenRoute } = options;
  const entries = recordList(section?.entries);
  const route = firstString(section?.route);
  const summary = firstString(section?.summary);
  const count = firstString(section?.count);

  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <div className={styles.cardTitleRow}>
            <h3 className={styles.entryTitle}>{title}</h3>
            {count ? <Tag>{count}</Tag> : null}
          </div>
          {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
        </div>
        {route ? (
          <Button
            size="small"
            onClick={() => {
              onOpenRoute(route, title);
            }}
          >
            打开详情
          </Button>
        ) : null}
      </div>
      {renderCompactRecordList(entries, {
        emptyLabel,
        fallbackRoute: route,
        fallbackRouteTitle: title,
        onOpenRoute,
      })}
    </div>
  );
}

function renderCognitionBlock(
  options: {
    title: string;
    records: Record<string, unknown>[];
    emptyLabel: string;
    fallbackRoute: string | null;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, records, emptyLabel, fallbackRoute, onOpenRoute } = options;
  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <h3 className={styles.entryTitle}>{title}</h3>
        </div>
      </div>
      {renderCompactRecordList(records, {
        emptyLabel,
        fallbackRoute,
        fallbackRouteTitle: title,
        onOpenRoute,
      })}
    </div>
  );
}

export default function MainBrainCockpitPanel({
  data,
  loading,
  refreshing,
  error,
  mainBrainData,
  mainBrainLoading,
  mainBrainError,
  mainBrainUnavailable,
  onRefresh,
  onOpenRoute,
}: MainBrainCockpitPanelProps) {
  const dedicatedSignals = buildDedicatedSignals(mainBrainData);
  const hasDedicatedSignals = dedicatedSignals.length > 0;
  const environmentSignals = hasDedicatedSignals ? [] : buildRuntimeEnvironmentCockpitSignals(data);
  const industrySignals = hasDedicatedSignals ? [] : buildRuntimeIndustryCockpitSignals(data);
  const signalCards =
    hasDedicatedSignals && dedicatedSignals.length > 0
      ? dedicatedSignals
      : [...environmentSignals, ...industrySignals];
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
  const mainBrainMeta = overviewCardMeta(data, "main-brain");
  const industryMeta = overviewCardMeta(data, "industry");
  const surface = mainBrainData?.surface ?? data?.surface;
  const generatedAt = mainBrainData?.generated_at ?? data?.generated_at;
  const errorMessage = mainBrainError ?? error;
  const cycleSignal =
    mainBrainData?.current_cycle ??
    (isRecord(mainBrainMeta.current_cycle) ? mainBrainMeta.current_cycle : null) ??
    (isRecord(industryMeta.current_cycle) ? industryMeta.current_cycle : null);
  const cycleDeadline = formatUtcMinute(extractTimestamp(cycleSignal));
  const focusCountValue = extractFocusCount(cycleSignal);
  const focusCount =
    focusCountValue === null ? RUNTIME_CENTER_TEXT.emptyValue : String(focusCountValue);
  const unconsumedReportsValue = deriveUnconsumedReportCount(data, mainBrainData);
  const unconsumedReports =
    unconsumedReportsValue === null
      ? RUNTIME_CENTER_TEXT.emptyValue
      : String(unconsumedReportsValue);
  const governancePayload = isRecord(mainBrainData?.governance)
    ? (mainBrainData?.governance as Record<string, unknown>)
    : null;
  const recoveryPayload = isRecord(mainBrainData?.recovery)
    ? (mainBrainData?.recovery as Record<string, unknown>)
    : null;
  const automationPayload = isRecord(mainBrainData?.automation)
    ? (mainBrainData?.automation as Record<string, unknown>)
    : null;
  const environmentPayload = isRecord(mainBrainData?.environment)
    ? (mainBrainData?.environment as Record<string, unknown>)
    : null;
  const reportCognitionPayload = isRecord(mainBrainData?.meta?.report_cognition)
    ? (mainBrainData?.meta?.report_cognition as Record<string, unknown>)
    : null;
  const assignmentRecords = recordList(mainBrainData?.assignments);
  const reportRecords = recordList(mainBrainData?.reports);
  const latestFindingRecords = recordList(reportCognitionPayload?.latest_findings);
  const conflictRecords = recordList(reportCognitionPayload?.conflicts);
  const holeRecords = recordList(reportCognitionPayload?.holes);
  const followupBacklogRecords = recordList(reportCognitionPayload?.followup_backlog);
  const unconsumedReportRecords = recordList(reportCognitionPayload?.unconsumed_reports);
  const needsFollowupReportRecords = recordList(reportCognitionPayload?.needs_followup_reports);
  const cognitionJudgment = isRecord(reportCognitionPayload?.judgment)
    ? (reportCognitionPayload?.judgment as Record<string, unknown>)
    : null;
  const cognitionNextAction = isRecord(reportCognitionPayload?.next_action)
    ? (reportCognitionPayload?.next_action as Record<string, unknown>)
    : null;
  const cognitionReasons = Array.isArray(reportCognitionPayload?.replan_reasons)
    ? (reportCognitionPayload?.replan_reasons as unknown[])
        .map((item) => firstString(item))
        .filter((item): item is string => item !== null)
    : [];
  const needsReplan = reportCognitionPayload?.needs_replan === true;
  const evidenceSection = isRecord(mainBrainData?.evidence)
    ? (mainBrainData?.evidence as Record<string, unknown>)
    : null;
  const decisionsSection = isRecord(mainBrainData?.decisions)
    ? (mainBrainData?.decisions as Record<string, unknown>)
    : null;
  const patchesSection = isRecord(mainBrainData?.patches)
    ? (mainBrainData?.patches as Record<string, unknown>)
    : null;
  const industryRoute =
    firstString(mainBrainData?.carrier?.route) ?? firstString(mainBrainMeta.industry_route);

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
          message="主脑驾驶舱加载失败"
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
                        label: "Next action",
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
                {renderCompactRecordList(reportRecords, {
                  emptyLabel: "当前没有可见汇报。",
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
                    firstString(
                      isRecord(automationPayload?.heartbeat)
                        ? automationPayload?.heartbeat.status
                        : null,
                    ),
                  ],
                  [
                    "心跳间隔",
                    firstString(
                      isRecord(automationPayload?.heartbeat)
                        ? automationPayload?.heartbeat.every
                        : null,
                    ),
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
                    firstString(
                      isRecord(governancePayload?.host_twin_summary)
                        ? governancePayload?.host_twin_summary.selected_seat_ref
                        : null,
                    ),
                  ],
                  [
                    "调度动作",
                    firstString(
                      isRecord(governancePayload?.host_twin_summary)
                        ? governancePayload?.host_twin_summary.recommended_scheduler_action
                        : null,
                    ),
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
                section: evidenceSection,
                emptyLabel: "当前没有可见证据。",
                onOpenRoute,
              })}
              {renderTraceBlock({
                title: "决策",
                section: decisionsSection,
                emptyLabel: "当前没有可见决策。",
                onOpenRoute,
              })}
              {renderTraceBlock({
                title: "补丁",
                section: patchesSection,
                emptyLabel: "当前没有可见补丁。",
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
