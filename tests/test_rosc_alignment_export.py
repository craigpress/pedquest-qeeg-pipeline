"""Round-trip test: ROSC alignment information flows into research-package provenance.

Covers gaps identified in the 2026-04-18 validation pass:
- provenance.alignment.time_reference reflects ROSC vs recording_start
- provenance.alignment.rosc_datetime matches what the pipeline was told
- bin_start_hours axis is anchored at ROSC when ROSC is provided
- negative case (no ROSC) still exports cleanly and labels the reference correctly
- cohort semi-long helper emits the same fields in its wide table
"""
from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from qeeg.alignment.time_axis import TimeAxisInfo
from qeeg.storage.export import (
    build_alignment_info,
    build_provenance,
    build_research_package,
    export_cohort_semi_long,
)
from qeeg.validation.alignment_check import AlignmentResult


# ----------------------------- fixtures -----------------------------------


def _fake_bin_summary() -> pd.DataFrame:
    """Minimal bin_summary with two bins — one complete, one low-coverage."""
    return pd.DataFrame([
        {
            "bin_label": "0-6h", "bin_start_hours": 0.0, "bin_end_hours": 6.0,
            "n_total_epochs": 21600, "n_usable_epochs": 20000,
            "n_observed": 20000, "n_effective_fft": 2500,
            "coverage_hours": 5.6, "coverage_fraction": 0.93, "meets_minimum": True,
            "background_continuity_index": 0.82,
            "missingness_flag": "complete",
            "adr_ant_median": 0.45, "adr_ant_mean": 0.47, "adr_ant_sd": 0.10,
            "adr_ant_iqr": 0.12, "adr_ant_min": 0.30, "adr_ant_max": 0.70,
            "adr_ant_n": 20000, "adr_ant_slope": -0.01,
            "suppression_left_median": 0.20, "suppression_left_mean": 0.25,
            "suppression_left_sd": 0.05, "suppression_left_iqr": 0.05,
            "suppression_left_min": 0.10, "suppression_left_max": 0.45,
            "suppression_left_n": 20000, "suppression_left_slope": 0.02,
        },
        {
            "bin_label": "6-12h", "bin_start_hours": 6.0, "bin_end_hours": 12.0,
            "n_total_epochs": 21600, "n_usable_epochs": 500,
            "n_observed": 500, "n_effective_fft": 60,
            "coverage_hours": 0.14, "coverage_fraction": 0.02, "meets_minimum": False,
            "background_continuity_index": 0.40,
            "missingness_flag": "low_data",
            "adr_ant_median": 0.52, "adr_ant_mean": 0.55, "adr_ant_sd": 0.08,
            "adr_ant_iqr": 0.10, "adr_ant_min": 0.40, "adr_ant_max": 0.70,
            "adr_ant_n": 500, "adr_ant_slope": -0.01,
            "suppression_left_median": 0.30, "suppression_left_mean": 0.33,
            "suppression_left_sd": 0.06, "suppression_left_iqr": 0.08,
            "suppression_left_min": 0.20, "suppression_left_max": 0.55,
            "suppression_left_n": 500, "suppression_left_slope": 0.02,
        },
    ])


def _unzip_provenance(buf: io.BytesIO) -> dict:
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        with zf.open("provenance.json") as fp:
            return json.loads(fp.read().decode("utf-8"))


def _unzip_semi_long(buf: io.BytesIO, patient_id: str) -> pd.DataFrame:
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        with zf.open(f"{patient_id}_semi_long.csv") as fp:
            return pd.read_csv(fp)


# ---------------------- build_alignment_info unit tests --------------------


def test_build_alignment_info_no_alignment_is_recording_start():
    info = build_alignment_info(
        TimeAxisInfo(reference="recording_start", reference_time=pd.Timestamp("2026-01-01 00:00:00")),
        None,
    )
    assert info["time_reference"] == "recording_start"
    assert info["is_aligned"] is False
    assert info["rosc_datetime"] is None
    assert info["hours_from_rosc_to_eeg"] is None
    assert info["has_pre_rosc_data"] is False


def test_build_alignment_info_rosc_aligned_roundtrip():
    rosc = pd.Timestamp("2026-01-01 10:00:00")
    eeg_start = pd.Timestamp("2026-01-01 12:00:00")
    alignment = AlignmentResult(
        is_aligned=True, hours_from_rosc_to_eeg=2.0,
        rosc_time=rosc, eeg_start=eeg_start, warning="",
    )
    time_info = TimeAxisInfo(reference="rosc", reference_time=rosc)
    info = build_alignment_info(time_info, alignment)
    assert info["time_reference"] == "rosc"
    assert info["is_aligned"] is True
    assert info["rosc_datetime"] == rosc.isoformat()
    assert info["hours_from_rosc_to_eeg"] == pytest.approx(2.0)
    assert info["has_pre_rosc_data"] is False


def test_build_alignment_info_pre_rosc_trim():
    rosc = pd.Timestamp("2026-01-01 10:00:00")
    eeg_start = pd.Timestamp("2026-01-01 09:30:00")  # EEG started 30 min before ROSC
    alignment = AlignmentResult(
        is_aligned=True, hours_from_rosc_to_eeg=-0.5,
        rosc_time=rosc, eeg_start=eeg_start,
        warning="EEG started 0.5h before ROSC — pre-ROSC data will be trimmed",
        has_pre_rosc_data=True, pre_rosc_hours=0.5,
    )
    info = build_alignment_info(
        TimeAxisInfo(reference="rosc", reference_time=rosc), alignment,
    )
    assert info["has_pre_rosc_data"] is True
    assert info["pre_rosc_hours"] == pytest.approx(0.5)
    assert "pre-ROSC" in info["alignment_warning"]


