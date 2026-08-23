"""Export endpoints — CSV, Excel, JSON, Parquet, Wide, Long, Semi-long, Codebook, Package, Cohort."""
from __future__ import annotations

import io
import hashlib
import json
import logging
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["export"])
logger = logging.getLogger(__name__)


def get_service():
    from api.main import pipeline_service
    return pipeline_service


def _safe_filename(patient_id: str, suffix: str) -> str:
    safe = re.sub(r'[^\w\-.]', '_', patient_id)
    return f"{safe}_{suffix}"


def _export_to_bytes(write_fn) -> bytes:
    """Run an export writer that requires a real output_path and return the bytes.

    Writes to a private system temp dir (random name, fixed inner filename) instead
    of a repo-root `.exports/` scratch path built from the raw patient_id. This
    removes both the path-traversal surface and the risk of PHI-derived files
    landing in the working tree. Mirrors the cohort-export tempfile pattern.
    """
    d = Path(tempfile.mkdtemp(prefix="qeeg_export_"))
    try:
        out = d / "export.csv"
        write_fn(out)
        return out.read_bytes()
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _build_column_map(schema) -> dict[str, str]:
    """Map raw I-codes to common_name labels from schema."""
    return {e.code: e.common_name or e.code for e in schema if e.common_name}


def _rename_bin_columns(df: pd.DataFrame, col_map: dict[str, str]) -> pd.DataFrame:
    """Rename bin_summary columns from I-codes to common_names."""
    rename = {}
    for col in df.columns:
        for suffix in ("_median", "_mean", "_sd", "_iqr", "_min", "_max", "_n"):
            if col.endswith(suffix):
                base = col[: -len(suffix)]
                if base in col_map:
                    rename[col] = f"{col_map[base]}{suffix}"
                break
    if rename:
        df = df.rename(columns=rename)
    return df


def _patient_cache_meta(service, patient_id: str) -> dict:
    meta = service.get_patient_meta(patient_id)
    if meta is None:
        return {}
    meta_path = meta.cache_dir / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024 * 8), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_hashes(source_files: list[str], fast: bool = False) -> dict[str, str]:
    """SHA-256 of every source CSV. When *fast* is True, fall back to the
    stat+head+tail content-hash fingerprint used for cache keying (~100× faster
    on network shares but not bit-identity proof)."""
    hashes: dict[str, str] = {}
    if fast:
        from qeeg.storage.result_cache import content_hash_file
    for src in source_files:
        if not src:
            continue
        p = Path(src)
        if not p.exists() or not p.is_file():
            continue
        try:
            hashes[src] = content_hash_file(p) if fast else _sha256_file(p)
        except OSError:
            continue
    return hashes


def _maybe_hash_file(path: Path | str | None, fast: bool = False) -> str | None:
    """Hash one optional file; return None if missing/unreadable."""
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    try:
        if fast:
            from qeeg.storage.result_cache import content_hash_file
            return content_hash_file(p)
        return _sha256_file(p)
    except OSError:
        return None


def _audit_paths_for_patient(service, patient_id: str) -> tuple[Path | None, Path | None, Path | None]:
    """Resolve MMX file, clinical-metadata JSON, and corrections JSON paths
    for this patient. Any of these may be None if not configured."""
    mmx_path = None
    study_name = service._patient_studies.get(patient_id)
    if study_name:
        study_cfg = service._studies.get(study_name)
        if study_cfg and study_cfg.mmx_study:
            mmx_cfg = service.get_mmx_config(study_cfg.mmx_study)
            if mmx_cfg:
                sp = mmx_cfg.get("source_path")
                if sp:
                    mmx_path = Path(sp)
    clinical_path = getattr(service, "_clinical_path", None)
    corrections_path = getattr(service, "_corrections_path", None)
    return mmx_path, clinical_path, corrections_path


def _clinical_metadata_for_patient(service, patient_id: str) -> dict | None:
    """Return the clinical-metadata row for this patient as a plain dict
    (not the dataclass). Returns None if no row is stored."""
    from dataclasses import asdict
    meta = service._clinical_metadata.get(patient_id)
    if meta is None:
        return None
    try:
        return asdict(meta)
    except TypeError:
        return dict(meta) if isinstance(meta, dict) else None


