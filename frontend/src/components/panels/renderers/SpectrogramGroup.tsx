import type { SubChartGroup, SpectrogramType } from "@/panels/types";
import { SpectrogramCanvas } from "@/components/charts/SpectrogramCanvas";
import { ChartContainer } from "@/components/charts/shared/ChartContainer";
import { groupToMetadata } from "@/panels/groupMetadata";
import { useAppStore, type SpectrogramFamily } from "@/stores/appStore";
import { COLOR_SCALE_OPTIONS } from "@/lib/colorScales";
import { usePreRecordingGap } from "@/hooks/usePreRecordingGap";
import { SpectrogramOverlay } from "./overlays";
import type { SpectrogramData } from "@/types/api";

function familyForSpecType(specType: SpectrogramType): SpectrogramFamily {
  switch (specType) {
    case "fft_left":
    case "fft_right":
      return "fft";
    case "rhythmicity":
      return "rhythmicity";
    case "coherence":
      return "coherence";
    case "asymmetry":
    case "asymmetry_hemi":
    case "asymmetry_ant":
    case "asymmetry_post":
    case "asymmetry_temp":
    case "asymmetry_parasag":
      return "asymmetry";
  }
}

interface Props {
  group: SubChartGroup;
  spectrograms: Partial<Record<SpectrogramType, SpectrogramData | null>>;
  /** When true, show the colorscale dropdown in the chart header. */
  showColorPicker?: boolean;
  /** Pre-computed shared colour bounds, e.g. FFT Left/Right normalised to a
   *  common range so side-by-side visual comparison is faithful. */
  sharedBounds?: { min: number; max: number };
}

export function SpectrogramGroup({ group, spectrograms, showColorPicker, sharedBounds }: Props) {
  const scales = useAppStore((s) => s.spectrogramColorScales);
  const setColorScale = useAppStore((s) => s.setSpectrogramColorScale);
  const binEdges = useAppStore((s) => s.config.binEdges);

  // A group with >1 spectrogram rows is a validator bug; defensively render only the first.
  const row = group.rows.find((r) => r.kind === "spectrogram");
  if (!row) return null;
  const source = row.traces[0]?.source;
  if (!source || source.kind !== "spectrogram") return null;

  const family = familyForSpecType(source.specType);
  const userScale = scales[family];
  // Asymmetry is diverging: always render RdBu regardless of the stored
  // override (which is still preserved in state / localStorage).
  const effectiveScale = family === "asymmetry" ? "RdBu" : userScale;

  const data = spectrograms[source.specType];
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);
  const hoursStart = data?.hours?.[0] ?? 0;
  const hoursEnd = data?.hours?.[data.hours.length - 1] ?? 0;
  const picker = showColorPicker ? (
    <select
      value={userScale}
      onChange={(e) => setColorScale(family, e.target.value)}
      className="bg-background border border-border rounded px-1.5 py-0.5 text-[13px] text-muted-foreground cursor-pointer"
    >
      {COLOR_SCALE_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  ) : null;

  return (
    <ChartContainer title={group.label} height="auto" headerExtra={picker} metadata={groupToMetadata(group)}>
      {data ? (
        <div style={{ position: "relative" }}>
          <SpectrogramCanvas
            data={data}
            height={group.height}
            colorScale={data.colorscale === "RdBu" ? "RdBu" : effectiveScale}
            sharedMin={sharedBounds?.min}
            sharedMax={sharedBounds?.max}
          />
          <SpectrogramOverlay
            hoursStart={hoursStart}
            hoursEnd={hoursEnd}
            binEdges={binEdges}
            gapEnd={gapEnd}
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-center text-xs text-muted-foreground"
          style={{ height: group.height }}
        >
          Loading…
        </div>
      )}
    </ChartContainer>
  );
}
