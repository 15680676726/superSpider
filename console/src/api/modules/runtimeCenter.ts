import { request } from "../request";
import type {
  PredictionCaseRecord,
  PredictionRecommendationView,
} from "./predictions";
import type {
  GovernanceBatchResult,
  GovernanceStatus,
  RuntimeHeartbeatConfig,
  RuntimeHeartbeatDetail,
  RuntimeHeartbeatMutationResult,
  RuntimeScheduleConfig,
  RuntimeScheduleDetail,
  RuntimeScheduleMutationResult,
  RuntimeScheduleSummary,
  StartupRecoverySummary,
} from "../types";

export interface RuntimeCapabilityOptimizationSummary {
  total_items: number;
  actionable_count: number;
  history_count: number;
  case_count: number;
  missing_capability_count: number;
  underperforming_capability_count: number;
  trial_count: number;
  rollout_count: number;
  retire_count: number;
  waiting_confirm_count: number;
  manual_only_count: number;
  executed_count: number;
}

export interface RuntimeCapabilityOptimizationItem {
  case: PredictionCaseRecord;
  recommendation: PredictionRecommendationView;
  status_bucket: "actionable" | "history";
  routes: Record<string, string>;
}

export interface RuntimeCapabilityOptimizationOverview {
  generated_at: string;
  summary: RuntimeCapabilityOptimizationSummary;
  actionable: RuntimeCapabilityOptimizationItem[];
  history: RuntimeCapabilityOptimizationItem[];
  routes: Record<string, string>;
}

export interface RuntimeWorkContextSummary {
  id: string;
  title?: string | null;
  context_type?: string | null;
  status?: string | null;
  context_key?: string | null;
}

export interface RuntimeTaskReview {
  headline: string;
  objective: string;
  status: string;
  phase: string;
  current_stage?: string | null;
  recent_failures?: string[];
  effective_actions?: string[];
  avoid_repeats?: string[];
  feedback_evidence_refs?: string[];
  owner_agent_id?: string | null;
  owner_agent_name?: string | null;
  latest_result_summary?: string | null;
  latest_evidence_summary?: string | null;
  pending_decision_count: number;
  evidence_count: number;
  child_task_count: number;
  child_terminal_count: number;
  child_completion_rate: number;
  summary_lines: string[];
  next_actions: string[];
  risks: string[];
  task_route?: string | null;
  review_route?: string | null;
}

export interface RuntimeTaskChildSummary {
  id: string;
  title: string;
  status: string;
  owner_agent_id?: string | null;
  owner_agent_name?: string | null;
  work_context_id?: string | null;
  context_key?: string | null;
  work_context?: RuntimeWorkContextSummary | null;
  summary?: string | null;
  updated_at?: string | null;
  route: string;
}

export interface RuntimeTaskDetail {
  task: {
    id: string;
    title: string;
    summary?: string | null;
    task_type?: string | null;
    status?: string | null;
    owner_agent_id?: string | null;
    parent_task_id?: string | null;
    goal_id?: string | null;
  };
  runtime?: {
    runtime_status?: string | null;
    current_phase?: string | null;
    risk_level?: string | null;
    active_environment_id?: string | null;
    last_result_summary?: string | null;
    last_error_summary?: string | null;
    last_owner_agent_id?: string | null;
  } | null;
  goal?: {
    id?: string | null;
    title?: string | null;
  } | null;
  child_tasks: RuntimeTaskChildSummary[];
  agents: Array<{
    agent_id: string;
    name?: string | null;
    role_name?: string | null;
    status?: string | null;
    route?: string | null;
  }>;
  work_context?: RuntimeWorkContextSummary | null;
  delegation?: {
    parent_task_id?: string | null;
    is_child_task?: boolean;
    is_parent_task?: boolean;
    child_task_status_counts?: Record<string, number>;
    child_terminal_count?: number;
    child_completion_rate?: number;
    child_results?: RuntimeTaskChildSummary[];
  } | null;
  review?: RuntimeTaskReview | null;
  stats?: Record<string, number>;
  route: string;
}

export interface RuntimeTaskReviewPayload {
  task?: RuntimeTaskDetail["task"];
  runtime?: RuntimeTaskDetail["runtime"];
  review: RuntimeTaskReview;
  route: string;
}

