import { useCallback, useMemo } from "react";

import {
  isFormalRuntimeThreadId,
  normalizeThreadId,
  parseIndustryThreadId,
} from "./chatPageHelpers";

type ThreadMetaLike = Record<string, unknown> | null | undefined;

export type RequestedIndustryThread = ReturnType<typeof parseIndustryThreadId>;

export type RuntimeBindingContext = {
  activeIndustryId: string | null;
  activeIndustryRoleId: string | null;
  activeAgentId: string | null;
};

export function resolveRuntimeBindingContext({
  threadMeta,
  requestedIndustryThread,
}: {
  threadMeta: ThreadMetaLike;
  requestedIndustryThread: RequestedIndustryThread;
}): RuntimeBindingContext {
  const meta = threadMeta && typeof threadMeta === "object" ? threadMeta : null;
  const activeIndustryId =
    typeof meta?.industry_instance_id === "string"
      ? meta.industry_instance_id
      : requestedIndustryThread?.instanceId || null;
  const activeIndustryRoleId =
    typeof meta?.industry_role_id === "string"
      ? meta.industry_role_id
      : requestedIndustryThread?.roleId || null;
  const activeAgentId =
    typeof meta?.agent_id === "string" ? meta.agent_id : null;
  return {
    activeIndustryId,
    activeIndustryRoleId,
    activeAgentId,
  };
}

export function buildWorkbenchPath({
  activeIndustryId,
  activeAgentId,
}: Pick<RuntimeBindingContext, "activeIndustryId" | "activeAgentId">): string {
  const params = new URLSearchParams();
  if (activeIndustryId) {
    params.set("industry", activeIndustryId);
  }
  if (activeAgentId) {
    params.set("agent", activeAgentId);
  }
  const query = params.toString();
  return query ? `/agents?${query}` : "/agents";
}

export function useRuntimeBinding({
  navigate,
  requestedThreadId,
  threadMeta,
  windowThreadId,
}: {
  navigate: (to: string, options?: { replace?: boolean }) => void;
  requestedThreadId: string | null;
  threadMeta: ThreadMetaLike;
  windowThreadId: string | null | undefined;
}) {
  const requestedThreadLooksBound = useMemo(
    () => isFormalRuntimeThreadId(requestedThreadId),
    [requestedThreadId],
  );
  const requestedIndustryThread = useMemo(
    () => parseIndustryThreadId(requestedThreadId),
    [requestedThreadId],
  );
  const metaIndustryId =
    typeof threadMeta?.industry_instance_id === "string"
      ? threadMeta.industry_instance_id
      : null;
  const metaIndustryRoleId =
    typeof threadMeta?.industry_role_id === "string"
      ? threadMeta.industry_role_id
      : null;
  const metaAgentId =
    typeof threadMeta?.agent_id === "string" ? threadMeta.agent_id : null;
  const binding = useMemo(
    () =>
      resolveRuntimeBindingContext({
        threadMeta: {
          industry_instance_id: metaIndustryId,
          industry_role_id: metaIndustryRoleId,
          agent_id: metaAgentId,
        },
        requestedIndustryThread,
      }),
    [metaAgentId, metaIndustryId, metaIndustryRoleId, requestedIndustryThread],
  );
  const activeChatThreadId = useMemo(
    () => normalizeThreadId(requestedThreadId || windowThreadId || null),
    [requestedThreadId, windowThreadId],
  );
  const openWorkbench = useCallback(() => {
    navigate(
      buildWorkbenchPath({
        activeIndustryId: binding.activeIndustryId,
        activeAgentId: binding.activeAgentId,
      }),
    );
  }, [binding.activeAgentId, binding.activeIndustryId, navigate]);

  return {
    ...binding,
    activeChatThreadId,
    openWorkbench,
    requestedIndustryThread,
    requestedThreadLooksBound,
  };
}
