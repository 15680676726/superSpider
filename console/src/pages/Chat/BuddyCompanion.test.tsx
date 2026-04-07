// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BuddyCompanion } from "./BuddyCompanion";

describe("BuddyCompanion", () => {
  it("renders final goal and current task ahead of decorative stats, then opens panel on click", () => {
    const onOpen = vi.fn();
    render(
      <BuddyCompanion
        surface={
          {
            growth_target: {
              final_goal: "完成职业转型并建立稳定作品集",
              why_it_matters: "这是接下来半年最关键的成长主线",
            },
            relationship: {
              encouragement_style: "old-friend",
            },
            presentation: {
              buddy_name: "Nova",
              presence_state: "focused",
              mood_state: "warm",
              rarity: "rare",
              current_goal_summary: "",
              current_task_summary: "先整理第一版作品集目录",
              why_now_summary: "",
              single_next_action_summary: "现在先列出 3 个必须入选的作品",
            },
            growth: {
              evolution_stage: "bonded",
              capability_points: 24,
              intimacy: 24,
              companion_experience: 48,
            },
          } as never
        }
        onOpen={onOpen}
      />,
    );

    expect(screen.getByText("Nova")).toBeInTheDocument();
    expect(screen.getByText("最终目标")).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) =>
        Boolean(element?.textContent?.includes("完成职业转型并建立稳定作品集")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("当前任务")).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) =>
        Boolean(element?.textContent?.includes("先整理第一版作品集目录")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("下一步")).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) =>
        Boolean(element?.textContent?.includes("现在先列出 3 个必须入选的作品")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByTestId("buddy-companion-species")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-companion-rarity")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-companion-sprite")).toHaveAttribute(
      "data-presence",
      "focused",
    );
    expect(screen.getByText("亲密度 24")).toBeInTheDocument();
    expect(screen.getByText("积分 24")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("buddy-companion-trigger"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
