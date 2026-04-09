// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

const { getActiveThreadIdMock, navigateMock } = vi.hoisted(() => ({
  getActiveThreadIdMock: vi.fn<() => string | null>(() => null),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../api", () => ({
  default: {
    listIndustryInstances: vi.fn(),
  },
}));

vi.mock("../pages/Chat/sessionApi", () => ({
  default: {
    getActiveThreadId: getActiveThreadIdMock,
  },
}));

import Sidebar from "./Sidebar";

describe("Sidebar", () => {
  afterEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    getActiveThreadIdMock.mockReset();
    getActiveThreadIdMock.mockReturnValue(null);
  });

  it("renders runtime-center-first navigation labels", async () => {
    render(
      <MemoryRouter>
        <Sidebar selectedKey="runtime-center" />
      </MemoryRouter>,
    );

    expect(screen.getByText("超级伙伴")).toBeInTheDocument();
    expect(screen.getByText("Super Partner 长期自治运行中心")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
    expect(screen.getByText("聊天前台")).toBeInTheDocument();
    expect(screen.getByText("运行中心")).toBeInTheDocument();
    expect(screen.getByText("主脑驾驶舱")).toBeInTheDocument();
    expect(screen.queryByText("执行位")).toBeNull();
    expect(screen.getByText("行业工作台")).toBeInTheDocument();
    expect(screen.getByText("设置")).toBeInTheDocument();
    expect(screen.getByText("系统维护")).toBeInTheDocument();
    expect(screen.getByText("渠道")).toBeInTheDocument();
    expect(screen.getByText("模型")).toBeInTheDocument();
    expect(screen.getByText("环境")).toBeInTheDocument();
    expect(screen.getByText("智能体配置")).toBeInTheDocument();

    expect(screen.getByText("能力市场")).toBeInTheDocument();
    fireEvent.click(screen.getByText("洞察"));

    await waitFor(() => {
      expect(screen.getByText("知识库")).toBeInTheDocument();
      expect(screen.getByText("报告")).toBeInTheDocument();
      expect(screen.getByText("绩效")).toBeInTheDocument();
      expect(screen.getByText("日历")).toBeInTheDocument();
      expect(screen.getByText("预测")).toBeInTheDocument();
    });

    expect(screen.queryByText("Runtime Center")).not.toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    expect(screen.queryByText("CoPaw Console")).toBeNull();
    expect(screen.queryByText("Buddy-first runtime command center")).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
    expect(screen.queryByText("系统与健康")).toBeNull();
    expect(screen.queryByText("构建")).toBeNull();
  });

  it("opens the buddy-first chat entry instead of auto-binding an industry execution core", () => {
    render(
      <MemoryRouter>
        <Sidebar selectedKey="chat" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("聊天前台"));

    expect(navigateMock).toHaveBeenCalledWith("/chat");
  });

  it("restores the active runtime thread when re-entering chat from the sidebar", () => {
    getActiveThreadIdMock.mockReturnValue(
      "industry-chat:industry-1:execution-core",
    );

    render(
      <MemoryRouter>
        <Sidebar selectedKey="chat" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("聊天前台"));

    expect(navigateMock).toHaveBeenCalledWith(
      "/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core",
    );
  });
});
