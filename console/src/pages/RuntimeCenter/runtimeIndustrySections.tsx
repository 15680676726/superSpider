import { Alert, Button, Card, Empty, Space, Tag, Typography } from "antd";

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
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";

const { Text } = Typography;

function nonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
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

function routeText(value: unknown): string | null {
  const record = recordValue(value);
  if (!record) {
    return null;
  }
  return textValue(record.route);
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

  const strategySource = mainBrainMeta.strategy ?? industryCard?.summary ?? industryEntry?.summary;
  const lanesSource = mainBrainMeta.lanes ?? industryMeta.lane_count;
  const cycleSource = mainBrainMeta.current_cycle ?? industryCard?.summary ?? industryEntry?.summary;
  const assignmentsSource = mainBrainMeta.assignments ?? industryMeta.assignment_count;
  const agentReportsSource = mainBrainMeta.agent_reports ?? industryMeta.report_count;
  const evidenceSource = mainBrainMeta.evidence ?? evidenceCard?.summary ?? evidenceCard?.count;
  const decisionsSource = mainBrainMeta.decisions ?? decisionsCard?.summary ?? decisionsCard?.count;
  const patchesSource = mainBrainMeta.patches ?? patchesCard?.summary ?? patchesCard?.count;

  return [
    buildSignal(
      "strategy",
      firstTextValue(strategySource) || "No strategy signal",
      detailText(strategySource) || firstTextValue(mainBrainEntry?.summary, industryEntry?.summary),
      routeText(strategySource) || industryRoute,
      "success",
      "Strategy detail",
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
      "Lane detail",
    ),
    buildSignal(
      "current_cycle",
      firstTextValue(cycleSource) || "No active cycle",
      detailText(cycleSource) ||
        firstTextValue(recordValue(cycleSource)?.status),
      routeText(cycleSource) || industryRoute,
      "default",
      "Cycle detail",
    ),
    buildSignal(
      "assignments",
      countText(assignmentsSource, textValue(industryMeta.assignment_count) || "0"),
      detailText(assignmentsSource) || firstTextValue(industryMeta.assignment_count),
      industryRoute,
      "default",
      "Assignments detail",
    ),
    buildSignal(
      "agent_reports",
      countText(agentReportsSource, textValue(industryMeta.report_count) || "0"),
      detailText(agentReportsSource) || firstTextValue(industryMeta.report_count),
      industryRoute,
      "default",
      "Reports detail",
    ),
    buildSignal(
      "evidence",
      countText(evidenceSource, textValue(evidenceCard?.count) || "0"),
      detailText(evidenceSource) || textValue(evidenceCard?.summary),
      textValue(evidenceCard?.entries?.[0]?.route) || null,
      "default",
      "Evidence detail",
    ),
    buildSignal(
      "decisions",
      countText(decisionsSource, textValue(decisionsCard?.count) || "0"),
      detailText(decisionsSource) || textValue(decisionsCard?.summary),
      textValue(decisionsCard?.entries?.[0]?.route) || null,
      "warning",
      "Decision detail",
    ),
    buildSignal(
      "patches",
      countText(patchesSource, textValue(patchesCard?.count) || "0"),
      detailText(patchesSource) || textValue(patchesCard?.summary),
      textValue(patchesCard?.entries?.[0]?.route) || null,
      "warning",
      "Patch detail",
    ),
  ];
}

function focusedSelectionId(
  focusSelection: Record<string, unknown> | null | undefined,
  kind: string,
  idKey: string,
): string | null {
  if (!focusSelection) {
    return null;
  }
  const selectionKind = typeof focusSelection.selection_kind === "string" ? focusSelection.selection_kind : null;
  if (selectionKind !== kind) {
    return null;
  }
  const value = focusSelection[idKey];
  return typeof value === "string" && value ? value : null;
}

