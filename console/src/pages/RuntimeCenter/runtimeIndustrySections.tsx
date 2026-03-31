import { Alert, Button, Card, Space, Tag, Typography } from "antd";

import type {
  IndustryInstanceDetail,
  IndustryMainChainGraph,
} from "../../api/modules/industry";
import { presentControlChain } from "../../runtime/controlChainPresentation";
import { buildStaffingPresentation } from "../../runtime/staffingGapPresentation";
import {
  runtimeRiskColor,
  runtimeRiskLabel,
  runtimeStatusColor,
} from "../../runtime/tagSemantics";
import styles from "./index.module.less";
import {
  formatPrimitiveValue,
  formatMainBrainSignalLabel,
  formatRuntimeFieldLabel,
  formatRuntimeSectionLabel as translateRuntimeSectionLabel,
  formatRuntimeStatus as translateRuntimeStatus,
  localizeRuntimeText,
} from "./text";
import {
  findChainNode,
  findIndustryAgentRoute,
  isIndustryExecutionSummary,
  isIndustryMainChainGraph,
  isRecord,
  metaNumberValue,
  metaStringValue,
  stringListValue,
} from "./runtimeDetailPrimitives";
export {
  renderOperatorAgentReportsSection,
  renderOperatorAssignmentsSection,
  renderOperatorBacklogSection,
  renderOperatorMediaAnalysesSection,
} from "./runtimeIndustryOperatorSections";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";

const { Text } = Typography;

function nonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

type IndustryCycleSynthesis = NonNullable<
  NonNullable<IndustryInstanceDetail["current_cycle"]>["synthesis"]
>;
type IndustrySynthesisFinding = IndustryCycleSynthesis["latest_findings"][number];
type IndustrySynthesisConflict = IndustryCycleSynthesis["conflicts"][number];
type IndustrySynthesisHole = IndustryCycleSynthesis["holes"][number];
type IndustrySynthesisAction = IndustryCycleSynthesis["recommended_actions"][number];

function renderSynthesisFollowupList(
  findings: IndustrySynthesisFinding[],
  keySuffix: string,
) {
  if (findings.length === 0) {
    return null;
  }
  return (
    <Space direction="vertical" size={4} style={{ width: "100%" }}>
      {findings.slice(0, 3).map((finding, index) => {
        const findingKey = finding.report_id
          ? `${finding.report_id}:${keySuffix}`
          : `${keySuffix}:${index}`;
        return (
          <Space
            key={findingKey}
            direction="vertical"
            size={0}
            style={{ width: "100%" }}
          >
            <Text type="secondary">
              {String(finding.headline || finding.summary || finding.report_id)}
            </Text>
            {nonEmpty(finding.followup_reason) ? (
              <Text type="secondary">{nonEmpty(finding.followup_reason)}</Text>
            ) : null}
          </Space>
        );
      })}
    </Space>
  );
}

