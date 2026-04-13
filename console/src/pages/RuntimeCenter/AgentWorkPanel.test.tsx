// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AgentWorkPanel from "./AgentWorkPanel";

describe("AgentWorkPanel", () => {
  it("shows only the morning report by default during the day", () => {
    render(
      <AgentWorkPanel
        title="小运营"
        summaryFields={[
          { label: "职责", value: "负责整理交付内容" },
          { label: "主要负责工作", value: "整理交付说明并回传进度" },
        ]}
        morningReport={{
          title: "早报",
          items: ["今天先整理交付说明。", "重点先收主资料。", "风险是最后确认还没回来。"],
        }}
        trend={[
          { label: "周一", completed: 1, completionRate: 80, quality: 75 },
          { label: "周二", completed: 2, completionRate: 90, quality: 82 },
        ]}
        dayMode="day"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "日报" }));

    expect(screen.getByText("今天先整理交付说明。")).toBeInTheDocument();
    expect(screen.queryByText("晚报")).not.toBeInTheDocument();
  });

  it("shows the evening report first at night and keeps the morning report collapsed", () => {
    render(
      <AgentWorkPanel
        title="小运营"
        summaryFields={[
          { label: "职责", value: "负责整理交付内容" },
          { label: "主要负责工作", value: "整理交付说明并回传进度" },
        ]}
        morningReport={{
          title: "早报",
          items: ["今天先整理交付说明。", "重点先收主资料。", "风险是最后确认还没回来。"],
        }}
        eveningReport={{
          title: "晚报",
          items: ["今天已经整理完主体说明。", "出了可发给用户的版本。", "明天继续补最后确认。"],
        }}
        trend={[
          { label: "周一", completed: 1, completionRate: 80, quality: 75 },
          { label: "周二", completed: 2, completionRate: 90, quality: 82 },
        ]}
        dayMode="night"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "日报" }));

    expect(screen.getByText("今天已经整理完主体说明。")).toBeInTheDocument();
    expect(screen.queryByText("今天先整理交付说明。")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "展开早报" }));

    expect(screen.getByText("今天先整理交付说明。")).toBeInTheDocument();
  });
});
