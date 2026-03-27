import { useEffect } from "react";
import { useAppStore } from "../stores";

/**
 * Hook that monitors browser online/offline events and syncs to useAppStore.
 * Mount once in the root component (e.g. App.tsx).
 */
export function useNetworkStatus(): boolean {
  const online = useAppStore((s) => s.online);
  const setOnline = useAppStore((s) => s.setOnline);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Sync initial state
    setOnline(navigator.onLine);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [setOnline]);

  return online;
}
