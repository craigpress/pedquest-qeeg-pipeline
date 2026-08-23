"""Patient data endpoints — summary, epochs, spectrograms, bins, overlays."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from api.models.schemas import (
    PatientSummary, QCSummary, SeizureSummary, TimeAxisResponse,
    ColumnEntryResponse, EpochDataResponse,
    SpectrogramResponse, BinSummaryResponse, BinRow,
    OverlayDataResponse, ArtifactRegion,
    ComparisonResponse, ComparisonMetric,
    ChartPanelMetadata, ChartMetadataResponse,
)

router = APIRouter(prefix="/api", tags=["patients"])


def get_service():
    from api.main import pipeline_service
    return pipeline_service


def _safe_float(val) -> float | None:
    """Convert to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f  # NaN check
    except (TypeError, ValueError):
        return None


def _get_result_or_404(patient_id: str):
    service = get_service()
    result = service.get_result(patient_id)
    if not result:
        raise HTTPException(404, f"Patient '{patient_id}' not found. Process data first.")
    return result


def _parse_clock_time(value: str) -> tuple[int, int, float] | None:
    """Parse a clock-time string into (hours, minutes, seconds).

    Tolerates:
      - HH:MM (seconds default to 0)
      - HH:MM:SS
      - HH:MM:SS.ffffff (fractional seconds)
      - Optional trailing AM/PM suffix (case-insensitive, spaces allowed)

    Returns None if parsing fails.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Strip trailing AM/PM (caller's 24h values are left alone if no suffix)
    suffix = None
    upper = s.upper()
    for mark in (" AM", " PM", "AM", "PM"):
        if upper.endswith(mark):
            suffix = mark.strip()
            s = s[: -len(mark)].strip()
            break
    parts = s.split(":")
    if len(parts) < 2 or len(parts) > 3:
        return None
    try:
        h = int(parts[0])
        m = int(parts[1])
        sec = float(parts[2]) if len(parts) == 3 else 0.0
    except ValueError:
        return None
    if suffix == "PM" and h < 12:
        h += 12
    elif suffix == "AM" and h == 12:
        h = 0
    return (h, m, sec)


def _split_datetime_str(value: str) -> tuple[str | None, str | None]:
    """Split a combined datetime string into (date_part, time_part).

    Handles ISO ("2024-01-15 08:30"), US ("1/15/2024 08:30"), or 'T' separator.
    Either part may be None if not recognizable.
    """
    if not value:
        return None, None
    s = str(value).strip().replace("T", " ")
    parts = s.split(None, 1)  # split on any whitespace, max 1
    if len(parts) == 2:
        return parts[0], parts[1]
    # Single token — treat as date if no colon, else time
    if ":" in parts[0]:
        return None, parts[0]
    return parts[0], None


def _build_time_axis_response(patient_id: str, time_info) -> TimeAxisResponse:
    """Build enriched TimeAxisResponse from time_info + clinical metadata + corrections."""
    service = get_service()
    clinical = service.get_clinical_metadata(patient_id)
    study_name = service.get_patient_study(patient_id)
    study = service.get_study(study_name) if study_name else None
    date_shifted = study.date_shifted if study else False

    resp = TimeAxisResponse(
        reference=time_info.reference,
        reference_time=str(time_info.reference_time),
        date_shifted=date_shifted,
    )

    if clinical:
        resp.age_at_arrest_days = clinical.age_at_arrest_days
        resp.rosc_time = clinical.rosc_time
        # If combined datetime was stored, split into date + time parts.
        # effective_rosc_datetime resolves rosc_datetime OR rosc_date+rosc_time.
        combined = clinical.effective_rosc_datetime
        rosc_date_from_combined, rosc_time_from_combined = _split_datetime_str(combined)
        if not resp.rosc_time and rosc_time_from_combined:
            resp.rosc_time = rosc_time_from_combined
        # Expose rosc_date only when the study is not date-shifted (synthetic
        # dates are meaningless calendar-wise).
        if not date_shifted:
            resp.rosc_date = clinical.rosc_date or rosc_date_from_combined

    # Look up EEG correction for the first source file to get EEG start info
    # Corrections are keyed by file stem (e.g. "2046_1")
    patient_corrections = [
        c for name, c in service._eeg_corrections.items()
        if name == patient_id or name.startswith(f"{patient_id}_")
    ]
    if patient_corrections:
        first_corr = sorted(patient_corrections, key=lambda c: (c.age_in_days_at_time_of_eeg, c.eeg_start_time))[0]
        resp.age_at_eeg_start_days = first_corr.age_in_days_at_time_of_eeg
        resp.eeg_start_time = first_corr.eeg_start_time
        # Derive eeg_start_date: for real-date studies, compute from rosc_date
        # + (age_at_eeg - age_at_arrest) day offset. For date-shifted studies,
        # leave null (synthetic dates are meaningless).
        if not date_shifted and resp.rosc_date and resp.age_at_arrest_days is not None:
            try:
                import pandas as pd
                day_offset = first_corr.age_in_days_at_time_of_eeg - resp.age_at_arrest_days
                eeg_date = (pd.Timestamp(resp.rosc_date) + pd.Timedelta(days=day_offset)).date()
                resp.eeg_start_date = str(eeg_date)
            except (ValueError, TypeError):
                pass

    # Compute hours from ROSC to EEG if both times are available.
    # Uses age-day deltas as the date anchor — works for both real-date and
    # date-shifted studies as long as clinical + corrections both supply ages.
    if (
        resp.rosc_time and resp.eeg_start_time
        and resp.age_at_arrest_days is not None
        and resp.age_at_eeg_start_days is not None
    ):
        rosc_parts = _parse_clock_time(resp.rosc_time)
        eeg_parts = _parse_clock_time(resp.eeg_start_time)
        if rosc_parts and eeg_parts:
            day_diff = resp.age_at_eeg_start_days - resp.age_at_arrest_days
            rh, rm, rs = rosc_parts
            eh, em, es = eeg_parts
            rosc_hours = rh + rm / 60 + rs / 3600
            eeg_hours = eh + em / 60 + es / 3600
            resp.hours_rosc_to_eeg = round(day_diff * 24 + (eeg_hours - rosc_hours), 2)

    return resp


def _build_patient_summary(result) -> PatientSummary:
    families = sorted({e.family for e in result.schema})
    study_name = get_service().get_patient_study(result.patient_id)
    return PatientSummary(
        patient_id=result.patient_id,
        qc=QCSummary(
            total_epochs=result.qc.total_epochs,
            usable_epochs=result.qc.usable_epochs,
            artifact_pct=result.qc.artifact_pct,
            seizure_epochs=result.qc.seizure_epochs,
            seizure_pct=result.qc.seizure_pct_of_total,
            recording_duration_hours=result.qc.recording_duration_hours,
            usable_hours=result.qc.usable_hours,
            median_suppression_pct=result.qc.median_suppression_pct,
            bin_coverage=result.qc.bin_coverage,
            warnings=result.qc.warnings,
        ),
        seizure=SeizureSummary(
            total_seizure_epochs=result.seizure_report.total_seizure_epochs,
            seizure_burden_pct=result.seizure_report.seizure_burden_pct,
            max_seizure_probability=result.seizure_report.max_seizure_probability,
            seizure_events=result.seizure_report.seizure_events,
            max_hourly_burden_pct=result.seizure_report.max_hourly_burden_pct,
            has_status_epilepticus=result.seizure_report.has_status_epilepticus,
            status_epilepticus_screen_flag=result.seizure_report.has_status_epilepticus,
            longest_seizure_minutes=result.seizure_report.longest_seizure_minutes,
            time_to_first_seizure_hours=result.seizure_report.time_to_first_seizure_hours,
            per_bin_burden=result.seizure_report.per_bin_burden,
        ),
        time_axis=_build_time_axis_response(result.patient_id, result.time_info),
        n_columns=len(result.schema),
        n_epochs=len(result.epochs),
        families=families,
        study_name=study_name,
    )


def _build_patient_summary_from_meta(meta) -> PatientSummary:
    """Build PatientSummary from lightweight PatientMeta (no DataFrame loading)."""
    families = sorted({e.family for e in meta.schema})
    study_name = get_service().get_patient_study(meta.patient_id)
    return PatientSummary(
        patient_id=meta.patient_id,
        qc=QCSummary(
            total_epochs=meta.qc.total_epochs,
            usable_epochs=meta.qc.usable_epochs,
            artifact_pct=meta.qc.artifact_pct,
            seizure_epochs=meta.qc.seizure_epochs,
            seizure_pct=meta.qc.seizure_pct_of_total,
            recording_duration_hours=meta.qc.recording_duration_hours,
            usable_hours=meta.qc.usable_hours,
            bin_coverage=meta.qc.bin_coverage,
            warnings=meta.qc.warnings,
        ),
        seizure=SeizureSummary(
            total_seizure_epochs=meta.seizure_report.total_seizure_epochs,
            seizure_burden_pct=meta.seizure_report.seizure_burden_pct,
            max_seizure_probability=meta.seizure_report.max_seizure_probability,
            seizure_events=meta.seizure_report.seizure_events,
            max_hourly_burden_pct=meta.seizure_report.max_hourly_burden_pct,
            has_status_epilepticus=meta.seizure_report.has_status_epilepticus,
            status_epilepticus_screen_flag=meta.seizure_report.has_status_epilepticus,
            longest_seizure_minutes=meta.seizure_report.longest_seizure_minutes,
            time_to_first_seizure_hours=meta.seizure_report.time_to_first_seizure_hours,
            per_bin_burden=meta.seizure_report.per_bin_burden,
        ),
        time_axis=_build_time_axis_response(meta.patient_id, meta.time_info),
        n_columns=len(meta.schema),
        n_epochs=meta.n_epochs,
        families=families,
        study_name=study_name,
    )


@router.get("/patients", response_model=list[PatientSummary])
async def list_patients(study: str | None = None):
    """List all processed patients with summary info, optionally filtered by study.

    Uses lightweight PatientMeta (no DataFrame loading) for fast response.
    """
    service = get_service()
    pids = service.list_patients()
    if study:
        study_pids = set(service.list_patients_by_study(study))
        pids = [p for p in pids if p in study_pids]
    summaries = []
    for pid in pids:
        meta = service.get_patient_meta(pid)
        if meta:
            summaries.append(_build_patient_summary_from_meta(meta))
    return summaries


@router.get("/patients/{patient_id}", response_model=PatientSummary)
async def get_patient(patient_id: str):
    """Get patient metadata and QC summary."""
    service = get_service()
    meta = service.get_patient_meta(patient_id)
    if meta:
        return _build_patient_summary_from_meta(meta)
    # Fallback to full result load for backward compatibility
    result = _get_result_or_404(patient_id)
    return _build_patient_summary(result)


@router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str):
    """Delete a patient's cached results."""
    service = get_service()
    meta = service.get_patient_meta(patient_id)
    if not meta:
        raise HTTPException(404, f"Patient '{patient_id}' not found")

    # Remove from index and hot cache
    service.remove_patient(patient_id)

    # Remove from disk cache
    from qeeg.storage.result_cache import clear_cache
    cleared = clear_cache(patient_id, service.cache_dir)

    return {"deleted": patient_id, "cache_cleared": cleared}


