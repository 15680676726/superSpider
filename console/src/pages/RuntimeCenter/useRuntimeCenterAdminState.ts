import { message } from "antd";
import { useCallback, useEffect, useState } from "react";
import type { NavigateFunction } from "react-router-dom";

import {
  api,
  type GovernanceStatus,
  type StartupRecoverySummary,
  type SystemSelfCheck,
} from "../../api";
import type { RuntimeCapabilityOptimizationOverview } from "../../api/modules/runtimeCenter";
import type { RuntimeOverviewEntry } from "./useRuntimeCenter";
import {
  formatRuntimeActionLabel,
  localizeRuntimeText,
  RUNTIME_CENTER_TEXT,
} from "./text";

export type RuntimeCenterTab =
  | "overview"
  | "governance"
  | "recovery"
  | "automation";

type UseRuntimeCenterAdminStateArgs = {
  activeTab: RuntimeCenterTab;
  dataGeneratedAt?: string | null;
  decisionEntries: RuntimeOverviewEntry[];
  patchEntries: RuntimeOverviewEntry[];
  reload: () => Promise<void>;
  navigate: NavigateFunction;
};

export function useRuntimeCenterAdminState({
  activeTab,
  dataGeneratedAt,
  decisionEntries,
  patchEntries,
  reload,
  navigate,
}: UseRuntimeCenterAdminStateArgs) {
  const [governanceStatus, setGovernanceStatus] = useState<GovernanceStatus | null>(null);
  const [governanceLoading, setGovernanceLoading] = useState(false);
  const [governanceError, setGovernanceError] = useState<string | null>(null);
  const [governanceBusyKey, setGovernanceBusyKey] = useState<string | null>(null);
  const [capabilityOptimizationOverview, setCapabilityOptimizationOverview] =
    useState<RuntimeCapabilityOptimizationOverview | null>(null);
  const [capabilityOptimizationLoading, setCapabilityOptimizationLoading] =
    useState(false);
  const [capabilityOptimizationError, setCapabilityOptimizationError] =
    useState<string | null>(null);
  const [capabilityOptimizationBusyId, setCapabilityOptimizationBusyId] =
    useState<string | null>(null);
  const [recoverySummary, setRecoverySummary] = useState<StartupRecoverySummary | null>(null);
  const [selfCheck, setSelfCheck] = useState<SystemSelfCheck | null>(null);
  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
  const [recoveryBusyKey, setRecoveryBusyKey] = useState<string | null>(null);
  const [operatorActor, setOperatorActor] = useState("runtime-center");
  const [governanceResolution, setGovernanceResolution] = useState<string>(
    () => RUNTIME_CENTER_TEXT.resolutionApproved,
  );
  const [emergencyReason, setEmergencyReason] = useState<string>(
    () => RUNTIME_CENTER_TEXT.defaultEmergencyReason,
  );
  const [resumeReason, setResumeReason] = useState<string>(
    () => RUNTIME_CENTER_TEXT.defaultResumeReason,
  );
  const [executeApprovedDecisions, setExecuteApprovedDecisions] = useState(true);
  const [selectedDecisionIds, setSelectedDecisionIds] = useState<string[]>([]);
  const [selectedPatchIds, setSelectedPatchIds] = useState<string[]>([]);

  const loadGovernance = useCallback(async () => {
    setGovernanceLoading(true);
    try {
      setGovernanceStatus(await api.getGovernanceStatus());
      setGovernanceError(null);
    } catch (err) {
      setGovernanceError(
        localizeRuntimeText(err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setGovernanceLoading(false);
    }
  }, []);

  const loadCapabilityOptimizations = useCallback(async () => {
    setCapabilityOptimizationLoading(true);
    try {
      setCapabilityOptimizationOverview(
        await api.getRuntimeCapabilityOptimizations(),
      );
      setCapabilityOptimizationError(null);
    } catch (err) {
      setCapabilityOptimizationError(
        localizeRuntimeText(err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setCapabilityOptimizationLoading(false);
    }
  }, []);

  const loadRecovery = useCallback(async () => {
    setRecoveryLoading(true);
    try {
      const [recoveryPayload, selfCheckPayload] = await Promise.all([
        api.getLatestRecoveryReport(),
        api.runSystemSelfCheck(),
      ]);
      setRecoverySummary(recoveryPayload);
      setSelfCheck(selfCheckPayload);
      setRecoveryError(null);
    } catch (err) {
      setRecoveryError(
        localizeRuntimeText(err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setRecoveryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "governance") {
      void loadGovernance();
      void loadCapabilityOptimizations();
    }
    if (activeTab === "recovery") {
      void loadRecovery();
    }
  }, [
    activeTab,
    dataGeneratedAt,
    loadCapabilityOptimizations,
    loadGovernance,
    loadRecovery,
  ]);

  useEffect(() => {
    setSelectedDecisionIds((current) =>
      current.filter((id) => decisionEntries.some((entry) => entry.id === id)),
    );
  }, [decisionEntries]);

  useEffect(() => {
    setSelectedPatchIds((current) =>
      current.filter((id) => patchEntries.some((entry) => entry.id === id)),
    );
  }, [patchEntries]);

  const runGovernanceAction = useCallback(
    async (key: string, task: () => Promise<void>) => {
      setGovernanceBusyKey(key);
      try {
        await task();
        message.success(
          localizeRuntimeText(
            RUNTIME_CENTER_TEXT.actionCompleted(formatRuntimeActionLabel(key)),
          ),
        );
        await Promise.all([
          reload(),
          loadGovernance(),
          loadCapabilityOptimizations(),
        ]);
      } catch (err) {
        message.error(
          localizeRuntimeText(err instanceof Error ? err.message : String(err)),
        );
      } finally {
        setGovernanceBusyKey(null);
      }
    },
    [loadCapabilityOptimizations, loadGovernance, reload],
  );

  const runRecoveryAction = useCallback(async (key: string, task: () => Promise<void>) => {
    setRecoveryBusyKey(key);
    try {
      await task();
    } catch (err) {
      message.error(
        localizeRuntimeText(err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setRecoveryBusyKey(null);
    }
  }, []);

  const handleDecisionBatch = useCallback(
    async (action: "approve" | "reject") => {
      if (selectedDecisionIds.length === 0) {
        message.warning(RUNTIME_CENTER_TEXT.selectDecisionBatch);
        return;
      }
      await runGovernanceAction(`decisions-${action}`, async () => {
        if (action === "approve") {
          await api.approveRuntimeDecisions({
            decision_ids: selectedDecisionIds,
            actor: operatorActor,
            resolution: governanceResolution,
            execute: executeApprovedDecisions,
          });
        } else {
          await api.rejectRuntimeDecisions({
            decision_ids: selectedDecisionIds,
            actor: operatorActor,
            resolution: governanceResolution,
          });
        }
        setSelectedDecisionIds([]);
      });
    },
    [
      executeApprovedDecisions,
      governanceResolution,
      operatorActor,
      runGovernanceAction,
      selectedDecisionIds,
    ],
  );

  const handlePatchBatch = useCallback(
    async (action: "approve" | "reject" | "apply" | "rollback") => {
      if (selectedPatchIds.length === 0) {
        message.warning(RUNTIME_CENTER_TEXT.selectPatchBatch);
        return;
      }
      await runGovernanceAction(`patches-${action}`, async () => {
        if (action === "approve") {
          await api.approveRuntimePatches({
            patch_ids: selectedPatchIds,
            actor: operatorActor,
          });
        }
        if (action === "reject") {
          await api.rejectRuntimePatches({
            patch_ids: selectedPatchIds,
            actor: operatorActor,
          });
        }
        if (action === "apply") {
          await api.applyRuntimePatches({
            patch_ids: selectedPatchIds,
            actor: operatorActor,
          });
        }
        if (action === "rollback") {
          await api.rollbackRuntimePatches({
            patch_ids: selectedPatchIds,
            actor: operatorActor,
          });
        }
        setSelectedPatchIds([]);
      });
    },
    [operatorActor, runGovernanceAction, selectedPatchIds],
  );

  const handleCapabilityOptimizationExecute = useCallback(
    async (
      item: RuntimeCapabilityOptimizationOverview["actionable"][number],
    ) => {
      const recommendation = item.recommendation.recommendation;
      const recommendationId = recommendation.recommendation_id;
      if (!recommendationId || !item.case.case_id) {
        message.warning("当前建议缺少可处理标识，无法交给主脑。");
        return;
      }
      setCapabilityOptimizationBusyId(recommendationId);
      try {
        const payload = await api.coordinatePredictionRecommendation(
          item.case.case_id,
          recommendationId,
          { actor: operatorActor },
        );
        message.success(localizeRuntimeText(payload.summary || "已交给主脑处理。"));
        if (
          typeof payload.chat_route === "string" &&
          payload.chat_route.startsWith("/") &&
          !payload.chat_route.startsWith("/api/")
        ) {
          navigate(payload.chat_route);
        }
        await Promise.all([
          reload(),
          loadGovernance(),
          loadCapabilityOptimizations(),
        ]);
      } catch (err) {
        message.error(
          localizeRuntimeText(err instanceof Error ? err.message : String(err)),
        );
      } finally {
        setCapabilityOptimizationBusyId(null);
      }
    },
    [loadCapabilityOptimizations, loadGovernance, navigate, operatorActor, reload],
  );

  const handleEmergencyStop = useCallback(async () => {
    await runGovernanceAction("emergency-stop", async () => {
      await api.emergencyStopRuntime({
        actor: operatorActor,
        reason: emergencyReason,
      });
    });
  }, [emergencyReason, operatorActor, runGovernanceAction]);

  const handleResumeRuntime = useCallback(async () => {
    await runGovernanceAction("resume", async () => {
      await api.resumeGovernedRuntime({
        actor: operatorActor,
        reason: resumeReason || undefined,
      });
    });
  }, [operatorActor, resumeReason, runGovernanceAction]);

  const handleRecoveryRefresh = useCallback(async () => {
    await runRecoveryAction("recovery-refresh", async () => {
      await loadRecovery();
    });
  }, [loadRecovery, runRecoveryAction]);

  const handleSelfCheck = useCallback(async () => {
    await runRecoveryAction("self-check", async () => {
      const payload = await api.runSystemSelfCheck();
      setSelfCheck(payload);
      message.success(RUNTIME_CENTER_TEXT.selfCheckCompleted);
    });
  }, [runRecoveryAction]);

  const refreshActiveTabData = useCallback(async () => {
    if (activeTab === "governance") {
      await Promise.all([reload(), loadGovernance(), loadCapabilityOptimizations()]);
      return;
    }
    if (activeTab === "recovery") {
      await Promise.all([reload(), loadRecovery()]);
      return;
    }
    await reload();
  }, [activeTab, loadCapabilityOptimizations, loadGovernance, loadRecovery, reload]);

  return {
    governanceStatus,
    governanceLoading,
    governanceError,
    governanceBusyKey,
    capabilityOptimizationOverview,
    capabilityOptimizationLoading,
    capabilityOptimizationError,
    capabilityOptimizationBusyId,
    recoverySummary,
    selfCheck,
    recoveryLoading,
    recoveryError,
    recoveryBusyKey,
    operatorActor,
    setOperatorActor,
    governanceResolution,
    setGovernanceResolution,
    emergencyReason,
    setEmergencyReason,
    resumeReason,
    setResumeReason,
    executeApprovedDecisions,
    setExecuteApprovedDecisions,
    selectedDecisionIds,
    setSelectedDecisionIds,
    selectedPatchIds,
    setSelectedPatchIds,
    loadRecovery,
    handleDecisionBatch,
    handlePatchBatch,
    handleCapabilityOptimizationExecute,
    handleEmergencyStop,
    handleResumeRuntime,
    handleRecoveryRefresh,
    handleSelfCheck,
    refreshActiveTabData,
  };
}
