import { getApiUrl } from "../api/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RuntimeEvent {
  /** Backend event name, e.g. "actor.updated", "governance.changed". */
  event_name: string;
  /** Raw payload from the SSE data field. */
  payload: Record<string, unknown>;
  /** ISO timestamp from the event, if present. */
  timestamp?: string;
}

export type EventHandler = (event: RuntimeEvent) => void;

type Unsubscribe = () => void;

// ---------------------------------------------------------------------------
// Topic-based pub/sub
// ---------------------------------------------------------------------------

const subscribers = new Map<string, Set<EventHandler>>();
const wildcardSubscribers = new Set<EventHandler>();

/**
 * Subscribe to events matching a topic prefix.
 *
 * - `"*"` — receive all events
 * - `"actor"` — receive events whose `event_name` starts with `"actor."`
 * - `"actor.updated"` — exact match
 *
 * Returns an unsubscribe function.
 */
export function subscribe(topic: string, handler: EventHandler): Unsubscribe {
  if (topic === "*") {
    wildcardSubscribers.add(handler);
    return () => {
      wildcardSubscribers.delete(handler);
    };
  }
  let set = subscribers.get(topic);
  if (!set) {
    set = new Set();
    subscribers.set(topic, set);
  }
  set.add(handler);
  return () => {
    set!.delete(handler);
    if (set!.size === 0) subscribers.delete(topic);
  };
}

function dispatch(event: RuntimeEvent): void {
  const name = event.event_name || "";

  // Wildcard subscribers get everything
  wildcardSubscribers.forEach((handler) => {
    try {
      handler(event);
    } catch {
      // subscriber threw — ignore
    }
  });

  // Exact match
  subscribers.get(name)?.forEach((handler) => {
    try {
      handler(event);
    } catch {
      // ignore
    }
  });

  // Prefix match: "actor.updated" matches topic "actor"
  const dotIndex = name.indexOf(".");
  if (dotIndex > 0) {
    const prefix = name.slice(0, dotIndex);
    subscribers.get(prefix)?.forEach((handler) => {
      try {
        handler(event);
      } catch {
        // ignore
      }
    });
  }
}

function parseSSEData(raw: string): RuntimeEvent | null {
  if (!raw || !raw.trim()) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      event_name:
        typeof parsed.event_name === "string" ? parsed.event_name : "unknown",
      payload: parsed,
      timestamp:
        typeof parsed.timestamp === "string" ? parsed.timestamp : undefined,
    };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// SSE Connection Manager (singleton)
// ---------------------------------------------------------------------------

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const SSE_PATH = "/runtime-center/events";

let eventSource: EventSource | null = null;
let reconnectTimer: number | null = null;
let reconnectAttempt = 0;
let disposed = false;

function reconnectDelay(): number {
  const base = RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt);
  const jitter = Math.random() * RECONNECT_BASE_MS;
  return Math.min(base + jitter, RECONNECT_MAX_MS);
}

function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function connect(): void {
  if (disposed) return;
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  const source = new EventSource(getApiUrl(SSE_PATH));
  eventSource = source;

  const handleMessage: EventListener = (rawEvent) => {
    const message = rawEvent as MessageEvent<string>;
    const event = parseSSEData(message.data);
    if (!event) return;

    // Skip heartbeat events from triggering full dispatches
    if (event.event_name.endsWith(".heartbeat")) return;

    // Reset reconnect counter on successful message
    reconnectAttempt = 0;

    dispatch(event);
  };

  source.addEventListener("runtime", handleMessage);

  // Also listen for generic "message" events (some backends use default event)
  source.addEventListener("message", handleMessage);

  source.onopen = () => {
    reconnectAttempt = 0;
  };

  source.onerror = () => {
    source.removeEventListener("runtime", handleMessage);
    source.removeEventListener("message", handleMessage);
    source.close();

    if (eventSource === source) {
      eventSource = null;
    }

    if (disposed) return;

    clearReconnectTimer();
    const delay = reconnectDelay();
    reconnectAttempt = Math.min(reconnectAttempt + 1, 10);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Start the global SSE connection. Safe to call multiple times — only the
 * first call opens the connection. Subsequent calls are no-ops.
 */
export function startEventBus(): void {
  disposed = false;
  if (eventSource) return;
  connect();
}

/**
 * Stop the global SSE connection and clear all reconnect timers.
 */
export function stopEventBus(): void {
  disposed = true;
  clearReconnectTimer();
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  reconnectAttempt = 0;
}

/**
 * Whether the SSE connection is currently open.
 */
export function isEventBusConnected(): boolean {
  return eventSource !== null && eventSource.readyState === EventSource.OPEN;
}

/**
 * Manually emit an event into the bus (useful for testing or local events).
 */
export function emit(event: RuntimeEvent): void {
  dispatch(event);
}
