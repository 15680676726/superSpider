import React, { useMemo } from "react";
import {
  Button,
  Card,
  Empty,
  Input,
  List,
  Radio,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  SafetyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  agentWorkbenchText,
  commonText,
  getAssignmentSourceLabel,
  getEnvironmentDisplayName,
  getEnvironmentKindLabel,
  getIndustryRoleClassLabel,
  getIndustryRuntimeStatusLabel,
  getModeLabel,
  getRiskLabel,
  getStatusLabel,
  runtimeCenterText,
} from "./copy";
import { localizeWorkbenchList, localizeWorkbenchText } from "./localize";
import {
  type AgentCapabilityDecision,
  type AgentDetail,
  type AgentProfile,
  type EnvironmentItem,
} from "./useAgentWorkbench";
import type { CapabilityMount } from "../../api";
import {
  presentDesiredStateLabel,
  presentEmploymentModeLabel,
  presentExecutionActorName,
  presentRuntimeStatusLabel,
} from "../../runtime/executionPresentation";
import {
  DELEGATE_TASK_CAPABILITY,
  delegationText,
  envColor,
  envIcon,
  EXECUTION_CORE_ROLE_ID,
  evidenceMetadata,
  evidenceMetaText,
  formatTime,
  isRecord,
  normalizeNonEmpty,
  resolveAgentDisplayName,
  riskColor,
  statusColor,
  TAB_KEYS,
} from "./sections/shared";
import {
  buildTaskGroups,
  EvidenceRow,
  formatDelegationEvidenceSummary,
  TaskSummaryCard,
  latestTaskFeedback,
  translatedEvidenceAction,
  delegationExecutedSummary,
} from "./sections/taskPanels";
import {
  EvidencePanel,
} from "./sections/detailPanels";
import { ActorRuntimePanel } from "./sections/runtimePanels";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;

function isExecutionCoreAgent(agent: AgentProfile | null | undefined): boolean {
  if (!agent) {
    return false;
  }
  return (
    agent.industry_role_id === EXECUTION_CORE_ROLE_ID ||
    agent.agent_id === "copaw-agent-runner"
  );
}

