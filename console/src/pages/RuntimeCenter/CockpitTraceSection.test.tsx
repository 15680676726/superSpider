// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CockpitTraceSection from "./CockpitTraceSection";

describe("CockpitTraceSection", () => {
  it("renders trace lines in order as plain logs", () => {
    render(
      <CockpitTraceSection
        trace={[
          {
            timestamp: "2026-04-16T09:00:00Z",
            level: "info",
            message: "接到新派工：整理交付说明",
          },
          {
            timestamp: "2026-04-16T09:20:00Z",
            level: "warn",
            message: "需要你决定：是否现在发送给用户",
            route: "/runtime-center/decisions/decision-1",
          },
        ]}
      />,
    );

    const lines = screen.getAllByTestId("cockpit-trace-line");
    expect(lines).toHaveLength(2);
    expect(lines[0]).toHaveTextContent("接到新派工：整理交付说明");
    expect(lines[1]).toHaveTextContent("需要你决定：是否现在发送给用户");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("shows an empty state when no trace exists", () => {
    render(<CockpitTraceSection trace={[]} />);

    expect(screen.getByText("今天还没有新的追溯记录。")).toBeInTheDocument();
  });
});
