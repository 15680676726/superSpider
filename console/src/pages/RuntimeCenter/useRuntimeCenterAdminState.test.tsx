// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("antd", () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock("../../api", () => {
  return {
    api: {
      getGovernanceStatus: vi.fn(),
      getRuntimeCapabilityOptimizations: vi.fn(),
      getLatestRecoveryReport: vi.fn(),
      runSystemSelfCheck: vi.fn(),
      approveRuntimeDecisions: vi.fn(),
      rejectRuntimeDecisions: vi.fn(),
      approveRuntimePatches: vi.fn(),
      rejectRuntimePatches: vi.fn(),
      applyRuntimePatches: vi.fn(),
      rollbackRuntimePatches: vi.fn(),
      coordinatePredictionRecommendation: vi.fn(),
      emergencyStopRuntime: vi.fn(),
      resumeGovernedRuntime: vi.fn(),
    },
  };
});

import { api } from "../../api";
import type { RuntimeOverviewEntry } from "./useRuntimeCenter";
import { RUNTIME_CENTER_TEXT } from "./text";
import { useRuntimeCenterAdminState } from "./useRuntimeCenterAdminState";

const mockedApi = vi.mocked(api);

function makeEntry(id: string): RuntimeOverviewEntry {
  return {
    id,
    title: `Entry ${id}`,
    kind: "decision",
    status: "pending",
    owner: "runtime-center",
    summary: "Summary",
    updated_at: "2026-03-26T08:00:00Z",
    route: `/api/runtime-center/${id}`,
    actions: {},
    meta: {},
  };
}

describe("useRuntimeCenterAdminState", () => {
  beforeEach(() => {
    mockedApi.getGovernanceStatus.mockReset();
    mockedApi.getRuntimeCapabilityOptimizations.mockReset();
    mockedApi.getLatestRecoveryReport.mockReset();
    mockedApi.runSystemSelfCheck.mockReset();
    mockedApi.approveRuntimeDecisions.mockReset();
    mockedApi.rejectRuntimeDecisions.mockReset();
    mockedApi.approveRuntimePatches.mockReset();
    mockedApi.rejectRuntimePatches.mockReset();
    mockedApi.applyRuntimePatches.mockReset();
    mockedApi.rollbackRuntimePatches.mockReset();
    mockedApi.coordinatePredictionRecommendation.mockReset();
    mockedApi.emergencyStopRuntime.mockReset();
    mockedApi.resumeGovernedRuntime.mockReset();
  });

  it("loads governance and capability optimization surfaces when the governance tab is active", async () => {
    mockedApi.getGovernanceStatus.mockResolvedValue({
      emergency_stop_active: false,
      pending_decisions: 1,
      pending_patches: 0,
      proposed_patches: 0,
      blocked_capability_refs: [],
      paused_schedule_ids: [],
      channel_shutdown_applied: false,
      updated_at: "2026-03-26T08:00:00Z",
    } as never);
    mockedApi.getRuntimeCapabilityOptimizations.mockResolvedValue({
      generated_at: "2026-03-26T08:00:00Z",
      summary: {
        total_items: 1,
        actionable_count: 1,
        history_count: 0,
        case_count: 1,
        missing_capability_count: 0,
        underperforming_capability_count: 0,
        trial_count: 0,
        rollout_count: 0,
        retire_count: 0,
        waiting_confirm_count: 0,
        manual_only_count: 0,
        executed_count: 0,
      },
      actionable: [],
      history: [],
      routes: {},
    } as never);

    const reload = vi.fn().mockResolvedValue(undefined);
    const navigate = vi.fn();
    const decisionEntries = [makeEntry("decision-1")];
    const patchEntries: RuntimeOverviewEntry[] = [];

    renderHook(() =>
      useRuntimeCenterAdminState({
        activeTab: "governance",
        dataGeneratedAt: "2026-03-26T08:00:00Z",
        decisionEntries,
        patchEntries,
        reload,
        navigate,
      }),
    );

    await waitFor(() => {
      expect(mockedApi.getGovernanceStatus).toHaveBeenCalledTimes(1);
      expect(mockedApi.getRuntimeCapabilityOptimizations).toHaveBeenCalledTimes(1);
    });
  });

  it("approves the selected decisions through one governance action flow and clears the selection", async () => {
    mockedApi.getGovernanceStatus.mockResolvedValue({
      emergency_stop_active: false,
      pending_decisions: 1,
      pending_patches: 0,
      proposed_patches: 0,
      blocked_capability_refs: [],
      paused_schedule_ids: [],
      channel_shutdown_applied: false,
      updated_at: "2026-03-26T08:00:00Z",
    } as never);
    mockedApi.getRuntimeCapabilityOptimizations.mockResolvedValue({
      generated_at: "2026-03-26T08:00:00Z",
      summary: {
        total_items: 0,
        actionable_count: 0,
        history_count: 0,
        case_count: 0,
        missing_capability_count: 0,
        underperforming_capability_count: 0,
        trial_count: 0,
        rollout_count: 0,
        retire_count: 0,
        waiting_confirm_count: 0,
        manual_only_count: 0,
        executed_count: 0,
      },
      actionable: [],
      history: [],
      routes: {},
    } as never);
    mockedApi.approveRuntimeDecisions.mockResolvedValue({
      success: true,
      total: 1,
      success_ids: ["decision-1"],
      failed: [],
    } as never);

    const reload = vi.fn().mockResolvedValue(undefined);
    const navigate = vi.fn();
    const decisionEntries = [makeEntry("decision-1")];
    const patchEntries: RuntimeOverviewEntry[] = [];

    const { result } = renderHook(() =>
      useRuntimeCenterAdminState({
        activeTab: "governance",
        dataGeneratedAt: "2026-03-26T08:00:00Z",
        decisionEntries,
        patchEntries,
        reload,
        navigate,
      }),
    );

    await waitFor(() => {
      expect(mockedApi.getGovernanceStatus).toHaveBeenCalledTimes(1);
    });

    act(() => {
      result.current.setSelectedDecisionIds(["decision-1"]);
    });

    await act(async () => {
      await result.current.handleDecisionBatch("approve");
    });

    expect(mockedApi.approveRuntimeDecisions).toHaveBeenCalledWith({
      decision_ids: ["decision-1"],
      actor: "runtime-center",
      resolution: RUNTIME_CENTER_TEXT.resolutionApproved,
      execute: true,
    });
    expect(reload).toHaveBeenCalled();
    expect(result.current.selectedDecisionIds).toEqual([]);
  });
});
