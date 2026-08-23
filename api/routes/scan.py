"""Folder scan endpoint — classify files for batch import."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models.schemas import ScanRequest, ScanResponse, ScannedFile

router = APIRouter(prefix="/api", tags=["scan"])

_RAW_EEG_EXTENSIONS = {".dat", ".lay"}

# Cache lives next to the app root (same as pipeline_service CACHE_DIR)
from qeeg.paths import CACHE_DIR as _CACHE_DIR
_SCAN_CACHE_FILE = _CACHE_DIR / "scan_cache.json"

# Thread pool for parallel file classification (I/O-bound).
# High worker count is appropriate here — purely network I/O, no CPU pressure.
_CLASSIFY_POOL = ThreadPoolExecutor(max_workers=32)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def _validate_folder_path(path_str: str) -> Path:
    """Validate a folder path. Raises HTTPException on security violations.

    Returns the path in its original (non-resolved) form so that mapped drives
    (e.g. Z:\\) are preserved. Resolving to UNC (\\\\server\\share\\...) would
    cause downstream upload/local registration to reject those paths.
    """
    if ".." in path_str:
        raise HTTPException(400, "Path traversal not allowed")
    if path_str.startswith("\\\\") or path_str.startswith("//"):
        raise HTTPException(400, "Network paths not allowed")
    p = Path(path_str)
    try:
        resolved = p.resolve()
    except (OSError, ValueError) as exc:
        raise HTTPException(400, f"Invalid path: {exc}") from exc
    if not resolved.exists():
        raise HTTPException(404, f"Folder not found: {path_str}")
    if not resolved.is_dir():
        raise HTTPException(400, f"Path is not a directory: {path_str}")
    # Return the non-resolved form — preserves drive letters on Windows
    return p


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

def _classify_csv(path: Path) -> tuple[str, Optional[str]]:
    """Classify a CSV as persyst_csv, clinical_csv, corrections_csv, or unknown.

    Reads a single 32KB chunk from the file — one network round-trip regardless
    of file size. This is critical for large (2-3GB) CSVs on network shares where
    multiple open() calls each trigger a separate network block transfer.
    """
    try:
        from qeeg.ingestion.parser import _ICODE_RE

        # Single read of 32KB — enough to cover 66 header/data lines in any
        # Persyst CSV. One network block fetch total.
        with open(path, "rb") as fh:
            raw = fh.read(32768)

        # Detect encoding from the chunk itself
        encoding = "utf-8"
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                raw.decode(enc)
                encoding = enc
                break
            except (UnicodeDecodeError, ValueError):
                continue

        text = raw.decode(encoding, errors="replace")
        reader = csv.reader(text.splitlines())

        first_row = next(reader, None)
        if first_row is not None:
            header_lower = {c.strip().lower() for c in first_row}
            if "new_name" in header_lower and any(
                "age_in_days" in h for h in header_lower
            ):
                return "corrections_csv", None
            if "patient_id" in header_lower and "age_days" in header_lower:
                return "clinical_csv", None

        # Reset and scan up to 66 lines for icode pattern
        reader = csv.reader(text.splitlines())
        for i, row in enumerate(reader):
            if i > 65:
                break
            if any(_ICODE_RE.match(c.strip()) for c in row if c.strip()):
                return "persyst_csv", None

        return "unknown", None

    except Exception as exc:
        return "unknown", str(exc)


def _classify_file(path: Path) -> tuple[str, Optional[str]]:
    """Return (file_type, error) for a single file."""
    ext = path.suffix.lower()
    if ext in _RAW_EEG_EXTENSIONS:
        return "raw_eeg", None
    if ext == ".csv":
        return _classify_csv(path)
    return "unknown", None


def _write_scan_sidecar(path: Path, file_type: str, qs) -> None:
    """Persist a scan-phase sidecar for a classified Persyst CSV."""
    try:
        from qeeg.ingestion.sidecar import read_sidecar, write_sidecar, SidecarMeta
        existing = read_sidecar(path)
        write_sidecar(
            path,
            SidecarMeta(
                source_csv=str(path),
                source_mtime=path.stat().st_mtime,
                file_type=file_type,
                csv_panel_type=qs.csv_panel_type,
                patient_id=qs.patient_id,
                test_date=qs.test_date,
                test_time=qs.test_time,
                encoding=qs.encoding,
                n_columns=qs.n_columns,
                n_data_rows=qs.n_data_rows,
                code_row_index=qs.code_row_index,
                trend_row_index=(qs.code_row_index - 1) if qs.code_row_index > 0 else -1,
                parquet_status=existing.parquet_status if existing else "pending",
                parquet_path=existing.parquet_path if existing else "",
                phase="scan",
            ),
        )
    except Exception:
        pass


def _classify_and_build(path: Path) -> ScannedFile:
    """Classify a single file and return a ScannedFile. Used in thread pool.

    Checks the local sidecar cache first — a ~1KB read from .qeeg_cache/ on
    local disk instead of a 32KB+ read from the network share. Falls back to
    the 32KB classify + quick_scan path when no valid sidecar exists.
    """
    # Sidecar fast path: avoids any network read on repeat scans
    try:
        from qeeg.ingestion.sidecar import read_sidecar
        sidecar = read_sidecar(path)
        if sidecar is not None:
            return ScannedFile(
                path=str(path),
                filename=path.name,
                file_type=sidecar.file_type,
                size_bytes=path.stat().st_size,
                error=None,
                csv_panel_type=sidecar.csv_panel_type or None,
            )
    except Exception:
        pass

    # Fallback: 32KB classify + quick_scan, then write sidecar for next time
    file_type, error = _classify_file(path)
    csv_panel_type: Optional[str] = None
    if file_type == "persyst_csv":
        try:
            from qeeg.ingestion.quick_scan import quick_scan
            qs = quick_scan(path)
            csv_panel_type = qs.csv_panel_type
            _write_scan_sidecar(path, file_type, qs)
        except Exception:
            pass
    return ScannedFile(
        path=str(path),
        filename=path.name,
        file_type=file_type,
        size_bytes=path.stat().st_size,
        error=error,
        csv_panel_type=csv_panel_type,
    )


def _queue_pending_conversions(scanned: list[ScannedFile]) -> None:
    """Enqueue persyst_csv files that don't yet have a ready Parquet conversion."""
    try:
        from qeeg.ingestion.sidecar import read_sidecar
        from qeeg.ingestion.conversion_queue import enqueue
        for sf in scanned:
            if sf.file_type != "persyst_csv":
                continue
            try:
                sidecar = read_sidecar(Path(sf.path))
                if sidecar is None or sidecar.parquet_status != "ready":
                    enqueue(Path(sf.path))
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Scan cache
# ---------------------------------------------------------------------------

