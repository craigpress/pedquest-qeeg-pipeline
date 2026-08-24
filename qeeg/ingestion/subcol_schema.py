"""Single source of truth for Persyst CSV sub-column semantics.

This module mirrors §3 of `PersystTrendCSV_Format_Reference.md` (OneDrive doc) in
Python form. It is the **canonical machine-readable schema** for:

- expected sub-column count per Persyst trend family
- per-sub-column slug, description, units (for multi-col families)
- bin-frequency formulae (for spectrogram families)

Three callers consume this module:

1. `qeeg/ingestion/subcol_validator.py` — reads ``EXPECTED_COUNTS`` and
   ``VARIABLE_COUNTS`` to enforce the sub-col contract at import.
2. `qeeg/constants.py` — re-exports ``I_GROUP_SUBCOLUMN_NAMES``,
   ``ARTIFACT_INTENSITY_COMPONENTS``,
   ``ELECTRODE_QUALITY_ELECTRODES`` derived from the schema, so legacy call
   sites keep working unchanged.
3. `qeeg/ingestion/column_mapper.py` — derives per-sub-col slug names from
   the schema via :func:`get_subcol_slug`.

When you update `PersystTrendCSV_Format_Reference.md` §3 (any sub-section),
update this file in lockstep. The two are kept in sync by code review;
`tests/test_subcol_schema.py` exercises a structural cross-check.

Historical corrections (2026-05-21):

* **aEEG positions 3/4/5** (`I20`, `I21`) were previously labeled
  ``bandwidth``, ``percent_bs``, ``amplitude`` based on pipeline-internal
  guesses. Corrected to ``p50``, ``p75``, ``p25`` to match the canonical CSV
  Format Reference §3.4: Persyst emits five statistical percentiles
  (``max, min, p50, p75, p25``) for any aEEG instrument across all MMX
  versions. Downstream column slugs change accordingly:
  ``aeeg_left_upper_margin`` → ``aeeg_left_max``, etc.

* **Electrode Signal Quality count.** Pre-existing code listed 24 channels
  by including the legacy alias pairs ``T3↔T7`` and ``T5↔P7`` etc. The real
  V7 CSV (1002_1.csv) shows 22 sub-columns. The schema lists the 22
  distinct electrodes for the V7 PedQuEST/POCCA setup; ``constants.py`` now
  re-exports this 22-electrode list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

Severity = Literal["error", "warn"]


@dataclass(frozen=True)
class SubcolumnSpec:
    """One sub-column's identity within a multi-sub-col instrument family."""
    position: int                          # 1-indexed sub-col position
    slug: str                              # emitted backend slug ("upper_margin")
    description: str                       # per CSV Format Reference §3
    units: str = ""
    legacy_slug: str = ""                  # only set when slug differs from doc spelling
    csv_ref_description: str = ""          # exact wording from doc, if it differs


@dataclass(frozen=True)
class FamilySchema:
    """Schema for one Persyst trend family."""
    family: str                            # canonical family slug
    expected_count: int                    # required (or expected) sub-col count
    severity: Severity                     # "error" = hard fail; "warn" = variable
    csv_ref_section: str                   # e.g. "§3.4"
    subcolumns: tuple[SubcolumnSpec, ...] = ()
    # If sub-col semantics are formulaic (spectrogram bins), provide a
    # frequency formula instead of a static subcolumns tuple.
    freq_formula: Optional[Callable[[int], float]] = None
    freq_unit: str = ""
    notes: str = ""

    @property
    def slugs(self) -> tuple[str, ...]:
        """Tuple of slugs in sub-col order (empty for formulaic spectrograms)."""
        return tuple(s.slug for s in self.subcolumns)


# ---------------------------------------------------------------------------
# Schema content
# Mirrors PersystTrendCSV_Format_Reference.md §3 — keep in sync.
# ---------------------------------------------------------------------------

# §3.1 Artifact Intensity (3 BSS components)
ARTIFACT_INTENSITY = FamilySchema(
    family="artifact_intensity",
    expected_count=3,
    severity="error",
    csv_ref_section="§3.1",
    subcolumns=(
        SubcolumnSpec(1, "emg",           "Muscle artifact",          units="µV (≥0)"),
        SubcolumnSpec(2, "eye_vertical",  "Vertical eye movement",    units="probability 0–1"),
        SubcolumnSpec(3, "eye_horizontal","Lateral eye movement",     units="probability 0–1"),
    ),
)

