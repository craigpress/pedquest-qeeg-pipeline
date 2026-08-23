"""FastAPI application for the qEEG Analysis Pipeline."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)

# Ensure project root is on sys.path so `qeeg` package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.services.pipeline_service import PipelineService
from qeeg.__version__ import __version__
from qeeg.ingestion.conversion_queue import start_worker as _start_conversion_worker

from qeeg.paths import UPLOAD_DIR
UPLOAD_DIR.mkdir(exist_ok=True)

pipeline_service = PipelineService(upload_dir=UPLOAD_DIR)
_start_conversion_worker()


def _preload_patient_caches() -> None:
    """Background thread: read parquet footers to warm Windows Defender's file scanner.

    Only reads the parquet schema (file footer, a few KB) — does NOT build DataFrames.
    This triggers Defender to scan each file once at startup so the first real request
    is fast. DataFrame construction is left to demand loading so the event loop is
    never blocked.
    """
    import time
    import pyarrow.parquet as _pq
    time.sleep(4)  # Wait for server to finish startup
    for pid in pipeline_service.list_patients():
        meta = pipeline_service.get_patient_meta(pid)
        if not meta:
            continue
        for fname in ("epochs.parquet", "bin_summary.parquet"):
            fpath = meta.cache_dir / fname
            if not fpath.exists():
                continue
            # Skip tiny files (test/synthetic data) — only warm real patient caches (>1 MB)
            if fpath.stat().st_size < 1024 * 1024:
                continue
            try:
                _pq.read_schema(str(fpath))
                log.info("Defender-warmed %s/%s", pid, fname)
            except Exception as exc:
                log.warning("Preload schema read failed for %s/%s: %s", pid, fname, exc)
        time.sleep(0.5)  # Yield between patients so event loop stays responsive


threading.Thread(target=_preload_patient_caches, daemon=True).start()

app = FastAPI(
    title="PedQuEST qEEG Analyzer",
    description="REST API for pediatric qEEG analysis (PedQuEST study)",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
from api.routes import upload, pipeline, patients, export, scan, manifest, studies  # noqa: E402

app.include_router(upload.router)
app.include_router(pipeline.router)
app.include_router(patients.router)
app.include_router(export.router)
app.include_router(scan.router)
app.include_router(manifest.router)
app.include_router(studies.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "patients_loaded": len(pipeline_service.list_patients())}


# Serve frontend static files in production (after vite build)
# IMPORTANT: This must be LAST — it's a catch-all mount.
# In dev mode (Vite on :3000 proxying to :8000), this is not needed.
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
