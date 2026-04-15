import {
  FileTextOutlined,
} from "@ant-design/icons";
import {
  Space,
  Tag,
  Typography,
} from "antd";

import {
  agentWorkbenchText,
  getArtifactKindLabel,
  getPhaseLabel,
  getReplayTypeLabel,
  getRiskLabel,
  getStatusLabel,
  runtimeCenterText,
} from "../copy";
import { localizeWorkbenchText } from "../localize";
import type {
  AgentProfile,
  EvidenceListItem,
  WorkTaskDetail,
} from "../useAgentWorkbench";
import {
  DELEGATE_TASK_CAPABILITY,
  delegationText,
  evidenceMetaText,
  evidenceMetadata,
  formatTime,
  normalizeNonEmpty,
  resolveAgentDisplayName,
  riskColor,
  statusColor,
} from "./shared";

const { Text } = Typography;

export type TaskGroup = {
  parent: WorkTaskDetail;
  children: WorkTaskDetail[];
};

export function latestTaskFeedback(
  entry: WorkTaskDetail,
): { text: string | null; isError: boolean } {
  const errorText = normalizeNonEmpty(entry.runtime?.last_error_summary);
  if (errorText) {
    return { text: localizeWorkbenchText(errorText), isError: true };
  }
  return {
    text:
      localizeWorkbenchText(
        normalizeNonEmpty(entry.runtime?.last_result_summary) ||
          normalizeNonEmpty(entry.task.summary),
      ) || null,
    isError: false,
  };
}

export function buildTaskGroups(tasks: WorkTaskDetail[]): {
  groups: TaskGroup[];
  standalone: WorkTaskDetail[];
  orphanChildren: WorkTaskDetail[];
} {
  const taskMap = new Map(tasks.map((entry) => [entry.task.id, entry]));
  const childrenByParent = new Map<string, WorkTaskDetail[]>();
  const groups: TaskGroup[] = [];
  const standalone: WorkTaskDetail[] = [];
  const orphanChildren: WorkTaskDetail[] = [];

  for (const entry of tasks) {
    const parentTaskId = normalizeNonEmpty(entry.task.parent_task_id);
    if (!parentTaskId) {
      continue;
    }
    const bucket = childrenByParent.get(parentTaskId) ?? [];
    bucket.push(entry);
    childrenByParent.set(parentTaskId, bucket);
  }

  for (const entry of tasks) {
    const parentTaskId = normalizeNonEmpty(entry.task.parent_task_id);
    if (parentTaskId) {
      continue;
    }
    const children = childrenByParent.get(entry.task.id) ?? [];
    if (children.length > 0) {
      groups.push({ parent: entry, children });
    } else {
      standalone.push(entry);
    }
  }

  for (const [parentTaskId, children] of childrenByParent.entries()) {
    if (!taskMap.has(parentTaskId)) {
      orphanChildren.push(...children);
    }
  }

  return { groups, standalone, orphanChildren };
}

export function delegationExecutedSummary(item: EvidenceListItem): string | null {
  const executed = evidenceMetadata(item).executed;
  if (!executed || typeof executed !== "object" || Array.isArray(executed)) {
    return null;
  }
  const summary = (executed as Record<string, unknown>).summary;
  return typeof summary === "string" && summary.trim() ? summary.trim() : null;
}

export function translatedEvidenceAction(item: EvidenceListItem): string {
  if (item.capability_ref === DELEGATE_TASK_CAPABILITY) {
    return "已委派子任务";
  }
  return localizeWorkbenchText(item.action_summary);
}

export function formatDelegationEvidenceSummary(
  item: EvidenceListItem,
  agents: AgentProfile[],
  taskTitleById?: Map<string, string>,
): string {
  const childTaskId = evidenceMetaText(item, "child_task_id");
  const childTaskTitle = childTaskId ? taskTitleById?.get(childTaskId) ?? null : null;
  const childOwnerAgentId = evidenceMetaText(item, "child_owner_agent_id");
  const executedSummary = delegationExecutedSummary(item);
  const parts: string[] = [];

  if (childTaskTitle) {
    parts.push(`已创建子任务“${localizeWorkbenchText(childTaskTitle)}”`);
  } else if (childTaskId) {
    parts.push(`已创建子任务 ${childTaskId}`);
  } else {
    parts.push("已创建委派子任务");
  }

  if (childOwnerAgentId) {
    parts.push(
      `${delegationText.targetAgentLabel}: ${
        resolveAgentDisplayName(childOwnerAgentId, agents) ?? childOwnerAgentId
      }`,
    );
  }

  if (executedSummary) {
    parts.push(
      `${delegationText.latestFeedbackLabel}: ${localizeWorkbenchText(executedSummary)}`,
    );
  }

  return parts.join(" | ");
}