# §3.2 Artifact Detector — deliberately not schematised.
#
# Persyst (Mike, 2026-08-20): the 18 columns are internal probabilistic
# classifiers consumed by the engine, not per-electrode measurements, and are
# not useful directly. The previous schema here named them positionally from a
# hardcoded BP-Longitudinal list and labelled them "binary 0/1" — both invented.
# Verified on subject-1: all 18 carry `raw_name = null`, so those electrode names
# were never read from the CSV. The family is discarded at ingestion
# (`qeeg.constants.DISCARDED_FAMILIES`); see docs/ARTIFACT_EXCLUSION.md.

# §3.3 Electrode Signal Quality (acquisition-system-dependent;
#       V7 PedQuEST/POCCA recordings export 22 channels)
_ESQ_22 = (
    # 19 standard 10-20 electrodes
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "T3",  "C3", "Cz", "C4",  "T4",
    "T5",  "P3", "Pz", "P4",  "T6",
    "O1",  "O2",
    # + 2 mastoid/reference + 1 EKG (composition recording-system dependent)
    "A1",  "A2", "EKG",
)
ELECTRODE_SIGNAL_QUALITY = FamilySchema(
    family="electrode_signal_quality",
    expected_count=22,
    severity="warn",   # recording-system-dependent — warn, don't fail
    csv_ref_section="§3.3",
    subcolumns=tuple(
        SubcolumnSpec(i + 1, name, f"Signal-quality on acquisition channel {name}",
                      units="dimensionless (0=clean, >1=disconnect)")
        for i, name in enumerate(_ESQ_22)
    ),
    notes="22 sub-cols verified against `1002_1.csv` I3 column count. The 22 "
          "labels above are the V7 PedQuEST/POCCA default; actual electrode "
          "list is determined at acquisition time and can vary by recording "
          "system. Older code listed 24 entries by including legacy alias "
          "duplicates (T3/T7, T5/P7, etc.) — those were never distinct "
          "exported columns.",
)

# §3.4 aEEG (5 amplitude-envelope values; doc §3.4 is canonical and applies
# to all MMX versions since the aEEG instrument has emitted the same 5 values
# in this fixed order historically).
#
# Per Persyst documentation and §3.4 verification: the 5 sub-columns are
# statistical percentiles of the smoothed aEEG envelope within the update
# window, in fixed order — NOT aEEG-specific quantities like "bandwidth" or
# "percent burst-suppression". Earlier pipeline-internal slug names
# (upper_margin / lower_margin / bandwidth / percent_bs / amplitude) were
# inferred guesses that drifted from the doc; corrected on 2026-05-21 to use
# canonical doc names.
AEEG = FamilySchema(
    family="aeeg",
    expected_count=5,
    severity="error",
    csv_ref_section="§3.4",
    subcolumns=(
        SubcolumnSpec(1, "max", "Maximum / upper envelope (p100)",     units="µV"),
        SubcolumnSpec(2, "min", "Minimum / lower envelope (p0)",       units="µV"),
        SubcolumnSpec(3, "p50", "Median (50th percentile)",            units="µV"),
        SubcolumnSpec(4, "p75", "75th percentile",                     units="µV"),
        SubcolumnSpec(5, "p25", "25th percentile",                     units="µV"),
    ),
    notes="Sub-col semantics are MMX-version-independent — the aEEG instrument "
          "has emitted (max, min, p50, p75, p25) in fixed order across all "
          "Persyst MMX revisions. Per CSV Format Reference §3.4.",
)

# §3.22 Seizure Detection (the combined Detections+Notifications instrument
# has 2 sub-cols; all other seizure instruments have 1).
SEIZURE_DETECTION_NOTIF_PAIR = FamilySchema(
    family="seizure_detection_notif_pair",
    expected_count=2,
    severity="error",
    csv_ref_section="§3.22",
    subcolumns=(
        SubcolumnSpec(1, "detection_event",    "Seizure detection event (binary)", units="binary 0/1"),
        SubcolumnSpec(2, "notification_event", "Seizure notification event (binary)", units="binary 0/1"),
    ),
)

# §3.12 FFT Spectrogram (40 bins, 0.5 Hz/bin, 0–20 Hz)
FFT_SPECTROGRAM = FamilySchema(
    family="fft_spectrogram",
    expected_count=40,
    severity="error",
    csv_ref_section="§3.12",
    freq_formula=lambda k: k * 0.5,
    freq_unit="Hz",
    notes="Bin k (1-indexed) is centered at k × 0.5 Hz. Units = µV/√Hz (square "
          "root of µV²/Hz); square to recover power spectral density.",
)

