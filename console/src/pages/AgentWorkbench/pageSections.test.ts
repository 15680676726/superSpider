// @vitest-environment jsdom

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildGoalTaskGroups } from "./sections/taskPanels";
import { ProfileCard, TAB_KEYS } from "./pageSections";

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

describe("pageSections decomposition", () => {
  it("keeps the new canonical tabs and legacy aliases in the shared tab key set", () => {
    expect(Array.from(TAB_KEYS).sort()).toEqual([
      "daily",
      "weekly",
      "profile",
      "performance",
      "evidence",
      "workbench",
      "workspace",
      "growth",
    ].sort());
  });

  it("groups parent tasks, standalone tasks, and orphan children via the extracted task panel module", () => {
    const grouped = buildGoalTaskGroups([
      {
        task: { id: "task-parent", parent_task_id: null },
        runtime: null,
      },
      {
        task: { id: "task-child", parent_task_id: "task-parent" },
        runtime: null,
      },
      {
        task: { id: "task-standalone", parent_task_id: null },
        runtime: null,
      },
      {
        task: { id: "task-orphan", parent_task_id: "missing-parent" },
        runtime: null,
      },
    ] as any);

    expect(grouped.groups).toHaveLength(1);
    expect(grouped.groups[0].parent.task.id).toBe("task-parent");
    expect(grouped.groups[0].children.map((item) => item.task.id)).toEqual(["task-child"]);
    expect(grouped.standalone.map((item) => item.task.id)).toEqual(["task-standalone"]);
    expect(grouped.orphanChildren.map((item) => item.task.id)).toEqual(["task-orphan"]);
  });

  it("renders current focus text from current_focus without relying on current_goal", () => {
    render(
      React.createElement(ProfileCard, {
        agent: {
          agent_id: "agent-1",
          name: "Operator",
          role_name: "Ops",
          role_summary: "ops role",
          agent_class: "business",
          employment_mode: "career",
          activation_mode: "persistent",
          suspendable: true,
          reports_to: null,
          mission: "Keep runtime healthy",
          status: "active",
          risk_level: "auto",
          current_focus_kind: "goal",
          current_focus_id: "goal-focus",
          current_focus: "Focused Goal Summary",
          current_task_id: null,
          industry_instance_id: null,
          industry_role_id: null,
          environment_summary: "",
          environment_constraints: [],
          evidence_expectations: [],
          today_output_summary: "",
          latest_evidence_summary: "",
          capabilities: [],
          updated_at: null,
        },
        linkedGoal: null,
        onOpenChat: vi.fn(),
      }),
    );

    expect(screen.getByText("当前焦点:")).toBeTruthy();
    expect(screen.getByText("Focused Goal Summary")).toBeTruthy();
    expect(screen.queryByText("Legacy Goal Summary")).toBeNull();
  });
});
