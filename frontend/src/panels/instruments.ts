/**
 * Instrument row factories and the canonical colour palette for Persyst traces.
 *
 * Each factory returns an `InstrumentRow` with the correct `kind`, backend
 * column source, trace colours, and info-panel description. `manifest.ts`
 * composes these into the 8 target panels. Keeping every concrete row in one
 * module means colour/unit/height changes are a single-file edit.
 */

import type { InstrumentRow, TraceSpec } from "./types";
import { resolvePersystName } from "./columnResolver";

// --- Canonical clinical palette --------------------------------------------
export const LEFT = "#3b82f6"; //  blue
export const RIGHT = "#ef4444"; // red
// Where L+R overlay, the two semi-transparent lines mix to appear purple.
export const GENERALIZED = "#22c55e"; // green
export const BILATERAL = "#a855f7"; //   purple
export const LEFT_ONLY = "#f59e0b"; //   amber
export const RIGHT_ONLY = "#d946ef"; //  magenta
export const DELTA = "#8b5cf6"; //       violet
export const THETA = "#06b6d4"; //       cyan
export const ALPHA = "#22c55e"; //       green
export const BETA = "#f59e0b"; //        amber
export const EMG = "#22c55e";
export const EYE_V = "#3b82f6";
export const EYE_H = "#ef4444";

// --- Helpers ---------------------------------------------------------------

function columnTrace(
  persystName: string,
  label: string,
  color: string,
  style: "solid" | "dashed" = "solid",
): TraceSpec {
  const key = resolvePersystName(persystName);
  return {
    source: key
      ? { kind: "column", key }
      : { kind: "missing", reason: `Backend column for "${persystName}" not produced` },
    color,
    label,
    style,
  };
}

function slug(persystName: string, extra?: string): string {
  const base = persystName
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
  return extra ? `${base}_${extra}` : base;
}

// --- Row factories ---------------------------------------------------------

export function artifactIntensityRow(): InstrumentRow {
  return {
    instrumentId: "artifact_intensity",
    persystName: "ArtifactIntensity",
    label: "Artifact Intensity",
    unit: "intensity",
    height: 70,
    kind: "line",
    overlapPrevious: false,
    description:
      "Persyst ArtifactIntensity — 3 BSS components. Green = EMG (muscle), blue = vertical eye, red = horizontal eye. Higher values indicate more artifact energy in the underlying EEG.",
    traces: [
      {
        source: { kind: "column", key: "artifact_intensity_emg" },
        color: EMG,
        label: "EMG",
      },
      {
        source: { kind: "column", key: "artifact_intensity_eye_vertical" },
        color: EYE_V,
        label: "Eye (V)",
      },
      {
        source: { kind: "column", key: "artifact_intensity_eye_horizontal" },
        color: EYE_H,
        label: "Eye (H)",
      },
    ],
  };
}

export function seizureProbabilityRow(): InstrumentRow {
  return {
    instrumentId: "seizure_probability",
    persystName: "SeizureProbabilityP14 Probability",
    label: "Seizure Probability (P14)",
    unit: "probability 0–1",
    height: 60,
    kind: "filled_area",
    yDomain: [0, 1],
    overlapPrevious: false,
    description:
      "Persyst P14 continuous seizure probability score (0–1). Red fill. Dashed reference line at 0.5 threshold used in POCCA/PedQuEST analyses.",
    traces: [
      {
        source: { kind: "column", key: "seizure_probability_p14_probability" },
        color: "#ef4444",
        label: "P14 Probability",
        fillOpacity: 0.35,
      },
    ],
  };
}

export function seizureDetectionRow(): InstrumentRow {
  return {
    instrumentId: "seizure_detection",
    persystName: "SeizureProbabilityP14 Detections",
    label: "P14 Detections",
    unit: "event",
    height: 60,
    kind: "bars",
    yDomain: [0, 1],
    overlapPrevious: true,
    description: "Binary detection events emitted by P14 when probability crosses threshold.",
    traces: [
      {
        source: { kind: "column", key: "seizure_detection_p14" },
        color: "#fb7185",
        label: "Detection",
      },
    ],
  };
}