# §3.13 Asymmetry Relative Spectrogram (40 bins, same axis as FFT)
ASYMMETRY_SPECTROGRAM = FamilySchema(
    family="asymmetry_spectrogram",
    expected_count=40,
    severity="error",
    csv_ref_section="§3.13",
    freq_formula=lambda k: k * 0.5,
    freq_unit="Hz",
    notes="Per-frequency REASI at the same 40-bin axis as FFT_Spectrogram. "
          "Values: % (−100 to +100).",
)

# §3.15 Coherence Spectrogram (63 bins, linear 0–32 Hz)
COHERENCE_SPECTROGRAM = FamilySchema(
    family="coherence_spectrogram",
    expected_count=63,
    severity="error",
    csv_ref_section="§3.15",
    freq_formula=lambda k: (k - 1) * (32.0 / 62.0),
    freq_unit="Hz",
    notes="Bin k (1-indexed) ≈ (k−1) × 0.516 Hz. _1 ≈ 0 Hz (DC); _63 = 32 Hz. "
          "Values: squared coherence 0–1.",
)

# §3.28 Rhythmicity Spectrogram (97 bins, sqrt-scaled 1–25 Hz — V7 default)
RHYTHMICITY_SPECTROGRAM = FamilySchema(
    family="rhythmicity_spectrogram",
    expected_count=97,
    severity="error",
    csv_ref_section="§3.28",
    freq_formula=lambda k: (1.0 + (k - 1) / 24.0) ** 2,
    freq_unit="Hz",
    notes="Sqrt-scaled axis: f_k = (1 + (k−1)/24)². _1 = 1 Hz; _97 = 25 Hz. "
          "Linear-scaled alternative emits 73 bins instead; the validator "
          "accepts either count without error.",
)

# §3.27 Rhythmicity FreqPow (16 cols = 4 bands × 4 values)
RHYTHMICITY_FREQPOW = FamilySchema(
    family="rhythmicity_freqpow",
    expected_count=16,
    severity="error",
    csv_ref_section="§3.27",
    subcolumns=(
        # Band 1 — 1–4 Hz (matches conventional delta)
        SubcolumnSpec( 1, "band1_1to4hz_freq",       "Band 1 (1–4 Hz) peak rhythmic frequency", units="Hz"),
        SubcolumnSpec( 2, "band1_1to4hz_bandwidth",  "Band 1 (1–4 Hz) spectral bandwidth (peak width)", units="Hz"),
        SubcolumnSpec( 3, "band1_1to4hz_power",      "Band 1 (1–4 Hz) rhythmic power", units="µV/Hz"),
        SubcolumnSpec( 4, "band1_1to4hz_fraction",   "Band 1 (1–4 Hz) rhythmicity fraction (rhythmic ÷ total power)", units="fraction 0–1"),
        # Band 2 — 4–9 Hz: spans conventional theta (4–8) AND low alpha (8–9)
        SubcolumnSpec( 5, "band2_4to9hz_freq",       "Band 2 (4–9 Hz) peak rhythmic frequency", units="Hz"),
        SubcolumnSpec( 6, "band2_4to9hz_bandwidth",  "Band 2 (4–9 Hz) spectral bandwidth (peak width)", units="Hz"),
        SubcolumnSpec( 7, "band2_4to9hz_power",      "Band 2 (4–9 Hz) rhythmic power", units="µV/Hz"),
        SubcolumnSpec( 8, "band2_4to9hz_fraction",   "Band 2 (4–9 Hz) rhythmicity fraction (rhythmic ÷ total power)", units="fraction 0–1"),
        # Band 3 — 9–16 Hz: spans conventional high alpha (9–13) AND low beta (13–16)
        SubcolumnSpec( 9, "band3_9to16hz_freq",      "Band 3 (9–16 Hz) peak rhythmic frequency", units="Hz"),
        SubcolumnSpec(10, "band3_9to16hz_bandwidth", "Band 3 (9–16 Hz) spectral bandwidth (peak width)", units="Hz"),
        SubcolumnSpec(11, "band3_9to16hz_power",     "Band 3 (9–16 Hz) rhythmic power", units="µV/Hz"),
        SubcolumnSpec(12, "band3_9to16hz_fraction",  "Band 3 (9–16 Hz) rhythmicity fraction (rhythmic ÷ total power)", units="fraction 0–1"),
        # Band 4 — 16–25 Hz (mid-beta)
        SubcolumnSpec(13, "band4_16to25hz_freq",     "Band 4 (16–25 Hz) peak rhythmic frequency", units="Hz"),
        SubcolumnSpec(14, "band4_16to25hz_bandwidth","Band 4 (16–25 Hz) spectral bandwidth (peak width)", units="Hz"),
        SubcolumnSpec(15, "band4_16to25hz_power",    "Band 4 (16–25 Hz) rhythmic power", units="µV/Hz"),
        SubcolumnSpec(16, "band4_16to25hz_fraction", "Band 4 (16–25 Hz) rhythmicity fraction (rhythmic ÷ total power)", units="fraction 0–1"),
    ),
    notes="Band edges are HARD-CODED in the Persyst algorithm at 1-4, 4-9, 9-16 "
          "and 16-25 Hz and are NOT configurable; the MMX P2D2FreqMin/Max only "
          "set the overall 1-25 Hz range. These are deliberately NOT named "
          "delta/theta/alpha/beta: band 2 (4-9 Hz) spans conventional theta AND "
          "low alpha, and band 3 (9-16 Hz) spans conventional high alpha AND low "
          "beta, so a peak reported in band 2 may be theta or alpha. Any methods "
          "section using these must state the Persyst edges rather than implying "
          "conventional bands. Per-band 4-tuple: peak frequency (Hz), spectral "
          "bandwidth (Hz), rhythmic power (µV/Hz), rhythmicity fraction (0-1). "
          "Source: Persyst (Mike), email to C. Press, 2026-08-21.",
)