export interface RuntimeHumanAssistTaskSummary {
  id: string;
  industry_instance_id?: string | null;
  assignment_id?: string | null;
  task_id?: string | null;
  chat_thread_id: string;
  title: string;
  summary?: string | null;
  task_type?: string | null;
  reason_code?: string | null;
  reason_summary?: string | null;
  required_action?: string | null;
  submission_mode?: string | null;
  acceptance_mode?: string | null;
  acceptance_spec?: Record<string, unknown>;
  resume_checkpoint_ref?: string | null;
  status: string;
  reward_preview?: Record<string, unknown>;
  reward_result?: Record<string, unknown>;
  block_evidence_refs?: string[];
  submission_evidence_refs?: string[];
  verification_evidence_refs?: string[];
  submission_text?: string | null;
  submission_payload?: Record<string, unknown>;
  verification_payload?: Record<string, unknown>;
  issued_at?: string | null;
  submitted_at?: string | null;
  verified_at?: string | null;
  closed_at?: string | null;
  expires_at?: string | null;
  route: string;
  tasks_route?: string | null;
  current_route?: string | null;
}

export interface RuntimeHumanAssistTaskDetail {
  task: RuntimeHumanAssistTaskSummary;
  routes: {
    self: string;
    list: string;
    current: string;
  };
}

export interface RuntimeCenterSurfaceInfo {
  version: "runtime-center-v1";
  mode: "operator-surface";
  status: "state-service" | "degraded" | "unavailable";
  read_only: boolean;
  source: string;
  note: string;
  services?: string[];
}

export interface RuntimeMainBrainBuddySummary {
  buddy_name: string;
  lifecycle_state: string;
  presence_state: string;
  mood_state: string;
  evolution_stage: string;
  growth_level: number;
  intimacy: number;
  affinity: number;
  current_goal_summary: string;
  current_task_summary: string;
  why_now_summary: string;
  single_next_action_summary: string;
  companion_strategy_summary: string;
}

export interface RuntimeMainBrainRecord {
  route?: string | null;
  title?: string | null;
  label?: string | null;
  name?: string | null;
  summary?: string | null;
  detail?: string | null;
  status?: string | null;
  count?: number | null;
  value?: string | number | null;
  route_title?: string | null;
  tone?: "default" | "success" | "warning" | "danger";
  [key: string]: unknown;
}

export interface RuntimeMainBrainSignal extends RuntimeMainBrainRecord {
  key: string;
}

export interface RuntimeMainBrainShell {
  verify_reminder?: string | null;
  resume_key?: string | null;
  fork_key?: string | null;
}

export interface RuntimeMainBrainPlanningConstraints extends RuntimeMainBrainRecord {
  planning_policy?: string[];
  strategic_uncertainties?: RuntimeMainBrainRecord[];
  lane_budgets?: RuntimeMainBrainRecord[];
}

export interface RuntimeMainBrainCycleDecision extends RuntimeMainBrainRecord {
  selected_backlog_item_ids?: string[];
  selected_assignment_ids?: string[];
  planning_shell?: RuntimeMainBrainShell | null;
}

export interface RuntimeMainBrainAssignmentPlan extends RuntimeMainBrainRecord {
  checkpoints?: RuntimeMainBrainRecord[];
  acceptance_criteria?: string[];
  planning_shell?: RuntimeMainBrainShell | null;
}

export interface RuntimeMainBrainUncertaintyRegister {
  status?: string | null;
  detail?: string | null;
  note?: string | null;
  route?: string | null;
  summary?: {
    uncertainty_count?: number | null;
    lane_budget_count?: number | null;
    trigger_rule_count?: number | null;
  } | null;
  items?: RuntimeMainBrainRecord[];
  [key: string]: unknown;
}

export interface RuntimeMainBrainReplan extends RuntimeMainBrainRecord {
  decision_kind?: string | null;
  strategy_trigger_rules?: RuntimeMainBrainRecord[];
  uncertainty_register?: RuntimeMainBrainUncertaintyRegister | null;
  planning_shell?: RuntimeMainBrainShell | null;
}

export interface RuntimeMainBrainPlanning extends RuntimeMainBrainRecord {
  strategy_constraints?: RuntimeMainBrainPlanningConstraints | null;
  latest_cycle_decision?: RuntimeMainBrainCycleDecision | null;
  focused_assignment_plan?: RuntimeMainBrainAssignmentPlan | null;
  replan?: RuntimeMainBrainReplan | null;
}

