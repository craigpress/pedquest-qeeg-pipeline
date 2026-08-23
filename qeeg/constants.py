"""Constants for the qEEG analysis pipeline."""

from __future__ import annotations

from datetime import datetime

# ---------------------------------------------------------------------------
# Excel date handling
# ---------------------------------------------------------------------------
EXCEL_EPOCH = datetime(1899, 12, 30)

# ---------------------------------------------------------------------------
# EEG frequency bands  (min_hz, max_hz)
# ---------------------------------------------------------------------------
FREQUENCY_BANDS: dict[str, tuple[float, float]] = {
    "infraslow": (0, 1),
    "delta": (1, 4),
    "theta": (4, 8),
    "alpha": (8, 13),
    "beta": (13, 20),
    "beta_wide": (13, 30),  # FFTEngine01 outputs both 13-20 and 13-30 Hz bands
}

# ---------------------------------------------------------------------------
# Brain regions
# ---------------------------------------------------------------------------
REGIONS: list[str] = [
    "Left Anterior",
    "Left Posterior",
    "Left Hemisphere",
    "Right Anterior",
    "Right Posterior",
    "Right Hemisphere",
]

ANTERIOR_REGIONS: list[str] = ["Left Anterior", "Right Anterior"]
POSTERIOR_REGIONS: list[str] = ["Left Posterior", "Right Posterior"]

# ---------------------------------------------------------------------------
# Age groups  (label, min_days, max_days)
# ---------------------------------------------------------------------------
AGE_GROUPS: list[tuple[str, int, int]] = [
    ("0-3 Months", 0, 91),
    ("4-6 Months", 92, 183),
    ("7-11 Months", 184, 334),
    ("1-3 Years", 335, 1095),
    ("4-8 Years", 1096, 2920),
    ("9-12 Years", 2921, 4380),
    ("13-18 Years", 4381, 6570),
]

# ---------------------------------------------------------------------------
# Time-binning defaults
# ---------------------------------------------------------------------------
DEFAULT_BIN_EDGES_HOURS: list[float] = [0, 6, 12, 18, 24, 48, 72]

# ---------------------------------------------------------------------------
# FFT engine
# ---------------------------------------------------------------------------
FFT_UPDATE_INTERVAL: int = 8  # FFT engine updates every 8 rows/seconds

# ---------------------------------------------------------------------------
# Sub-column identity lookup by I-group
#
# Keys are I-group integers (the leading number in I{group}_{sub}).
# Values are lists of sub-column labels indexed from 0 (sub-index 1).
#
# Multi-sub-col families (I1 Artifact Intensity, I2 Artifact Detector,
# I3 Electrode Signal Quality, I20/I21 aEEG) read their slug lists from the
# canonical schema in ``qeeg.ingestion.subcol_schema`` (which mirrors
# ``PersystTrendCSV_Format_Reference.md`` §3). Edits to those slug lists
# belong in the schema, not here.
# ---------------------------------------------------------------------------
from qeeg.ingestion.subcol_schema import (
    ARTIFACT_INTENSITY as _AI_SCHEMA,
    ELECTRODE_SIGNAL_QUALITY as _ESQ_SCHEMA,
    AEEG as _AEEG_SCHEMA,
    get_all_slugs as _get_all_slugs,
)

