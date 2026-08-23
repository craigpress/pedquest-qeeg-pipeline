/** Hook for fetching and caching patient epoch data by column family.
 *  Missing families are requested together so the backend can satisfy a panel
 *  with one parquet read instead of many concurrent column-selective reads. */
import { useState, useEffect, useRef } from "react";
import { getEpochData } from "@/api/client";
import type { EpochData } from "@/types/api";

interface UsePatientDataResult {
  data: EpochData | null;
  loading: boolean;
  error: string | null;
  /** Families still in flight. Empty when all families have resolved. */
  pendingFamilies: string[];
}

/** Keyed by `${patientId}:${family}[:${columnFilter}][:${column list}]`. */
const familyCache = new Map<string, EpochData>();

function familyKey(
  patientId: string,
  family: string,
  columnFilter?: string,
  columns?: string[],
): string {
  const colKey = columns && columns.length > 0 ? `:${columns.join("|")}` : "";
  return `${patientId}:${family}${columnFilter ? `:${columnFilter}` : ""}${colKey}`;
}

/** Merge a newly-arrived family's EpochData into an accumulator. The first
 *  family establishes the hours axis; subsequent families align by index
 *  (backend emits the same hours grid for all families). */
function mergeFamily(acc: EpochData | null, next: EpochData): EpochData {
  if (!acc) return next;
  return {
    hours: acc.hours,
    usable: acc.usable,
    columns: { ...acc.columns, ...next.columns },
  };
}

export function usePatientData(
  patientId: string | null,
  families: string[],
  columnFilter?: string,
  columns?: string[],
): UsePatientDataResult {
  const [data, setData] = useState<EpochData | null>(null);
  const [pendingFamilies, setPendingFamilies] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!patientId || families.length === 0) {
      setData(null);
      setPendingFamilies([]);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Seed from cache; fetch only what's missing.
    let seeded: EpochData | null = null;
    const toFetch: string[] = [];
    for (const fam of families) {
      const cached = familyCache.get(familyKey(patientId, fam, columnFilter, columns));
      if (cached) {
        seeded = mergeFamily(seeded, cached);
      } else {
        toFetch.push(fam);
      }
    }
    setData(seeded);
    setPendingFamilies(toFetch);
    setError(null);

    if (toFetch.length === 0) return;

      getEpochData(patientId, toFetch, columnFilter, controller.signal, columns)
      .then((result) => {
        if (controller.signal.aborted) return;
        const cleaned = stripElectrodeChains(insertGapNulls(result));
        for (const fam of toFetch) {
          familyCache.set(familyKey(patientId, fam, columnFilter, columns), cleaned);
        }
        while (familyCache.size > 80) {
          const firstKey = familyCache.keys().next().value;
          if (firstKey) familyCache.delete(firstKey);
        }
        setData((prev) => mergeFamily(prev, cleaned));
        setPendingFamilies([]);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err.message);
        setPendingFamilies([]);
      });

    return () => controller.abort();
  }, [patientId, families.join(","), columnFilter, columns?.join(",")]);

  return { data, loading: pendingFamilies.length > 0, error, pendingFamilies };
}

/** Clear the epoch data cache (e.g., after re-processing). */
export function clearPatientDataCache(patientId?: string): void {
  if (patientId) {
    for (const key of familyCache.keys()) {
      if (key.startsWith(`${patientId}:`)) {
        familyCache.delete(key);
      }
    }
  } else {
    familyCache.clear();
  }
}

/** Remove per-electrode-chain variants (e.g. adr_f3c3p3) — only regional/hemisphere
 *  summaries are used in charts. Running-average columns (adr_avg_*, fft_avg2m_*)
 *  are KEPT because the Persyst panel manifest addresses them explicitly. */
const ELECTRODE_CHAIN_RE = /[a-z]{1,3}\d{1,2}[a-z]{1,3}\d{1,2}/;

function stripElectrodeChains(data: EpochData): EpochData {
  const cols: Record<string, (number | null)[]> = {};
  for (const [col, vals] of Object.entries(data.columns)) {
    if (!ELECTRODE_CHAIN_RE.test(col)) {
      cols[col] = vals;
    }
  }
  return { ...data, columns: cols };
}

/** Insert null sentinel rows at time gaps so Recharts breaks lines.
 *  Gap threshold adapts to actual data spacing: 3x the median inter-point
 *  interval, with a minimum of 3 minutes. This handles families with
 *  different cadences (10s epochs vs 64s FFT vs 2-min averages). */
function insertGapNulls(data: EpochData): EpochData {
  if (data.hours.length < 2) return data;

  // Compute adaptive threshold from median spacing
  const diffs: number[] = [];
  const sampleLimit = Math.min(data.hours.length - 1, 500);
  const step = Math.max(1, Math.floor((data.hours.length - 1) / sampleLimit));
  for (let i = step; i < data.hours.length; i += step) {
    diffs.push(data.hours[i] - data.hours[i - step]);
  }
  diffs.sort((a, b) => a - b);
  const medianDiff = diffs[Math.floor(diffs.length / 2)] || 0.003;
  const threshold = Math.max(medianDiff * 3, 0.05); // at least 3 min

  const newHours: number[] = [];
  const newUsable: boolean[] = [];
  const newColumns: Record<string, (number | null)[]> = {};
  const colNames = Object.keys(data.columns);
  for (const col of colNames) newColumns[col] = [];

  for (let i = 0; i < data.hours.length; i++) {
    if (i > 0 && data.hours[i] - data.hours[i - 1] > threshold) {
      const mid = (data.hours[i - 1] + data.hours[i]) / 2;
      newHours.push(mid);
      newUsable.push(false);
      for (const col of colNames) newColumns[col].push(null);
    }
    newHours.push(data.hours[i]);
    newUsable.push(data.usable[i]);
    for (const col of colNames) newColumns[col].push(data.columns[col][i]);
  }

  return { hours: newHours, usable: newUsable, columns: newColumns };
}