function ProfileCard({
  agent,
  onOpenChat,
}: {
  agent: AgentProfile;
  onOpenChat: () => void;
}) {
  return (
    <Card className="baize-card"
      title={
        <Space wrap>
          <UserOutlined />
          <span>{presentExecutionActorName(agent.agent_id, agent.name)}</span>
          <Tag color={statusColor(agent.status)}>
            {getIndustryRuntimeStatusLabel(agent.status)}
          </Tag>
          <Tag color={riskColor(agent.risk_level)}>
            <SafetyOutlined /> {getRiskLabel(agent.risk_level)}
          </Tag>
        </Space>
      }
      extra={
        <Button className="baize-btn" size="small" type="link" onClick={onOpenChat}>
          {"进入主脑聊天"}
        </Button>
      }
      style={{ marginBottom: 32 }}
    >
      <Paragraph>
        <Text strong>{agentWorkbenchText.roleLabel}:</Text>{" "}
        {localizeWorkbenchText(agent.role_name) || agentWorkbenchText.unassignedRole}
        {agent.role_summary ? ` - ${localizeWorkbenchText(agent.role_summary)}` : ""}
      </Paragraph>
      <Paragraph>
        <Text strong>{agentWorkbenchText.classLabel}:</Text>{" "}
        {getIndustryRoleClassLabel(agent.agent_class)} |{" "}
        <Text strong>{agentWorkbenchText.employmentLabel}:</Text>{" "}
        {presentEmploymentModeLabel(agent.employment_mode)} |{" "}
        <Text strong>{agentWorkbenchText.activationLabel}:</Text>{" "}
        {getIndustryRuntimeStatusLabel(agent.activation_mode)}
        {agent.suspendable ? ` | ${agentWorkbenchText.suspendable}` : ""}
      </Paragraph>
      {agent.runtime_status || agent.desired_state || agent.thread_id ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.runtimeLabel}:</Text>{" "}
          {presentRuntimeStatusLabel(agent.runtime_status || agent.status)}
          {agent.desired_state
            ? ` | 调度目标：${presentDesiredStateLabel(agent.desired_state)}`
            : ""}
          {typeof agent.queue_depth === "number"
            ? ` | ${agentWorkbenchText.queueTag(agent.queue_depth)}`
            : ""}
          {agent.current_mailbox_id
            ? ` | ${agentWorkbenchText.mailboxTag(agent.current_mailbox_id)}`
            : ""}
          {agent.thread_id ? ` | ${agent.thread_id}` : ""}
        </Paragraph>
      ) : null}
      {agent.mission ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.missionLabel}:</Text>{" "}
          {localizeWorkbenchText(agent.mission)}
        </Paragraph>
      ) : null}
      {agent.reports_to ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.reportsToLabel}:</Text>{" "}
          {presentExecutionActorName(agent.reports_to, agent.reports_to)}
        </Paragraph>
      ) : null}
      {agent.industry_instance_id ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.industryTeamLabel}:</Text>{" "}
          {agent.industry_instance_id}
        </Paragraph>
      ) : null}
      {agent.current_focus ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.currentFocusLabel}:</Text>{" "}
          {localizeWorkbenchText(agent.current_focus)}
        </Paragraph>
      ) : null}
      {agent.environment_summary ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.environmentLabel}:</Text>{" "}
          {localizeWorkbenchText(agent.environment_summary)}
        </Paragraph>
      ) : null}
      {agent.environment_constraints.length > 0 ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.environmentConstraintsLabel}:</Text>{" "}
          {localizeWorkbenchList(agent.environment_constraints).join(" | ")}
        </Paragraph>
      ) : null}
      {agent.today_output_summary ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.todayLabel}:</Text>{" "}
          {localizeWorkbenchText(agent.today_output_summary)}
        </Paragraph>
      ) : null}
      {agent.latest_evidence_summary ? (
        <Paragraph>
          <Text strong>{agentWorkbenchText.latestEvidenceLabel}:</Text>{" "}
          {localizeWorkbenchText(agent.latest_evidence_summary)}
        </Paragraph>
      ) : null}
      {agent.capabilities.length > 0 ? (
        <div>
          <Text strong>{agentWorkbenchText.capabilitiesLabel}:</Text>{" "}
          {agent.capabilities.slice(0, 12).map((capability) => (
            <Tag key={capability}>{capability}</Tag>
          ))}
        </div>
      ) : null}
      {agent.evidence_expectations.length > 0 ? (
        <div style={{ marginTop: 12 }}>
          <Text strong>{agentWorkbenchText.evidenceExpectationsLabel}:</Text>{" "}
          {localizeWorkbenchList(agent.evidence_expectations.slice(0, 6)).map((item) => (
            <Tag key={item}>{item}</Tag>
          ))}
        </div>
      ) : null}
    </Card>
  );
}

