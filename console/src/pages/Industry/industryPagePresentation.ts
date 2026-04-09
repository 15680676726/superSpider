import type {
  IndustryCapabilityRecommendationSection,
  IndustryDetailFocusSelection,
  IndustryInstanceDetail,
  IndustryRuntimeAgentReport,
  IndustryRuntimeAssignment,
  IndustryRuntimeBacklogItem,
} from "../../api/modules/industry";
import { normalizeDisplayChinese } from "../../text";
import { normalizeSpiderMeshBrand } from "../../utils/brand";

export function presentRecommendationSubsectionTitle(
  section: IndustryCapabilityRecommendationSection,
): string {
  if (section.section_kind === "execution-core") {
    return "\u7f16\u6392\u80fd\u529b";
  }
  if (section.section_kind === "system-baseline") {
    return "\u57fa\u7840\u8fd0\u884c";
  }
  if (section.section_kind === "shared") {
    return "\u591a\u4eba\u5171\u7528";
  }
  return normalizeSpiderMeshBrand(section.role_name || section.title) || section.title;
}

export function isFocusedAssignment(
  assignment: IndustryRuntimeAssignment,
  selection:
    | { selection_kind: "assignment" | "backlog"; assignment_id?: string | null }
    | null
    | undefined,
): boolean {
  return Boolean(
    assignment.selected ||
      (selection?.selection_kind === "assignment" &&
        selection.assignment_id === assignment.assignment_id),
  );
}

export function isFocusedBacklog(
  backlogItem: IndustryRuntimeBacklogItem,
  selection:
    | { selection_kind: "assignment" | "backlog"; backlog_item_id?: string | null }
    | null
    | undefined,
): boolean {
  return Boolean(
    backlogItem.selected ||
      (selection?.selection_kind === "backlog" &&
        selection.backlog_item_id === backlogItem.backlog_item_id),
  );
}

export function resolveReportWorkContextId(
  report: IndustryRuntimeAgentReport,
): string | null {
  const workContextId = report.work_context_id?.trim();
  if (workContextId) {
    return workContextId;
  }
  const metadata = report.metadata;
  if (
    metadata &&
    typeof metadata === "object" &&
    typeof metadata.work_context_id === "string" &&
    metadata.work_context_id.trim()
  ) {
    return metadata.work_context_id.trim();
  }
  return null;
}

export function runtimeSurfaceCardStyle(selected: boolean) {
  return {
    borderRadius: 12,
    border: `1px solid ${
      selected ? "var(--ant-primary-color, #1677ff)" : "var(--baize-border-color)"
    }`,
    background: selected ? "rgba(22,119,255,0.08)" : "rgba(255,255,255,0.02)",
    boxShadow: selected ? "0 0 0 1px rgba(22,119,255,0.12)" : "none",
  } as const;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function stringValue(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function summarizeHostTwin(value: unknown): string | null {
  if (!isRecord(value)) {
    return null;
  }
  const coordination = isRecord(value.coordination) ? value.coordination : value;
  return (
    stringValue(coordination.recommended_scheduler_action) ||
    stringValue(coordination.selected_seat_ref) ||
    stringValue(coordination.seat_selection_policy) ||
    stringValue(coordination.active_app_family_count) ||
    stringValue(coordination.contention_severity) ||
    stringValue(coordination.blocked_surface_count) ||
    null
  );
}

export function resolveExecutionEnvironmentVisibility(
  detail: IndustryInstanceDetail,
): {
  environment: string | null;
  hostTwinSummary: string | null;
  constraints: string[];
} {
  const anyDetail = detail as unknown as Record<string, unknown>;
  const identity =
    (detail.execution_core_identity || null) as Record<string, unknown> | null;

  const directEnv =
    anyDetail.execution_environment ||
    anyDetail.executionEnvironment ||
    anyDetail.environment ||
    null;
  const envRecord = isRecord(directEnv) ? directEnv : null;

  const hostTwin =
    (envRecord && isRecord(envRecord.host_twin) ? envRecord.host_twin : null) ||
    (envRecord && isRecord(envRecord.hostTwin) ? envRecord.hostTwin : null) ||
    (identity && isRecord(identity.host_twin) ? identity.host_twin : null) ||
    (identity && isRecord(identity.hostTwin) ? identity.hostTwin : null) ||
    (isRecord(anyDetail.host_twin) ? anyDetail.host_twin : null) ||
    (isRecord(anyDetail.hostTwin) ? anyDetail.hostTwin : null) ||
    null;

  const constraintsFromIdentity = Array.isArray(
    detail.execution_core_identity?.environment_constraints,
  )
    ? detail.execution_core_identity!.environment_constraints.filter(
        (item): item is string =>
          typeof item === "string" && item.trim().length > 0,
      )
    : [];
  const constraintsFromEnv =
    envRecord && Array.isArray(envRecord.environment_constraints)
      ? envRecord.environment_constraints.filter(
          (item): item is string =>
            typeof item === "string" && item.trim().length > 0,
        )
      : [];

  return {
    environment:
      stringValue(envRecord?.environment_summary) ||
      stringValue(envRecord?.environment) ||
      stringValue(identity?.environment_summary) ||
      stringValue(identity?.environment) ||
      null,
    hostTwinSummary:
      stringValue(envRecord?.host_twin_summary) ||
      stringValue(identity?.host_twin_summary) ||
      summarizeHostTwin(hostTwin) ||
      null,
    constraints: Array.from(
      new Set([...constraintsFromIdentity, ...constraintsFromEnv]),
    ),
  };
}

export function resolveEvidenceLabel(record: Record<string, unknown>): string {
  return (
    stringValue(record.summary) ||
    stringValue(record.title) ||
    stringValue(record.headline) ||
    stringValue(record.evidence_id) ||
    stringValue(record.id) ||
    "证据记录"
  );
}

export function buildIndustryRuntimeFocusSummary(options: {
  focusSelection?: IndustryDetailFocusSelection | null;
  focusedAssignment?: IndustryRuntimeAssignment | null;
  focusedBacklog?: IndustryRuntimeBacklogItem | null;
  followupReport?: IndustryRuntimeAgentReport | null;
  executionCurrentFocus?: string | null;
  mainChainCurrentFocus?: string | null;
}): string {
  const {
    executionCurrentFocus,
    focusSelection,
    focusedAssignment,
    focusedBacklog,
    followupReport,
    mainChainCurrentFocus,
  } = options;

  const summary =
    focusSelection?.summary ||
    focusSelection?.title ||
    (focusedAssignment
      ? `派工：${focusedAssignment.title || focusedAssignment.assignment_id}`
      : null) ||
    (focusedBacklog
      ? `待办：${focusedBacklog.title || focusedBacklog.backlog_item_id}`
      : null) ||
    (followupReport
      ? `跟进：${followupReport.headline || followupReport.report_id}`
      : null) ||
    executionCurrentFocus ||
    mainChainCurrentFocus ||
    "当前还没有聚焦子视图。";

  return normalizeDisplayChinese(summary);
}