export interface RuntimeMainBrainReportCognition extends RuntimeMainBrainRecord {
  needs_replan?: boolean;
  replan_reasons?: string[];
  judgment?: RuntimeMainBrainRecord | null;
  next_action?: RuntimeMainBrainRecord | null;
  latest_findings?: RuntimeMainBrainRecord[];
  conflicts?: RuntimeMainBrainRecord[];
  holes?: RuntimeMainBrainRecord[];
  followup_backlog?: RuntimeMainBrainRecord[];
  unconsumed_reports?: RuntimeMainBrainRecord[];
  needs_followup_reports?: RuntimeMainBrainRecord[];
}

export interface RuntimeMainBrainHostTwinSummary extends RuntimeMainBrainRecord {
  selected_seat_ref?: string | null;
  recommended_scheduler_action?: string | null;
  continuity_state?: string | null;
  active_app_family_keys?: string[];
  blocked_surface_count?: number | null;
  legal_recovery_mode?: string | null;
}

export interface RuntimeMainBrainHandoff extends RuntimeMainBrainRecord {
  active?: boolean | null;
}

export interface RuntimeMainBrainStaffing extends RuntimeMainBrainRecord {
  pending_confirmation_count?: number | null;
}

export interface RuntimeMainBrainHumanAssist extends RuntimeMainBrainRecord {
  blocked_count?: number | null;
}

export interface RuntimeMainBrainEnvironment extends RuntimeMainBrainRecord {
  host_twin_summary?: RuntimeMainBrainHostTwinSummary | null;
  handoff?: RuntimeMainBrainHandoff | null;
  staffing?: RuntimeMainBrainStaffing | null;
  human_assist?: RuntimeMainBrainHumanAssist | null;
}

export interface RuntimeMainBrainEntropyState extends RuntimeMainBrainRecord {
  sidecar_memory_status?: string | null;
  carry_forward_contract?: string | null;
}

export interface RuntimeMainBrainCompactionState extends RuntimeMainBrainRecord {
  mode?: string | null;
  spill_count?: number | null;
  replacement_count?: number | null;
}

export interface RuntimeMainBrainToolResultBudget extends RuntimeMainBrainRecord {
  message_budget?: number | null;
  used_budget?: number | null;
  remaining_budget?: number | null;
  remaining?: number | null;
  budget_remaining?: number | null;
}

export interface RuntimeMainBrainToolUseSummary extends RuntimeMainBrainRecord {
  artifact_refs?: string[];
}

export interface RuntimeMainBrainQueryRuntimeEntropy extends RuntimeMainBrainRecord {
  runtime_entropy?: RuntimeMainBrainEntropyState | null;
  sidecar_memory?: RuntimeMainBrainRecord | null;
  compaction_state?: RuntimeMainBrainCompactionState | null;
  tool_result_budget?: RuntimeMainBrainToolResultBudget | null;
  tool_use_summary?: RuntimeMainBrainToolUseSummary | null;
}

export interface RuntimeMainBrainGovernance extends RuntimeMainBrainRecord {
  pending_decisions?: number | null;
  pending_patches?: number | null;
  paused_schedule_count?: number | null;
  handoff_active?: boolean | null;
  query_runtime_entropy?: RuntimeMainBrainQueryRuntimeEntropy | null;
}

export interface RuntimeMainBrainHeartbeat extends RuntimeMainBrainRecord {
  enabled?: boolean | null;
  every?: string | null;
}

export interface RuntimeMainBrainAutomation extends RuntimeMainBrainRecord {
  schedule_count?: number | null;
  active_schedule_count?: number | null;
  heartbeat?: RuntimeMainBrainHeartbeat | null;
}

export interface RuntimeMainBrainSection {
  count: number;
  summary?: string | null;
  route?: string | null;
  entries: RuntimeMainBrainRecord[];
  meta: RuntimeMainBrainRecord;
  [key: string]: unknown;
}

export interface RuntimeMainBrainMeta {
  control_chain: RuntimeMainBrainSignal[];
  agent_reports?: RuntimeMainBrainRecord | null;
}

export interface RuntimeCenterSurfaceCard {
  key: string;
  title: string;
  source: string;
  status: "state-service" | "degraded" | "unavailable";
  count: number;
  summary: string;
  entries: Array<{
    id: string;
    title: string;
    kind: string;
    status: string;
    owner?: string | null;
    summary?: string | null;
    updated_at?: string | null;
    route?: string | null;
    actions: Record<string, string>;
    meta: Record<string, unknown>;
  }>;
  meta: Record<string, unknown>;
}

