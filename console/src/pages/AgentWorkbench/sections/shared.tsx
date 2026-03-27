import React from "react";
import {
  FolderOpenOutlined,
  GlobalOutlined,
  MessageOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import type { AgentProfile, EvidenceListItem } from "../useAgentWorkbench";
import { runtimeRiskColor, runtimeStatusColor } from "../../../runtime/tagSemantics";

export const TAB_KEYS = new Set(["workbench", "workspace", "daily", "weekly", "growth"]);
export const DELEGATE_TASK_CAPABILITY = "system:delegate_task";
export const EXECUTION_CORE_ROLE_ID = "execution-core";

export const delegationText = {
  delegatedTaskGroupsTitle: "委派任务组",
  standaloneTasksTitle: "直接执行任务",
  orphanChildTasksTitle: "待关联子任务",
  parentTaskTag: "父任务",
  childTaskTag: "子任务",
  standaloneTaskTag: "直接任务",
  delegatedGroupCount: (count: number) => `委派组 ${count}`,
  childTaskCount: (count: number) => `子任务 ${count}`,
  directExecutionCount: (count: number) => `直接任务 ${count}`,
  latestFeedbackLabel: "最新反馈",
  delegationEvidenceTitle: "委派证据",
  executionEvidenceTitle: "执行证据",
  targetAgentLabel: "目标智能体",
  childTaskLabel: "子任务",
  parentTaskLabel: "父任务",
  noDelegationEvidence: "暂无委派证据",
  noExecutionEvidence: "暂无执行证据",
  pendingParentLink: "待补父任务关联",
} as const;

export function statusColor(status: string): string {
  return runtimeStatusColor(status);
}

export function riskColor(level: string): string {
  return runtimeRiskColor(level);
}

export function envIcon(kind: string) {
  const map: Record<string, React.ReactNode> = {
    workspace: <FolderOpenOutlined />,
    browser: <GlobalOutlined />,
    session: <MessageOutlined />,
    terminal: <ThunderboltOutlined />,
  };
  return map[kind] || <FolderOpenOutlined />;
}

export function envColor(kind: string): string {
  const map: Record<string, string> = {
    workspace: "var(--baize-success)",
    browser: "var(--baize-info)",
    session: "#13c2c2",
    terminal: "var(--baize-warning)",
  };
  return map[kind] || "var(--baize-text-dim)";
}

export function formatTime(value: string | null | undefined, fallback: string): string {
  if (!value) return fallback;
  const parsed = new Date(value.endsWith("Z") ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function normalizeNonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

export function resolveAgentDisplayName(
  agentId: string | null | undefined,
  agents: AgentProfile[],
): string | null {
  const normalizedId = normalizeNonEmpty(agentId);
  if (!normalizedId) {
    return null;
  }
  const matched = agents.find((agent) => agent.agent_id === normalizedId);
  if (!matched?.name) {
    return normalizedId;
  }
  return matched.name === normalizedId
    ? normalizedId
    : `${matched.name} (${normalizedId})`;
}

export function evidenceMetadata(item: EvidenceListItem): Record<string, unknown> {
  return isRecord(item.metadata) ? item.metadata : {};
}

export function evidenceMetaText(
  item: EvidenceListItem,
  key: string,
): string | null {
  const value = evidenceMetadata(item)[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}
