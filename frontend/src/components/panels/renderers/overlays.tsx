/**
 * Shared chart overlays — artifact regions, bin boundaries, pre-recording
 * gap, gap null breaks. Every line-style renderer drops these in so the new
 * panel stack preserves the functional parity described in the plan.
 */

import { ReferenceArea, ReferenceLine } from "recharts";
import { useAppStore } from "@/stores/appStore";

interface OverlayOpts {
  binEdges: number[];
  gapEnd: number | null | undefined;
}

/** Bin boundaries: vertical dashed lines at each interior edge. */
export function BinBoundaries({ binEdges }: { binEdges: number[] }) {
  const visible = useAppStore((s) => s.overlayVisibility.binBoundaries);
  if (!visible) return null;
  return (
    <>
      {binEdges.slice(1, -1).map((edge) => (
        <ReferenceLine
          key={`bin-${edge}`}
          x={edge}
          stroke="var(--muted-foreground)"
          strokeDasharray="2 4"
          strokeOpacity={0.3}
        />
      ))}
    </>
  );
}

/** Pre-recording gap: shaded region at the start of the axis up to gapEnd. */
export function PreRecordingGap({ gapEnd }: { gapEnd: number | null | undefined }) {
  if (gapEnd == null) return null;
  return (
    <ReferenceArea
      x1={0}
      x2={gapEnd}
      fill="var(--muted-foreground)"
      fillOpacity={0.15}
      label={{
        value: "No EEG data",
        position: "insideTop",
        fontSize: 9,
        fill: "var(--muted-foreground)",
      }}
    />
  );
}

/** Vertical cursor line at the current shared cursor position. */
export function CursorLine({ cursorHours }: { cursorHours: number }) {
  if (!cursorHours && cursorHours !== 0) return null;
  return (
    <ReferenceLine
      x={cursorHours}
      stroke="var(--foreground)"
      strokeWidth={1}
      strokeOpacity={0.8}
      ifOverflow="visible"
    />
  );
}

function ArtifactAndGapRegions() {
  const overlayData = useAppStore((s) => s.overlayData);
  const showArtifacts = useAppStore((s) => s.overlayVisibility.artifacts);
  const showGaps = useAppStore((s) => s.overlayVisibility.gaps);
  if (!overlayData) return null;
  return (
    <>
      {showGaps && overlayData.gap_regions.map((r, idx) => (
        <ReferenceArea
          key={`gap-${idx}-${r.start_hours}`}
          x1={r.start_hours}
          x2={r.end_hours}
          fill="var(--muted-foreground)"
          fillOpacity={0.12}
          stroke="var(--muted-foreground)"
          strokeOpacity={0.25}
        />
      ))}
      {showArtifacts && overlayData.artifact_regions.map((r, idx) => (
        <ReferenceArea
          key={`artifact-${idx}-${r.start_hours}`}
          x1={r.start_hours}
          x2={r.end_hours}
          fill="var(--destructive)"
          fillOpacity={0.08}
          stroke="var(--destructive)"
          strokeOpacity={0.18}
        />
      ))}
    </>
  );
}

/** Convenience: render both overlays together. */
export function ChartOverlays({ binEdges, gapEnd }: OverlayOpts) {
  return (
    <>
      <PreRecordingGap gapEnd={gapEnd} />
      <ArtifactAndGapRegions />
      <BinBoundaries binEdges={binEdges} />
    </>
  );
}

/**
 * Absolute-positioned artifact/gap/bin overlays for the spectrogram canvas.
 *
 * The spectrogram is a raw `<canvas>` (not Recharts), so Recharts
 * `<ReferenceArea>` cannot be used. This renders colored vertical bands as
 * absolutely-positioned divs over the canvas wrapper. `hoursStart` and
 * `hoursEnd` are the canvas time-axis bounds; regions outside that window
 * are clipped.
 */
export function SpectrogramOverlay({
  hoursStart,
  hoursEnd,
  binEdges,
  gapEnd,
}: {
  hoursStart: number;
  hoursEnd: number;
  binEdges: number[];
  gapEnd: number | null | undefined;
}) {
  const overlayData = useAppStore((s) => s.overlayData);
  const showArtifacts = useAppStore((s) => s.overlayVisibility.artifacts);
  const showGaps = useAppStore((s) => s.overlayVisibility.gaps);
  const showBins = useAppStore((s) => s.overlayVisibility.binBoundaries);

  const range = hoursEnd - hoursStart;
  if (!(range > 0)) return null;

  const pct = (h: number) => ((h - hoursStart) / range) * 100;
  const clampedBandPct = (s: number, e: number) => {
    const lo = Math.max(0, Math.min(100, pct(s)));
    const hi = Math.max(0, Math.min(100, pct(e)));
    return { left: `${Math.min(lo, hi)}%`, width: `${Math.max(0, hi - lo)}%` };
  };

  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
      }}
    >
      {gapEnd != null && gapEnd > hoursStart && (
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            ...clampedBandPct(hoursStart, Math.min(gapEnd, hoursEnd)),
            background: "var(--muted-foreground)",
            opacity: 0.15,
          }}
        />
      )}
      {showGaps &&
        overlayData?.gap_regions.map((r, idx) => (
          <div
            key={`spec-gap-${idx}-${r.start_hours}`}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              ...clampedBandPct(r.start_hours, r.end_hours),
              background: "var(--muted-foreground)",
              opacity: 0.12,
              borderLeft: "1px solid var(--muted-foreground)",
              borderRight: "1px solid var(--muted-foreground)",
            }}
          />
        ))}
      {showArtifacts &&
        overlayData?.artifact_regions.map((r, idx) => (
          <div
            key={`spec-artifact-${idx}-${r.start_hours}`}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              ...clampedBandPct(r.start_hours, r.end_hours),
              background: "var(--destructive)",
              opacity: 0.08,
              borderLeft: "1px solid var(--destructive)",
              borderRight: "1px solid var(--destructive)",
            }}
          />
        ))}
      {showBins &&
        binEdges.slice(1, -1).map((edge) => (
          <div
            key={`spec-bin-${edge}`}
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: `${pct(edge)}%`,
              width: 0,
              borderLeft: "1px dashed var(--muted-foreground)",
              opacity: 0.3,
            }}
          />
        ))}
    </div>
  );
}
