import { useEffect, useCallback } from "react";
import { useModelStore } from "../../../stores";
import { subscribe } from "../../../runtime/eventBus";

/**
 * Thin wrapper around `useModelStore` that:
 * 1. Triggers the initial load on mount.
 * 2. Subscribes to model-related event bus topics so the list
 *    refreshes automatically when the backend pushes changes.
 * 3. Exposes the same API surface the page already expects.
 */
export function useProviders() {
  const providers = useModelStore((s) => s.providers);
  const activeModels = useModelStore((s) => s.activeModels);
  const loading = useModelStore((s) => s.loading);
  const error = useModelStore((s) => s.error);
  const load = useModelStore((s) => s.load);
  // Initial load
  useEffect(() => {
    void load();
  }, [load]);

  // Auto-refresh when backend pushes model/provider events
  useEffect(() => {
    const unsub = subscribe("model", () => {
      void load();
    });
    const unsub2 = subscribe("provider", () => {
      void load();
    });
    return () => {
      unsub();
      unsub2();
    };
  }, [load]);

  const fetchAll = useCallback(
    async (_showLoading = true) => {
      await load();
    },
    [load],
  );

  return {
    providers,
    activeModels,
    loading,
    error,
    fetchAll,
  };
}
