"""C.3 — orig_step fallback reads engine cadence from MMX config."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


def _make_service(tmp_path: Path, with_mmx_step: float | None = None):
    from api.services.pipeline_service import PipelineService, StudyConfig
    from qeeg.ingestion.mmx_parser import EngineConfig

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    svc = PipelineService(upload_dir=upload_dir)

    if with_mmx_step is not None:
        svc._mmx_configs["STUDY_MMX"] = {
            "engines": {
                "FastEngine": EngineConfig(
                    name="FastEngine",
                    epoch_duration=with_mmx_step,
                    epoch_step=with_mmx_step,
                )
            },
            "fingerprint": "abc123",
            "source_path": "test.mmx",
        }
        svc._studies["PedQuEST"] = StudyConfig(name="PedQuEST", mmx_study="STUDY_MMX")
        svc._patient_studies["PAT001"] = "PedQuEST"
    return svc


def _seed_clinical_and_correction(svc, patient_id, csv_path):
    from api.services.pipeline_service import ClinicalMetadata, EEGCorrection

    svc._clinical_metadata[patient_id] = ClinicalMetadata(
        patient_id=patient_id,
        age_at_arrest_days=100,
        rosc_datetime="2024-01-15T08:30:00",
    )
    svc._eeg_corrections[csv_path.stem] = EEGCorrection(
        new_name=csv_path.stem,
        age_in_days_at_time_of_eeg=99,
        eeg_start_time="10:00:00",
        eeg_duration="01:00:00",
    )


class _FakeParsed:
    def __init__(self, df):
        self.data = df


def test_orig_step_uses_engine_cadence_when_clock_flat(synthetic_csv, tmp_path):
    """When ClockDateTime is flat (last==first) and MMX has epoch_step=2.0,
    orig_step should fall back to 2.0/86400 instead of 1.0/86400.
    """
    from api.services import pipeline_service as ps_mod

    svc = _make_service(tmp_path, with_mmx_step=2.0)
    _seed_clinical_and_correction(svc, "PAT001", synthetic_csv)

    flat_df = pd.DataFrame({
        "ClockDateTime": [1.0] * 10,
        "I1_1": list(range(10)),
    })

    with patch.object(ps_mod, "parse_persyst_csv", return_value=_FakeParsed(flat_df.copy())):
        parsed_list, _ = svc._apply_date_corrections([synthetic_csv], "PAT001")

    assert parsed_list is not None
    df = parsed_list[0].data
    stride = float(df["ClockDateTime"].iloc[1] - df["ClockDateTime"].iloc[0])
    expected = 2.0 / 86400.0
    assert stride == pytest.approx(expected, rel=1e-6), (
        f"stride {stride} should equal engine cadence {expected} (2.0 s in days)"
    )


def test_orig_step_uses_min_across_multiple_engines(synthetic_csv, tmp_path):
    """With multiple engines (FFT at 1s, Rhythmicity at 322s), orig_step must
    pick the SMALLEST cadence — rows are emitted at the fastest engine's rate.
    Picking the first-found would give subject-10's 322× time-axis inflation.
    """
    from api.services import pipeline_service as ps_mod
    from api.services.pipeline_service import EngineConfig, StudyConfig

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    svc = ps_mod.PipelineService(upload_dir=upload_dir)
    svc._mmx_configs["STUDY_MMX"] = {
        "engines": {
            "Rhythmicity": EngineConfig(
                name="Rhythmicity", epoch_duration=322.0, epoch_step=322.0,
            ),
            "FFT": EngineConfig(
                name="FFT", epoch_duration=1.0, epoch_step=1.0,
            ),
        },
        "fingerprint": "multi123",
        "source_path": "test.mmx",
    }
    svc._studies["PedQuEST"] = StudyConfig(name="PedQuEST", mmx_study="STUDY_MMX")
    svc._patient_studies["PAT003"] = "PedQuEST"
    _seed_clinical_and_correction(svc, "PAT003", synthetic_csv)

    flat_df = pd.DataFrame({
        "ClockDateTime": [1.0] * 10,
        "I1_1": list(range(10)),
    })
    with patch.object(ps_mod, "parse_persyst_csv", return_value=_FakeParsed(flat_df.copy())):
        parsed_list, _ = svc._apply_date_corrections([synthetic_csv], "PAT003")

    assert parsed_list is not None
    df = parsed_list[0].data
    stride = float(df["ClockDateTime"].iloc[1] - df["ClockDateTime"].iloc[0])
    # Must be FFT's 1s, not Rhythmicity's 322s (which would give ~0.003729)
    assert stride == pytest.approx(1.0 / 86400.0, rel=1e-6), (
        f"stride {stride} should be min engine step (1s), not 322s"
    )


def test_orig_step_falls_back_to_one_second_without_mmx(synthetic_csv, tmp_path):
    """Without an MMX config, fallback remains 1.0/86400 seconds."""
    from api.services import pipeline_service as ps_mod

    svc = _make_service(tmp_path, with_mmx_step=None)
    _seed_clinical_and_correction(svc, "PAT002", synthetic_csv)

    flat_df = pd.DataFrame({
        "ClockDateTime": [1.0] * 10,
        "I1_1": list(range(10)),
    })

    with patch.object(ps_mod, "parse_persyst_csv", return_value=_FakeParsed(flat_df.copy())):
        parsed_list, _ = svc._apply_date_corrections([synthetic_csv], "PAT002")

    assert parsed_list is not None
    df = parsed_list[0].data
    stride = float(df["ClockDateTime"].iloc[1] - df["ClockDateTime"].iloc[0])
    assert stride == pytest.approx(1.0 / 86400.0, rel=1e-6)