function renderMainBrainPlanningSection({
  payload,
  lanes,
  visibleLanes,
  focusedLaneIds,
  followupReports,
  pendingSignalCount,
  strategySummary,
  synthesisFollowups,
}: {
  payload: IndustryInstanceDetail;
  lanes: IndustryInstanceDetail["lanes"];
  visibleLanes: IndustryInstanceDetail["lanes"];
  focusedLaneIds: Set<string>;
  followupReports: IndustryInstanceDetail["agent_reports"];
  pendingSignalCount: number;
  strategySummary: string | null;
  synthesisFollowups: IndustrySynthesisFinding[];
}) {
  return (
    <Card size="small" title="Main-Brain Planning" style={{ marginTop: 16 }}>
      <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
        <Tag>{`Lanes ${lanes.length}`}</Tag>
        <Tag>{`派工 ${payload.assignments.length}`}</Tag>
        <Tag>{`汇报 ${payload.agent_reports.length}`}</Tag>
        {followupReports.length > 0 ? (
          <Tag color="warning">{`跟进 ${followupReports.length}`}</Tag>
        ) : null}
        {payload.staffing?.pending_proposals.length ? (
          <Tag>{`Staffing proposals ${payload.staffing.pending_proposals.length}`}</Tag>
        ) : null}
        {payload.staffing?.temporary_seats.length ? (
          <Tag>{`Temporary seats ${payload.staffing.temporary_seats.length}`}</Tag>
        ) : null}
        {pendingSignalCount > 0 ? (
          <Tag color="warning">{`Pending signals ${pendingSignalCount}`}</Tag>
        ) : null}
        {payload.current_cycle?.status ? (
          <Tag color={runtimeStatusColor(payload.current_cycle.status)}>
            {translateRuntimeStatus(payload.current_cycle.status)}
          </Tag>
        ) : null}
      </Space>
      <Text type="secondary">
        {strategySummary || "当前还没有策略摘要。"}
      </Text>
      {payload.current_cycle ? (
        <div style={{ marginTop: 10 }}>
          <Text strong>{payload.current_cycle.title || "Current cycle"}</Text>
          {payload.current_cycle.summary ? (
            <div style={{ marginTop: 4 }}>
              <Text type="secondary">{payload.current_cycle.summary}</Text>
            </div>
          ) : null}
        </div>
      ) : null}
      {visibleLanes.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <div className={styles.detailSectionTitle}>运行泳道</div>
          <Space wrap size={[6, 6]}>
            {visibleLanes.map((lane) => (
              <Tag
                key={lane.lane_id}
                color={
                  focusedLaneIds.has(lane.lane_id)
                    ? "blue"
                    : runtimeStatusColor(lane.status || "unknown")
                }
              >
                {lane.title || lane.lane_id}
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}
      {followupReports.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <div className={styles.detailSectionTitle}>待处理汇报跟进</div>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            {followupReports.slice(0, 3).map((report) => (
              <Text key={report.report_id} type="secondary">
                {String(report.headline || report.summary || report.report_id)}
              </Text>
            ))}
          </Space>
        </div>
      ) : null}
      {synthesisFollowups.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <div className={styles.detailSectionTitle}>主管跟进</div>
          {renderSynthesisFollowupList(synthesisFollowups, "planning")}
        </div>
      ) : null}
    </Card>
  );
}

function renderMainBrainSynthesisSection({
  cycleSynthesis,
  synthesisFindings,
  synthesisConflicts,
  synthesisHoles,
  synthesisFollowups,
  recommendedActions,
  controlCoreContract,
  synthesisSummary,
}: {
  cycleSynthesis: IndustryCycleSynthesis | null | undefined;
  synthesisFindings: IndustrySynthesisFinding[];
  synthesisConflicts: IndustrySynthesisConflict[];
  synthesisHoles: IndustrySynthesisHole[];
  synthesisFollowups: IndustrySynthesisFinding[];
  recommendedActions: IndustrySynthesisAction[];
  controlCoreContract: string[];
  synthesisSummary: string;
}) {
  return (
    <Card size="small" title="主脑综合" style={{ marginTop: 16 }}>
      <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
        <Tag>{`发现 ${synthesisFindings.length}`}</Tag>
        <Tag color={synthesisConflicts.length > 0 ? "error" : "default"}>
          {`冲突 ${synthesisConflicts.length}`}
        </Tag>
        <Tag color={synthesisHoles.length > 0 ? "warning" : "default"}>
          {`缺口 ${synthesisHoles.length}`}
        </Tag>
        {cycleSynthesis?.needs_replan ? <Tag color="error">需要重规划</Tag> : null}
      </Space>
      <Text type="secondary">{synthesisSummary}</Text>
      {synthesisConflicts.length > 0 ? (
        <>
          <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
            冲突
          </div>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            {synthesisConflicts.slice(0, 3).map((conflict) => (
              <Text key={conflict.conflict_id} type="secondary">
                {String(conflict.summary || conflict.conflict_id)}
              </Text>
            ))}
          </Space>
        </>
      ) : null}
      {synthesisFollowups.length > 0 ? (
        <>
          <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
            主管跟进
          </div>
          {renderSynthesisFollowupList(synthesisFollowups, "synthesis")}
        </>
      ) : null}
      {synthesisHoles.length > 0 ? (
        <>
          <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
            缺口 / 跟进
          </div>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            {synthesisHoles.slice(0, 3).map((hole) => (
              <Text key={hole.hole_id} type="secondary">
                {String(hole.summary || hole.hole_id)}
              </Text>
            ))}
          </Space>
        </>
      ) : null}
      {recommendedActions.length > 0 ? (
        <>
          <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
            建议动作
          </div>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            {recommendedActions.slice(0, 3).map((action) => (
              <Text key={action.action_id} type="secondary">
                {String(action.title || action.summary || action.action_id)}
              </Text>
            ))}
          </Space>
        </>
      ) : null}
      {controlCoreContract.length > 0 ? (
        <>
          <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
            Control Contract
          </div>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            {controlCoreContract.map((item) => (
              <Text key={item} type="secondary">
                {item}
              </Text>
            ))}
          </Space>
        </>
      ) : null}
    </Card>
  );
}

export interface RuntimeCockpitSignal {
  key: string;
  label: string;
  value: string;
  detail?: string | null;
  route?: string | null;
  routeTitle?: string | null;
  tone?: "default" | "success" | "warning" | "danger";
}

function runtimeCardMap(payload: RuntimeCenterOverviewPayload | null) {
  return new Map((payload?.cards ?? []).map((card) => [card.key, card]));
}

function textValue(value: unknown): string | null {
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized ? localizeRuntimeText(normalized) : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function firstTextValue(...values: unknown[]): string | null {
  for (const value of values) {
    const record = recordValue(value);
    if (record) {
      const nested = firstTextValue(
        record.title,
        record.name,
        record.label,
        record.summary,
        record.value,
        record.count,
        record.total,
      );
      if (nested) {
        return nested;
      }
      continue;
    }
    const text = textValue(value);
    if (text) {
      return text;
    }
  }
  return null;
}

function countText(value: unknown, fallback = "0"): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  const record = recordValue(value);
  if (record) {
    const candidate = record.count ?? record.total ?? record.visible_count ?? record.recent_count;
    const text = textValue(candidate);
    if (text) {
      return text;
    }
    const nested = firstTextValue(record.title, record.name, record.label, record.summary);
    if (nested) {
      return nested;
    }
  }
  const text = textValue(value);
  return text || fallback;
}

function detailText(value: unknown): string | null {
  const record = recordValue(value);
  if (!record) {
    return null;
  }
  return firstTextValue(
    record.detail,
    record.note,
    record.summary,
    record.description,
    record.reason,
    record.status,
  );
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const record = recordValue(value);
  if (!record) {
    return null;
  }
  const candidate = record.count ?? record.total ?? record.visible_count ?? record.recent_count;
  if (typeof candidate === "number" && Number.isFinite(candidate)) {
    return candidate;
  }
  if (typeof candidate === "string" && candidate.trim()) {
    const parsed = Number(candidate);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function routeText(value: unknown): string | null {
  const record = recordValue(value);
  if (!record) {
    return null;
  }
  return textValue(record.route);
}

function signalSource(mainBrainMeta: Record<string, unknown>, key: string): unknown {
  const signalMap = recordValue(mainBrainMeta.signals);
  if (signalMap && key in signalMap) {
    return signalMap[key];
  }
  return mainBrainMeta[key];
}

function buildSignal(
  key: string,
  value: string,
  detail: string | null,
  route: string | null,
  tone?: RuntimeCockpitSignal["tone"],
  routeTitle?: string,
): RuntimeCockpitSignal {
  return {
    key,
    label: formatMainBrainSignalLabel(key),
    value,
    detail,
    route,
    routeTitle,
    tone,
  };
}

export function buildRuntimeIndustryCockpitSignals(
  payload: RuntimeCenterOverviewPayload | null,
): RuntimeCockpitSignal[] {
  const cards = runtimeCardMap(payload);
  const mainBrainCard = cards.get("main-brain") ?? null;
  const industryCard = cards.get("industry") ?? null;
  const evidenceCard = cards.get("evidence") ?? null;
  const decisionsCard = cards.get("decisions") ?? null;
  const patchesCard = cards.get("patches") ?? null;
  const mainBrainMeta = recordValue(mainBrainCard?.meta) ?? {};
  const industryMeta = recordValue(industryCard?.meta) ?? {};
  const mainBrainEntry = mainBrainCard?.entries?.[0] ?? null;
  const industryEntry = industryCard?.entries?.[0] ?? null;
  const industryRoute = textValue(industryEntry?.route) || textValue(industryCard?.entries?.[0]?.route);

  const strategySource =
    signalSource(mainBrainMeta, "strategy") ?? industryCard?.summary ?? industryEntry?.summary;
  const lanesSource = signalSource(mainBrainMeta, "lanes") ?? industryMeta.lane_count;
  const backlogSource = signalSource(mainBrainMeta, "backlog") ?? industryMeta.backlog_count;
  const cycleSource =
    signalSource(mainBrainMeta, "current_cycle") ?? industryCard?.summary ?? industryEntry?.summary;
  const assignmentsSource =
    signalSource(mainBrainMeta, "assignments") ?? industryMeta.assignment_count;
  const agentReportsSource =
    signalSource(mainBrainMeta, "agent_reports") ?? industryMeta.report_count;
  const evidenceSource =
    signalSource(mainBrainMeta, "evidence") ?? evidenceCard?.summary ?? evidenceCard?.count;
  const decisionsSource =
    signalSource(mainBrainMeta, "decisions") ?? decisionsCard?.summary ?? decisionsCard?.count;
  const patchesSource =
    signalSource(mainBrainMeta, "patches") ?? patchesCard?.summary ?? patchesCard?.count;
  const assignmentsRoute = routeText(assignmentsSource) || industryRoute;
  const reportsRoute = routeText(agentReportsSource) || industryRoute;
  const unconsumedReports =
    numberValue(recordValue(agentReportsSource)?.unconsumed_count) ||
    numberValue(recordValue(agentReportsSource)?.pending_count) ||
    numberValue(recordValue(agentReportsSource)?.unconsumed_reports) ||
    0;

  return [
    buildSignal(
      "strategy",
      firstTextValue(strategySource) || "No strategy signal",
      detailText(strategySource) || firstTextValue(mainBrainEntry?.summary, industryEntry?.summary),
      routeText(strategySource) || industryRoute,
      "success",
      "策略详情",
    ),
    buildSignal(
      "lanes",
      countText(lanesSource, textValue(industryMeta.lane_count) || "0"),
      detailText(lanesSource) ||
        firstTextValue(
          industryMeta.backlog_count,
          industryMeta.cycle_count,
          industryMeta.assignment_count,
          industryMeta.report_count,
        ),
      industryRoute,
      "default",
      "泳道详情",
    ),
    buildSignal(
      "backlog",
      countText(backlogSource, textValue(industryMeta.backlog_count) || "0"),
      detailText(backlogSource) || firstTextValue(industryMeta.backlog_count),
      routeText(backlogSource) || industryRoute,
      "default",
      "待办详情",
    ),
    buildSignal(
      "current_cycle",
      firstTextValue(cycleSource) || "暂无活动周期",
      detailText(cycleSource) ||
        firstTextValue(recordValue(cycleSource)?.status),
      routeText(cycleSource) || industryRoute,
      "default",
      "周期详情",
    ),
    buildSignal(
      "assignments",
      countText(assignmentsSource, textValue(industryMeta.assignment_count) || "0"),
      detailText(assignmentsSource) || firstTextValue(industryMeta.assignment_count),
      assignmentsRoute,
      "default",
      "派工详情",
    ),
    buildSignal(
      "agent_reports",
      countText(agentReportsSource, textValue(industryMeta.report_count) || "0"),
      detailText(agentReportsSource) ||
        (unconsumedReports > 0
          ? `未消费 ${unconsumedReports}`
          : firstTextValue(industryMeta.report_count)),
      reportsRoute,
      unconsumedReports > 0 ? "warning" : "default",
      "汇报详情",
    ),
    buildSignal(
      "evidence",
      countText(evidenceSource, textValue(evidenceCard?.count) || "0"),
      detailText(evidenceSource) || textValue(evidenceCard?.summary),
      textValue(evidenceCard?.entries?.[0]?.route) || null,
      "default",
      "证据详情",
    ),
    buildSignal(
      "decisions",
      countText(decisionsSource, textValue(decisionsCard?.count) || "0"),
      detailText(decisionsSource) || textValue(decisionsCard?.summary),
      textValue(decisionsCard?.entries?.[0]?.route) || null,
      "warning",
      "决策详情",
    ),
    buildSignal(
      "patches",
      countText(patchesSource, textValue(patchesCard?.count) || "0"),
      detailText(patchesSource) || textValue(patchesCard?.summary),
      textValue(patchesCard?.entries?.[0]?.route) || null,
      "warning",
      "补丁详情",
    ),
  ];
}

export function renderIndustryExecutionFocusSection(
  payload: IndustryInstanceDetail,
  openRoute: (route: string, title: string) => void,
) {
  const execution = isIndustryExecutionSummary(payload.execution)
    ? payload.execution
    : null;
  const mainChain = isIndustryMainChainGraph(payload.main_chain)
    ? payload.main_chain
    : null;
  const focusSelection = payload.focus_selection || null;
  const evidenceNode = findChainNode(mainChain, "evidence");
  const assignmentNode = findChainNode(mainChain, "assignment");
  const backlogNode = findChainNode(mainChain, "backlog");
  const currentOwnerAgentId =
    execution?.current_owner_agent_id || mainChain?.current_owner_agent_id || null;
  const liveFocusSummary =
    assignmentNode?.route
      ? assignmentNode.summary || assignmentNode.label
      : backlogNode?.route
        ? backlogNode.summary || backlogNode.label
        : null;
  const currentFocus =
    liveFocusSummary ||
    execution?.current_focus ||
    mainChain?.current_focus ||
    "暂无活动焦点";
  const currentOwner =
    execution?.current_owner ||
    mainChain?.current_owner ||
    payload.agents.find((agent) => agent.agent_id === currentOwnerAgentId)?.name ||
    "Execution core";
  const currentRisk = execution?.current_risk || mainChain?.current_risk || "unknown";
  const latestEvidence =
    execution?.latest_evidence_summary ||
    mainChain?.latest_evidence_summary ||
    "No evidence written yet";
  const loopState = mainChain?.loop_state || execution?.status || payload.status;
  const evidenceCount = execution?.evidence_count ?? payload.evidence.length;
  const currentFocusRoute = assignmentNode?.route || backlogNode?.route || null;
  const currentOwnerRoute = findIndustryAgentRoute(payload, currentOwnerAgentId);
  const latestEvidenceRoute = evidenceNode?.route || null;
  const staffingPresentation = buildStaffingPresentation(payload.staffing);
  const lanes = Array.isArray(payload.lanes) ? payload.lanes : [];
  const focusedLaneIds = new Set(payload.current_cycle?.focus_lane_ids || []);
  const visibleLanes = lanes.slice(0, 4);
  const pendingSignalCount =
    typeof payload.staffing?.researcher?.pending_signal_count === "number"
      ? payload.staffing.researcher.pending_signal_count
      : 0;
  const followupReports = (Array.isArray(payload.agent_reports) ? payload.agent_reports : []).filter(
    (report) => report.needs_followup || report.processed === false,
  );
  const strategySummary =
    payload.strategy_memory?.north_star ||
    payload.strategy_memory?.summary ||
    null;
  const cycleSynthesis = payload.current_cycle?.synthesis;
  const synthesisConflicts = cycleSynthesis?.conflicts || [];
  const synthesisHoles = cycleSynthesis?.holes || [];
  const synthesisFindings = cycleSynthesis?.latest_findings || [];
  const synthesisFollowups = synthesisFindings.filter(
    (finding) => finding.needs_followup || nonEmpty(finding.followup_reason),
  );
  const recommendedActions = cycleSynthesis?.recommended_actions || [];
  const controlCoreContract = cycleSynthesis?.control_core_contract || [];
  const synthesisSummary = cycleSynthesis
    ? [
        `发现 ${synthesisFindings.length}`,
        `冲突 ${synthesisConflicts.length}`,
        `缺口 ${synthesisHoles.length}`,
        `动作 ${recommendedActions.length}`,
      ].join(" / ")
    : "当前还没有周期综合结果。";

  const items = [
    {
      key: "goal",
      label: "当前焦点",
      value: currentFocus,
      note:
        execution?.current_stage ||
        execution?.next_step ||
        assignmentNode?.summary ||
        backlogNode?.summary ||
        null,
      status: loopState,
      route: currentFocusRoute,
      routeTitle: currentFocus,
    },
    {
      key: "owner",
      label: "当前负责人",
      value: currentOwner,
      note: currentOwnerAgentId,
      status:
        payload.agents.find((agent) => agent.agent_id === currentOwnerAgentId)?.status ||
        payload.status,
      route: currentOwnerRoute,
      routeTitle: currentOwner,
    },
    {
      key: "risk",
      label: "当前风险",
      value: runtimeRiskLabel(currentRisk),
      note: execution?.blocked_reason || execution?.stuck_reason || null,
      status: currentRisk,
      route: null,
      routeTitle: "当前风险",
    },
    {
      key: "evidence",
      label: "当前证据",
      value: latestEvidence,
      note: `${evidenceCount} 条证据记录`,
      status: evidenceCount > 0 ? "active" : "idle",
      route: latestEvidenceRoute,
      routeTitle: "最新证据",
    },
    {
      key: "team-status",
      label: "当前团队状态",
      value: translateRuntimeStatus(payload.status),
      note: `循环 ${translateRuntimeStatus(loopState)} · 范围 ${payload.owner_scope}`,
      status: payload.status,
      route: null,
      routeTitle: payload.label,
    },
  ];

  return (
    <section key="industry-focus" className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>运行焦点</div>
      {focusSelection ? (
        <Alert
          showIcon
          type="info"
          message={
            focusSelection.selection_kind === "assignment"
              ? "已聚焦派工"
              : "已聚焦待办"
          }
          description={
            focusSelection.summary || focusSelection.title || "已聚焦的运行时子视图"
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <div className={styles.industryFocusGrid}>
        {items.map((item) => (
          <div key={item.key} className={styles.industryFocusCard}>
            <div className={styles.industryFocusCardTop}>
              <div className={styles.industryFocusLabel}>{item.label}</div>
              <Tag
                color={
                  item.key === "risk"
                    ? runtimeRiskColor(currentRisk)
                    : runtimeStatusColor(item.status)
                }
              >
                {item.key === "risk"
                  ? runtimeRiskLabel(currentRisk)
                  : translateRuntimeStatus(item.status)}
              </Tag>
            </div>
            <div className={styles.industryFocusValue}>{item.value}</div>
            {item.note ? (
              <div className={styles.industryFocusNote}>{item.note}</div>
            ) : null}
            {item.route ? (
              <Button
                size="small"
                onClick={() => {
                  openRoute(item.route!, item.routeTitle);
                }}
              >
                打开详情
              </Button>
            ) : null}
          </div>
        ))}
      </div>
      {renderMainBrainPlanningSection({
        payload,
        lanes,
        visibleLanes,
        focusedLaneIds,
        followupReports,
        pendingSignalCount,
        strategySummary,
        synthesisFollowups,
      })}
      {renderMainBrainSynthesisSection({
        cycleSynthesis,
        synthesisFindings,
        synthesisConflicts,
        synthesisHoles,
        synthesisFollowups,
        recommendedActions,
        controlCoreContract,
        synthesisSummary,
      })}
      {staffingPresentation.hasAnyState ? (
        <div style={{ marginTop: 16 }}>
          <div className={styles.detailSectionTitle}>Staffing Closure</div>
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {staffingPresentation.activeGap ? (
              <Alert
                showIcon
                type={
                  staffingPresentation.activeGap.badges.includes("Needs approval")
                    ? "warning"
                    : "info"
                }
                message={staffingPresentation.activeGap.title}
                description={[
                  staffingPresentation.activeGap.detail,
                  staffingPresentation.activeGap.meta.join(" / "),
                ]
                  .filter(Boolean)
                  .join(" | ")}
              />
            ) : null}
            {staffingPresentation.pendingProposals.length ? (
              <Card size="small" title="待处理提案">
                <Space direction="vertical" size={6}>
                  {staffingPresentation.pendingProposals.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.temporarySeats.length ? (
              <Card size="small" title="临时席位">
                <Space direction="vertical" size={6}>
                  {staffingPresentation.temporarySeats.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.researcher ? (
              <Card size="small" title="研究位">
                <Space direction="vertical" size={6}>
                  <Text strong>{staffingPresentation.researcher.headline}</Text>
                  <Text type="secondary">{staffingPresentation.researcher.detail}</Text>
                  <Space wrap>
                    {staffingPresentation.researcher.badges.map((badge) => (
                      <Tag key={badge}>{badge}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            ) : null}
          </Space>
        </div>
      ) : null}
    </section>
  );
}

export function renderIndustryMainChainSection(
  graph: IndustryMainChainGraph,
  openRoute: (route: string, title: string) => void,
) {
  const controlChain = presentControlChain(graph);
  return (
    <section key="industry-main-chain" className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>Spider Main Chain</div>
      <div className={styles.mainChainHeader}>
        <Tag color={runtimeStatusColor(controlChain.loopState || "unknown")}>
          {controlChain.loopStateLabel}
        </Tag>
        {controlChain.currentFocus ? (
          <span className={styles.mainChainHeaderText}>
            焦点：{controlChain.currentFocus}
          </span>
        ) : null}
        {controlChain.currentOwner ? (
          <span className={styles.mainChainHeaderText}>
            Owner: {controlChain.currentOwner}
          </span>
        ) : null}
        {controlChain.currentRisk ? (
          <Tag color={runtimeRiskColor(controlChain.currentRisk)}>
            {runtimeRiskLabel(controlChain.currentRisk)}
          </Tag>
        ) : null}
      </div>
      {controlChain.latestEvidenceSummary ? (
        <div className={styles.mainChainSummary}>{controlChain.latestEvidenceSummary}</div>
      ) : null}
      {controlChain.synthesis ? (
        <div className={styles.mainChainSummary}>{controlChain.synthesis.summary}</div>
      ) : null}
      <div className={styles.mainChainTimeline}>
        {controlChain.nodes.map((node, index) => (
          <div key={node.id} className={styles.mainChainNode}>
            <div className={styles.mainChainRail}>
              <div className={styles.mainChainDot} />
              {index < controlChain.nodes.length - 1 ? (
                <div className={styles.mainChainConnector} />
              ) : null}
            </div>
            <div className={styles.mainChainCard}>
              <div className={styles.mainChainCardTop}>
                <div>
                  <div className={styles.mainChainNodeLabel}>{node.label}</div>
                  <div className={styles.mainChainNodeId}>{node.id}</div>
                </div>
                <Space size={8} wrap>
                  <Tag color={runtimeStatusColor(node.status)}>
                    {node.statusLabel}
                  </Tag>
                  {node.route ? (
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(node.route!, node.label);
                      }}
                    >
                      Open
                    </Button>
                  ) : null}
                </Space>
              </div>
              {node.summary ? (
                <div className={styles.mainChainNodeSummary}>{node.summary}</div>
              ) : null}
              <div className={styles.mainChainMetaGrid}>
                <div className={styles.mainChainMetaCard}>
                  <span className={styles.mainChainMetaLabel}>Truth Source</span>
                  <code className={styles.mainChainMetaValue}>{node.truthSource}</code>
                </div>
                {node.currentRef ? (
                  <div className={styles.mainChainMetaCard}>
                    <span className={styles.mainChainMetaLabel}>Current Ref</span>
                    <code className={styles.mainChainMetaValue}>{node.currentRef}</code>
                  </div>
                ) : null}
                {node.backflowPort ? (
                  <div className={styles.mainChainMetaCard}>
                    <span className={styles.mainChainMetaLabel}>Backflow Port</span>
                    <code className={styles.mainChainMetaValue}>{node.backflowPort}</code>
                  </div>
                ) : null}
              </div>
              {node.metrics.length > 0 ? (
                <div className={styles.mainChainMetricGrid}>
                  {node.metrics.map((metric) => (
                    <div key={`${node.id}:${metric.key}`} className={styles.mainChainMetric}>
                      <span className={styles.mainChainMetaLabel}>
                        {metric.label}
                      </span>
                      <span className={styles.mainChainMetricValue}>
                        {metric.value}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function renderReviewListCard(
  title: string,
  items: string[],
  codeStyle = false,
) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div key={title} className={styles.reviewListCard}>
      <div className={styles.reviewListTitle}>{title}</div>
      <ul className={styles.reviewList}>
        {items.map((item, index) => (
          <li key={`${title}:${index}`} className={styles.reviewListItem}>
            {codeStyle ? <code className={styles.reviewCode}>{item}</code> : item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function renderTaskReviewSection(
  sectionKey: string,
  review: Record<string, unknown>,
  openRoute: (route: string, title: string) => void,
) {
  const headline = metaStringValue(review, "headline") || "Task review";
  const objective = metaStringValue(review, "objective");
  const status = metaStringValue(review, "status");
  const phase = metaStringValue(review, "phase");
  const currentStage = metaStringValue(review, "current_stage");
  const executionState = metaStringValue(review, "execution_state");
  const nextStep = metaStringValue(review, "next_step");
  const ownerAgentName = metaStringValue(review, "owner_agent_name");
  const latestResultSummary = metaStringValue(review, "latest_result_summary");
  const latestEvidenceSummary = metaStringValue(review, "latest_evidence_summary");
  const blockedReason = metaStringValue(review, "blocked_reason");
  const stuckReason = metaStringValue(review, "stuck_reason");
  const taskRoute = metaStringValue(review, "task_route");
  const reviewRoute = metaStringValue(review, "review_route");
  const pendingDecisionCount = metaNumberValue(review, "pending_decision_count");
  const evidenceCount = metaNumberValue(review, "evidence_count");
  const childTaskCount = metaNumberValue(review, "child_task_count");
  const childCompletionRate = metaNumberValue(review, "child_completion_rate");
  const summaryLines = stringListValue(review, "summary_lines");
  const nextActions = stringListValue(review, "next_actions");
  const recentFailures = stringListValue(review, "recent_failures");
  const effectiveActions = stringListValue(review, "effective_actions");
  const avoidRepeats = stringListValue(review, "avoid_repeats");
  const risks = stringListValue(review, "risks");
  const feedbackEvidenceRefs = stringListValue(review, "feedback_evidence_refs");

  const metaItems = [
    {
      label: formatRuntimeFieldLabel("execution_state"),
      value: executionState,
    },
    {
      label: formatRuntimeFieldLabel("current_stage"),
      value: currentStage && currentStage !== phase ? currentStage : null,
    },
    {
      label: formatRuntimeFieldLabel("owner_agent_name"),
      value: ownerAgentName,
    },
    {
      label: formatRuntimeFieldLabel("pending_decision_count"),
      value:
        pendingDecisionCount === null ? null : formatPrimitiveValue(pendingDecisionCount),
    },
    {
      label: formatRuntimeFieldLabel("evidence_count"),
      value: evidenceCount === null ? null : formatPrimitiveValue(evidenceCount),
    },
    {
      label: formatRuntimeFieldLabel("child_task_count"),
      value: childTaskCount === null ? null : formatPrimitiveValue(childTaskCount),
    },
    {
      label: formatRuntimeFieldLabel("child_completion_rate"),
      value:
        childCompletionRate === null ? null : `${formatPrimitiveValue(childCompletionRate)}%`,
    },
    {
      label: formatRuntimeFieldLabel("blocked_reason"),
      value: blockedReason,
    },
    {
      label: formatRuntimeFieldLabel("stuck_reason"),
      value: stuckReason,
    },
    {
      label: formatRuntimeFieldLabel("latest_result_summary"),
      value: latestResultSummary,
    },
    {
      label: formatRuntimeFieldLabel("latest_evidence_summary"),
      value:
        latestEvidenceSummary && latestEvidenceSummary !== latestResultSummary
          ? latestEvidenceSummary
          : null,
    },
  ].filter((item) => item.value);

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)}
      </div>
      <div className={styles.reviewSummaryCard}>
        <div className={styles.reviewHeadlineRow}>
          <div className={styles.reviewHeadlineBlock}>
            <div className={styles.reviewHeadline}>{headline}</div>
            {objective ? <div className={styles.reviewObjective}>{objective}</div> : null}
          </div>
          <Space size={8} wrap className={styles.reviewTagRow}>
            {status ? (
              <Tag color={runtimeStatusColor(status)}>
                {translateRuntimeStatus(status)}
              </Tag>
            ) : null}
            {phase ? <Tag>{`Phase ${phase}`}</Tag> : null}
            {currentStage && currentStage !== phase ? (
              <Tag>{`恢复 ${currentStage}`}</Tag>
            ) : null}
          </Space>
        </div>

        {nextStep ? <div className={styles.reviewNextStep}>{`Next: ${nextStep}`}</div> : null}

        {metaItems.length > 0 ? (
          <div className={styles.reviewMetaGrid}>
            {metaItems.map((item) => (
              <div key={item.label} className={styles.reviewMetaItem}>
                <span className={styles.reviewMetaLabel}>{item.label}</span>
                <span className={styles.reviewMetaValue}>{item.value}</span>
              </div>
            ))}
          </div>
        ) : null}

        {taskRoute || reviewRoute ? (
          <div className={styles.routeActions}>
            {taskRoute ? (
              <Button size="small" onClick={() => openRoute(taskRoute, "Task detail")}>
                Task detail
              </Button>
            ) : null}
            {reviewRoute ? (
              <Button size="small" onClick={() => openRoute(reviewRoute, "执行审查")}>
                查看审查路由
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className={styles.reviewPanels}>
        {renderReviewListCard("摘要", summaryLines)}
        {renderReviewListCard("下一动作", nextActions)}
        {renderReviewListCard("最近失败", recentFailures)}
        {renderReviewListCard("有效动作", effectiveActions)}
        {renderReviewListCard("避免重复", avoidRepeats)}
        {renderReviewListCard("风险", risks)}
        {renderReviewListCard("证据引用", feedbackEvidenceRefs, true)}
      </div>
    </section>
  );
}
