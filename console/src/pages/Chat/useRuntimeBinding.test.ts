import { describe, expect, it } from "vitest";

import {
  buildWorkbenchPath,
  resolveRuntimeBindingContext,
} from "./useRuntimeBinding";

describe("useRuntimeBinding", () => {
  it("prefers explicit thread metadata over the parsed thread fallback", () => {
    const resolved = resolveRuntimeBindingContext({
      threadMeta: {
        industry_instance_id: "industry-meta",
        industry_role_id: "role-meta",
        agent_id: "agent-meta",
      },
      requestedIndustryThread: {
        instanceId: "industry-thread",
        roleId: "role-thread",
      },
    });

    expect(resolved.activeIndustryId).toBe("industry-meta");
    expect(resolved.activeIndustryRoleId).toBe("role-meta");
    expect(resolved.activeAgentId).toBe("agent-meta");
  });

  it("builds the canonical workbench route from runtime binding context", () => {
    expect(buildWorkbenchPath({ activeIndustryId: "industry-1", activeAgentId: "agent-1" })).toBe(
      "/agents?industry=industry-1&agent=agent-1",
    );
    expect(buildWorkbenchPath({ activeIndustryId: "industry-1", activeAgentId: null })).toBe(
      "/agents?industry=industry-1",
    );
    expect(buildWorkbenchPath({ activeIndustryId: null, activeAgentId: null })).toBe("/agents");
  });
});
