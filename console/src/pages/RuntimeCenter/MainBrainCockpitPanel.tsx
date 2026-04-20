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
import type { ResearchSessionSummary } from "./researchHelpers";
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
  researchSummary?: ResearchSessionSummary | null;
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

function ResearchSummarySection({
  researchSummary,
}: {
  researchSummary?: ResearchSessionSummary | null;
}) {
  if (!researchSummary) {
    return null;
  }
  const brief = researchSummary.brief ?? {
    goal: researchSummary.goal,
    question: null,
    whyNeeded: null,
    doneWhen: null,
    requestedSources: [],
    scopeType: null,
    scopeId: null,
  };
  const findings = researchSummary.findings ?? [];
  const sources = researchSummary.sources ?? [];
  const gaps = researchSummary.gaps ?? [];
  const conflicts = researchSummary.conflicts ?? [];
  const retrieval = researchSummary.retrieval ?? null;
  const writebackTruth = researchSummary.writebackTruth ?? null;

  return (
    <div className={styles.stageSummaryCard} style={{ marginBottom: 16 }}>
      <div className={styles.stageSummaryTop}>
        <div>
          <div className={styles.stageSummaryTitle}>研究进展</div>
          <div className={styles.stageSummaryPeriod}>
            {normalizeDisplayChinese(researchSummary.statusLabel)}
          </div>
        </div>
      </div>

      <div className={styles.approvalReasonBlock}>
        <div className={styles.approvalLabel}>当前研究目标</div>
        <p className={styles.approvalText}>{normalizeDisplayChinese(researchSummary.goal)}</p>
      </div>

      <div className={styles.approvalReasonBlock}>
        <div className={styles.approvalLabel}>轮次进展</div>
        <p className={styles.approvalText}>{normalizeDisplayChinese(researchSummary.roundLabel)}</p>
      </div>

      <div className={styles.approvalReasonBlock}>
        <div className={styles.approvalLabel}>最近状态</div>
        <p className={styles.approvalText}>
          {normalizeDisplayChinese(researchSummary.latestStatus)}
        </p>
      </div>

      {brief.question || brief.whyNeeded || brief.doneWhen ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>研究简报</div>
          {brief.question ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(brief.question)}
            </p>
          ) : null}
          {brief.whyNeeded ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(brief.whyNeeded)}
            </p>
          ) : null}
          {brief.doneWhen ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(brief.doneWhen)}
            </p>
          ) : null}
        </div>
      ) : null}

      {findings.length > 0 ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>核心发现</div>
          <ul className={styles.stageSummaryList}>
            {findings.map((item) => (
              <li key={item.id} className={styles.stageSummaryListItem}>
                {normalizeDisplayChinese(item.summary)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {sources.length > 0 ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>来源</div>
          <ul className={styles.stageSummaryList}>
            {sources.map((item) => (
              <li key={item.id} className={styles.stageSummaryListItem}>
                {normalizeDisplayChinese(item.title)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {retrieval ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>检索摘要</div>
          {retrieval.intent ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(retrieval.intent)}
            </p>
          ) : null}
          {retrieval.requestedSources.length > 0 ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(retrieval.requestedSources.join(" / "))}
            </p>
          ) : null}
          {retrieval.modeSequence.length > 0 ? (
            <p className={styles.approvalText}>
              {normalizeDisplayChinese(retrieval.modeSequence.join(" -> "))}
            </p>
          ) : null}
          {retrieval.selectedHits.length > 0 ? (
            <ul className={styles.stageSummaryList}>
              {retrieval.selectedHits.map((item) => (
                <li key={item.id} className={styles.stageSummaryListItem}>
                  {normalizeDisplayChinese(item.title)}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {gaps.length > 0 ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>缺口</div>
          <ul className={styles.stageSummaryList}>
            {gaps.map((item) => (
              <li key={item} className={styles.stageSummaryListItem}>
                {normalizeDisplayChinese(item)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {conflicts.length > 0 ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>冲突</div>
          <ul className={styles.stageSummaryList}>
            {conflicts.map((item) => (
              <li key={item} className={styles.stageSummaryListItem}>
                {normalizeDisplayChinese(item)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {writebackTruth ? (
        <div className={styles.approvalReasonBlock}>
          <div className={styles.approvalLabel}>回写真相</div>
          <p className={styles.approvalText}>
            {normalizeDisplayChinese(writebackTruth.statusLabel)}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default function MainBrainCockpitPanel({
  title,
  researchSummary,
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
      <ResearchSummarySection researchSummary={researchSummary} />
      <Tabs defaultActiveKey="summary" items={tabItems} destroyOnHidden />
    </Card>
  );
}