export interface RuntimeMainBrainResponse {
  generated_at: string;
  surface: RuntimeCenterSurfaceInfo;
  strategy: RuntimeMainBrainRecord;
  carrier: RuntimeMainBrainRecord;
  lanes: RuntimeMainBrainRecord[];
  cycles: RuntimeMainBrainRecord[];
  backlog: RuntimeMainBrainRecord[];
  current_cycle: RuntimeMainBrainRecord | null;
  main_brain_planning: RuntimeMainBrainPlanning;
  assignments: RuntimeMainBrainRecord[];
  reports: RuntimeMainBrainRecord[];
  report_cognition: RuntimeMainBrainReportCognition;
  environment: RuntimeMainBrainEnvironment;
  governance: RuntimeMainBrainGovernance;
  recovery: RuntimeMainBrainRecord;
  automation: RuntimeMainBrainAutomation;
  buddy_summary?: RuntimeMainBrainBuddySummary | null;
  evidence: RuntimeMainBrainSection;
  decisions: RuntimeMainBrainSection;
  patches: RuntimeMainBrainSection;
  signals: Record<string, RuntimeMainBrainSignal>;
  meta: RuntimeMainBrainMeta;
}

export interface RuntimeCenterSurfaceResponse {
  generated_at: string;
  surface: RuntimeCenterSurfaceInfo;
  cards: RuntimeCenterSurfaceCard[];
  main_brain: RuntimeMainBrainResponse | null;
}

