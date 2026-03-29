import { request } from "../request";
import type { MediaAnalysisSummary, MediaSourceSpec } from "./media";

export interface IndustryPreviewPayload {
  industry: string;
  company_name?: string;
  sub_industry?: string;
  product?: string;
  business_model?: string;
  region?: string;
  target_customers?: string[];
  channels?: string[];
  goals?: string[];
  constraints?: string[];
  budget_summary?: string;
  notes?: string;
  owner_scope?: string;
  experience_mode?: "system-led" | "operator-guided";
  experience_notes?: string;
  operator_requirements?: string[];
  media_inputs?: MediaSourceSpec[];
}

export interface IndustryProfile {
  schema_version: "industry-profile-v1";
  industry: string;
  company_name?: string | null;
  sub_industry?: string | null;
  product?: string | null;
  business_model?: string | null;
  region?: string | null;
  target_customers: string[];
  channels: string[];
  goals: string[];
  constraints: string[];
  budget_summary?: string | null;
  notes?: string | null;
  experience_mode: "system-led" | "operator-guided";
  experience_notes?: string | null;
  operator_requirements: string[];
}

export interface IndustryRoleBlueprint {
  schema_version: "industry-role-blueprint-v1";
  role_id: string;
  agent_id: string;
  name: string;
  role_name: string;
  role_summary: string;
  mission: string;
  goal_kind: string;
  agent_class: "system" | "business";
  employment_mode: "career" | "temporary";
  activation_mode: "persistent" | "on-demand";
  suspendable: boolean;
  reports_to?: string | null;
  risk_level: "auto" | "guarded" | "confirm";
  environment_constraints: string[];
  allowed_capabilities: string[];
  preferred_capability_families: string[];
  evidence_expectations: string[];
}

export interface IndustryTeamBlueprint {
  schema_version: "industry-team-blueprint-v1";
  team_id: string;
  label: string;
  summary: string;
  topology?: "solo" | "lead-plus-support" | "pod" | "full-team" | null;
  agents: IndustryRoleBlueprint[];
}

export interface IndustryDraftGoal {
  goal_id: string;
  kind: string;
  owner_agent_id: string;
  title: string;
  summary: string;
  plan_steps: string[];
}

export interface IndustryDraftSchedule {
  schedule_id: string;
  owner_agent_id: string;
  title: string;
  summary: string;
  cron: string;
  timezone: string;
  dispatch_channel: string;
  dispatch_mode: "stream" | "final";
}

export interface IndustryDraftPlan {
  schema_version: "industry-draft-v1";
  team: IndustryTeamBlueprint;
  goals: IndustryDraftGoal[];
  schedules: IndustryDraftSchedule[];
  generation_summary?: string | null;
}

export interface IndustryCapabilityRecommendation {
  recommendation_id: string;
  install_kind:
    | "mcp-template"
    | "mcp-registry"
    | "builtin-runtime"
    | "hub-skill";
  template_id: string;
  install_option_key: string;
  title: string;
  description: string;
  default_client_key: string;
  capability_ids: string[];
  capability_tags: string[];
  capability_families: string[];
  suggested_role_ids: string[];
  target_agent_ids: string[];
  default_enabled: boolean;
  installed: boolean;
  selected: boolean;
  required: boolean;
  risk_level: "auto" | "guarded" | "confirm";
  capability_budget_cost: number;
  source_kind:
    | "install-template"
    | "mcp-registry"
    | "hub-search"
    | "skillhub-curated";
  source_label: string;
  source_url: string;
  version: string;
  review_required: boolean;
  review_summary: string;
  review_notes: string[];
  notes: string[];
  discovery_queries: string[];
  match_signals: string[];
  governance_path: string[];
  recommendation_group:
    | "system-baseline"
    | "execution-core"
    | "shared"
    | "role-specific";
  assignment_scope: "system" | "shared" | "agent";
  shared_reuse: boolean;
  routes: Record<string, unknown>;
}

export interface IndustryCapabilityRecommendationSection {
  section_id: string;
  section_kind: "system-baseline" | "execution-core" | "shared" | "role";
  title: string;
  summary: string;
  role_id?: string | null;
  role_name?: string | null;
  target_agent_id?: string | null;
  items: IndustryCapabilityRecommendation[];
}

export interface IndustryCapabilityRecommendationPack {
  summary: string;
  items: IndustryCapabilityRecommendation[];
  warnings: string[];
  sections: IndustryCapabilityRecommendationSection[];
}

