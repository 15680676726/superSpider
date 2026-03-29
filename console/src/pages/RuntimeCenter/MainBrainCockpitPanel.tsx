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
  formatRuntimeFieldLabel,
  formatRuntimeSourceList,
  formatRuntimeStatus,
  formatRuntimeSurfaceNote,
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

type MainBrainCockpitPanelProps = {
  data: RuntimeCenterOverviewPayload | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
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
  environment: <ShieldCheck size={18} color="#10b981" />,
  evidence: <Activity size={18} color="#1B4FD8" />,
  decisions: <ShieldAlert size={18} color="#f43f5e" />,
  patches: <RotateCcw size={18} color="#f97316" />,
};

const { Text } = Typography;

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
            aria-label={`Open ${signal.label} detail`}
            onClick={() => {
              onOpenRoute(signal.route!, signal.routeTitle || signal.label);
            }}
          >
            Open Detail
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

function deriveUnconsumedReportCount(payload: RuntimeCenterOverviewPayload | null): number | null {
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

export default function MainBrainCockpitPanel({
  data,
  loading,
  refreshing,
  error,
  onRefresh,
  onOpenRoute,
}: MainBrainCockpitPanelProps) {
  const environmentSignals = buildRuntimeEnvironmentCockpitSignals(data);
  const industrySignals = buildRuntimeIndustryCockpitSignals(data);
  const surface = data?.surface;
  const signalCards = [...environmentSignals, ...industrySignals];
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
  const chainSignals = chainOrder
    .map((key) => signalCards.find((signal) => signal.key === key) ?? null)
    .filter((signal): signal is RuntimeCockpitSignal => signal !== null);

  const carrierSignal = environmentSignals.find((signal) => signal.key === "carrier") ?? null;
  const strategySignal = industrySignals.find((signal) => signal.key === "strategy") ?? null;
  const mainBrainMeta = overviewCardMeta(data, "main-brain");
  const industryMeta = overviewCardMeta(data, "industry");
  const cycleSignal =
    (isRecord(mainBrainMeta.current_cycle) ? mainBrainMeta.current_cycle : null) ??
    (isRecord(industryMeta.current_cycle) ? industryMeta.current_cycle : null);
  const cycleDeadline = formatUtcMinute(extractTimestamp(cycleSignal));
  const focusCountValue = extractFocusCount(cycleSignal);
  const focusCount =
    focusCountValue === null ? RUNTIME_CENTER_TEXT.emptyValue : String(focusCountValue);
  const unconsumedReportsValue = deriveUnconsumedReportCount(data);
  const unconsumedReports =
    unconsumedReportsValue === null
      ? RUNTIME_CENTER_TEXT.emptyValue
      : String(unconsumedReportsValue);

  if (loading && !data) {
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

      {error ? (
        <Alert
          showIcon
          type="error"
          message="主脑驾驶舱加载失败"
          description={error}
          style={{ marginBottom: 20 }}
        />
      ) : null}

      <Space wrap size={[8, 8]} style={{ marginBottom: 16 }}>
        {surface?.source ? <Tag>{formatRuntimeSourceList(surface.source)}</Tag> : null}
        {surface?.note ? <Tag>{formatRuntimeSurfaceNote(surface.note)}</Tag> : null}
        {data?.generated_at ? (
          <Tag>{RUNTIME_CENTER_TEXT.generatedAt(formatCnTimestamp(data.generated_at))}</Tag>
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
        <Card size="small" title="Unified Runtime Chain" style={{ marginBottom: 16 }}>
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
                    aria-label={`Open ${signal.label} chain detail`}
                    onClick={() => {
                      onOpenRoute(signal.route!, signal.routeTitle || signal.label);
                    }}
                  >
                    Open Detail
                  </Button>
                ) : null}
              </div>
            ))}
          </Space>
        </Card>
      ) : null}

      <section className={styles.metrics}>
        {signalCards.map((signal) => renderSignalCard(signal, onOpenRoute))}
      </section>
    </Card>
  );
}
