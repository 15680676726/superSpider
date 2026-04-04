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

export function presentBuddyMoodLabel(mood?: string | null): string {
  switch ((mood || "").trim()) {
    case "warm":
      return "温暖";
    case "concerned":
      return "在意你";
    case "playful":
      return "轻松";
    case "proud":
      return "为你骄傲";
    case "determined":
      return "很笃定";
    case "calm":
    default:
      return "平静";
  }
}

export function buildBuddyStatusLine(surface: BuddySurfaceResponse): string {
  const name = surface.presentation.buddy_name || "你的伙伴";
  const stage = presentBuddyStageLabel(surface.growth.evolution_stage);
  const mood = presentBuddyMoodLabel(surface.presentation.mood_state);
  return `${name} · ${stage} · ${mood}`;
}