export function spikeDensityTripletRow(): InstrumentRow {
  return {
    instrumentId: "spike_density",
    persystName: "SpikeDensityV1",
    label: "Spike Density",
    unit: "spikes / sec",
    height: 100,
    kind: "line",
    overlapPrevious: false,
    thresholdY: 1.5,
    description:
      "Persyst SpikeDensityV1 engine. Left (blue) + Right (red) + Generalized (green) per-second spike rate.",
    traces: [
      {
        source: { kind: "column", key: "spike_left_per_sec" },
        color: LEFT,
        label: "Left",
      },
      {
        source: { kind: "column", key: "spike_right_per_sec" },
        color: RIGHT,
        label: "Right",
      },
      {
        source: { kind: "column", key: "spike_generalized_per_sec" },
        color: GENERALIZED,
        label: "Generalized",
      },
    ],
  };
}

export function spikeBooleanRow(
  which: "left_only" | "right_only" | "bilateral" | "generalized",
): InstrumentRow {
  const table = {
    left_only: {
      persystName:
        "[>= 3 <0> [EventDensity Spike Left <Detector,Count_epoch>]] AND NOT[>= 3 <0> [EventDensity Spike Right <Detector,Count_epoch>]]",
      label: "Spikes — Left Only",
      color: LEFT_ONLY,
      fn: "spike_left_only" as const,
      overlapPrevious: false,
    },
    right_only: {
      persystName:
        "[>= 3 <0> [EventDensity Spike Right <Detector,Count_epoch>]] AND NOT[>= 3 <0> [EventDensity Spike Left <Detector,Count_epoch>]]",
      label: "Spikes — Right Only",
      color: RIGHT_ONLY,
      fn: "spike_right_only" as const,
      overlapPrevious: true,
    },
    bilateral: {
      persystName:
        "[>= 3 <0> [EventDensity Spike Left <Detector,Count_epoch>]] AND [>= 3 <0> [EventDensity Spike Right <Detector,Count_epoch>]]",
      label: "Spikes — Bilateral",
      color: BILATERAL,
      fn: "spike_bilateral" as const,
      overlapPrevious: true,
    },
    generalized: {
      persystName: "[>= 3 <0> [EventDensity SpikeGen <Detector,Count_epoch>01]]",
      label: "Spikes — Generalized",
      color: GENERALIZED,
      fn: "spike_generalized" as const,
      overlapPrevious: true,
    },
  };
  const cfg = table[which];
  return {
    instrumentId: `spike_boolean_${which}`,
    persystName: cfg.persystName,
    label: cfg.label,
    unit: "active",
    height: 28,
    kind: "boolean_strip",
    overlapPrevious: cfg.overlapPrevious,
    description: `Derived on the frontend from spike_{left,right,generalized}_per_sec. Active when spike rate ≥ 1.5/sec (≈ ≥3 per 2-s epoch, Persyst convention). Not a faithful EventDensity replica — approximated from available counters.`,
    traces: [
      { source: { kind: "derived", fn: cfg.fn }, color: cfg.color, label: cfg.label, fillOpacity: 0.5 },
    ],
  };
}

export function rhythmicityBooleanPlaceholder(
  persystName: string,
  label: string,
): InstrumentRow {
  return {
    instrumentId: `placeholder_${slug(label)}`,
    persystName,
    label,
    unit: "",
    height: 28,
    kind: "boolean_strip",
    overlapPrevious: true,
    description: `Persyst rhythmicity boolean expression. Requires per-region SumValues_Abs_0-0 / _2-2 aggregates not currently emitted by this pipeline. Displayed as an empty row pending backend work.`,
    traces: [{ source: { kind: "missing", reason: "SumValues_Abs_*" }, color: "#525252", label }],
  };
}