def _corrections_for_source_files(service, source_files: list[str]) -> dict | None:
    """Return {dat_stem: correction_row} for every segment in source_files.
    Returns None if no matching corrections exist."""
    if not source_files:
        return None
    paths = [Path(s) for s in source_files if s]
    try:
        relevant = service._relevant_corrections_for_paths(paths)
    except Exception:
        relevant = {}
    return relevant or None


class SinglePatientPackageRequest(BaseModel):
    include_groups: list[str] | None = None


@router.post("/export/{patient_id}/package")
async def export_research_package(
    patient_id: str,
    request: SinglePatientPackageRequest = SinglePatientPackageRequest(),
    fast_provenance: bool = False,
):
    """Download a ZIP research export package for a single patient.

    *fast_provenance* (query param): when true, use the stat+head+tail
    fingerprint for raw CSV hashes instead of full SHA-256. MMX, clinical
    metadata, corrections, and the in-zip manifest always use full SHA-256."""
    import logging
    logger = logging.getLogger(__name__)

    from qeeg.storage.export import build_research_package, build_alignment_info

    service = get_service()
    result = service.get_result(patient_id)
    if not result:
        raise HTTPException(404, f"Patient '{patient_id}' not found")

    col_map = _build_column_map(result.schema)
    alignment_info = build_alignment_info(
        getattr(result, "time_info", None),
        getattr(result, "alignment", None),
    )

    artifact_counts = {
        "total_epochs": result.qc.total_epochs,
        "artifact_rejected": result.qc.total_epochs - result.qc.usable_epochs,
        "seizure_epochs": result.qc.seizure_epochs,
        "usable_epochs": result.qc.usable_epochs,
    }

    # Handle both dataclass and dict metadata (dict when loaded from disk cache)
    meta = result.parsed.metadata
    if isinstance(meta, dict):
        persyst_version = meta.get("persyst_version", "")
        source_path = meta.get("source_path", "")
    else:
        persyst_version = getattr(meta, "persyst_version", "")
        source_path = getattr(meta, "source_path", "") or ""

    # Resolve MMX fingerprint and engines summary for this patient
    mmx_fingerprint = ""
    mmx_engines_summary = None
    study_name = service._patient_studies.get(patient_id)
    if study_name:
        study_cfg = service._studies.get(study_name)
        if study_cfg and study_cfg.mmx_study:
            mmx_cfg = service.get_mmx_config(study_cfg.mmx_study)
            if mmx_cfg:
                mmx_fingerprint = mmx_cfg.get("fingerprint", "")
                raw_engines = mmx_cfg.get("engines")
                if raw_engines:
                    mmx_engines_summary = {
                        name: {"epoch_duration": ec.epoch_duration, "epoch_step": ec.epoch_step}
                        for name, ec in raw_engines.items()
                    }

    cache_meta = _patient_cache_meta(service, patient_id)
    config_dict = cache_meta.get("config", {})
    source_files = cache_meta.get("source_files") or ([source_path] if source_path else [])
    stage_row_counts = cache_meta.get("stage_row_counts") or getattr(result, "stage_row_counts", {}) or {}

    mmx_path, clinical_path, corrections_path = _audit_paths_for_patient(service, patient_id)
    hash_strategy = "fingerprint_stat_head_tail" if fast_provenance else "full_sha256"

    try:
        buf = build_research_package(
            patient_id=patient_id,
            epochs=result.epochs,
            bin_summary=result.bin_summary,
            schema=result.schema,
            config=config_dict,
            qc_dict=result.qc.to_dict(),
            seizure_dict=result.seizure_report.to_dict(),
            persyst_version=persyst_version,
            source_files=source_files,
            source_file_hashes=_source_hashes(source_files, fast=fast_provenance),
            artifact_rejection_counts=artifact_counts,
            col_map=col_map,
            mmx_fingerprint=mmx_fingerprint,
            mmx_engines_summary=mmx_engines_summary,
            include_groups=request.include_groups,
            alignment_info=alignment_info,
            mmx_file_hash=_maybe_hash_file(mmx_path, fast=False),
            clinical_metadata_hash=_maybe_hash_file(clinical_path, fast=False),
            corrections_hash=_maybe_hash_file(corrections_path, fast=False),
            stage_row_counts=stage_row_counts,
            hash_strategy=hash_strategy,
            clinical_metadata=_clinical_metadata_for_patient(service, patient_id),
            eeg_corrections=_corrections_for_source_files(service, source_files),
        )
    except Exception as e:
        logger.exception("Research package build failed")
        raise HTTPException(500, f"Package build failed: {e}")

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "research_package.zip")}"'},
    )