# ---------------------------------------------------------------------------
# Single-value families (sub-col count always = 1)
# Listed here for completeness; no per-sub-col semantics.
# ---------------------------------------------------------------------------
SINGLE_VALUE_FAMILIES: frozenset[str] = frozenset({
    "fft_power", "fft_power_ratio", "fft_edge_sef", "reasi", "easi",
    "coherence_avg", "suppression_ratio", "peak_envelope",
    "seizure_probability", "seizure_detection", "seizure_notification",
    "seizure_events_p14", "spike_density", "event_density",
    "boolean_indicator", "rhythmic_delta_indicator",
    "sleep_stages", "sleep_wake", "color_scaled_bars",
    "heart_rate", "time_avg", "sum_values_abs", "threshold",
    "comment", "time_display",
})


# ---------------------------------------------------------------------------
# Master registry — every multi-sub-col schema, keyed by family slug
# ---------------------------------------------------------------------------
_ALL_SCHEMAS: tuple[FamilySchema, ...] = (
    ARTIFACT_INTENSITY,
    ELECTRODE_SIGNAL_QUALITY,
    AEEG,
    SEIZURE_DETECTION_NOTIF_PAIR,
    FFT_SPECTROGRAM,
    ASYMMETRY_SPECTROGRAM,
    COHERENCE_SPECTROGRAM,
    RHYTHMICITY_SPECTROGRAM,
    RHYTHMICITY_FREQPOW,
)

SCHEMAS: dict[str, FamilySchema] = {s.family: s for s in _ALL_SCHEMAS}

# Convenience views used by the validator and constants
EXPECTED_COUNTS: dict[str, int] = {
    s.family: s.expected_count for s in _ALL_SCHEMAS if s.severity == "error"
}
VARIABLE_COUNTS: dict[str, tuple[int, str]] = {
    s.family: (s.expected_count,
               "recording-system-dependent" if s.family == "electrode_signal_quality"
               else "variable")
    for s in _ALL_SCHEMAS if s.severity == "warn"
}

# Linear-rhythmicity alternative (accepted by validator without error)
RHYTHMICITY_SPECTROGRAM_LINEAR_COUNT: int = 73


# ---------------------------------------------------------------------------
# Public helpers (used by column_mapper.py)
# ---------------------------------------------------------------------------

def get_subcol_slug(family: str, position: int) -> str:
    """Return the slug for ``family`` sub-col at 1-indexed ``position``.

    Returns the empty string if the family has no static sub-col list
    (e.g. formulaic spectrograms) or if the position is out of range.
    """
    schema = SCHEMAS.get(family)
    if not schema or not schema.subcolumns:
        return ""
    idx = position - 1
    if 0 <= idx < len(schema.subcolumns):
        return schema.subcolumns[idx].slug
    return ""


def get_spectrogram_bin_freq(family: str, position: int) -> Optional[float]:
    """Return the bin-center frequency (Hz) for a spectrogram family.

    Returns None for non-spectrogram families or out-of-range positions.
    """
    schema = SCHEMAS.get(family)
    if not schema or schema.freq_formula is None:
        return None
    if position < 1 or position > schema.expected_count:
        return None
    return schema.freq_formula(position)


def get_all_slugs(family: str) -> tuple[str, ...]:
    """Return the ordered tuple of sub-col slugs for ``family``."""
    schema = SCHEMAS.get(family)
    return schema.slugs if schema else ()
