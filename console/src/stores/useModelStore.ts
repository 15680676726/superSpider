import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import api from "../api";
import type {
  ProviderInfo,
  ActiveModelsInfo,
  ProviderFallbackConfig,
} from "../api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelState {
  /** All known providers (built-in + custom). */
  providers: ProviderInfo[];
  /** Currently active model slot + fallback resolution info. */
  activeModels: ActiveModelsInfo | null;
  /** Fallback chain configuration. */
  fallbackConfig: ProviderFallbackConfig | null;
  /** Loading flag for the initial fetch. */
  loading: boolean;
  /** Last error message. */
  error: string | null;
}

interface ModelActions {
  /** Fetch providers + active models + fallback config. */
  load: () => Promise<void>;
  /** Refresh only active models (after switching model). */
  refreshActiveModels: () => Promise<void>;
  /** Patch providers list (e.g. after event bus notification). */
  setProviders: (providers: ProviderInfo[]) => void;
  /** Patch active models (e.g. after event bus notification). */
  setActiveModels: (activeModels: ActiveModelsInfo) => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useModelStore = create<ModelState & ModelActions>()(
  immer((set, get) => ({
    // --- state ---
    providers: [],
    activeModels: null,
    fallbackConfig: null,
    loading: false,
    error: null,

    // --- actions ---
    load: async () => {
      if (get().loading) return;
      set((s) => {
        s.loading = true;
        s.error = null;
      });
      try {
        const [providers, active, fallback] = await Promise.allSettled([
          api.listProviders(),
          api.getActiveModels(),
          api.getProviderFallback(),
        ]);
        set((s) => {
          if (providers.status === "fulfilled") {
            s.providers = providers.value;
          }
          if (active.status === "fulfilled") {
            s.activeModels = active.value;
          }
          if (fallback.status === "fulfilled") {
            s.fallbackConfig = fallback.value;
          }
          s.loading = false;
        });
      } catch (err) {
        set((s) => {
          s.loading = false;
          s.error =
            err instanceof Error ? err.message : "Failed to load models";
        });
      }
    },

    refreshActiveModels: async () => {
      try {
        const active = await api.getActiveModels();
        set((s) => {
          s.activeModels = active;
        });
      } catch {
        // silent
      }
    },

    setProviders: (providers) => {
      set((s) => {
        s.providers = providers;
      });
    },

    setActiveModels: (activeModels) => {
      set((s) => {
        s.activeModels = activeModels;
      });
    },
  })),
);
