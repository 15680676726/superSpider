import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { isApiError } from "../../api/errors";
import { request } from "../../api";
import { subscribe } from "../../runtime/eventBus";
import type { RuntimeMainBrainResponse } from "../../api/modules/runtimeCenter";
import {
  normalizeRuntimePath,
  requestRuntimeMainBrain,
  requestRuntimeOverview,
  requestRuntimeRecord,
} from "../../runtime/runtimeSurfaceClient";
import {
  formatRuntimeActionLabel,
  localizeRuntimeText,
  RUNTIME_CENTER_TEXT,
} from "./text";

export type RuntimeCardStatus = "state-service" | "degraded" | "unavailable";

export interface RuntimeOverviewEntry {
  id: string;
  title: string;
  kind: string;
  status: string;
  owner?: string | null;
  summary?: string | null;
  updated_at?: string | null;
  route?: string | null;
  actions: Record<string, string>;
  meta: Record<string, unknown>;
}

export interface RuntimeOverviewCard {
  key: string;
  title: string;
  source: string;
  status: RuntimeCardStatus;
  count: number;
  summary: string;
  entries: RuntimeOverviewEntry[];
  meta: Record<string, unknown>;
}

export interface RuntimeCenterOverviewPayload {
  generated_at: string;
  surface?: {
    version: "runtime-center-v1";
    mode: "operator-surface";
    status: RuntimeCardStatus;
    read_only: boolean;
    source: string;
    note: string;
    services?: string[];
  };
  cards: RuntimeOverviewCard[];
}

interface RuntimeActionResult {
  success?: boolean;
  summary?: string;
  error?: string | null;
  phase?: string;
  task_id?: string;
  decision_request_id?: string | null;
}

export interface RuntimeCenterDetailState {
  route: string;
  title: string;
  payload: Record<string, unknown> | null;
}

function normalizeCardStatus(status: string | undefined): RuntimeCardStatus {
  if (status === "state-service") {
    return "state-service";
  }
  if (status === "fallback" || status === "hybrid" || status === "degraded") {
    return "degraded";
  }
  return "unavailable";
}

function normalizeOverview(
  payload: RuntimeCenterOverviewPayload,
): RuntimeCenterOverviewPayload {
  const visibleCards = (payload.cards ?? []).filter(
    (card) => card.key !== "goals" && card.key !== "schedules",
  );
  return {
    ...payload,
    surface: payload.surface
      ? {
          ...payload.surface,
          status: normalizeCardStatus(payload.surface.status),
        }
      : payload.surface,
    cards: visibleCards.map((card) => ({
      ...card,
      status: normalizeCardStatus(card.status),
      meta: card.meta ?? {},
      entries: (card.entries ?? []).map((entry) => ({
        ...entry,
        actions: entry.actions ?? {},
        meta: entry.meta ?? {},
      })),
    })),
  };
}

function buildActionBody(
  cardKey: string,
  actionKey: string,
): Record<string, unknown> | undefined {
  if (actionKey === "delete") {
    return undefined;
  }
  if (cardKey === "decisions") {
    if (actionKey === "approve") {
      return {
        resolution: RUNTIME_CENTER_TEXT.resolutionApproved,
      };
    }
    if (actionKey === "reject") {
      return {
        resolution: RUNTIME_CENTER_TEXT.resolutionRejected,
      };
    }
    if (actionKey === "review") {
      return {
        actor: "runtime-center",
      };
    }
  }
  return {
    actor: "runtime-center",
  };
}

function actionMethod(actionKey: string): "POST" | "DELETE" {
  return actionKey === "delete" ? "DELETE" : "POST";
}

