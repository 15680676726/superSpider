// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
import {
  buildRuntimeEnvironmentCockpitSignals,
} from "./runtimeEnvironmentSections";
import { buildRuntimeIndustryCockpitSignals } from "./runtimeIndustrySections";
import {
  renderIndustryExecutionFocusSection,
  runtimeEntryPrimaryLabel,
} from "./viewHelpers";

const baseDetail = {
  instance_id: "industry-1",
  bootstrap_kind: "industry-v1",
  label: "Demo Industry",
  summary: "Demo",
  owner_scope: "operator",
  profile: {
    schema_version: "industry-profile-v1",
    industry: "demo",
    target_customers: [],
    channels: [],
    goals: [],
    constraints: [],
    experience_mode: "operator-guided",
    operator_requirements: [],
  },
  team: {
    schema_version: "industry-team-blueprint-v1",
    team_id: "team-1",
    label: "Demo Team",
    summary: "Demo Team",
    agents: [],
  },
  status: "active",
  autonomy_status: null,
  lifecycle_status: null,
  updated_at: "2026-03-26T08:00:00Z",
  stats: {},
  routes: {},
  execution: null,
  main_chain: null,
  focus_selection: null,
  strategy_memory: null,
  execution_core_identity: null,
  goals: [],
  agents: [],
  schedules: [],
  lanes: [],
  backlog: [],
  staffing: {
    pending_proposals: [],
    temporary_seats: [],
  },
  current_cycle: null,
  cycles: [],
  assignments: [],
  agent_reports: [],
  tasks: [],
  decisions: [],
  evidence: [],
  patches: [],
  growth: [],
  proposals: [],
  reports: {
    daily: {
      window: "daily",
      since: "2026-03-26T00:00:00Z",
      until: "2026-03-26T23:59:59Z",
      evidence_count: 0,
      proposal_count: 0,
      patch_count: 0,
      applied_patch_count: 0,
      growth_count: 0,
      decision_count: 0,
      recent_evidence: [],
      highlights: [],
    },
    weekly: {
      window: "weekly",
      since: "2026-03-20T00:00:00Z",
      until: "2026-03-26T23:59:59Z",
      evidence_count: 0,
      proposal_count: 0,
      patch_count: 0,
      applied_patch_count: 0,
      growth_count: 0,
      decision_count: 0,
      recent_evidence: [],
      highlights: [],
    },
  },
  media_analyses: [],
} as IndustryInstanceDetail;

