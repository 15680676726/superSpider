import { Button, Card, Empty, Progress, Tabs, Typography, type TabsProps } from "antd";
import { useMemo, useState, type ReactNode } from "react";

import { normalizeDisplayChinese } from "../../text";
import styles from "./index.module.less";

const { Text } = Typography;

export interface CockpitSummaryField {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}

export interface CockpitReportBlock {
  title: string;
  items: string[];
  generatedAt?: string | null;
}

export interface CockpitTrendPoint {
  label: string;
  completed: number;
  completionRate: number;
  quality: number;
}

export interface CockpitTraceLine {
  timestamp: string;
  level?: "info" | "warn" | "error";
  message: string;
  route?: string | null;
}

export type DayMode = "day" | "night";

export type AgentWorkPanelProps = {
  title: string;
  summaryFields: CockpitSummaryField[];
  morningReport?: CockpitReportBlock | null;
  eveningReport?: CockpitReportBlock | null;
  trend?: CockpitTrendPoint[];
  trace?: CockpitTraceLine[];
  dayMode: DayMode;
};

type CockpitSummarySectionProps = {
  summaryFields: CockpitSummaryField[];
  emptyText?: string;
};

type CockpitReportSectionProps = {
  morningReport?: CockpitReportBlock | null;
  eveningReport?: CockpitReportBlock | null;
  dayMode: DayMode;
  emptyText?: string;
};

type CockpitTrendSectionProps = {
  trend?: CockpitTrendPoint[];
  emptyText?: string;
};