export const runtimeCenterApi = {
  getRuntimeTaskDetail: (taskId: string) =>
    request<RuntimeTaskDetail>(
      `/runtime-center/tasks/${encodeURIComponent(taskId)}`,
    ),

  getRuntimeTaskReview: (taskId: string) =>
    request<RuntimeTaskReviewPayload>(
      `/runtime-center/tasks/${encodeURIComponent(taskId)}/review`,
    ),

  listRuntimeHumanAssistTasks: (params?: {
    chat_thread_id?: string;
    industry_instance_id?: string;
    assignment_id?: string;
    task_id?: string;
    status?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.chat_thread_id) {
      search.set("chat_thread_id", params.chat_thread_id);
    }
    if (params?.industry_instance_id) {
      search.set("industry_instance_id", params.industry_instance_id);
    }
    if (params?.assignment_id) {
      search.set("assignment_id", params.assignment_id);
    }
    if (params?.task_id) {
      search.set("task_id", params.task_id);
    }
    if (params?.status) {
      search.set("status", params.status);
    }
    if (typeof params?.limit === "number") {
      search.set("limit", String(params.limit));
    }
    const suffix = search.toString();
    return request<RuntimeHumanAssistTaskSummary[]>(
      `/runtime-center/human-assist-tasks${suffix ? `?${suffix}` : ""}`,
    );
  },

  getCurrentRuntimeHumanAssistTask: (chatThreadId: string) =>
    request<RuntimeHumanAssistTaskSummary>(
      `/runtime-center/human-assist-tasks/current?chat_thread_id=${encodeURIComponent(chatThreadId)}`,
    ),

  getRuntimeHumanAssistTaskDetail: (taskId: string) =>
    request<RuntimeHumanAssistTaskDetail>(
      `/runtime-center/human-assist-tasks/${encodeURIComponent(taskId)}`,
    ),

  getRuntimeHeartbeat: () =>
    request<RuntimeHeartbeatDetail>("/runtime-center/heartbeat"),

  updateRuntimeHeartbeat: (body: RuntimeHeartbeatConfig) =>
    request<RuntimeHeartbeatMutationResult>("/runtime-center/heartbeat", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  runRuntimeHeartbeat: () =>
    request<RuntimeHeartbeatMutationResult>("/runtime-center/heartbeat/run", {
      method: "POST",
    }),

  listRuntimeSchedules: () =>
    request<RuntimeScheduleSummary[]>("/runtime-center/schedules"),

  getRuntimeSchedule: (scheduleId: string) =>
    request<RuntimeScheduleDetail>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}`,
    ),

  createRuntimeSchedule: (spec: RuntimeScheduleConfig) =>
    request<RuntimeScheduleMutationResult>("/runtime-center/schedules", {
      method: "POST",
      body: JSON.stringify(spec),
    }),

  updateRuntimeSchedule: (scheduleId: string, spec: RuntimeScheduleConfig) =>
    request<RuntimeScheduleMutationResult>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}`,
      {
        method: "PUT",
        body: JSON.stringify(spec),
      },
    ),

  deleteRuntimeSchedule: (scheduleId: string) =>
    request<RuntimeScheduleMutationResult>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}`,
      {
        method: "DELETE",
      },
    ),

  runRuntimeSchedule: (scheduleId: string) =>
    request<RuntimeScheduleMutationResult>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}/run`,
      {
        method: "POST",
      },
    ),

  pauseRuntimeSchedule: (scheduleId: string) =>
    request<RuntimeScheduleMutationResult>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}/pause`,
      {
        method: "POST",
      },
    ),

  resumeRuntimeSchedule: (scheduleId: string) =>
    request<RuntimeScheduleMutationResult>(
      `/runtime-center/schedules/${encodeURIComponent(scheduleId)}/resume`,
      {
        method: "POST",
      },
    ),

  getGovernanceStatus: () =>
    request<GovernanceStatus>("/runtime-center/governance/status"),

  getRuntimeCapabilityOptimizations: (params?: {
    industry_instance_id?: string;
    owner_scope?: string;
    limit?: number;
    history_limit?: number;
    window_days?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.industry_instance_id) {
      search.set("industry_instance_id", params.industry_instance_id);
    }
    if (params?.owner_scope) {
      search.set("owner_scope", params.owner_scope);
    }
    if (typeof params?.limit === "number") {
      search.set("limit", String(params.limit));
    }
    if (typeof params?.history_limit === "number") {
      search.set("history_limit", String(params.history_limit));
    }
    if (typeof params?.window_days === "number") {
      search.set("window_days", String(params.window_days));
    }
    const suffix = search.toString();
    return request<RuntimeCapabilityOptimizationOverview>(
      `/runtime-center/governance/capability-optimizations${suffix ? `?${suffix}` : ""}`,
    );
  },

  emergencyStopRuntime: (body: { actor: string; reason: string }) =>
    request<GovernanceStatus>("/runtime-center/governance/emergency-stop", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  resumeGovernedRuntime: (body: { actor: string; reason?: string }) =>
    request<GovernanceStatus>("/runtime-center/governance/resume", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  approveRuntimeDecisions: (body: {
    decision_ids: string[];
    actor: string;
    resolution?: string;
    execute?: boolean;
    control_thread_id?: string;
    session_id?: string;
    user_id?: string;
    agent_id?: string;
    work_context_id?: string;
  }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/decisions/approve",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  rejectRuntimeDecisions: (body: {
    decision_ids: string[];
    actor: string;
    resolution?: string;
    execute?: boolean;
    control_thread_id?: string;
    session_id?: string;
    user_id?: string;
    agent_id?: string;
    work_context_id?: string;
  }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/decisions/reject",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  approveRuntimePatches: (body: { patch_ids: string[]; actor: string }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/patches/approve",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  rejectRuntimePatches: (body: { patch_ids: string[]; actor: string }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/patches/reject",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  applyRuntimePatches: (body: { patch_ids: string[]; actor: string }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/patches/apply",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  rollbackRuntimePatches: (body: { patch_ids: string[]; actor: string }) =>
    request<GovernanceBatchResult>(
      "/runtime-center/governance/patches/rollback",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  getLatestRecoveryReport: () =>
    request<StartupRecoverySummary>("/runtime-center/recovery/latest"),

  pauseActorRuntime: (
    agentId: string,
    body: { actor?: string; reason?: string | null } = {},
  ) =>
    request<Record<string, unknown>>(
      `/runtime-center/actors/${encodeURIComponent(agentId)}/pause`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  resumeActorRuntime: (
    agentId: string,
    body: { actor?: string } = {},
  ) =>
    request<Record<string, unknown>>(
      `/runtime-center/actors/${encodeURIComponent(agentId)}/resume`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  retryActorMailboxRuntime: (
    agentId: string,
    mailboxId: string,
    body: { actor?: string } = {},
  ) =>
    request<Record<string, unknown>>(
      `/runtime-center/actors/${encodeURIComponent(agentId)}/retry/${encodeURIComponent(mailboxId)}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  cancelActorRuntime: (
    agentId: string,
    body: { actor?: string; task_id?: string | null } = {},
  ) =>
    request<Record<string, unknown>>(
      `/runtime-center/actors/${encodeURIComponent(agentId)}/cancel`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
};