def _file_cache_key(path: Path) -> str:
    """Key = path + mtime + size (no file read needed)."""
    stat = path.stat()
    return f"{path}|{stat.st_mtime}|{stat.st_size}"


def _folder_cache_key(folder: Path, file_paths: list[Path]) -> str:
    """Stable cache key for a folder scan: hash of all file keys.
    Stat calls are parallelized to avoid serial network round-trips."""
    futures = [_CLASSIFY_POOL.submit(_file_cache_key, p) for p in file_paths]
    parts = sorted(f.result() for f in futures)
    raw = "\n".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _load_scan_cache() -> dict:
    try:
        if _SCAN_CACHE_FILE.exists():
            return json.loads(_SCAN_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_scan_cache(cache: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _SCAN_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass


def _cached_scan(folder: Path, file_paths: list[Path]) -> Optional[list[ScannedFile]]:
    """Return cached ScannedFile list if folder+files haven't changed."""
    cache = _load_scan_cache()
    key = _folder_cache_key(folder, file_paths)
    entry = cache.get(key)
    if not entry:
        return None
    try:
        return [ScannedFile(**f) for f in entry["files"]]
    except Exception:
        return None


def _store_scan(folder: Path, file_paths: list[Path], files: list[ScannedFile]) -> None:
    cache = _load_scan_cache()
    key = _folder_cache_key(folder, file_paths)
    cache[key] = {
        "folder": str(folder),
        "scanned_at": time.time(),
        "files": [f.model_dump() for f in files],
    }
    # Keep at most 20 folder entries to avoid unbounded growth
    if len(cache) > 20:
        oldest_key = next(iter(cache))
        del cache[oldest_key]
    _save_scan_cache(cache)


# ---------------------------------------------------------------------------
# Sync scan helper (used by both endpoints)
# ---------------------------------------------------------------------------

_RELEVANT_EXTENSIONS = {".csv"}

def _collect_file_paths(folder: Path, recursive: bool) -> list[Path]:
    iter_files = folder.rglob("*.csv") if recursive else folder.glob("*.csv")
    return sorted(iter_files)


def _run_parallel_classify(file_paths: list[Path]) -> list[ScannedFile]:
    """Classify all files in parallel using the thread pool."""
    futures = [_CLASSIFY_POOL.submit(_classify_and_build, p) for p in file_paths]
    return [f.result() for f in futures]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scan/folder", response_model=ScanResponse)
def scan_folder(req: ScanRequest):
    """Recursively walk a directory and classify files for batch import.

    Security: rejects path traversal (..) and UNC/network paths.
    Returns cached results when folder contents are unchanged.
    """
    folder = _validate_folder_path(req.folder_path)
    file_paths = _collect_file_paths(folder, req.recursive)

    # Check cache first
    cached = _cached_scan(folder, file_paths)
    if cached is not None:
        scanned = cached
    else:
        scanned = _run_parallel_classify(file_paths)
        _store_scan(folder, file_paths, scanned)

    _queue_pending_conversions(scanned)

    counts: dict[str, int] = {}
    for f in scanned:
        counts[f.file_type] = counts.get(f.file_type, 0) + 1

    return ScanResponse(folder=str(folder), files=scanned, counts=counts)


@router.post("/scan/folder/stream")
async def scan_folder_stream(req: ScanRequest):
    """SSE stream of folder scan progress.

    Emits 'progress' events with {classified, total} as each file is classified,
    then a final 'complete' event with the full ScanResponse payload.
    """
    folder = _validate_folder_path(req.folder_path)

    async def event_generator():
        loop = asyncio.get_event_loop()
        file_paths = await loop.run_in_executor(
            None, _collect_file_paths, folder, req.recursive
        )
        total = len(file_paths)

        # Check cache — if hit, emit a single complete event immediately
        cached = await loop.run_in_executor(None, _cached_scan, folder, file_paths)
        if cached is not None:
            scanned = cached
            counts: dict[str, int] = {}
            for f in scanned:
                counts[f.file_type] = counts.get(f.file_type, 0) + 1
            result = ScanResponse(folder=str(folder), files=scanned, counts=counts)
            yield {
                "event": "progress",
                "data": json.dumps({"classified": total, "total": total, "cached": True}),
            }
            yield {"event": "complete", "data": result.model_dump_json()}
            return

        scanned: list[ScannedFile] = []
        futures = [_CLASSIFY_POOL.submit(_classify_and_build, p) for p in file_paths]

        for i, future in enumerate(futures):
            sf = await loop.run_in_executor(None, future.result)
            scanned.append(sf)
            yield {
                "event": "progress",
                "data": json.dumps({"classified": i + 1, "total": total, "cached": False}),
            }

        counts = {}
        for f in scanned:
            counts[f.file_type] = counts.get(f.file_type, 0) + 1

        result = ScanResponse(folder=str(folder), files=scanned, counts=counts)
        await loop.run_in_executor(None, _store_scan, folder, file_paths, scanned)
        await loop.run_in_executor(None, _queue_pending_conversions, scanned)

        yield {"event": "complete", "data": result.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.get("/scan/conversion/status")
def conversion_status():
    """Return background Parquet conversion queue depth."""
    from qeeg.ingestion.conversion_queue import queue_size
    return {"queued": queue_size()}
