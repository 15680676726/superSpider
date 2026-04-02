// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatIntentShellCard } from "./ChatIntentShellCard";

describe("ChatIntentShellCard", () => {
  it("renders the current shell surface in the same chat window", () => {
    render(
      <ChatIntentShellCard
        shell={{
          mode: "plan",
          label: "PLAN",
          summary: "Use a compact planning shell for this reply.",
          hint:
            "Goal, constraints, affected scope/files, checklist, acceptance criteria, verification steps.",
          triggerSource: "keyword",
          matchedText: "计划",
          confidence: 0.95,
          updatedAt: 500,
          payload: {
            mode_hint: "plan",
          },
        }}
      />,
    );

    expect(screen.getByText("PLAN")).toBeTruthy();
    expect(
      screen.getByText("Use a compact planning shell for this reply."),
    ).toBeTruthy();
    expect(screen.getByText(/Goal, constraints/)).toBeTruthy();
  });
});
