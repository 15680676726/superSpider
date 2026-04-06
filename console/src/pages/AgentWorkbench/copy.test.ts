import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import {
  agentReportsText,
  agentWorkbenchText,
  commonText,
  getStatusLabel,
  workspaceText,
} from "./copy";

describe("AgentWorkbench copy", () => {
  it("uses current focus wording instead of legacy current goal wording", () => {
    expect(agentWorkbenchText.currentFocusLabel).toBe("当前焦点");
    expect(agentWorkbenchText.currentFocusLabel).not.toContain("目标");
  });

  it("locks the new top-level tab copy", () => {
    expect(agentWorkbenchText.tabDaily).toBe("今日简报");
    expect(agentWorkbenchText.tabWeekly).toBe("周报");
    expect(agentWorkbenchText.tabProfile).toBe("简历");
    expect(agentWorkbenchText.tabPerformance).toBe("绩效");
    expect(agentWorkbenchText.tabEvidence).toBe("证据产物");
    expect(workspaceText.taskProgressHint).toBe(
      "执行进展请看今日简报、周报和证据产物。",
    );
  });

  it("reuses the shared runtime status copy for common runtime states", () => {
    expect(getStatusLabel("active")).toBe(presentRuntimeStatusLabel("active"));
    expect(getStatusLabel("idle")).toBe(presentRuntimeStatusLabel("idle"));
    expect(getStatusLabel("assigned")).toBe(presentRuntimeStatusLabel("assigned"));
    expect(getStatusLabel("approved")).toBe(
      presentRuntimeStatusLabel("approved"),
    );
    expect(getStatusLabel("open")).toBe(presentRuntimeStatusLabel("open"));
  });

  it("keeps workbench-specific statuses local", () => {
    expect(getStatusLabel("scheduled")).toBe("已排期");
    expect(getStatusLabel("warn")).toBe("警告");
  });
  it("does not keep retired linked-panel copy keys after the legacy panels were removed", () => {
    for (const key of [
      "teammatesSectionTitle",
      "noTeammates",
      "openChatAction",
      "latestCollaborationLabel",
      "linkedAgentsTitle",
      "noLinkedAgents",
      "compiledTaskSpecsTitle",
      "noCompiledSpecs",
      "linkedTasksTitle",
      "noLinkedTasks",
      "decisionRequestsTitle",
      "noDecisionRequests",
      "linkedPatchesTitle",
      "noLinkedPatches",
      "growthTitle",
      "noLinkedGrowth",
      "planStepsLabel",
      "industryContextLabel",
      "recorded",
      "metricTasks",
      "metricDecisions",
      "metricEvidence",
      "metricPatches",
      "metricGrowth",
      "metricAgents",
    ]) {
      expect(agentWorkbenchText).not.toHaveProperty(key);
    }
    expect(commonText).not.toHaveProperty("openInChat");
    expect(workspaceText).not.toHaveProperty("tabTitle");
    for (const key of [
      "evidenceToday",
      "growthToday",
      "proposalsToday",
      "patchesToday",
      "dailyFocusLabel",
      "dailyFocusTraceable",
      "dailyFocusGap",
      "noEvidenceToday",
      "latestEvidence",
      "evidenceIn7d",
      "growthIn7d",
      "proposalsIn7d",
      "patchesIn7d",
      "weeklySignalLabel",
      "weeklySignalActive",
      "weeklySignalIncomplete",
      "noAppliedPatches",
      "appliedPatchHighlights",
    ]) {
      expect(agentReportsText).not.toHaveProperty(key);
    }
  });
});