type CockpitTraceSectionProps = {
  trace?: CockpitTraceLine[];
  emptyText?: string;
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function renderValue(value: ReactNode): ReactNode {
  if (typeof value === "string") {
    return normalizeDisplayChinese(value);
  }
  return value;
}

function ReportBlockCard({
  block,
  tone,
}: {
  block: CockpitReportBlock;
  tone: "plan" | "done";
}) {
  return (
    <div
      className={`${styles.cockpitReportCard} ${
        tone === "done" ? styles.cockpitReportCardDone : styles.cockpitReportCardPlan
      }`}
    >
      <div className={styles.cockpitReportHeader}>
        <div className={styles.cockpitReportTitle}>
          {normalizeDisplayChinese(block.title)}
        </div>
        <span className={styles.cockpitReportBadge}>
          {tone === "done" ? "完成情况" : "今日安排"}
        </span>
      </div>
      <ul className={styles.cockpitReportList}>
        {block.items.map((item) => (
          <li key={`${block.title}:${item}`} className={styles.cockpitReportItem}>
            {normalizeDisplayChinese(item)}
          </li>
        ))}
      </ul>
      {block.generatedAt ? (
        <div className={styles.cockpitReportMeta}>
          {normalizeDisplayChinese(block.generatedAt)}
        </div>
      ) : null}
    </div>
  );
}

export function CockpitSummarySection({
  summaryFields,
  emptyText = "暂时还没有可展示的摘要。",
}: CockpitSummarySectionProps) {
  if (summaryFields.length === 0) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
      </div>
    );
  }

  return (
    <div className={styles.cockpitSummaryGrid}>
      {summaryFields.map((field) => (
        <div key={field.label} className={styles.cockpitSummaryCard}>
          <div className={styles.cockpitSummaryLabel}>
            {normalizeDisplayChinese(field.label)}
          </div>
          <div className={styles.cockpitSummaryValue}>{renderValue(field.value)}</div>
          {field.hint ? (
            <div className={styles.cockpitSummaryHint}>{renderValue(field.hint)}</div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function CockpitReportSection({
  morningReport,
  eveningReport,
  dayMode,
  emptyText = "今天还没有生成日报。",
}: CockpitReportSectionProps) {
  const [showMorningAtNight, setShowMorningAtNight] = useState(false);

  if (!morningReport && !eveningReport) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
      </div>
    );
  }

  if (dayMode === "night") {
    return (
      <div className={styles.cockpitReportStack}>
        {eveningReport ? <ReportBlockCard block={eveningReport} tone="done" /> : null}
        {morningReport ? (
          <div className={styles.cockpitFoldCard}>
            <div className={styles.cockpitFoldHeader}>
              <div>
                <div className={styles.cockpitFoldTitle}>早报</div>
                <div className={styles.cockpitFoldHint}>
                  晚上默认先看完成情况，早上的计划默认收起。
                </div>
              </div>
              <Button
                size="small"
                onClick={() => setShowMorningAtNight((value) => !value)}
              >
                {showMorningAtNight ? "收起早报" : "展开早报"}
              </Button>
            </div>
            {showMorningAtNight ? (
              <div style={{ marginTop: 12 }}>
                <ReportBlockCard block={morningReport} tone="plan" />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className={styles.cockpitReportStack}>
      {morningReport ? <ReportBlockCard block={morningReport} tone="plan" /> : null}
    </div>
  );
}

export function CockpitTrendSection({
  trend,
  emptyText = "当前还没有足够的数据生成统计。",
}: CockpitTrendSectionProps) {
  const items = trend ?? [];
  if (items.length === 0) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
      </div>
    );
  }

  return (
    <div className={styles.cockpitTrendGrid}>
      {items.map((item) => (
        <div key={item.label} className={styles.cockpitTrendCard}>
          <div className={styles.cockpitTrendTop}>
            <div>
              <div className={styles.cockpitTrendLabel}>
                {normalizeDisplayChinese(item.label)}
              </div>
              <div className={styles.cockpitTrendNumber}>{item.completed}</div>
            </div>
            <Text className={styles.cockpitTrendSubLabel}>完成数量</Text>
          </div>

          <div className={styles.cockpitTrendMetric}>
            <div className={styles.cockpitTrendMetricHeader}>
              <span>完成率</span>
              <span>{`${clampPercent(item.completionRate)}%`}</span>
            </div>
            <Progress percent={clampPercent(item.completionRate)} showInfo={false} />
          </div>

          <div className={styles.cockpitTrendMetric}>
            <div className={styles.cockpitTrendMetricHeader}>
              <span>质量</span>
              <span>{`${clampPercent(item.quality)}%`}</span>
            </div>
            <Progress
              percent={clampPercent(item.quality)}
              showInfo={false}
              strokeColor="#22c55e"
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CockpitTraceSection({
  trace,
  emptyText = "今天还没有追溯日志。",
}: CockpitTraceSectionProps) {
  const items = trace ?? [];
  if (items.length === 0) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
      </div>
    );
  }

  return (
    <div className={styles.cockpitTraceList}>
      {items.map((item, index) => (
        <div
          key={`${item.timestamp}:${item.message}:${index}`}
          className={`${styles.cockpitTraceLine} ${
            item.level === "error"
              ? styles.cockpitTraceLineError
              : item.level === "warn"
                ? styles.cockpitTraceLineWarn
                : ""
          }`}
        >
          <span className={styles.cockpitTraceTime}>
            {normalizeDisplayChinese(item.timestamp)}
          </span>
          <span className={styles.cockpitTraceMessage}>
            {normalizeDisplayChinese(item.message)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function AgentWorkPanel({
  title,
  summaryFields,
  morningReport,
  eveningReport,
  trend,
  trace,
  dayMode,
}: AgentWorkPanelProps) {
  const tabItems = useMemo<TabsProps["items"]>(
    () => [
      {
        key: "summary",
        label: "简介",
        children: <CockpitSummarySection summaryFields={summaryFields} />,
      },
      {
        key: "report",
        label: "日报",
        children: (
          <CockpitReportSection
            morningReport={morningReport}
            eveningReport={eveningReport}
            dayMode={dayMode}
          />
        ),
      },
      {
        key: "stats",
        label: "统计",
        children: <CockpitTrendSection trend={trend} />,
      },
      {
        key: "trace",
        label: "追溯",
        children: <CockpitTraceSection trace={trace} />,
      },
    ],
    [dayMode, eveningReport, morningReport, summaryFields, trace, trend],
  );

  return (
    <Card className="baize-card">
      <div className={styles.panelHeader}>
        <div>
          <h2 className={styles.cardTitle}>{normalizeDisplayChinese(title)}</h2>
          <p className={styles.cardSummary}>用最少的信息看清这个智能体今天在做什么、做到了哪。</p>
        </div>
      </div>
      <Tabs defaultActiveKey="summary" items={tabItems} />
    </Card>
  );
}
