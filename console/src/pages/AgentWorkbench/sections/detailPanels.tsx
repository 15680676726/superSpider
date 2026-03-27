import {
  AimOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Card,
  Empty,
  List,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";

import {
  agentWorkbenchText,
  formatPriorityTag,
  getIndustryRuntimeStatusLabel,
  getRiskLabel,
  getStatusLabel,
  runtimeCenterText,
} from "../copy";
import { localizeWorkbenchText } from "../localize";
import type {
  AgentProfile,
  EvidenceListItem,
  GoalDetail,
} from "../useAgentWorkbench";
import { presentExecutionActorName } from "../../../runtime/executionPresentation";
import {
  DELEGATE_TASK_CAPABILITY,
  delegationText,
  formatTime,
  riskColor,
  statusColor,
} from "./shared";
import {
  buildGoalTaskGroups,
  EvidenceRow,
  GoalTaskSummary,
  formatDelegationEvidenceSummary,
  translatedEvidenceAction,
} from "./taskPanels";

const { Paragraph, Text } = Typography;

export function GoalDetailPanel({
  detail,
  loading,
  error,
}: {
  detail: GoalDetail | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.goalDetailTitle} style={{ marginBottom: 32 }}>
        <Spin />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.goalDetailTitle} style={{ marginBottom: 32 }}>
        <Alert
          showIcon
          type="error"
          message={agentWorkbenchText.goalDetailUnavailable}
          description={error}
        />
      </Card>
    );
  }

  if (!detail) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.goalDetailTitle} style={{ marginBottom: 32 }}>
        <Empty
          description={agentWorkbenchText.goalDetailHint}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }

  const planSteps = detail.override?.plan_steps ?? [];
  const taskGroups = buildGoalTaskGroups(detail.tasks);
  const delegatedChildCount = taskGroups.groups.reduce(
    (count, group) => count + group.children.length,
    0,
  );
  const goalDelegationEvidence = detail.evidence.filter(
    (item) => item.capability_ref === DELEGATE_TASK_CAPABILITY,
  );
  const goalTaskTitleById = new Map(
    detail.tasks.map((entry) => [entry.task.id, entry.task.title]),
  );

  return (
    <Card className="baize-card"
      title={
        <Space wrap>
          <AimOutlined />
          <span>{localizeWorkbenchText(detail.goal.title)}</span>
          <Tag color={statusColor(detail.goal.status)}>
            {getStatusLabel(detail.goal.status)}
          </Tag>
          <Tag>{formatPriorityTag(detail.goal.priority)}</Tag>
        </Space>
      }
      style={{ marginBottom: 32 }}
    >
      {detail.goal.summary ? (
        <Paragraph>{localizeWorkbenchText(detail.goal.summary)}</Paragraph>
      ) : null}

      <Space wrap style={{ marginBottom: 32 }}>
        <Tag>{agentWorkbenchText.metricTasks(detail.stats.task_count)}</Tag>
        <Tag>{agentWorkbenchText.metricDecisions(detail.stats.decision_count)}</Tag>
        <Tag>{agentWorkbenchText.metricEvidence(detail.stats.evidence_count)}</Tag>
        <Tag>{agentWorkbenchText.metricPatches(detail.stats.patch_count)}</Tag>
        <Tag>{agentWorkbenchText.metricGrowth(detail.stats.growth_count)}</Tag>
        <Tag>{agentWorkbenchText.metricAgents(detail.stats.agent_count)}</Tag>
        {detail.goal.owner_scope ? <Tag>{detail.goal.owner_scope}</Tag> : null}
      </Space>

      {planSteps.length > 0 ? (
        <div style={{ marginBottom: 32 }}>
          <Text strong>{agentWorkbenchText.planStepsLabel}:</Text>
          <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {planSteps.map((step, index) => (
              <Tag key={`${index}-${step}`} color="blue">
                {index + 1}. {localizeWorkbenchText(step)}
              </Tag>
            ))}
          </div>
        </div>
      ) : null}

      {detail.industry?.instance_id ? (
        <div style={{ marginBottom: 32 }}>
          <Text strong>{agentWorkbenchText.industryContextLabel}:</Text>{" "}
          <Tag>{localizeWorkbenchText(detail.industry.label || detail.industry.instance_id)}</Tag>
          {detail.industry.role?.role_name ? (
            <Tag color="blue">
              {localizeWorkbenchText(String(detail.industry.role.role_name))}
            </Tag>
          ) : null}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <Card className="baize-card" size="small" title={agentWorkbenchText.linkedAgentsTitle}>
          <List
            dataSource={detail.agents}
            locale={{ emptyText: agentWorkbenchText.noLinkedAgents }}
            renderItem={(agent) => (
              <List.Item key={agent.agent_id}>
                <Space direction="vertical" size={0}>
                  <Space wrap>
                    <Text strong>{presentExecutionActorName(agent.agent_id, agent.name)}</Text>
                    <Tag color={statusColor(agent.status)}>
                      {getIndustryRuntimeStatusLabel(agent.status)}
                    </Tag>
                  </Space>
                  <Text type="secondary">
                    {localizeWorkbenchText(agent.role_name) || agentWorkbenchText.unassignedRole}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>

        <Card className="baize-card"
          size="small"
          title={
            <Space wrap>
              <span>{agentWorkbenchText.linkedTasksTitle}</span>
              {taskGroups.groups.length > 0 ? (
                <Tag color="purple">
                  {delegationText.delegatedGroupCount(taskGroups.groups.length)}
                </Tag>
              ) : null}
              {delegatedChildCount > 0 ? (
                <Tag color="geekblue">
                  {delegationText.childTaskCount(delegatedChildCount)}
                </Tag>
              ) : null}
              {taskGroups.standalone.length > 0 ? (
                <Tag>{delegationText.directExecutionCount(taskGroups.standalone.length)}</Tag>
              ) : null}
            </Space>
          }
        >
          {detail.tasks.length === 0 ? (
            <Empty
              description={agentWorkbenchText.noLinkedTasks}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {taskGroups.groups.length > 0 ? (
                <div>
                  <Text strong>{delegationText.delegatedTaskGroupsTitle}</Text>
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                    {taskGroups.groups.map((group) => (
                      <div
                        key={group.parent.task.id}
                        style={{
                          border: "1px solid var(--baize-border-color)",
                          borderRadius: 8,
                          padding: 12,
                          background: "transparent",
                        }}
                      >
                        <GoalTaskSummary
                          entry={group.parent}
                          agents={detail.agents}
                          tagLabel={delegationText.parentTaskTag}
                          tagColor="purple"
                        />
                        <div
                          style={{
                            marginTop: 12,
                            paddingLeft: 12,
                            borderLeft: "2px solid rgba(27, 79, 216, 0.35)",
                            display: "flex",
                            flexDirection: "column",
                            gap: 12,
                          }}
                        >
                          {group.children.map((child) => (
                            <GoalTaskSummary
                              key={child.task.id}
                              entry={child}
                              agents={detail.agents}
                              tagLabel={delegationText.childTaskTag}
                              tagColor="geekblue"
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {taskGroups.standalone.length > 0 ? (
                <div>
                  <Text strong>{delegationText.standaloneTasksTitle}</Text>
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                    {taskGroups.standalone.map((entry) => (
                      <div
                        key={entry.task.id}
                        style={{
                          border: "1px solid var(--baize-border-color)",
                          borderRadius: 8,
                          padding: 12,
                        }}
                      >
                        <GoalTaskSummary
                          entry={entry}
                          agents={detail.agents}
                          tagLabel={delegationText.standaloneTaskTag}
                          tagColor="default"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {taskGroups.orphanChildren.length > 0 ? (
                <div>
                  <Text strong>{delegationText.orphanChildTasksTitle}</Text>
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                    {taskGroups.orphanChildren.map((entry) => (
                      <div
                        key={entry.task.id}
                        style={{
                          border: "1px solid var(--baize-border-color)",
                          borderRadius: 8,
                          padding: 12,
                        }}
                      >
                        <GoalTaskSummary
                          entry={entry}
                          agents={detail.agents}
                          tagLabel={delegationText.childTaskTag}
                          tagColor="geekblue"
                        />
                        <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
                          {`${delegationText.parentTaskLabel}: ${
                            entry.task.parent_task_id || delegationText.pendingParentLink
                          }`}
                        </Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </Card>

        <Card className="baize-card"
          size="small"
          title={
            <Space wrap>
              <span>{delegationText.delegationEvidenceTitle}</span>
              {goalDelegationEvidence.length > 0 ? (
                <Tag color="purple">{goalDelegationEvidence.length}</Tag>
              ) : null}
            </Space>
          }
        >
          <List
            dataSource={goalDelegationEvidence.slice(0, 8)}
            locale={{ emptyText: delegationText.noDelegationEvidence }}
            renderItem={(item) => (
              <List.Item key={item.id}>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space wrap>
                    <Text strong>{translatedEvidenceAction(item)}</Text>
                    <Tag color="purple">{delegationText.childTaskTag}</Tag>
                    {item.task_id ? <Tag>{agentWorkbenchText.taskTag(item.task_id)}</Tag> : null}
                    {item.risk_level && item.risk_level !== "auto" ? (
                      <Tag color={riskColor(item.risk_level)}>
                        {getRiskLabel(item.risk_level)}
                      </Tag>
                    ) : null}
                  </Space>
                  <Text type="secondary">
                    {formatDelegationEvidenceSummary(
                      item,
                      detail.agents,
                      goalTaskTitleById,
                    )}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {formatTime(item.created_at, runtimeCenterText.noTimestamp)}
                    {item.environment_ref ? ` - ${item.environment_ref}` : ""}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      </div>
    </Card>
  );
}

export function EvidencePanel({
  evidence,
  agents,
}: {
  evidence: EvidenceListItem[];
  agents: AgentProfile[];
}) {
  if (evidence.length === 0) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.recentEvidenceTitle} style={{ marginBottom: 32 }}>
        <Empty
          description={agentWorkbenchText.noEvidenceRecords}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }

  const delegationEvidence = evidence.filter(
    (item) => item.capability_ref === DELEGATE_TASK_CAPABILITY,
  );
  const executionEvidence = evidence.filter(
    (item) => item.capability_ref !== DELEGATE_TASK_CAPABILITY,
  );

  return (
    <Card className="baize-card" title={agentWorkbenchText.recentEvidenceTitle} style={{ marginBottom: 32 }}>
      {delegationEvidence.length > 0 ? (
        <div style={{ marginBottom: executionEvidence.length > 0 ? 20 : 0 }}>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>{delegationText.delegationEvidenceTitle}</Text>
            <Tag color="purple">{delegationEvidence.length}</Tag>
          </Space>
          {delegationEvidence.slice(0, 6).map((item) => (
            <EvidenceRow key={item.id} item={item} agents={agents} />
          ))}
        </div>
      ) : null}

      {executionEvidence.length > 0 ? (
        <div>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>{delegationText.executionEvidenceTitle}</Text>
            <Tag>{executionEvidence.length}</Tag>
          </Space>
          {executionEvidence.slice(0, 10).map((item) => (
            <EvidenceRow key={item.id} item={item} agents={agents} />
          ))}
        </div>
      ) : null}
    </Card>
  );
}
