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
  it("renders trace lines inside the dedicated trace tab", () => {
    render(
      <AgentWorkPanel
        title="测试执行位"
        summaryFields={[{ label: "职责", value: "负责回传执行结果" }]}
        trace={[
          {
            timestamp: "2026-04-16 09:00:00",
            level: "info",
            message: "接到任务：整理交付证据",
          },
          {
            timestamp: "2026-04-16 09:10:00",
            level: "warn",
            message: "等待确认：补齐截图",
          },
        ]}
        dayMode="day"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "追溯" }));

    expect(screen.getByText("2026-04-16 09:00:00")).toBeInTheDocument();
    expect(screen.getByText("接到任务：整理交付证据")).toBeInTheDocument();
    expect(screen.getByText("等待确认：补齐截图")).toBeInTheDocument();
  });
});
