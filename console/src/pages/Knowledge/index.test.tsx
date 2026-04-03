// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KnowledgePage from "./index";

const requestMock = vi.fn();

vi.mock("../../api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

afterEach(() => {
  cleanup();
  requestMock.mockReset();
});

function createAgentProfile(overrides: Record<string, unknown> = {}) {
  return {
    agent_id: "agent-1",
    name: "执行位甲",
    role_name: "执行位",
    role_summary: "正式职责摘要",
    agent_class: "business",
    employment_mode: "career",
    activation_mode: "persistent",
    suspendable: true,
    reports_to: null,
    mission: "负责当前执行闭环。",
    status: "active",
    risk_level: "guarded",
    current_focus_kind: "assignment",
    current_focus_id: "assignment-1",
    current_focus: "当前聚焦摘要",
    current_task_id: null,
    current_mailbox_id: null,
    queue_depth: 0,
    industry_instance_id: null,
    industry_role_id: "operator",
    resident: true,
    environment_summary: "",
    environment_constraints: [],
    evidence_expectations: [],
    today_output_summary: "",
    latest_evidence_summary: "",
    capabilities: [],
    updated_at: null,
    ...overrides,
  };
}

function mockKnowledgePageRequests() {
  requestMock.mockImplementation((url: string) => {
    if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
      return Promise.resolve([
        {
          strategy_id: "strategy-1",
          scope_type: "global",
          title: "正式战略",
          summary: "统一主链",
          mission: "维持运行一致性",
          north_star: "单一运行真相",
          thinking_axes: ["strategy"],
          delegation_policy: ["lane-first"],
          evidence_requirements: ["evidence"],
          active_goal_titles: ["旧活跃目标"],
          status: "active",
        },
      ]);
    }
    if (url === "/runtime-center/knowledge/documents") {
      return Promise.resolve([]);
    }
    if (url === "/runtime-center/knowledge") {
      return Promise.resolve([]);
    }
    if (url === "/runtime-center/knowledge/memory") {
      return Promise.resolve([]);
    }
    if (url === "/runtime-center/agents?view=business") {
      return Promise.resolve([createAgentProfile()]);
    }
    if (url === "/runtime-center/agents/agent-1") {
      return Promise.resolve({
        agent: {
          agent_id: "agent-1",
          name: "执行位甲",
        },
        mailbox: [],
        checkpoints: [],
        leases: [],
        growth: [],
      });
    }
    if (url === "/runtime-center/memory/backends") {
      return Promise.resolve([]);
    }
    if (url.startsWith("/runtime-center/memory/index?")) {
      return Promise.resolve([]);
    }
    if (url.startsWith("/runtime-center/memory/entities?")) {
      return Promise.resolve([]);
    }
    if (url.startsWith("/runtime-center/memory/opinions?")) {
      return Promise.resolve([]);
    }
    if (url.startsWith("/runtime-center/memory/reflections?")) {
      return Promise.resolve([]);
    }
    throw new Error(`Unexpected request: ${url}`);
  });
}

describe("KnowledgePage", () => {
  it("does not render legacy active goal titles in strategy cards", async () => {
    mockKnowledgePageRequests();

    render(<KnowledgePage />);

    expect(await screen.findByText("正式战略")).toBeTruthy();
    expect(screen.queryByText(/活跃目标:/)).toBeNull();
    expect(screen.queryByText("旧活跃目标")).toBeNull();
  });

  it("renders execution summaries from current_focus instead of current_goal", async () => {
    mockKnowledgePageRequests();

    render(<KnowledgePage />);

    expect(await screen.findByText("正式战略")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /执行记录/ }));

    expect(await screen.findByText("当前聚焦摘要")).toBeTruthy();
    expect(screen.queryByText("旧目标摘要")).toBeNull();
  });
});
