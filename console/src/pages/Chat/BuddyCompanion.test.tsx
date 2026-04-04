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
        surface={{
          presentation: {
            buddy_name: "Nova",
          },
          growth: {
            evolution_stage: "bonded",
            intimacy: 24,
          },
        } as never}
        onOpen={onOpen}
      />,
    );

    expect(screen.getByText("Nova")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("buddy-companion-trigger"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
