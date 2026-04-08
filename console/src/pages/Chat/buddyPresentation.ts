import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import { resolveBuddyEvolutionView } from "./buddyEvolution";

function firstNonEmptyString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }
    const normalized = value.trim();
    if (normalized) {
      return normalized;
    }
  }
  return "";
}

export function presentBuddyStageLabel(stage?: string | null): string {
  switch ((stage || "").trim()) {
    case "seed":
      return "幼年期";
    case "bonded":
      return "成长期";
    case "capable":
      return "成熟期";
    case "seasoned":
      return "完全体";
    case "signature":
      return "究极体";
    default:
      return "成长中";
  }
}

export function presentBuddyPresenceLabel(presence?: string | null): string {
  switch ((presence || "").trim()) {
    case "attentive":
      return "留意着你";
    case "focused":
      return "专注陪你";
    case "supporting":
      return "正在陪跑";
    case "pulling-back":
      return "把你拉回正轨";
    case "celebrating":
      return "陪你庆祝";
    case "resting":
      return "安静守着";
    case "idle":
    case "available":
    default:
      return "陪在身边";
  }
}

export function presentBuddyMoodLabel(mood?: string | null): string {
  switch ((mood || "").trim()) {
    case "warm":
      return "温暖";
    case "concerned":
      return "在意你";
    case "playful":
      return "轻松";
    case "proud":
      return "替你骄傲";
    case "determined":
      return "很坚定";
    case "calm":
    default:
      return "平静";
  }
}

export function presentBuddyEncouragementStyleLabel(style?: string | null): string {
  switch ((style || "").trim()) {
    case "old-friend":
      return "像老朋友";
    case "coach":
      return "像成长教练";
    case "steady":
      return "稳稳陪着你";
    default:
      return "像老朋友";
  }
}

export type BuddyDisplaySnapshot = {
  buddyName: string;
  finalGoalSummary: string;
  currentTaskSummary: string;
  whyNowSummary: string;
  singleNextActionSummary: string;
  companionStrategySummary: string | null;
  stage: string;
  stageLabel: string;
  capabilityPoints: number;
  settledClosureCount: number;
  independentOutcomeCount: number;
  distinctSettledCycleCount: number;
  recentCompletionRate: number;
  recentExecutionErrorRate: number;
  progressToNextStage: number;
  presenceLabel: string;
  moodLabel: string;
  encouragementStyleLabel: string;
};

export function resolveBuddyDisplaySnapshot(
  surface: BuddySurfaceResponse,
): BuddyDisplaySnapshot {
  const evolution = resolveBuddyEvolutionView({
    evolutionStage: surface.growth?.evolution_stage,
    currentForm: surface.presentation?.current_form,
    capabilityPoints: surface.growth?.capability_points,
    capabilityScore: surface.growth?.capability_score,
    companionExperience: surface.growth?.companion_experience,
    rarity: surface.presentation?.rarity,
  });
  const buddyName = firstNonEmptyString(
    surface.presentation?.buddy_name,
    surface.relationship?.buddy_name,
    "你的伙伴",
  );
  const finalGoalSummary = firstNonEmptyString(
    surface.presentation?.current_goal_summary,
    surface.growth_target?.final_goal,
    surface.growth_target?.primary_direction,
    "先一起确认最终目标。",
  );
  const currentTaskSummary = firstNonEmptyString(
    surface.presentation?.current_task_summary,
    "先把当前任务缩成一个最小动作。",
  );
  const whyNowSummary = firstNonEmptyString(
    surface.presentation?.why_now_summary,
    surface.growth_target?.why_it_matters,
    "先把最关键的一步落下来。",
  );
  const singleNextActionSummary = firstNonEmptyString(
    surface.presentation?.single_next_action_summary,
    currentTaskSummary,
    "先完成眼前这一个最小动作。",
  );
  const companionStrategySummary = firstNonEmptyString(
    surface.presentation?.companion_strategy_summary,
  );

  return {
    buddyName,
    finalGoalSummary,
    currentTaskSummary,
    whyNowSummary,
    singleNextActionSummary,
    companionStrategySummary: companionStrategySummary || null,
    stage: evolution.stage,
    stageLabel: presentBuddyStageLabel(evolution.stage),
    capabilityPoints: Math.max(0, Number(surface.growth?.capability_points ?? 0)),
    settledClosureCount: Math.max(0, Number(surface.growth?.settled_closure_count ?? 0)),
    independentOutcomeCount: Math.max(
      0,
      Number(surface.growth?.independent_outcome_count ?? 0),
    ),
    distinctSettledCycleCount: Math.max(
      0,
      Number(surface.growth?.distinct_settled_cycle_count ?? 0),
    ),
    recentCompletionRate: Math.max(0, Number(surface.growth?.recent_completion_rate ?? 0)),
    recentExecutionErrorRate: Math.max(
      0,
      Number(surface.growth?.recent_execution_error_rate ?? 0),
    ),
    progressToNextStage: Math.max(0, Number(surface.growth?.progress_to_next_stage ?? 0)),
    presenceLabel: presentBuddyPresenceLabel(surface.presentation?.presence_state),
    moodLabel: presentBuddyMoodLabel(surface.presentation?.mood_state),
    encouragementStyleLabel: presentBuddyEncouragementStyleLabel(
      surface.relationship?.encouragement_style,
    ),
  };
}

export function buildBuddyStatusLine(surface: BuddySurfaceResponse): string {
  const snapshot = resolveBuddyDisplaySnapshot(surface);
  return `${snapshot.buddyName} · ${snapshot.stageLabel} · ${snapshot.presenceLabel} · ${snapshot.moodLabel}`;
}
