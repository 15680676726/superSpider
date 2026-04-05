// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BuddyCompanion } from "./BuddyCompanion";

describe("BuddyCompanion", () => {
  it("renders compact buddy shell and opens panel on click", () => {
    const onOpen = vi.fn();
    render(
      <BuddyCompanion
        surface={
          {
            presentation: {
              buddy_name: "Nova",
              presence_state: "focused",
              mood_state: "warm",
              rarity: "rare",
            },
            growth: {
              evolution_stage: "bonded",
              intimacy: 24,
            },
          } as never
        }
        onOpen={onOpen}
      />,
    );

    expect(screen.getByText("Nova")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-companion-species")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-companion-rarity")).toBeInTheDocument();
    expect(screen.getByTestId("buddy-companion-sprite")).toHaveAttribute(
      "data-presence",
      "focused",
    );
    expect(screen.getByText("亲密度 24")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("buddy-companion-trigger"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
