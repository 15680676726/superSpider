// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();
const requestRuntimeBusinessAgentsMock = vi.fn();
const requestRuntimeEnvironmentListMock = vi.fn();
const requestRuntimeEvidenceListMock = vi.fn();
const requestRuntimeAgentDetailMock = vi.fn();

vi.mock("../../api", () => ({
  api: {},
  request: (...args: unknown[]) => requestMock(...args),
}));

vi.mock("../../runtime/runtimeSurfaceClient", () => ({
  requestRuntimeBusinessAgents: (...args: unknown[]) =>
    requestRuntimeBusinessAgentsMock(...args),
  requestRuntimeEnvironmentList: (...args: unknown[]) =>
    requestRuntimeEnvironmentListMock(...args),
  requestRuntimeEvidenceList: (...args: unknown[]) =>
    requestRuntimeEvidenceListMock(...args),
  requestRuntimeAgentDetail: (...args: unknown[]) =>
    requestRuntimeAgentDetailMock(...args),
}));

import { useAgentWorkbench } from "./useAgentWorkbench";

describe("useAgentWorkbench", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    requestMock.mockResolvedValue([]);
    requestRuntimeBusinessAgentsMock.mockResolvedValue([
      {
        agent_id: "agent-1",
        name: "执行位 1",
        role_name: "执行位",
        role_summary: "负责执行",
        agent_class: "business",
        employment_mode: "career",
        activation_mode: "persistent",
        suspendable: true,
        reports_to: null,
        mission: "",
        status: "active",
        risk_level: "auto",
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
    ]);
    requestRuntimeEnvironmentListMock.mockResolvedValue([]);
    requestRuntimeEvidenceListMock.mockResolvedValue([]);
    requestRuntimeAgentDetailMock.mockResolvedValue({
      agent: {
        agent_id: "agent-1",
        name: "执行位 1",
        role_name: "执行位",
        role_summary: "负责执行",
        agent_class: "business",
        employment_mode: "career",
        activation_mode: "persistent",
        suspendable: true,
        reports_to: null,
        mission: "",
        status: "active",
        risk_level: "auto",
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
      runtime: null,
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
      capability_surface: null,
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
    });
  });

  it("loads dashboard surfaces without calling the retired goals frontdoor", async () => {
    const { result } = renderHook(() => useAgentWorkbench());

    await waitFor(() => expect(result.current.loading).toBe(false));
    await waitFor(() =>
      expect(result.current.agentDetail?.agent.agent_id).toBe("agent-1"),
    );

    expect(requestRuntimeBusinessAgentsMock).toHaveBeenCalledTimes(1);
    expect(requestRuntimeEnvironmentListMock).toHaveBeenCalledTimes(1);
    expect(requestRuntimeEvidenceListMock).toHaveBeenCalledTimes(1);
  });

  it("routes capability review decisions through the governed runtime-center path", async () => {
    const { result } = renderHook(() => useAgentWorkbench());

    await waitFor(() => expect(result.current.loading).toBe(false));
    await result.current.resolveCapabilityDecision("decision-1", "review");

    expect(requestMock).toHaveBeenCalledWith(
      "/runtime-center/governed/decisions/decision-1/review",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("routes actor-backed capability governance through the agent surface", async () => {
    const { result } = renderHook(() => useAgentWorkbench());

    await waitFor(() => expect(result.current.loading).toBe(false));
    await result.current.submitGovernedCapabilityAssignment("agent-1", {
      capabilities: ["tool:send_file_to_user"],
      mode: "replace",
      reason: "read-only actor compatibility cutover",
    });

    expect(requestMock).toHaveBeenCalledWith(
      "/runtime-center/agents/agent-1/capabilities/governed",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("does not expose retired actor runtime mutation helpers", async () => {
    const { result } = renderHook(() => useAgentWorkbench());

    await waitFor(() => expect(result.current.loading).toBe(false));

    const hookState = result.current as Record<string, unknown>;
    expect(hookState.pauseActorRuntime).toBeUndefined();
    expect(hookState.resumeActorRuntime).toBeUndefined();
    expect(hookState.retryActorMailboxRuntime).toBeUndefined();
    expect(hookState.cancelActorRuntime).toBeUndefined();
  });
});