export function useRuntimeCenter() {
  const [data, setData] = useState<RuntimeCenterOverviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mainBrainData, setMainBrainData] =
    useState<RuntimeMainBrainResponse | null>(null);
  const [mainBrainLoading, setMainBrainLoading] = useState(true);
  const [mainBrainError, setMainBrainError] = useState<string | null>(null);
  const [mainBrainUnavailable, setMainBrainUnavailable] = useState(false);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RuntimeCenterDetailState | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const reloadTimerRef = useRef<number | null>(null);

  const load = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setMainBrainLoading(true);
    setMainBrainError(null);
    setMainBrainUnavailable(false);
    const overviewPromise =
      requestRuntimeOverview<RuntimeCenterOverviewPayload>();
    const mainBrainPromise = requestRuntimeMainBrain<RuntimeMainBrainResponse>();

    try {
      const payload = await overviewPromise;
      setData(normalizeOverview(payload));
      setError(null);
    } catch (err) {
      setError(
        localizeRuntimeText(err instanceof Error ? err.message : String(err)),
      );
      if (mode === "initial") {
        setData(null);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }

    try {
      const payload = await mainBrainPromise;
      setMainBrainData(payload);
      setMainBrainError(null);
      setMainBrainUnavailable(false);
    } catch (err) {
      if (isApiError(err) && err.isNotFound) {
        setMainBrainUnavailable(true);
        setMainBrainData(null);
        setMainBrainError(null);
      } else {
        const detail = localizeRuntimeText(
          err instanceof Error ? err.message : String(err),
        );
        setMainBrainError(detail);
        setMainBrainData(null);
      }
    } finally {
      setMainBrainLoading(false);
    }
  }, []);

  useEffect(() => {
    void load("initial");
  }, [load]);

  // Subscribe to the global event bus instead of opening a dedicated SSE
  // connection. The global bus (started in main.tsx) already connects to
  // /runtime-center/events and handles reconnection with back-off.
  useEffect(() => {
    const scheduleReload = () => {
      if (reloadTimerRef.current !== null) {
        window.clearTimeout(reloadTimerRef.current);
      }
      reloadTimerRef.current = window.setTimeout(() => {
        reloadTimerRef.current = null;
        void load();
      }, 250);
    };

    // Listen to all runtime-center related events via prefix match
    const unsub = subscribe("*", (event) => {
      // Any non-heartbeat event triggers a debounced reload
      if (!event.event_name.endsWith(".heartbeat")) {
        scheduleReload();
      }
    });

    return () => {
      unsub();
      if (reloadTimerRef.current !== null) {
        window.clearTimeout(reloadTimerRef.current);
        reloadTimerRef.current = null;
      }
    };
  }, [load]);

  const invokeAction = useCallback(
    async (
      cardKey: string,
      entryId: string,
      actionKey: string,
      actionPath: string,
    ) => {
      const busyId = `${cardKey}:${entryId}:${actionKey}`;
      setBusyActionId(busyId);
      try {
        const method = actionMethod(actionKey);
        const body = buildActionBody(cardKey, actionKey);
        const result = await request<RuntimeActionResult>(
          normalizeRuntimePath(actionPath),
          {
            method,
            body: body === undefined ? undefined : JSON.stringify(body),
          },
        );
        if (result?.phase === "waiting-confirm") {
          message.warning(
            result.decision_request_id
              ? RUNTIME_CENTER_TEXT.confirmationRequiredWithId(
                  result.decision_request_id,
                )
              : RUNTIME_CENTER_TEXT.confirmationRequired,
          );
        } else if (result?.success === false) {
          message.error(
            localizeRuntimeText(
              result.error || result.summary || RUNTIME_CENTER_TEXT.actionFailed,
            ),
          );
        } else {
          message.success(
            localizeRuntimeText(
              result?.summary ||
                RUNTIME_CENTER_TEXT.actionCompleted(
                  formatRuntimeActionLabel(actionKey),
                ),
            ),
          );
        }
        await load();
      } catch (err) {
        const detail = localizeRuntimeText(
          err instanceof Error ? err.message : String(err),
        );
        message.error(detail);
      } finally {
        setBusyActionId(null);
      }
    },
    [load],
  );

  const openDetail = useCallback(async (route: string, title: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const payload = await requestRuntimeRecord<Record<string, unknown>>(route);
      setDetail({
        route,
        title,
        payload,
      });
    } catch (err) {
      const detailMessage = localizeRuntimeText(
        err instanceof Error ? err.message : String(err),
      );
      setDetailError(detailMessage);
      message.error(detailMessage);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = useCallback(() => {
    setDetail(null);
    setDetailError(null);
  }, []);

  return {
    data,
    loading,
    refreshing,
    error,
    mainBrainData,
    mainBrainError,
    mainBrainLoading,
    mainBrainUnavailable,
    busyActionId,
    detail,
    detailLoading,
    detailError,
    reload: () => load(),
    invokeAction,
    openDetail,
    closeDetail,
  };
}
