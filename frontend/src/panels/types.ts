/**
 * Persyst-style panel manifest types.
 *
 * A PanelManifest is an ordered list of SubChartGroups. Each group is a single
 * sub-chart that may overlay multiple traces (e.g. aEEG Left + aEEG Right →
 * blue/red/purple overlay on one chart). Groups come pre-resolved from the
 * Persyst `_OverlapPrevious` attribute at module load.
 */

export type InstrumentKind =
  | "line"
  | "filled_area"
  | "spectrogram"
  | "aeeg_envelope"
  | "bsr_line"
  | "bars"
  | "boolean_strip";

/** Where a single trace's data comes from. */
export type TraceSource =
  | { kind: "column"; key: string }
  | { kind: "spectrogram"; specType: SpectrogramType }
  | { kind: "derived"; fn: DerivedFn }
  | { kind: "missing"; reason: string };

export type SpectrogramType =
  | "fft_left"
  | "fft_right"
  | "asymmetry"
  | "asymmetry_hemi"
  | "asymmetry_ant"
  | "asymmetry_post"
  | "asymmetry_temp"
  | "asymmetry_parasag"
  | "rhythmicity"
  | "coherence";

export type DerivedFn =
  | "spike_left_only"
  | "spike_right_only"
  | "spike_bilateral"
  | "spike_generalized";

export interface TraceSpec {
  source: TraceSource;
  color: string;
  label: string;
  style?: "solid" | "dashed";
  fillOpacity?: number;
}

export interface InstrumentRow {
  /** Stable slug we assign (e.g. "aeeg_left_hemi"). */
  instrumentId: string;
  /** Exact Persyst instrument name from Trend panels.md. */
  persystName: string;
  /** Display label shown as sub-chart title. */
  label: string;
  unit: string;
  height: number;
  kind: InstrumentKind;
  yDomain?: [number, number];
  logScale?: boolean;
  thresholdY?: number;
  /** From Persyst `_OverlapPrevious` — `true` means overlay on the prior row's sub-chart. */
  overlapPrevious: boolean;
  description: string;
  /** Spectrograms only — used by validator to prevent duplicate Hz ranges in one group. */
  freqRange?: [number, number];
  traces: TraceSpec[];
}

export interface SubChartGroup {
  groupId: string;
  /** Composite label from grouped rows (e.g. "aEEG Left & Right Hemisphere"). */
  label: string;
  /** First row's kind decides which renderer handles the group. */
  kind: InstrumentKind;
  /** Max height across rows in the group. */
  height: number;
  rows: InstrumentRow[];
  /** Info-panel description composed from grouped rows. */
  description: string;
  /** Spectrograms only — validator enforces distinct ranges within a group. */
  freqRange?: [number, number];
}

export interface PanelManifest {
  panelId: string;
  displayName: string;
  description: string;
  groups: SubChartGroup[];
}