export function rhythmicitySpectrogramRow(which: "left" | "right"): InstrumentRow {
  const s = which === "left" ? "Left" : "Right";
  return {
    instrumentId: `rhythmicity_spec_${which}_hemi`,
    persystName: `Rhythmicity Spectrogram 3.00 ${s} Hemisphere_avg`,
    label: `Rhythmicity Spectrogram — ${s} Hemisphere`,
    unit: "power",
    height: 160,
    kind: "spectrogram",
    freqRange: [1, 25],
    overlapPrevious: false,
    description: `Persyst Rhythmicity engine (3.00 Hz bandwidth), ${s} hemisphere average. 97 bins × 0.25 Hz from 1–25 Hz. Bright bands indicate sustained rhythmic activity.`,
    traces: [
      {
        source: { kind: "spectrogram", specType: "rhythmicity" },
        color: "#ffffff",
        label: `Rhythmicity ${s}`,
      },
    ],
  };
}

export function fftSpectrogramRow(which: "left" | "right"): InstrumentRow {
  const s = which === "left" ? "Left" : "Right";
  return {
    instrumentId: `fft_spec_${which}_hemi`,
    persystName: `FFT_Spectrogram 0-20 ${s} Hemisphere_avg`,
    label: `FFT Spectrogram — ${s} Hemisphere`,
    unit: "power",
    height: 160,
    kind: "spectrogram",
    freqRange: [0, 20],
    overlapPrevious: false,
    description: `Persyst FFT engine, ${s} hemisphere electrode average. 40 bins × 0.5 Hz from 0–20 Hz.`,
    traces: [
      {
        source: { kind: "spectrogram", specType: which === "left" ? "fft_left" : "fft_right" },
        color: "#ffffff",
        label: `FFT ${s}`,
      },
    ],
  };
}

export function asymmetrySpectrogramRow(
  which: "hemi" | "ant" | "post" | "temp" | "parasag",
  height: number = 160,
): InstrumentRow {
  const labels = {
    hemi: "Hemisphere",
    ant: "Anterior",
    post: "Posterior",
    temp: "Temporal",
    parasag: "Parasagittal",
  } as const;
  const persystLabels = {
    hemi: "Hemi",
    ant: "Anterior",
    post: "Posterior",
    temp: "Temporal",
    parasag: "Parasagittal",
  } as const;
  const specType = ({
    hemi: "asymmetry_hemi",
    ant: "asymmetry_ant",
    post: "asymmetry_post",
    temp: "asymmetry_temp",
    parasag: "asymmetry_parasag",
  } as const)[which];
  const regionLabel = labels[which];
  return {
    instrumentId: `asymmetry_spec_${which}`,
    persystName: `Asymmetry, Relative Spectrogram 0-20 Asym ${persystLabels[which]}`,
    label: `Asymmetry Spectrogram — ${regionLabel}`,
    unit: "(L−R)/(L+R)",
    height,
    kind: "spectrogram",
    freqRange: [0, 20],
    overlapPrevious: false,
    description: `Relative asymmetry spectrogram, ${regionLabel.toLowerCase()} region pair. Red = right-hemisphere dominant, blue = left-hemisphere dominant. RdBu diverging colour scale.`,
    traces: [{ source: { kind: "spectrogram", specType }, color: "#ffffff", label: `Asym ${regionLabel}` }],
  };
}

export function aeegLeftRow(overlapPrevious = false): InstrumentRow {
  return {
    instrumentId: "aeeg_left",
    persystName: "aEEG Left Hemisphere_avg",
    label: "aEEG Left Hemisphere (linear scale)",
    unit: "μV (linear)",
    height: 220,
    kind: "aeeg_envelope",
    logScale: false,
    overlapPrevious,
    description:
      "Amplitude-integrated EEG, left hemisphere average. Filled band between lower and upper margins. Left shown in blue; when a right-hemisphere row overlays, the shared region appears purple. Rendered on a LINEAR μV scale (Persyst traditionally displays aEEG log-compressed; workbench uses linear due to Recharts Area-log fill limitations).",
    traces: [
      {
        source: { kind: "column", key: "aeeg_left_max" },
        color: LEFT,
        label: "Left upper (max / p100)",
      },
      {
        source: { kind: "column", key: "aeeg_left_min" },
        color: LEFT,
        label: "Left lower (min / p0)",
      },
    ],
  };
}

