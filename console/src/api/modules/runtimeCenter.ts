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

export interface RuntimeMainBrainSection {
  count: number;
  summary?: string | null;
  route?: string | null;
  entries: Record<string, unknown>[];
  meta: Record<string, unknown>;
}

export interface RuntimeMainBrainResponse {
  generated_at: string;
  surface: RuntimeCenterSurfaceInfo;
  strategy: Record<string, unknown>;
  carrier: Record<string, unknown>;
  lanes: Record<string, unknown>[];
  cycles: Record<string, unknown>[];
  backlog: Record<string, unknown>[];
  current_cycle: Record<string, unknown> | null;
  assignments: Record<string, unknown>[];
  reports: Record<string, unknown>[];
  report_cognition: Record<string, unknown>;
  environment: Record<string, unknown>;
  governance: Record<string, unknown>;
  recovery: Record<string, unknown>;
  automation: Record<string, unknown>;
  evidence: RuntimeMainBrainSection;
  decisions: RuntimeMainBrainSection;
  patches: RuntimeMainBrainSection;
  signals: Record<string, unknown>;
  meta: Record<string, unknown>;
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
