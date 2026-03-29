// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { agentWorkbenchText, runtimeCenterText } from "./copy";
import { ActorRuntimePanel } from "./sections/runtimePanels";

describe("runtimePanels", () => {
  it("renders the extracted actor runtime panel through the section module", () => {
    const pauseLabelPattern = new RegExp(
      runtimeCenterText.actionPause.split("").join("\\s*"),
    );
    const resumeLabelPattern = new RegExp(
      runtimeCenterText.actionResume.split("").join("\\s*"),
    );

    render(
      <ActorRuntimePanel
        actorActionKey={null}
        detail={{
          agent: {
            agent_id: "agent-1",
            current_task_id: "task-1",
          },
          runtime: {
            runtime_status: "running",
            desired_state: "active",
            queue_depth: 1,
            current_task_id: "task-1",
            current_mailbox_id: "mailbox-1",
            current_environment_id: "env-1",
            last_checkpoint_id: "checkpoint-1",
          },
          goals: [],
          tasks: [],
          mailbox: [],
          checkpoints: [],
          leases: [],
          thread_bindings: [],
          teammates: [],
          latest_collaboration: [],
          decisions: [],
          evidence: [],
          patches: [],
          growth: [],
          environments: [],
          workspace: {
            current_environment_id: null,
            current_environment_ref: null,
            current_environment: null,
            files_supported: false,
          },
          stats: {
            task_count: 0,
            mailbox_count: 0,
            checkpoint_count: 0,
            lease_count: 0,
            binding_count: 0,
            teammate_count: 0,
            decision_count: 0,
            evidence_count: 0,
            patch_count: 0,
            growth_count: 0,
            environment_count: 0,
          },
        } as never}
        onCancelActor={vi.fn()}
        onPauseActor={vi.fn()}
        onResumeActor={vi.fn()}
        onRetryMailbox={vi.fn()}
      />,
    );

    expect(screen.getByText(agentWorkbenchText.actorRuntimeTitle)).toBeTruthy();
    expect(screen.getByRole("button", { name: pauseLabelPattern })).toBeTruthy();
    expect(screen.getByRole("button", { name: resumeLabelPattern })).toBeTruthy();
  });

  it("shows host coordination facts from host_twin projection for active runtime environment", () => {
    render(
      <ActorRuntimePanel
        actorActionKey={null}
        detail={{
          agent: {
            agent_id: "agent-1",
            current_task_id: "task-1",
          },
          runtime: {
            runtime_status: "running",
            desired_state: "active",
            queue_depth: 1,
            current_task_id: "task-1",
            current_mailbox_id: "mailbox-1",
            current_environment_id: "env-1",
            last_checkpoint_id: "checkpoint-1",
          },
          goals: [],
          tasks: [],
          mailbox: [],
          checkpoints: [],
          leases: [],
          thread_bindings: [],
          teammates: [],
          latest_collaboration: [],
          decisions: [],
          evidence: [],
          patches: [],
          growth: [],
          environments: [
            {
              id: "env-1",
              kind: "workspace",
              display_name: "Host workspace",
              ref: "session:web:main",
              status: "active",
              last_active_at: null,
              evidence_count: 0,
              host_contract: {
                handoff_state: "agent-attached",
                handoff_owner_ref: "human-operator:alice",
              },
              host_twin: {
                app_family_twins: {
                  office_document: {
                    writer_lock_scope: "workbook:weekly-report",
                  },
                },
                coordination: {
                  seat_owner_ref: "ops-agent",
                  writer_owner_ref: "ops-agent",
                  workspace_owner_ref: "ops-agent",
                  selected_seat_ref: "env-1",
                  seat_selection_policy: "sticky-active-seat",
                  recommended_scheduler_action: "handoff",
                  contention_forecast: {
                    severity: "blocked",
                    reason: "captcha-required",
                  },
                },
              },
            },
          ],
          workspace: {
            current_environment_id: "env-1",
            current_environment_ref: "session:web:main",
            current_environment: null,
            files_supported: false,
          },
          stats: {
            task_count: 0,
            mailbox_count: 0,
            checkpoint_count: 0,
            lease_count: 0,
            binding_count: 0,
            teammate_count: 0,
            decision_count: 0,
            evidence_count: 0,
            patch_count: 0,
            growth_count: 0,
            environment_count: 1,
          },
        } as never}
        onCancelActor={vi.fn()}
        onPauseActor={vi.fn()}
        onResumeActor={vi.fn()}
        onRetryMailbox={vi.fn()}
      />,
    );

    expect(screen.getByText("Host coordination")).toBeTruthy();
    expect(screen.getByText("Seat owner: ops-agent")).toBeTruthy();
    expect(screen.getByText("Workspace owner: ops-agent")).toBeTruthy();
    expect(screen.getByText("Writer owner: ops-agent")).toBeTruthy();
    expect(screen.getByText("Handoff: agent-attached")).toBeTruthy();
    expect(screen.getByText("Handoff owner: human-operator:alice")).toBeTruthy();
    expect(screen.getByText("Contention: blocked (captcha-required)")).toBeTruthy();
    expect(screen.getByText("Scheduler action: handoff")).toBeTruthy();
    expect(screen.getByText("Writer lock: workbook:weekly-report")).toBeTruthy();
  });
});
