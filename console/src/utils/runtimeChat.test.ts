import { describe, expect, it } from "vitest";

import {
  buildAgentChatBinding,
  buildBoundAgentChatBinding,
} from "./runtimeChat";

describe("runtimeChat", () => {
  it("projects current focus metadata into bound agent chat bindings", () => {
    const binding = buildBoundAgentChatBinding({
      agentId: "ops-agent",
      agentName: "Ops Agent",
      roleName: "Operations",
      currentFocusKind: "goal",
      currentFocusId: "goal-1",
      currentFocus: "Launch runtime center",
      industryInstanceId: "industry-1",
      industryRoleId: "operations",
      threadId: "industry-chat:industry-1:execution-core",
    });

    expect(binding.meta).toMatchObject({
      current_focus_kind: "goal",
      current_focus_id: "goal-1",
      current_focus: "Launch runtime center",
    });
    expect(binding.meta).not.toHaveProperty("current_goal");
  });

  it("uses focus-first agent metadata when opening the retained control thread", () => {
    const binding = buildAgentChatBinding({
      agent_id: "ops-agent",
      name: "Ops Agent",
      role_name: "Operations",
      current_focus_kind: "goal",
      current_focus_id: "goal-1",
      current_focus: "Launch runtime center",
      current_goal: "Legacy goal title",
      industry_instance_id: "industry-1",
      industry_role_id: "operations",
    });

    expect(binding.threadId).toBe("industry-chat:industry-1:execution-core");
    expect(binding.meta).toMatchObject({
      current_focus_kind: "goal",
      current_focus_id: "goal-1",
      current_focus: "Launch runtime center",
    });
    expect(binding.meta).not.toHaveProperty("current_goal");
  });
});