I_GROUP_SUBCOLUMN_NAMES: dict[int, list[str]] = {
    # Schema-driven: see subcol_schema.ARTIFACT_INTENSITY /
    # ELECTRODE_SIGNAL_QUALITY / AEEG. I-group 2 (Artifact Detector) is
    # absent on purpose: the family is discarded, and the names it used to
    # carry were invented rather than read from the export.
    1:  list(_AI_SCHEMA.slugs),
    3:  list(_ESQ_SCHEMA.slugs),
    20: list(_AEEG_SCHEMA.slugs),  # aEEG Left Hemisphere
    21: list(_AEEG_SCHEMA.slugs),  # aEEG Right Hemisphere (same structure)

    # --- RDA (Rhythmic Delta Activity) display tracks ---
    # Single-column tracks, color-coded in Persyst display.
    # I116 = left (blue), I117 = right (red), I118 = generalized (green)
    116: ["left"],
    117: ["right"],
    118: ["generalized"],

    # --- Seizure ---
    # I119 = SeizureEventsP14 (event overlay display, ClsId 650112EF)
    #   _1 = detection event (red), _2 = notification event (gray)
    # I120-122 = SeizureProbabilityP14 data instruments (ClsId 934F0588):
    #   I120 = notification value (OutputIndex 2, SumType 2)
    #   I121 = continuous probability (OutputIndex 0, SumType 9)
    #   I122 = binary detection flag (OutputIndex 1, SumType 8)
    # I182 = time-display variant of seizure probability (trend starts "Time,")
    119: ["detection_event", "notification_event"],

    # --- Sleep staging sub-columns ---
    # I123: raw stage integer output (0=indeterminate, 1=W, 2=N1, 3=N2, 4=N3, 5=REM)
    123: ["stage_raw"],
    # I124-I129: six display panels, one per AASM sleep stage
    # Order: Wake, N1, N2, N3, REM, Indeterminate (verify against MMX if needed)
    124: ["wake"],
    125: ["n1"],
    126: ["n2"],
    127: ["n3"],
    128: ["rem"],
    129: ["indeterminate"],
    # I130: binary wake/sleep/indeterminate state
    130: ["state_binary"],

    # --- Spike density --- (each I-group has 1 sub-column; names from trend)
    131: ["burst_bilateral"],
    132: ["generalized_per_10s"],
    133: ["generalized_per_sec"],
    134: ["left_per_10s"],
    135: ["left_per_sec"],
    136: ["right_per_10s"],
    137: ["right_per_sec"],
    138: ["vertex_per_sec"],
    139: ["all_foci_per_sec"],
    140: ["threshold_right"],
    141: ["threshold_generalized"],
    142: ["threshold_left"],
    143: ["rate_display_left_right"],
    144: ["rate_display_left_right"],
    145: ["rate_display_with_gen"],
    146: ["rate_display_with_gen"],

    # --- Boolean periodic discharges (ACNS 2021 terminology) ---
    # LAD = Lateralized Aperiodic Discharges (left)
    # LPD = Lateralized Periodic Discharges (left)
    # LRD = Lateralized Rhythmic Discharges (left)
    # RAD/RPD/RRD = same, right hemisphere
    92: ["lad"],
    93: ["lpd"],
    94: ["lrd"],
    95: ["rad"],
    96: ["rpd"],
    97: ["rrd"],
}

# Mapping: ACNS periodic discharge acronym → full clinical name
PERIODIC_DISCHARGE_NAMES: dict[str, str] = {
    "lad": "Lateralized Aperiodic Discharges (left)",
    "lpd": "Lateralized Periodic Discharges (left)",
    "lrd": "Lateralized Rhythmic Discharges (left)",
    "rad": "Right Aperiodic Discharges",
    "rpd": "Right Periodic Discharges",
    "rrd": "Right Rhythmic Discharges",
}

# ---------------------------------------------------------------------------
# Schema-driven electrode and component lists.
#
# These re-export the canonical lists from ``qeeg.ingestion.subcol_schema`` so
# legacy import paths (``from qeeg.constants import ELECTRODE_QUALITY_ELECTRODES``)
# keep working unchanged.
# ---------------------------------------------------------------------------
ARTIFACT_INTENSITY_COMPONENTS: list[str] = list(_AI_SCHEMA.slugs)
ELECTRODE_QUALITY_ELECTRODES:  list[str] = list(_ESQ_SCHEMA.slugs)
# 22 channels for this template (recording-system dependent); see subcol_schema.

# ---------------------------------------------------------------------------
# Asymmetry index band labels (EASI/REASI)
# ---------------------------------------------------------------------------
ASYMMETRY_BANDS: dict[str, str] = {
    "0 - 5 Hz":   "delta",       # REASI delta band (0–5 Hz)
    "6 - 14 Hz":  "alpha",       # REASI alpha band (6–14 Hz, Persyst convention)
    "0 - 20 Hz":  "broadband",   # EASI/REASI broadband (0–20 Hz)
}

# Asymmetry region labels used in trend names
ASYMMETRY_REGIONS: dict[str, str] = {
    "Asym Hemi":         "hemisphere",
    "Asym Anterior":     "anterior",
    "Asym Posterior":    "posterior",
    "Asym Parasagittal": "parasagittal",
    "Asym Temporal":     "temporal",
}

