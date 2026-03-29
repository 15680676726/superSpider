import { Alert, Button, Card, Skeleton, Space, Tag } from "antd";
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
  formatRuntimeSourceList,
  formatRuntimeStatus,
  formatRuntimeSurfaceNote,
} from "./text";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
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
  current_cycle: <RotateCcw size={18} color="#C9A84C" />,
  assignments: <Bot size={18} color="#10b981" />,
  agent_reports: <Bot size={18} color="#10b981" />,
  environment: <ShieldCheck size={18} color="#10b981" />,
  evidence: <Activity size={18} color="#1B4FD8" />,
  decisions: <ShieldAlert size={18} color="#f43f5e" />,
  patches: <RotateCcw size={18} color="#f97316" />,
};

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

      <section className={styles.metrics}>
        {signalCards.map((signal) => renderSignalCard(signal, onOpenRoute))}
      </section>
    </Card>
  );
}
