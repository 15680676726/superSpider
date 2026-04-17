import {
  Button,
  Card,
  Empty,
  Popconfirm,
  Tabs,
  type TabsProps,
} from "antd";
import { useMemo, type ReactNode } from "react";

import { normalizeDisplayChinese } from "../../text";
import {
  CockpitReportSection,
  CockpitSummarySection,
  CockpitTraceSection,
  CockpitTrendSection,
  type CockpitReportBlock,
  type CockpitSummaryField,
  type CockpitTraceLine,
  type CockpitTrendPoint,
  type DayMode,
} from "./AgentWorkPanel";
import styles from "./index.module.less";

export interface PendingApprovalItem {
  id: string;
  kind: "decision" | "patch";
  title: string;
  reason: string;
  recommendation: string;
  risk: string;
  initiator: string;
  createdAt: string;
}

export interface MainBrainStageSummary {
  title: string;
  periodLabel?: string | null;
  summary: string;
  bullets?: string[];
}

export interface MainBrainCockpitPanelProps {
  title: string;
  summaryFields: CockpitSummaryField[];
  morningReport?: CockpitReportBlock | null;
  eveningReport?: CockpitReportBlock | null;
  trend?: CockpitTrendPoint[];
  trace?: CockpitTraceLine[];
  approvals: PendingApprovalItem[];
  stageSummary?: MainBrainStageSummary | null;
  dayMode: DayMode;
  systemManagement: ReactNode;
  onApproveApproval: (approvalId: string) => void;
  onRejectApproval: (approvalId: string) => void;
  onOpenChat: (approvalId: string) => void;
}

function ApprovalList({
  approvals,
  onApproveApproval,
  onRejectApproval,
  onOpenChat,
}: Pick<
  MainBrainCockpitPanelProps,
  "approvals" | "onApproveApproval" | "onRejectApproval" | "onOpenChat"
>) {
  if (approvals.length === 0) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有待处理审批。" />
      </div>
    );
  }

  return (
    <div className={styles.approvalList}>
      {approvals.map((approval) => (
        <div key={approval.id} className={styles.approvalCard}>
          <div className={styles.approvalTop}>
            <div>
              <div className={styles.approvalTitle}>
                {normalizeDisplayChinese(approval.title)}
              </div>
              <div className={styles.approvalMeta}>
                <span>{normalizeDisplayChinese(approval.initiator)}</span>
                <span>{normalizeDisplayChinese(approval.createdAt)}</span>
              </div>
            </div>
            <span className={styles.approvalBadge}>待处理</span>
          </div>

          <div className={styles.approvalReasonBlock}>
            <div className={styles.approvalLabel}>为什么需要你决定</div>
            <p className={styles.approvalText}>{normalizeDisplayChinese(approval.reason)}</p>
          </div>

          <div className={styles.approvalReasonBlock}>
            <div className={styles.approvalLabel}>主脑建议</div>
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(approval.recommendation)}
            </p>
          </div>

          <div className={styles.approvalReasonBlock}>
            <div className={styles.approvalLabel}>不处理的影响</div>
            <p className={styles.approvalText}>{normalizeDisplayChinese(approval.risk)}</p>
          </div>

          <div className={styles.approvalActions}>
            <Popconfirm
              title="确认同意这项待处理？"
              okText="确认同意"
              cancelText="再想想"
              onConfirm={() => onApproveApproval(approval.id)}
            >
              <Button aria-label="同意" type="primary">
                同意
              </Button>
            </Popconfirm>

            <Popconfirm
              title="确认拒绝这项待处理？"
              okText="确认拒绝"
              cancelText="再想想"
              onConfirm={() => onRejectApproval(approval.id)}
            >
              <Button aria-label="拒绝" danger>
                拒绝
              </Button>
            </Popconfirm>

            <Button onClick={() => onOpenChat(approval.id)}>去聊天处理</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function StageSummarySection({
  stageSummary,
}: {
  stageSummary?: MainBrainStageSummary | null;
}) {
  if (!stageSummary) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前还没有阶段总结。" />
      </div>
    );
  }

  return (
    <div className={styles.stageSummaryCard}>
      <div className={styles.stageSummaryTop}>
        <div>
          <div className={styles.stageSummaryTitle}>
            {normalizeDisplayChinese(stageSummary.title)}
          </div>
          {stageSummary.periodLabel ? (
            <div className={styles.stageSummaryPeriod}>
              {normalizeDisplayChinese(stageSummary.periodLabel)}
            </div>
          ) : null}
        </div>
      </div>
      <p className={styles.stageSummaryText}>
        {normalizeDisplayChinese(stageSummary.summary)}
      </p>
      {stageSummary.bullets && stageSummary.bullets.length > 0 ? (
        <ul className={styles.stageSummaryList}>
          {stageSummary.bullets.map((item) => (
            <li key={item} className={styles.stageSummaryListItem}>
              {normalizeDisplayChinese(item)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default function MainBrainCockpitPanel({
  title,
  summaryFields,
  morningReport,
  eveningReport,
  trend,
  trace,
  approvals,
  stageSummary,
  dayMode,
  systemManagement,
  onApproveApproval,
  onRejectApproval,
  onOpenChat,
}: MainBrainCockpitPanelProps) {
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
      {
        key: "stage-summary",
        label: "阶段总结",
        children: <StageSummarySection stageSummary={stageSummary} />,
      },
      {
        key: "approvals",
        label: "审批",
        children: (
          <ApprovalList
            approvals={approvals}
            onApproveApproval={onApproveApproval}
            onRejectApproval={onRejectApproval}
            onOpenChat={onOpenChat}
          />
        ),
      },
      {
        key: "system-management",
        label: "系统管理",
        children: systemManagement,
      },
    ],
    [
      approvals,
      dayMode,
      eveningReport,
      morningReport,
      onApproveApproval,
      onOpenChat,
      onRejectApproval,
      stageSummary,
      summaryFields,
      systemManagement,
      trace,
      trend,
    ],
  );

  return (
    <Card className="baize-card">
      <div className={styles.panelHeader}>
        <div>
          <h2 className={styles.cardTitle}>{normalizeDisplayChinese(title)}</h2>
          <p className={styles.cardSummary}>这里展示主脑今天的统筹判断、待处理事项和系统级控制入口。</p>
        </div>
      </div>
      <Tabs defaultActiveKey="summary" items={tabItems} destroyOnHidden />
    </Card>
  );
}
