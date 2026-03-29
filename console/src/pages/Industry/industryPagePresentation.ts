import type {
  IndustryCapabilityRecommendationSection,
  IndustryRuntimeAgentReport,
  IndustryRuntimeAssignment,
  IndustryRuntimeBacklogItem,
} from "../../api/modules/industry";
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
