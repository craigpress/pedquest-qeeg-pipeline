/**
 * The 8 target Persyst panels, encoded verbatim from `Ref Files/Trend panels.md`.
 *
 * Row ordering and every `overlapPrevious` flag match the source XML exactly.
 * Groups (one sub-chart per group) are produced at module load by collapsing
 * contiguous `overlapPrevious: true` rows into the preceding group.
 *
 * Extending: to add another Persyst panel, append a `{ panelId, displayName,
 * rows }` entry to `PANEL_SPECS`. The manifest structure is the same; the
 * dashboard dropdown reads `PANELS` directly.
 */

import type { PanelManifest, InstrumentRow, SubChartGroup } from "./types";
import {
  aeegLeftRow,
  aeegRightRow,
  artifactIntensityRow,
  asymmetrySpectrogramRow,
  bsrRow,
  easiRow,
  ekgRow,
  fftSpectrogramRow,
  powerBandRow,
  quadrantRatioRow,
  reasiRow,
  rhythmicityBooleanPlaceholder,
  rhythmicitySpectrogramRow,
  seizureDetectionRow,
  seizureProbabilityRow,
  sefRow,
  spikeBooleanRow,
  spikeDensityTripletRow,
} from "./instruments";
import { validateManifest } from "./manifest.validate";

// --- Per-panel row lists ----------------------------------------------------

function comprehensiveRows(): InstrumentRow[] {
  return [
    aeegLeftRow(false),
    aeegRightRow(true),
    artifactIntensityRow(),
    seizureProbabilityRow(),
    seizureDetectionRow(),
    spikeDensityTripletRow(),
    spikeBooleanRow("left_only"),
    spikeBooleanRow("right_only"),
    spikeBooleanRow("bilateral"),
    spikeBooleanRow("generalized"),
    // Three rhythmicity boolean expressions (SumValues_Abs_0-0 / _2-2 thresholds).
    // Backend does not emit those aggregates today → placeholder rows.
    rhythmicityBooleanPlaceholder(
      "[>= 1.1 <0> [SumValues_Abs_0-0 L...]] AND [>= 5 <0> [SumValues_Abs_2-2 L...]] AND NOT[... R...]",
      "Rhythmicity — Left Only (placeholder)",
    ),
    { ...rhythmicityBooleanPlaceholder("Rhythmicity — Bilateral (placeholder)", "Rhythmicity — Bilateral (placeholder)"), overlapPrevious: true },
    { ...rhythmicityBooleanPlaceholder("Rhythmicity — Right Only (placeholder)", "Rhythmicity — Right Only (placeholder)"), overlapPrevious: true },
    rhythmicitySpectrogramRow("left"),
    rhythmicitySpectrogramRow("right"),
    fftSpectrogramRow("left"),
    fftSpectrogramRow("right"),
    asymmetrySpectrogramRow("hemi"),
    bsrRow("left", false),
    bsrRow("right", true),
    ekgRow(),
  ];
}

function aeegPanelRows(): InstrumentRow[] {
  // EventDensity regional Spike counts not produced by backend → omit those rows
  // (shown as a note in the panel description instead of blank placeholders).
  return [
    artifactIntensityRow(),
    seizureProbabilityRow(),
    seizureDetectionRow(),
    rhythmicityBooleanPlaceholder(
      "EventDensity SpikeBurst <Detector,Count_overlap>",
      "Spike Burst Density (placeholder)",
    ),
    rhythmicitySpectrogramRow("left"),
    rhythmicitySpectrogramRow("right"),
    asymmetrySpectrogramRow("hemi"),
    aeegLeftRow(false),
    aeegRightRow(true),
  ];
}

function asymmetryRows(): InstrumentRow[] {
  return [
    reasiRow("0-5", false),
    reasiRow("6-14", false),
    asymmetrySpectrogramRow("ant", 180),
    asymmetrySpectrogramRow("post", 180),
    asymmetrySpectrogramRow("temp", 180),
    asymmetrySpectrogramRow("parasag", 180),
    aeegLeftRow(false),
    aeegRightRow(true),
  ];
}

function suppressionRows(): InstrumentRow[] {
  // Per XML: aEEG L and aEEG R are BOTH overlapPrevious=0 in this panel —
  // they render as separate stand-alone charts, not an overlay.
  return [
    aeegLeftRow(false),
    { ...aeegRightRow(false), overlapPrevious: false },
    bsrRow("left", false),
    bsrRow("right", true),
    rhythmicitySpectrogramRow("left"),
    rhythmicitySpectrogramRow("right"),
  ];
}

