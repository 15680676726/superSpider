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

export const runtimeCenterApi = {
  getRuntimeTaskDetail: (taskId: string) =>
    request<RuntimeTaskDetail>(
      `/runtime-center/tasks/${encodeURIComponent(taskId)}`,
    ),

  getRuntimeTaskReview: (taskId: string) =>
    request<RuntimeTaskReviewPayload>(
      `/runtime-center/tasks/${encodeURIComponent(taskId)}/review`,
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