@router.get("/patients/{patient_id}/schema", response_model=list[ColumnEntryResponse])
async def get_patient_schema(patient_id: str):
    """Get the column schema for a patient."""
    result = _get_result_or_404(patient_id)
    return [
        ColumnEntryResponse(
            col_index=e.col_index, code=e.code, i_group=e.i_group,
            sub_index=e.sub_index, trend_name=e.trend_name, family=e.family,
            frequency_band=e.frequency_band, freq_min_hz=e.freq_min_hz,
            freq_max_hz=e.freq_max_hz, hemisphere=e.hemisphere, region=e.region,
            electrode=e.electrode, sub_column_name=e.sub_column_name,
            common_name=e.common_name,
        )
        for e in result.schema
    ]


@router.get("/patients/{patient_id}/chart-metadata", response_model=ChartMetadataResponse)
async def get_chart_metadata(patient_id: str):
    """Get metadata for each dashboard chart panel (variables, units, derivation)."""
    result = _get_result_or_404(patient_id)
    from qeeg.storage.export import build_chart_metadata

    config = getattr(result, "config", None)
    config_dict = config if isinstance(config, dict) else None
    engines = getattr(result, "engines", None)

    panels = build_chart_metadata(result.schema, config_dict, engines)
    return ChartMetadataResponse(
        panels=[ChartPanelMetadata(**p) for p in panels],
    )


