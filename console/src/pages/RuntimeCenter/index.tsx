import { Alert, Button, Card, Empty, Space, Tag, message } from "antd";
import { RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../../api";
import type {
  RuntimeHumanCockpitApproval,
  RuntimeHumanCockpitCard,
  RuntimeHumanCockpitReportBlock,
  RuntimeHumanCockpitStageSummary,
  RuntimeHumanCockpitSummaryField,
  RuntimeHumanCockpitTrendPoint,
  RuntimeMainBrainRecord,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import { PageHeader } from "../../components/PageHeader";
import { normalizeDisplayChinese } from "../../text";
import {
  presentExecutionActorName,
  presentRuntimeStatusLabel,
} from "../../runtime/executionPresentation";
import { runtimeStatusColor } from "../../runtime/tagSemantics";
import AgentCardStrip, { type AgentCardStripItem } from "./AgentCardStrip";
import AgentWorkPanel, {
  type CockpitReportBlock,
  type CockpitSummaryField,
  type CockpitTrendPoint,
  type DayMode,
} from "./AgentWorkPanel";
import MainBrainCockpitPanel, {
  type MainBrainStageSummary,
  type PendingApprovalItem,
} from "./MainBrainCockpitPanel";
import MainBrainSystemManagement from "./MainBrainSystemManagement";
import styles from "./index.module.less";
import {
  useRuntimeCenter,
  type RuntimeCenterAgentSummary,
} from "./useRuntimeCenter";
import { formatTimestamp, renderDetailDrawer } from "./viewHelpers";

const MAIN_BRAIN_ID = "main-brain";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function firstText(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return normalizeDisplayChinese(value.trim());
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
    if (isRecord(value)) {
      const nested = firstText(
        value.title,
        value.headline,
        value.label,
        value.name,
        value.summary,
        value.description,
        value.detail,
        value.reason,
        value.status,
        value.value,
      );
      if (nested) {
        return nested;
      }
    }
  }
  return null;
}

function buildList(...values: Array<string | null | undefined>): string[] {
  return Array.from(
    new Set(values.map((item) => item?.trim()).filter((item): item is string => Boolean(item))),
  );
}

function resolveDayMode(now = new Date()): DayMode {
  const hour = now.getHours();
  return hour >= 18 || hour < 6 ? "night" : "day";
}

function statusNeedsAttention(status?: string | null): boolean {
  const normalized = typeof status === "string" ? status.trim().toLowerCase() : "";
  return [
    "blocked",
    "error",
    "failed",
    "pending",
    "open",
    "reviewing",
    "waiting",
    "human-required",
    "waiting-confirm",
  ].some((token) => normalized.includes(token));
}

function progressFromStatus(status?: string | null): number {
  const normalized = typeof status === "string" ? status.trim().toLowerCase() : "";
  if (["completed", "done", "approved", "applied"].includes(normalized)) {
    return 100;
  }
  if (["running", "executing", "active", "claimed"].includes(normalized)) {
    return 72;
  }
  if (["queued", "assigned", "waiting", "open", "pending"].includes(normalized)) {
    return 36;
  }
  if (["reviewing", "paused"].includes(normalized)) {
    return 54;
  }
  if (["blocked", "error", "failed"].includes(normalized)) {
    return 18;
  }
  return 48;
}

function reportBlock(title: string, items: Array<string | null | undefined>): CockpitReportBlock | null {
  const lines = buildList(...items).slice(0, 3);
  if (lines.length === 0) {
    return null;
  }
  return {
    title,
    items: lines,
  };
}

function metricPoint(
  label: string,
  completed: number,
  completionRate: number,
  quality: number,
): CockpitTrendPoint {
  return {
    label,
    completed,
    completionRate: Math.max(0, Math.min(100, Math.round(completionRate))),
    quality: Math.max(0, Math.min(100, Math.round(quality))),
  };
}

function matchesAgent(record: RuntimeMainBrainRecord, agentId: string): boolean {
  return (
    firstText(record.owner_agent_id, record.agent_id, record.owner) === agentId ||
    firstText(record.owner_agent_name) === agentId
  );
}

function pickLatestRecord<T extends RuntimeMainBrainRecord>(
  records: T[] | null | undefined,
): T | undefined {
  let latest: T | undefined;
  let latestSortKey = "";
  for (const record of records ?? []) {
    const sortKey =
      firstText(
        record.updated_at,
        record.created_at,
        record.recorded_at,
        record.generated_at,
      ) ?? "";
    if (!latest || sortKey > latestSortKey) {
      latest = record;
      latestSortKey = sortKey;
    }
  }
  return latest;
}

function buildMainBrainSummaryFields(
  mainBrainData: RuntimeMainBrainResponse | null,
  approvals: PendingApprovalItem[],
): CockpitSummaryField[] {
  if (!mainBrainData) {
    return [
      {
        label: "职责",
        value: "负责统筹安排、跟进进度、收结果、把需要你决定的事情提出来。",
      },
      {
        label: "当前重点",
        value: "正在等待主脑运行数据。",
      },
    ];
  }

  return [
    {
      label: "职责",
      value:
        firstText(mainBrainData.strategy?.summary) ||
        "负责统筹安排、跟进进度、收结果、把需要你决定的事情提出来。",
    },
    {
      label: "当前重点",
      value:
        firstText(
          mainBrainData.report_cognition?.next_action?.title,
          mainBrainData.report_cognition?.next_action?.summary,
          mainBrainData.current_cycle?.title,
          mainBrainData.current_cycle?.summary,
        ) || "今天还没有新的主脑重点。",
    },
    {
      label: "今日进展",
      value: `已派工 ${mainBrainData.assignments.length} 项，已回收 ${mainBrainData.reports.length} 份汇报，新增 ${mainBrainData.evidence.count} 条证据。`,
    },
    {
      label: "需要你决定",
      value:
        approvals.length > 0
          ? `当前有 ${approvals.length} 项待处理。`
          : "当前没有必须你立刻决定的事项。",
    },
  ];
}

function buildMainBrainReports(
  mainBrainData: RuntimeMainBrainResponse | null,
): { morningReport: CockpitReportBlock | null; eveningReport: CockpitReportBlock | null } {
  if (!mainBrainData) {
    return { morningReport: null, eveningReport: null };
  }

  const morningReport = reportBlock("早报", [
    firstText(mainBrainData.current_cycle?.summary, mainBrainData.current_cycle?.title),
    firstText(
      mainBrainData.report_cognition?.next_action?.summary,
      mainBrainData.report_cognition?.next_action?.title,
    ),
    `今天主脑需要盯住 ${mainBrainData.assignments.length} 项执行任务。`,
  ]);

  const latestReport = pickLatestRecord(mainBrainData.reports);
  const eveningReport = reportBlock("晚报", [
    firstText(latestReport?.headline, latestReport?.summary),
    `今天共收到 ${mainBrainData.reports.length} 份汇报。`,
    `今天新增 ${mainBrainData.evidence.count} 条证据。`,
    mainBrainData.decisions.count > 0
      ? `还有 ${mainBrainData.decisions.count} 项待你确认。`
      : null,
  ]);

  return { morningReport, eveningReport };
}

function buildMainBrainTrend(
  mainBrainData: RuntimeMainBrainResponse | null,
  approvals: PendingApprovalItem[],
): CockpitTrendPoint[] {
  if (!mainBrainData) {
    return [];
  }

  const approvalPressure = approvals.length === 0 ? 92 : Math.max(30, 100 - approvals.length * 18);
  return [
    metricPoint(
      "派工",
      mainBrainData.assignments.length,
      mainBrainData.assignments.length > 0 ? 78 : 24,
      82,
    ),
    metricPoint(
      "汇报",
      mainBrainData.reports.length,
      mainBrainData.reports.length > 0 ? 84 : 28,
      80,
    ),
    metricPoint(
      "证据",
      mainBrainData.evidence.count,
      mainBrainData.evidence.count > 0 ? 88 : 20,
      approvalPressure,
    ),
  ];
}

function buildStageSummary(mainBrainData: RuntimeMainBrainResponse | null): MainBrainStageSummary | null {
  if (!mainBrainData) {
    return null;
  }

  const bullets = buildList(
    mainBrainData.assignments.length > 0
      ? `当前阶段已经派出 ${mainBrainData.assignments.length} 项执行任务。`
      : null,
    mainBrainData.reports.length > 0
      ? `已回收 ${mainBrainData.reports.length} 份执行汇报。`
      : null,
    mainBrainData.evidence.count > 0
      ? `已有 ${mainBrainData.evidence.count} 条证据进入系统。`
      : null,
    firstText(
      mainBrainData.report_cognition?.replan_reasons?.[0],
      mainBrainData.report_cognition?.judgment?.summary,
    ),
  );

  if (bullets.length === 0) {
    return null;
  }

  return {
    title: firstText(mainBrainData.current_cycle?.title) || "当前阶段汇总",
    periodLabel: "当前周期",
    summary:
      firstText(
        mainBrainData.current_cycle?.summary,
        mainBrainData.strategy?.summary,
        mainBrainData.report_cognition?.next_action?.summary,
      ) || "主脑正在持续收口当前阶段结果。",
    bullets,
  };
}

function buildApprovalItems(mainBrainData: RuntimeMainBrainResponse | null): PendingApprovalItem[] {
  if (!mainBrainData) {
    return [];
  }

  return (mainBrainData.decisions.entries ?? [])
    .map((entry) => {
      const route = firstText(entry.route);
      const kind: "decision" | "patch" =
        route?.includes("patch") || firstText(entry.kind)?.toLowerCase() === "patch"
          ? "patch"
          : "decision";
      const id =
        firstText(entry.id, entry.decision_id, entry.patch_id, entry.title) ??
        `${kind}-${Math.random().toString(36).slice(2, 8)}`;
      return {
        id,
        kind,
        title: firstText(entry.title, entry.headline) || "待处理事项",
        reason:
          firstText(entry.summary, entry.reason, entry.detail) || "主脑判断这件事需要你拍板。",
        recommendation:
          kind === "patch"
            ? "建议先确认是否允许应用这次变更。"
            : "建议先确认是否现在执行这项决定。",
        risk:
          firstText(entry.risk, entry.impact) || "如果继续搁置，当前推进会继续往后顺延。",
        initiator: firstText(entry.owner, entry.initiator) || "主脑",
        createdAt: firstText(entry.created_at, entry.updated_at) || "刚刚",
      };
    })
    .filter((item) => item.title);
}

function buildMainBrainCard(
  mainBrainData: RuntimeMainBrainResponse | null,
  pendingApprovals: PendingApprovalItem[],
  buddyName?: string | null,
  loading?: boolean,
  error?: string | null,
  unavailable?: boolean,
): AgentCardStripItem {
  let status = "running";
  if (error) {
    status = "blocked";
  } else if (loading) {
    status = "queued";
  } else if (unavailable) {
    status = "idle";
  } else if (pendingApprovals.length > 0) {
    status = "reviewing";
  }

  const progress =
    mainBrainData == null
      ? progressFromStatus(status)
      : Math.min(96, 40 + mainBrainData.reports.length * 12 + mainBrainData.evidence.count * 8);

  return {
    id: MAIN_BRAIN_ID,
    name: normalizeDisplayChinese(buddyName || "伙伴"),
    role: "主脑",
    status,
    progress,
    needsAttention: Boolean(error) || pendingApprovals.length > 0,
    isMainBrain: true,
  };
}

function buildAgentCard(agent: RuntimeCenterAgentSummary, mainBrainData: RuntimeMainBrainResponse | null): AgentCardStripItem {
  const reports =
    mainBrainData?.reports.filter((record) => matchesAgent(record, agent.agent_id)) ?? [];
  const assignments =
    mainBrainData?.assignments.filter((record) => matchesAgent(record, agent.agent_id)) ?? [];

  const attention = statusNeedsAttention(agent.status) || reports.some((item) => statusNeedsAttention(firstText(item.status)));
  const progressBase = progressFromStatus(agent.status);
  const progressBoost = Math.min(24, assignments.length * 12 + reports.length * 10);

  return {
    id: agent.agent_id,
    name: presentExecutionActorName(agent.agent_id, agent.name),
    role: normalizeDisplayChinese(agent.role_name || "职业智能体"),
    status: agent.status || "idle",
    progress: Math.min(100, progressBase + progressBoost),
    needsAttention: attention,
  };
}

function buildAgentSummaryFields(
  agent: RuntimeCenterAgentSummary,
  mainBrainData: RuntimeMainBrainResponse | null,
): CockpitSummaryField[] {
  const relatedAssignment = pickLatestRecord(
    mainBrainData?.assignments.filter((record) => matchesAgent(record, agent.agent_id)),
  );
  const relatedReport = pickLatestRecord(
    mainBrainData?.reports.filter((record) => matchesAgent(record, agent.agent_id)),
  );

  return [
    {
      label: "职业",
      value: agent.role_name || "职业智能体",
    },
    {
      label: "职责",
      value: agent.role_summary || "负责对应岗位的执行与结果回传。",
    },
    {
      label: "主要负责工作",
      value:
        firstText(
          agent.current_focus,
          relatedAssignment?.summary,
          relatedAssignment?.title,
          relatedReport?.headline,
        ) || "当前还没有明确展示的工作重点。",
    },
    {
      label: "当前状态",
      value: presentRuntimeStatusLabel(agent.status),
    },
  ];
}

function buildAgentReports(
  agent: RuntimeCenterAgentSummary,
  mainBrainData: RuntimeMainBrainResponse | null,
): { morningReport: CockpitReportBlock | null; eveningReport: CockpitReportBlock | null } {
  const relatedAssignment = pickLatestRecord(
    mainBrainData?.assignments.filter((record) => matchesAgent(record, agent.agent_id)),
  );
  const relatedReport = pickLatestRecord(
    mainBrainData?.reports.filter((record) => matchesAgent(record, agent.agent_id)),
  );

  const morningReport = reportBlock("早报", [
    firstText(agent.current_focus),
    firstText(relatedAssignment?.summary, relatedAssignment?.title),
    agent.role_summary ? `今天继续推进：${agent.role_summary}` : null,
  ]);

  const eveningReport = reportBlock("晚报", [
    firstText(relatedReport?.headline, relatedReport?.summary),
    relatedReport ? `当前结果状态：${firstText(relatedReport.result, relatedReport.status) || "推进中"}` : null,
    relatedReport && firstText(relatedReport.updated_at)
      ? `最后回传时间：${firstText(relatedReport.updated_at)}`
      : null,
  ]);

  return { morningReport, eveningReport };
}

function buildAgentTrend(
  agent: RuntimeCenterAgentSummary,
  mainBrainData: RuntimeMainBrainResponse | null,
): CockpitTrendPoint[] {
  const relatedAssignments =
    mainBrainData?.assignments.filter((record) => matchesAgent(record, agent.agent_id)) ?? [];
  const relatedReports =
    mainBrainData?.reports.filter((record) => matchesAgent(record, agent.agent_id)) ?? [];
  const completedCount = relatedAssignments.filter(
    (record) => firstText(record.status)?.toLowerCase() === "completed",
  ).length;

  const baseCompletion = progressFromStatus(agent.status);
  const feedbackQuality = relatedReports.length > 0 ? 84 : 45;
  const continuity = statusNeedsAttention(agent.status) ? 42 : 88;

  return [
    metricPoint("任务完成", completedCount || relatedAssignments.length, baseCompletion, feedbackQuality),
    metricPoint("结果回传", relatedReports.length, relatedReports.length > 0 ? 82 : 30, feedbackQuality),
    metricPoint("协作连贯", continuity >= 80 ? 1 : 0, continuity, continuity),
  ];
}

function mapCockpitCard(card: RuntimeHumanCockpitCard): AgentCardStripItem {
  return {
    id: card.id,
    name: card.name,
    role: card.role,
    status: card.status,
    progress: card.progress,
    needsAttention: card.needs_attention,
    isMainBrain: card.is_main_brain,
  };
}

function mapCockpitSummaryFields(
  fields: RuntimeHumanCockpitSummaryField[] | undefined,
): CockpitSummaryField[] {
  return (fields ?? []).map((field) => ({
    label: field.label,
    value: field.value,
    hint: field.hint ?? undefined,
  }));
}

function mapCockpitReportBlock(
  block: RuntimeHumanCockpitReportBlock | null | undefined,
): CockpitReportBlock | null {
  if (!block) {
    return null;
  }
  return {
    title: block.title,
    items: block.items,
    generatedAt: block.generated_at ?? undefined,
  };
}

function mapCockpitTrend(
  trend: RuntimeHumanCockpitTrendPoint[] | undefined,
): CockpitTrendPoint[] {
  return (trend ?? []).map((item) => ({
    label: item.label,
    completed: item.completed,
    completionRate: item.completion_rate,
    quality: item.quality,
  }));
}

function mapCockpitApprovals(
  approvals: RuntimeHumanCockpitApproval[] | undefined,
): PendingApprovalItem[] {
  return (approvals ?? []).map((item) => ({
    id: item.id,
    kind: item.kind,
    title: item.title,
    reason: item.reason,
    recommendation: item.recommendation,
    risk: item.risk,
    initiator: item.initiator,
    createdAt: item.created_at,
  }));
}

function mapCockpitStageSummary(
  summary: RuntimeHumanCockpitStageSummary | null | undefined,
): MainBrainStageSummary | null {
  if (!summary) {
    return null;
  }
  return {
    title: summary.title,
    periodLabel: summary.period_label ?? undefined,
    summary: summary.summary,
    bullets: summary.bullets ?? [],
  };
}

export default function RuntimeCenterPage() {
  const navigate = useNavigate();
  const {
    data,
    loading,
    refreshing,
    error,
    buddySummary,
    mainBrainData,
    mainBrainError,
    mainBrainLoading,
    mainBrainUnavailable,
    businessAgents,
    detail,
    detailLoading,
    detailError,
    reload,
    openDetail,
    closeDetail,
  } = useRuntimeCenter();

  const [selectedId, setSelectedId] = useState(MAIN_BRAIN_ID);
  const dayMode = useMemo(() => resolveDayMode(), []);

  const cockpit = mainBrainData?.cockpit ?? null;
  const cockpitMainBrain = cockpit?.main_brain ?? null;
  const cockpitAgents = cockpit?.agents ?? [];

  const approvals = useMemo(
    () =>
      cockpitMainBrain
        ? mapCockpitApprovals(cockpitMainBrain.approvals)
        : buildApprovalItems(mainBrainData),
    [cockpitMainBrain, mainBrainData],
  );
  const mainBrainCard = useMemo(
    () =>
      cockpitMainBrain
        ? mapCockpitCard(cockpitMainBrain.card)
        : buildMainBrainCard(
            mainBrainData,
            approvals,
            buddySummary?.buddy_name,
            mainBrainLoading,
            mainBrainError,
            mainBrainUnavailable,
          ),
    [
      cockpitMainBrain,
      approvals,
      buddySummary?.buddy_name,
      mainBrainData,
      mainBrainError,
      mainBrainLoading,
      mainBrainUnavailable,
    ],
  );

  const agentCards = useMemo<AgentCardStripItem[]>(
    () =>
      cockpitAgents.length > 0
        ? [mainBrainCard, ...cockpitAgents.map((agent) => mapCockpitCard(agent.card))]
        : [
            mainBrainCard,
            ...businessAgents.map((agent) => buildAgentCard(agent, mainBrainData)),
          ],
    [businessAgents, cockpitAgents, mainBrainCard, mainBrainData],
  );

  useEffect(() => {
    const validIds = new Set(agentCards.map((item) => item.id));
    if (!validIds.has(selectedId)) {
      setSelectedId(MAIN_BRAIN_ID);
    }
  }, [agentCards, selectedId]);

  const selectedLegacyAgent = useMemo(
    () => businessAgents.find((agent) => agent.agent_id === selectedId) ?? null,
    [businessAgents, selectedId],
  );
  const selectedCockpitAgent = useMemo(
    () => cockpitAgents.find((agent) => agent.agent_id === selectedId) ?? null,
    [cockpitAgents, selectedId],
  );
  const visibleAgentCount = cockpitAgents.length > 0 ? cockpitAgents.length : businessAgents.length;

  const headerStats = useMemo(
    () => [
      {
        label: "今日推进",
        value: String(mainBrainData?.assignments.length ?? visibleAgentCount).padStart(2, "0"),
      },
      {
        label: "待你决定",
        value: String(approvals.length).padStart(2, "0"),
      },
      {
        label: "结果回传",
        value: String((mainBrainData?.reports.length ?? 0) + (mainBrainData?.evidence.count ?? 0)).padStart(2, "0"),
      },
    ],
    [approvals.length, mainBrainData?.assignments.length, mainBrainData?.evidence.count, mainBrainData?.reports.length, visibleAgentCount],
  );

  const mainBrainSummaryFields = useMemo(
    () =>
      cockpitMainBrain
        ? mapCockpitSummaryFields(cockpitMainBrain.summary_fields)
        : buildMainBrainSummaryFields(mainBrainData, approvals),
    [approvals, cockpitMainBrain, mainBrainData],
  );
  const mainBrainReports = useMemo(
    () =>
      cockpitMainBrain
        ? {
            morningReport: mapCockpitReportBlock(cockpitMainBrain.morning_report),
            eveningReport: mapCockpitReportBlock(cockpitMainBrain.evening_report),
          }
        : buildMainBrainReports(mainBrainData),
    [cockpitMainBrain, mainBrainData],
  );
  const mainBrainTrend = useMemo(
    () =>
      cockpitMainBrain
        ? mapCockpitTrend(cockpitMainBrain.trend)
        : buildMainBrainTrend(mainBrainData, approvals),
    [approvals, cockpitMainBrain, mainBrainData],
  );
  const stageSummary = useMemo(
    () =>
      cockpitMainBrain
        ? mapCockpitStageSummary(cockpitMainBrain.stage_summary)
        : buildStageSummary(mainBrainData),
    [cockpitMainBrain, mainBrainData],
  );

  const openSurfaceRoute = async (route: string, title: string) => {
    if (route.startsWith("/api/")) {
      await openDetail(route, title);
      return;
    }
    navigate(route);
  };

  const handleApprovalAction = async (
    approvalId: string,
    action: "approve" | "reject",
  ) => {
    const target = approvals.find((item) => item.id === approvalId);
    if (!target) {
      return;
    }

    try {
      if (target.kind === "patch") {
        if (action === "approve") {
          await api.approveRuntimePatches({ patch_ids: [approvalId], actor: "runtime-center" });
        } else {
          await api.rejectRuntimePatches({ patch_ids: [approvalId], actor: "runtime-center" });
        }
      } else if (action === "approve") {
        await api.approveRuntimeDecisions({
          decision_ids: [approvalId],
          actor: "runtime-center",
          resolution: "驾驶舱批准",
          execute: true,
        });
      } else {
        await api.rejectRuntimeDecisions({
          decision_ids: [approvalId],
          actor: "runtime-center",
          resolution: "驾驶舱拒绝",
        });
      }

      message.success(action === "approve" ? "已提交同意" : "已提交拒绝");
      await reload();
    } catch (actionError) {
      message.error(
        normalizeDisplayChinese(
          actionError instanceof Error ? actionError.message : String(actionError),
        ),
      );
    }
  };

  const renderSelectedPanel = () => {
    if (selectedId === MAIN_BRAIN_ID) {
      return (
        <MainBrainCockpitPanel
          title={`${mainBrainCard.name}（主脑）`}
          summaryFields={mainBrainSummaryFields}
          morningReport={mainBrainReports.morningReport}
          eveningReport={mainBrainReports.eveningReport}
          trend={mainBrainTrend}
          approvals={approvals}
          stageSummary={stageSummary}
          dayMode={dayMode}
          systemManagement={
            <MainBrainSystemManagement
              refreshSignal={data?.generated_at ?? null}
              onOpenDetail={(route, title) => {
                void openSurfaceRoute(route, title);
              }}
              onRuntimeChanged={() => {
                void reload();
              }}
            />
          }
          onApproveApproval={(approvalId) => {
            void handleApprovalAction(approvalId, "approve");
          }}
          onRejectApproval={(approvalId) => {
            void handleApprovalAction(approvalId, "reject");
          }}
          onOpenChat={() => {
            navigate("/chat");
          }}
        />
      );
    }

    if (!selectedCockpitAgent && !selectedLegacyAgent) {
      return (
        <Card className="baize-card">
          <div className={styles.cockpitEmptyWrap}>
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂时找不到这个智能体。" />
          </div>
        </Card>
      );
    }

    if (selectedCockpitAgent) {
      return (
        <AgentWorkPanel
          title={selectedCockpitAgent.card.name}
          summaryFields={mapCockpitSummaryFields(selectedCockpitAgent.summary_fields)}
          morningReport={mapCockpitReportBlock(selectedCockpitAgent.morning_report)}
          eveningReport={mapCockpitReportBlock(selectedCockpitAgent.evening_report)}
          trend={mapCockpitTrend(selectedCockpitAgent.trend)}
          dayMode={dayMode}
        />
      );
    }

    const legacyAgent = selectedLegacyAgent;
    if (!legacyAgent) {
      return null;
    }

    const summaryFields = buildAgentSummaryFields(legacyAgent, mainBrainData);
    const reports = buildAgentReports(legacyAgent, mainBrainData);
    const trend = buildAgentTrend(legacyAgent, mainBrainData);

    return (
      <AgentWorkPanel
        title={presentExecutionActorName(legacyAgent.agent_id, legacyAgent.name)}
        summaryFields={summaryFields}
        morningReport={reports.morningReport}
        eveningReport={reports.eveningReport}
        trend={trend}
        dayMode={dayMode}
      />
    );
  };

  return (
    <div className={`${styles.page} page-container`}>
      <PageHeader
        eyebrow="主脑驾驶舱"
        title="运行中心"
        description="先看今天谁在推进、推进到了哪、有没有需要你决定的事情。"
        stats={headerStats}
        aside={
          <span style={{ fontSize: 12, color: "var(--baize-text-muted)" }}>
            {data?.generated_at ? formatTimestamp(data.generated_at) : "等待运行数据"}
          </span>
        }
        actions={
          <Space size={12} wrap>
            <Tag color={runtimeStatusColor(mainBrainCard.status)}>
              {presentRuntimeStatusLabel(mainBrainCard.status)}
            </Tag>
            <Button
              className="baize-btn baize-btn-primary"
              icon={<RefreshCw size={16} />}
              loading={refreshing || loading || mainBrainLoading}
              onClick={() => {
                void reload();
              }}
            >
              刷新
            </Button>
          </Space>
        }
      />

      {!data && error ? <Alert showIcon type="error" message={error} /> : null}
      {mainBrainError ? <Alert showIcon type="warning" message={mainBrainError} /> : null}

      <Card className="baize-card">
        <div className={styles.panelHeader}>
          <div>
            <h2 className={styles.cardTitle}>今日协作总览</h2>
            <p className={styles.cardSummary}>
              上面选智能体，下面直接看它的简介、日报和统计。默认先看主脑。
            </p>
          </div>
          <Space size={8} wrap>
            <Tag>{`职业智能体 ${visibleAgentCount}`}</Tag>
            {approvals.length > 0 ? <Tag color="gold">{`待处理 ${approvals.length}`}</Tag> : null}
          </Space>
        </div>

        <AgentCardStrip
          agents={agentCards}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </Card>

      {renderSelectedPanel()}

      {renderDetailDrawer(
        detail,
        detailLoading,
        detailError,
        closeDetail,
        (route, title) => {
          void openSurfaceRoute(route, title);
        },
      )}
    </div>
  );
}
