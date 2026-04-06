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
          summary: "这次回复使用精简计划模式。",
          hint:
            "覆盖焦点、约束、影响范围/文件、检查清单、验收标准和验证步骤。",
          triggerSource: "keyword",
          matchedText: "计划",
          confidence: 0.95,
          triggerSourceLabel: "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d",
          matchedTextLabel: "\u547d\u4e2d\uff1a\u8ba1\u5212",
          confidenceLabel: "\u7f6e\u4fe1\u5ea6 95%",
          metaSummary:
            "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d \u00b7 \u547d\u4e2d\uff1a\u8ba1\u5212 \u00b7 \u7f6e\u4fe1\u5ea6 95%",
          updatedAt: 500,
          payload: {
            mode_hint: "plan",
          },
        }}
      />,
    );

    expect(screen.getByText("PLAN")).toBeTruthy();
    expect(
      screen.getByText("这次回复使用精简计划模式。"),
    ).toBeTruthy();
    expect(
      screen.getByText("覆盖焦点、约束、影响范围/文件、检查清单、验收标准和验证步骤。"),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d \u00b7 \u547d\u4e2d\uff1a\u8ba1\u5212 \u00b7 \u7f6e\u4fe1\u5ea6 95%",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/trigger=keyword/)).toBeNull();
    expect(screen.queryByText(/match=\u8ba1\u5212/)).toBeNull();
    expect(screen.queryByText(/confidence=0.95/)).toBeNull();
  });
});
