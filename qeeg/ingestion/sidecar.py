"""Per-file metadata cache for Persyst CSV files.

Stores classification results, header mappings, and Parquet status in
.qeeg_cache/sidecars/<path_hash>.json on local disk. Never writes to the
source network share. The Parquet cache lives in .qeeg_cache/parquet/.

On scan: sidecar replaces the 32KB-per-file network read (becomes ~1KB local read).
On parse: if Parquet is ready, parse_persyst_csv() returns via DuckDB without
touching the network CSV at all.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Both dirs live inside .qeeg_cache/ at the project root — never on the share.
from ..paths import CACHE_DIR as _CACHE_DIR, SIDECAR_DIR as _SIDECAR_DIR, PARQUET_DIR as _PARQUET_DIR


def _path_hash(csv_path: Path) -> str:
    """Stable key derived from the absolute resolved path."""
    return hashlib.md5(str(csv_path.resolve()).encode()).hexdigest()


def sidecar_path(csv_path: Path) -> Path:
    return _SIDECAR_DIR / f"{_path_hash(csv_path)}.json"


def parquet_cache_path(csv_path: Path) -> Path:
    return _PARQUET_DIR / f"{_path_hash(csv_path)}.parquet"


@dataclass
class SidecarMeta:
    source_csv: str
    source_mtime: float
    file_type: str
    csv_panel_type: str
    patient_id: str
    test_date: str
    test_time: str
    encoding: str
    n_columns: int
    n_data_rows: int
    code_row_index: int = -1
    trend_row_index: int = -1
    persyst_version: str = ""
    code_to_description: dict = field(default_factory=dict)
    description_to_codes: dict = field(default_factory=dict)
    parquet_status: str = "pending"   # "pending" | "ready" | "failed"
    parquet_path: str = ""
    phase: str = "scan"               # "scan" | "full"


def read_sidecar(csv_path: Path) -> Optional[SidecarMeta]:
    """Return sidecar if it exists and the CSV mtime still matches.

    Returns None on any miss, mtime mismatch, or parse failure so callers
    always fall back to the CSV read path gracefully.
    """
    sp = sidecar_path(csv_path)
    if not sp.exists():
        return None
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        current_mtime = csv_path.stat().st_mtime
        # 1-second tolerance handles FAT32 / SMB mtime precision limits
        if abs(data.get("source_mtime", 0.0) - current_mtime) > 1.0:
            return None
        # Forward-compatible: ignore unknown fields added in future versions
        known = {f.name for f in dataclasses.fields(SidecarMeta)}
        filtered = {k: v for k, v in data.items() if k in known}
        return SidecarMeta(**filtered)
    except Exception:
        return None


def write_sidecar(csv_path: Path, meta: SidecarMeta) -> None:
    """Persist sidecar to local .qeeg_cache/sidecars/. Silently ignores failures."""
    sp = sidecar_path(csv_path)
    try:
        _SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(dataclasses.asdict(meta), indent=2), encoding="utf-8")
    except Exception as exc:
        log.debug("Could not write sidecar for %s: %s", csv_path.name, exc)
