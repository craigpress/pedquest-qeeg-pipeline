/** Color scale functions for Canvas heatmaps. */

/** Interpolate between two [r,g,b] colors. */
function lerp3(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

function colorFromStops(
  stops: { pos: number; color: [number, number, number] }[],
  t: number,
): [number, number, number] {
  const clamped = Math.max(0, Math.min(1, t));
  for (let i = 0; i < stops.length - 1; i++) {
    if (clamped >= stops[i].pos && clamped <= stops[i + 1].pos) {
      const local = (clamped - stops[i].pos) / (stops[i + 1].pos - stops[i].pos);
      return lerp3(stops[i].color, stops[i + 1].color, local);
    }
  }
  return stops[stops.length - 1].color;
}

// "Hot" colorscale: black → red → yellow → white (clinical standard)
const HOT_STOPS = [
  { pos: 0.0, color: [0, 0, 0] as [number, number, number] },
  { pos: 0.33, color: [180, 0, 0] as [number, number, number] },
  { pos: 0.66, color: [255, 200, 0] as [number, number, number] },
  { pos: 1.0, color: [255, 255, 255] as [number, number, number] },
];

// Diverging RdBu: blue → white → red (for asymmetry)
const RDBU_STOPS = [
  { pos: 0.0, color: [33, 102, 172] as [number, number, number] },
  { pos: 0.25, color: [103, 169, 207] as [number, number, number] },
  { pos: 0.5, color: [247, 247, 247] as [number, number, number] },
  { pos: 0.75, color: [239, 138, 98] as [number, number, number] },
  { pos: 1.0, color: [178, 24, 43] as [number, number, number] },
];

// Clinical EEG: deep blue → blue → cyan → green → yellow → orange → red → white
// High-contrast multi-hue scale common in clinical EEG software
const EEG_CLINICAL_STOPS = [
  { pos: 0.000, color: [0, 16, 96] as [number, number, number] },
  { pos: 0.143, color: [0, 80, 255] as [number, number, number] },
  { pos: 0.286, color: [0, 200, 255] as [number, number, number] },
  { pos: 0.429, color: [0, 255, 102] as [number, number, number] },
  { pos: 0.571, color: [230, 255, 0] as [number, number, number] },
  { pos: 0.714, color: [255, 140, 0] as [number, number, number] },
  { pos: 0.857, color: [255, 0, 0] as [number, number, number] },
  { pos: 1.000, color: [255, 255, 255] as [number, number, number] },
];

// Viridis: purple → teal → yellow (perceptually uniform, colorblind-safe)
const VIRIDIS_STOPS = [
  { pos: 0.0, color: [68, 1, 84] as [number, number, number] },
  { pos: 0.13, color: [72, 36, 117] as [number, number, number] },
  { pos: 0.25, color: [56, 88, 140] as [number, number, number] },
  { pos: 0.38, color: [39, 130, 142] as [number, number, number] },
  { pos: 0.5, color: [31, 158, 137] as [number, number, number] },
  { pos: 0.63, color: [53, 183, 121] as [number, number, number] },
  { pos: 0.75, color: [110, 206, 88] as [number, number, number] },
  { pos: 0.88, color: [181, 222, 43] as [number, number, number] },
  { pos: 1.0, color: [253, 231, 37] as [number, number, number] },
];

// Inferno: black → purple → orange → yellow (perceptually uniform, high contrast)
const INFERNO_STOPS = [
  { pos: 0.0, color: [0, 0, 4] as [number, number, number] },
  { pos: 0.13, color: [40, 11, 84] as [number, number, number] },
  { pos: 0.25, color: [101, 21, 110] as [number, number, number] },
  { pos: 0.38, color: [159, 42, 99] as [number, number, number] },
  { pos: 0.5, color: [212, 72, 66] as [number, number, number] },
  { pos: 0.63, color: [245, 125, 21] as [number, number, number] },
  { pos: 0.75, color: [250, 193, 39] as [number, number, number] },
  { pos: 1.0, color: [252, 255, 164] as [number, number, number] },
];

// Parula: blue → teal → yellow (MATLAB default, good for EEG)
const PARULA_STOPS = [
  { pos: 0.0, color: [53, 42, 135] as [number, number, number] },
  { pos: 0.13, color: [15, 92, 221] as [number, number, number] },
  { pos: 0.25, color: [0, 139, 206] as [number, number, number] },
  { pos: 0.38, color: [13, 164, 157] as [number, number, number] },
  { pos: 0.5, color: [68, 171, 91] as [number, number, number] },
  { pos: 0.63, color: [159, 178, 46] as [number, number, number] },
  { pos: 0.75, color: [232, 185, 35] as [number, number, number] },
  { pos: 0.88, color: [252, 205, 37] as [number, number, number] },
  { pos: 1.0, color: [249, 251, 14] as [number, number, number] },
];

export function hotColor(t: number): [number, number, number] {
  return colorFromStops(HOT_STOPS, t);
}

export function rdbuColor(t: number): [number, number, number] {
  return colorFromStops(RDBU_STOPS, t);
}

export function eegClinicalColor(t: number): [number, number, number] {
  return colorFromStops(EEG_CLINICAL_STOPS, t);
}

export function viridisColor(t: number): [number, number, number] {
  return colorFromStops(VIRIDIS_STOPS, t);
}

export function infernoColor(t: number): [number, number, number] {
  return colorFromStops(INFERNO_STOPS, t);
}

export function parulaColor(t: number): [number, number, number] {
  return colorFromStops(PARULA_STOPS, t);
}

export type ColorScaleFn = (t: number) => [number, number, number];

/** All available colorscale names (for UI dropdowns). */
export const COLOR_SCALE_OPTIONS: { value: string; label: string }[] = [
  { value: "eeg_clinical", label: "Clinical EEG" },
  { value: "hot", label: "Hot" },
  { value: "viridis", label: "Viridis" },
  { value: "inferno", label: "Inferno" },
  { value: "parula", label: "Parula" },
];

export function getColorScale(name: string): ColorScaleFn {
  switch (name) {
    case "RdBu":
      return rdbuColor;
    case "eeg_clinical":
      return eegClinicalColor;
    case "viridis":
      return viridisColor;
    case "inferno":
      return infernoColor;
    case "parula":
      return parulaColor;
    case "hot":
    default:
      return hotColor;
  }
}

/** Pre-compute a 256-entry lookup table for fast Canvas rendering. */
export function buildColorLUT(scaleFn: ColorScaleFn): Uint8ClampedArray {
  const lut = new Uint8ClampedArray(256 * 4);
  for (let i = 0; i < 256; i++) {
    const [r, g, b] = scaleFn(i / 255);
    lut[i * 4 + 0] = Math.round(r);
    lut[i * 4 + 1] = Math.round(g);
    lut[i * 4 + 2] = Math.round(b);
    lut[i * 4 + 3] = 255;
  }
  return lut;
}
