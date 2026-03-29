// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import { renderRuntimeDetailDrawer } from "./runtimeDetailDrawer";

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
  updated_at: "2026-03-26T08:00:00Z",
  stats: {},
  routes: {},
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

describe("runtimeDetailDrawer", () => {
  it("renders industry focus and main chain through specialized sections without jsdom pseudo-element warnings", () => {
    render(
      renderRuntimeDetailDrawer(
        {
          route: "/api/runtime-center/industry/industry-1",
          title: "Industry detail",
          payload: {
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
            ],
            current_cycle: {
              cycle_id: "cycle-1",
              cycle_kind: "weekly",
              title: "本周增长与交付协调",
              summary: "先稳交付，再补增长。",
              status: "active",
              focus_lane_ids: ["lane-growth"],
              backlog_item_ids: [],
              assignment_ids: [],
              report_ids: [],
              synthesis: {
                latest_findings: [],
                conflicts: [],
                holes: [],
                recommended_actions: [],
                needs_replan: false,
              },
            },
            assignments: [
              {
                assignment_id: "assignment-1",
                title: "Handle backlog",
                summary: "Operator-focused assignment card",
                status: "active",
                owner_agent_id: "ops-agent",
                lane_id: "lane-growth",
                cycle_id: "cycle-1",
                evidence_ids: [],
                metadata: {},
                route: "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
              } as any,
            ],
            agent_reports: [
              {
                report_id: "report-1",
                report_kind: "status",
                headline: "交付风险提醒",
                status: "recorded",
                findings: [],
                uncertainties: [],
                needs_followup: true,
                processed: false,
                evidence_ids: [],
                decision_ids: [],
                metadata: {},
                route: "/api/runtime-center/industry/industry-1?report_id=report-1",
              } as any,
            ],
            focus_selection: {
              selection_kind: "assignment",
              assignment_id: "assignment-1",
              title: "Handle backlog",
              summary: "Focused runtime subview",
              status: "active",
              route: "/api/runtime-center/industry/industry-1?assignment_id=assignment-1",
            },
            execution: {
              status: "active",
              current_focus: "Handle backlog",
              current_owner: "Execution Core",
              current_risk: "auto",
              evidence_count: 0,
              latest_evidence_summary: "",
            },
            main_chain: {
              schema_version: "industry-main-chain-v1",
              loop_state: "active",
              current_focus: "Handle backlog",
              current_owner: "Execution Core",
              current_risk: "auto",
              nodes: [],
            },
          },
        },
        false,
        null,
        vi.fn(),
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("Runtime Focus")).toBeTruthy();
    expect(screen.getByText("Main-Brain Planning")).toBeTruthy();
    expect(screen.getByText("Spider Main Chain")).toBeTruthy();
    expect(screen.getByText("Focused Assignment")).toBeTruthy();
    expect(screen.getByText("增长获客")).toBeTruthy();
    expect(screen.getByText("本周增长与交付协调")).toBeTruthy();
    expect(screen.getAllByText("Open Assignment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Open Report").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unconsumed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Needs follow-up").length).toBeGreaterThan(0);
    expect(screen.queryByText("Execution")).toBeNull();
    expect(screen.queryByText("Main Chain")).toBeNull();
  });

  it("renders host twin as a structured execution-side section", () => {
    render(
      renderRuntimeDetailDrawer(
        {
          route: "/api/runtime-center/environments/env:session:session:web:main",
          title: "Environment detail",
          payload: {
            environment_id: "env:session:session:web:main",
            host_twin: {
              projection_kind: "host_twin_projection",
              ownership: {
                seat_owner_agent_id: "ops-agent",
                handoff_owner_ref: "human-operator:alice",
                account_scope_ref: "windows:user:alice",
                workspace_scope: "project:copaw",
                active_owner_kind: "agent-with-human-handoff",
              },
              surface_mutability: {
                browser: {
                  surface_ref: "browser:web:main",
                  mutability: "blocked",
                  safe_to_mutate: false,
                  blocker_family: "modal-uac-login",
                },
              },
              continuity: {
                status: "guarded",
                valid: true,
                resume_kind: "host-companion-session",
                requires_human_return: true,
              },
              legal_recovery: {
                path: "handoff",
                checkpoint_ref: "checkpoint:captcha:jd-seller",
                verification_channel: "runtime-center-self-check",
                return_condition: "captcha-cleared",
              },
              active_blocker_families: ["modal-uac-login"],
              trusted_anchors: [
                {
                  anchor_kind: "browser-dom",
                  surface_ref: "browser:web:main",
                  anchor_ref: "#shop-header",
                  source: "browser_site_contract.last_verified_dom_anchor",
                },
              ],
              app_family_twins: {
                browser_backoffice: {
                  active: true,
                  family_kind: "browser_backoffice",
                  surface_ref: "browser:web:main",
                  contract_status: "verified-writer",
                  family_scope_ref: "site:jd:seller-center",
                },
                office_document: {
                  active: true,
                  family_kind: "office_document",
                  contract_status: "verified-writer",
                  family_scope_ref: "app:excel",
                  writer_lock_scope: "workbook:weekly-report",
                },
              },
              latest_blocking_event: {
                event_family: "modal-uac-login",
                event_name: "captcha-required",
                recommended_runtime_response: "handoff",
              },
              coordination: {
                seat_owner_ref: "ops-agent",
                workspace_owner_ref: "ops-agent",
                writer_owner_ref: "ops-agent",
                selected_seat_ref: "env:session:session:web:main",
                seat_selection_policy: "sticky-active-seat",
                recommended_scheduler_action: "handoff",
                contention_forecast: {
                  severity: "blocked",
                  reason: "captcha-required",
                },
              },
            },
            workspace_graph: {
              workspace_id: "workspace:copaw:main",
            },
          },
        },
        false,
        null,
        vi.fn(),
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("Host Twin")).toBeTruthy();
    expect(screen.getAllByText("Coordination").length).toBeGreaterThan(0);
    expect(screen.getByText("App Family Twins")).toBeTruthy();
    expect(screen.getByText("browser_backoffice")).toBeTruthy();
    expect(screen.getByText("office_document")).toBeTruthy();
    expect(screen.getByText("sticky-active-seat")).toBeTruthy();
    expect(screen.getByText("workbook:weekly-report")).toBeTruthy();
    expect(screen.getByText("human-operator:alice")).toBeTruthy();
    expect(screen.getByText("runtime-center-self-check")).toBeTruthy();
    expect(screen.getByText("#shop-header")).toBeTruthy();
    expect(screen.getAllByText("browser:web:main").length).toBeGreaterThan(0);
    expect(screen.queryByText("Projection Kind")).toBeNull();
  });
});