@router.get("/export/{patient_id}/{fmt}")
async def export_patient(patient_id: str, fmt: str):
    """Export patient data. fmt: csv, xlsx, json, parquet, wide, long, semilong, codebook."""
    service = get_service()
    result = service.get_result(patient_id)
    if not result:
        raise HTTPException(404, f"Patient '{patient_id}' not found")

    col_map = _build_column_map(result.schema)

    if fmt == "csv":
        df = _rename_bin_columns(result.bin_summary.copy(), col_map)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "bins.csv")}"'},
        )

    elif fmt == "wide":
        # Patient-level wide format: one row per patient, columns per feature x bin
        from qeeg.storage.export import export_patient_wide
        renamed_bins = _rename_bin_columns(result.bin_summary.copy(), col_map)
        content = _export_to_bytes(lambda out: export_patient_wide(
            bin_summaries={patient_id: renamed_bins},
            qc_reports={patient_id: result.qc.to_dict()},
            output_path=out,
        ))
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "wide.csv")}"'},
        )

    elif fmt == "long":
        # Bin-level long format: one row per patient x bin x feature
        from qeeg.storage.export import export_patient_bins_long
        renamed_bins = _rename_bin_columns(result.bin_summary.copy(), col_map)
        content = _export_to_bytes(lambda out: export_patient_bins_long(
            bin_summaries={patient_id: renamed_bins},
            patient_info={patient_id: {}},
            output_path=out,
        ))
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "long.csv")}"'},
        )

    elif fmt == "semilong":
        # Semi-long format: 1 row per patient x bin, features as columns
        from qeeg.storage.export import export_patient_semi_long
        renamed_bins = _rename_bin_columns(result.bin_summary.copy(), col_map)
        content = _export_to_bytes(lambda out: export_patient_semi_long(
            bin_summaries={patient_id: renamed_bins},
            patient_info={patient_id: {}},
            output_path=out,
        ))
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "semilong.csv")}"'},
        )

    elif fmt == "codebook":
        from qeeg.storage.export import build_data_dictionary

        entries = build_data_dictionary(result.schema)
        return StreamingResponse(
            io.BytesIO(json.dumps(entries, indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "codebook.json")}"'},
        )

    elif fmt == "xlsx":
        df = _rename_bin_columns(result.bin_summary.copy(), col_map)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Bin Summary", index=False)
            qc_df = pd.DataFrame([result.qc.to_dict()])
            qc_df.to_excel(writer, sheet_name="QC Report", index=False)
            sz_df = pd.DataFrame([result.seizure_report.to_dict()])
            sz_df.to_excel(writer, sheet_name="Seizure Report", index=False)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "report.xlsx")}"'},
        )

    elif fmt == "json":
        data = {
            "patient_id": patient_id,
            "qc": result.qc.to_dict(),
            "seizure": result.seizure_report.to_dict(),
            "bin_summary": result.bin_summary.replace({np.nan: None}).to_dict(orient="records"),
            "warnings": result.warnings,
        }
        return StreamingResponse(
            io.BytesIO(json.dumps(data, indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "report.json")}"'},
        )

    elif fmt == "parquet":
        from qeeg.storage.parquet_io import parquet_bytes

        buf = io.BytesIO(parquet_bytes(result.epochs, patient_id=patient_id))
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{_safe_filename(patient_id, "epochs.parquet")}"'},
        )

    else:
        raise HTTPException(400, f"Unsupported format: {fmt}. Use csv, xlsx, json, parquet, wide, long, semilong, or codebook.")