# ---------------------- provenance integration tests -----------------------


def test_build_provenance_includes_alignment_when_provided():
    align = build_alignment_info(
        TimeAxisInfo(reference="rosc", reference_time=pd.Timestamp("2026-01-01 10:00:00")),
        AlignmentResult(
            is_aligned=True, hours_from_rosc_to_eeg=1.5,
            rosc_time=pd.Timestamp("2026-01-01 10:00:00"),
            eeg_start=pd.Timestamp("2026-01-01 11:30:00"),
        ),
    )
    prov = build_provenance(config={}, alignment_info=align)
    assert "alignment" in prov
    assert prov["alignment"]["time_reference"] == "rosc"
    assert prov["alignment"]["is_aligned"] is True


def test_build_provenance_omits_alignment_when_none():
    prov = build_provenance(config={})
    assert "alignment" not in prov  # backward compatible


# ---------------------- research package round-trips -----------------------


def test_research_package_rosc_aligned():
    rosc = pd.Timestamp("2026-01-01 10:00:00")
    align = build_alignment_info(
        TimeAxisInfo(reference="rosc", reference_time=rosc),
        AlignmentResult(
            is_aligned=True, hours_from_rosc_to_eeg=2.0,
            rosc_time=rosc, eeg_start=pd.Timestamp("2026-01-01 12:00:00"),
        ),
    )
    buf = build_research_package(
        patient_id="P001",
        epochs=pd.DataFrame(),
        bin_summary=_fake_bin_summary(),
        schema=[],
        config={},
        qc_dict={"total_epochs": 21600, "usable_epochs": 20500, "seizure_epochs": 0},
        seizure_dict={"n_seizures": 0},
        alignment_info=align,
    )
    prov = _unzip_provenance(buf)
    assert prov["alignment"]["time_reference"] == "rosc"
    assert prov["alignment"]["rosc_datetime"] == rosc.isoformat()
    assert prov["alignment"]["is_aligned"] is True

    # semi-long still has bin_start_hours=0 for first bin (ROSC-anchored)
    semi = _unzip_semi_long(buf, "P001")
    assert "patient_id" in semi.columns
    assert (semi["patient_id"] == "P001").all()
    assert semi.loc[semi["time_bin"] == "0-6h", "bin_start_hours"].iloc[0] == 0.0


def test_research_package_no_rosc_is_recording_start():
    align = build_alignment_info(
        TimeAxisInfo(reference="recording_start", reference_time=pd.Timestamp("2026-01-01 00:00:00")),
        None,
    )
    buf = build_research_package(
        patient_id="P002",
        epochs=pd.DataFrame(),
        bin_summary=_fake_bin_summary(),
        schema=[],
        config={},
        qc_dict={"total_epochs": 21600, "usable_epochs": 20500, "seizure_epochs": 0},
        seizure_dict={"n_seizures": 0},
        alignment_info=align,
    )
    prov = _unzip_provenance(buf)
    assert prov["alignment"]["time_reference"] == "recording_start"
    assert prov["alignment"]["is_aligned"] is False
    assert prov["alignment"]["rosc_datetime"] is None


# -------------------------- cohort semi-long -------------------------------


class _FakeResult:
    """Minimal PatientResult stand-in for export_cohort_semi_long."""

    def __init__(self, bin_summary: pd.DataFrame, time_info, alignment):
        self.bin_summary = bin_summary
        self.time_info = time_info
        self.alignment = alignment
        self.schema = []


def test_cohort_semi_long_concatenates_with_patient_id_and_reference():
    rosc = pd.Timestamp("2026-01-01 10:00:00")
    r_aligned = _FakeResult(
        _fake_bin_summary(),
        TimeAxisInfo(reference="rosc", reference_time=rosc),
        AlignmentResult(
            is_aligned=True, hours_from_rosc_to_eeg=2.0,
            rosc_time=rosc, eeg_start=pd.Timestamp("2026-01-01 12:00:00"),
        ),
    )
    r_no_rosc = _FakeResult(
        _fake_bin_summary(),
        TimeAxisInfo(reference="recording_start", reference_time=pd.Timestamp("2026-01-01 00:00:00")),
        None,
    )
    df = export_cohort_semi_long(
        {"P001": r_aligned, "P002": r_no_rosc},
        col_map={},
        schema_by_patient={"P001": [], "P002": []},
    )
    assert list(df.columns)[0] == "patient_id"
    assert set(df["patient_id"].unique()) == {"P001", "P002"}
    assert (df.loc[df["patient_id"] == "P001", "time_reference"] == "rosc").all()
    assert (df.loc[df["patient_id"] == "P002", "time_reference"] == "recording_start").all()
    assert (df.loc[df["patient_id"] == "P001", "rosc_aligned"]).all()
    assert not (df.loc[df["patient_id"] == "P002", "rosc_aligned"]).any()
    # Only the non-no_data rows should appear — 2 rows per patient × 2 patients = 4
    assert len(df) == 4