function powerByBandRows(): InstrumentRow[] {
  // L is base chart; R overlaps on the same chart (overlapPrevious=true).
  const r: InstrumentRow[] = [artifactIntensityRow()];
  for (const band of ["1-4", "4-8", "8-13", "13-20"] as const) {
    r.push(powerBandRow(band, "Left", false));
    r.push(powerBandRow(band, "Right", true));
  }
  r.push(asymmetrySpectrogramRow("hemi"));
  return r;
}

function ravQuadrantRows(): InstrumentRow[] {
  // Mirror ADR pattern: Left is base, Right overlays per region → 3 composed rows.
  return [
    quadrantRatioRow("RAV", "Left", "Hemisphere", false),
    quadrantRatioRow("RAV", "Right", "Hemisphere", true),
    quadrantRatioRow("RAV", "Left", "Anterior", false),
    quadrantRatioRow("RAV", "Right", "Anterior", true),
    quadrantRatioRow("RAV", "Left", "Posterior", false),
    quadrantRatioRow("RAV", "Right", "Posterior", true),
    asymmetrySpectrogramRow("hemi"),
    easiRow("0-20", false),
    reasiRow("0-20", true),
    aeegLeftRow(false),
    aeegRightRow(true),
  ];
}

function adrQuadrantRows(): InstrumentRow[] {
  // Per XML: L is base, R overlays for each region (so 3 overlay charts).
  return [
    quadrantRatioRow("ADR", "Left", "Hemisphere", false),
    quadrantRatioRow("ADR", "Right", "Hemisphere", true),
    quadrantRatioRow("ADR", "Left", "Anterior", false),
    quadrantRatioRow("ADR", "Right", "Anterior", true),
    quadrantRatioRow("ADR", "Left", "Posterior", false),
    quadrantRatioRow("ADR", "Right", "Posterior", true),
    asymmetrySpectrogramRow("hemi"),
    easiRow("0-20", false),
    reasiRow("0-20", true),
    aeegLeftRow(false),
    aeegRightRow(true),
  ];
}

function sefSrRows(): InstrumentRow[] {
  // Per XML: every SEF/BSR row is its own chart.
  return [
    sefRow(95, "All 10-20", "All 10-20", false),
    sefRow(95, "Asym Anterior", "Asym Anterior", false),
    sefRow(95, "Asym Posterior", "Asym Posterior", false),
    sefRow(95, "Left Anterior", "Left Anterior", false),
    sefRow(95, "Left Posterior", "Left Posterior", false),
    sefRow(95, "Right Anterior", "Right Anterior", false),
    sefRow(95, "Right Posterior", "Right Posterior", false),
    sefRow(50, "All 10-20", "All 10-20", false),
    sefRow(75, "All 10-20", "All 10-20", false),
    sefRow(90, "All 10-20", "All 10-20", false),
    bsrRow("left", false),
    { ...bsrRow("right", false), overlapPrevious: false },
    { ...bsrRow("all", false), overlapPrevious: false },
  ];
}

// --- Panel specs (order = dropdown order) ----------------------------------

const PANEL_SPECS: { panelId: string; displayName: string; description: string; rows: InstrumentRow[] }[] =
  [
    {
      panelId: "comprehensive",
      displayName: "Comprehensive",
      description:
        "Full clinical overview — artifact, seizure probability, spike density, rhythmicity, FFT, asymmetry, aEEG, BSR, EKG.",
      rows: comprehensiveRows(),
    },
    {
      panelId: "aeeg",
      displayName: "aEEG",
      description:
        "Amplitude-integrated EEG focus. Overlaid L/R aEEG envelopes with artifact, seizure probability, rhythmicity context. EventDensity regional spike counts are not produced by this pipeline — shown as placeholders.",
      rows: aeegPanelRows(),
    },
    {
      panelId: "asymmetry",
      displayName: "Asymmetry",
      description:
        "REASI hemisphere indices (delta + alpha band) followed by per-region asymmetry spectrograms.",
      rows: asymmetryRows(),
    },
    {
      panelId: "suppression_ratio",
      displayName: "Suppression Ratio",
      description:
        "Burst-suppression assessment — stand-alone L and R aEEG envelopes, BSR (L overlay R), rhythmicity spectrograms.",
      rows: suppressionRows(),
    },
    {
      panelId: "power_by_band",
      displayName: "Power by Frequency Band",
      description:
        "Absolute FFT power per epoch for delta (1–4), theta (4–8), alpha (8–13), and beta (13–20 Hz) bands, each hemisphere. Log-scale y-axis.",
      rows: powerByBandRows(),
    },
    {
      panelId: "rav_quadrant",
      displayName: "Relative Alpha Variability (Quadrant)",
      description:
        "Relative Alpha Variability (6–14/1–20 Hz) across four quadrants (L/R × Hemisphere/Anterior/Posterior), followed by asymmetry context.",
      rows: ravQuadrantRows(),
    },
    {
      panelId: "adr_quadrant",
      displayName: "Alpha-Delta Ratios (Quadrant)",
      description:
        "Alpha-Delta Ratio (8–13/1–4 Hz) overlaid L+R for hemisphere, anterior, posterior regions, plus asymmetry context.",
      rows: adrQuadrantRows(),
    },
    {
      panelId: "sef_sr",
      displayName: "SEF and SR",
      description:
        "Spectral Edge Frequency percentiles (95/50/75/90) across regions, plus Burst-Suppression Ratio across hemispheres.",
      rows: sefSrRows(),
    },
  ];

