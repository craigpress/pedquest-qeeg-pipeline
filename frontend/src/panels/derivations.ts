/**
 * Frontend-computed derived traces.
 *
 * Persyst's Comprehensive panel references boolean spike-event expressions
 * (left-only, right-only, bilateral, generalized) backed by its own
 * `EventDensity Spike <region-list> <Detector,Count_epoch>` engines. Our
 * backend does not emit those columns — instead we approximate them from the
 * per-second spike counters already produced by `spike_density` (I143/I145).
 *
 * Threshold: Persyst uses `>= 3 events per epoch`. With a 2-s spike-detector
 * epoch (per SpikeDensityV1 convention), `>= 3 per epoch` ≈ `>= 1.5 per second`.
 * This is surfaced to the clinician via the row's info-panel description.
 */

import type { EpochData } from "@/types/api";

export const SPIKE_PER_SEC_THRESHOLD = 1.5;

export type BooleanStripSeries = {
  hours: number[];
  /** 0 = inactive (not drawn), 1 = active. Nulls propagate from missing data. */
  values: (number | null)[];
};

function readCol(data: EpochData, col: string): (number | null)[] | null {
  const v = data.columns[col];
  return v ?? null;
}

function binaryFromPredicate(
  hours: number[],
  predicate: (i: number) => boolean | null,
): BooleanStripSeries {
  const values: (number | null)[] = new Array(hours.length);
  for (let i = 0; i < hours.length; i++) {
    const p = predicate(i);
    values[i] = p === null ? null : p ? 1 : 0;
  }
  return { hours, values };
}

/** Left-hemisphere spikes AND NOT right-hemisphere spikes. */
export function spike_left_only(data: EpochData): BooleanStripSeries {
  const L = readCol(data, "spike_left_per_sec");
  const R = readCol(data, "spike_right_per_sec");
  const T = SPIKE_PER_SEC_THRESHOLD;
  return binaryFromPredicate(data.hours, (i) => {
    const l = L?.[i];
    const r = R?.[i];
    if (l == null || r == null) return null;
    return l >= T && !(r >= T);
  });
}

/** Right-hemisphere spikes AND NOT left-hemisphere spikes. */
export function spike_right_only(data: EpochData): BooleanStripSeries {
  const L = readCol(data, "spike_left_per_sec");
  const R = readCol(data, "spike_right_per_sec");
  const T = SPIKE_PER_SEC_THRESHOLD;
  return binaryFromPredicate(data.hours, (i) => {
    const l = L?.[i];
    const r = R?.[i];
    if (l == null || r == null) return null;
    return r >= T && !(l >= T);
  });
}

/** Both hemispheres active simultaneously. */
export function spike_bilateral(data: EpochData): BooleanStripSeries {
  const L = readCol(data, "spike_left_per_sec");
  const R = readCol(data, "spike_right_per_sec");
  const T = SPIKE_PER_SEC_THRESHOLD;
  return binaryFromPredicate(data.hours, (i) => {
    const l = L?.[i];
    const r = R?.[i];
    if (l == null || r == null) return null;
    return l >= T && r >= T;
  });
}

/** Generalized spikes (midline / bilateral synchronous discharges). */
export function spike_generalized(data: EpochData): BooleanStripSeries {
  const G = readCol(data, "spike_generalized_per_sec");
  const T = SPIKE_PER_SEC_THRESHOLD;
  return binaryFromPredicate(data.hours, (i) => {
    const g = G?.[i];
    if (g == null) return null;
    return g >= T;
  });
}

export const DERIVED_FUNCTIONS = {
  spike_left_only,
  spike_right_only,
  spike_bilateral,
  spike_generalized,
} as const;

/** Families needed to compute any derived function. */
export const DERIVED_REQUIRED_FAMILIES = ["spike_density"] as const;
