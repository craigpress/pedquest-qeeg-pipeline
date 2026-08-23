"""Canonical filesystem roots — defined once, imported everywhere.

All live at the project root (never on the network share). Centralized so the
repo-root computation is not re-derived per module; it was previously duplicated
in sidecar.py, api/services/pipeline_service.py, and api/routes/scan.py via a
fragile ``Path(__file__).resolve().parent.parent.parent`` that silently depended
on each file's directory depth.
"""
from __future__ import annotations

from pathlib import Path

# qeeg/paths.py -> qeeg -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CACHE_DIR = PROJECT_ROOT / ".qeeg_cache"
SIDECAR_DIR = CACHE_DIR / "sidecars"
PARQUET_DIR = CACHE_DIR / "parquet"
UPLOAD_DIR = PROJECT_ROOT / ".uploads"
EXPORT_DIR = PROJECT_ROOT / ".exports"
