"""Manifest builder endpoint — groups scanned files by patient and validates."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

log = logging.getLogger(__name__)

from api.models.schemas import (
    ManifestBuildRequest,
    ManifestBuildResponse,
    PatientManifestEntry,
    ScannedFile,
)

router = APIRouter(prefix="/api", tags=["manifest"])

# Year range outside which we consider EEG timestamps de-identified / date-shifted
_PLAUSIBLE_YEAR_MIN = 2000
_PLAUSIBLE_YEAR_MAX = 2040


def _is_deidentified_date(eeg_start: Optional[str]) -> bool:
    """Return True if eeg_start looks like a de-identified (date-shifted) timestamp.

    Heuristic: years outside [2000, 2040] are not plausible for real clinical recordings.
    """
    if not eeg_start:
        return False
    try:
        import pandas as pd

        year = pd.Timestamp(eeg_start).year
        return not (_PLAUSIBLE_YEAR_MIN <= year <= _PLAUSIBLE_YEAR_MAX)
    except Exception:
        return False


def _build_patient_entry(
    patient_id: str,
    group,  # PatientFileGroup from patient_grouper
    clinical_csv: Optional[str],
    corrections_csv: Optional[str],
    raw_eeg_by_prefix: dict[str, list[str]],
) -> PatientManifestEntry:
    persyst_files = [str(p) for p in group.files]
    file_panel_types = [s.csv_panel_type for s in group.scans]
    n_columns_per_file = [s.n_columns for s in group.scans]

    validation_errors: list[str] = []
    validation_warnings: list[str] = []

    # All persyst_csv types are processable — time_averages and trend files are
    # merged by semantic column name in merge_segments_by_semantic_name.
    all_csv_files = group.trend_files + group.time_average_files + group.spectrogram_files + group.other_files
    if not all_csv_files:
        validation_errors.append("No Persyst CSV files found for this patient")

    # Montage compatibility: warn only — different column counts are expected when Persyst exports
    # multiple panels into separate CSVs; the pipeline outer-joins them column-wise.
    trend_scans = [s for s in group.scans if s.csv_panel_type == "trends"]
    unique_col_counts = set(s.n_columns for s in trend_scans) if trend_scans else set()
    if len(unique_col_counts) > 1:
        validation_warnings.append(
            f"Trend files have different column counts {sorted(unique_col_counts)} — will be merged column-wise"
        )

    # De-identified date detection
    requires_corrections = any(
        _is_deidentified_date(s.eeg_start) for s in group.scans
    )
    if requires_corrections and corrections_csv is None:
        validation_errors.append(
            "De-identified dates detected but no corrections CSV was found in the scan"
        )

    # Warn if clinical metadata is absent (non-blocking)
    if clinical_csv is None:
        validation_warnings.append(
            "No clinical CSV found — age and ROSC time will not be available"
        )

    patient_raw_eeg = raw_eeg_by_prefix.get(patient_id, [])

    return PatientManifestEntry(
        patient_id=patient_id,
        persyst_files=persyst_files,
        file_panel_types=file_panel_types,
        clinical_csv=clinical_csv,
        corrections_csv=corrections_csv,
        raw_eeg_files=patient_raw_eeg,
        total_duration_hours=round(group.total_duration_hours, 4),
        total_epochs=group.total_epochs,
        n_columns_per_file=n_columns_per_file,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        requires_corrections=requires_corrections,
    )


@router.post("/manifest/build", response_model=ManifestBuildResponse)
def build_manifest(req: ManifestBuildRequest):
    """Group scan results by patient and validate for batch processing.

    Accepts: list of ScannedFile from POST /api/scan/folder.
    Groups Persyst CSVs via patient_grouper, attaches companion files,
    and validates montage compatibility + corrections requirement.
    """
    from qeeg.ingestion.patient_grouper import group_files_by_patient

    persyst_paths: list[Path] = []
    clinical_csv: Optional[str] = None
    corrections_csv: Optional[str] = None
    raw_eeg_files: list[str] = []

    for f in req.scanned_files:
        match f.file_type:
            case "persyst_csv":
                persyst_paths.append(Path(f.path))
            case "clinical_csv":
                clinical_csv = f.path  # last one wins if multiple present
            case "corrections_csv":
                corrections_csv = f.path
            case "raw_eeg":
                raw_eeg_files.append(f.path)

    if not persyst_paths:
        raise HTTPException(400, "No Persyst CSV files found in scan results")

    groups = group_files_by_patient(persyst_paths)

    # Index raw EEG files by patient ID prefix for companion matching
    raw_eeg_by_prefix: dict[str, list[str]] = {}
    for rp in raw_eeg_files:
        stem = Path(rp).stem
        prefix = stem.split("_", 1)[0] if "_" in stem else stem
        raw_eeg_by_prefix.setdefault(prefix, []).append(rp)

    patients: list[PatientManifestEntry] = [
        _build_patient_entry(
            patient_id=patient_id,
            group=group,
            clinical_csv=clinical_csv,
            corrections_csv=corrections_csv,
            raw_eeg_by_prefix=raw_eeg_by_prefix,
        )
        for patient_id, group in sorted(groups.items())
    ]

    # Auto-ingest clinical CSV so ROSC / age metadata is available without a
    # separate manual upload step.
    if clinical_csv:
        try:
            from api.routes.upload import _parse_clinical_csv_from_path, get_service
            metadata_list = _parse_clinical_csv_from_path(Path(clinical_csv))
            get_service().store_clinical_metadata(metadata_list)
            log.info(
                "Auto-ingested clinical metadata from %s (%d records)",
                clinical_csv, len(metadata_list),
            )
        except Exception as exc:
            log.warning("Auto-ingest of clinical CSV %s failed: %s", clinical_csv, exc)

    n_valid = sum(1 for p in patients if not p.validation_errors)
    n_errors = sum(1 for p in patients if p.validation_errors)
    n_warnings = sum(
        1 for p in patients if p.validation_warnings and not p.validation_errors
    )

    return ManifestBuildResponse(
        patients=patients,
        total_patients=len(patients),
        global_clinical_csv=clinical_csv,
        global_corrections_csv=corrections_csv,
        validation_summary={"valid": n_valid, "errors": n_errors, "warnings": n_warnings},
    )
