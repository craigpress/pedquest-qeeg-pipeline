"""Background Parquet conversion queue.

A single daemon thread converts queued CSVs to Parquet via
convert_csv_to_parquet(). Callers enqueue and return immediately.
The worker is started once at app startup via start_worker().
"""
from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_queue: queue.Queue[Optional[Path]] = queue.Queue()
_enqueued: set[str] = set()
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None


def _worker() -> None:
    while True:
        csv_path = _queue.get()
        if csv_path is None:
            _queue.task_done()
            return  # sentinel — stops the worker
        try:
            from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
            convert_csv_to_parquet(csv_path)
        except Exception as exc:
            log.warning("Parquet conversion failed for %s: %s", csv_path.name, exc)
        finally:
            with _lock:
                _enqueued.discard(str(csv_path.resolve()))
            _queue.task_done()


def start_worker() -> None:
    """Start the background conversion worker daemon thread (idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(
        target=_worker, daemon=True, name="parquet-converter"
    )
    _thread.start()
    log.debug("Parquet conversion worker started")


def enqueue(csv_path: Path) -> bool:
    """Queue a CSV for background Parquet conversion.

    Returns True if enqueued, False if already queued or being converted.
    """
    key = str(csv_path.resolve())
    with _lock:
        if key in _enqueued:
            return False
        _enqueued.add(key)
    _queue.put(csv_path)
    return True


def queue_size() -> int:
    """Number of conversions waiting in the queue (not including in-progress)."""
    return _queue.qsize()