@router.get("/patients/{patient_id}/epochs", response_model=EpochDataResponse)
def get_epochs(
    patient_id: str,
    families: str = Query(..., description="Comma-separated column families, e.g. fft_power,aeeg"),
    max_points: int = Query(2000, description="Max time points (server-side downsample)"),
    column_filter: Optional[str] = Query(None, description="Substring filter for column names (e.g. 'easi' to get only EASI/REASI)"),
    columns: Optional[str] = Query(None, description="Comma-separated exact output column names to return"),
):
    """Get epoch data for specific column families (columnar format).

    Server-side downsampling to max_points (default 2000) reduces JSON payload
    from ~36MB to ~1.7MB for fft_power. Frontend no longer needs to downsample.
    """
    service = get_service()
    if not service.get_patient_meta(patient_id):
        raise HTTPException(404, f"Patient '{patient_id}' not found. Process data first.")
    family_list = [f.strip() for f in families.split(",") if f.strip()]
    requested_columns = {c.strip() for c in columns.split(",") if c.strip()} if columns else None
    hours, data_columns = service.get_epoch_data_selective(patient_id, family_list, requested_columns)
    usable = data_columns.pop("_usable", [True] * len(hours))

    # Apply column name filter if provided (e.g. "easi" keeps only EASI/REASI columns)
    if column_filter:
        filt = column_filter.lower()
        data_columns = {k: v for k, v in data_columns.items() if filt in k.lower()}

    n = len(hours)
    if n > max_points and max_points > 0:
        step = n / max_points
        ds_hours = []
        ds_usable = []
        ds_columns: dict[str, list] = {k: [] for k in data_columns}
        for i in range(max_points):
            start = int(i * step)
            end = min(int((i + 1) * step), n)
            mid = (start + end) // 2
            ds_hours.append(hours[mid])
            ds_usable.append(usable[mid])
            for k, vals in data_columns.items():
                # Peak-preserve for seizure probability, use midpoint for others
                if "seizure" in k and "probability" in k:
                    window = [vals[t] for t in range(start, end) if vals[t] is not None]
                    ds_columns[k].append(max(window) if window else None)
                else:
                    ds_columns[k].append(vals[mid])
        hours = ds_hours
        usable = ds_usable
        data_columns = ds_columns

    return EpochDataResponse(hours=hours, usable=usable, columns=data_columns)


