"""Regression tests for qeeg.ingestion.subcol_validator.

Verifies the sub-column count contract defined in
`PersystTrendCSV_Format_Reference.md` §3.0 holds against the real V7 Research
panel export. The export is expected at:
  C:/Users/craig/OneDrive/Documents/0_PEDQuEST/EEG Analytics Pipeline/1002_1.csv

If the export is missing on this machine, tests that depend on it are skipped
rather than failing CI on developer workstations without the real data.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from qeeg.ingestion.subcol_validator import (
    classify_trend,
    validate_subcol_counts,
    EXPECTED_SUBCOL_COUNTS_FIXED,
    EXPECTED_SUBCOL_COUNTS_VARIABLE,
)


V7_RESEARCH_CSV = Path(
    r"C:\Users\craig\OneDrive\Documents\0_PEDQuEST\EEG Analytics Pipeline\1002_1.csv"
)


def _read_header_rows(path: Path) -> tuple[list[str], list[str]]:
    """Read just the trend-name row (row 7) and ID row (row 8) from a Persyst CSV."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [f.readline() for _ in range(8)]
    trend_row = next(csv.reader(io.StringIO(lines[6])))
    id_row = next(csv.reader(io.StringIO(lines[7])))
    return trend_row, id_row


def _build_code_to_description(trend_row: list[str], id_row: list[str]) -> dict[str, str]:
    """Replicate parser._fill_forward + zip logic for header rows."""
    # Forward-fill empty trend cells with the previous non-empty value
    filled = []
    last = ""
    for cell in trend_row:
        if cell.strip():
            last = cell.strip()
        filled.append(last)
    code_to_desc = {}
    for code, desc in zip(id_row, filled):
        code = code.strip()
        if code and code != "ClockDateTime":
            code_to_desc[code] = desc
    return code_to_desc


# ---------------------------------------------------------------------------
# Unit-level classifier tests (no CSV required)
# ---------------------------------------------------------------------------

def test_classify_artifact_intensity():
    assert classify_trend("Artifact Intensity") == "artifact_intensity"


def test_classify_aeeg():
    assert classify_trend("aEEG, Left Hemisphere") == "aeeg"


def test_classify_fft_spectrogram():
    assert classify_trend("FFT Spectrogram, C3-P3") == "fft_spectrogram"


def test_classify_rhythmicity_freqpow_before_full_spectrogram():
    # FreqPow must match before the generic "Rhythmicity Spectrogram" classifier
    assert classify_trend(
        "Rhythmicity Spectrogram FreqPow LA , 1 - 25 Hz, Left Anterior"
    ) == "rhythmicity_freqpow"
    assert classify_trend("Rhythmicity Spectrogram, C3-P3") == "rhythmicity_spectrogram"


def test_classify_coherence():
    assert classify_trend("Coherence_Spectrogram 0-32 C3-P3*C4-P4, C3-P3*C4-P4") == "coherence_spectrogram"
    assert classify_trend("Coherence_Avg 0-32 C3-P3*C4-P4, C3-P3*C4-P4") == "coherence_avg"


def test_classify_seizure_pair():
    assert classify_trend(
        "Seizure Detections (red) and Notifications (gray)"
    ) == "seizure_detection_notif_pair"


def test_classify_unknown_returns_none():
    assert classify_trend("") is None
    assert classify_trend("Some unknown future trend") is None


# ---------------------------------------------------------------------------
# Expected-count table sanity
# ---------------------------------------------------------------------------

