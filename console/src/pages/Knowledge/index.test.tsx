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

it("renders slot preferences continuity anchors details and applied proposal truth from the memory sleep surface", async () => {
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
      return Promise.resolve(createAgentDetail("agent-1", "Execution Agent"));
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
          scope_type: "work_context",
          scope_id: "ctx-anchors",
          sleep: {
            industry_profile: {
              profile_id: "industry-profile:anchors:v2",
              industry_instance_id: "industry-anchors",
              headline: "Industry long-term memory",
              summary: "Keep the story continuity stable across rounds.",
              strategic_direction: "Protect continuity first.",
              active_constraints: ["Never break character continuity."],
              active_focuses: ["Protect continuity anchors."],
              key_entities: ["hero"],
              key_relations: ["hero follows oath"],
              evidence_refs: [],
              version: 2,
              status: "active",
              metadata: {
                last_applied_proposal_id: "structure:accepted-1",
                applied_proposal_ids: ["structure:accepted-1"],
              },
            },
            work_context_overlay: {
              overlay_id: "overlay:anchors:v3",
              work_context_id: "ctx-anchors",
              headline: "Current work memory",
              summary: "This round should preserve the hero oath and timeline order.",
              focus_summary: "Protect hero oath before the next scene.",
              active_constraints: ["Hero oath stays active."],
              active_focuses: ["Keep the next scene aligned."],
              active_entities: ["hero"],
              active_relations: ["hero -> oath"],
              evidence_refs: [],
              version: 3,
              status: "active",
              metadata: {
                continuity_anchors: [
                  "Hero oath cannot be broken before chapter ten.",
                  "Timeline stays before the market opens.",
                ],
                last_applied_proposal_id: "structure:accepted-1",
              },
            },
            slot_preferences: [
              {
                preference_id: "pref:character-state",
                industry_instance_id: "industry-anchors",
                slot_key: "character_state",
                slot_label: "Character State",
                promotion_count: 4,
                status: "active",
              },
            ],
            continuity_details: [
              {
                detail_id: "detail:hero-oath",
                scope_type: "work_context",
                scope_id: "ctx-anchors",
                detail_key: "hero_oath",
                detail_text: "Hero oath cannot be broken before chapter ten.",
                source_kind: "manual",
                pinned: true,
                status: "active",
              },
            ],
            structure_proposals: [
              {
                proposal_id: "structure:accepted-1",
                title: "Promote continuity anchors",
                summary: "Lift continuity anchors to the formal read surface.",
                recommended_action: "Keep continuity anchors at the top.",
                risk_level: "medium",
                status: "accepted",
              },
            ],
            soft_rules: [],
            conflicts: [],
          },
        }),
      );
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<KnowledgePage />);

  fireEvent.click(screen.getAllByRole("tab")[2]);

  expect(await screen.findByText("Industry long-term memory")).toBeTruthy();
  expect(screen.getByText("Character State")).toBeTruthy();
  expect(screen.getAllByText("Hero oath cannot be broken before chapter ten.").length).toBeGreaterThan(0);
  expect(screen.getByText("Timeline stays before the market opens.")).toBeTruthy();
  expect(screen.getAllByText("structure:accepted-1").length).toBeGreaterThan(0);
});

