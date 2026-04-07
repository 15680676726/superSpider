import { describe, expect, it } from "vitest";

import {
  buildBuddyStatusLine,
  presentBuddyEncouragementStyleLabel,
  presentBuddyMoodLabel,
  presentBuddyPresenceLabel,
  presentBuddyStageLabel,
  resolveBuddyDisplaySnapshot,
} from "./buddyPresentation";

describe("buddyPresentation", () => {
  it("maps evolution, presence, mood, and encouragement labels into readable text", () => {
    expect(presentBuddyStageLabel("seed")).toBe("幼年期");
    expect(presentBuddyStageLabel("signature")).toBe("究极体");
    expect(presentBuddyPresenceLabel("focused")).toBe("专注陪你");
    expect(presentBuddyMoodLabel("determined")).toBe("很坚定");
    expect(presentBuddyEncouragementStyleLabel("old-friend")).toBe("像老朋友");
  });

  it("builds a compact buddy status line", () => {
    expect(
      buildBuddyStatusLine({
        presentation: {
          buddy_name: "Nova",
          presence_state: "focused",
          mood_state: "warm",
        },
        growth: {
          evolution_stage: "bonded",
          capability_points: 24,
          capability_score: 24,
        },
      } as never),
    ).toBe("Nova · 成长期 · 专注陪你 · 温暖");
  });

  it("resolves a single buddy display snapshot with fallbacks", () => {
    expect(
      resolveBuddyDisplaySnapshot({
        growth_target: {
          final_goal: "建立可持续的创作事业",
          why_it_matters: "这是把长期方向落到现实里的关键一步。",
        },
        relationship: {
          buddy_name: "Nova",
          encouragement_style: "old-friend",
        },
        presentation: {
          buddy_name: "",
          current_goal_summary: "",
          current_task_summary: "先写出第一篇案例文章",
          why_now_summary: "",
          single_next_action_summary: "现在先打开文档，写下标题和三条要点",
          companion_strategy_summary: "先接住情绪，再把任务缩成一个最小动作。",
          presence_state: "focused",
          mood_state: "warm",
          current_form: "",
        },
        growth: {
          capability_points: 40,
          capability_score: 63,
          companion_experience: 180,
          evolution_stage: "",
        },
      } as never),
    ).toEqual(
      expect.objectContaining({
        buddyName: "Nova",
        finalGoalSummary: "建立可持续的创作事业",
        currentTaskSummary: "先写出第一篇案例文章",
        whyNowSummary: "这是把长期方向落到现实里的关键一步。",
        singleNextActionSummary: "现在先打开文档，写下标题和三条要点",
        companionStrategySummary: "先接住情绪，再把任务缩成一个最小动作。",
        stageLabel: "成熟期",
        encouragementStyleLabel: "像老朋友",
      }),
    );
  });
});
