/**
 * Dispatcher: picks the right renderer for a SubChartGroup based on the
 * group's `kind`. Kept deliberately thin — renderers own all chart logic.
 */

import type { SubChartGroup, SpectrogramType } from "@/panels/types";
import type { EpochData, SpectrogramData } from "@/types/api";
import { LineGroup } from "./renderers/LineGroup";
import { FilledAreaGroup } from "./renderers/FilledAreaGroup";
import { SpectrogramGroup } from "./renderers/SpectrogramGroup";
import { AeegEnvelopeGroup } from "./renderers/AeegEnvelopeGroup";
import { BsrLineGroup } from "./renderers/BsrLineGroup";
import { BarsGroup } from "./renderers/BarsGroup";
import { BooleanStripGroup } from "./renderers/BooleanStripGroup";

interface Props {
  group: SubChartGroup;
  data: EpochData | null;
  spectrograms: Partial<Record<SpectrogramType, SpectrogramData | null>>;
  /** True only for the first spectrogram in a panel — shows the colorscale picker. */
  showColorPicker?: boolean;
  /** Pre-computed shared colour bounds (e.g. FFT Left/Right sharing the same
   *  min/max) so paired spectrograms are directly visually comparable. */
  sharedBounds?: { min: number; max: number };
}

export function SubChart({ group, data, spectrograms, showColorPicker, sharedBounds }: Props) {
  switch (group.kind) {
    case "line":
      return <LineGroup group={group} data={data} />;
    case "filled_area":
      return <FilledAreaGroup group={group} data={data} />;
    case "spectrogram":
      return (
        <SpectrogramGroup
          group={group}
          spectrograms={spectrograms}
          showColorPicker={showColorPicker}
          sharedBounds={sharedBounds}
        />
      );
    case "aeeg_envelope":
      return <AeegEnvelopeGroup group={group} data={data} />;
    case "bsr_line":
      return <BsrLineGroup group={group} data={data} />;
    case "bars":
      return <BarsGroup group={group} data={data} />;
    case "boolean_strip":
      return <BooleanStripGroup group={group} data={data} />;
    default:
      return (
        <div className="p-2 text-xs text-muted-foreground">
          Unsupported sub-chart kind: {group.kind}
        </div>
      );
  }
}
