from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    total_rows: int = 0
    leading_zero_rows: int = 0
    timestamp_gaps: list[dict] = field(default_factory=list)  # [{start_idx, end_idx, gap_seconds}]
    out_of_range: dict[str, int] = field(default_factory=dict)  # {column: count}
    phi_detected: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Report is valid only if there are no warnings AND no PHI detected."""
        if self.phi_detected:
            return False
        return len(self.warnings) == 0


def detect_leading_zeros(df: pd.DataFrame, fft_columns: list[str]) -> int:
    """Find how many leading rows have all-zero FFT values (engine startup).

    Scans all rows until the first non-zero FFT value is found.
    """
    if not fft_columns:
        return 0
    fft_data = df[fft_columns]
    for i in range(len(fft_data)):
        if (fft_data.iloc[i] != 0).any():
            return i
    return len(fft_data)


def detect_timestamp_gaps(timestamps: pd.Series, threshold_seconds: float = 60.0) -> list[dict]:
    """Find gaps in timestamps exceeding threshold.

    Uses positional indexing so this works regardless of the Series index type.
    """
    if len(timestamps) < 2:
        return []
    diffs = timestamps.diff().dt.total_seconds()
    gaps = []
    for pos in range(len(diffs)):
        val = diffs.iloc[pos]
        if pd.notna(val) and val > threshold_seconds:
            gaps.append({
                "start_idx": pos - 1,
                "end_idx": pos,
                "gap_seconds": float(val),
            })
    return gaps


# Physiologically plausible value range per family, from actual Persyst output
# scales. Module-level so the doc-sync generator (scripts/sync_persyst_docs.py)
# reads the SAME source — never restate these ranges in prose docs.
#   fft_power 0–500 µV²; fft_power_ratio/adr 0–100 (dimensionless); relative_power
#   0–1 (band / total 1-30 Hz); electrode_quality/seizure_probability 0–1;
#   status_epilepticus/seizure_burden 0–100; artifact_intensity 0–50 (BSS power);
#   aeeg 0–500 µV.
FAMILY_VALUE_RANGES: dict[str, tuple[float, float]] = {
    "fft_power": (0, 500),
    "fft_power_ratio": (0, 100),
    "adr": (0, 100),
    "relative_power": (0, 1),
    "electrode_quality": (0, 1.2),  # actual data caps at 1.2 (Persyst disconnect marker)
    "seizure_probability": (0, 1),
    "status_epilepticus": (0, 100),
    "seizure_burden": (0, 100),
    "artifact_intensity": (0, 50),
    "aeeg": (0, 500),
    # Bounds below are inferred from the documented unit scales in
    # export._FAMILY_UNITS (kept in sync via the families.generated contract).
    # suppression_ratio guards the BSR percent-scale class fixed in pipeline.py.
    "suppression_ratio": (0, 100),         # % burst-suppression
    "asymmetry": (-1, 1),                  # asymmetry index
    "asymmetry_spectrogram": (-100, 100),  # % per bin
    "coherence_spectrogram": (0, 1),       # coherence
    "spectral_edge": (0, 50),              # Hz (SEF)
    "peak_envelope": (0, 500),             # µV
    "heart_rate": (0, 300),                # bpm
    "rhythmic_delta": (0, 1),          # boolean 0/1
    "seizure_detection": (0, 1),           # boolean 0/1
    "seizure_notification": (0, 1),        # boolean 0/1
}


def check_value_ranges(df: pd.DataFrame, column_families: dict[str, list[str]]) -> dict[str, int]:
    """Check for physiologically implausible values per family.

    Ranges come from the module-level :data:`FAMILY_VALUE_RANGES`.
    """
    ranges = FAMILY_VALUE_RANGES
    out_of_range = {}
    for family, cols in column_families.items():
        if family not in ranges:
            continue
        lo, hi = ranges[family]
        existing = [c for c in cols if c in df.columns]
        if not existing:
            continue
        subset = df[existing]
        bad_count = int(((subset < lo) | (subset > hi)).sum().sum())
        if bad_count > 0:
            out_of_range[family] = bad_count
    return out_of_range


def strip_phi_metadata(metadata) -> None:
    """Clear all PHI-containing fields from ExportMetadata in-place."""
    metadata.patient_name = ""
    metadata.patient_id = ""
    metadata.test_date = ""
    metadata.test_time = ""


def validate_export(df: pd.DataFrame, timestamps: pd.Series, fft_columns: list[str],
                    column_families: dict[str, list[str]], metadata=None) -> ValidationReport:
    """Run all validation checks on a parsed export."""
    report = ValidationReport(total_rows=len(df))
    report.leading_zero_rows = detect_leading_zeros(df, fft_columns)
    if report.leading_zero_rows > 0:
        report.warnings.append(f"Warning: {report.leading_zero_rows} leading zero rows (FFT engine startup)")
    report.timestamp_gaps = detect_timestamp_gaps(timestamps)
    if report.timestamp_gaps:
        report.warnings.append(f"Warning: {len(report.timestamp_gaps)} timestamp gaps detected")
    report.out_of_range = check_value_ranges(df, column_families)
    for family, count in report.out_of_range.items():
        report.warnings.append(f"Warning: {count} out-of-range values in {family}")
    if metadata and metadata.patient_name and metadata.patient_name.replace("X", "").replace("x", "").strip():
        report.phi_detected = True
        report.warnings.append("Warning: Possible PHI detected in patient name")
        strip_phi_metadata(metadata)
    return report
