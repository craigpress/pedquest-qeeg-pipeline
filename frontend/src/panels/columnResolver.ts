/**
 * Persyst instrument name → backend column key.
 *
 * The backend's column-cleaner (`_clean_column_name` in `qeeg/storage/parquet_io.py`)
 * plus family-specific slug logic (`qeeg/ingestion/column_mapper.py::generate_common_name`)
 * produce the keys consumed by `/patients/{id}/epochs`. This module mirrors that
 * mapping for the instruments referenced by the 8 target Persyst panels.
 *
 * Returns `null` for instruments that have no backend column (either not produced
 * by the pipeline or intentional Persyst placeholder like `Time Avg <0,120> []`).
 */

type Region = "hemisphere" | "anterior" | "posterior";
type Side = "left" | "right";

const BAND_MAP: Record<string, string> = {
  "1-4": "delta",
  "4-8": "theta",
  "8-13": "alpha",
  "13-20": "beta",
};

const ASYM_BAND_MAP: Record<string, string> = {
  "0-5": "delta",
  "6-14": "alpha",
  "0-20": "broadband",
};

function side(s: string): Side | null {
  if (s === "Left") return "left";
  if (s === "Right") return "right";
  return null;
}

function region(r: string): Region | null {
  if (r === "Hemisphere") return "hemisphere";
  if (r === "Anterior") return "anterior";
  if (r === "Posterior") return "posterior";
  return null;
}

/**
 * Resolve `Time Avg <0,120> [...]` wrapper to its backend column key.
 *
 * Mapping rules:
 * - `FFT_Power <band> <Side> <Region>_avg`          → `fft_avg2m_<bandSlug>_<side>_<region>`
 * - `FFT_PowerRatio 6-14//1-20 <Side> <Region>_avg` → `rav_<side>_<region>`
 * - `FFT_PowerRatio 8-13//1-4 <Side> <Region>_avg`  → `adr_avg_<side>_<region>`
 */
export function resolveTimeAvg120(inner: string): string | null {
  // FFT_Power <band> <Side> <Region>_avg
  const mPower = inner.match(
    /^FFT_Power (\d+-\d+) (Left|Right) (Hemisphere|Anterior|Posterior)_avg$/,
  );
  if (mPower) {
    const band = BAND_MAP[mPower[1]];
    const s = side(mPower[2]);
    const r = region(mPower[3]);
    if (band && s && r) return `fft_avg2m_${band}_${s}_${r}`;
    return null;
  }

  // FFT_PowerRatio <ratio> <Side> <Region>_avg
  const mRatio = inner.match(
    /^FFT_PowerRatio (6-14\/\/1-20|8-13\/\/1-4) (Left|Right) (Hemisphere|Anterior|Posterior)_avg$/,
  );
  if (mRatio) {
    const prefix = mRatio[1] === "6-14//1-20" ? "rav" : "adr_avg";
    const s = side(mRatio[2]);
    const r = region(mRatio[3]);
    if (s && r) return `${prefix}_${s}_${r}`;
    return null;
  }

  return null;
}

/**
 * Resolve a Persyst instrument name to a backend column key, or `null` if the
 * instrument is a spectrogram, a placeholder, or unsupported by the backend.
 *
 * Note: this does NOT handle spectrogram instruments — those are routed through
 * the `/spectrogram/{type}` endpoint via `TraceSource = { kind: "spectrogram", ... }`.
 */
export function resolvePersystName(persystName: string): string | null {
  // Direct lookup first
  const direct = DIRECT_MAP[persystName];
  if (direct !== undefined) return direct;

  // Time Avg <0,120> [INNER] → resolveTimeAvg120(INNER)
  const mTimeAvg = persystName.match(/^Time Avg <0,120> \[(.*)\]$/);
  if (mTimeAvg) {
    return resolveTimeAvg120(mTimeAvg[1]);
  }

  // Raw FFT_Power <band> <Side> <Region>_avg  (no time-avg wrapper)
  // → backend `fft_<bandSlug>_<side>_<region>` (per-epoch band power, no temporal smoothing)
  const mRawPower = persystName.match(
    /^FFT_Power (\d+-\d+) (Left|Right) (Hemisphere|Anterior|Posterior)_avg$/,
  );
  if (mRawPower) {
    const band = BAND_MAP[mRawPower[1]];
    const s = side(mRawPower[2]);
    const r = region(mRawPower[3]);
    if (band && s && r) return `fft_${band}_${s}_${r}`;
    return null;
  }

  // REASI / EASI with band + hemisphere region
  // "Asymmetry, Relative Index (REASI) 0-5 Asym Hemi"
  // "Asymmetry, Absolute Index (EASI) 0-20 Asym Hemi"
  const mIdx = persystName.match(
    /^Asymmetry, (Relative|Absolute) Index \((REASI|EASI)\) (0-5|6-14|0-20) Asym (Hemi|Anterior|Posterior|Temporal|Parasagittal)$/,
  );
  if (mIdx) {
    const indexType = mIdx[2].toLowerCase();
    const band = ASYM_BAND_MAP[mIdx[3]];
    const regionSlug = mIdx[4].toLowerCase() === "hemi" ? "hemisphere" : mIdx[4].toLowerCase();
    if (band) return `asymmetry_${indexType}_${band}_${regionSlug}`;
    return null;
  }

  // FFT_Edge (SEF) — backend slug after B3 fix is `sef_{percentile}_{channels_slug}`.
  // Channels convention: `all` for whole-brain (Persyst "All 10-20"), otherwise
  // `{hemisphere}_{region}` or `asym_{region}`.
  const mSef = persystName.match(
    /^FFT_Edge (\d+) 0-32 (All 10-20|Left Anterior|Left Posterior|Right Anterior|Right Posterior|Asym Anterior|Asym Posterior)_avg$/,
  );
  if (mSef) {
    const pct = mSef[1];
    const ch = mSef[2];
    if (ch === "All 10-20") return `sef_${pct}_all`;
    if (ch.startsWith("Asym ")) return `sef_${pct}_asym_${ch.slice(5).toLowerCase()}`;
    return `sef_${pct}_${ch.toLowerCase().replace(" ", "_")}`;
  }

  return null;
}

