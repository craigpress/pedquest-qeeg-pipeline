"""Publication-grade audit bundle.

Produces a machine-readable provenance record that makes a pipeline run
independently reproducible and auditable by a journal statistician or a
clinical-data reviewer. The bundle captures:

* pipeline + cache-schema + Python + dependency versions
* git commit and dirty-worktree flag
* SHA-256 hashes for every raw input file (CSVs, MMX, clinical metadata,
  EEG corrections)
* SHA-256 hashes for every generated export (epochs parquet, bin summary
  parquet, data dictionary, etc.)
* stage row-count checkpoints (parsed, ROSC-trimmed, artifact-clean,
  usable, binned)
* exact ``PipelineConfig`` as JSON
* per-segment correction/clinical rows if applicable

The bundle is written as ``audit_bundle.json`` alongside the other research
artefacts in a cohort or single-patient package and stored in the cache
directory as ``.qeeg_cache/<hash>_<patient>/audit_bundle.json`` for the most
recent run. It is the primary artefact a statistician fact-checks before
analysis lock.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from qeeg.__version__ import __version__ as PIPELINE_VERSION
from qeeg.storage.result_cache import CACHE_SCHEMA_VERSION


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str | None:
    """Full-content SHA-256 of a file, or None if the file is unreadable."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, FileNotFoundError):
        return None


def _git_info(repo_root: Path) -> dict[str, Any]:
    """Return {commit, dirty, branch} for the enclosing git repo (best-effort)."""
    def _run(args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip() or None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    commit = _run(["rev-parse", "HEAD"])
    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    status = _run(["status", "--porcelain"])
    dirty = bool(status)
    return {"commit": commit, "branch": branch, "dirty": dirty}


def _python_info() -> dict[str, Any]:
    return {
        "version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }


def _pip_freeze_digest() -> dict[str, Any]:
    """Return {packages_sha256, package_count} from the current environment."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return {"packages_sha256": None, "package_count": 0}
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        lines.sort()
        normalised = "\n".join(lines).encode("utf-8")
        digest = hashlib.sha256(normalised).hexdigest()
        return {"packages_sha256": digest, "package_count": len(lines)}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"packages_sha256": None, "package_count": 0}


def build_audit_bundle(
    *,
    patient_id: str,
    config: dict[str, Any] | None,
    raw_inputs: Iterable[Path] = (),
    auxiliary_inputs: Iterable[Path] = (),
    generated_exports: Iterable[Path] = (),
    stage_row_counts: dict[str, int] | None = None,
    mmx_path: Path | None = None,
    clinical_rows: list[dict[str, Any]] | None = None,
    correction_rows: list[dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Build an audit bundle dict. Callers serialise via ``json.dumps``.

    Args:
        patient_id: opaque patient identifier (study ID or de-identified stem).
        config: the exact ``PipelineConfig`` as dict (see
            ``qeeg.config.PipelineConfig.model_dump``).
        raw_inputs: Persyst CSV paths contributing to this run.
        auxiliary_inputs: Clinical metadata, EEG corrections, etc.
        generated_exports: Output files whose SHA-256 should be captured
            (epochs.parquet, bin_summary.parquet, data_dictionary.json,
            research_package.zip, etc.).
        stage_row_counts: Per-stage integer row counts (e.g. ``{"parsed":
            123456, "rosc_trimmed": 120000, "artifact_clean": 100000,
            "usable": 98000, "binned": 12}``).
        mmx_path: MMX panel config used; hashed separately.
        clinical_rows: Clinical metadata rows applied to this patient (list of
            dicts). Not hashed — the raw file hash is authoritative.
        correction_rows: EEG correction rows applied to this patient.
        repo_root: Directory to query ``git`` from.
        cache_dir: Patient cache directory, for reference in the output.

    Returns:
        A JSON-serialisable dict. No I/O performed; caller writes to disk.
    """
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    raw_input_hashes = [
        {"path": str(p), "sha256": _sha256_file(Path(p)), "size_bytes": Path(p).stat().st_size if Path(p).exists() else None}
        for p in raw_inputs
    ]
    aux_input_hashes = [
        {"path": str(p), "sha256": _sha256_file(Path(p)), "size_bytes": Path(p).stat().st_size if Path(p).exists() else None}
        for p in auxiliary_inputs
    ]
    export_hashes = [
        {"path": str(p), "sha256": _sha256_file(Path(p)), "size_bytes": Path(p).stat().st_size if Path(p).exists() else None}
        for p in generated_exports
    ]

    mmx_hash = None
    if mmx_path is not None and Path(mmx_path).exists():
        mmx_hash = _sha256_file(Path(mmx_path))

    return {
        "audit_bundle_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "patient_id": patient_id,
        "pipeline": {
            "version": PIPELINE_VERSION,
            "cache_schema_version": CACHE_SCHEMA_VERSION,
        },
        "python": _python_info(),
        "dependencies": _pip_freeze_digest(),
        "git": _git_info(repo_root),
        "config": config or {},
        "mmx": {"path": str(mmx_path) if mmx_path else None, "sha256": mmx_hash},
        "inputs": {
            "raw": raw_input_hashes,
            "auxiliary": aux_input_hashes,
        },
        "exports": export_hashes,
        "stage_row_counts": stage_row_counts or {},
        "clinical_rows": clinical_rows or [],
        "correction_rows": correction_rows or [],
        "cache_dir": str(cache_dir) if cache_dir else None,
    }


def write_audit_bundle(bundle: dict[str, Any], out_path: Path) -> Path:
    """Serialise a bundle to JSON. Returns the output path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    return out_path
