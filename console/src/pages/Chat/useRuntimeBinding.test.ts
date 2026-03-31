// @vitest-environment jsdom

import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  buildWorkbenchPath,
  resolveRuntimeBindingContext,
  useRuntimeBinding,
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

  it("keeps the workbench callback stable across unrelated thread-meta updates", () => {
    const navigate = vi.fn();
    const { result, rerender } = renderHook(
      (props: { threadMeta: Record<string, unknown> }) =>
        useRuntimeBinding({
          navigate,
          requestedThreadId: "industry-chat:industry-1:execution-core",
          threadMeta: props.threadMeta,
          windowThreadId: null,
        }),
      {
        initialProps: {
          threadMeta: {
            industry_instance_id: "industry-1",
            industry_role_id: "execution-core",
            agent_id: "agent-1",
            ui_updated_at: 1,
          },
        },
      },
    );
    const firstOpenWorkbench = result.current.openWorkbench;

    rerender({
      threadMeta: {
        industry_instance_id: "industry-1",
        industry_role_id: "execution-core",
        agent_id: "agent-1",
        ui_updated_at: 2,
      },
    });

    expect(result.current.openWorkbench).toBe(firstOpenWorkbench);
  });
});
