// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  default: {
    listIndustryInstances: vi.fn(),
  },
}));

vi.mock("../pages/Chat/sessionApi", () => ({
  default: {
    getActiveThreadId: vi.fn(() => null),
  },
}));

import Sidebar from "./Sidebar";

describe("Sidebar", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders localized sidebar labels in Chinese", async () => {
    render(
      <MemoryRouter>
        <Sidebar selectedKey="runtime-center" />
      </MemoryRouter>,
    );

    expect(screen.getByText("对话")).toBeInTheDocument();
    expect(screen.getByText("聊天")).toBeInTheDocument();
    expect(screen.getByText("运行")).toBeInTheDocument();
    expect(screen.getByText("运行中心")).toBeInTheDocument();
    expect(screen.getByText("智能体")).toBeInTheDocument();
    expect(screen.getByText("行业中枢")).toBeInTheDocument();
    expect(screen.getByText("设置")).toBeInTheDocument();
    expect(screen.getByText("系统")).toBeInTheDocument();
    expect(screen.getByText("渠道")).toBeInTheDocument();
    expect(screen.getByText("模型")).toBeInTheDocument();
    expect(screen.getByText("环境")).toBeInTheDocument();
    expect(screen.getByText("智能体配置")).toBeInTheDocument();

    fireEvent.click(screen.getByText("构建"));
    fireEvent.click(screen.getByText("洞察"));

    await waitFor(() => {
      expect(screen.getByText("能力市场")).toBeInTheDocument();
      expect(screen.getByText("知识库")).toBeInTheDocument();
      expect(screen.getByText("报告")).toBeInTheDocument();
      expect(screen.getByText("绩效")).toBeInTheDocument();
      expect(screen.getByText("日历")).toBeInTheDocument();
      expect(screen.getByText("预测")).toBeInTheDocument();
    });

    expect(screen.queryByText("Chat")).not.toBeInTheDocument();
    expect(screen.queryByText("Runtime Center")).not.toBeInTheDocument();
    expect(screen.queryByText("Capability Market")).not.toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });
});
