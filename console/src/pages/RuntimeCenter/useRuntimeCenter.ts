import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { message } from "antd";
import { request } from "../../api";
import { subscribe } from "../../runtime/eventBus";
import type {
  RuntimeCenterSurfaceResponse,
  RuntimeMainBrainBuddySummary,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import {
  normalizeRuntimePath,
  requestRuntimeRecord,
  type RuntimeSurfaceSection,
  requestRuntimeSurface,
} from "../../runtime/runtimeSurfaceClient";
import {
  formatRuntimeActionLabel,
  localizeRuntimeText,
  RUNTIME_CENTER_TEXT,
} from "./text";

let runtimeCenterSurfaceCache: RuntimeCenterSurfaceResponse | null = null;
let runtimeCenterBuddySummaryCache: RuntimeMainBrainBuddySummary | null = null;
let runtimeCenterMainBrainHydratedCache = false;

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

export interface RuntimeCenterAgentSummary {
  agent_id: string;
  name?: string | null;
  role_name?: string | null;
  role_summary?: string | null;
  agent_class?: string | null;
  status?: string | null;
  current_focus?: string | null;
  current_focus_kind?: string | null;
  current_focus_id?: string | null;
  reports_to?: string | null;
  industry_role_id?: string | null;
}

const MAIN_BRAIN_AGENT_IDS = new Set(["copaw-agent-runner"]);
const MAIN_BRAIN_AGENT_CLASSES = new Set(["system"]);
const MAIN_BRAIN_ROLE_IDS = new Set(["execution-core"]);

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
  if (status === "fallback" || status === "degraded") {
    return "degraded";
  }
  return "unavailable";
}

