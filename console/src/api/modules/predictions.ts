import { request } from "../request";

export interface PredictionCaseRecord {
  case_id: string;
  title: string;
  summary: string;
  case_kind: "manual" | "cycle";
  status: "open" | "reviewing" | "closed" | "failed";
  topic_type: string;
  owner_scope?: string | null;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  workflow_run_id?: string | null;
  question: string;
  time_window_days: number;
  overall_confidence: number;
  primary_recommendation_id?: string | null;
  input_payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PredictionScenarioRecord {
  scenario_id: string;
  case_id: string;
  scenario_kind: "best" | "base" | "worst";
  title: string;
  summary: string;
  confidence: number;
  goal_delta: number;
  task_load_delta: number;
  risk_delta: number;
  resource_delta: number;
  externality_delta: number;
  assumptions: string[];
  risk_factors: string[];
  recommendation_ids: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PredictionSignalRecord {
  signal_id: string;
  case_id: string;
  label: string;
  summary: string;
  source_kind: string;
  source_ref?: string | null;
  direction: "positive" | "negative" | "neutral";
  strength: number;
  metric_key?: string | null;
  report_id?: string | null;
  evidence_id?: string | null;
  agent_id?: string | null;
  workflow_run_id?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PredictionRecommendationRecord {
  recommendation_id: string;
  case_id: string;
  recommendation_type: string;
  title: string;
  summary: string;
  priority: number;
  confidence: number;
  risk_level: "auto" | "guarded" | "confirm";
  action_kind: string;
  executable: boolean;
  auto_eligible: boolean;
  auto_executed: boolean;
  status: string;
  target_agent_id?: string | null;
  target_goal_id?: string | null;
  target_schedule_id?: string | null;
  target_capability_ids: string[];
  decision_request_id?: string | null;
  execution_task_id?: string | null;
  execution_evidence_id?: string | null;
  outcome_summary?: string | null;
  action_payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PredictionReviewRecord {
  review_id: string;
  case_id: string;
  recommendation_id?: string | null;
  reviewer?: string | null;
  summary: string;
  outcome: "hit" | "partial" | "miss" | "unknown";
  adopted?: boolean | null;
  benefit_score?: number | null;
  actual_payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PredictionCaseSummary {
  case: PredictionCaseRecord;
  scenario_count: number;
  signal_count: number;
  recommendation_count: number;
  review_count: number;
  latest_review_outcome?: string | null;
  pending_decision_count: number;
  routes: Record<string, string>;
}

export interface PredictionDecisionRecord {
  id: string;
  task_id?: string | null;
  decision_type?: string | null;
  risk_level?: string | null;
  summary?: string | null;
  status?: string | null;
  requested_by?: string | null;
  resolution?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  expires_at?: string | null;
  route?: string | null;
  governance_route?: string | null;
  chat_thread_id?: string | null;
  chat_route?: string | null;
  preferred_route?: string | null;
  requires_human_confirmation?: boolean;
  [key: string]: unknown;
}

export interface PredictionRecommendationView {
  recommendation: PredictionRecommendationRecord;
  decision?: PredictionDecisionRecord | null;
  routes: Record<string, string>;
}

export interface PredictionCaseDetail {
  case: PredictionCaseRecord;
  scenarios: PredictionScenarioRecord[];
  signals: PredictionSignalRecord[];
  recommendations: PredictionRecommendationView[];
  reviews: PredictionReviewRecord[];
  stats: Record<string, unknown>;
  routes: Record<string, unknown>;
}

export interface PredictionRecommendationExecutionResponse {
  execution: {
    phase?: string;
    summary?: string;
    decision_request_id?: string | null;
    error?: string | null;
    [key: string]: unknown;
  };
  decision?: PredictionDecisionRecord | null;
  detail: PredictionCaseDetail;
}

export interface PredictionRecommendationCoordinationResponse {
  detail: PredictionCaseDetail;
  summary?: string;
  industry_instance_id?: string | null;
  backlog_item_id?: string | null;
  backlog_status?: string | null;
  reused_backlog?: boolean;
  started_cycle_id?: string | null;
  coordination_reason?: string | null;
  chat_thread_id?: string | null;
  chat_route?: string | null;
}

export interface PredictionReviewPayload {
  recommendation_id?: string;
  reviewer?: string;
  summary?: string;
  outcome?: "hit" | "partial" | "miss" | "unknown";
  adopted?: boolean | null;
  benefit_score?: number | null;
  actual_payload?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export const predictionsApi = {
  listPredictions: (params?: {
    case_kind?: string;
    status?: string;
    industry_instance_id?: string;
    owner_scope?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.case_kind) {
      search.set("case_kind", params.case_kind);
    }
    if (params?.status) {
      search.set("status", params.status);
    }
    if (params?.industry_instance_id) {
      search.set("industry_instance_id", params.industry_instance_id);
    }
    if (params?.owner_scope) {
      search.set("owner_scope", params.owner_scope);
    }
    if (typeof params?.limit === "number") {
      search.set("limit", String(params.limit));
    }
    const suffix = search.toString();
    return request<PredictionCaseSummary[]>(
      `/predictions${suffix ? `?${suffix}` : ""}`,
    );
  },

  getPredictionCase: (caseId: string) =>
    request<PredictionCaseDetail>(`/predictions/${encodeURIComponent(caseId)}`),

  coordinatePredictionRecommendation: (
    caseId: string,
    recommendationId: string,
    payload?: { actor?: string },
  ) =>
    request<PredictionRecommendationCoordinationResponse>(
      `/predictions/${encodeURIComponent(caseId)}/recommendations/${encodeURIComponent(recommendationId)}/coordinate`,
      {
        method: "POST",
        body: JSON.stringify(payload || {}),
      },
    ),

  addPredictionReview: (caseId: string, payload: PredictionReviewPayload) =>
    request<PredictionCaseDetail>(
      `/predictions/${encodeURIComponent(caseId)}/reviews`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
