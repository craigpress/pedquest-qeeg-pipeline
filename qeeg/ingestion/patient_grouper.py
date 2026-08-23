"""Group EEG export files by patient ID."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .identity import derive_patient_id
from .quick_scan import quick_scan, QuickScanResult


@dataclass
class PatientFileGroup:
    patient_id: str
    files: list[Path] = field(default_factory=list)
    scans: list[QuickScanResult] = field(default_factory=list)
    total_duration_hours: float = 0.0
    total_epochs: int = 0
    trend_files: list[Path] = field(default_factory=list)
    spectrogram_files: list[Path] = field(default_factory=list)
    time_average_files: list[Path] = field(default_factory=list)
    other_files: list[Path] = field(default_factory=list)


# Metadata patient_id values that are placeholders, not real IDs
_JUNK_PIDS = {"x", "xx", "xxx", "xxxx", "xxxxx", "xxxxxx", "xxxxxxx",
              "test", "patient", "unknown", "na", "n/a", "none", ""}


def _is_valid_pid(pid: str) -> bool:
    """Return True if pid looks like a real patient identifier."""
    if not pid:
        return False
    if pid.lower().strip() in _JUNK_PIDS:
        return False
    # Single character is too generic to be a real patient ID
    if len(pid) <= 1:
        return False
    return True


def group_files_by_patient(paths: list[Path]) -> dict[str, PatientFileGroup]:
    """Scan files and group by patient ID.

    Patient ID is determined by:
    1. Metadata patient_id from CSV header (if valid — not a placeholder like 'X')
    2. Filename stem pattern: extract numeric prefix before underscore
       (e.g., '2046_1.csv' -> '2046', '2046_2.csv' -> '2046')
    3. Full filename stem as fallback
    """
    groups: dict[str, PatientFileGroup] = {}

    for p in paths:
        scan_result = quick_scan(p)

        # Determine patient ID — prefer metadata, but reject junk values
        pid = scan_result.patient_id
        if not _is_valid_pid(pid) or pid == p.stem:
            # Shared identity rule (see qeeg.ingestion.identity):
            #   "2046_1"          → "2046"      (PedQuEST: numeric studyID_eegNumber)
            #   "01-001_UUID_2"   → "01-001"    (POCCA: siteID-patientID_UUID_eegNumber)
            #   "01-001"          → "01-001"    (first EEG, no underscore)
            pid = derive_patient_id(p.stem) or p.stem

        if pid not in groups:
            groups[pid] = PatientFileGroup(patient_id=pid)

        groups[pid].files.append(p)
        groups[pid].scans.append(scan_result)

    # Sort files within each group by EEG start time, then build typed lists
    for group in groups.values():
        paired = sorted(
            zip(group.scans, group.files),
            key=lambda x: x[0].eeg_start or "",
        )
        group.scans = [s for s, _ in paired]
        group.files = [f for _, f in paired]

        # Build typed lists in sorted order; accumulate stats from trend files only
        for scan, f in zip(group.scans, group.files):
            panel = scan.csv_panel_type
            if panel == "spectrograms":
                group.spectrogram_files.append(f)
            elif panel == "time_averages":
                group.time_average_files.append(f)
            elif panel == "trends":
                group.trend_files.append(f)
                group.total_epochs += scan.n_data_rows
                if scan.duration_hours:
                    group.total_duration_hours += scan.duration_hours
            else:
                group.other_files.append(f)

    return groups