class BatchExportRequest(BaseModel):
    patient_ids: list[str]
    mmx_study: str | None = None
    include_groups: list[str] | None = None


@router.post("/export/batch-package")
async def export_batch_research_package(request: BatchExportRequest, fast_provenance: bool = False):
    """Download a single ZIP containing research packages for multiple patients.

    *fast_provenance* (query param): when true, use the fast cache-keying
    fingerprint for per-patient raw CSV hashes. Auxiliary files (MMX, clinical
    metadata, corrections) and the in-zip manifests always use full SHA-256."""
    from qeeg.storage.export import build_research_package, build_alignment_info

    service = get_service()

    results = {}
    missing = []
    for pid in request.patient_ids:
        result = service.get_result(pid)
        if result:
            results[pid] = result
        else:
            missing.append(pid)

    if not results:
        raise HTTPException(404, f"No processed patients found. Missing: {missing}")

    zip_buf = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for pid, result in results.items():
                col_map = _build_column_map(result.schema)
                artifact_counts = {
                    "total_epochs": result.qc.total_epochs,
                    "artifact_rejected": result.qc.total_epochs - result.qc.usable_epochs,
                    "seizure_epochs": result.qc.seizure_epochs,
                    "usable_epochs": result.qc.usable_epochs,
                }
                meta = result.parsed.metadata
                if isinstance(meta, dict):
                    persyst_version = meta.get("persyst_version", "")
                    source_path = meta.get("source_path", "")
                else:
                    persyst_version = getattr(meta, "persyst_version", "")
                    source_path = getattr(meta, "source_path", "") or ""
                cache_meta = _patient_cache_meta(service, pid)
                config_dict = cache_meta.get("config", {})
                source_files = cache_meta.get("source_files") or ([source_path] if source_path else [])
                stage_row_counts = cache_meta.get("stage_row_counts") or getattr(result, "stage_row_counts", {}) or {}

                alignment_info = build_alignment_info(
                    getattr(result, "time_info", None),
                    getattr(result, "alignment", None),
                )
                mmx_path, clinical_path, corrections_path = _audit_paths_for_patient(service, pid)
                hash_strategy = "fingerprint_stat_head_tail" if fast_provenance else "full_sha256"

                patient_zip_buf = build_research_package(
                    patient_id=pid,
                    epochs=result.epochs,
                    bin_summary=result.bin_summary,
                    schema=result.schema,
                    config=config_dict,
                    qc_dict=result.qc.to_dict(),
                    seizure_dict=result.seizure_report.to_dict(),
                    persyst_version=persyst_version,
                    source_files=source_files,
                    source_file_hashes=_source_hashes(source_files, fast=fast_provenance),
                    artifact_rejection_counts=artifact_counts,
                    col_map=col_map,
                    include_groups=request.include_groups,
                    alignment_info=alignment_info,
                    mmx_file_hash=_maybe_hash_file(mmx_path, fast=False),
                    clinical_metadata_hash=_maybe_hash_file(clinical_path, fast=False),
                    corrections_hash=_maybe_hash_file(corrections_path, fast=False),
                    stage_row_counts=stage_row_counts,
                    hash_strategy=hash_strategy,
                    clinical_metadata=_clinical_metadata_for_patient(service, pid),
                    eeg_corrections=_corrections_for_source_files(service, source_files),
                )
                # Nest each patient's ZIP contents under a patient_id/ folder
                with zipfile.ZipFile(patient_zip_buf, "r") as inner_zf:
                    for item in inner_zf.infolist():
                        data = inner_zf.read(item.filename)
                        zf.writestr(f"{pid}/{item.filename}", data)

        zip_buf.seek(0)
    except Exception as e:
        logger.exception("Batch research package export failed")
        raise HTTPException(500, f"Batch package export failed: {e}")

    headers = {"Content-Disposition": 'attachment; filename="batch_research_package.zip"'}
    if missing:
        headers["X-Missing-Patients"] = ",".join(missing)

    return StreamingResponse(zip_buf, media_type="application/zip", headers=headers)


