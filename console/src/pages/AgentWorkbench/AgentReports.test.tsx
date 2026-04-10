// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("../../api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

import { AgentGrowthTrajectory } from "./AgentReports";

describe("AgentGrowthTrajectory", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("scopes the learning feed to the selected agent instead of showing the global feed", async () => {
    requestMock.mockImplementation(async (url: string) => {
      if (url.startsWith("/runtime-center/learning/growth")) {
        return [
          {
            id: "growth-a",
            agent_id: "agent-a",
            change_type: "patch_applied",
            description: "Agent A growth",
            source_patch_id: "patch-a",
            risk_level: "auto",
            result: "applied",
            created_at: "2026-04-09T10:00:00Z",
          },
        ];
      }
      if (url.startsWith("/runtime-center/learning/proposals")) {
        return [
          {
            id: "proposal-a",
            title: "Agent A proposal",
            description: "Proposal for agent A",
            source_agent_id: "agent-a",
            agent_id: "agent-a",
            status: "open",
            created_at: "2026-04-09T09:00:00Z",
          },
          {
            id: "proposal-b",
            title: "Agent B proposal",
            description: "Proposal for agent B",
            source_agent_id: "agent-b",
            agent_id: "agent-b",
            status: "open",
            created_at: "2026-04-09T08:00:00Z",
          },
        ];
      }
      if (url.startsWith("/runtime-center/learning/patches")) {
        return [
          {
            id: "patch-a",
            kind: "plan_patch",
            title: "Patch A",
            description: "Patch for agent A",
            status: "applied",
            risk_level: "auto",
            applied_at: "2026-04-09T11:00:00Z",
            created_at: "2026-04-09T10:30:00Z",
            agent_id: "agent-a",
          },
          {
            id: "patch-b",
            kind: "plan_patch",
            title: "Patch B",
            description: "Patch for agent B",
            status: "applied",
            risk_level: "auto",
            applied_at: "2026-04-09T07:00:00Z",
            created_at: "2026-04-09T06:30:00Z",
            agent_id: "agent-b",
          },
        ];
      }
      if (url.startsWith("/runtime-center/evidence")) {
        return [];
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<AgentGrowthTrajectory agentId="agent-a" agentName="Agent A" />);

    await screen.findByText("Agent A growth");
    expect(screen.queryByText("Agent B proposal")).not.toBeInTheDocument();
    expect(screen.queryByText("Patch B")).not.toBeInTheDocument();
    expect(screen.getByText("Patch A")).toBeInTheDocument();
    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith(
        "/runtime-center/learning/growth?agent_id=agent-a&limit=50",
      );
      expect(requestMock).toHaveBeenCalledWith(
        "/runtime-center/learning/patches?agent_id=agent-a&limit=50",
      );
    });
  });
});