it("submits a manual pin from the memory sleep surface", async () => {
  requestMock.mockImplementation((url: string, options?: RequestInit) => {
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
      return Promise.resolve(createAgentDetail("agent-1", "Execution Agent"));
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
          scope_type: "work_context",
          scope_id: "ctx-pin",
          sleep: {
            work_context_overlay: {
              overlay_id: "overlay:ctx-pin:v1",
              work_context_id: "ctx-pin",
              headline: "Current work memory",
              summary: "Keep the stop-loss rule stable.",
              focus_summary: "Protect the risk boundary first.",
              active_constraints: ["Do not break the stop-loss rule."],
              active_focuses: ["Protect the risk boundary first."],
              active_entities: [],
              active_relations: [],
              evidence_refs: [],
              version: 1,
              status: "active",
              metadata: {},
            },
            structure_proposals: [],
            soft_rules: [],
            conflicts: [],
            continuity_details: [],
          },
        }),
      );
    }
    if (url === "/runtime-center/memory/continuity-details/pin") {
      const body = options?.body ? JSON.parse(String(options.body)) : {};
      return Promise.resolve({
        detail_id: "continuity:work_context:ctx-pin:risk-boundary",
        scope_type: "work_context",
        scope_id: "ctx-pin",
        detail_key: body.detail_key,
        detail_text: body.detail_text,
        source_kind: "manual",
        pinned: true,
        status: "active",
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<KnowledgePage />);

  fireEvent.click(screen.getAllByRole("tab")[2]);
  fireEvent.change(await screen.findByLabelText("manual-pin-key"), {
    target: { value: "risk-boundary" },
  });
  fireEvent.change(screen.getByLabelText("manual-pin-text"), {
    target: { value: "Do not average down after stop-loss." },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存手动钉住" }));

  await waitFor(() =>
    expect(requestMock).toHaveBeenCalledWith(
      "/runtime-center/memory/continuity-details/pin",
      expect.objectContaining({
        method: "POST",
      }),
    ),
  );
}, 30000);

  it("applies and rejects structure proposals from the memory sleep surface", async () => {
    const surfacePayload = createMemorySurfacePayload({
      scope_type: "work_context",
      scope_id: "ctx-1",
      sleep: {
        structure_proposals: [
          {
            proposal_id: "structure:1",
            title: "应用型提案",
            summary: "应用这个结构提案。",
            recommended_action: "提高 overlay 读取优先级。",
            risk_level: "medium",
            status: "pending",
          },
          {
            proposal_id: "structure:2",
            title: "驳回型提案",
            summary: "驳回这个结构提案。",
            recommended_action: "保持当前读层顺序。",
            risk_level: "low",
            status: "pending",
          },
        ],
        soft_rules: [],
        conflicts: [],
      },
    });

    requestMock.mockImplementation((url: string, options?: RequestInit) => {
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
        return Promise.resolve(createAgentDetail("agent-1", "Execution Agent"));
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
        return Promise.resolve(surfacePayload);
      }
      if (
        url === "/runtime-center/memory/sleep/structure-proposals/structure%3A1/apply" &&
        options?.method === "POST"
      ) {
        (surfacePayload.sleep as Record<string, unknown>).structure_proposals = [
          {
            proposal_id: "structure:1",
            title: "应用型提案",
            summary: "应用这个结构提案。",
            recommended_action: "提高 overlay 读取优先级。",
            risk_level: "medium",
            status: "accepted",
          },
          {
            proposal_id: "structure:2",
            title: "驳回型提案",
            summary: "驳回这个结构提案。",
            recommended_action: "保持当前读层顺序。",
            risk_level: "low",
            status: "pending",
          },
        ];
        return Promise.resolve({ status: "accepted" });
      }
      if (
        url === "/runtime-center/memory/sleep/structure-proposals/structure%3A2/reject" &&
        options?.method === "POST"
      ) {
        (surfacePayload.sleep as Record<string, unknown>).structure_proposals = [
          {
            proposal_id: "structure:1",
            title: "应用型提案",
            summary: "应用这个结构提案。",
            recommended_action: "提高 overlay 读取优先级。",
            risk_level: "medium",
            status: "accepted",
          },
          {
            proposal_id: "structure:2",
            title: "驳回型提案",
            summary: "驳回这个结构提案。",
            recommended_action: "保持当前读层顺序。",
            risk_level: "low",
            status: "rejected",
          },
        ];
        return Promise.resolve({ status: "rejected" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    fireEvent.click(screen.getAllByRole("tab")[2]);

    expect(await screen.findByText("应用型提案")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: "应用提案" })[0]);

    await waitFor(() => {
      expect(
        requestMock.mock.calls.some(
          ([url, options]) =>
            url === "/runtime-center/memory/sleep/structure-proposals/structure%3A1/apply" &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "驳回提案" })[0]);

    await waitFor(() => {
      expect(
        requestMock.mock.calls.some(
          ([url, options]) =>
            url === "/runtime-center/memory/sleep/structure-proposals/structure%3A2/reject" &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
    });
  }, 30000);

  it("rebuilds sleep memory and exposes version diff rollback actions", async () => {
    const surfacePayload = createMemorySurfacePayload({
      scope_type: "work_context",
      scope_id: "ctx-1",
      sleep: {
        industry_profile: {
          profile_id: "industry-profile:1",
          industry_instance_id: "industry-1",
          headline: "行业长期记忆",
          summary: "新行业摘要",
          strategic_direction: "证据先行",
          active_constraints: ["先审后动"],
          active_focuses: ["收口行业规则"],
          key_entities: [],
          key_relations: [],
          evidence_refs: [],
          version: 3,
          status: "active",
        },
        work_context_overlay: {
          overlay_id: "overlay:1",
          work_context_id: "ctx-1",
          headline: "工作记忆 overlay",
          summary: "当前工作上下文摘要",
          focus_summary: "新聚焦",
          active_constraints: ["当前约束"],
          active_focuses: ["当前焦点"],
          active_entities: [],
          active_relations: [],
          evidence_refs: [],
          version: 4,
          status: "active",
        },
        structure_proposals: [],
        soft_rules: [],
        conflicts: [],
      },
    });

    requestMock.mockImplementation((url: string, options?: RequestInit) => {
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
        return Promise.resolve(createAgentDetail("agent-1", "Execution Agent"));
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
        return Promise.resolve(surfacePayload);
      }
      if (url === "/runtime-center/memory/sleep/rebuild" && options?.method === "POST") {
        return Promise.resolve({
          scope_type: "work_context",
          scope_id: "ctx-1",
          sleep_job: { status: "completed", trigger_kind: "manual" },
        });
      }
      if (
        url ===
        "/runtime-center/memory/sleep/industry-profiles/industry-1/diff?from_version=2&to_version=3"
      ) {
        return Promise.resolve({
          changes: [{ field: "summary", from: "旧行业摘要", to: "新行业摘要" }],
          from_version: 2,
          to_version: 3,
        });
      }
      if (
        url === "/runtime-center/memory/sleep/industry-profiles/industry-1/rollback" &&
        options?.method === "POST"
      ) {
        const currentIndustryProfile =
          ((surfacePayload.sleep as Record<string, unknown>).industry_profile as
            | Record<string, unknown>
            | undefined) || {};
        (surfacePayload.sleep as Record<string, unknown>).industry_profile = {
          ...currentIndustryProfile,
          version: 4,
          summary: "旧行业摘要",
        };
        return Promise.resolve({ status: "active", version: 4 });
      }
      if (
        url ===
        "/runtime-center/memory/sleep/work-context-overlays/ctx-1/diff?from_version=3&to_version=4"
      ) {
        return Promise.resolve({
          changes: [{ field: "focus_summary", from: "旧聚焦", to: "新聚焦" }],
          from_version: 3,
          to_version: 4,
        });
      }
      if (
        url === "/runtime-center/memory/sleep/work-context-overlays/ctx-1/rollback" &&
        options?.method === "POST"
      ) {
        const currentWorkContextOverlay =
          ((surfacePayload.sleep as Record<string, unknown>).work_context_overlay as
            | Record<string, unknown>
            | undefined) || {};
        (surfacePayload.sleep as Record<string, unknown>).work_context_overlay = {
          ...currentWorkContextOverlay,
          version: 5,
          focus_summary: "旧聚焦",
        };
        return Promise.resolve({ status: "active", version: 5 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    fireEvent.click(screen.getAllByRole("tab")[2]);

    expect(await screen.findByText("行业长期记忆")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "重建睡眠记忆" }));
    fireEvent.click(screen.getByRole("button", { name: "查看行业差异" }));
    fireEvent.click(screen.getByRole("button", { name: "回滚行业版本" }));
    fireEvent.click(screen.getByRole("button", { name: "查看上下文差异" }));
    fireEvent.click(screen.getByRole("button", { name: "回滚上下文版本" }));

    await waitFor(() => {
      expect(
        requestMock.mock.calls.some(
          ([url, options]) =>
            url === "/runtime-center/memory/sleep/rebuild" &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
      expect(
        requestMock.mock.calls.some(
          ([url]) =>
            url ===
            "/runtime-center/memory/sleep/industry-profiles/industry-1/diff?from_version=2&to_version=3",
        ),
      ).toBe(true);
      expect(
        requestMock.mock.calls.some(
          ([url, options]) =>
            url === "/runtime-center/memory/sleep/industry-profiles/industry-1/rollback" &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
      expect(
        requestMock.mock.calls.some(
          ([url]) =>
            url ===
            "/runtime-center/memory/sleep/work-context-overlays/ctx-1/diff?from_version=3&to_version=4",
        ),
      ).toBe(true);
      expect(
        requestMock.mock.calls.some(
          ([url, options]) =>
            url === "/runtime-center/memory/sleep/work-context-overlays/ctx-1/rollback" &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
    });
  }, 30000);
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

  it("renders industry profile, work overlay, and structure proposals from the memory sleep surface", async () => {
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
        return Promise.resolve(createAgentDetail("agent-1", "Execution Agent"));
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
            scope_type: "work_context",
            scope_id: "ctx-1",
            sleep: {
              digest: {
                headline: "工作记忆摘要",
                summary: "当前工作上下文正在处理财务复核和外呼审批。",
                current_constraints: ["外呼审批必须先完成财务复核。"],
                current_focus: ["先完成财务复核，再处理审批。"],
                top_entities: ["外呼审批", "财务复核"],
                top_relations: ["外呼审批依赖财务复核"],
                evidence_refs: ["evidence:1"],
              },
              industry_profile: {
                profile_id: "industry-profile:1",
                industry_instance_id: "industry-1",
                headline: "行业长期记忆",
                summary: "行业长期基线强调先证据后动作。",
                strategic_direction: "证据先行",
                active_constraints: ["外呼审批必须先完成财务复核。"],
                active_focuses: ["收口共享行业规则"],
                key_entities: ["外呼审批"],
                key_relations: ["外呼审批依赖财务复核"],
                evidence_refs: ["evidence:1"],
              },
              work_context_overlay: {
                overlay_id: "overlay:1",
                work_context_id: "ctx-1",
                headline: "工作记忆 overlay",
                summary: "当前上下文明确承接行业长期规则。",
                focus_summary: "先完成财务复核，再处理外呼审批",
                active_constraints: ["当前工作上下文继承行业复核规则"],
                active_focuses: ["财务复核", "外呼审批"],
                active_entities: ["跟进线程"],
                active_relations: ["跟进线程依赖审批门"],
                evidence_refs: ["evidence:1"],
              },
              structure_proposals: [
                {
                  proposal_id: "structure:1",
                  title: "把财务复核提升为工作记忆首条",
                  summary: "建议只调整 overlay 的默认读顺序。",
                  recommended_action: "保持事实不变，只调整 overlay 的默认读顺序。",
                  risk_level: "medium",
                  status: "pending",
                },
              ],
              soft_rules: [],
              conflicts: [],
            },
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<KnowledgePage />);

    fireEvent.click(await screen.findByRole("tab", { name: /检索与反思/ }));

    await waitFor(() => {
      expect(screen.getByText("行业长期记忆")).toBeTruthy();
    });
    expect(screen.getByText("工作记忆 overlay")).toBeTruthy();
    expect(screen.getByText("把财务复核提升为工作记忆首条")).toBeTruthy();
  });
});
