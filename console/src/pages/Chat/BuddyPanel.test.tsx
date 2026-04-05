// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BuddyPanel } from "./BuddyPanel";

describe("BuddyPanel", () => {
  it("renders relationship, growth, and donor-style avatar metadata from buddy surface", () => {
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
              current_goal_summary: "Become a durable creator",
              current_task_summary: "Publish the first case study",
              why_now_summary: "This unlocks the first proof of work.",
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
    expect(screen.getByText("Become a durable creator")).toBeInTheDocument();
    expect(screen.getByText("Publish the first case study")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-panel-avatar-species")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-panel-avatar-rarity")).toBeInTheDocument();
    expect(screen.getByText(/知识值/)).toBeInTheDocument();
  });
});