@router.post("/export/batch-semi-long")
async def export_batch_semi_long(request: BatchExportRequest, format: str = "csv"):
    """Single concatenated semi-long file across patients.

    One row per patient × time-bin, ``patient_id`` + ``time_reference`` leading.
    Use ``?format=parquet`` for zstd-compressed Parquet; otherwise returns CSV.
    """
    from qeeg.storage.export import export_cohort_semi_long

    service = get_service()
    results = {}
    missing: list[str] = []
    schema_by_patient: dict[str, list] = {}
    col_map: dict[str, str] = {}
    for pid in request.patient_ids:
        r = service.get_result(pid)
        if r:
            results[pid] = r
            schema_by_patient[pid] = r.schema
            col_map.update(_build_column_map(r.schema))
        else:
            missing.append(pid)

    if not results:
        raise HTTPException(404, f"No processed patients found. Missing: {missing}")

    try:
        df = export_cohort_semi_long(
            results=results,
            col_map=col_map,
            include_groups=request.include_groups,
            schema_by_patient=schema_by_patient,
        )
    except Exception as e:
        logger.exception("Cohort semi-long export failed")
        raise HTTPException(500, f"Cohort semi-long export failed: {e}")

    headers: dict[str, str] = {}
    if missing:
        headers["X-Missing-Patients"] = ",".join(missing)

    if format.lower() == "parquet":
        import pyarrow as pa
        import pyarrow.parquet as pq
        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), buf, compression="zstd")
        buf.seek(0)
        headers["Content-Disposition"] = 'attachment; filename="cohort_semi_long.parquet"'
        return StreamingResponse(buf, media_type="application/vnd.apache.parquet", headers=headers)

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    out = io.BytesIO(csv_buf.getvalue().encode("utf-8"))
    headers["Content-Disposition"] = 'attachment; filename="cohort_semi_long.csv"'
    return StreamingResponse(out, media_type="text/csv", headers=headers)


@router.post("/export/cohort")
async def export_cohort(request: BatchExportRequest):
    """Export a cohort-level partitioned Parquet dataset as a ZIP archive."""
    from qeeg.storage.export import export_cohort_dataset

    service = get_service()

    # Collect results for all requested patients
    results = {}
    missing = []
    for pid in request.patient_ids:
        result = service.get_result(pid)
        if result:
            results[pid] = result
        else:
            missing.append(pid)

    if not results:
        raise HTTPException(404, f"No processed patients found. Missing: {missing}")

    # Resolve MMX identity if applicable
    mmx_identity = None
    if request.mmx_study:
        mmx_cfg = service._mmx_configs.get(request.mmx_study)
        if mmx_cfg:
            mmx_identity = {
                "study_name": request.mmx_study,
                "fingerprint": mmx_cfg.get("fingerprint", ""),
            }

    # Export to a temp directory, then zip it
    tmp_dir = tempfile.mkdtemp(prefix="cohort_export_")
    try:
        dataset_dir = Path(tmp_dir) / "cohort_dataset"
        cohort_config = {
            pid: _patient_cache_meta(service, pid).get("config", {})
            for pid in results
        }
        export_cohort_dataset(
            results=results,
            output_dir=dataset_dir,
            config={"patients": cohort_config},
            mmx_identity=mmx_identity,
        )

        # Create ZIP of the dataset directory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in dataset_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(dataset_dir)
                    zf.write(file_path, arcname)
        zip_buf.seek(0)
    except Exception as e:
        logger.exception("Cohort export failed")
        raise HTTPException(500, f"Cohort export failed: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    warnings_header = ""
    if missing:
        warnings_header = f"X-Missing-Patients: {','.join(missing)}"

    headers = {
        "Content-Disposition": 'attachment; filename="cohort_dataset.zip"',
    }
    if warnings_header:
        headers["X-Missing-Patients"] = ",".join(missing)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers=headers,
    )