function CapabilityGovernancePanel({
  agent,
  detail,
  capabilityCatalog,
  capabilityCatalogLoading,
  capabilityActionKey,
  onRefresh,
  onSubmitGovernedChange,
  onResolveDecision,
}: {
  agent: AgentProfile;
  detail: AgentDetail | null;
  capabilityCatalog: CapabilityMount[];
  capabilityCatalogLoading: boolean;
  capabilityActionKey: string | null;
  onRefresh: () => Promise<void>;
  onSubmitGovernedChange: (
    agentId: string,
    payload: {
      capabilities: string[];
      mode: "replace" | "merge";
      actor?: string;
      reason?: string | null;
      use_recommended?: boolean;
    },
    options?: { requireActor?: boolean },
  ) => Promise<{
    submitted?: boolean;
    updated?: boolean;
    result?: {
      summary?: string;
      error?: string | null;
      phase?: string;
      decision_request_id?: string | null;
    };
    decision?: AgentCapabilityDecision | null;
  }>;
  onResolveDecision: (
    decisionId: string,
    action: "approve" | "reject" | "review",
    payload?: Record<string, unknown>,
  ) => Promise<Record<string, unknown>>;
}) {
  const surface = detail?.capability_surface ?? null;
  const requireActor = Boolean(detail?.runtime);
  const [mode, setMode] = React.useState<"replace" | "merge">("replace");
  const [selectedCapabilities, setSelectedCapabilities] = React.useState<string[]>([]);
  const [reason, setReason] = React.useState("");
  const fallbackCapabilities = useMemo(() => {
    const recommendedCapabilities = surface?.recommended_capabilities ?? [];
    if (recommendedCapabilities.length > 0) {
      return recommendedCapabilities;
    }
    return surface?.effective_capabilities ?? [];
  }, [surface?.effective_capabilities, surface?.recommended_capabilities]);

  React.useEffect(() => {
    setSelectedCapabilities(fallbackCapabilities);
    setMode("replace");
    setReason("");
  }, [agent.agent_id, fallbackCapabilities]);

  const catalogOptions = useMemo(
    () =>
      [...capabilityCatalog]
        .sort((left, right) => left.id.localeCompare(right.id))
        .map((capability) => ({
          label: `${capability.id}${capability.enabled ? "" : "（未启用）"}`,
          value: capability.id,
        })),
    [capabilityCatalog],
  );

  const handleGovernedSubmit = async (useRecommended: boolean) => {
    try {
      const result = await onSubmitGovernedChange(
        agent.agent_id,
        {
          capabilities: useRecommended ? [] : selectedCapabilities,
          mode,
          reason: reason || null,
          use_recommended: useRecommended,
        },
        { requireActor },
      );
      if (result.result?.phase === "waiting-confirm") {
        const decisionId = result.result.decision_request_id || result.decision?.id;
        message.warning(
          decisionId
            ? agentWorkbenchText.capabilityDecisionQueued(decisionId)
            : agentWorkbenchText.capabilityDecisionQueuedNoId,
        );
      } else if (result.updated) {
        message.success(
          localizeWorkbenchText(result.result?.summary) ||
            agentWorkbenchText.capabilityUpdated,
        );
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    }
  };

  const handleDecisionAction = async (
    decision: AgentCapabilityDecision,
    action: "approve" | "reject" | "review",
  ) => {
    try {
      await onResolveDecision(
        decision.id,
        action,
        action === "approve"
          ? {
              resolution: `批准 ${presentExecutionActorName(agent.agent_id, agent.name)} 的能力治理请求`,
              execute: true,
            }
          : action === "reject"
            ? {
                resolution: `拒绝 ${presentExecutionActorName(agent.agent_id, agent.name)} 的能力治理请求`,
              }
            : { actor: "copaw-governance" },
      );
      message.success(
        agentWorkbenchText.capabilityDecisionResult(action),
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    }
  };

  if (!surface) {
    return (
      <Card className="baize-card"
        title={agentWorkbenchText.capabilityGovernanceTitle}
        style={{ marginBottom: 32 }}
      >
        <Empty
          description={agentWorkbenchText.capabilityGovernanceUnavailable}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }

  return (
    <Card className="baize-card"
      title={
        <Space wrap>
          <SafetyOutlined />
          <span>{agentWorkbenchText.capabilityGovernanceTitle}</span>
          <Tag color="gold">
            {agentWorkbenchText.capabilityGovernanceMode}
          </Tag>
          {surface.drift_detected ? (
            <Tag color="orange">{agentWorkbenchText.capabilityDriftDetected}</Tag>
          ) : (
            <Tag color="green">{agentWorkbenchText.capabilityAligned}</Tag>
          )}
        </Space>
      }
      extra={
        <Button className="baize-btn" size="small" onClick={() => void onRefresh()}>
          {commonText.refresh}
        </Button>
      }
      style={{ marginBottom: 32 }}
    >
      <Paragraph type="secondary">
        {agentWorkbenchText.capabilityGovernanceSummary}
      </Paragraph>

      <Space wrap style={{ marginBottom: 32 }}>
        <Tag>{agentWorkbenchText.capabilityBaselineCount(surface.stats.baseline_count)}</Tag>
        <Tag>{agentWorkbenchText.capabilityBlueprintCount(surface.stats.blueprint_count)}</Tag>
        <Tag>{agentWorkbenchText.capabilityExplicitCount(surface.stats.explicit_count)}</Tag>
        <Tag color="green">
          {agentWorkbenchText.capabilityEffectiveCount(surface.stats.effective_count)}
        </Tag>
        <Tag color="orange">
          {agentWorkbenchText.capabilityPendingCount(surface.stats.pending_decision_count)}
        </Tag>
      </Space>

      <div style={{ marginBottom: 32 }}>
        <Text strong>
          {agentWorkbenchText.recommendedCapabilitiesLabel}:
        </Text>
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {surface.recommended_capabilities.length === 0 ? (
            <Text type="secondary">{agentWorkbenchText.noRecommendedCapabilities}</Text>
          ) : (
            surface.recommended_capabilities.map((capability) => (
              <Tag key={`recommended-${capability}`} color="gold">
                {capability}
              </Tag>
            ))
          )}
        </div>
      </div>

      <div style={{ marginBottom: 32 }}>
        <Text strong>
          {agentWorkbenchText.effectiveCapabilitiesLabel}:
        </Text>
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {surface.items
            .filter((item) => item.assignment_sources.includes("effective"))
            .map((item) => {
              const assignmentSourceLabel = item.assignment_sources
                .map((source) => getAssignmentSourceLabel(source))
                .join(" / ");
              return (
                <Tooltip
                  key={item.id}
                  title={
                    item.summary
                      ? `${localizeWorkbenchText(item.summary)}\n${assignmentSourceLabel}`
                      : assignmentSourceLabel
                  }
                >
                  <Tag color={item.enabled ? "blue" : "default"}>
                    {item.id}
                    {assignmentSourceLabel ? ` | ${assignmentSourceLabel}` : ""}
                  </Tag>
                </Tooltip>
              );
            })}
        </div>
      </div>

      <Card className="baize-card"
        size="small"
        title={agentWorkbenchText.capabilityChangeRequestTitle}
        style={{ marginBottom: 32 }}
      >
        <Paragraph type="secondary">
          {agentWorkbenchText.capabilityChangeRequestSummary}
        </Paragraph>
        <div style={{ marginBottom: 32 }}>
          <Text strong>
            {agentWorkbenchText.capabilityAssignmentModeLabel}:
          </Text>
          <div style={{ marginTop: 8 }}>
            <Radio.Group
              value={mode}
              onChange={(event) => setMode(event.target.value as "replace" | "merge")}
            >
              <Radio.Button value="replace">{agentWorkbenchText.capabilityModeReplace}</Radio.Button>
              <Radio.Button value="merge">{agentWorkbenchText.capabilityModeMerge}</Radio.Button>
            </Radio.Group>
          </div>
        </div>
        <div style={{ marginBottom: 32 }}>
          <Text strong>
            {agentWorkbenchText.capabilityPickerLabel}:
          </Text>
          <Select
            mode="multiple"
            allowClear
            showSearch
            optionFilterProp="label"
            value={selectedCapabilities}
            onChange={(values) => setSelectedCapabilities(values)}
            options={catalogOptions}
            loading={capabilityCatalogLoading}
            style={{ width: "100%", marginTop: 8 }}
            placeholder={agentWorkbenchText.capabilityPickerPlaceholder}
          />
        </div>
        <div style={{ marginBottom: 32 }}>
          <Text strong>
            {agentWorkbenchText.capabilityReasonLabel}:
          </Text>
          <TextArea
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={agentWorkbenchText.capabilityReasonPlaceholder}
            style={{ marginTop: 8 }}
          />
        </div>
        <Space wrap>
          <Button className="baize-btn"
            onClick={() =>
              setSelectedCapabilities(surface.recommended_capabilities)
            }
          >
            {agentWorkbenchText.useRecommendedCapabilities}
          </Button>
          <Button className="baize-btn"
            loading={
              capabilityActionKey ===
              `govern:${requireActor ? "actor" : "agent"}:${agent.agent_id}`
            }
            onClick={() => void handleGovernedSubmit(true)}
          >
            {agentWorkbenchText.submitRecommendedGovernance}
          </Button>
          <Button className="baize-btn"
            type="primary"
            disabled={selectedCapabilities.length === 0}
            loading={
              capabilityActionKey ===
              `govern:${requireActor ? "actor" : "agent"}:${agent.agent_id}`
            }
            onClick={() => void handleGovernedSubmit(false)}
          >
            {agentWorkbenchText.submitGovernedChange}
          </Button>
        </Space>
      </Card>

      <Card className="baize-card"
        size="small"
        title={agentWorkbenchText.capabilityDecisionQueueTitle}
      >
        <List
          dataSource={surface.pending_decisions.length > 0 ? surface.pending_decisions : surface.recent_decisions}
          locale={{
            emptyText: agentWorkbenchText.noCapabilityDecisions,
          }}
          renderItem={(decision) => (
            <List.Item
              key={decision.id}
              actions={[
                decision.actions?.approve ? (
                  <Button className="baize-btn"
                    key="approve"
                    size="small"
                    type="primary"
                    loading={capabilityActionKey === `decision:approve:${decision.id}`}
                    onClick={() => void handleDecisionAction(decision, "approve")}
                  >
                    {runtimeCenterText.actionApprove}
                  </Button>
                ) : null,
                decision.actions?.reject ? (
                  <Button className="baize-btn"
                    key="reject"
                    size="small"
                    danger
                    loading={capabilityActionKey === `decision:reject:${decision.id}`}
                    onClick={() => void handleDecisionAction(decision, "reject")}
                  >
                    {runtimeCenterText.actionReject}
                  </Button>
                ) : null,
              ].filter(Boolean)}
            >
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                <Space wrap>
                  <Text strong>
                    {localizeWorkbenchText(decision.summary) || decision.id}
                  </Text>
                  {decision.status ? (
                    <Tag color={statusColor(decision.status)}>
                      {getStatusLabel(decision.status)}
                    </Tag>
                  ) : null}
                  {decision.risk_level ? (
                    <Tag color={riskColor(decision.risk_level)}>
                      {getRiskLabel(decision.risk_level)}
                    </Tag>
                  ) : null}
                </Space>
                {decision.capabilities.length > 0 ? (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {decision.capabilities.map((capability) => (
                      <Tag key={`${decision.id}-${capability}`}>{capability}</Tag>
                    ))}
                  </div>
                ) : null}
                <Text type="secondary">
                  {getModeLabel(decision.capability_assignment_mode || "replace")}
                  {decision.actor ? ` | ${decision.actor}` : ""}
                  {decision.created_at
                    ? ` | ${formatTime(decision.created_at, runtimeCenterText.noTimestamp)}`
                    : ""}
                </Text>
                {decision.reason ? (
                  <Text type="secondary">
                    {localizeWorkbenchText(decision.reason)}
                  </Text>
                ) : null}
              </Space>
            </List.Item>
          )}
        />
      </Card>
    </Card>
  );
}

function EnvironmentPanel({ environments }: { environments: EnvironmentItem[] }) {
  if (environments.length === 0) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.activeEnvironmentsTitle} style={{ marginBottom: 32 }}>
        <Empty
          description={agentWorkbenchText.noActiveEnvironments}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }
  return (
    <Card className="baize-card" title={agentWorkbenchText.activeEnvironmentsTitle} style={{ marginBottom: 32 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {environments.slice(0, 8).map((env) => (
          <Tooltip key={env.id} title={env.ref}>
            <Card className="baize-card"
              size="small"
              style={{ minWidth: 180, borderLeft: `3px solid ${envColor(env.kind)}` }}
            >
              <Space>
                {envIcon(env.kind)}
                <Text strong>{getEnvironmentDisplayName(env.kind, env.display_name)}</Text>
              </Space>
              <br />
              <Text type="secondary" style={{ fontSize: 11 }}>
                {agentWorkbenchText.environmentEvidenceLine(
                  getEnvironmentKindLabel(env.kind),
                  env.evidence_count,
                )}
              </Text>
              {env.last_active_at ? (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {agentWorkbenchText.lastActiveLine(
                      formatTime(env.last_active_at, runtimeCenterText.noTimestamp),
                    )}
                  </Text>
                </>
              ) : null}
            </Card>
          </Tooltip>
        ))}
      </div>
    </Card>
  );
}

export {
  TAB_KEYS,
  DELEGATE_TASK_CAPABILITY,
  EXECUTION_CORE_ROLE_ID,
  delegationText,
  statusColor,
  riskColor,
  envIcon,
  envColor,
  formatTime,
  isRecord,
  normalizeNonEmpty,
  resolveAgentDisplayName,
  latestTaskFeedback,
  buildTaskGroups,
  evidenceMetadata,
  evidenceMetaText,
  delegationExecutedSummary,
  translatedEvidenceAction,
  formatDelegationEvidenceSummary,
  TaskSummaryCard,
  EvidenceRow,
  isExecutionCoreAgent,
  ProfileCard,
  CapabilityGovernancePanel,
  ActorRuntimePanel,
  EnvironmentPanel,
  EvidencePanel,
};

