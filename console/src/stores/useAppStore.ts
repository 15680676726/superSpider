import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import api from "../api";
import type { SystemOverview, GovernanceStatus } from "../api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AppState {
  /** Application version string from backend. */
  version: string;
  /** System overview snapshot. */
  systemOverview: SystemOverview | null;
  /** Global governance status. */
  governance: GovernanceStatus | null;
  /** Whether the initial bootstrap load is in progress. */
  bootstrapLoading: boolean;
  /** Last bootstrap error message, if any. */
  bootstrapError: string | null;
  /** Network connectivity status. */
  online: boolean;
}

interface AppActions {
  /** Load version + system overview in one shot. */
  bootstrap: () => Promise<void>;
  /** Refresh system overview only. */
  refreshSystemOverview: () => Promise<void>;
  /** Update online status (called by network detector). */
  setOnline: (online: boolean) => void;
  /** Patch governance status (called by event bus). */
  setGovernance: (governance: GovernanceStatus | null) => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState & AppActions>()(
  immer((set, get) => ({
    // --- state ---
    version: "",
    systemOverview: null,
    governance: null,
    bootstrapLoading: false,
    bootstrapError: null,
    online: typeof navigator !== "undefined" ? navigator.onLine : true,

    // --- actions ---
    bootstrap: async () => {
      if (get().bootstrapLoading) return;
      set((s) => {
        s.bootstrapLoading = true;
        s.bootstrapError = null;
      });
      try {
        const [versionRes, overview] = await Promise.allSettled([
          api.getVersion(),
          api.getSystemOverview(),
        ]);
        set((s) => {
          if (versionRes.status === "fulfilled") {
            s.version = versionRes.value?.version ?? "";
          }
          if (overview.status === "fulfilled") {
            s.systemOverview = overview.value;
          }
          s.bootstrapLoading = false;
        });
      } catch (err) {
        set((s) => {
          s.bootstrapLoading = false;
          s.bootstrapError =
            err instanceof Error ? err.message : "Bootstrap failed";
        });
      }
    },

    refreshSystemOverview: async () => {
      try {
        const overview = await api.getSystemOverview();
        set((s) => {
          s.systemOverview = overview;
        });
      } catch {
        // silent — callers can handle via the store error state if needed
      }
    },

    setOnline: (online) => {
      set((s) => {
        s.online = online;
      });
    },

    setGovernance: (governance) => {
      set((s) => {
        s.governance = governance;
      });
    },
  })),
);
