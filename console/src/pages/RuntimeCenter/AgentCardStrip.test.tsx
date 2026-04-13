// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AgentCardStrip from "./AgentCardStrip";

describe("AgentCardStrip", () => {
  it("keeps main brain first and moves attention cards before normal cards", () => {
    const onSelect = vi.fn();

    render(
      <AgentCardStrip
        agents={[
          {
            id: "agent-normal",
            name: "小运营",
            role: "运营",
            status: "推进中",
            progress: 42,
            needsAttention: false,
          },
          {
            id: "agent-pending",
            name: "小客服",
            role: "客服",
            status: "待处理",
            progress: 18,
            needsAttention: true,
          },
          {
            id: "main-brain",
            name: "伙伴",
            role: "主脑",
            status: "统筹中",
            progress: 66,
            needsAttention: false,
            isMainBrain: true,
          },
        ]}
        selectedId="main-brain"
        onSelect={onSelect}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toHaveTextContent("伙伴");
    expect(buttons[1]).toHaveTextContent("小客服");
    expect(buttons[2]).toHaveTextContent("小运营");

    fireEvent.click(screen.getByRole("button", { name: /小运营 运营/i }));
    expect(onSelect).toHaveBeenCalledWith("agent-normal");
  });
});
