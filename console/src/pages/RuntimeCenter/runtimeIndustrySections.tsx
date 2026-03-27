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
  formatRuntimeFieldLabel,
  formatRuntimeSectionLabel as translateRuntimeSectionLabel,
  formatRuntimeStatus as translateRuntimeStatus,
} from "./text";
import {
  findChainNode,
  findIndustryAgentRoute,
  findIndustryGoalRoute,
  isIndustryExecutionSummary,
  isIndustryMainChainGraph,
  metaNumberValue,
  metaStringValue,
  stringListValue,
} from "./runtimeDetailPrimitives";

const { Text } = Typography;

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
  const goalNode = findChainNode(mainChain, "goal");
  const evidenceNode = findChainNode(mainChain, "evidence");
  const currentGoalId =
    execution?.current_goal_id || mainChain?.current_goal_id || null;
  const currentOwnerAgentId =
    execution?.current_owner_agent_id || mainChain?.current_owner_agent_id || null;
  const currentFocus =
    execution?.current_goal || mainChain?.current_goal || "No active focus";
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
  const currentGoalRoute = goalNode?.route || findIndustryGoalRoute(payload, currentGoalId);
  const currentOwnerRoute = findIndustryAgentRoute(payload, currentOwnerAgentId);
  const latestEvidenceRoute = evidenceNode?.route || null;
  const staffingPresentation = buildStaffingPresentation(payload.staffing);
  const cycleSynthesis = payload.current_cycle?.synthesis;
  const synthesisConflicts = cycleSynthesis?.conflicts || [];
  const synthesisHoles = cycleSynthesis?.holes || [];
  const synthesisFindings = cycleSynthesis?.latest_findings || [];
  const synthesisSummary = cycleSynthesis
    ? [
        `Findings ${synthesisFindings.length}`,
        `Conflicts ${synthesisConflicts.length}`,
        `Holes ${synthesisHoles.length}`,
        `Actions ${(cycleSynthesis.recommended_actions || []).length}`,
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
        goalNode?.summary ||
        null,
      status: loopState,
      route: currentGoalRoute,
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
        {controlChain.currentGoal ? (
          <span className={styles.mainChainHeaderText}>
            Goal: {controlChain.currentGoal}
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
