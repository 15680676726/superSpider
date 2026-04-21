import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../api";
import {
  buildActorPulseItems,
  compareActorPriority,
  isInterestingActor,
  type ActorPulseItem,
  type RuntimeActorDetailPayload,
  type RuntimeActorRecord,
} from "../runtime/executionPulse";
import { subscribe } from "../runtime/eventBus";

interface ActorPulseSnapshot {
  taskId: string | null;
  mailboxId: string | null;
  checkpointId: string | null;
  queueDepth: number;
  errorSummary: string | null;
  resultSummary: string | null;
  heartbeatAt: string | null;
  stableSince: number;
}

interface UseRuntimeExecutionPulseOptions {
  actor?: string;
  maxItems?: number;
  preferredAgentId?: string | null;
  autoLoad?: boolean;
  enableEvents?: boolean;
  active?: boolean;
}

interface SharedPulseFetchResult {
  details: RuntimeActorDetailPayload[];
  error: string | null;
  fetchedAt: number;
}

interface SharedPulseFetchEntry {
  promise: Promise<SharedPulseFetchResult> | null;
  value: SharedPulseFetchResult | null;
  loadedAt: number;
}

const PULSE_EVENT_DEBOUNCE_MS = 400;
const PULSE_MIN_RELOAD_INTERVAL_MS = 2_000;
const PULSE_SHARED_FETCH_TTL_MS = 1_500;
const SHARED_PULSE_FETCHES = new Map<string, SharedPulseFetchEntry>();
const RELEVANT_PULSE_EVENT_PREFIXES = [
  "actor",
  "actor-mailbox",
  "decision",
  "environment",
  "governance",
  "recovery",
  "task",
] as const;

function pulseFetchCacheKey(
  maxItems: number,
  preferredAgentId?: string | null,
): string {
  return `${maxItems}:${preferredAgentId?.trim() || "*"}`;
}

function isRelevantPulseEventName(eventName: string | undefined): boolean {
  if (typeof eventName !== "string" || !eventName.trim()) {
    return false;
  }
  return RELEVANT_PULSE_EVENT_PREFIXES.some(
    (prefix) => eventName === prefix || eventName.startsWith(`${prefix}.`),
  );
}

async function fetchSharedPulseDetails(
  {
    maxItems,
    preferredAgentId,
    force,
  }: {
    maxItems: number;
    preferredAgentId?: string | null;
    force: boolean;
  },
): Promise<SharedPulseFetchResult> {
  const cacheKey = pulseFetchCacheKey(maxItems, preferredAgentId);
  const cached = SHARED_PULSE_FETCHES.get(cacheKey);
  const now = Date.now();
  if (!force) {
    if (cached?.promise) {
      return cached.promise;
    }
    if (
      cached?.value &&
      now - cached.loadedAt < PULSE_SHARED_FETCH_TTL_MS
    ) {
      return cached.value;
    }
  }

  const promise = (async (): Promise<SharedPulseFetchResult> => {
    const runtimes = await request<RuntimeActorRecord[]>("/runtime-center/actors?limit=50");
    const runtimeList = Array.isArray(runtimes) ? runtimes : [];
    const interesting = runtimeList.filter(isInterestingActor);
    const prioritized = prioritizeActors(interesting, preferredAgentId).slice(0, maxItems);
    if (prioritized.length === 0) {
      return {
        details: [],
        error: null,
        fetchedAt: Date.now(),
      };
    }
    const details = await Promise.allSettled(
      prioritized.map((runtime) =>
        request<RuntimeActorDetailPayload>(
          `/runtime-center/actors/${encodeURIComponent(runtime.agent_id)}?mailbox_limit=8&checkpoint_limit=8&lease_limit=4`,
        ),
      ),
    );
    const fulfilled = details
      .filter(
        (
          result,
        ): result is PromiseFulfilledResult<RuntimeActorDetailPayload> =>
          result.status === "fulfilled",
      )
      .map((result) => result.value);
    const failed = details.filter(
      (result): result is PromiseRejectedResult => result.status === "rejected",
    );
    return {
      details: fulfilled,
      error:
        failed.length > 0
          ? failed
              .map((result) =>
                result.reason instanceof Error
                  ? result.reason.message
                  : String(result.reason),
              )
              .join(" | ")
          : null,
      fetchedAt: Date.now(),
    };
  })();

  SHARED_PULSE_FETCHES.set(cacheKey, {
    promise,
    value: cached?.value ?? null,
    loadedAt: cached?.loadedAt ?? 0,
  });

  try {
    const value = await promise;
    SHARED_PULSE_FETCHES.set(cacheKey, {
      promise: null,
      value,
      loadedAt: value.fetchedAt,
    });
    return value;
  } catch (error) {
    SHARED_PULSE_FETCHES.set(cacheKey, {
      promise: null,
      value: cached?.value ?? null,
      loadedAt: cached?.loadedAt ?? 0,
    });
    throw error;
  }
}

function prioritizeActors(
  actors: RuntimeActorRecord[],
  preferredAgentId?: string | null,
): RuntimeActorRecord[] {
  const preferred = preferredAgentId?.trim() || null;
  const sorted = [...actors].sort(compareActorPriority);
  if (!preferred) {
    return sorted;
  }
  const preferredIndex = sorted.findIndex((item) => item.agent_id === preferred);
  if (preferredIndex >= 0) {
    const [preferredActor] = sorted.splice(preferredIndex, 1);
    sorted.unshift(preferredActor);
  }
  return sorted;
}