@router.get("/patients/{patient_id}/spectrogram/{spec_type}", response_model=SpectrogramResponse)
def get_spectrogram(
    patient_id: str,
    spec_type: str,
    max_time_points: int = 2000,
):
    """Get spectrogram matrix. spec_type: fft_left, fft_right, asymmetry, rhythmicity.

    Downsamples along time axis to max_time_points (default 2000) using
    peak-preserving windowing so spectral features are not lost.
    """
    service = get_service()
    if not service.get_patient_meta(patient_id):
        raise HTTPException(404, f"Patient '{patient_id}' not found. Process data first.")
    _ASYM_TYPES = {"asymmetry", "asymmetry_hemi", "asymmetry_ant", "asymmetry_post", "asymmetry_temp", "asymmetry_parasag"}
    valid_types = ("fft_left", "fft_right", "asymmetry", "asymmetry_hemi", "asymmetry_ant",
                   "asymmetry_post", "asymmetry_temp", "asymmetry_parasag", "rhythmicity", "coherence")
    if spec_type not in valid_types:
        raise HTTPException(400, f"spec_type must be one of {valid_types}")

    frequencies, hours, matrix = service.get_spectrogram_data_selective(patient_id, spec_type)

    # Server-side time-axis downsampling — 129k×40 = 47MB JSON without this
    n_time = len(hours)
    if n_time > max_time_points and matrix:
        step = n_time / max_time_points
        ds_hours = []
        ds_matrix = [[] for _ in range(len(matrix))]  # matrix[freq][time]
        for j in range(max_time_points):
            start = int(j * step)
            end = min(int((j + 1) * step), n_time)
            mid = (start + end) // 2
            ds_hours.append(hours[mid])
            for fi in range(len(matrix)):
                window = [matrix[fi][t] for t in range(start, end) if matrix[fi][t] is not None]
                ds_matrix[fi].append(max(window) if window else None)
        hours = ds_hours
        matrix = ds_matrix

    colorscale = "RdBu" if spec_type in _ASYM_TYPES else "viridis" if spec_type == "coherence" else "hot"
    return SpectrogramResponse(
        frequencies=frequencies, hours=hours, matrix=matrix, colorscale=colorscale,
    )


