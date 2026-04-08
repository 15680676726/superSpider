import { request } from "../request";

export interface BuddyIdentityRequest {
  display_name: string;
  profession: string;
  current_stage: string;
  interests: string[];
  strengths: string[];
  constraints: string[];
  goal_intention: string;
}

export interface BuddyIdentityResponse {
  session_id: string;
  profile: {
    profile_id: string;
    display_name: string;
    profession: string;
    current_stage: string;
    interests: string[];
    strengths: string[];
    constraints: string[];
    goal_intention: string;
  };
  question_count: number;
  next_question: string;
  finished: boolean;
}

export interface BuddyClarificationResponse {
  session_id: string;
  question_count: number;
  tightened: boolean;
  finished: boolean;
  next_question: string;
  candidate_directions: string[];
  recommended_direction: string;
}

export interface BuddyExecutionCarrierChatBinding {
  thread_id?: string | null;
  control_thread_id?: string | null;
  user_id?: string | null;
  channel?: string | null;
  context_key?: string | null;
  binding_kind?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface BuddyExecutionCarrier {
  instance_id: string;
  label: string;
  owner_scope: string;
  current_cycle_id: string;
  team_generated: boolean;
  thread_id?: string | null;
  control_thread_id?: string | null;
  chat_binding?: BuddyExecutionCarrierChatBinding | null;
}

export interface BuddyConfirmDirectionResponse {
  session: {
    session_id: string;
    profile_id: string;
    status: string;
    question_count: number;
    candidate_directions: string[];
    recommended_direction: string;
    selected_direction: string;
  };
  growth_target: {
    target_id: string;
    profile_id: string;
    primary_direction: string;
    final_goal: string;
    why_it_matters: string;
    current_cycle_label: string;
  };
  relationship: {
    relationship_id: string;
    profile_id: string;
    buddy_name: string;
    encouragement_style: string;
  };
  domain_capability?: {
    domain_id: string;
    profile_id: string;
    domain_key: string;
    domain_label: string;
    status: string;
    capability_points?: number;
    settled_closure_count?: number;
    independent_outcome_count?: number;
    recent_completion_rate?: number;
    recent_execution_error_rate?: number;
    distinct_settled_cycle_count?: number;
    strategy_score: number;
    execution_score: number;
    evidence_score: number;
    stability_score: number;
    capability_score: number;
    evolution_stage: string;
  } | null;
  execution_carrier?: BuddyExecutionCarrier | null;
}

export interface BuddyDirectionTransitionPreviewResponse {
  session_id: string;
  selected_direction: string;
  selected_domain_key: string;
  suggestion_kind: string;
  recommended_action: "keep-active" | "restore-archived" | "start-new";
  reason_summary: string;
  current_domain?: {
    domain_id: string;
    domain_key: string;
    domain_label: string;
    status: string;
    capability_points?: number;
    capability_score: number;
    evolution_stage: string;
  } | null;
  archived_matches: Array<{
    domain_id: string;
    domain_key: string;
    domain_label: string;
    status: string;
    capability_points?: number;
    capability_score: number;
    evolution_stage: string;
  }>;
}

export interface BuddySurfaceResponse {
  profile: {
    profile_id: string;
    display_name: string;
    profession: string;
    current_stage: string;
    interests: string[];
    strengths: string[];
    constraints: string[];
    goal_intention: string;
  };
  growth_target?: {
    target_id: string;
    profile_id: string;
    primary_direction: string;
    final_goal: string;
    why_it_matters: string;
    current_cycle_label: string;
  } | null;
  relationship?: {
    relationship_id: string;
    profile_id: string;
    buddy_name: string;
    encouragement_style: string;
  } | null;
  execution_carrier?: BuddyExecutionCarrier | null;
  presentation: {
    profile_id: string;
    buddy_name: string;
    lifecycle_state: string;
    presence_state: string;
    mood_state: string;
    current_form: string;
    rarity: string;
    current_goal_summary: string;
    current_task_summary: string;
    why_now_summary: string;
    single_next_action_summary: string;
    companion_strategy_summary: string;
  };
  growth: {
    profile_id: string;
    domain_id?: string;
    domain_key?: string;
    domain_label?: string;
    intimacy: number;
    affinity: number;
    growth_level: number;
    companion_experience: number;
    capability_points?: number;
    capability_score?: number;
    settled_closure_count?: number;
    independent_outcome_count?: number;
    recent_completion_rate?: number;
    recent_execution_error_rate?: number;
    distinct_settled_cycle_count?: number;
    strategy_score?: number;
    execution_score?: number;
    evidence_score?: number;
    stability_score?: number;
    knowledge_value: number;
    skill_value: number;
    pleasant_interaction_score: number;
    communication_count: number;
    completed_support_runs: number;
    completed_assisted_closures: number;
    evolution_stage: string;
    progress_to_next_stage: number;
  };
  onboarding: {
    session_id: string | null;
    status: string;
    question_count: number;
    tightened: boolean;
    next_question: string;
    candidate_directions: string[];
    recommended_direction: string;
    selected_direction: string;
    requires_direction_confirmation: boolean;
    requires_naming: boolean;
    completed: boolean;
  };
}

export const buddyApi = {
  submitBuddyIdentity(payload: BuddyIdentityRequest) {
    return request<BuddyIdentityResponse>("/buddy/onboarding/identity", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  answerBuddyClarification(payload: {
    session_id: string;
    answer: string;
    existing_question_count?: number;
  }) {
    return request<BuddyClarificationResponse>("/buddy/onboarding/clarify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listBuddyCandidateDirections(sessionId: string) {
    return request<BuddyClarificationResponse>(
      `/buddy/onboarding/${encodeURIComponent(sessionId)}/candidates`,
    );
  },
  previewBuddyDirectionTransition(payload: {
    session_id: string;
    selected_direction: string;
  }) {
    return request<BuddyDirectionTransitionPreviewResponse>(
      "/buddy/onboarding/direction-transition-preview",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  confirmBuddyDirection(payload: {
    session_id: string;
    selected_direction: string;
    capability_action: "keep-active" | "restore-archived" | "start-new";
    target_domain_id?: string;
  }) {
    return request<BuddyConfirmDirectionResponse>("/buddy/onboarding/confirm-direction", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  nameBuddy(payload: { session_id: string; buddy_name: string }) {
    return request<{ buddy_name: string; profile_id: string }>("/buddy/name", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getBuddySurface(profileId?: string | null) {
    const suffix = profileId
      ? `?profile_id=${encodeURIComponent(profileId)}`
      : "";
    return request<BuddySurfaceResponse>(`/buddy/surface${suffix}`);
  },
};

