import { describe, expect, it } from "vitest";

import { resolveVerifiedRuntimeBindingState } from "./useChatRuntimeState";

describe("resolveVerifiedRuntimeBindingState", () => {
  it("does not treat URL fallback ids as a verified bound context", () => {
    expect(
      resolveVerifiedRuntimeBindingState({
        threadMeta: {},
        activeAgentId: null,
        activeIndustryId: "industry-from-url",
        activeIndustryRoleId: "execution-core",
        runtimeWindowUserId: "window-user",
      }),
    ).toEqual(
      expect.objectContaining({
        hasIndustryContext: false,
        hasAgentBinding: false,
        hasBoundAgentContext: false,
        sessionKind: "",
      }),
    );
  });

  it("treats verified thread metadata as the only bound-context truth", () => {
    expect(
      resolveVerifiedRuntimeBindingState({
        threadMeta: {
          industry_instance_id: "industry-1",
          industry_label: "Acme Mesh",
          industry_role_name: "执行中枢",
          session_kind: "industry-control-thread",
          agent_id: "agent-1",
          agent_name: "Spider Mesh 主脑",
          current_focus: "Ship phase split",
        },
        activeAgentId: "agent-url",
        activeIndustryId: "industry-url",
        activeIndustryRoleId: "execution-core",
        runtimeWindowUserId: "window-user",
      }),
    ).toEqual(
      expect.objectContaining({
        industryLabel: "Acme Mesh",
        roleLabel: "执行中枢",
        agentLabel: "Spider Mesh 主脑",
        currentFocus: "Ship phase split",
        hasIndustryContext: true,
        hasAgentBinding: true,
        hasBoundAgentContext: true,
        sessionKind: "industry-control-thread",
        bindingLabel: "Acme Mesh / 执行中枢",
      }),
    );
  });
});