describe("runtimeCenter viewHelpers", () => {
  it("prefers executor runtime ids over legacy entry titles", () => {
    expect(
      runtimeEntryPrimaryLabel({
        id: "runtime-1",
        title: "Legacy external runtime",
        kind: "executor-runtime",
        status: "ready",
        summary: null,
        updated_at: null,
        route: null,
        actions: {},
        meta: {
          executor_id: "codex",
          provider_id: "codex-app-server",
        },
      }),
    ).toBe("codex");
  });

  it("labels the runtime focus card as current focus instead of current goal", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_focus: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "auto",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("当前焦点")).toBeTruthy();
    expect(screen.queryByText("当前目标")).toBeNull();
  });

  it("uses no active focus as the empty-state copy", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "idle",
            current_focus: "",
            current_owner: "Execution Core",
            current_risk: "unknown",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("暂无活动焦点")).toBeTruthy();
    expect(screen.queryByText("暂无活动目标")).toBeNull();
  });

  it("localizes fallback owner, risk scope, and evidence copy for ordinary users", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          owner_scope: "operator",
          execution: {
            status: "idle",
            current_focus: "",
            current_owner: "",
            current_risk: "unknown",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
          main_chain: null,
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("主脑执行核心")).toBeTruthy();
    expect(screen.getAllByText("未知").length).toBeGreaterThan(0);
    expect(screen.getByText("还没有写入证据")).toBeTruthy();
    expect(screen.getByText("循环 待命 · 范围 操作员")).toBeTruthy();
    expect(screen.queryByText("Execution core")).toBeNull();
    expect(screen.queryByText("No evidence written yet")).toBeNull();
  });

  it("renders shared risk labels instead of raw runtime risk tokens", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_focus: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "guarded",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getAllByText("守护").length).toBeGreaterThan(0);
    expect(screen.queryByText("guarded")).toBeNull();
  });

  it("uses the shared runtime status color tags for execution focus", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_focus: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "auto",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(
      screen
        .getAllByText("自治运行中")
        .some((node) => node.className.includes("ant-tag-green")),
    ).toBe(true);
  });
  it("opens the current focus card through the live assignment route instead of the legacy goal route", () => {
    const openRoute = vi.fn();

    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          goals: [
            {
              goal_id: "goal-legacy",
              kind: "legacy",
              title: "Legacy Goal",
              summary: "Legacy goal summary",
              plan_steps: [],
              status: "active",
              priority: 1,
              owner_scope: null,
              owner_agent_id: "agent-legacy",
              role_id: "role-legacy",
              route: "/api/runtime-center/goals/goal-legacy",
              task_count: 0,
              decision_count: 0,
              evidence_count: 0,
            },
          ],
          execution: {
            status: "active",
            current_focus_id: "assignment-1",
            current_focus: null,
            current_owner: "Execution Core",
            current_risk: "auto",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
          main_chain: {
            schema_version: "industry-main-chain-v1",
            loop_state: "active",
            current_focus_id: "assignment-1",
            current_focus: null,
            current_owner_agent_id: null,
            current_owner: "Execution Core",
            current_risk: "auto",
            latest_evidence_summary: "",
            nodes: [
              {
                node_id: "assignment",
                label: "Assignment",
                status: "active",
                truth_source: "AssignmentRecord",
                current_ref: "assignment-1",
                route: "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
                summary: "Live Assignment Title",
                backflow_port: "AssignmentService.reconcile_assignments()",
                metrics: {},
              },
              {
                node_id: "backlog",
                label: "Backlog",
                status: "materialized",
                truth_source: "BacklogItemRecord",
                current_ref: "backlog-1",
                route: "/api/runtime-center/industry/industry-1?backlog_item_id=backlog-1",
                summary: "Live Backlog Title",
                backflow_port: "BacklogService.record_chat_writeback()",
                metrics: {},
              },
            ],
          },
        },
        openRoute,
      ) as React.ReactElement,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开详情" }));

    expect(openRoute).toHaveBeenCalledWith(
      "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
      "Live 派工 Title",
    );
    expect(openRoute).not.toHaveBeenCalledWith(
      "/api/runtime-center/goals/goal-legacy",
      expect.anything(),
    );
  });

  it("surfaces main-brain planning with lanes, cycle, assignments, and reports", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          lanes: [
            {
              lane_id: "lane-growth",
              lane_key: "growth",
              title: "增长获客",
              summary: "推进新增获客。",
              status: "active",
              priority: 3,
              metadata: {},
            },
            {
              lane_id: "lane-fulfillment",
              lane_key: "fulfillment",
              title: "交付履约",
              summary: "盯住本周交付节奏。",
              status: "queued",
              priority: 2,
              metadata: {},
            },
          ],
          current_cycle: {
            cycle_id: "cycle-1",
            cycle_kind: "weekly",
            title: "本周增长与交付协调",
            summary: "先稳交付，再补增长。",
            status: "active",
            focus_lane_ids: ["lane-growth"],
            goal_ids: [],
            backlog_item_ids: ["backlog-1"],
            assignment_ids: ["assignment-1"],
            report_ids: ["report-1"],
            metadata: {},
            synthesis: {
              latest_findings: [
                {
                  report_id: "report-1",
                  headline: "交付风险提醒",
                  summary: "Need follow-up from the main brain.",
                  findings: [],
                  uncertainties: [],
                  needs_followup: true,
                  followup_reason: "Awaiting explicit approval",
                },
              ],
              conflicts: [],
              holes: [
                {
                  hole_id: "hole-1",
                  kind: "follow-up",
                  summary: "Weekend variance still lacks a validated cause.",
                },
              ],
              recommended_actions: [
                {
                  action_id: "action-1",
                  action_type: "staffing-follow-up",
                  title: "Approve closer staffing",
                  summary: "Approve closer seating for live follow-up.",
                },
              ],
              needs_replan: true,
              control_core_contract: ["synthesize-before-reassign"],
            },
          },
          assignments: [
            {
              assignment_id: "assignment-1",
              title: "跟进重点线索",
              status: "active",
              evidence_ids: [],
              metadata: {},
            },
          ],
          agent_reports: [
            {
              report_id: "report-1",
              headline: "交付风险提醒",
              report_kind: "status",
              status: "recorded",
              findings: [],
              uncertainties: [],
              needs_followup: true,
              processed: false,
              evidence_ids: [],
              decision_ids: [],
              metadata: {},
            },
          ],
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getAllByText("主脑规划").length).toBeGreaterThan(0);
    expect(screen.getByText("增长获客")).toBeTruthy();
    expect(screen.getByText("交付履约")).toBeTruthy();
    expect(screen.getByText("本周增长与交付协调")).toBeTruthy();
    expect(screen.getByText("派工 1")).toBeTruthy();
    expect(screen.getByText("汇报 1")).toBeTruthy();
    expect(screen.getAllByText("等待明确批准").length).toBeGreaterThan(0);
    expect(screen.getByText("批准补充岗位编制")).toBeTruthy();
    expect(screen.getByText("控制合同")).toBeTruthy();
    expect(screen.getByText("synthesize-before-reassign")).toBeTruthy();
  });

  it("labels pending researcher followups as main-brain review items", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          staffing: {
            pending_proposals: [],
            temporary_seats: [],
            researcher: {
              role_id: "researcher",
              role_name: "Researcher",
              agent_id: "industry-researcher-demo",
              status: "waiting-review",
              pending_signal_count: 2,
              waiting_for_main_brain: true,
              current_assignment: {
                assignment_id: "assignment-researcher",
                title: "Weekly signal scan",
                status: "active",
              },
              latest_report: {
                report_id: "report-researcher",
                headline: "Signal summary ready",
                status: "recorded",
              },
            },
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("待主脑处理研究汇报 2")).toBeTruthy();
    expect(screen.queryByText("待处理信号 2")).toBeNull();
  });

  it("prefers the dedicated main-brain overview card when building cockpit signals", () => {
    const payload = {
      generated_at: "2026-03-29T09:00:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service,governance_service",
        note: "Shared runtime surface",
        services: ["state_query_service", "governance_service"],
      },
      cards: [
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "Main brain cockpit",
          entries: [],
          meta: {
            carrier: {
              status: "state-service",
              summary: "Carrier ready",
              route: "/api/runtime-center/governance/status",
            },
            strategy: {
              summary: "North star: weekly alignment",
            },
            lanes: {
              count: 4,
              summary: "4 lanes active",
            },
            backlog: {
              count: 7,
              summary: "7 backlog items",
              route: "/api/runtime-center/industry/industry-1?backlog_item_id=backlog-1",
            },
            current_cycle: {
              title: "Cycle 12",
              summary: "Weekly cadence",
              status: "active",
              route: "/api/runtime-center/industry/industry-1?cycle_id=cycle-12",
            },
            assignments: {
              count: 3,
              summary: "3 active assignments",
              route: "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
            },
            agent_reports: {
              count: 2,
              summary: "2 agent reports",
              route: "/api/runtime-center/industry/industry-1?report_id=report-1",
            },
            evidence: {
              count: 5,
              summary: "5 evidence records",
              route: "/api/runtime-center/evidence/evidence-5",
            },
            decisions: {
              count: 1,
              summary: "1 decision pending",
              route: "/api/runtime-center/decisions/decision-1",
            },
            patches: {
              count: 2,
              summary: "2 patches pending",
              route: "/api/runtime-center/patches/patch-2",
            },
            environment: {
              summary: "Host twin ready",
              detail: "Workspace bound",
              route: "/api/runtime-center/governance/status",
            },
          },
        },
      ],
    } as RuntimeCenterOverviewPayload;

    const industrySignals = buildRuntimeIndustryCockpitSignals(payload);
    const environmentSignals = buildRuntimeEnvironmentCockpitSignals(payload);

    expect(industrySignals.find((signal) => signal.key === "strategy")?.value).toBe(
      "北极星：周节奏对齐",
    );
    expect(industrySignals.find((signal) => signal.key === "lanes")?.value).toBe("4");
    expect(industrySignals.find((signal) => signal.key === "backlog")?.value).toBe("7");
    expect(industrySignals.find((signal) => signal.key === "current_cycle")?.value).toBe(
      "周期 12",
    );
    expect(industrySignals.find((signal) => signal.key === "assignments")?.value).toBe("3");
    expect(industrySignals.find((signal) => signal.key === "assignments")?.route).toBe(
      "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
    );
    expect(industrySignals.find((signal) => signal.key === "agent_reports")?.value).toBe(
      "2",
    );
    expect(industrySignals.find((signal) => signal.key === "agent_reports")?.route).toBe(
      "/api/runtime-center/industry/industry-1?report_id=report-1",
    );
    expect(industrySignals.find((signal) => signal.key === "evidence")?.value).toBe("5");
    expect(industrySignals.find((signal) => signal.key === "evidence")?.route).toBe(
      "/api/runtime-center/evidence/evidence-5",
    );
    expect(industrySignals.find((signal) => signal.key === "decisions")?.value).toBe("1");
    expect(industrySignals.find((signal) => signal.key === "decisions")?.route).toBe(
      "/api/runtime-center/decisions/decision-1",
    );
    expect(industrySignals.find((signal) => signal.key === "patches")?.value).toBe("2");
    expect(industrySignals.find((signal) => signal.key === "patches")?.route).toBe(
      "/api/runtime-center/patches/patch-2",
    );

    expect(environmentSignals.find((signal) => signal.key === "carrier")?.route).toBe(
      "/api/runtime-center/governance/status",
    );
    expect(environmentSignals.find((signal) => signal.key === "environment")?.detail).toBe(
      "工作区已绑定",
    );
  });

  it("marks the environment as unavailable when no backing truth is exposed", () => {
    const payload = {
      generated_at: "2026-03-29T09:00:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service",
        note: "Shared runtime surface",
        services: ["state_query_service"],
      },
      cards: [
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "Main brain cockpit",
          entries: [],
          meta: {
            carrier: {
              status: "state-service",
              summary: "Carrier ready",
              route: "/api/runtime-center/governance/status",
            },
          },
        },
        {
          key: "governance",
          title: "Governance",
          source: "governance_service",
          status: "idle",
          count: 0,
          summary: null,
          entries: [],
          meta: {},
        },
      ],
    } as RuntimeCenterOverviewPayload;

    const environmentSignal = buildRuntimeEnvironmentCockpitSignals(payload).find(
      (signal) => signal.key === "environment",
    );

    expect(environmentSignal?.value).toBe("环境待接线");
    expect(environmentSignal?.detail).toBe("还没有可验证的环境连续性或宿主绑定信息。");
    expect(environmentSignal?.tone).toBe("warning");
  });
  it("renders human-readable weixin ilink runtime status instead of raw internal keys", () => {
    const payload = {
      generated_at: "2026-04-17T09:00:00Z",
      surface: {
        version: "runtime-center-v1",
        mode: "operator-surface",
        status: "state-service",
        read_only: true,
        source: "state_query_service,governance_service",
        note: "Shared runtime surface",
        services: ["state_query_service", "governance_service"],
      },
      cards: [
        {
          key: "main-brain",
          title: "Main-Brain",
          source: "state_query_service",
          status: "state-service",
          count: 1,
          summary: "Main brain cockpit",
          entries: [],
          meta: {
            carrier: {
              status: "state-service",
              summary: "Carrier ready",
              route: "/api/runtime-center/governance/status",
            },
            environment: {
              summary: "Host twin ready",
              detail: "Workspace bound",
              route: "/api/runtime-center/governance/status",
            },
          },
        },
        {
          key: "governance",
          title: "Governance",
          source: "governance_service",
          status: "state-service",
          count: 1,
          summary: "Runtime is accepting new work.",
          entries: [],
          meta: {
            channel_runtime_summary: {
              channel: "weixin_ilink",
              title: "微信个人（iLink）",
              login_status: "waiting_scan",
              polling_status: "stopped",
              summary: "微信个人（iLink）等待扫码；轮询未运行。",
              route: "/api/runtime-center/channel-runtimes/weixin_ilink",
            },
          },
        },
      ],
    } as RuntimeCenterOverviewPayload;

    const environmentSignal = buildRuntimeEnvironmentCockpitSignals(payload).find(
      (signal) => signal.key === "environment",
    );

    expect(environmentSignal?.detail).toContain("微信个人（iLink）等待扫码");
    expect(environmentSignal?.detail).toContain("轮询未运行");
    expect(environmentSignal?.detail).not.toContain("waiting_scan");
    expect(environmentSignal?.detail).not.toContain("stopped");
  });
});
