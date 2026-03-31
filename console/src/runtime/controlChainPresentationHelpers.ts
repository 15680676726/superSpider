import type {
  IndustryInstanceDetail,
  IndustryMainChainGraph,
  IndustryRuntimeCycleSynthesis,
} from "../api/modules/industry";
import { normalizeDisplayChinese } from "../text";

export type ControlChainInput =
  | IndustryInstanceDetail
  | IndustryMainChainGraph
  | null
  | undefined;

export function normalizeNonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

export function normalizeDisplayText(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return normalizeNonEmpty(normalizeDisplayChinese(value));
}

export function humanizeToken(value: string): string {
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

export function resolveChainGraph(value: ControlChainInput): IndustryMainChainGraph | null {
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

export function resolveSynthesis(
  value: ControlChainInput,
): IndustryRuntimeCycleSynthesis | null {
  if (isIndustryDetail(value)) {
    return value.current_cycle?.synthesis || null;
  }
  return null;
}

export function presentNodeLabel(
  nodeId: string,
  fallback: string | null | undefined,
  controlChainLabels: Record<string, string>,
): string {
  return (
    controlChainLabels[nodeId] ||
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

export function presentNodeMetrics(
  metrics: Record<string, unknown> | null | undefined,
): Array<{ key: string; label: string; value: string }> {
  return Object.entries(metrics || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => ({
      key,
      label: humanizeToken(key),
      value: presentMetricValue(value),
    }));
}