def test_expected_counts_match_doc():
    """Hard-coded expectations from PersystTrendCSV_Format_Reference.md §3.0."""
    assert EXPECTED_SUBCOL_COUNTS_FIXED["artifact_intensity"] == 3
    assert EXPECTED_SUBCOL_COUNTS_FIXED["aeeg"] == 5
    assert EXPECTED_SUBCOL_COUNTS_FIXED["seizure_detection_notif_pair"] == 2
    assert EXPECTED_SUBCOL_COUNTS_FIXED["rhythmicity_freqpow"] == 16
    assert EXPECTED_SUBCOL_COUNTS_FIXED["fft_spectrogram"] == 40
    assert EXPECTED_SUBCOL_COUNTS_FIXED["asymmetry_spectrogram"] == 40
    assert EXPECTED_SUBCOL_COUNTS_FIXED["coherence_spectrogram"] == 63
    assert EXPECTED_SUBCOL_COUNTS_FIXED["rhythmicity_spectrogram"] == 97
    assert EXPECTED_SUBCOL_COUNTS_VARIABLE["electrode_signal_quality"][0] == 22


# ---------------------------------------------------------------------------
# Synthetic validator behavior
# ---------------------------------------------------------------------------

def test_validator_flags_fft_short_by_one():
    """39 FFT_Spectrogram sub-cols (one short of 40) → error."""
    bad = {f"I1_{k}": "FFT Spectrogram, C3-P3" for k in range(1, 40)}
    mm = validate_subcol_counts(bad)
    assert len(mm) == 1
    assert mm[0].severity == "error"
    assert mm[0].observed == 39 and mm[0].expected == 40
    assert mm[0].family == "fft_spectrogram"


def test_validator_accepts_correct_counts():
    """Well-formed instruments produce no mismatches."""
    code_to_desc = {}
    code_to_desc.update({f"I1_{k}": "Artifact Intensity" for k in range(1, 4)})           # 3
    code_to_desc.update({f"I2_{k}": "Artifact Detector"  for k in range(1, 19)})          # 18
    code_to_desc.update({f"I3_{k}": "Electrode Signal Quality" for k in range(1, 23)})    # 22
    code_to_desc.update({f"I4_{k}": "aEEG, Left Hemisphere" for k in range(1, 6)})        # 5
    code_to_desc.update({f"I5_{k}": "FFT Spectrogram, C3-P3" for k in range(1, 41)})      # 40
    code_to_desc.update({f"I6_{k}": "Rhythmicity Spectrogram, C3-P3" for k in range(1, 98)})  # 97
    code_to_desc.update({f"I7_{k}": "Coherence_Spectrogram 0-32 X" for k in range(1, 64)})    # 63
    mm = validate_subcol_counts(code_to_desc)
    assert mm == []


def test_validator_warns_on_eq_count_mismatch():
    """Electrode Signal Quality with a non-22 count → warn, not error."""
    bad = {f"I3_{k}": "Electrode Signal Quality" for k in range(1, 19)}  # 18 (legacy)
    mm = validate_subcol_counts(bad)
    assert len(mm) == 1
    assert mm[0].severity == "warn"
    assert mm[0].observed == 18 and mm[0].expected == 22


def test_validator_accepts_linear_rhythmicity_variant():
    """73-bin linear-scaled rhythmicity is an allowed alternative, not an error."""
    ok = {f"I1_{k}": "Rhythmicity Spectrogram, C3-P3" for k in range(1, 74)}  # 73
    mm = validate_subcol_counts(ok)
    assert mm == []


# ---------------------------------------------------------------------------
# Live V7 CSV check
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not V7_RESEARCH_CSV.exists(),
    reason=f"V7 Research-panel CSV not available at {V7_RESEARCH_CSV}",
)
def test_v7_research_csv_passes_subcol_contract():
    """The real V7 Research export must satisfy the sub-col contract.

    Any error-severity mismatch indicates the contract is wrong (or the export
    has drifted). Warn-severity mismatches (e.g. Electrode Signal Quality on a
    different acquisition system) are acceptable but should be logged.
    """
    trend_row, id_row = _read_header_rows(V7_RESEARCH_CSV)
    code_to_desc = _build_code_to_description(trend_row, id_row)
    mismatches = validate_subcol_counts(code_to_desc)
    errors = [m for m in mismatches if m.severity == "error"]
    assert errors == [], (
        f"V7 Research CSV violated the fixed-cardinality sub-col contract:\n"
        + "\n".join(str(m) for m in errors)
    )