function normalizeOverview(
  payload: RuntimeCenterOverviewPayload,
): RuntimeCenterOverviewPayload {
  const visibleCards = (payload.cards ?? []).filter(
    (card) =>
      card.key !== "goals" &&
      card.key !== "schedules" &&
      card.key !== "main-brain",
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

function metaString(
  meta: Record<string, unknown> | undefined,
  key: string,
): string | null {
  if (!meta) {
    return null;
  }
  const value = meta[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function deriveBusinessAgents(
  payload: RuntimeCenterOverviewPayload,
): RuntimeCenterAgentSummary[] {
  const agentsCard = (payload.cards ?? []).find((card) => card.key === "agents");
  if (!agentsCard) {
    return [];
  }
  return (agentsCard.entries ?? [])
    .map((entry) => ({
      agent_id: entry.id,
      name: entry.title || entry.id,
      role_name: metaString(entry.meta, "role_name") ?? entry.owner ?? null,
      role_summary: entry.summary ?? null,
      agent_class: metaString(entry.meta, "agent_class"),
      status: entry.status ?? null,
      current_focus: metaString(entry.meta, "current_focus"),
      current_focus_kind: metaString(entry.meta, "current_focus_kind"),
      current_focus_id: metaString(entry.meta, "current_focus_id"),
      reports_to: metaString(entry.meta, "reports_to"),
      industry_role_id: metaString(entry.meta, "industry_role_id"),
    } satisfies RuntimeCenterAgentSummary))
    .filter((agent) => !isMainBrainAgent(agent));
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

function isMainBrainAgent(agent: RuntimeCenterAgentSummary | null | undefined): boolean {
  if (!agent) {
    return false;
  }
  return (
    MAIN_BRAIN_AGENT_IDS.has(agent.agent_id) ||
    MAIN_BRAIN_AGENT_CLASSES.has(agent.agent_class ?? "") ||
    MAIN_BRAIN_ROLE_IDS.has(agent.industry_role_id ?? "")
  );
}

export function useRuntimeCenter() {
  const [surfaceData, setSurfaceData] =
    useState<RuntimeCenterSurfaceResponse | null>(() => runtimeCenterSurfaceCache);
  const [buddySummary, setBuddySummary] =
    useState<RuntimeMainBrainBuddySummary | null>(() => runtimeCenterBuddySummaryCache);
  const [loading, setLoading] = useState(() => runtimeCenterSurfaceCache == null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mainBrainHydrated, setMainBrainHydrated] = useState(
    () => runtimeCenterMainBrainHydratedCache,
  );
  const [mainBrainLoading, setMainBrainLoading] = useState(false);
  const [mainBrainError, setMainBrainError] = useState<string | null>(null);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RuntimeCenterDetailState | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const surfaceReloadTimerRef = useRef<number | null>(null);
  const pendingSectionsRef = useRef<Set<RuntimeSurfaceSection>>(new Set());
  const cardsRequestSeqRef = useRef(0);
  const mainBrainRequestSeqRef = useRef(0);
  const detailRequestSeqRef = useRef(0);

  const data = useMemo<RuntimeCenterOverviewPayload | null>(() => {
    if (!surfaceData) {
      return null;
    }
    return normalizeOverview({
      generated_at: surfaceData.generated_at,
      surface: surfaceData.surface,
      cards: surfaceData.cards,
    });
  }, [surfaceData]);
  const mainBrainData = useMemo<RuntimeMainBrainResponse | null>(
    () => surfaceData?.main_brain ?? null,
    [surfaceData],
  );
  const businessAgents = useMemo<RuntimeCenterAgentSummary[]>(
    () => (data ? deriveBusinessAgents(data) : []),
    [data],
  );
  const mainBrainUnavailable =
    mainBrainHydrated &&
    surfaceData !== null &&
    surfaceData.main_brain == null &&
    mainBrainError == null;
  const businessAgentsLoading = loading;
  const businessAgentsError = data ? null : error;

  const loadSurface = useCallback(
    async (
      mode: "initial" | "refresh" = "refresh",
      options?: { sections?: RuntimeSurfaceSection[] },
    ) => {
      const hasCachedSurface = runtimeCenterSurfaceCache !== null;
      const requestedSections = new Set<RuntimeSurfaceSection>(
        options?.sections ?? ["cards", "main_brain"],
      );
      const requestsCards = requestedSections.has("cards");
      const requestsMainBrain = requestedSections.has("main_brain");
      const cardsRequestSeq = requestsCards ? cardsRequestSeqRef.current + 1 : null;
      const mainBrainRequestSeq = requestsMainBrain
        ? mainBrainRequestSeqRef.current + 1
        : null;

      if (cardsRequestSeq !== null) {
        cardsRequestSeqRef.current = cardsRequestSeq;
      }
      if (mainBrainRequestSeq !== null) {
        mainBrainRequestSeqRef.current = mainBrainRequestSeq;
      }

      if (requestsCards && mode === "initial" && !hasCachedSurface) {
        setLoading(true);
      } else if (requestsCards) {
        setRefreshing(true);
      }
      if (requestsMainBrain) {
        setMainBrainLoading(true);
        setMainBrainError(null);
      }
      try {
        const requestOptions = options?.sections?.length
          ? { sections: options.sections }
          : undefined;
        const payload = requestOptions
          ? await requestRuntimeSurface<RuntimeCenterSurfaceResponse>(
              requestOptions,
            )
          : await requestRuntimeSurface<RuntimeCenterSurfaceResponse>();
        const canApplyCards =
          cardsRequestSeq !== null && cardsRequestSeqRef.current === cardsRequestSeq;
        const canApplyMainBrain =
          mainBrainRequestSeq !== null &&
          mainBrainRequestSeqRef.current === mainBrainRequestSeq;
        const hasStaleSection =
          (requestsCards && !canApplyCards) ||
          (requestsMainBrain && !canApplyMainBrain);
        if (!canApplyCards && !canApplyMainBrain) {
          return;
        }
        setSurfaceData((previous) => ({
          generated_at: hasStaleSection
            ? previous?.generated_at ?? payload.generated_at
            : payload.generated_at,
          surface: hasStaleSection
            ? previous?.surface ?? payload.surface
            : payload.surface,
          cards: canApplyCards
            ? payload.cards
            : previous?.cards ?? [],
          main_brain: canApplyMainBrain
            ? payload.main_brain
            : previous?.main_brain ?? null,
        }));
        runtimeCenterSurfaceCache = {
          generated_at: hasStaleSection
            ? runtimeCenterSurfaceCache?.generated_at ?? payload.generated_at
            : payload.generated_at,
          surface: hasStaleSection
            ? runtimeCenterSurfaceCache?.surface ?? payload.surface
            : payload.surface,
          cards: canApplyCards
            ? payload.cards
            : runtimeCenterSurfaceCache?.cards ?? [],
          main_brain: canApplyMainBrain
            ? payload.main_brain
            : runtimeCenterSurfaceCache?.main_brain ?? null,
        };
        if (canApplyMainBrain) {
          const nextBuddySummary = payload.main_brain?.buddy_summary ?? null;
          setBuddySummary(nextBuddySummary);
          runtimeCenterBuddySummaryCache = nextBuddySummary;
          setMainBrainHydrated(true);
          runtimeCenterMainBrainHydratedCache = true;
        }
        if (canApplyCards) {
          setError(null);
        }
        if (
          canApplyCards &&
          !requestsMainBrain &&
          !runtimeCenterMainBrainHydratedCache &&
          payload.surface
        ) {
          void loadSurface("refresh", { sections: ["main_brain"] });
        }
      } catch (err) {
        const detail = localizeRuntimeText(
          err instanceof Error ? err.message : String(err),
        );
        if (
          requestsCards &&
          cardsRequestSeq !== null &&
          cardsRequestSeqRef.current === cardsRequestSeq
        ) {
          setError(detail);
        }
        if (
          requestsMainBrain &&
          mainBrainRequestSeq !== null &&
          mainBrainRequestSeqRef.current === mainBrainRequestSeq
        ) {
          setMainBrainError(detail);
        }
        if (
          mode === "initial" &&
          requestsCards &&
          cardsRequestSeq !== null &&
          cardsRequestSeqRef.current === cardsRequestSeq
        ) {
          setSurfaceData(null);
        }
      } finally {
        if (
          requestsCards &&
          cardsRequestSeq !== null &&
          cardsRequestSeqRef.current === cardsRequestSeq
        ) {
          setLoading(false);
          setRefreshing(false);
        }
        if (
          requestsMainBrain &&
          mainBrainRequestSeq !== null &&
          mainBrainRequestSeqRef.current === mainBrainRequestSeq
        ) {
          setMainBrainLoading(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    void loadSurface("initial", { sections: ["cards"] });
  }, [loadSurface]);

  // Subscribe to the global event bus instead of opening a dedicated SSE
  // connection. The global bus (started in main.tsx) already connects to
  // /runtime-center/events and handles reconnection with back-off.
  useEffect(() => {
    const scheduleReload = (sections: RuntimeSurfaceSection[]) => {
      sections.forEach((section) => pendingSectionsRef.current.add(section));
      if (surfaceReloadTimerRef.current !== null) {
        window.clearTimeout(surfaceReloadTimerRef.current);
      }
      surfaceReloadTimerRef.current = window.setTimeout(() => {
        surfaceReloadTimerRef.current = null;
        const pendingSections = Array.from(pendingSectionsRef.current);
        pendingSectionsRef.current.clear();
        void loadSurface("refresh", { sections: pendingSections });
      }, 250);
    };

    const unsub = subscribe("*", (event) => {
      if (event.event_name.endsWith(".heartbeat")) {
        return;
      }
      const topic = event.event_name.split(".", 1)[0] ?? "";
      const sections = new Set<RuntimeSurfaceSection>();
      if (topic === "agent" || topic === "actor" || topic === "task") {
        sections.add("cards");
      }
      if (
        topic === "assignment" ||
        topic === "report" ||
        topic === "industry" ||
        topic === "cycle" ||
        topic === "backlog" ||
        topic === "strategy"
      ) {
        sections.add("main_brain");
      }
      if (
        topic === "governance" ||
        topic === "decision" ||
        topic === "patch" ||
        topic === "learning" ||
        topic === "recovery" ||
        topic === "automation" ||
        topic === "schedule"
      ) {
        sections.add("cards");
        sections.add("main_brain");
      }
      if (sections.size === 0) {
        return;
      }
      scheduleReload(Array.from(sections));
    });

    return () => {
      unsub();
      if (surfaceReloadTimerRef.current !== null) {
        window.clearTimeout(surfaceReloadTimerRef.current);
        surfaceReloadTimerRef.current = null;
      }
    };
  }, [loadSurface]);

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
        await loadSurface("refresh");
      } catch (err) {
        const detail = localizeRuntimeText(
          err instanceof Error ? err.message : String(err),
        );
        message.error(detail);
      } finally {
        setBusyActionId(null);
      }
    },
    [loadSurface],
  );

  const openDetail = useCallback(async (route: string, title: string) => {
    const detailRequestSeq = detailRequestSeqRef.current + 1;
    detailRequestSeqRef.current = detailRequestSeq;
    setDetailLoading(true);
    setDetailError(null);
    try {
      const payload = await requestRuntimeRecord<Record<string, unknown>>(route);
      if (detailRequestSeqRef.current !== detailRequestSeq) {
        return;
      }
      setDetail({
        route,
        title,
        payload,
      });
    } catch (err) {
      if (detailRequestSeqRef.current !== detailRequestSeq) {
        return;
      }
      const detailMessage = localizeRuntimeText(
        err instanceof Error ? err.message : String(err),
      );
      setDetailError(detailMessage);
      message.error(detailMessage);
    } finally {
      if (detailRequestSeqRef.current === detailRequestSeq) {
        setDetailLoading(false);
      }
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
    buddySummary,
    mainBrainData,
    mainBrainError,
    mainBrainLoading,
    mainBrainUnavailable,
    businessAgents,
    businessAgentsLoading,
    businessAgentsError,
    busyActionId,
    detail,
    detailLoading,
    detailError,
    reload: () => loadSurface(),
    invokeAction,
    openDetail,
    closeDetail,
  };
}

export function resetRuntimeCenterSurfaceCache(): void {
  runtimeCenterSurfaceCache = null;
  runtimeCenterBuddySummaryCache = null;
  runtimeCenterMainBrainHydratedCache = false;
}
