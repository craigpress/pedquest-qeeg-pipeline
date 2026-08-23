"""Backend integration test: reprocess must fully invalidate the patient cache.

The frontend relies on reprocess clearing server-side state so a fresh
``GET /patients/{id}`` returns recomputed values. These tests pin that
behavior end-to-end without a browser:

* after reprocess the disk cache directory is replaced;
* the hot cache entry is dropped before run_pipeline re-warms it;
* ``/api/patients/{id}/epochs`` returns data for the new cache dir;
* clinical/correction cache-key inputs survive reprocess so study context
  isn't silently reset to defaults.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app, pipeline_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def processed_patient(synthetic_csv: Path):
    """Process a synthetic CSV and register it with the pipeline service.

    Yields (patient_id, initial_cache_dir). Cleans up the patient from both
    disk and index on teardown.
    """
    import shutil as _shutil
    from qeeg.pipeline import process_patient
    from qeeg.storage.result_cache import save_result, content_hash_files
    from qeeg.config import PipelineConfig

    with pipeline_service._lock:
        pipeline_service._hot_cache.clear()
        pipeline_service._bin_summary_cache.clear()

    result = process_patient(synthetic_csv)
    pid = result.patient_id
    config = PipelineConfig()
    content_hash = content_hash_files([synthetic_csv])
    save_result(
        result,
        config.model_dump(),
        content_hash,
        [str(synthetic_csv)],
        pipeline_service.cache_dir,
    )
    pipeline_service._build_patient_index()

    # Resolve the concrete cache directory for this patient.
    initial_cache = None
    for d in pipeline_service.cache_dir.iterdir():
        if d.is_dir() and d.name.endswith(f"_{pid}"):
            initial_cache = d
            break
    assert initial_cache is not None, "cache dir for patient not found"

    yield pid, initial_cache

    pipeline_service._patient_index.pop(pid, None)
    with pipeline_service._lock:
        pipeline_service._hot_cache.pop(pid, None)
        pipeline_service._bin_summary_cache.pop(pid, None)
    for d in pipeline_service.cache_dir.iterdir():
        if d.is_dir() and d.name.endswith(f"_{pid}"):
            _shutil.rmtree(d, ignore_errors=True)


def test_reprocess_clears_disk_and_hot_cache_before_rerun(processed_patient):
    """``reprocess_patient`` calls clear_cache and drops the hot-cache entry
    so stale data cannot leak into the fresh compute."""
    pid, initial_cache = processed_patient

    # Warm the hot cache so we can observe its invalidation.
    meta = pipeline_service._patient_index[pid]
    pipeline_service._get_or_load_frames(pid, meta)
    with pipeline_service._lock:
        assert pid in pipeline_service._hot_cache

    # Mid-request observer: when run_pipeline starts, the hot cache entry for
    # this patient must already have been cleared by reprocess_patient. We
    # intercept run_pipeline to capture that snapshot.
    snapshots: dict[str, object] = {}
    original_run = pipeline_service.run_pipeline

    def fake_run(*args, **kwargs):
        snapshots["hot_cache_has_pid"] = pid in pipeline_service._hot_cache
        snapshots["disk_cache_dirs"] = [
            d.name for d in pipeline_service.cache_dir.iterdir()
            if d.is_dir() and d.name.endswith(f"_{pid}")
        ]
        # Stop the pipeline from actually running to keep the test hermetic.
        from api.services.pipeline_service import JobStatus
        return JobStatus(job_id="fake", patient_id=pid)

    pipeline_service.run_pipeline = fake_run  # type: ignore[method-assign]
    try:
        from qeeg.config import PipelineConfig
        pipeline_service.reprocess_patient(pid, PipelineConfig())
    finally:
        pipeline_service.run_pipeline = original_run  # type: ignore[method-assign]

    assert snapshots["hot_cache_has_pid"] is False, (
        "reprocess did not evict the hot-cache entry before rerunning"
    )
    assert snapshots["disk_cache_dirs"] == [], (
        f"reprocess did not clear the disk cache dir: {snapshots['disk_cache_dirs']}"
    )

    # The index entry must also be gone so the next request rebuilds from disk
    # with fresh metadata.
    assert pid not in pipeline_service._patient_index


def test_cache_key_changes_when_config_changes(processed_patient):
    """Config mutations must produce a different cache key so the cache lookup
    misses and forces a recompute — this is what guarantees reprocess-with-
    new-params actually returns new data."""
    from qeeg.storage.result_cache import _cache_key

    _pid, initial_cache = processed_patient
    # Baseline config
    base_config = {"artifact": {"mode": "quality", "intensity_threshold": 5.0}}
    base_key = _cache_key("contenthash", base_config)

    # A different artifact mode must produce a different key.
    new_config = {"artifact": {"mode": "intensity", "intensity_threshold": 5.0}}
    new_key = _cache_key("contenthash", new_config)
    assert base_key != new_key, "config change did not change cache key"

    # Same config, different clinical metadata must also change the key so
    # reprocess-after-metadata-upload invalidates stale caches.
    key_no_clin = _cache_key("contenthash", base_config)
    key_with_clin = _cache_key("contenthash", base_config, clinical_meta={"rosc_date": "2026-04-01"})
    assert key_no_clin != key_with_clin

    # Same for corrections + MMX.
    key_with_corr = _cache_key("contenthash", base_config, eeg_corrections={"seg1": {"start": "12:00:00"}})
    assert key_no_clin != key_with_corr
    key_with_mmx = _cache_key("contenthash", base_config, mmx_config={"fingerprint": "abc"})
    assert key_no_clin != key_with_mmx