export function useRuntimeExecutionPulse(
  options: UseRuntimeExecutionPulseOptions = {},
) {
  const {
    maxItems = 4,
    preferredAgentId = null,
    autoLoad = true,
    enableEvents = true,
    active = true,
  } = options;
  const [items, setItems] = useState<ActorPulseItem[]>([]);
  const [loading, setLoading] = useState(Boolean(autoLoad && active));
  const [error, setError] = useState<string | null>(null);
  const itemsRef = useRef<ActorPulseItem[]>([]);
  const loadPulseRef = useRef<((force?: boolean) => Promise<void> | void) | null>(null);
  const reloadTimerRef = useRef<number | null>(null);
  const loadPromiseRef = useRef<Promise<void> | null>(null);
  const pendingReloadRef = useRef(false);
  const pendingForceReloadRef = useRef(false);
  const hiddenReloadRef = useRef(false);
  const lastLoadedAtRef = useRef(0);
  const snapshotRef = useRef<Map<string, ActorPulseSnapshot>>(new Map());

  const commitItems = useCallback((nextItems: ActorPulseItem[]) => {
    itemsRef.current = nextItems;
    setItems(nextItems);
  }, []);

  const schedulePendingReload = useCallback(() => {
    if (!active) {
      return;
    }
    if (loadPromiseRef.current !== null || reloadTimerRef.current !== null) {
      return;
    }
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      hiddenReloadRef.current = true;
      return;
    }
    const elapsed = Date.now() - lastLoadedAtRef.current;
    const delay = Math.max(
      PULSE_EVENT_DEBOUNCE_MS,
      PULSE_MIN_RELOAD_INTERVAL_MS - Math.max(elapsed, 0),
      0,
    );
    reloadTimerRef.current = window.setTimeout(() => {
      reloadTimerRef.current = null;
      if (!pendingReloadRef.current) {
        return;
      }
      const forceReload = pendingForceReloadRef.current;
      pendingReloadRef.current = false;
      pendingForceReloadRef.current = false;
      void loadPulseRef.current?.(forceReload);
    }, delay);
  }, [active]);

  const loadPulse = useCallback(async (force = false) => {
    if (!active) {
      setLoading(false);
      return;
    }
    if (loadPromiseRef.current !== null) {
      pendingReloadRef.current = true;
      pendingForceReloadRef.current = pendingForceReloadRef.current || force;
      return loadPromiseRef.current;
    }
    const elapsed = Date.now() - lastLoadedAtRef.current;
    if (!force && lastLoadedAtRef.current > 0 && elapsed < PULSE_MIN_RELOAD_INTERVAL_MS) {
      pendingReloadRef.current = true;
      schedulePendingReload();
      return;
    }
    const hadItems = itemsRef.current.length > 0;
    setLoading((current) => current || !hadItems);
    const task = (async () => {
    try {
      const result = await fetchSharedPulseDetails({
        maxItems,
        preferredAgentId,
        force,
      });
      if (result.details.length === 0) {
        if (result.error) {
          if (!hadItems) {
            snapshotRef.current = new Map();
            commitItems([]);
          }
          setError(result.error);
          return;
        }
        snapshotRef.current = new Map();
        commitItems([]);
        setError(null);
        return;
      }
      const pulse = buildActorPulseItems(
        result.details,
        snapshotRef.current,
        result.fetchedAt,
      );
      snapshotRef.current = pulse.snapshots as Map<string, ActorPulseSnapshot>;
      const orderedItems = [...pulse.items].sort((left, right) => {
        if (left.agentId === preferredAgentId) {
          return -1;
        }
        if (right.agentId === preferredAgentId) {
          return 1;
        }
        return 0;
      });
      commitItems(orderedItems);
      setError(result.error);
    } catch (err) {
      if (!hadItems) {
        snapshotRef.current = new Map();
        commitItems([]);
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      lastLoadedAtRef.current = Date.now();
      loadPromiseRef.current = null;
      setLoading(false);
      if (pendingReloadRef.current) {
        schedulePendingReload();
      }
    }
    })();
    loadPromiseRef.current = task;
    return task;
  }, [active, commitItems, maxItems, preferredAgentId, schedulePendingReload]);

  useEffect(() => {
    loadPulseRef.current = loadPulse;
  }, [loadPulse]);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    if (!active) {
      setLoading(false);
      return;
    }
    if (!autoLoad) {
      return;
    }
    pendingReloadRef.current = false;
    pendingForceReloadRef.current = false;
    hiddenReloadRef.current = false;
    void loadPulse(false);
  }, [active, autoLoad, loadPulse]);

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    const handleVisibilityChange = () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }
      if (hiddenReloadRef.current || pendingReloadRef.current) {
        hiddenReloadRef.current = false;
        pendingReloadRef.current = true;
        schedulePendingReload();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      if (reloadTimerRef.current !== null) {
        window.clearTimeout(reloadTimerRef.current);
        reloadTimerRef.current = null;
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [active, schedulePendingReload]);

  useEffect(() => {
    if (!active || !enableEvents) {
      return undefined;
    }
    const unsubscribe = subscribe("*", (event) => {
      if (!isRelevantPulseEventName(event.event_name)) {
        return;
      }
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        hiddenReloadRef.current = true;
        pendingReloadRef.current = true;
        return;
      }
      pendingReloadRef.current = true;
      schedulePendingReload();
    });
    return () => {
      unsubscribe();
    };
  }, [active, enableEvents, schedulePendingReload]);

  return {
    items,
    loading,
    error,
    reloadPulse: () => loadPulse(true),
  };
}
