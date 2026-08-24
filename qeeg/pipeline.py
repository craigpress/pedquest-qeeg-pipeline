"""Pipeline orchestrator: wires all modules together for per-patient processing."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from qeeg.config import PipelineConfig
from qeeg.constants import DISCARDED_FAMILIES
from qeeg.ingestion.parser import ParsedExport, parse_persyst_csv
from qeeg.ingestion.column_mapper import (
    ColumnEntry,
    build_column_schema,
    build_column_schema_with_mmx,
    get_columns_by_family,
    get_fft_power_columns,
)
from qeeg.ingestion.subcol_validator import validate_subcol_counts
from qeeg.ingestion.timestamps import excel_serial_to_timestamp
from qeeg.validation.data_checks import validate_export, ValidationReport
from qeeg.validation.alignment_check import check_rosc_alignment, parse_rosc_time
from qeeg.alignment.time_axis import build_time_axis, TimeAxisInfo
from qeeg.quality.artifact_filter import apply_artifact_filter, FilterResult
from qeeg.quality.ar_rejection import apply_ar_rejection, ARRejectionResult
from qeeg.quality.qc_report import build_qc_report, QCReport
from qeeg.features.region_mapping import compute_regional_features
from qeeg.features.derived_features import (
    compute_all_derived,
    get_independent_mask,
)
from qeeg.ingestion.cadence import FAMILY_ENGINE_MAP, get_family_cadence
from qeeg.analysis.time_binning import aggregate_by_bins
from qeeg.analysis.time_binning import infer_epoch_durations_hours
from qeeg.analysis.seizure import (
    compute_seizure_mask,
    compute_seizure_report,
    detect_seizure_columns,
    SeizureReport,
)
log = logging.getLogger(__name__)


@dataclass
class PatientResult:
    """Result of processing a single patient."""

    patient_id: str
    parsed: ParsedExport
    schema: list[ColumnEntry]
    validation: ValidationReport
    time_info: TimeAxisInfo
    artifact_result: FilterResult
    seizure_report: SeizureReport
    qc: QCReport
    epochs: pd.DataFrame  # full epoch data with derived features + flags
    bin_summary: pd.DataFrame  # aggregated by time bins
    warnings: list[str] = field(default_factory=list)
    alignment: Any = None  # AlignmentResult | None — ROSC alignment info (for provenance)
    ar_rejection: ARRejectionResult | None = None  # AR-suppressed-zero handling
    stage_row_counts: dict[str, int] = field(default_factory=dict)


def process_patient(
    csv_path: str | Path,
    config: PipelineConfig | None = None,
    patient_id: str | None = None,
    rosc_time_str: str | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
    parsed: ParsedExport | None = None,
    mmx_engines: dict | None = None,
    mmx: Optional[Any] = None,  # MMXConfig — avoids circular import at module level
    pre_built_schema: list[ColumnEntry] | None = None,
) -> PatientResult:
    """Run the full pipeline for a single patient CSV.

    Args:
        csv_path: path to Persyst CSV export
        config: pipeline configuration (uses defaults if None)
        patient_id: override patient ID (otherwise extracted from filename)
        rosc_time_str: ROSC time string (optional)
        progress_cb: callback(stage_name, fraction_complete)
        parsed: pre-parsed export (skips parsing if provided; for multi-file concat)
        mmx_engines: engine configs from MMX file (optional; uses defaults if None)
        mmx: full MMXConfig for MMX-first column resolution (optional)
        pre_built_schema: optional pre-built column schema. Required when the
            parsed DataFrame has semantic-slug column names instead of raw
            ``I{group}_{sub}`` codes (e.g. after multi-segment semantic merge).
            Takes precedence over ``mmx`` when both are supplied.
    """
    cfg = config or PipelineConfig()
    csv_path = Path(csv_path)

    if patient_id is None:
        patient_id = csv_path.stem

    def _progress(stage: str, frac: float) -> None:
        if progress_cb:
            progress_cb(stage, frac)

    # ── 1. PARSE (skip if pre-parsed) ─────────────────────────────────
    _progress("Parsing CSV", 0.0)
    if parsed is None:
        parsed = parse_persyst_csv(csv_path)
    if pre_built_schema is not None:
        schema = pre_built_schema
    elif mmx is not None:
        schema = build_column_schema_with_mmx(parsed.code_to_description, mmx)
    else:
        schema = build_column_schema(parsed.code_to_description)

    # Sub-column-count check against the contract in
    # PersystTrendCSV_Format_Reference.md §3.0. A family exporting a different
    # number of sub-columns than expected means the export's layout has moved,
    # which silently shifts what every sub-column after it means. Warn rather
    # than fail: verified clean (0 mismatches) on all four real V8 exports
    # including the 4,103-column full-panel one, so a mismatch here is news.
    for mismatch in validate_subcol_counts(parsed.code_to_description):
        log.warning("sub-column count mismatch: %s", mismatch)

    df = parsed.data

    # Drop deliberately-discarded families before anything reads the frame, so
    # no downstream stage can treat them as measurements (constants.py).
    _discarded = [e.code for e in schema
                  if e.family in DISCARDED_FAMILIES and e.code in df.columns]
    if _discarded:
        df = df.drop(columns=_discarded)
        schema = [e for e in schema if e.family not in DISCARDED_FAMILIES]
        log.info("discarded %d column(s) from families %s",
                 len(_discarded), sorted(DISCARDED_FAMILIES))

    # Rename I-code columns to their common_name slugs.
    #
    # The multi-segment path has always done this (segment_merge._rename_segment),
    # the single-file path did not -- so the same recording analysed two ways
    # produced two different column vocabularies, and only the merged one matched
    # the published crosswalk. It also made the Persyst-native-vs-derived
    # precedence in compute_all_derived path-dependent: that guard tests
    # `name in df.columns`, which could only ever be true once columns were named.
    #
    # Skipped when a pre-built schema was supplied, since that is the merge path
    # and its columns are already slugs.
    if pre_built_schema is None and schema:
        from dataclasses import replace as _replace
        from qeeg.ingestion.segment_merge import _rename_segment

        df, _slug_trends, slug_to_entry = _rename_segment(df, schema)
        # Downstream keys off entry.code, so it becomes the slug -- the same
        # contract the merge path establishes. source_code keeps the I-code for
        # provenance.
        schema = [_replace(e, code=slug, source_code=e.code)
                  for slug, e in slug_to_entry.items()]
        parsed = _replace(parsed, data=df,
                          code_to_description=dict(_slug_trends)) \
            if hasattr(parsed, "__dataclass_fields__") else parsed
    _progress("Parsing CSV", 1.0)

    # ── 2. TIMESTAMPS ─────────────────────────────────────────────────
    _progress("Processing timestamps", 0.0)
    if "ClockDateTime" in df.columns:
        # Parser already converts to Timestamps; if still numeric, convert now
        if pd.api.types.is_numeric_dtype(df["ClockDateTime"]):
            timestamps = excel_serial_to_timestamp(df["ClockDateTime"])
        else:
            timestamps = pd.to_datetime(df["ClockDateTime"], errors="coerce")
    else:
        timestamps = pd.Series(pd.NaT, index=df.index)
    _progress("Processing timestamps", 1.0)

    # ── 3. VALIDATE ───────────────────────────────────────────────────
    _progress("Validating data", 0.0)
    fft_cols = [e.code for e in schema if e.family == "fft_power"]
    col_families: dict[str, list[str]] = {}
    for entry in schema:
        col_families.setdefault(entry.family, []).append(entry.code)

    validation = validate_export(df, timestamps, fft_cols, col_families, parsed.metadata)

    # Remove leading zero rows
    if validation.leading_zero_rows > 0:
        df = df.iloc[validation.leading_zero_rows:].reset_index(drop=True)
        timestamps = timestamps.iloc[validation.leading_zero_rows:].reset_index(drop=True)
    _progress("Validating data", 1.0)

    # ── 4. ALIGNMENT ──────────────────────────────────────────────────
    _progress("Aligning to ROSC", 0.0)
    rosc_ts = parse_rosc_time(rosc_time_str or cfg.rosc_time)
    eeg_start = timestamps.iloc[0] if len(timestamps) > 0 and pd.notna(timestamps.iloc[0]) else None

    alignment = check_rosc_alignment(rosc_ts, eeg_start)
    effective_rosc = rosc_ts if alignment.is_aligned else None
    hours_relative, time_info = build_time_axis(timestamps, effective_rosc)
    _progress("Aligning to ROSC", 1.0)

    warnings: list[str] = list(validation.warnings)
    if alignment.warning:
        warnings.append(alignment.warning)

    # Trim epochs before ROSC when EEG started early
    if alignment.has_pre_rosc_data:
        pre_rosc_mask = hours_relative >= 0
        n_trimmed = (~pre_rosc_mask).sum()
        df = df[pre_rosc_mask].reset_index(drop=True)
        timestamps = timestamps[pre_rosc_mask].reset_index(drop=True)
        hours_relative = hours_relative[pre_rosc_mask].reset_index(drop=True)
        warnings.append(f"Trimmed {n_trimmed} epochs recorded before ROSC")

    # ── 4b. AR-SUPPRESSED ZEROS → NaN ─────────────────────────────────
    # Must run before the artifact filter and before any aggregation: those
    # filters read the same columns, and a suppressed 0 read as a measurement
    # makes an artifacted epoch look artifact-free.
    ar_result = None
    if cfg.artifact.ar_rejection:
        _progress("Marking AR-suppressed values", 0.0)
        df, ar_result = apply_ar_rejection(df, schema)
        for w in ar_result.warnings:
            warnings.append(w)
        if ar_result.segment_empty:
            warnings.append(
                "Segment has no analysable reference measure — exclude from analysis"
            )
        elif ar_result.cells_nulled:
            warnings.append(
                f"AR rejection: {ar_result.rows_all_rejected} epochs fully rejected, "
                f"{ar_result.rows_partial} partially; {ar_result.cells_nulled} values "
                f"set to NaN across {ar_result.columns_touched} columns"
            )
        _progress("Marking AR-suppressed values", 1.0)

    # ── 5. ARTIFACT FILTER ────────────────────────────────────────────
    _progress("Filtering artifacts", 0.0)
    artifact_cols = {
        "intensity": [e.code for e in schema if e.family == "artifact_intensity"],
        "quality": [e.code for e in schema if e.family == "electrode_quality"],
    }
    artifact_result = apply_artifact_filter(
        df,
        artifact_cols,
        mode=cfg.artifact.mode,
        intensity_threshold=cfg.artifact.intensity_threshold,
        quality_threshold=cfg.artifact.quality_threshold,
        min_clean_electrodes=cfg.artifact.min_clean_electrodes,
    )

    # An epoch where AR rejected every region had nothing analysable in it, so it
    # is excluded regardless of the artifact mode — including mode="none", which
    # means "apply no threshold", not "keep epochs that carry no data".
    if (ar_result is not None and cfg.artifact.exclude_all_region_rejected
            and ar_result.all_regions_mask is not None):
        blank = ar_result.all_regions_mask.reindex(artifact_result.mask.index, fill_value=False)
        n_extra = int((artifact_result.mask & blank).sum())
        if n_extra:
            artifact_result.mask &= ~blank
            artifact_result.excluded_epochs = int((~artifact_result.mask).sum())
            artifact_result.artifact_pct = (
                100.0 * artifact_result.excluded_epochs / artifact_result.total_epochs
                if artifact_result.total_epochs else 0.0
            )
            artifact_result.method = f"{artifact_result.method}+ar_rejection"
            warnings.append(
                f"Excluded {n_extra} additional epochs where AR rejected every region"
            )
    _progress("Filtering artifacts", 1.0)

    # ── 6. SEIZURE DETECTION ──────────────────────────────────────────
    _progress("Detecting seizures", 0.0)
    seizure_cols = detect_seizure_columns(list(df.columns), parsed.code_to_description)
    seizure_mask = compute_seizure_mask(
        df, seizure_cols, mode=cfg.seizure.exclusion_mode,
        probability_threshold=cfg.seizure.probability_threshold,
    )
    # ── 7. USABLE MASK ────────────────────────────────────────────────
    # Artifact-clean mask (for seizure burden denominator — must NOT exclude seizures)
    artifact_clean = artifact_result.mask.copy()

    # Seizure burden uses artifact-only denominator: "of interpretable time, how much is seizure?"
    seizure_report = compute_seizure_report(
        df, seizure_cols, seizure_mask,
        usable_mask=artifact_clean,
        hours_relative=hours_relative,
    )

    # Analysis mask excludes both artifact AND seizure epochs (for feature aggregation)
    usable = artifact_clean.copy()
    if cfg.seizure.exclusion_mode != "none":
        usable = usable & ~seizure_mask
    _progress("Detecting seizures", 1.0)

    # ── 8. REGION MAPPING & DERIVED FEATURES ──────────────────────────
    _progress("Computing features", 0.0)
    fft_power_map = get_fft_power_columns(schema)
    regional = compute_regional_features(
        df, fft_power_map,
        require_bilateral=cfg.features.require_bilateral_hemispheres,
    )

    derived_frames = [regional]
    # Need regional cols in df for compute_all_derived
    df = pd.concat([df, regional], axis=1)
    for region in ["anterior", "posterior"]:
        derived = compute_all_derived(df, region)
        derived_frames.append(derived)

    # Independent observation mask for FFT features (legacy single-engine path).
    fft_all_cols = [e.code for e in schema if e.family in ("fft_power", "fft_power_ratio", "alpha_variability")]
    independent_mask = get_independent_mask(df, fft_all_cols, engines=mmx_engines)
    epoch_durations_hours = infer_epoch_durations_hours(hours_relative)

    # Per-engine independence markers — persisted to epoch parquet so the
    # audit-recompute script can verify cadence-adjusted N for non-FFT
    # engines (Amplitude01 / RhythmicityEngine01) the same way it does for
    # FFTEngine01. One marker per engine whose cadence > 1 row.
    engine_to_families: dict[str, list[str]] = {}
    for fam, eng in FAMILY_ENGINE_MAP.items():
        engine_to_families.setdefault(eng, []).append(fam)
    engine_independent_masks: dict[str, pd.Series] = {}
    for engine_name, families in engine_to_families.items():
        rep_family = families[0]
        cadence = get_family_cadence(rep_family, mmx_engines)
        if cadence <= 1:
            continue
        engine_cols = [
            e.code for e in schema
            if e.family in families and e.code in df.columns
        ]
        if not engine_cols:
            continue
        engine_independent_masks[engine_name] = get_independent_mask(
            df, engine_cols, interval=cadence,
        )

    # Batch-assign all pipeline columns at once to avoid fragmentation
    pipeline_cols = pd.DataFrame({
        "_timestamp": timestamps,
        "_hours_relative": hours_relative,
        "_artifact_clean": artifact_result.mask,
        "_seizure_flag": seizure_mask,
        "_usable": usable,
        "_is_independent_fft": independent_mask,
    }, index=df.index)
    for engine_name, mask in engine_independent_masks.items():
        pipeline_cols[f"_is_independent_{engine_name.lower()}"] = mask
    for df_extra in derived_frames:
        pipeline_cols = pd.concat([pipeline_cols, df_extra], axis=1)
    df = pd.concat([df, pipeline_cols.drop(columns=regional.columns, errors="ignore")], axis=1)

    # ── 8b. aEEG BACKGROUND CLASSIFICATION ───────────────────────────
    # DISABLED: Hellstrom-Westas classification is neonatal-only (validated for 0-7 days post-birth).
    # Not valid for PedQuEST/POCCA pediatric populations.
    # Code preserved in git history for future exploration if age-stratified thresholds are developed.
    _progress("Computing features", 1.0)

    # ── 9. TIME BINNING ───────────────────────────────────────────────
    _progress("Binning by time", 0.0)
    analysis_vars = _select_analysis_variables(df, schema)
    # Identify FFT-cadence columns for legacy compatibility and build
    # per-variable MMX-engine cadence masks for publication reporting.
    fft_families = {"fft_power", "fft_power_ratio", "alpha_variability", "rda", "asymmetry"}
    fft_cols_for_mask = [
        e.code for e in schema
        if e.family in fft_families and e.code in df.columns
    ]
    # Also include derived FFT columns
    fft_derived_prefixes = (
        "fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
        "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
        "theta_delta_ratio_", "alpha_delta_ratio_",
        "log_theta_delta_ratio_", "log_alpha_delta_ratio_",
    )
    for col in df.columns:
        if any(col.startswith(p) for p in fft_derived_prefixes):
            fft_cols_for_mask.append(col)

    family_by_col = {e.code: e.family for e in schema if e.code in df.columns}
    for col in df.columns:
        if any(col.startswith(p) for p in fft_derived_prefixes):
            family_by_col[col] = "fft_power"

    independent_masks: dict[str, pd.Series] = {}
    effective_basis: dict[str, str] = {}
    for col in analysis_vars:
        family = family_by_col.get(col)
        cadence = get_family_cadence(family, mmx_engines) if family else 1
        if cadence > 1:
            independent_masks[col] = get_independent_mask(df, [col], interval=cadence)
            effective_basis[col] = f"{family}_cadence_adjusted"
        else:
            effective_basis[col] = "row_count"

    # Identify suppression columns for background continuity index
    suppression_cols = [
        e.code for e in schema
        if e.family == "suppression_ratio" and e.code in df.columns
    ]

    bin_summary = aggregate_by_bins(
        df,
        hours_relative,
        variables=analysis_vars,
        edges=cfg.binning.bin_edges_hours,
        usable_mask=usable,
        independent_mask=independent_mask,
        fft_columns=fft_cols_for_mask,
        independent_masks=independent_masks,
        effective_basis=effective_basis,
        min_coverage_hours=cfg.binning.min_coverage_hours,
        suppression_columns=suppression_cols if suppression_cols else None,
        # ACNS 2021 continuity boundary (default 10%): <10% suppression =
        # continuous/nearly-continuous, >=10% = discontinuous. Config-driven. (P0-1)
        suppression_threshold=cfg.binning.suppression_continuity_threshold_pct,
        seizure_mask=seizure_mask,
        artifact_clean_mask=artifact_clean,  # P0-3: burden denominator (pre-seizure-exclusion)
        epoch_durations_hours=epoch_durations_hours,
    )
    _progress("Binning by time", 1.0)

    # ── 10. QC REPORT ─────────────────────────────────────────────────
    qc = build_qc_report(
        patient_id=patient_id,
        total_epochs=len(parsed.data),
        artifact_result=artifact_result,
        seizure_mask=seizure_mask,
        timestamps=timestamps,
        leading_zeros=validation.leading_zero_rows,
        gap_count=len(validation.timestamp_gaps),
        ar_rejection=ar_result,
        epochs=df,
    )
    qc.warnings.extend(warnings)

    # Median suppression ratio across usable epochs, averaged across hemispheres.
    # artifact_result.mask is True = keep (usable). P0-1: V8 Suppression Ratio is
    # already a 0–100 percent (PERSYST_V10_REFERENCE §3a / CSV ref §3.18; verified
    # against the real subject-1 V8 export, column max 30.97 > 1 rules out a 0–1
    # fraction). Report the median as-is; the prior ×100 overstated it 100×.
    if suppression_cols:
        sr_cols = [c for c in suppression_cols if c in df.columns]
        if sr_cols:
            sr_vals = df.loc[artifact_result.mask, sr_cols]
            if not sr_vals.empty:
                median_val = float(sr_vals.median(axis=0).mean())
                qc.median_suppression_pct = round(median_val, 1)
                if not (0.0 <= qc.median_suppression_pct <= 100.0):
                    qc.warnings.append(
                        f"median_suppression_pct={qc.median_suppression_pct} outside "
                        "expected 0-100 percent range — possible BSR scale/units error"
                    )

    # Bin coverage
    for _, brow in bin_summary.iterrows():
        qc.bin_coverage[brow["bin_label"]] = brow.get("coverage_hours", 0.0)

    # Publication-audit stage row counts. parsed_rows is pre-any-trim; each
    # subsequent count reflects rows surviving that stage.
    parsed_total = int(len(parsed.data))
    n_leading_zero = int(getattr(validation, "leading_zero_rows", 0) or 0)
    post_leading_zero = parsed_total - n_leading_zero
    n_pre_rosc_trimmed = max(0, post_leading_zero - int(len(df)))
    stage_row_counts = {
        "parsed": parsed_total,
        "leading_zero_removed": n_leading_zero,
        "post_leading_zero": post_leading_zero,
        "pre_rosc_trimmed": n_pre_rosc_trimmed,
        "post_rosc_trim": int(len(df)),
        "artifact_clean": int(artifact_result.mask.sum()) if hasattr(artifact_result.mask, "sum") else 0,
        "seizure_flagged": int(seizure_mask.sum()) if hasattr(seizure_mask, "sum") else 0,
        "usable": int(usable.sum()) if hasattr(usable, "sum") else 0,
        "binned_rows": int(len(bin_summary)),
    }

    return PatientResult(
        patient_id=patient_id,
        parsed=parsed,
        schema=schema,
        validation=validation,
        time_info=time_info,
        artifact_result=artifact_result,
        ar_rejection=ar_result,
        seizure_report=seizure_report,
        qc=qc,
        epochs=df,
        bin_summary=bin_summary,
        warnings=warnings,
        alignment=alignment,
        stage_row_counts=stage_row_counts,
    )


def _select_analysis_variables(df: pd.DataFrame, schema: list[ColumnEntry]) -> list[str]:
    """Select columns to include in bin aggregation.

    Includes all clinically relevant families and derived features.
    """
    # Craig, 2026-07-28: rda and sleep belong in the binned analysis.
    # Both were absent while `rda` was already listed in fft_families below for
    # cadence masking -- the code built an independence mask for a family it
    # then never aggregated -- and while periodic_discharge, the same kind of
    # boolean indicator, was included. Post-arrest, rhythmic delta and
    # sleep-wake state are prognostically meaningful.
    keep_families = {
        "fft_power", "fft_power_ratio", "aeeg",
        "adr",                     # native alpha/delta & theta/delta ratios (P0-4: primary post-arrest prognostic marker)
        "relative_power",          # native band / 1-30 Hz relative power (V8+)
        "seizure_probability", "peak_envelope",
        "status_epilepticus",      # V8-native status-epilepticus metric (P0-4)
        "seizure_burden",          # V8-native seizure-burden metric (P0-4)
        "suppression_ratio",       # burst-suppression index
        "asymmetry",               # EASI/REASI indices
        "spectral_edge",           # SEF50, SEF90
        "spike_density",           # spike detection rates
        "alpha_variability",       # RAV
        "rhythmic_delta",      # boolean PD flags (LAD, LPD, etc.)
        "rda",                     # rhythmic delta: left / right / generalized
        "sleep",                   # sleep stage + sleep-wake state
    }
    selected = []
    for entry in schema:
        if entry.family in keep_families and entry.code in df.columns:
            selected.append(entry.code)

    # Also include derived columns (regional aggregates, ratios, log-ratios)
    derived_prefixes = (
        "fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
        "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
        "theta_delta_ratio_", "alpha_delta_ratio_",
        "log_theta_delta_ratio_", "log_alpha_delta_ratio_",
    )
    for col in df.columns:
        if any(col.startswith(p) for p in derived_prefixes):
            selected.append(col)

    return selected


def concatenate_and_process(
    file_paths: list[str | Path],
    config: PipelineConfig | None = None,
    patient_id: str | None = None,
    rosc_time_str: str | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
    mmx_engines: dict | None = None,
    mmx: Optional[Any] = None,
) -> PatientResult:
    """Parse multiple files for the same patient and merge semantically.

    Multi-segment Persyst exports often come from different MMX panel
    configurations of the same underlying recording. The raw ``I{group}_{sub}``
    codes are NOT portable between such segments — ``I288_1`` may mean
    different instruments in each. We therefore resolve every I-code to a
    ``common_name`` slug (via ``column_mapper.generate_common_name``) and
    merge by that slug.

    Disjoint time ranges stitch naturally by concatenation; overlapping ranges
    collapse per semantic column with highest non-NaN density winning
    (first-seen segment breaks ties). The merged DataFrame exposes semantic
    slugs only — raw I-group codes are no longer passed downstream.
    """
    if not file_paths:
        raise ValueError("No files provided")

    if len(file_paths) == 1:
        return process_patient(
            file_paths[0], config=config, patient_id=patient_id,
            rosc_time_str=rosc_time_str, progress_cb=progress_cb,
            mmx_engines=mmx_engines, mmx=mmx,
        )

    all_parsed = [parse_persyst_csv(Path(p)) for p in file_paths]

    from qeeg.ingestion.segment_merge import merge_segments_by_semantic_name
    merged_parsed, merged_schema = merge_segments_by_semantic_name(all_parsed, mmx=mmx)

    if "ClockDateTime" in merged_parsed.data.columns:
        merged_parsed.data = (
            merged_parsed.data.sort_values("ClockDateTime").reset_index(drop=True)
        )

    pid = patient_id or Path(file_paths[0]).stem
    return process_patient(
        file_paths[0], config=config, patient_id=pid,
        rosc_time_str=rosc_time_str, progress_cb=progress_cb,
        parsed=merged_parsed,
        mmx_engines=mmx_engines, mmx=mmx,
        pre_built_schema=merged_schema,
    )
