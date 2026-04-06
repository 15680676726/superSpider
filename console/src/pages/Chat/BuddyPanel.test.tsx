// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BuddyPanel } from "./BuddyPanel";

describe("BuddyPanel", () => {
  it("renders relationship, growth, and buddy goal/task summaries from the buddy surface", () => {
    render(
      <BuddyPanel
        open
        onClose={() => {}}
        surface={
          {
            profile: {
              display_name: "Alex",
            },
            relationship: {
              encouragement_style: "old-friend",
            },
            presentation: {
              buddy_name: "Nova",
              presence_state: "supporting",
              mood_state: "warm",
              rarity: "common",
              current_goal_summary: "建立可持续的创作事业与独立成长轨道",
              current_task_summary: "写出第一篇真正代表自己的案例文章",
              why_now_summary: "这是把长期方向拉进现实的第一份证据。",
              single_next_action_summary: "现在先打开文档，写下案例标题和三条核心观点。",
              companion_strategy_summary:
                "先接住情绪，再把任务缩成一个最小动作；避免高压催促。",
            },
            growth: {
              evolution_stage: "bonded",
              intimacy: 25,
              affinity: 19,
              growth_level: 2,
              companion_experience: 45,
              knowledge_value: 20,
              skill_value: 12,
              communication_count: 7,
              completed_support_runs: 2,
              pleasant_interaction_score: 31,
              progress_to_next_stage: 44,
            },
          } as never
        }
      />,
    );

    expect(screen.getByText("Nova 的伙伴面板")).toBeInTheDocument();
    expect(screen.getByText(/当前陪伴状态：/)).toBeInTheDocument();
    expect(screen.getByText("建立可持续的创作事业与独立成长轨道")).toBeInTheDocument();
    expect(screen.getByText("写出第一篇真正代表自己的案例文章")).toBeInTheDocument();
    expect(screen.getByText("现在先打开文档，写下案例标题和三条核心观点。")).toBeInTheDocument();
    expect(screen.getByText("先接住情绪，再把任务缩成一个最小动作；避免高压催促。")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-panel-avatar-species")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-panel-avatar-rarity")).toBeInTheDocument();
    expect(screen.getByText(/知识值/)).toBeInTheDocument();
  });
});
