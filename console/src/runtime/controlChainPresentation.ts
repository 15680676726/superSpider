import type {
  IndustryInstanceDetail,
  IndustryMainChainGraph,
  IndustryMainChainNode,
  IndustryRuntimeCycleSynthesis,
} from "../api/modules/industry";
import { normalizeDisplayChinese } from "../text";
import { presentRuntimeStatusLabel } from "./executionPresentation";

export const CONTROL_CHAIN_NODE_ORDER = [
  "writeback",
  "backlog",
  "cycle",
  "assignment",
  "report",
  "replan",
] as const;

const CONTROL_CHAIN_LABELS: Record<string, string> = {
  writeback: "写回",
  backlog: "待办",
  cycle: "周期",
  assignment: "派工",
  report: "汇报",
  replan: "重规划",
};

export type ControlChainNodeId = (typeof CONTROL_CHAIN_NODE_ORDER)[number];

export interface ControlChainMetricPresentation {
  key: string;
  label: string;
  value: string;
}

export interface ControlChainNodePresentation {
  id: string;
  label: string;
  status: string;
  statusLabel: string;
  truthSource: string;
  currentRef: string | null;
  route: string | null;
  summary: string | null;
  backflowPort: string | null;
  metrics: ControlChainMetricPresentation[];
}

export interface ControlChainSynthesisPresentation {
  findingCount: number;
  conflictCount: number;
  holeCount: number;
  actionCount: number;
  needsReplan: boolean;
  summary: string;
  controlCoreContract: string[];
}

export interface ControlChainPresentation {
  loopState: string | null;
  loopStateLabel: string;
  currentFocus: string | null;
  currentOwner: string | null;
  currentRisk: string | null;
  latestEvidenceSummary: string | null;
  nodes: ControlChainNodePresentation[];
  synthesis: ControlChainSynthesisPresentation | null;
  hasAnyState: boolean;
}

function normalizeNonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function humanizeToken(value: string): string {
  return normalizeDisplayChinese(
    value
      .replace(/[_-]+/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .trim(),
  );
}

function isMainChainGraph(value: unknown): value is IndustryMainChainGraph {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as IndustryMainChainGraph).schema_version === "industry-main-chain-v1" &&
    Array.isArray((value as IndustryMainChainGraph).nodes)
  );
}

function isIndustryDetail(value: unknown): value is IndustryInstanceDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as IndustryInstanceDetail).instance_id === "string"
  );
}

function resolveChainGraph(
  value: IndustryInstanceDetail | IndustryMainChainGraph | null | undefined,
): IndustryMainChainGraph | null {
  if (!value) {
    return null;
  }
  if (isMainChainGraph(value)) {
    return value;
  }
  if (isIndustryDetail(value) && isMainChainGraph(value.main_chain)) {
    return value.main_chain;
  }
  return null;
}

function resolveSynthesis(
  value: IndustryInstanceDetail | IndustryMainChainGraph | null | undefined,
): IndustryRuntimeCycleSynthesis | null {
  if (isIndustryDetail(value)) {
    return value.current_cycle?.synthesis || null;
  }
  return null;
}

function presentNodeLabel(nodeId: string, fallback?: string | null): string {
  return (
    CONTROL_CHAIN_LABELS[nodeId] ||
    normalizeNonEmpty(fallback || undefined) ||
    humanizeToken(nodeId) ||
    nodeId
  );
}

function presentMetricValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function presentNodeMetrics(
  metrics: Record<string, unknown>,
): ControlChainMetricPresentation[] {
  return Object.entries(metrics || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => ({
      key,
      label: humanizeToken(key),
      value: presentMetricValue(value),
    }));
}

function presentNode(node: IndustryMainChainNode): ControlChainNodePresentation {
  return {
    id: node.node_id,
    label: presentNodeLabel(node.node_id, node.label),
    status: node.status,
    statusLabel: presentRuntimeStatusLabel(node.status),
    truthSource: node.truth_source,
    currentRef: normalizeNonEmpty(node.current_ref || undefined),
    route: normalizeNonEmpty(node.route || undefined),
    summary: normalizeNonEmpty(
      node.summary ? normalizeDisplayChinese(node.summary) : undefined,
    ),
    backflowPort: normalizeNonEmpty(node.backflow_port || undefined),
    metrics: presentNodeMetrics(node.metrics || {}),
  };
}

function presentSynthesis(
  synthesis: IndustryRuntimeCycleSynthesis | null,
): ControlChainSynthesisPresentation | null {
  if (!synthesis) {
    return null;
  }
  const findingCount = synthesis.latest_findings.length;
  const conflictCount = synthesis.conflicts.length;
  const holeCount = synthesis.holes.length;
  const actionCount = synthesis.recommended_actions.length;
  return {
    findingCount,
    conflictCount,
    holeCount,
    actionCount,
    needsReplan: Boolean(synthesis.needs_replan),
    summary: [
      `发现 ${findingCount}`,
      `冲突 ${conflictCount}`,
      `缺口 ${holeCount}`,
      `动作 ${actionCount}`,
    ].join(" / "),
    controlCoreContract: [...(synthesis.control_core_contract || [])],
  };
}

export function presentControlChain(
  value: IndustryInstanceDetail | IndustryMainChainGraph | null | undefined,
): ControlChainPresentation {
  const graph = resolveChainGraph(value);
  const order = new Map<string, number>(
    CONTROL_CHAIN_NODE_ORDER.map((nodeId, index) => [nodeId, index]),
  );
  const nodes = (graph?.nodes || [])
    .filter((node) => order.has(node.node_id))
    .sort(
      (left, right) =>
        (order.get(left.node_id) ?? Number.MAX_SAFE_INTEGER) -
        (order.get(right.node_id) ?? Number.MAX_SAFE_INTEGER),
    )
    .map(presentNode);
  const synthesis = presentSynthesis(resolveSynthesis(value));
  return {
    loopState: normalizeNonEmpty(graph?.loop_state || undefined),
    loopStateLabel: presentRuntimeStatusLabel(graph?.loop_state || null),
    currentFocus: normalizeNonEmpty(
      graph?.current_focus ? normalizeDisplayChinese(graph.current_focus) : undefined,
    ),
    currentOwner: normalizeNonEmpty(
      graph?.current_owner ? normalizeDisplayChinese(graph.current_owner) : undefined,
    ),
    currentRisk: normalizeNonEmpty(graph?.current_risk || undefined),
    latestEvidenceSummary: normalizeNonEmpty(
      graph?.latest_evidence_summary
        ? normalizeDisplayChinese(graph.latest_evidence_summary)
        : undefined,
    ),
    nodes,
    synthesis,
    hasAnyState: Boolean(graph || synthesis),
  };
}
