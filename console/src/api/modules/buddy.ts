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
  };
  growth: {
    profile_id: string;
    intimacy: number;
    affinity: number;
    growth_level: number;
    companion_experience: number;
    knowledge_value: number;
    skill_value: number;
    pleasant_interaction_score: number;
    communication_count: number;
    completed_support_runs: number;
    completed_assisted_closures: number;
    evolution_stage: string;
    progress_to_next_stage: number;
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
  confirmBuddyDirection(payload: {
    session_id: string;
    selected_direction: string;
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