/** Direct 1:1 mappings — covers the fixed-name instruments in the 8 panels. */
const DIRECT_MAP: Record<string, string | null> = {
  // Artifact
  ArtifactIntensity: "__artifact_intensity_multi__", // handled specially (3 sub-traces)

  // Seizure. Both instruments ship under one display label, so column identity
  // comes from the MMX instrument suffix. The Detections instrument classifies
  // into the seizure_detection family, so it is named seizure_detection_p14 --
  // distinct from the SeizureEventsP14 overlay pair (seizure_detection_event /
  // seizure_notification_event) and from the 2-minute running max
  // (seizure_detection_p14_max120s).
  "SeizureProbabilityP14 Probability": "seizure_probability_p14_probability",
  "SeizureProbabilityP14 Detections": "seizure_detection_p14",

  // Spike (single-trace raw)
  SpikeDensityV1: "__spike_density_triplet__", // handled specially (L/R/Gen overlay)

  // aEEG L/R
  "aEEG Left Hemisphere_avg": "__aeeg_envelope_left__",
  "aEEG Right Hemisphere_avg": "__aeeg_envelope_right__",

  // BSR / Suppression — backend emits `suppression_{left,right}` (no `_hemisphere`
  // suffix) and `suppression_all` for whole brain. Note: this MMX's patient CSV
  // may not contain the All 10-20 variant even though the MMX defines it —
  // renderer falls back to "no data" in that case.
  "BSR Left Hemisphere_avg": "suppression_left",
  "BSR Right Hemisphere_avg": "suppression_right",
  "BSR All 10-20_avg": "suppression_all",

  // EKG - use heart_rate as best-available proxy; raw EKG signal not at epoch cadence
  "EKG Channel": "heart_rate",

  // Rhythmicity / FFT hemisphere spectrograms routed through spectrogram endpoint,
  // not column lookup — these entries return null intentionally.
  "Rhythmicity Spectrogram 3.00 Left Hemisphere_avg": null,
  "Rhythmicity Spectrogram 3.00 Right Hemisphere_avg": null,
  "FFT_Spectrogram 0-20 Left Hemisphere_avg": null,
  "FFT_Spectrogram 0-20 Right Hemisphere_avg": null,
  "Asymmetry, Relative Spectrogram 0-20 Asym Hemi": null,
  "Asymmetry, Relative Spectrogram 0-20 Asym Anterior": null,
  "Asymmetry, Relative Spectrogram 0-20 Asym Posterior": null,
  "Asymmetry, Relative Spectrogram 0-20 Asym Temporal": null,
  "Asymmetry, Relative Spectrogram 0-20 Asym Parasagittal": null,

  // EventDensity SpikeBurst — backend does not emit; frontend shows placeholder
  "EventDensity SpikeBurst <Detector,Count_overlap>": null,

  // Empty placeholder in Persyst XML (Power-by-Band row 9)
  "Time Avg <0,120> []": null,
};

/** Families required to fetch a backend column by key. */
export function familiesForColumn(col: string): string[] {
  if (col.startsWith("artifact_intensity")) return ["artifact_intensity"];
  if (col.startsWith("seizure_probability") || col.startsWith("seizure_prob"))
    return ["seizure_probability"];
  if (col.startsWith("seizure_detection")) return ["seizure_detection"];
  if (col.startsWith("seizure_notification")) return ["seizure_notification"];
  if (col.startsWith("spike")) return ["spike_density"];
  if (col.startsWith("aeeg")) return ["aeeg"];
  if (col.startsWith("suppression")) return ["suppression_ratio"];
  if (col.startsWith("heart_rate")) return ["heart_rate"];
  if (col.startsWith("fft_avg2m") || col.startsWith("fft_avg64s") || col.startsWith("fft_"))
    return ["fft_power"];
  if (col.startsWith("adr_avg") || col.startsWith("adr_")) return ["fft_power_ratio"];
  if (col.startsWith("rav")) return ["alpha_variability"];
  if (col.startsWith("asymmetry_reasi") || col.startsWith("asymmetry_easi"))
    return ["asymmetry"];
  if (col.startsWith("sef")) return ["spectral_edge"];
  if (col.startsWith("rhythmicity")) return ["rhythmicity"];
  return [];
}
