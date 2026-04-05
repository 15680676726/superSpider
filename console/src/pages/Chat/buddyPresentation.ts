import type { BuddySurfaceResponse } from "../../api/modules/buddy";

export function presentBuddyStageLabel(stage?: string | null): string {
  switch ((stage || "").trim()) {
    case "seed":
      return "初生";
    case "bonded":
      return "结伴";
    case "capable":
      return "得力";
    case "seasoned":
      return "成熟";
    case "signature":
      return "标志形态";
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

export function buildBuddyStatusLine(surface: BuddySurfaceResponse): string {
  const name = surface.presentation.buddy_name || "你的伙伴";
  const stage = presentBuddyStageLabel(surface.growth.evolution_stage);
  const presence = presentBuddyPresenceLabel(surface.presentation.presence_state);
  const mood = presentBuddyMoodLabel(surface.presentation.mood_state);
  return `${name} · ${stage} · ${presence} · ${mood}`;
}
