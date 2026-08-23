"""Regression tests for reprocess context preservation."""

from __future__ import annotations

from pathlib import Path

from qeeg.config import PipelineConfig
from api.services.pipeline_service import PipelineService


def test_duplicate_cache_ranking_prefers_clinical_time_context():
    bad_newer = {
        "time_info": {"reference": "recording_start"},
        "qc": {"recording_duration_hours": 3695.99, "timestamp_gaps": 2},
        "config": {"binning": {"max_hours": 168.0}},
    }
    good_older = {
        "time_info": {"reference": "rosc"},
        "qc": {"recording_duration_hours": 11.53, "timestamp_gaps": 0},
        "config": {"binning": {"max_hours": 168.0}},
    }

    assert PipelineService._cache_candidate_rank(good_older, True, 1.0) > (
        PipelineService._cache_candidate_rank(bad_newer, True, 2.0)
    )


def test_reprocess_preserves_study_and_mmx_context(tmp_path: Path):
    from api.services.pipeline_service import PipelineService, StudyConfig

    upload_dir = tmp_path / "uploads"
    cache_dir = tmp_path / "cache"
    upload_dir.mkdir()
    cache_dir.mkdir()
    source = tmp_path / "P001.csv"
    source.write_text("ClockDateTime,I1_1\n1,2\n", encoding="utf-8")

    svc = PipelineService(upload_dir=upload_dir)
    svc.cache_dir = cache_dir
    patient_dir = cache_dir / "abc_P001"
    patient_dir.mkdir()
    (patient_dir / "meta.json").write_text(
        '{"patient_id": "P001", "source_files": ["' + str(source).replace("\\", "\\\\") + '"]}',
        encoding="utf-8",
    )

    svc._studies["StudyA"] = StudyConfig(name="StudyA", mmx_study="MMX_A")
    svc._patient_studies["P001"] = "StudyA"

    captured = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return "job"

    svc.run_pipeline = fake_run_pipeline  # type: ignore[method-assign]

    job = svc.reprocess_patient("P001", PipelineConfig())

    assert job == "job"
    assert captured["patient_id"] == "P001"
    assert captured["mmx_study"] == "MMX_A"
    assert captured["study_name"] == "StudyA"
