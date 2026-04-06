import type {
  IndustryExecutionSummary,
  IndustryInstanceDetail,
  IndustryMainChainGraph,
  IndustryMainChainNode,
} from "../../api/modules/industry";
import {
  formatPrimitiveValue,
  formatRuntimeFieldLabel,
} from "./text";

export const DETAIL_SECTION_ORDER = [
  "schedule",
  "state",
  "spec",
  "work_context",
  "task",
  "runtime",
  "task_subgraph",
  "host_contract",
  "seat_runtime",
  "host_companion_session",
  "browser_site_contract",
  "desktop_app_contract",
  "cooperative_adapter_availability",
  "workspace_graph",
  "host_event_summary",
  "host_events",
  "review",
  "goal",
  "decision",
  "patch",
  "event",
  "agent",
  "industry",
  "execution_core_identity",
  "strategy_memory",
  "lanes",
  "backlog",
  "current_cycle",
  "cycles",
  "assignments",
  "agent_reports",
  "kernel",
  "profile",
  "capability_surface",
  "team",
  "reports",
  "stats",
  "child_contexts",
  "threads",
  "routes",
  "tasks",
  "agents",
  "patches",
  "growth",
  "evidence",
  "decisions",
  "frames",
] as const;

export function metaRows(meta: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(meta)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 4)
    .map(([key, value]) => [
      formatRuntimeFieldLabel(key),
      Array.isArray(value) ? value.join(", ") : formatPrimitiveValue(value),
    ]);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function metaStringValue(
  meta: Record<string, unknown>,
  key: string,
): string | null {
  const value = meta[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function metaNumberValue(
  meta: Record<string, unknown>,
  key: string,
): number | null {
  const value = meta[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function primaryTitle(
  payload: Record<string, unknown>,
  fallback: string,
): string {
  const focusSelection = payload.focus_selection;
  if (isRecord(focusSelection) && typeof focusSelection.title === "string" && focusSelection.title) {
    return focusSelection.title;
  }
  for (const key of [
    "schedule",
    "work_context",
    "task",
    "goal",
    "decision",
    "patch",
    "event",
    "agent",
  ]) {
    const value = payload[key];
    if (!isRecord(value)) {
      continue;
    }
    const title =
      (typeof value.title === "string" && value.title) ||
      (typeof value.name === "string" && value.name) ||
      (typeof value.description === "string" && value.description) ||
      (typeof value.id === "string" && value.id);
    if (title) {
      return title;
    }
  }
  return fallback;
}

export function objectRows(record: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => [formatRuntimeFieldLabel(key), formatPrimitiveValue(value)]);
}

export function stringListValue(
  record: Record<string, unknown>,
  key: string,
): string[] {
  const value = record[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

export function isTaskReviewRecord(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.headline === "string" &&
    typeof value.objective === "string" &&
    Array.isArray(value.summary_lines) &&
    Array.isArray(value.next_actions)
  );
}

export function isIndustryExecutionSummary(
  value: unknown,
): value is IndustryExecutionSummary {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    typeof value.evidence_count === "number"
  );
}

export function isIndustryMainChainNode(value: unknown): value is IndustryMainChainNode {
  return (
    isRecord(value) &&
    typeof value.node_id === "string" &&
    typeof value.label === "string" &&
    typeof value.status === "string" &&
    typeof value.truth_source === "string"
  );
}

export function isIndustryMainChainGraph(
  value: unknown,
): value is IndustryMainChainGraph {
  return (
    isRecord(value) &&
    value.schema_version === "industry-main-chain-v1" &&
    Array.isArray(value.nodes) &&
    value.nodes.every(isIndustryMainChainNode)
  );
}

export function isIndustryInstanceDetailPayload(
  value: unknown,
): value is IndustryInstanceDetail {
  return (
    isRecord(value) &&
    typeof value.instance_id === "string" &&
    typeof value.owner_scope === "string" &&
    Array.isArray(value.goals) &&
    Array.isArray(value.agents) &&
    Array.isArray(value.tasks)
  );
}

export function findIndustryAgentRoute(
  payload: IndustryInstanceDetail,
  agentId?: string | null,
): string | null {
  if (!agentId) {
    return null;
  }
  const matched = payload.agents.find((agent) => agent.agent_id === agentId);
  return matched?.route ?? null;
}

export function findChainNode(
  graph: IndustryMainChainGraph | null,
  nodeId: string,
): IndustryMainChainNode | null {
  if (!graph) {
    return null;
  }
  return graph.nodes.find((node) => node.node_id === nodeId) ?? null;
}