export function aeegRightRow(overlapPrevious = true): InstrumentRow {
  return {
    instrumentId: "aeeg_right",
    persystName: "aEEG Right Hemisphere_avg",
    label: "aEEG Right Hemisphere (linear scale)",
    unit: "μV (linear)",
    height: 220,
    kind: "aeeg_envelope",
    logScale: false,
    overlapPrevious,
    description:
      "Amplitude-integrated EEG, right hemisphere average. Red band; overlaps left to produce purple shared region where bilateral amplitudes coincide. Rendered on a LINEAR μV scale (Persyst traditionally displays aEEG log-compressed; workbench uses linear due to Recharts Area-log fill limitations).",
    traces: [
      {
        source: { kind: "column", key: "aeeg_right_max" },
        color: RIGHT,
        label: "Right upper (max / p100)",
      },
      {
        source: { kind: "column", key: "aeeg_right_min" },
        color: RIGHT,
        label: "Right lower (min / p0)",
      },
    ],
  };
}

export function bsrRow(
  which: "left" | "right" | "all",
  overlapPrevious = false,
): InstrumentRow {
  // Backend emits `suppression_{left,right}` (no "_hemisphere" suffix) and
  // `suppression_all` for whole brain. Display label uses "Suppression Ratio"
  // (the Persyst-documented name) rather than the BSR abbreviation.
  const cfg = {
    left: {
      label: "Suppression Ratio — Left Hemisphere",
      color: LEFT,
      persystName: "BSR Left Hemisphere_avg",
      key: "suppression_left",
    },
    right: {
      label: "Suppression Ratio — Right Hemisphere",
      color: RIGHT,
      persystName: "BSR Right Hemisphere_avg",
      key: "suppression_right",
    },
    all: {
      label: "Suppression Ratio — All 10-20 (whole brain)",
      color: "#6b7280",
      persystName: "BSR All 10-20_avg",
      key: "suppression_all",
    },
  }[which];
  return {
    instrumentId: `bsr_${which}`,
    persystName: cfg.persystName,
    label: cfg.label,
    unit: "fraction 0–1",
    height: 90,
    kind: "bsr_line",
    yDomain: [0, 1],
    overlapPrevious,
    description: `Suppression ratio (${cfg.label.replace("Suppression Ratio — ", "")}). Proportion of each epoch below the suppression threshold (near-flat EEG).`,
    traces: [{ source: { kind: "column", key: cfg.key }, color: cfg.color, label: cfg.label }],
  };
}

export function ekgRow(): InstrumentRow {
  return {
    instrumentId: "ekg_channel",
    persystName: "EKG Channel",
    label: "Heart Rate (EKG proxy)",
    unit: "bpm",
    height: 70,
    kind: "line",
    overlapPrevious: false,
    description:
      "Raw EKG is not exposed at epoch cadence by the pipeline; heart-rate derived trend is shown as a proxy. Replace with waveform access when available.",
    traces: [{ source: { kind: "column", key: "heart_rate" }, color: "#14b8a6", label: "HR (bpm)" }],
  };
}

export function reasiRow(
  band: "0-5" | "6-14" | "0-20",
  overlapPrevious = false,
): InstrumentRow {
  const persystName = `Asymmetry, Relative Index (REASI) ${band} Asym Hemi`;
  const key = resolvePersystName(persystName);
  return {
    instrumentId: `reasi_${band}_hemi`,
    persystName,
    label: `REASI ${band} Hz — Hemisphere`,
    unit: "(−1, +1)",
    height: 100,
    kind: "filled_area",
    yDomain: [-1, 1],
    overlapPrevious,
    description: `Relative hemispheric asymmetry index (REASI), ${band} Hz. Positive = right-dominant (red fill); negative = left-dominant (blue fill).`,
    traces: [
      {
        source: key ? { kind: "column", key } : { kind: "missing", reason: persystName },
        color: "#a855f7",
        label: `REASI ${band}`,
      },
    ],
  };
}

export function easiRow(band: "0-20", overlapPrevious = false): InstrumentRow {
  const persystName = `Asymmetry, Absolute Index (EASI) ${band} Asym Hemi`;
  const key = resolvePersystName(persystName);
  return {
    instrumentId: `easi_${band}_hemi`,
    persystName,
    label: `EASI ${band} Hz — Hemisphere`,
    unit: "(−1, +1)",
    height: 100,
    kind: "filled_area",
    yDomain: [-1, 1],
    overlapPrevious,
    description: `Absolute hemispheric asymmetry index (EASI), ${band} Hz.`,
    traces: [
      {
        source: key ? { kind: "column", key } : { kind: "missing", reason: persystName },
        color: "#f97316",
        label: `EASI ${band}`,
      },
    ],
  };
}

