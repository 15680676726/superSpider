// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KnowledgePage, {
  MEMORY_SCOPE_OPTIONS,
  buildMemoryScopeSearch,
} from "./index";

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
    name: "Execution Agent",
    role_name: "Operator",
    role_summary: "Formal role summary",
    agent_class: "business",
    employment_mode: "career",
    activation_mode: "persistent",
    suspendable: true,
    reports_to: null,
    mission: "Handle the current execution loop.",
    status: "active",
    risk_level: "guarded",
    current_focus_kind: "assignment",
    current_focus_id: "assignment-1",
    current_focus: "Current focus summary",
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

function createStrategyPayload(overrides: Record<string, unknown> = {}) {
  return {
    strategy_id: "strategy-1",
    scope_type: "global",
    title: "Formal strategy",
    summary: "Unified runtime truth",
    mission: "Keep execution aligned",
    north_star: "Single runtime truth",
    thinking_axes: ["strategy"],
    delegation_policy: ["lane-first"],
    evidence_requirements: ["evidence"],
    active_goal_titles: ["legacy goal title"],
    status: "active",
    ...overrides,
  };
}

function createMemorySurfacePayload(overrides: Record<string, unknown> = {}) {
  return {
    scope_type: "global",
    scope_id: "runtime",
    query: null,
    activation: null,
    sleep: {},
    relation_count: 0,
    relation_kind_counts: {},
    relations: [],
    ...overrides,
  };
}

function createAgentDetail(
  agentId: string,
  agentName: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    agent: {
      agent_id: agentId,
      name: agentName,
    },
    mailbox: [],
    checkpoints: [],
    leases: [],
    growth: [],
    ...overrides,
  };
}

function createDeferredPromise<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function mockKnowledgePageRequests() {
  requestMock.mockImplementation((url: string) => {
    if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
      return Promise.resolve([createStrategyPayload()]);
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
          name: "Execution Agent",
        },
        mailbox: [],
        checkpoints: [],
        leases: [],
        growth: [],
      });
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
    if (url.startsWith("/runtime-center/memory/surface?")) {
      return Promise.resolve(createMemorySurfacePayload());
    }
    throw new Error(`Unexpected request: ${url}`);
  });
}

