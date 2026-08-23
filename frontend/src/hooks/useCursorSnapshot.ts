import { useEffect, useId, useRef } from "react";
import { useAppStore } from "@/stores/appStore";

export interface CursorEntry {
  label: string;
  value: number | null;
  unit?: string;
}

/**
 * Finds the data point nearest to cursorPct and pushes it to
 * ``appStore.cursorValues`` under a per-hook owner id so multiple charts can
 * all contribute values simultaneously instead of clobbering each other.
 *
 * The hook clears its own entries on unmount to keep the aggregate view clean
 * when panels change.
 */
export function useCursorSnapshot(
  chartData: Record<string, unknown>[],
  entries: Array<{ key: string; label: string; unit?: string }>,
) {
  const ownerId = useId();
  const cursorPct = useAppStore((s) => s.cursorPct);
  const setCursorValuesForOwner = useAppStore((s) => s.setCursorValuesForOwner);
  const clearCursorValuesForOwner = useAppStore((s) => s.clearCursorValuesForOwner);
  const summary = useAppStore((s) => s.patientSummary);

  const entriesRef = useRef(entries);
  entriesRef.current = entries;

  useEffect(() => {
    if (chartData.length === 0 || entriesRef.current.length === 0 || !summary) return;

    const roscOffset = Math.max(0, summary.time_axis?.hours_rosc_to_eeg ?? 0);
    const totalHours = roscOffset + summary.qc.recording_duration_hours;
    const targetHour = cursorPct * totalHours;

    const hours = chartData.map((d) => (d.hours as number) ?? 0);
    let nearest = 0;
    let minDist = Infinity;
    for (let i = 0; i < hours.length; i++) {
      const dist = Math.abs(hours[i] - targetHour);
      if (dist < minDist) { minDist = dist; nearest = i; }
    }

    const values: Record<string, CursorEntry> = {};
    for (const e of entriesRef.current) {
      values[e.key] = {
        label: e.label,
        value: (chartData[nearest]?.[e.key] ?? null) as number | null,
        unit: e.unit,
      };
    }
    setCursorValuesForOwner(ownerId, values);
  }, [ownerId, cursorPct, chartData, summary, setCursorValuesForOwner]);

  // Drop our entries from the aggregate view on unmount or when the hook
  // stops receiving data (e.g., the panel is switched out).
  useEffect(() => {
    return () => clearCursorValuesForOwner(ownerId);
  }, [ownerId, clearCursorValuesForOwner]);
}