# ---------------------------------------------------------------------------
# Feature family classification (regex patterns)
# Order matters: first match wins.
# ---------------------------------------------------------------------------
# Families recognised in the export but deliberately dropped at ingestion, so
# they never reach the dataframe, the schema, or any export.
#
# artifact_detector: Persyst (Mike, 2026-08-20) describes the 18 columns as
# internal probabilistic classifiers used by the engine — not per-electrode
# measurements, and not useful directly. They are still classified here rather
# than left unmatched, because falling through to `other` would give them
# positional names and readmit them as data. See docs/ARTIFACT_EXCLUSION.md.
DISCARDED_FAMILIES: frozenset[str] = frozenset({"artifact_detector"})

FEATURE_FAMILIES: dict[str, str] = {
    # -- Artifact & quality (3 intensity, 24 quality sub-columns; the 18
    #    detector sub-columns are matched only so they can be discarded)
    # Handle both human-readable ("Artifact Intensity") and MMX Name ("ArtifactIntensity")
    "artifact_intensity": r"Artifact Intensity|ArtifactIntensity",
    "artifact_detector":  r"Artifact Detector|ArtifactDetector|^Artifact$",
    "electrode_quality":  r"Electrode Signal Quality|ElectrodeSignalQuality",
    # -- Alpha variability (RAV / Relative Alpha, 6-14/1-20 Hz).
    #    Must come BEFORE fft_power_ratio.
    #    Handles both: old "RAV" label, and new MMX Name "FFT_PowerRatio 6-14//1-20 …"
    "alpha_variability": r"\bRAV\b|Relative Alpha|FFT_PowerRatio\s+6-14|FFT PowerRatio\s*,?\s*6-14",
    # -- FFT spectral (ratio before power so "FFT PowerRatio" doesn't match fft_power)
    #    Match both underscore (MMX Name) and space (old human-readable) forms.
    "fft_power_ratio":   r"FFT_PowerRatio|FFT PowerRatio",
    "fft_power":         r"FFT_Power\b|FFT Power,\s*\d",
    "fft_spectrogram":   r"FFT_Spectrogram|FFT Spectrogram",
    "spectral_edge":     r"FFT_Edge|SEF\d+",
    # -- Amplitude / envelope
    "aeeg":              r"aEEG",
    "peak_envelope":     r"PeakEnvelope",
    "suppression_ratio": r"Suppression Ratio|^BSR\b",
    # -- Status Epilepticus & Seizure Burden (Persyst-native metrics, V8+).
    #    Matched before the generic seizure patterns. Kept as their own families
    #    so they stay distinct from the pipeline-calculated screen flags /
    #    burden percentages (status_epilepticus_screen_flag, seizure_burden_pct).
    "status_epilepticus":    r"[Ss]tatus\s+[Ee]pilepticus",
    "seizure_burden":        r"[Ss]eizure\s+[Bb]urden",
    # -- Seizure (MMX-Name exact forms first, then loose regex)
    #    SeizureProbabilityP14 Detections → seizure_detection
    #    SeizureProbabilityP14 Probability → seizure_probability
    "seizure_detection":     r"SeizureProbabilityP14\s+Detections|[Ss]eizure\s+[Dd]etect",
    "seizure_probability":   r"SeizureProbabilityP14|[Ss]eizure\s+[Pp]rob",
    "seizure_notification":  r"[Ss]eizure\s+[Nn]otif",
    # -- Spikes (EventDensity and SpikeDensityV1 before generic "Spike")
    "spike_density": r"SpikeDensityV1|EventDensity\s+Spike|Spike",
    # -- Rhythmic Delta Activity (RDA).
    #    Must come BEFORE rhythmicity so "delta indicator" doesn't fall into rhythmicity.
    "rda":        r"[Rr]hythmic\s+delta\s+indicator",
    # -- Rhythmicity spectrogram, SumValues, Thresholds (P2D2 rhythmicity index)
    "rhythmicity": r"Rhythmic",
    # -- Asymmetry (index + spectrogram)
    "asymmetry": r"Asymmetry",
    # -- Coherence
    "coherence_spectrogram": r"Coherence",
    # -- Sleep staging
    "sleep": r"Sleep",
    # -- Periodic discharge booleans (LAD+, LPD+, LRD+, RAD+, RPD+, RRD+) — ACNS 2021
    "rhythmic_delta": r"Boolean\s+[LR][A-Z]D",
    # -- Cardiovascular
    "heart_rate": r"Heart Rate|EKG Channel",
    # -- Annotations / display
    # NOTE: "Time Avg <…>" are DATA instruments (FFT averages); must NOT match here.
    # Only match bare "Time," or "Time " patterns that Persyst uses for clock display rows.
    "annotation":   r"Comment",
    "time_display": r"^Time[,\s](?!Avg\s*<)",
}

