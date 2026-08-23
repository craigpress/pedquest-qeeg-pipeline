"""Validate Persyst CSV sub-column counts against the schema in
`qeeg.ingestion.subcol_schema`, which mirrors
`PersystTrendCSV_Format_Reference.md` §3.

For every instrument observed in a parsed CSV, infer its trend family from the
trend name and compare the observed `max(sub-col index)` to the expected count.

Two outcomes:
- `severity="error"` — fixed-cardinality family with a mismatch (e.g. FFT
  Spectrogram has 39 bins instead of 40). Caller should hard-fail.
- `severity="warn"` — recording-system-dependent family (Electrode Signal
  Quality) where the count varies legitimately. Log and persist; do not fail.

Companion documents (keep in sync when editing):
- `PersystTrendCSV_Format_Reference.md` §3 (canonical sub-col definitions — doc)
- `qeeg/ingestion/subcol_schema.py` (Python source of truth — code)
- `docs/PERSYST_V10_REFERENCE.md` §8–§9 (verification status)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from qeeg.ingestion.subcol_schema import (
    EXPECTED_COUNTS as EXPECTED_SUBCOL_COUNTS_FIXED,
    VARIABLE_COUNTS as EXPECTED_SUBCOL_COUNTS_VARIABLE,
    SINGLE_VALUE_FAMILIES,
    RHYTHMICITY_SPECTROGRAM_LINEAR_COUNT,
)

logger = logging.getLogger(__name__)

Severity = Literal["error", "warn"]


# ---------------------------------------------------------------------------
# Trend-name → family classifier
# ---------------------------------------------------------------------------
# Ordered most-specific first; matched case-insensitively against the trend name.
# CRITICAL: Single-value families whose labels embed a multi-col family name
# (e.g. "SumValues LA delta freq, Rhythmicity Spectrogram FreqPow LA ...") must
# match BEFORE the embedded family. Persyst compound labels list the derived
# instrument first, then the source instrument as suffix.
_CLASSIFIERS: list[tuple[re.Pattern, str]] = [
    # ---- Single-value compound trends (must precede their source patterns) ----
    (re.compile(r"^Threshold\b", re.I),                        "threshold"),
    (re.compile(r"^SumValues\b", re.I),                        "sum_values_abs"),
    (re.compile(r"^Spike Rate ?Threshold", re.I),              "boolean_indicator"),
    (re.compile(r"^Boolean (?:LAD|LPD|LRD|RAD|RPD|RRD)\+", re.I), "boolean_indicator"),
    (re.compile(r"^Spikes\s*>=", re.I),                        "boolean_indicator"),
    (re.compile(r"^Rhythmic delta indicator", re.I),           "rhythmic_delta_indicator"),
    (re.compile(r"^Sleep-Wake (?:Stage|State)", re.I),         "sleep_wake"),

    # ---- Multi-column families (fixed cardinality > 1) ----
    (re.compile(r"^Artifact Intensity\b", re.I),               "artifact_intensity"),
    (re.compile(r"^Electrode Signal Quality\b", re.I),         "electrode_signal_quality"),
    (re.compile(r"^aEEG\b", re.I),                             "aeeg"),
    (re.compile(r"^Rhythmicity Spectrogram FreqPow", re.I),    "rhythmicity_freqpow"),
    (re.compile(r"^Rhythmicity Spectrogram\b", re.I),          "rhythmicity_spectrogram"),
    (re.compile(r"^Coherence_Spectrogram\b", re.I),            "coherence_spectrogram"),
    (re.compile(r"^Coherence_Avg\b", re.I),                    "coherence_avg"),
    (re.compile(r"^Asymmetry,?\s*Relative Spectrogram", re.I), "asymmetry_spectrogram"),
    (re.compile(r"^Asymmetry,?\s*Absolute Index", re.I),       "easi"),
    (re.compile(r"^Asymmetry,?\s*Relative Index", re.I),       "reasi"),
    (re.compile(r"^FFT Spectrogram\b", re.I),                  "fft_spectrogram"),
    (re.compile(r"^Seizure Detections.*Notifications", re.I),  "seizure_detection_notif_pair"),

    # ---- Single-value primary families ----
    (re.compile(r"Seizure probability", re.I),                 "seizure_probability"),
    (re.compile(r"Seizure Notifications", re.I),               "seizure_notification"),
    (re.compile(r"Seizure Detections", re.I),                  "seizure_detection"),
    (re.compile(r"FFT Edge|SEF\d", re.I),                      "fft_edge_sef"),
    (re.compile(r"FFT PowerRatio", re.I),                      "fft_power_ratio"),
    (re.compile(r"FFT Power", re.I),                           "fft_power"),
    (re.compile(r"^Suppression Ratio|^BSR\b", re.I),           "suppression_ratio"),
    (re.compile(r"^PeakEnvelope", re.I),                       "peak_envelope"),
    (re.compile(r"^Spike Burst Detection", re.I),              "boolean_indicator"),
    (re.compile(r"^Spike Detections", re.I),                   "spike_density"),
    (re.compile(r"^EventDensity", re.I),                       "event_density"),
    (re.compile(r"^SleepStages\b", re.I),                      "sleep_stages"),
    (re.compile(r"^Heart Rate\b", re.I),                       "heart_rate"),
    (re.compile(r"^Time Avg\b", re.I),                         "time_avg"),
    (re.compile(r"^Time \(\d+", re.I),                         "time_avg"),   # "Time (64 sec running ave)…", "Time (2 min …)"
    (re.compile(r"^Comment\b", re.I),                          "comment"),
]


def classify_trend(name: str) -> Optional[str]:
    """Return the canonical family slug for a Persyst trend-name string.

    Returns None for unknown/empty names.
    """
    if not name:
        return None
    for pat, family in _CLASSIFIERS:
        if pat.search(name):
            return family
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class SubcolMismatch:
    instrument_index: int            # the n in I{n}_{k}
    trend_name: str
    family: Optional[str]
    expected: int
    observed: int
    severity: Severity
    detail: str

    def __str__(self) -> str:
        return (
            f"I{self.instrument_index} ({self.family or 'unknown family'}): "
            f"expected {self.expected} sub-cols, observed {self.observed} — {self.detail}"
        )


_ICODE_RE = re.compile(r"^I(\d+)_(\d+)$")


def validate_subcol_counts(
    code_to_description: dict[str, str],
) -> list[SubcolMismatch]:
    """Validate sub-col counts for every I-instrument in a parsed CSV.

    `code_to_description` is the mapping the parser already builds
    (`I{n}_{k}` → trend-name string).

    Returns a list of mismatches; empty list = all instruments conform.
    """
    # Group I-codes by instrument index, capture max sub-col seen and trend name.
    per_instrument: dict[int, dict] = {}
    for code, desc in code_to_description.items():
        m = _ICODE_RE.match(code)
        if not m:
            continue
        inst = int(m.group(1))
        sub = int(m.group(2))
        rec = per_instrument.setdefault(inst, {"max_sub": 0, "name": desc})
        rec["max_sub"] = max(rec["max_sub"], sub)
        # Preserve the first non-empty trend name we see for this instrument
        if not rec["name"] and desc:
            rec["name"] = desc

    mismatches: list[SubcolMismatch] = []
    for inst, info in per_instrument.items():
        name = info["name"] or ""
        observed = info["max_sub"]
        family = classify_trend(name)

        if family is None:
            continue  # Unknown family — don't speculate

        if family in EXPECTED_SUBCOL_COUNTS_FIXED:
            expected = EXPECTED_SUBCOL_COUNTS_FIXED[family]
            # Special case: rhythmicity_spectrogram can be 97 (sqrt) or 73 (linear)
            if family == "rhythmicity_spectrogram" and observed == RHYTHMICITY_SPECTROGRAM_LINEAR_COUNT:
                continue
            if observed != expected:
                mismatches.append(SubcolMismatch(
                    instrument_index=inst, trend_name=name, family=family,
                    expected=expected, observed=observed,
                    severity="error",
                    detail=(f"fixed-cardinality family — see "
                            f"PersystTrendCSV_Format_Reference.md §3 for {family}"),
                ))
            continue

        if family in EXPECTED_SUBCOL_COUNTS_VARIABLE:
            expected, why = EXPECTED_SUBCOL_COUNTS_VARIABLE[family]
            if observed != expected:
                mismatches.append(SubcolMismatch(
                    instrument_index=inst, trend_name=name, family=family,
                    expected=expected, observed=observed,
                    severity="warn",
                    detail=f"recording-system-dependent ({why}); V7 reference = {expected}",
                ))
            continue

        if family in SINGLE_VALUE_FAMILIES:
            if observed != 1:
                mismatches.append(SubcolMismatch(
                    instrument_index=inst, trend_name=name, family=family,
                    expected=1, observed=observed,
                    severity="error",
                    detail="single-value family — sub-col count must be 1",
                ))

    return mismatches


def log_and_partition(
    mismatches: Iterable[SubcolMismatch],
) -> tuple[list[SubcolMismatch], list[SubcolMismatch]]:
    """Log mismatches at appropriate level and split into (errors, warnings)."""
    errors: list[SubcolMismatch] = []
    warnings_: list[SubcolMismatch] = []
    for m in mismatches:
        if m.severity == "error":
            logger.error("Persyst sub-col contract violation: %s", m)
            errors.append(m)
        else:
            logger.warning("Persyst sub-col deviation (allowed): %s", m)
            warnings_.append(m)
    return errors, warnings_