export interface IndustryBootstrapInstallItem {
  recommendation_id?: string | null;
  install_kind:
    | "mcp-template"
    | "mcp-registry"
    | "builtin-runtime"
    | "hub-skill";
  template_id: string;
  install_option_key?: string;
  client_key?: string | null;
  bundle_url?: string | null;
  version?: string | null;
  source_kind?:
    | "install-template"
    | "mcp-registry"
    | "hub-search"
    | "skillhub-curated";
  source_label?: string | null;
  review_acknowledged?: boolean;
  enabled?: boolean;
  required?: boolean;
  capability_assignment_mode?: "replace" | "merge";
  capability_ids?: string[];
  target_agent_ids?: string[];
  target_role_ids?: string[];
}

export interface IndustryBootstrapInstallAssignmentResult {
  agent_id: string;
  capability_ids: string[];
  status: "assigned" | "failed" | "skipped";
  detail: string;
  routes: Record<string, string>;
}

export interface IndustryBootstrapInstallResult {
  recommendation_id?: string | null;
  install_kind:
    | "mcp-template"
    | "mcp-registry"
    | "builtin-runtime"
    | "hub-skill";
  template_id: string;
  install_option_key: string;
  client_key: string;
  capability_ids: string[];
  source_kind:
    | "install-template"
    | "mcp-registry"
    | "hub-search"
    | "skillhub-curated";
  source_label: string;
  source_url: string;
  version: string;
  status:
    | "installed"
    | "already-installed"
    | "updated-existing"
    | "enabled-existing"
    | "failed"
    | "skipped";
  detail: string;
  installed: boolean;
  assignment_results: IndustryBootstrapInstallAssignmentResult[];
  routes: Record<string, string>;
}

export interface IndustryBootstrapPayload {
  profile: IndustryProfile;
  draft: IndustryDraftPlan;
  install_plan?: IndustryBootstrapInstallItem[];
  owner_scope?: string;
  goal_priority?: number;
  auto_activate?: boolean;
  auto_dispatch?: boolean;
  execute?: boolean;
  media_inputs?: MediaSourceSpec[];
  media_analysis_ids?: string[];
}

export interface IndustryReadinessCheck {
  key: string;
  title: string;
  status: "ready" | "warning" | "missing";
  detail: string;
  required: boolean;
  context: Record<string, unknown>;
}

export interface IndustryRuntimeGoal {
  goal_id: string;
  kind: string;
  title: string;
  summary: string;
  status: string;
  priority: number;
  owner_scope: string | null;
  plan_steps: string[];
  owner_agent_id: string | null;
  role_id?: string | null;
  role_name?: string | null;
  agent_class?: string | null;
  route: string;
  task_count: number;
  decision_count: number;
  evidence_count: number;
}

export interface IndustryRuntimeAgent {
  agent_id: string;
  name: string;
  role_name: string;
  role_summary: string;
  agent_class?: "system" | "business";
  employment_mode?: "career" | "temporary";
  activation_mode?: "persistent" | "on-demand";
  suspendable?: boolean;
  reports_to?: string | null;
  mission?: string;
  status: string;
  runtime_status?: string;
  desired_state?: string;
  risk_level: string;
  current_goal_id?: string | null;
  current_goal?: string;
  current_task_id?: string | null;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
  environment_summary?: string;
  environment_constraints?: string[];
  evidence_expectations?: string[];
  capabilities: string[];
  updated_at?: string | null;
  route?: string | null;
}

export interface IndustryRuntimeSchedule {
  schedule_id: string;
  title: string;
  status: string;
  enabled: boolean;
  cron: string;
  timezone: string;
  dispatch_channel?: string | null;
  dispatch_mode?: "stream" | "final" | null;
  owner_agent_id?: string | null;
  industry_role_id?: string | null;
  summary?: string | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_error?: string | null;
  updated_at?: string | null;
  route: string;
}

export interface IndustryReportSnapshot {
  window: "daily" | "weekly";
  since: string;
  until: string;
  evidence_count: number;
  proposal_count: number;
  patch_count: number;
  applied_patch_count: number;
  growth_count: number;
  decision_count: number;
  recent_evidence: Array<Record<string, unknown>>;
  highlights: string[];
}

export interface IndustryExecutionSummary {
  status: string;
  current_focus_id?: string | null;
  current_focus?: string | null;
  current_owner_agent_id?: string | null;
  current_owner?: string | null;
  current_risk?: string | null;
  evidence_count: number;
  latest_evidence_summary?: string | null;
  next_step?: string | null;
  current_task_id?: string | null;
  current_task_route?: string | null;
  current_stage?: string | null;
  trigger_source?: string | null;
  trigger_actor?: string | null;
  trigger_reason?: string | null;
  blocked_reason?: string | null;
  stuck_reason?: string | null;
  updated_at?: string | null;
}

