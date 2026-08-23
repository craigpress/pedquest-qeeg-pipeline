/** Hook for synchronized time axis across all chart panels. */
import { useCallback } from "react";
import { useAppStore } from "@/stores/appStore";

export interface TimeSyncState {
  domain: [number, number] | null;
  setDomain: (domain: [number, number] | null) => void;
  resetZoom: () => void;
}

export function useTimeSync(): TimeSyncState {
  const domain = useAppStore((s) => s.timeDomain);
  const setDomain = useAppStore((s) => s.setTimeDomain);

  const resetZoom = useCallback(() => {
    setDomain(null);
  }, [setDomain]);

  return { domain, setDomain, resetZoom };
}