export function powerBandRow(
  band: "1-4" | "4-8" | "8-13" | "13-20",
  sideKey: "Left" | "Right",
  overlapPrevious: boolean,
): InstrumentRow {
  const persystName = `FFT_Power ${band} ${sideKey} Hemisphere_avg`;
  const key = resolvePersystName(persystName);
  const colorBySide = sideKey === "Left" ? LEFT : RIGHT;
  const bandName = ({ "1-4": "Delta", "4-8": "Theta", "8-13": "Alpha", "13-20": "Beta" } as const)[band];
  return {
    instrumentId: `fft_power_${band}_${sideKey.toLowerCase()}_hemi`,
    persystName,
    label: `${bandName} (${band} Hz) — ${sideKey} Hemisphere`,
    unit: "μV²/Hz",
    height: 90,
    kind: "line",
    logScale: true,
    overlapPrevious,
    description: `Absolute FFT power, ${bandName} band (${band} Hz), ${sideKey} hemisphere (per-epoch, no temporal smoothing).`,
    traces: [
      {
        source: key ? { kind: "column", key } : { kind: "missing", reason: persystName },
        color: colorBySide,
        label: `${bandName} ${sideKey}`,
      },
    ],
  };
}

export function quadrantRatioRow(
  ratioKind: "RAV" | "ADR",
  sideKey: "Left" | "Right",
  region: "Hemisphere" | "Anterior" | "Posterior",
  overlapPrevious: boolean,
): InstrumentRow {
  const persystInner =
    ratioKind === "RAV" ? `FFT_PowerRatio 6-14//1-20 ${sideKey} ${region}_avg` : `FFT_PowerRatio 8-13//1-4 ${sideKey} ${region}_avg`;
  const persystName = `Time Avg <0,120> [${persystInner}]`;
  const key = resolvePersystName(persystName);
  const colorBySide = sideKey === "Left" ? LEFT : RIGHT;
  return {
    instrumentId: `${ratioKind.toLowerCase()}_${sideKey.toLowerCase()}_${region.toLowerCase()}`,
    persystName,
    label: `${ratioKind} — ${sideKey} ${region}`,
    unit: "ratio",
    height: 90,
    kind: "line",
    overlapPrevious,
    description:
      ratioKind === "RAV"
        ? `Relative Alpha Variability (6–14 / 1–20 Hz), ${sideKey} ${region.toLowerCase()}, 2-min running avg.`
        : `Alpha-Delta Ratio (8–13 / 1–4 Hz), ${sideKey} ${region.toLowerCase()}, 2-min running avg.`,
    traces: [
      {
        source: key ? { kind: "column", key } : { kind: "missing", reason: persystName },
        color: colorBySide,
        label: `${ratioKind} ${sideKey}`,
      },
    ],
  };
}

export function sefRow(
  percentile: 50 | 75 | 90 | 95,
  regionLabel: string,
  persystRegion: string,
  overlapPrevious: boolean,
): InstrumentRow {
  const persystName = `FFT_Edge ${percentile} 0-32 ${persystRegion}_avg`;
  const key = resolvePersystName(persystName);
  return {
    instrumentId: `sef_${percentile}_${slug(regionLabel)}`,
    persystName,
    label: `SEF${percentile} — ${regionLabel}`,
    unit: "Hz",
    height: 80,
    kind: "line",
    yDomain: [0, 32],
    overlapPrevious,
    description: `Spectral edge frequency at the ${percentile}th percentile, ${regionLabel}. After backend B3 fix, emits ${key ? "`" + key + "`" : "(no mapping)"}. Note: this patient's Persyst CSV may not include regional SEF variants — if so, rows render as "no data".`,
    traces: [
      {
        source: key ? { kind: "column", key } : { kind: "missing", reason: persystName },
        color: "#0ea5e9",
        label: `SEF${percentile}`,
      },
    ],
  };
}