function renderAssignmentSummaryTags(assignments: Record<string, unknown>[]) {
  const activeCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "active",
  ).length;
  const readyCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "ready",
  ).length;
  const completedCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "completed",
  ).length;
  const evidenceCounts = assignments.map((assignment) =>
    Array.isArray(assignment.evidence_ids) ? assignment.evidence_ids.length : 0,
  );
  const maxEvidence = evidenceCounts.length > 0 ? Math.max(...evidenceCounts) : 0;

  return (
    <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
      {activeCount > 0 ? <Tag color="blue">{`Active ${activeCount}`}</Tag> : null}
      {readyCount > 0 ? <Tag>{`Ready ${readyCount}`}</Tag> : null}
      {completedCount > 0 ? <Tag color="success">{`Completed ${completedCount}`}</Tag> : null}
      {maxEvidence > 0 ? <Tag>{`Max evidence ${maxEvidence}`}</Tag> : null}
    </Space>
  );
}

export function renderOperatorAssignmentsSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
  focusSelection?: Record<string, unknown> | null,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }
  const assignments = sectionValue.filter(isRecord);
  const focusedAssignmentId = focusedSelectionId(focusSelection, "assignment", "assignment_id");

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
      </div>

      {assignments.length > 0 ? renderAssignmentSummaryTags(assignments) : null}

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="鏆傛棤鍐呭" />
      ) : (
        <div className={styles.detailArray}>
          {sectionValue.map((item, index) => {
            if (!isRecord(item)) {
              return (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {formatPrimitiveValue(item)}
                </pre>
              );
            }

            const assignmentId =
              typeof item.assignment_id === "string" && item.assignment_id ? item.assignment_id : null;
            const title =
              (typeof item.title === "string" && item.title) ||
              (typeof item.summary === "string" && item.summary) ||
              assignmentId ||
              `Assignment ${index + 1}`;
            const summary = typeof item.summary === "string" ? item.summary : null;
            const status = typeof item.status === "string" && item.status ? item.status : "unknown";
            const route = typeof item.route === "string" && item.route ? item.route : null;
            const focused =
              item.selected === true || (assignmentId && assignmentId === focusedAssignmentId);
            const ownerAgentId =
              typeof item.owner_agent_id === "string" && item.owner_agent_id
                ? item.owner_agent_id
                : null;
            const laneId =
              typeof item.lane_id === "string" && item.lane_id ? item.lane_id : null;
            const cycleId =
              typeof item.cycle_id === "string" && item.cycle_id ? item.cycle_id : null;
            const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0;
            const lastReportId =
              typeof item.last_report_id === "string" && item.last_report_id
                ? item.last_report_id
                : null;

            return (
              <Card
                key={assignmentId || `${sectionKey}:${index}`}
                size="small"
                style={
                  focused
                    ? {
                        border: "1px solid rgba(22, 119, 255, 0.35)",
                        boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
                      }
                    : undefined
                }
              >
                <Space wrap size={[6, 6]} style={{ marginBottom: summary ? 6 : 0 }}>
                  <Text strong>{title}</Text>
                  <Tag color={runtimeStatusColor(status)}>{translateRuntimeStatus(status)}</Tag>
                  {focused ? <Tag color="blue">Focused</Tag> : null}
                  {evidenceCount > 0 ? <Tag>{`Evidence ${evidenceCount}`}</Tag> : null}
                </Space>
                {summary ? <Text type="secondary">{summary}</Text> : null}
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {ownerAgentId ? <span>{`Owner ${ownerAgentId}`}</span> : null}
                  {laneId ? <span>{`Lane ${laneId}`}</span> : null}
                  {cycleId ? <span>{`Cycle ${cycleId}`}</span> : null}
                  {lastReportId ? <span>{`Last report ${lastReportId}`}</span> : null}
                </Space>
                {route ? (
                  <div className={styles.routeActions}>
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(route, title);
                      }}
                    >
                      Open Assignment
                    </Button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function renderOperatorAgentReportsSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
  focusSelection?: Record<string, unknown> | null,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }

  const reports = sectionValue.filter(isRecord);
  const focusedReportId = focusedSelectionId(focusSelection, "agent_report", "report_id");
  const unconsumedCount = reports.filter((report) => report.processed !== true).length;
  const followupCount = reports.filter((report) => report.needs_followup === true).length;

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
      </div>

      {reports.length > 0 ? (
        <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
          {unconsumedCount > 0 ? <Tag color="warning">{`Unconsumed ${unconsumedCount}`}</Tag> : <Tag color="success">All consumed</Tag>}
          {followupCount > 0 ? <Tag color="warning">{`Follow-ups ${followupCount}`}</Tag> : null}
        </Space>
      ) : null}

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="鏆傛棤鍐呭" />
      ) : (
        <div className={styles.detailArray}>
          {sectionValue.map((item, index) => {
            if (!isRecord(item)) {
              return (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {formatPrimitiveValue(item)}
                </pre>
              );
            }

            const reportId =
              typeof item.report_id === "string" && item.report_id ? item.report_id : null;
            const headline =
              (typeof item.headline === "string" && item.headline) ||
              (typeof item.summary === "string" && item.summary) ||
              reportId ||
              `Report ${index + 1}`;
            const summary = typeof item.summary === "string" ? item.summary : null;
            const status = typeof item.status === "string" && item.status ? item.status : "unknown";
            const processed = item.processed === true;
            const needsFollowup = item.needs_followup === true;
            const route = typeof item.route === "string" && item.route ? item.route : null;
            const focused =
              item.selected === true || (reportId && reportId === focusedReportId);
            const reportKind =
              typeof item.report_kind === "string" && item.report_kind ? item.report_kind : null;
            const riskLevel =
              typeof item.risk_level === "string" && item.risk_level ? item.risk_level : null;
            const ownerAgentId =
              typeof item.owner_agent_id === "string" && item.owner_agent_id
                ? item.owner_agent_id
                : null;
            const laneId = typeof item.lane_id === "string" && item.lane_id ? item.lane_id : null;
            const assignmentId =
              typeof item.assignment_id === "string" && item.assignment_id ? item.assignment_id : null;
            const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0;

            return (
              <Card
                key={reportId || `${sectionKey}:${index}`}
                size="small"
                style={
                  focused
                    ? {
                        border: "1px solid rgba(22, 119, 255, 0.35)",
                        boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
                      }
                    : undefined
                }
              >
                <Space wrap size={[6, 6]} style={{ marginBottom: summary ? 6 : 0 }}>
                  <Text strong>{headline}</Text>
                  <Tag color={runtimeStatusColor(status)}>{translateRuntimeStatus(status)}</Tag>
                  {focused ? <Tag color="blue">Focused</Tag> : null}
                  {processed ? <Tag color="success">Consumed</Tag> : <Tag color="warning">Unconsumed</Tag>}
                  {needsFollowup ? <Tag color="warning">Needs follow-up</Tag> : null}
                  {evidenceCount > 0 ? <Tag>{`Evidence ${evidenceCount}`}</Tag> : null}
                  {riskLevel ? <Tag color={runtimeRiskColor(riskLevel)}>{riskLevel}</Tag> : null}
                  {reportKind ? <Tag>{reportKind}</Tag> : null}
                </Space>
                {summary ? <Text type="secondary">{summary}</Text> : null}
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {ownerAgentId ? <span>{`Owner ${ownerAgentId}`}</span> : null}
                  {laneId ? <span>{`Lane ${laneId}`}</span> : null}
                  {assignmentId ? <span>{`Assignment ${assignmentId}`}</span> : null}
                </Space>
                {route ? (
                  <div className={styles.routeActions}>
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(route, headline);
                      }}
                    >
                      Open Report
                    </Button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
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
    "No active focus";
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
        `Findings ${synthesisFindings.length}`,
        `Conflicts ${synthesisConflicts.length}`,
        `Holes ${synthesisHoles.length}`,
        `Actions ${recommendedActions.length}`,
      ].join(" / ")
    : "No cycle synthesis yet.";

  const items = [
    {
      key: "goal",
      label: "Current Focus",
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
      label: "Current Owner",
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
      label: "Current Risk",
      value: runtimeRiskLabel(currentRisk),
      note: execution?.blocked_reason || execution?.stuck_reason || null,
      status: currentRisk,
      route: null,
      routeTitle: "Current Risk",
    },
    {
      key: "evidence",
      label: "Current Evidence",
      value: latestEvidence,
      note: `${evidenceCount} evidence record(s)`,
      status: evidenceCount > 0 ? "active" : "idle",
      route: latestEvidenceRoute,
      routeTitle: "Latest Evidence",
    },
    {
      key: "team-status",
      label: "Current Team Status",
      value: translateRuntimeStatus(payload.status),
      note: `Loop ${translateRuntimeStatus(loopState)} · Scope ${payload.owner_scope}`,
      status: payload.status,
      route: null,
      routeTitle: payload.label,
    },
  ];

  return (
    <section key="industry-focus" className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>Runtime Focus</div>
      {focusSelection ? (
        <Alert
          showIcon
          type="info"
          message={
            focusSelection.selection_kind === "assignment"
              ? "Focused Assignment"
              : "Focused Backlog"
          }
          description={
            focusSelection.summary || focusSelection.title || "Focused runtime subview"
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
                Open Detail
              </Button>
            ) : null}
          </div>
        ))}
      </div>
      <Card size="small" title="Main-Brain Planning" style={{ marginTop: 16 }}>
        <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
          <Tag>{`Lanes ${lanes.length}`}</Tag>
          <Tag>{`Assignments ${payload.assignments.length}`}</Tag>
          <Tag>{`Reports ${payload.agent_reports.length}`}</Tag>
          {followupReports.length > 0 ? (
            <Tag color="warning">{`Follow-ups ${followupReports.length}`}</Tag>
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
          {strategySummary || "No strategy summary is available yet."}
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
            <div className={styles.detailSectionTitle}>Operating Lanes</div>
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
            <div className={styles.detailSectionTitle}>Pending Report Follow-ups</div>
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
            <div className={styles.detailSectionTitle}>Supervisor Follow-ups</div>
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {synthesisFollowups.slice(0, 3).map((finding) => (
                <Space
                  key={finding.report_id}
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
              ))}
            </Space>
          </div>
        ) : null}
      </Card>
      <Card size="small" title="Main-Brain Synthesis" style={{ marginTop: 16 }}>
        <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
          <Tag>{`Findings ${synthesisFindings.length}`}</Tag>
          <Tag color={synthesisConflicts.length > 0 ? "error" : "default"}>
            {`Conflicts ${synthesisConflicts.length}`}
          </Tag>
          <Tag color={synthesisHoles.length > 0 ? "warning" : "default"}>
            {`Holes ${synthesisHoles.length}`}
          </Tag>
          {cycleSynthesis?.needs_replan ? <Tag color="error">Replan needed</Tag> : null}
        </Space>
        <Text type="secondary">{synthesisSummary}</Text>
        {synthesisConflicts.length > 0 ? (
          <>
            <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
              Conflicts
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
              Supervisor Follow-ups
            </div>
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {synthesisFollowups.slice(0, 3).map((finding) => (
                <Space
                  key={`${finding.report_id}:synthesis`}
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
              ))}
            </Space>
          </>
        ) : null}
        {synthesisHoles.length > 0 ? (
          <>
            <div className={styles.detailSectionTitle} style={{ marginTop: 10 }}>
              Holes / Follow-ups
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
              Recommended Actions
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
              <Card size="small" title="Pending Proposals">
                <Space direction="vertical" size={6}>
                  {staffingPresentation.pendingProposals.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.temporarySeats.length ? (
              <Card size="small" title="Temporary Seats">
                <Space direction="vertical" size={6}>
                  {staffingPresentation.temporarySeats.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.researcher ? (
              <Card size="small" title="Researcher">
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
            Focus: {controlChain.currentFocus}
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
              <Tag>{`Resume ${currentStage}`}</Tag>
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
              <Button size="small" onClick={() => openRoute(reviewRoute, "Execution review")}>
                Review route
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className={styles.reviewPanels}>
        {renderReviewListCard("Summary", summaryLines)}
        {renderReviewListCard("Next actions", nextActions)}
        {renderReviewListCard("Recent failures", recentFailures)}
        {renderReviewListCard("Effective moves", effectiveActions)}
        {renderReviewListCard("Avoid repeats", avoidRepeats)}
        {renderReviewListCard("Risks", risks)}
        {renderReviewListCard("Evidence refs", feedbackEvidenceRefs, true)}
      </div>
    </section>
  );
}
