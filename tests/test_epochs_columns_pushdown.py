"""Tests for the ``columns=`` query path and parquet column pushdown.

The epoch endpoint accepts an explicit column list so the frontend can ask
for only the traces the active panel will actually render. The backend must
push the column list down to parquet (not load every column and filter in
memory). These tests cover:

* the route parses ``columns=`` and forwards it to the service;
* ``get_epoch_data_selective`` returns only the requested columns;
* the hot cache's ``loaded_columns`` reflects pushdown (fewer than all
  parquet columns) after a selective request.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app, pipeline_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def loaded_patient(synthetic_csv: Path):
    """Process a synthetic CSV and register it with the pipeline service."""
    import shutil
    from qeeg.pipeline import process_patient
    from qeeg.storage.result_cache import save_result, content_hash_files
    from qeeg.config import PipelineConfig

    # Fresh hot cache so loaded_columns reflects only this test's requests.
    with pipeline_service._lock:
        pipeline_service._hot_cache.clear()
        pipeline_service._bin_summary_cache.clear()

    result = process_patient(synthetic_csv)
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
    # Drop the hot cache the builder may have warmed so we can observe pushdown
    # on the first request.
    with pipeline_service._lock:
        pipeline_service._hot_cache.pop(result.patient_id, None)
        pipeline_service._bin_summary_cache.pop(result.patient_id, None)
    yield result

    pipeline_service._patient_index.pop(result.patient_id, None)
    with pipeline_service._lock:
        pipeline_service._hot_cache.pop(result.patient_id, None)
    for cache_sub in pipeline_service.cache_dir.iterdir():
        if cache_sub.is_dir() and cache_sub.name.endswith(f"_{result.patient_id}"):
            shutil.rmtree(cache_sub, ignore_errors=True)


def test_epochs_endpoint_forwards_columns_to_service(client: TestClient, loaded_patient):
    """When ``columns=`` is passed, the response returns only those columns."""
    pid = loaded_patient.patient_id
    # Pick two concrete column names known to exist via the schema.
    names = [
        e.common_name for e in loaded_patient.schema
        if e.common_name and e.family == "fft_power"
    ][:2]
    if len(names) < 2:
        pytest.skip("Synthetic fixture did not produce two fft_power columns")

    resp = client.get(
        f"/api/patients/{pid}/epochs",
        params={"families": "fft_power", "columns": ",".join(names)},
    )
    assert resp.status_code == 200
    body = resp.json()
    # All returned data columns must be in the requested set.
    returned = set(body["columns"].keys())
    assert returned, "response returned no columns"
    assert returned.issubset(set(names)), (
        f"unexpected columns in response: returned={returned} requested={names}"
    )
    assert body["hours"], "hours axis must be non-empty"


def test_get_epoch_data_selective_pushes_down_columns(loaded_patient):
    """Parquet pushdown: after a selective request, the hot cache should hold
    far fewer columns than the full parquet has."""
    pid = loaded_patient.patient_id

    meta = pipeline_service._patient_index[pid]
    import pyarrow.parquet as pq
    all_parquet_cols = set(pq.read_schema(str(meta.cache_dir / "epochs.parquet")).names)
    assert len(all_parquet_cols) >= 5, "fixture too small to demonstrate pushdown"

    # Request a single family worth of columns.
    names = [e.common_name for e in loaded_patient.schema if e.common_name and e.family == "fft_power"]
    assert names, "no fft_power columns to exercise"
    hours, data = pipeline_service.get_epoch_data_selective(
        pid, ["fft_power"], requested_columns=set(names),
    )
    assert hours, "selective call returned empty hours axis"

    with pipeline_service._lock:
        cached = pipeline_service._hot_cache.get(pid)
    assert cached is not None, "hot cache not populated after selective load"
    assert cached.full_load is False, "selective load should not mark full_load"
    # Pushdown: the cache must not hold every parquet column.
    assert len(cached.loaded_columns) < len(all_parquet_cols), (
        f"pushdown did not reduce loaded columns: "
        f"loaded={len(cached.loaded_columns)} parquet_total={len(all_parquet_cols)}"
    )


def test_selective_epoch_load_preserves_earlier_columns(loaded_patient):
    """Switching panels should union new columns with already-cached ones so
    previously-loaded traces remain available without re-reading parquet."""
    pid = loaded_patient.patient_id

    fft_names = [e.common_name for e in loaded_patient.schema if e.common_name and e.family == "fft_power"]
    assert fft_names
    pipeline_service.get_epoch_data_selective(pid, ["fft_power"], requested_columns=set(fft_names[:2]))
    with pipeline_service._lock:
        first_loaded = set(pipeline_service._hot_cache[pid].loaded_columns)

    # Request a different family. The union must include the first load.
    other_family = next(
        (f for f in {e.family for e in loaded_patient.schema}
         if f not in {"fft_power"} and any(
             e.common_name for e in loaded_patient.schema if e.family == f
         )),
        None,
    )
    if other_family is None:
        pytest.skip("No second family available to exercise the union path")

    pipeline_service.get_epoch_data_selective(pid, [other_family], requested_columns=None)
    with pipeline_service._lock:
        second_loaded = set(pipeline_service._hot_cache[pid].loaded_columns)

    assert first_loaded.issubset(second_loaded), (
        "second selective load dropped columns from the earlier load"
    )
