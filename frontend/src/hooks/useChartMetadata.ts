import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { getChartMetadata } from "@/api/client";
import type { ChartPanelMetadata } from "@/types/api";

/**
 * Fetches chart metadata once per patient and caches it in appStore.
 * Call this once at the dashboard level; individual charts read via
 * the `usePanel` helper below.
 */
export function useChartMetadata() {
  const patientId = useAppStore((s) => s.patientId);
  const chartMetadata = useAppStore((s) => s.chartMetadata);
  const setChartMetadata = useAppStore((s) => s.setChartMetadata);

  useEffect(() => {
    if (!patientId) return;
    // Already cached for this patient
    if (chartMetadata) return;

    let stale = false;
    getChartMetadata(patientId)
      .then((data) => {
        if (!stale) setChartMetadata(data);
      })
      .catch(() => {
        // Non-fatal — charts render fine without metadata
      });
    return () => { stale = true; };
  }, [patientId, chartMetadata, setChartMetadata]);

  return chartMetadata;
}

/** Look up a single panel's metadata by panel_id. */
export function usePanelMetadata(panelId: string | undefined): ChartPanelMetadata | null {
  const chartMetadata = useAppStore((s) => s.chartMetadata);
  if (!panelId || !chartMetadata) return null;
  return chartMetadata.panels.find((p) => p.panel_id === panelId) ?? null;
}