# ---------------------------------------------------------------------------
# Spectrogram frequency mappings (from MMX FreqMin/FreqMax)
# Source: PedQuEST_Pennsieve_V7_research.mmx instrument definitions (unchanged from V3)
# ---------------------------------------------------------------------------
SPECTROGRAM_FREQ_MAP: dict[str, dict] = {
    "fft_spectrogram": {
        "freq_min": 0.0, "freq_max": 20.0,
        "n_bins": 40, "resolution_hz": 0.5,
        # bin i (1-indexed) covers: (i-1)*0.5 to i*0.5 Hz
    },
    "asymmetry_spectrogram": {
        "freq_min": 0.0, "freq_max": 20.0,
        "n_bins": 40, "resolution_hz": 0.5,
    },
    "rhythmicity_spectrogram": {
        "freq_min": 1.0, "freq_max": 25.0,
        "n_bins": 97, "resolution_hz": 0.25,
        # NOTE: column_mapper and pipeline_service now read rhythmicity bin
        # frequencies from qeeg.ingestion.subcol_schema (which encodes the
        # correct sqrt formula f_k = (1 + (k-1)/24)²). The linear
        # resolution_hz here is retained only as a half-bin-width fallback
        # for band classification (see column_mapper._spectrogram_freq_label
        # and pipeline_service spectrogram axis builder).
    },
    "rhythmicity_freqpow": {
        "freq_min": 1.0, "freq_max": 25.0,
        "n_bins": 16, "resolution_hz": 1.5,
    },
    "coherence_spectrogram": {
        # These are the nominal range and a half-bin-width fallback, NOT the
        # emitted axis. The axis comes from subcol_schema's formula
        # f_k = (k-1) * 32/62, so bin 1 is 0.00 Hz and bin 63 is 32.00 Hz.
        #
        # Whether Persyst's sub-column 1 is the DC bin or the first non-DC bin
        # is UNRESOLVED and open with the vendor -- coherence appears in the
        # help only as a stored value, never as a documented trend type. This
        # entry used to claim "DC bin excluded: 63 bins from 0.5 to 32.0 Hz",
        # which contradicted the formula the code actually runs. Left as the
        # third convention it has always been, but no longer asserting a
        # resolution we do not have. Tier EMP -- see HANDOFF.md open items.
        "freq_min": 0.0, "freq_max": 32.0,
        "n_bins": 63, "resolution_hz": 0.5,
    },
}

# Families whose raw data updates at FFT_UPDATE_INTERVAL and need downsample
FAMILIES_NEEDING_DOWNSAMPLE: set[str] = {
    "fft_power",
    "fft_power_ratio",
    "alpha_variability",  # RAV is FFT-engine derived; updates every 8 rows
    "rda",                # Rhythmicity engine; updates on FFT cadence
}

# ---------------------------------------------------------------------------
# 10-20 electrode name normalization (old → new standard)
# Persyst versions differ: older exports use T3/T4/T5/T6, newer use T7/T8/P7/P8.
# Normalize to the current international 10-20 standard names.
# ---------------------------------------------------------------------------
ELECTRODE_NAME_MAP: dict[str, str] = {
    "T3": "T7",
    "T4": "T8",
    "T5": "P7",
    "T6": "P8",
}

# Full alias table including identity mappings for the new names.
# Useful when you need to normalize a single electrode name to the 2006 standard.
ELECTRODE_10_20_ALIASES: dict[str, str] = {
    "T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8",
    "T7": "T7", "T8": "T8", "P7": "P7", "P8": "P8",
}


def normalize_electrode_name(name: str) -> str:
    """Normalize a single electrode name to the 10-20 revised (2006) standard."""
    return ELECTRODE_10_20_ALIASES.get(name, name)

# ---------------------------------------------------------------------------
# Quality / validation thresholds
# ---------------------------------------------------------------------------
MIN_BIN_COVERAGE_HOURS: float = 1.0   # minimum usable hours per bin
MAX_ROSC_TO_EEG_HOURS: float = 22.0   # date-shift validation threshold