// --- Grouping: collapse overlapPrevious runs into SubChartGroups -----------

/**
 * Composite label rules for grouped sub-charts (DO NOT re-regress these):
 *
 *   1. Single row → use the row label verbatim.
 *   2. Exactly 2 rows → `"<a> + <b>"` (clean, readable case).
 *   3. 3+ rows, all sharing a common prefix before the first `—` (em dash)
 *      or `:` separator → collapse to
 *      `"<prefix> — <suffix1> / <suffix2> / ..."` so we say "Spikes" once
 *      instead of repeating it for every row.
 *   4. No common prefix OR the composite would exceed 80 chars → truncate to
 *      `"<first row label> + <N> more"`.
 *
 * The `description` field is NOT shortened — info panels render the full
 * per-row text, so long descriptions are fine there.
 */
const MAX_COMPOSITE_LABEL_LEN = 80;

function splitLabelPrefix(label: string): { prefix: string; suffix: string } | null {
  // Prefer em dash — (Persyst convention), fall back to colon.
  const emIdx = label.indexOf("—");
  const sepIdx = emIdx >= 0 ? emIdx : label.indexOf(":");
  if (sepIdx < 0) return null;
  const prefix = label.slice(0, sepIdx).trim();
  const suffix = label.slice(sepIdx + 1).trim();
  if (!prefix || !suffix) return null;
  return { prefix, suffix };
}

function composeGroupLabel(labels: string[]): string {
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} + ${labels[1]}`;

  // Try common-prefix collapse.
  const parts = labels.map(splitLabelPrefix);
  const firstPrefix = parts[0]?.prefix;
  const allMatch =
    firstPrefix !== undefined && parts.every((p) => p !== null && p.prefix === firstPrefix);
  if (allMatch) {
    const suffixes = parts.map((p) => p!.suffix).join(" / ");
    const collapsed = `${firstPrefix} — ${suffixes}`;
    if (collapsed.length <= MAX_COMPOSITE_LABEL_LEN) return collapsed;
  }

  // Fallback: first + N more.
  return `${labels[0]} + ${labels.length - 1} more`;
}

function buildGroups(rows: InstrumentRow[]): SubChartGroup[] {
  const groups: SubChartGroup[] = [];
  const groupLabels: string[][] = [];
  for (const row of rows) {
    if (row.overlapPrevious && groups.length > 0) {
      const g = groups[groups.length - 1];
      g.rows.push(row);
      g.height = Math.max(g.height, row.height);
      groupLabels[groupLabels.length - 1].push(row.label);
      g.label = composeGroupLabel(groupLabels[groupLabels.length - 1]);
      // description stays long — info panel wants the full per-row detail.
      g.description = `${g.description}\n\n${row.label}: ${row.description}`;
    } else {
      groups.push({
        groupId: row.instrumentId,
        label: row.label,
        kind: row.kind,
        height: row.height,
        rows: [row],
        description: row.description,
        freqRange: row.freqRange,
      });
      groupLabels.push([row.label]);
    }
  }
  return groups;
}

export const PANELS: PanelManifest[] = PANEL_SPECS.map((spec) => ({
  panelId: spec.panelId,
  displayName: spec.displayName,
  description: spec.description,
  groups: buildGroups(spec.rows),
}));

// --- Validation at module load ---------------------------------------------

validateManifest(PANELS);

export function findPanel(panelId: string): PanelManifest | null {
  return PANELS.find((p) => p.panelId === panelId) ?? null;
}
