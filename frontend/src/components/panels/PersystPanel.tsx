/**
 * Renders a single Persyst-style panel from the manifest.
 *
 * For the given `panelId`:
 *  1. Resolve the manifest (all 8 panels built at module load).
 *  2. Compute the union of backend column families the sub-charts need,
 *     issue a single `usePatientData` call, and hand the epoch bundle down.
 *  3. Fetch exactly the spectrograms this panel uses via
 *     `useSpectrogramBundle` — not the global 9-spectrogram set.
 *  4. Dispatch each SubChartGroup to the right renderer.
 *
 * The first spectrogram in each panel exposes the colorscale picker (header
 * `headerExtra`); subsequent spectrograms follow the shared selection.
 */

import { useEffect, useMemo, useState } from "react";
import { findPanel } from "@/panels/manifest";
import { familiesForColumn } from "@/panels/columnResolver";
import { useAppStore } from "@/stores/appStore";
import { usePatientData } from "@/hooks/usePatientData";
import { spectrogramTypesForPanel, useSpectrogramBundle } from "@/hooks/useSpectrogramBundle";
import { SubChart } from "./SubChart";
import { DERIVED_REQUIRED_FAMILIES } from "@/panels/derivations";
import { ChartContainer } from "@/components/charts/shared/ChartContainer";
import { useCursorTracking } from "@/hooks/useCursorTracking";
import { getOverlayData } from "@/api/client";
import type { SpectrogramData } from "@/types/api";
import type { SpectrogramType } from "@/panels/types";

/** Pairs of spectrogram types that must share colour bounds. FFT Left/Right
 *  are the canonical case — raw absolute power side-by-side is only
 *  interpretable if both panels normalise to the same range. */
const SHARED_BOUND_PAIRS: SpectrogramType[][] = [["fft_left", "fft_right"]];

function computeSharedBounds(
  specs: Partial<Record<SpectrogramType, SpectrogramData | null>>,
): Map<SpectrogramType, { min: number; max: number }> {
  const map = new Map<SpectrogramType, { min: number; max: number }>();
  for (const pair of SHARED_BOUND_PAIRS) {
    let sharedMin = Infinity;
    let sharedMax = -Infinity;
    let any = false;
    for (const t of pair) {
      const d = specs[t];
      if (!d || !d.matrix) continue;
      for (const row of d.matrix) {
        if (!row) continue;
        for (const v of row) {
          if (typeof v === "number" && !isNaN(v)) {
            if (v < sharedMin) sharedMin = v;
            if (v > sharedMax) sharedMax = v;
            any = true;
          }
        }
      }
    }
    if (any && isFinite(sharedMin) && isFinite(sharedMax)) {
      for (const t of pair) map.set(t, { min: sharedMin, max: sharedMax });
    }
  }
  return map;
}

interface Props {
  panelId: string;
}

export function PersystPanel({ panelId }: Props) {
  const patientId = useAppStore((s) => s.patientId);
  const setOverlayData = useAppStore((s) => s.setOverlayData);
  const trackCursor = useCursorTracking();
  const panel = findPanel(panelId);

  useEffect(() => {
    if (!patientId) return;
    const controller = new AbortController();
    getOverlayData(patientId, controller.signal)
      .then(setOverlayData)
      .catch((err) => {
        if (!controller.signal.aborted) console.warn("Failed to load overlay data", err);
      });
    return () => controller.abort();
  }, [patientId, setOverlayData]);

  // Union of families needed across every column-backed trace + derived prerequisites.
  const families = useMemo(() => {
    if (!panel) return [];
    const set = new Set<string>();
    for (const g of panel.groups) {
      for (const r of g.rows) {
        for (const t of r.traces) {
          if (t.source.kind === "column") {
            for (const fam of familiesForColumn(t.source.key)) set.add(fam);
          } else if (t.source.kind === "derived") {
            for (const fam of DERIVED_REQUIRED_FAMILIES) set.add(fam);
          }
        }
      }
    }
    return Array.from(set).sort();
  }, [panel]);

  const columnKeys = useMemo(() => {
    if (!panel) return [];
    const set = new Set<string>();
    for (const g of panel.groups) {
      for (const r of g.rows) {
        for (const t of r.traces) {
          if (t.source.kind === "column") {
            set.add(t.source.key);
          } else if (t.source.kind === "derived") {
            set.add("spike_left_per_sec");
            set.add("spike_right_per_sec");
            set.add("spike_generalized_per_sec");
          }
        }
      }
    }
    return Array.from(set).sort();
  }, [panel]);

  const { data, error, pendingFamilies } = usePatientData(patientId, families, undefined, columnKeys);
  const { bundle: spectrograms, pendingSpectrograms } = useSpectrogramBundle(panel);
  const sharedBoundsMap = useMemo(() => computeSharedBounds(spectrograms), [spectrograms]);
  const anyPending = pendingFamilies.length > 0 || pendingSpectrograms.length > 0;
  const totalLoads = families.length + (panel ? spectrogramTypesForPanel(panel).length : 0);
  const pendingCount = pendingFamilies.length + pendingSpectrograms.length;
  const loadedCount = Math.max(0, totalLoads - pendingCount);
  const [loadingSeconds, setLoadingSeconds] = useState(0);

  useEffect(() => {
    if (!anyPending) {
      setLoadingSeconds(0);
      return;
    }
    setLoadingSeconds(0);
    const id = window.setInterval(() => setLoadingSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [anyPending, patientId, panelId]);

  if (!panel) {
    return (
      <ChartContainer title="Unknown panel" height={120}>
        <div className="p-3 text-xs text-destructive">Panel not found: {panelId}</div>
      </ChartContainer>
    );
  }

  return (
    <div className="space-y-2" onMouseMove={trackCursor}>
      {panel.description && (
        <div className="text-xs text-muted-foreground leading-relaxed px-1">{panel.description}</div>
      )}

      {error && (
        <div className="text-xs text-destructive px-1">Error loading epoch data: {error}</div>
      )}
      {anyPending && (
        <div
          className="rounded border border-border/70 bg-muted/20 px-2 py-1.5 text-xs text-muted-foreground"
          data-testid="family-loading-indicators"
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
              Loading panel data {loadedCount}/{totalLoads}
            </span>
            {loadingSeconds >= 3 && (
              <span>Large cached studies can take 30-60s on first load while parquet columns warm.</span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1">
          {pendingFamilies.map((fam) => (
            <span key={`fam-${fam}`} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
              Loading {fam}…
            </span>
          ))}
          {pendingSpectrograms.map((t) => (
            <span key={`spec-${t}`} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
              Loading {t} spectrogram…
            </span>
          ))}
          </div>
        </div>
      )}

      {panel.groups.map((group) => {
        // If this sub-chart is one half of a shared-bound pair, look up its bounds.
        let sharedBounds: { min: number; max: number } | undefined;
        if (group.kind === "spectrogram") {
          const specSource = group.rows[0]?.traces[0]?.source;
          if (specSource && specSource.kind === "spectrogram") {
            sharedBounds = sharedBoundsMap.get(specSource.specType);
          }
        }
        return (
          <SubChart
            key={group.groupId}
            group={group}
            data={data}
            spectrograms={spectrograms}
            showColorPicker={group.kind === "spectrogram"}
            sharedBounds={sharedBounds}
          />
        );
      })}
    </div>
  );
}