describe("KnowledgePage", () => {
  it("does not request memory workspace before the main page payload resolves", async () => {
    let resolveStrategies!: (value: unknown) => void;
    let resolveDocuments!: (value: unknown) => void;
    let resolveChunks!: (value: unknown) => void;
    let resolveKnowledgeMemory!: (value: unknown) => void;
    let resolveAgents!: (value: unknown) => void;

    requestMock.mockImplementation((url: string) => {
      if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
        return new Promise((resolve) => {
          resolveStrategies = resolve;
        });
      }
      if (url === "/runtime-center/knowledge/documents") {
        return new Promise((resolve) => {
          resolveDocuments = resolve;
        });
      }
      if (url === "/runtime-center/knowledge") {
        return new Promise((resolve) => {
          resolveChunks = resolve;
        });
      }
      if (url === "/runtime-center/knowledge/memory") {
        return new Promise((resolve) => {
          resolveKnowledgeMemory = resolve;
        });
      }
      if (url === "/runtime-center/agents?view=business") {
        return new Promise((resolve) => {
          resolveAgents = resolve;
        });
      }
      if (url === "/runtime-center/agents/agent-1") {
        return Promise.resolve({
          agent: {
            agent_id: "agent-1",
            name: "Execution Agent",
          },
          mailbox: [],
          checkpoints: [],
          leases: [],
          growth: [],
        });
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
      if (url.startsWith("/runtime-center/memory/surface?")) {
        return Promise.resolve(createMemorySurfacePayload());
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    expect(requestMock).toHaveBeenCalledWith(
      "/runtime-center/strategy-memory?status=active&limit=20",
    );
    expect(
      requestMock.mock.calls.some(
        ([url]) =>
          typeof url === "string" && url.startsWith("/runtime-center/memory/"),
      ),
    ).toBe(false);

    resolveStrategies([createStrategyPayload()]);
    resolveDocuments([]);
    resolveChunks([]);
    resolveKnowledgeMemory([]);
    resolveAgents([createAgentProfile()]);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();
    expect(requestMock).not.toHaveBeenCalledWith("/runtime-center/memory/backends");
    expect(
      requestMock.mock.calls.some(
        ([url]) =>
          typeof url === "string" &&
          url.startsWith("/runtime-center/memory/surface?"),
      ),
    ).toBe(true);
  });

  it("does not render legacy active goal titles in strategy cards", async () => {
    mockKnowledgePageRequests();

    render(<KnowledgePage />);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();
    expect(screen.queryByText(/active goal/i)).toBeNull();
    expect(screen.queryByText("legacy goal title")).toBeNull();
  });

  it("renders execution summaries from current_focus instead of current_goal", async () => {
    mockKnowledgePageRequests();

    render(<KnowledgePage />);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("tab")[3]);

    expect(await screen.findByText("Current focus summary")).toBeTruthy();
    expect(screen.queryByText("legacy goal summary")).toBeNull();
  });

  it("renders dedicated activation relation surface from aggregated memory route", async () => {
    requestMock.mockImplementation((url: string) => {
      if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
        return Promise.resolve([createStrategyPayload()]);
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
            name: "Execution Agent",
          },
          mailbox: [],
          checkpoints: [],
          leases: [],
          growth: [],
        });
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
      if (url.startsWith("/runtime-center/memory/surface?")) {
        return Promise.resolve(
          createMemorySurfacePayload({
            activation: {
              scope_type: "global",
              scope_id: "runtime",
              activated_count: 2,
              contradiction_count: 0,
              top_entities: ["approval", "finance"],
              top_opinions: ["approval:requirement:must"],
              top_relations: ["Approval supports finance review"],
              top_relation_kinds: ["supports"],
              top_constraints: ["Approval needs evidence review"],
              top_next_actions: ["Collect finance evidence"],
              support_refs: ["fact:approval"],
              top_evidence_refs: ["fact:approval"],
              evidence_refs: ["fact:approval"],
              strategy_refs: ["strategy-1"],
            },
            relation_count: 1,
            relation_kind_counts: {
              supports: 1,
            },
            relations: [
              {
                relation_id: "rel:approval->finance",
                source_node_id: "fact:approval",
                target_node_id: "entity:finance",
                relation_kind: "supports",
                scope_type: "global",
                scope_id: "runtime",
                summary: "Approval supports finance review.",
                confidence: 0.91,
                source_refs: ["fact:approval"],
                metadata: {
                  reason: "queue ownership",
                },
              },
            ],
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("tab")[2]);

    expect(await screen.findByText("Approval supports finance review.")).toBeTruthy();
    expect(screen.getByText("Approval needs evidence review")).toBeTruthy();
    expect(
      requestMock.mock.calls.some(
        ([url]) =>
          typeof url === "string" &&
          url.startsWith("/runtime-center/memory/surface?") &&
          url.includes("relation_limit=12"),
      ),
    ).toBe(true);
  });

  it("renders sleep digest, focus, rules, and pending conflicts from aggregated memory route", async () => {
    requestMock.mockImplementation((url: string) => {
      if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
        return Promise.resolve([createStrategyPayload()]);
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
            name: "Execution Agent",
          },
          mailbox: [],
          checkpoints: [],
          leases: [],
          growth: [],
        });
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
      if (url.startsWith("/runtime-center/memory/surface?")) {
        return Promise.resolve(
          createMemorySurfacePayload({
            sleep: {
              digest: {
                headline: "Finance review digest",
                summary: "Outbound approval should wait for finance review before release.",
                current_constraints: [
                  "Outbound approval must wait for finance review.",
                ],
                current_focus: ["Clear the finance review gate."],
                top_entities: ["approval", "finance"],
                top_relations: ["Approval supports finance review."],
                evidence_refs: ["fact:approval"],
              },
              aliases: [],
              merges: [],
              soft_rules: [
                {
                  rule_id: "rule:finance-review",
                  rule_text: "Wait for finance review before outbound approval.",
                  rule_kind: "requirement",
                  state: "active",
                  risk_level: "low",
                  hit_count: 3,
                  conflict_count: 0,
                  day_span: 2,
                  evidence_refs: ["fact:approval"],
                },
              ],
              conflicts: [
                {
                  proposal_id: "proposal:legacy-shortcut",
                  title: "Legacy shortcut conflicts",
                  summary:
                    "A legacy note says approval can happen before finance review.",
                  recommended_action: "Keep finance review as the active rule.",
                  risk_level: "high",
                  status: "pending",
                  conflicting_refs: ["fact:legacy"],
                  supporting_refs: ["fact:approval"],
                },
              ],
            },
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("tab")[2]);

    expect((await screen.findAllByText("Finance review digest")).length).toBeGreaterThan(0);
    expect(screen.getByText("Clear the finance review gate.")).toBeTruthy();
    expect(
      screen.getByText("Wait for finance review before outbound approval."),
    ).toBeTruthy();
    expect(screen.getByText("Legacy shortcut conflicts")).toBeTruthy();
    expect(
      screen.getByText(
        "A legacy note says approval can happen before finance review.",
      ),
    ).toBeTruthy();
  });

  it("supports work_context scope in the memory workspace query chain", async () => {
    const { scopeId, search } = buildMemoryScopeSearch("work_context", "wc-123");

    expect(scopeId).toBe("wc-123");
    expect(search.get("scope_type")).toBe("work_context");
    expect(search.get("scope_id")).toBe("wc-123");
    expect(search.get("work_context_id")).toBe("wc-123");
  });

  it("exposes work_context in the shared memory scope options", () => {
    expect(MEMORY_SCOPE_OPTIONS).toEqual(
      expect.arrayContaining([
        { label: "全局", value: "global" },
        { label: "行业", value: "industry" },
        { label: "执行位", value: "agent" },
        { label: "任务", value: "task" },
        { label: "工作上下文", value: "work_context" },
      ]),
    );
  });

  it("does not let a stale agent detail request override the current selection", async () => {
    const detailA = createDeferredPromise<ReturnType<typeof createAgentDetail>>();
    const detailB = createDeferredPromise<ReturnType<typeof createAgentDetail>>();

    requestMock.mockImplementation((url: string) => {
      if (url === "/runtime-center/strategy-memory?status=active&limit=20") {
        return Promise.resolve([createStrategyPayload()]);
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
        return Promise.resolve([
          createAgentProfile({
            agent_id: "agent-a",
            name: "Agent A",
            role_name: "Planner",
            role_summary: "Agent A summary",
          }),
          createAgentProfile({
            agent_id: "agent-b",
            name: "Agent B",
            role_name: "Operator",
            role_summary: "Agent B summary",
          }),
        ]);
      }
      if (url === "/runtime-center/agents/agent-a") {
        return detailA.promise;
      }
      if (url === "/runtime-center/agents/agent-b") {
        return detailB.promise;
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
      if (url.startsWith("/runtime-center/memory/surface?")) {
        return Promise.resolve(createMemorySurfacePayload());
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    expect(await screen.findByText("Formal strategy")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: /执行记录/ }));
    fireEvent.click(await screen.findByText("Agent B"));

    await waitFor(() => {
      expect(
        requestMock.mock.calls.some(
          ([url]) => url === "/runtime-center/agents/agent-b",
        ),
      ).toBe(true);
    });

    await act(async () => {
      detailB.resolve(
        createAgentDetail("agent-b", "Agent B", {
          mailbox: [{ title: "B mailbox", status: "open" }],
        }),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText(/B mailbox/)).toBeTruthy();

    await act(async () => {
      detailA.resolve(
        createAgentDetail("agent-a", "Agent A", {
          mailbox: [{ title: "A mailbox", status: "open" }],
        }),
      );
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.getByText(/B mailbox/)).toBeTruthy();
      expect(screen.queryByText(/A mailbox/)).toBeNull();
    });
  });
});
