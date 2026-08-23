"""Cache processed PatientResults to disk for instant reload.

Files are identified by a fast content fingerprint (stat + 4KB head + 4KB
tail). This catches cp -p / rsync -a mtime-preserved copies without paying
the cost of streaming SHA-256 over multi-GB network-share CSVs.

Cache structure:
    {cache_dir}/{content_hash}_{patient_id}/
        epochs.parquet
        bin_summary.parquet
        schema.json          # column schema for label mapping
        meta.json            # qc, seizure report, time_info, config, source info
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = 3  # v3: multi-segment merge uses semantic common_name slugs, not raw I-codes
_HEAD_TAIL_BYTES = 4096  # bytes sampled from start + end as a content fingerprint


def _file_fingerprint(path: Path) -> bytes:
    """name|size|mtime + 4KB head + 4KB tail. Cheap on network shares;
    catches the cp -p / rsync -a mtime-preserved collision case where two
    distinct files share name+size+mtime but differ in their actual bytes."""
    st = path.stat()
    head = b""
    tail = b""
    if st.st_size > 0:
        with open(path, "rb") as fh:
            head = fh.read(_HEAD_TAIL_BYTES)
            if st.st_size > _HEAD_TAIL_BYTES:
                fh.seek(max(0, st.st_size - _HEAD_TAIL_BYTES))
                tail = fh.read(_HEAD_TAIL_BYTES)
    return f"{path.name}|{st.st_size}|{st.st_mtime}".encode() + b"|" + head + b"|" + tail


def content_hash_file(path: Path) -> str:
    """Hash a file using stat + small head/tail content sample.

    Full streaming SHA-256 was a 30+ minute operation on 4GB network-share CSVs.
    Stat-only hashing collided across cp -p / rsync -a copies that preserve
    mtime, so we mix in a 4KB head + 4KB tail content sample. The cache is
    also version-pinned by __version__ + CACHE_SCHEMA_VERSION so algorithm
    changes auto-invalidate.
    """
    h = hashlib.sha256()
    h.update(_file_fingerprint(path))
    return h.hexdigest()


def content_hash_files(paths: list[Path]) -> str:
    """Hash multiple files (sorted by name for determinism)."""
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: x.name):
        h.update(_file_fingerprint(p))
    return h.hexdigest()


def full_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Streaming SHA-256 for publication provenance.

    Unlike ``content_hash_file`` (stat+head+tail for cache keying), this reads
    the entire file so the hash uniquely identifies its bytes. Use only for
    audit bundles — on a network share with ~2 MB/s read speed, a 4 GB file
    takes 30+ minutes.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _cache_key(content_hash: str, config_dict: dict,
               clinical_meta: Optional[dict] = None,
               eeg_corrections: Optional[dict] = None,
               mmx_config: Optional[dict] = None) -> str:
    """Combine content hash + config + pipeline version for the full cache key.

    Including the pipeline version means algorithm changes auto-invalidate
    cached results — no stale data served after code updates.

    clinical_meta, eeg_corrections, and mmx_config are included so that
    uploading new data triggers reprocessing rather than a stale hit.
    """
    from qeeg.__version__ import __version__
    config_blob = json.dumps(config_dict, sort_keys=True, default=str)
    clinical_blob = json.dumps(clinical_meta, sort_keys=True, default=str) if clinical_meta else ""
    corrections_blob = json.dumps(eeg_corrections, sort_keys=True, default=str) if eeg_corrections else ""
    mmx_blob = json.dumps(mmx_config, sort_keys=True, default=str) if mmx_config else ""
    combined = hashlib.sha256(
        f"{__version__}|v{CACHE_SCHEMA_VERSION}|{content_hash}|{config_blob}|{clinical_blob}|{corrections_blob}|{mmx_blob}".encode()
    ).hexdigest()[:16]
    return combined


def _find_by_content_hash(content_hash: str, config_dict: dict,
                          cache_dir: Path,
                          clinical_meta: Optional[dict] = None,
                          eeg_corrections: Optional[dict] = None,
                          mmx_config: Optional[dict] = None) -> Optional[Path]:
    """Find a cached result directory matching content hash + config."""
    if not cache_dir.exists():
        return None
    target_key = _cache_key(content_hash, config_dict, clinical_meta, eeg_corrections, mmx_config)
    for d in cache_dir.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("cache_key") == target_key:
                # Verify data files exist
                if (d / "epochs.parquet").exists() and (d / "bin_summary.parquet").exists():
                    return d
        except Exception:
            continue
    return None


def save_result(result, config_dict: dict, content_hash: str,
                source_files: list[str], cache_dir: Path,
                clinical_meta: Optional[dict] = None,
                eeg_corrections: Optional[dict] = None,
                mmx_config: Optional[dict] = None) -> Path:
    """Save a PatientResult to disk cache. Returns the cache directory."""
    from qeeg.storage.parquet_io import save_epochs

    pid = result.patient_id
    cache_key = _cache_key(content_hash, config_dict, clinical_meta, eeg_corrections, mmx_config)
    # Use short hash prefix + patient_id for readable directory names
    dir_name = f"{content_hash[:12]}_{pid}"
    patient_dir = cache_dir / dir_name
    patient_dir.mkdir(parents=True, exist_ok=True)

    # Epochs (largest — parquet compresses well)
    save_epochs(result.epochs, patient_dir / "epochs.parquet", patient_id=pid)

    # Bin summary
    save_epochs(result.bin_summary, patient_dir / "bin_summary.parquet", patient_id=pid)

    # Column schema
    schema_entries = []
    for e in result.schema:
        schema_entries.append({
            "col_index": e.col_index, "code": e.code,
            "i_group": e.i_group, "sub_index": e.sub_index,
            "trend_name": e.trend_name, "family": e.family,
            "frequency_band": e.frequency_band,
            "freq_min_hz": e.freq_min_hz, "freq_max_hz": e.freq_max_hz,
            "hemisphere": e.hemisphere, "region": e.region,
            "electrode": e.electrode,
            "sub_column_name": e.sub_column_name,
            "common_name": e.common_name,
        })
    (patient_dir / "schema.json").write_text(
        json.dumps(schema_entries, indent=2, default=str), encoding="utf-8"
    )

    # Metadata
    meta = {
        "patient_id": pid,
        "cache_key": cache_key,
        "content_hash": content_hash,
        "source_files": [str(f) for f in source_files],
        "qc": result.qc.to_dict(),
        "seizure_report": result.seizure_report.to_dict(),
        "time_info": {
            "reference": result.time_info.reference,
            "reference_time": str(result.time_info.reference_time) if result.time_info.reference_time else None,
        },
        "artifact_result": {
            "total_epochs": result.artifact_result.total_epochs,
            "excluded_epochs": result.artifact_result.excluded_epochs,
            "artifact_pct": result.artifact_result.artifact_pct,
            "method": result.artifact_result.method,
        },
        "validation": {
            "leading_zero_rows": result.validation.leading_zero_rows,
        },
        "warnings": result.warnings,
        "n_epochs": len(result.epochs),
        "n_bins": len(result.bin_summary),
        "config": config_dict,
        "stage_row_counts": getattr(result, "stage_row_counts", {}) or {},
    }
    (patient_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )

    log.info("Cached result for %s at %s (content hash: %s…)", pid, patient_dir, content_hash[:12])
    return patient_dir


def load_result(content_hash: str, config_dict: dict, cache_dir: Path,
                clinical_meta: Optional[dict] = None,
                eeg_corrections: Optional[dict] = None,
                mmx_config: Optional[dict] = None):
    """Load a cached PatientResult if the cache is valid.

    Returns a dict with keys: epochs, bin_summary, schema, meta
    or None if cache is missing or stale.
    """
    patient_dir = _find_by_content_hash(content_hash, config_dict, cache_dir,
                                        clinical_meta, eeg_corrections, mmx_config)
    if patient_dir is None:
        return None

    try:
        from qeeg.storage.parquet_io import load_epochs

        meta = json.loads((patient_dir / "meta.json").read_text(encoding="utf-8"))
        epochs = load_epochs(patient_dir / "epochs.parquet")
        bin_summary = load_epochs(patient_dir / "bin_summary.parquet")

        schema_raw = []
        schema_path = patient_dir / "schema.json"
        if schema_path.exists():
            schema_raw = json.loads(schema_path.read_text(encoding="utf-8"))

        log.info("Cache hit for %s (hash: %s…)", meta.get("patient_id", "?"), content_hash[:12])
        return {
            "epochs": epochs,
            "bin_summary": bin_summary,
            "schema": schema_raw,
            "meta": meta,
        }
    except Exception as e:
        log.warning("Failed to load cache at %s: %s", patient_dir, e)
        return None


def load_patient_meta(patient_dir: Path) -> dict | None:
    """Load meta.json and schema.json from a cache directory without touching parquet.

    Returns dict with keys: meta, schema, cache_dir. Or None on failure.
    Used by the patient index to rebuild lightweight metadata on startup.
    """
    meta_path = patient_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        schema_raw: list[dict] = []
        schema_path = patient_dir / "schema.json"
        if schema_path.exists():
            schema_raw = json.loads(schema_path.read_text(encoding="utf-8"))
        # Verify parquet files exist (don't load them)
        if not (patient_dir / "epochs.parquet").exists():
            log.warning("epochs.parquet missing in %s, skipping", patient_dir.name)
            return None
        if not (patient_dir / "bin_summary.parquet").exists():
            log.warning("bin_summary.parquet missing in %s, skipping", patient_dir.name)
            return None
        return {"meta": meta, "schema": schema_raw, "cache_dir": patient_dir}
    except Exception as e:
        log.warning("Failed to load meta from %s: %s", patient_dir, e)
        return None


def list_cached_patients(cache_dir: Path) -> list[dict]:
    """List all cached patient results with summary info."""
    results = []
    if not cache_dir.exists():
        return results
    for patient_dir in sorted(cache_dir.iterdir()):
        meta_path = patient_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            results.append({
                "patient_id": meta["patient_id"],
                "content_hash": meta.get("content_hash", ""),
                "n_epochs": meta.get("n_epochs", 0),
                "n_bins": meta.get("n_bins", 0),
                "source_files": meta.get("source_files", []),
                "qc_summary": meta.get("qc", {}),
            })
        except Exception:
            continue
    return results


def clear_cache(patient_id: str, cache_dir: Path) -> bool:
    """Remove all cached results for exactly one patient. Returns True if any deleted."""
    import shutil
    deleted = False
    if not cache_dir.exists():
        return False
    for d in list(cache_dir.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        matches = False
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                matches = meta.get("patient_id") == patient_id
            except Exception:
                matches = False
        else:
            matches = d.name.endswith(f"_{patient_id}")
        if matches:
            shutil.rmtree(d)
            deleted = True
    return deleted


def cache_size_bytes(cache_dir: Path) -> int:
    """Total size of cache directory in bytes."""
    if not cache_dir.exists():
        return 0
    total = 0
    for f in cache_dir.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total