@router.get("/patients/{patient_id}/bins", response_model=BinSummaryResponse)
def get_bins(patient_id: str):
    """Get time-binned summary statistics with readable column names."""
    service = get_service()
    meta = service.get_patient_meta(patient_id)
    if not meta:
        raise HTTPException(404, f"Patient '{patient_id}' not found. Process data first.")

    # Build I-code → common_name mapping for readable metric keys
    code_to_name: dict[str, str] = {}
    for e in meta.schema:
        if e.common_name:
            code_to_name[e.code] = e.common_name

    # bin_summary is always small — load it directly without loading epochs
    bins_df = service.get_bin_summary(patient_id)
    if bins_df is None:
        raise HTTPException(404, f"Bin summary not available for '{patient_id}'. Process data first.")
    bin_rows = []
    for _, row in bins_df.iterrows():
        metrics: dict[str, float | None] = {}
        for col in bins_df.columns:
            for suffix in ("_median", "_mean", "_sd", "_iqr", "_min", "_max", "_n",
                           "_log_mean", "_log_sd"):
                if col.endswith(suffix):
                    base = col[: -len(suffix)]
                    readable = code_to_name.get(base, base)
                    key = f"{readable}{suffix}"
                    val = row[col]
                    metrics[key] = _safe_float(val)
                    break
        bin_rows.append(BinRow(
            bin_label=row["bin_label"],
            bin_start_hours=float(row["bin_start_hours"]),
            bin_end_hours=float(row["bin_end_hours"]),
            coverage_hours=float(row.get("coverage_hours", 0)),
            coverage_fraction=float(row.get("coverage_fraction", 0)),
            n_observed=int(row.get("n_observed", 0)),
            n_effective_fft=int(row.get("n_effective_fft", 0)),
            meets_minimum=bool(row.get("meets_minimum", False)),
            background_continuity_index=_safe_float(row.get("background_continuity_index")),
            seizure_burden_hours=_safe_float(row.get("seizure_burden_hours")),
            missingness_flag=str(row.get("missingness_flag", "")),
            metrics=metrics,
        ))

    edges = sorted({r.bin_start_hours for r in bin_rows} | {r.bin_end_hours for r in bin_rows})
    return BinSummaryResponse(bins=bin_rows, bin_edges=edges)


@router.get("/patients/{patient_id}/overlay", response_model=OverlayDataResponse)
def get_overlay(patient_id: str):
    """Get artifact regions, bin boundaries, and gap regions for chart overlays."""
    service = get_service()
    if not service.get_patient_meta(patient_id):
        raise HTTPException(404, f"Patient '{patient_id}' not found. Process data first.")
    data = service.get_overlay_data_selective(patient_id)
    return OverlayDataResponse(
        artifact_regions=[ArtifactRegion(**r) for r in data["artifact_regions"]],
        bin_boundaries=data["bin_boundaries"],
        gap_regions=[ArtifactRegion(**r) for r in data["gap_regions"]],
    )


@router.get("/compare", response_model=ComparisonResponse)
async def compare_patients(
    ids: str = Query(..., description="Comma-separated patient IDs"),
):
    """Compare key metrics across multiple patients."""
    service = get_service()
    patient_ids = [pid.strip() for pid in ids.split(",") if pid.strip()]
    metrics = []

    for pid in patient_ids:
        result = service.get_result(pid)
        if not result:
            continue

        # I-code → common_name map
        code_to_name: dict[str, str] = {}
        for e in result.schema:
            if e.common_name:
                code_to_name[e.code] = e.common_name

        # Patient-level metrics (readable names)
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Artifact (%)", value=result.qc.artifact_pct))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Usable (h)", value=result.qc.usable_hours))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Duration (h)", value=result.qc.recording_duration_hours))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Seizure Burden (%)", value=result.seizure_report.seizure_burden_pct))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Seizure Events", value=float(result.seizure_report.seizure_events)))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Status screen (algorithmic)", value=1.0 if result.seizure_report.has_status_epilepticus else 0.0))
        metrics.append(ComparisonMetric(patient_id=pid, metric_name="Max Hourly Sz Burden (%)", value=result.seizure_report.max_hourly_burden_pct))

        # Per-bin metrics with readable names
        for _, row in result.bin_summary.iterrows():
            label = row["bin_label"]
            for col in result.bin_summary.columns:
                if col.endswith("_median"):
                    val = row[col]
                    if val == val:  # not NaN
                        base = col[: -len("_median")]
                        readable = code_to_name.get(base, base)
                        metrics.append(ComparisonMetric(
                            patient_id=pid, metric_name=f"{readable} (median)", value=float(val), bin_label=label,
                        ))

    return ComparisonResponse(patient_ids=patient_ids, metrics=metrics)
