// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import RuntimeExecutionStrip, { type RuntimeExecutionStripPulse } from "./RuntimeExecutionStrip";

vi.mock("../hooks/useRuntimeExecutionPulse", () => ({
  useRuntimeExecutionPulse: vi.fn(() => ({
    items: [],
    loading: false,
    error: null,
    actorBusyKey: null,
    pauseActor: vi.fn(),
    resumeActor: vi.fn(),
    cancelActor: vi.fn(),
  })),
}));

describe("RuntimeExecutionStrip", () => {
  it("adds hover titles to long line-level execution fields", () => {
    const currentGoal = "请协助完成京东后台数据调取协调，仅执行“收集/调取数据”这一动作，不做后续分析。";
    const currentWorkTitle = "京东后台数据调取协调任务正在等待浏览器与表格环境同时就绪，然后发起统一数据收集动作";
    const currentWorkSummary = "该执行位会先进入京东后台，再提取订单、商品、流量与售后相关数据，统一汇总到当前工作区。";
    const triggerReason = "环境里模型推断需显式指定模型或改用自定义提供方，因此当前任务需要先等待环境预检通过。";
    const nextStep = "等待环境修复完成后自动恢复，并继续推进数据收集动作，不触发后续分析。";
    const primaryRisk = "当前环境模型配置尚未闭合，可能导致执行位重复尝试进入环境准备阶段。";
    const latestEvidenceSummary = "最近一次证据显示浏览器会话已建立，但表格编辑器尚未取得可写上下文。";

    const pulse: RuntimeExecutionStripPulse = {
      items: [
        {
          agentId: "agent-jd",
          title: "京东执行位",
          roleName: "运营执行",
          actorClass: "execution-seat",
          runtimeStatus: "blocked",
          desiredState: "active",
          queueDepth: 1,
          currentTaskId: "task-jd",
          currentAssignmentId: "assign-jd",
          currentAssignmentStatus: "running",
          currentMailboxId: "mailbox-jd",
          currentEnvironmentId: "env-jd",
          currentGoal,
          currentWorkTitle,
          currentWorkSummary,
          executionState: "waiting-resource",
          currentStage: "collect",
          blockedReason: null,
          stuckReason: null,
          nextStep,
          triggerSource: "environment",
          triggerActor: "main-brain",
          triggerReason,
          currentOwnerName: "运营席位",
          latestEvidenceSummary,
          primaryRisk,
          latestCheckpointSummary: "等待环境预检",
          latestResultSummary: null,
          latestErrorSummary: null,
          lastHeartbeatAt: "2026-03-28T10:00:00.000Z",
          lastStartedAt: "2026-03-28T09:58:00.000Z",
          lastCheckpointId: "cp-jd",
          detailRoute: "/runtime-center/actors/agent-jd",
          signals: [
            {
              level: "watch",
              label: "等待确认",
              detail: triggerReason,
            },
          ],
          activeMailboxRoute: "/runtime-center/mailbox/mailbox-jd",
        },
      ],
      loading: false,
      error: null,
      actorBusyKey: null,
      pauseActor: vi.fn(),
      resumeActor: vi.fn(),
      cancelActor: vi.fn(),
    };

    render(
      <MemoryRouter>
        <RuntimeExecutionStrip pulse={pulse} sticky={false} />
      </MemoryRouter>,
    );

    expect(screen.getByText(currentWorkTitle)).toHaveAttribute("title", currentWorkTitle);
    expect(screen.getByText(currentWorkSummary)).toHaveAttribute("title", currentWorkSummary);
    expect(screen.getByText(`焦点：${currentGoal}`)).toHaveAttribute("title", `焦点：${currentGoal}`);
    expect(screen.getByText(`触发：${triggerReason}`)).toHaveAttribute("title", `触发：${triggerReason}`);
    expect(screen.getByText(`下一步：${nextStep}`)).toHaveAttribute("title", `下一步：${nextStep}`);
    expect(screen.getByText(`风险：${primaryRisk}`)).toHaveAttribute("title", `风险：${primaryRisk}`);
    expect(screen.getByText(`证据：${latestEvidenceSummary}`)).toHaveAttribute(
      "title",
      `证据：${latestEvidenceSummary}`,
    );
  });
});
