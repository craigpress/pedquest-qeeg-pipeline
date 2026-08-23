/**
 * Fetches exactly the spectrogram bundle required by the active Persyst panel,
 * not the full 9-spectrogram set. Replaces the eager `useEffect` previously in
 * `PatientDashboard` so switching panels doesn't reload spectrograms the new
 * panel doesn't use.
 */

import { useEffect, useState } from "react";
import { useAppStore } from "@/stores/appStore";
import { getSpectrogram } from "@/api/client";
import type { SpectrogramData } from "@/types/api";
import type { PanelManifest, SpectrogramType } from "@/panels/types";

const spectrogramCache = new Map<string, SpectrogramData | null>();

function spectrogramKey(patientId: string, type: SpectrogramType, reprocessTrigger: number): string {
  return `${patientId}:${reprocessTrigger}:${type}`;
}

export function spectrogramTypesForPanel(panel: PanelManifest): SpectrogramType[] {
  const set = new Set<SpectrogramType>();
  for (const g of panel.groups) {
    for (const r of g.rows) {
      for (const t of r.traces) {
        if (t.source.kind === "spectrogram") set.add(t.source.specType);
      }
    }
  }
  return Array.from(set);
}

export interface SpectrogramBundleResult {
  bundle: Partial<Record<SpectrogramType, SpectrogramData | null>>;
  pendingSpectrograms: SpectrogramType[];
}

export function useSpectrogramBundle(
  panel: PanelManifest | null,
): SpectrogramBundleResult {
  const patientId = useAppStore((s) => s.patientId);
  const reprocessTrigger = useAppStore((s) => s.reprocessTrigger);
  const [bundle, setBundle] = useState<Partial<Record<SpectrogramType, SpectrogramData | null>>>({});
  const [pendingSpectrograms, setPendingSpectrograms] = useState<SpectrogramType[]>([]);

  useEffect(() => {
    setBundle({});
    if (!patientId || !panel) {
      setPendingSpectrograms([]);
      return;
    }

    const needed = spectrogramTypesForPanel(panel);
    const seeded: Partial<Record<SpectrogramType, SpectrogramData | null>> = {};
    const toFetch: SpectrogramType[] = [];
    for (const type of needed) {
      const key = spectrogramKey(patientId, type, reprocessTrigger);
      if (spectrogramCache.has(key)) {
        seeded[type] = spectrogramCache.get(key) ?? null;
      } else {
        toFetch.push(type);
      }
    }
    setBundle(seeded);
    setPendingSpectrograms(toFetch);

    if (toFetch.length === 0) return;

    const ctrl = new AbortController();
    const { signal } = ctrl;

    for (const type of toFetch) {
      getSpectrogram(patientId, type, signal)
        .then((d) => {
          if (signal.aborted) return;
          spectrogramCache.set(spectrogramKey(patientId, type, reprocessTrigger), d);
          while (spectrogramCache.size > 24) {
            const firstKey = spectrogramCache.keys().next().value;
            if (firstKey) spectrogramCache.delete(firstKey);
          }
          setBundle((b) => ({ ...b, [type]: d }));
          setPendingSpectrograms((prev) => prev.filter((t) => t !== type));
        })
        .catch(() => {
          if (signal.aborted) return;
          spectrogramCache.set(spectrogramKey(patientId, type, reprocessTrigger), null);
          setBundle((b) => ({ ...b, [type]: null }));
          setPendingSpectrograms((prev) => prev.filter((t) => t !== type));
        });
    }

    return () => ctrl.abort();
  }, [patientId, panel?.panelId, reprocessTrigger]);

  return { bundle, pendingSpectrograms };
}