export function TaskSummaryCard({
  entry,
  agents,
  tagLabel,
  tagColor,
}: {
  entry: WorkTaskDetail;
  agents: AgentProfile[];
  tagLabel: string;
  tagColor: string;
}) {
  const ownerAgentId =
    normalizeNonEmpty(entry.task.owner_agent_id) ||
    normalizeNonEmpty(entry.runtime?.last_owner_agent_id) ||
    null;
  const ownerLabel = resolveAgentDisplayName(ownerAgentId, agents);
  const feedback = latestTaskFeedback(entry);

  return (
    <Space direction="vertical" size={4} style={{ width: "100%" }}>
      <Space wrap>
        <Text strong>{localizeWorkbenchText(entry.task.title)}</Text>
        <Tag color={tagColor}>{tagLabel}</Tag>
        <Tag color={statusColor(entry.task.status)}>
          {getStatusLabel(entry.task.status)}
        </Tag>
        <Tag color={riskColor(entry.task.current_risk_level)}>
          {getRiskLabel(entry.task.current_risk_level)}
        </Tag>
        {entry.runtime?.current_phase ? (
          <Tag>{getPhaseLabel(entry.runtime.current_phase)}</Tag>
        ) : null}
      </Space>
      <Text type="secondary">
        {ownerLabel ? `${agentWorkbenchText.ownerLabel}: ${ownerLabel} | ` : ""}
        {agentWorkbenchText.taskEvidenceDecisionLine(
          entry.evidence_count,
          entry.decision_count,
        )}
      </Text>
      {feedback.text ? (
        <Text type={feedback.isError ? "danger" : "secondary"}>
          {`${delegationText.latestFeedbackLabel}: ${feedback.text}`}
        </Text>
      ) : null}
    </Space>
  );
}

export function EvidenceRow({
  item,
  agents,
  taskTitleById,
}: {
  item: EvidenceListItem;
  agents: AgentProfile[];
  taskTitleById?: Map<string, string>;
}) {
  const childTaskId = evidenceMetaText(item, "child_task_id");
  const childOwnerAgentId = evidenceMetaText(item, "child_owner_agent_id");
  const childTaskTitle = childTaskId ? taskTitleById?.get(childTaskId) ?? null : null;
  const summary =
    item.capability_ref === DELEGATE_TASK_CAPABILITY
      ? formatDelegationEvidenceSummary(item, agents, taskTitleById)
      : item.result_summary;
  const artifacts = Array.isArray(item.artifacts) ? item.artifacts.slice(0, 2) : [];
  const replayPointers = Array.isArray(item.replay_pointers)
    ? item.replay_pointers.slice(0, 2)
    : [];

  return (
    <div
      key={item.id}
      style={{
        padding: "8px 0",
        borderBottom: "var(--baize-border)",
      }}
    >
      <Space wrap>
        <FileTextOutlined />
        <Text strong>{translatedEvidenceAction(item)}</Text>
        {item.capability_ref === DELEGATE_TASK_CAPABILITY ? (
          <Tag color="purple">{delegationText.childTaskTag}</Tag>
        ) : null}
        {item.capability_ref ? <Tag color="blue">{item.capability_ref}</Tag> : null}
        {item.task_id ? <Tag>{agentWorkbenchText.taskTag(item.task_id)}</Tag> : null}
        {typeof item.artifact_count === "number" && item.artifact_count > 0 ? (
          <Tag color="gold">{agentWorkbenchText.evidenceArtifactCount(item.artifact_count)}</Tag>
        ) : null}
        {typeof item.replay_count === "number" && item.replay_count > 0 ? (
          <Tag>{agentWorkbenchText.evidenceReplayCount(item.replay_count)}</Tag>
        ) : null}
        {item.risk_level && item.risk_level !== "auto" ? (
          <Tag color={riskColor(item.risk_level)}>{getRiskLabel(item.risk_level)}</Tag>
        ) : null}
      </Space>
      {childTaskId || childOwnerAgentId ? (
        <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {childTaskId ? (
            <Tag color="geekblue">
              {childTaskTitle
                ? `${delegationText.childTaskLabel}: ${localizeWorkbenchText(childTaskTitle)}`
                : `${delegationText.childTaskLabel}: ${childTaskId}`}
            </Tag>
          ) : null}
          {childOwnerAgentId ? (
            <Tag>
              {`${delegationText.targetAgentLabel}: ${
                resolveAgentDisplayName(childOwnerAgentId, agents) ??
                childOwnerAgentId
              }`}
            </Tag>
          ) : null}
        </div>
      ) : null}
      <div style={{ marginTop: 4 }}>
        <Text type="secondary">{localizeWorkbenchText(summary)}</Text>
      </div>
      {artifacts.length > 0 ? (
        <div style={{ marginTop: 4, display: "grid", gap: 2 }}>
          {artifacts.map((artifact, index) => {
            const label = getArtifactKindLabel(artifact.artifact_type) || "产物";
            const parts = [
              label,
              normalizeNonEmpty(artifact.summary),
              normalizeNonEmpty(artifact.storage_uri),
            ].filter((value): value is string => Boolean(value));
            return (
              <Text key={artifact.id || `${item.id}:artifact:${index}`} type="secondary">
                {localizeWorkbenchText(parts.join(" · "))}
              </Text>
            );
          })}
        </div>
      ) : null}
      {replayPointers.length > 0 ? (
        <div style={{ marginTop: 4, display: "grid", gap: 2 }}>
          {replayPointers.map((replay, index) => {
            const label = getReplayTypeLabel(replay.replay_type) || "回放";
            const parts = [
              label,
              normalizeNonEmpty(replay.summary),
              normalizeNonEmpty(replay.storage_uri),
            ].filter((value): value is string => Boolean(value));
            return (
              <Text key={replay.id || `${item.id}:replay:${index}`} type="secondary">
                {localizeWorkbenchText(parts.join(" · "))}
              </Text>
            );
          })}
        </div>
      ) : null}
      <Text type="secondary" style={{ fontSize: 11 }}>
        {formatTime(item.created_at, runtimeCenterText.noTimestamp)}
        {item.environment_ref ? ` - ${item.environment_ref}` : ""}
      </Text>
    </div>
  );
}