export interface IndustryExecutionCoreIdentity {
  schema_version?: string;
  role_id?: string | null;
  agent_id?: string | null;
  identity_label?: string | null;
  industry_label?: string | null;
  industry_summary?: string | null;
  role_name?: string | null;
  role_summary?: string | null;
  mission?: string | null;
  allowed_capabilities?: string[];
  thinking_axes?: string[];
  operating_mode?: string | null;
  delegation_policy?: string[];
  direct_execution_policy?: string[];
  environment_constraints?: string[];
  evidence_expectations?: string[];
  [key: string]: unknown;
}

export interface IndustryStrategyTeammateContract {
  agent_id?: string | null;
  role_id?: string | null;
  role_name?: string | null;
  role_summary?: string | null;
  mission?: string | null;
  employment_mode?: "career" | "temporary" | null;
  reports_to?: string | null;
  goal_kind?: string | null;
  risk_level?: string | null;
  capabilities?: string[];
  evidence_expectations?: string[];
  environment_constraints?: string[];
  [key: string]: unknown;
}

export interface IndustryStrategyMemory {
  strategy_id?: string | null;
  status?: string | null;
  summary?: string | null;
  north_star?: string | null;
  priority_order?: string[];
  current_focuses?: string[];
  paused_lane_ids?: string[];
  teammate_contracts?: IndustryStrategyTeammateContract[];
  lane_weights?: Record<string, unknown>;
  planning_policy?: Record<string, unknown>;
  review_rules?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface IndustryRuntimeLane {
  lane_id: string;
  lane_key: string;
  title: string;
  summary?: string | null;
  status: string;
  owner_agent_id?: string | null;
  owner_role_id?: string | null;
  priority: number;
  health_status?: string | null;
  source_ref?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
  route?: string | null;
}

export interface IndustryRuntimeBacklogItem {
  backlog_item_id: string;
  lane_id?: string | null;
  cycle_id?: string | null;
  assignment_id?: string | null;
  goal_id?: string | null;
  title: string;
  summary?: string | null;
  status: string;
  priority: number;
  source_kind: string;
  source_ref?: string | null;
  evidence_ids: string[];
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
  selected?: boolean;
  route?: string | null;
}

export interface IndustryRuntimeSynthesisFinding {
  report_id: string;
  cycle_id?: string | null;
  assignment_id?: string | null;
  goal_id?: string | null;
  task_id?: string | null;
  lane_id?: string | null;
  owner_agent_id?: string | null;
  owner_role_id?: string | null;
  headline?: string | null;
  summary?: string | null;
  status?: string | null;
  result?: string | null;
  findings: string[];
  uncertainties: string[];
  recommendation?: string | null;
  needs_followup: boolean;
  followup_reason?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface IndustryRuntimeSynthesisConflict {
  conflict_id: string;
  kind: string;
  topic_key?: string | null;
  summary?: string | null;
  report_ids: string[];
  owner_agent_ids: string[];
  [key: string]: unknown;
}

export interface IndustryRuntimeSynthesisHole {
  hole_id: string;
  kind: string;
  summary?: string | null;
  report_id?: string | null;
  report_ids?: string[];
  [key: string]: unknown;
}

export interface IndustryRuntimeSynthesisAction {
  action_id: string;
  action_type: string;
  title?: string | null;
  summary?: string | null;
  priority?: number;
  lane_id?: string | null;
  source_ref?: string | null;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface IndustryRuntimeCycleSynthesis {
  latest_findings: IndustryRuntimeSynthesisFinding[];
  conflicts: IndustryRuntimeSynthesisConflict[];
  holes: IndustryRuntimeSynthesisHole[];
  recommended_actions: IndustryRuntimeSynthesisAction[];
  needs_replan: boolean;
  control_core_contract: string[];
  [key: string]: unknown;
}

export interface IndustryRuntimeCycle {
  cycle_id: string;
  cycle_kind: string;
  title: string;
  summary?: string | null;
  status: string;
  source_ref?: string | null;
  started_at?: string | null;
  due_at?: string | null;
  completed_at?: string | null;
  focus_lane_ids: string[];
  backlog_item_ids: string[];
  goal_ids: string[];
  assignment_ids: string[];
  report_ids: string[];
  synthesis?: IndustryRuntimeCycleSynthesis | null;
  metadata: Record<string, unknown>;
  is_current?: boolean;
  route?: string | null;
}

export interface IndustryRuntimeAssignment {
  assignment_id: string;
  cycle_id?: string | null;
  lane_id?: string | null;
  backlog_item_id?: string | null;
  goal_id?: string | null;
  task_id?: string | null;
  owner_agent_id?: string | null;
  owner_role_id?: string | null;
  title: string;
  summary?: string | null;
  status: string;
  report_back_mode?: string | null;
  evidence_ids: string[];
  last_report_id?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
  selected?: boolean;
  route?: string | null;
}

export interface IndustryRuntimeAgentReport {
  report_id: string;
  cycle_id?: string | null;
  assignment_id?: string | null;
  goal_id?: string | null;
  task_id?: string | null;
  lane_id?: string | null;
  owner_agent_id?: string | null;
  owner_role_id?: string | null;
  report_kind: string;
  headline: string;
  summary?: string | null;
  status: string;
  result?: string | null;
  findings: string[];
  uncertainties: string[];
  recommendation?: string | null;
  needs_followup: boolean;
  followup_reason?: string | null;
  risk_level?: string | null;
  evidence_ids: string[];
  decision_ids: string[];
  processed: boolean;
  processed_at?: string | null;
  work_context_id?: string | null;
  context_key?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
  route?: string | null;
}

export interface IndustryStaffingAssignmentSummary {
  assignment_id?: string | null;
  goal_id?: string | null;
  backlog_item_id?: string | null;
  lane_id?: string | null;
  title?: string | null;
  summary?: string | null;
  status?: string | null;
  route?: string | null;
  updated_at?: string | null;
}

export interface IndustryStaffingReportSummary {
  report_id?: string | null;
  assignment_id?: string | null;
  goal_id?: string | null;
  headline?: string | null;
  summary?: string | null;
  status?: string | null;
  result?: string | null;
  processed?: boolean;
  route?: string | null;
  updated_at?: string | null;
}

export interface IndustryStaffingGap {
  backlog_item_id?: string | null;
  kind: string;
  reason?: string | null;
  requested_surfaces: string[];
  target_role_id?: string | null;
  target_role_name?: string | null;
  target_agent_id?: string | null;
  decision_request_id?: string | null;
  proposal_status?: string | null;
  status?: string | null;
  requires_confirmation: boolean;
  title?: string | null;
  summary?: string | null;
  route?: string | null;
  updated_at?: string | null;
}

export interface IndustryTemporarySeat {
  role_id: string;
  role_name: string;
  agent_id: string;
  status: string;
  employment_mode?: "career" | "temporary";
  activation_mode?: "persistent" | "on-demand";
  reports_to?: string | null;
  route?: string | null;
  current_assignment?: IndustryStaffingAssignmentSummary | null;
  latest_report?: IndustryStaffingReportSummary | null;
  origin?: IndustryStaffingGap | null;
  auto_retire_hint?: string | null;
}

export interface IndustryResearcherState {
  role_id: string;
  role_name: string;
  agent_id: string;
  status: string;
  route?: string | null;
  current_assignment?: IndustryStaffingAssignmentSummary | null;
  latest_report?: IndustryStaffingReportSummary | null;
  pending_signal_count?: number;
  waiting_for_main_brain?: boolean;
}

export interface IndustryStaffingState {
  active_gap?: IndustryStaffingGap | null;
  pending_proposals: IndustryStaffingGap[];
  temporary_seats: IndustryTemporarySeat[];
  researcher?: IndustryResearcherState | null;
}

export interface IndustryMainChainNode {
  node_id: string;
  label: string;
  status: string;
  truth_source: string;
  current_ref?: string | null;
  route?: string | null;
  summary?: string | null;
  backflow_port?: string | null;
  metrics: Record<string, unknown>;
}

export interface IndustryMainChainGraph {
  schema_version: "industry-main-chain-v1";
  loop_state: string;
  current_focus_id?: string | null;
  current_focus?: string | null;
  current_owner_agent_id?: string | null;
  current_owner?: string | null;
  current_risk?: string | null;
  latest_evidence_summary?: string | null;
  nodes: IndustryMainChainNode[];
}

export interface IndustryDetailFocusSelection {
  selection_kind: "assignment" | "backlog";
  assignment_id?: string | null;
  backlog_item_id?: string | null;
  title?: string | null;
  summary?: string | null;
  status?: string | null;
  route?: string | null;
}

export interface IndustryInstanceSummary {
  instance_id: string;
  bootstrap_kind: "industry-v1";
  label: string;
  summary: string;
  owner_scope: string;
  profile: IndustryProfile;
  team: IndustryTeamBlueprint;
  execution_core_identity?: IndustryExecutionCoreIdentity | null;
  strategy_memory?: IndustryStrategyMemory | null;
  status: string;
  autonomy_status?: string | null;
  lifecycle_status?: string | null;
  updated_at: string | null;
  stats: Record<string, number>;
  routes: Record<string, unknown>;
}

export interface IndustryInstanceDetail extends IndustryInstanceSummary {
  goals: IndustryRuntimeGoal[];
  agents: IndustryRuntimeAgent[];
  schedules: IndustryRuntimeSchedule[];
  lanes: IndustryRuntimeLane[];
  backlog: IndustryRuntimeBacklogItem[];
  staffing: IndustryStaffingState;
  current_cycle?: IndustryRuntimeCycle | null;
  cycles: IndustryRuntimeCycle[];
  assignments: IndustryRuntimeAssignment[];
  agent_reports: IndustryRuntimeAgentReport[];
  tasks: Array<Record<string, unknown>>;
  decisions: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  patches: Array<Record<string, unknown>>;
  growth: Array<Record<string, unknown>>;
  proposals: Array<Record<string, unknown>>;
  execution?: IndustryExecutionSummary | null;
  main_chain?: IndustryMainChainGraph | null;
  focus_selection?: IndustryDetailFocusSelection | null;
  reports: {
    daily: IndustryReportSnapshot;
    weekly: IndustryReportSnapshot;
  };
  media_analyses: MediaAnalysisSummary[];
}

export interface IndustryBootstrapResponse {
  profile: IndustryProfile;
  team: IndustryTeamBlueprint;
  recommendation_pack: IndustryCapabilityRecommendationPack;
  install_results: IndustryBootstrapInstallResult[];
  goals: Array<Record<string, unknown>>;
  schedules: Array<Record<string, unknown>>;
  readiness_checks: IndustryReadinessCheck[];
  media_analyses: MediaAnalysisSummary[];
  routes: Record<string, unknown>;
}

export interface IndustryPreviewResponse {
  profile: IndustryProfile;
  draft: IndustryDraftPlan;
  recommendation_pack: IndustryCapabilityRecommendationPack;
  readiness_checks: IndustryReadinessCheck[];
  can_activate: boolean;
  media_analyses: MediaAnalysisSummary[];
  media_warnings: string[];
}

export interface IndustryDeleteResponse {
  deleted: boolean;
  instance_id: string;
  previous_status: string;
  deleted_counts: Record<string, number>;
}

export const industryApi = {
  previewIndustry: (payload: IndustryPreviewPayload) =>
    request<IndustryPreviewResponse>("/industry/v1/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  bootstrapIndustry: (payload: IndustryBootstrapPayload) =>
    request<IndustryBootstrapResponse>("/industry/v1/bootstrap", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateIndustryTeam: (instanceId: string, payload: IndustryBootstrapPayload) =>
    request<IndustryBootstrapResponse>(
      `/industry/v1/instances/${encodeURIComponent(instanceId)}/team`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),

  listIndustryInstances: (
    limitOrOptions: number | { limit?: number; status?: string } = 20,
  ) => {
    const options =
      typeof limitOrOptions === "number"
        ? { limit: limitOrOptions }
        : limitOrOptions;
    const params = new URLSearchParams();
    params.set("limit", String(options.limit ?? 20));
    if (options.status) {
      params.set("status", options.status);
    }
    return request<IndustryInstanceSummary[]>(
      `/industry/v1/instances?${params.toString()}`,
    );
  },

  getIndustryInstance: (instanceId: string) =>
    request<IndustryInstanceDetail>(
      `/industry/v1/instances/${encodeURIComponent(instanceId)}`,
    ),

  getRuntimeIndustryDetail: (
    instanceId: string,
    options?: {
      assignmentId?: string | null;
      backlogItemId?: string | null;
    },
  ) => {
    const params = new URLSearchParams();
    if (options?.assignmentId) {
      params.set("assignment_id", options.assignmentId);
    }
    if (options?.backlogItemId) {
      params.set("backlog_item_id", options.backlogItemId);
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return request<IndustryInstanceDetail>(
      `/runtime-center/industry/${encodeURIComponent(instanceId)}${suffix}`,
    );
  },

  deleteIndustryInstance: (instanceId: string) =>
    request<IndustryDeleteResponse>(
      `/industry/v1/instances/${encodeURIComponent(instanceId)}`,
      {
        method: "DELETE",
      },
    ),
};


