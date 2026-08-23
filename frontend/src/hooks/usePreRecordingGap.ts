/**
 * Compute the pre-recording gap when ROSC precedes the first EEG epoch.
 *
 * Returns { gapEnd } if hours[0] > 0 and time axis is ROSC-referenced,
 * meaning there's a gap from 0h to the first data point that should
 * be visually indicated on charts.
 */
import { useAppStore } from "@/stores/appStore";

interface PreRecordingGap {
  /** End of the gap (hours); start is always 0. Null if no gap. */
  gapEnd: number | null;
}

export function usePreRecordingGap(firstHour: number | undefined): PreRecordingGap {
  const summary = useAppStore((s) => s.patientSummary);

  // Only show gap when time axis is ROSC-referenced and data starts after 0h
  const isRoscReferenced = summary?.time_axis?.reference === "rosc";
  const hasGap = isRoscReferenced && firstHour != null && firstHour > 0.5;

  return { gapEnd: hasGap ? firstHour : null };
}
