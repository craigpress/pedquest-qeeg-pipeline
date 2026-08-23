"""Tests for multi-panel CSV classification and grouping."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from qeeg.ingestion.quick_scan import _classify_panel, quick_scan
from qeeg.ingestion.patient_grouper import group_files_by_patient

_EXCEL_EPOCH = datetime(1899, 12, 30)


def _to_serial(dt: datetime) -> float:
    return (dt - _EXCEL_EPOCH).total_seconds() / 86400.0


def _write_persyst_csv(
    path: Path,
    columns: list[tuple[str, str]],  # (icode, trend_name)
    n_rows: int = 5,
    patient_id: str = "TEST001",
    start: datetime | None = None,
) -> Path:
    """Write a minimal valid Persyst CSV with the given column definitions."""
    if start is None:
        start = datetime(2025, 3, 15, 10, 0, 0)

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")

    w.writerow(["File", "C:\\Data\\TEST.eeg"])
    w.writerow(["PatientName", "Test Patient"])
    w.writerow(["PatientID", patient_id])
    w.writerow(["PatientBirthDate", "01/01/2015"])
    w.writerow(["TestDate", "03/15/2025"])
    w.writerow(["TestTime", "10:00:00"])

    # Trend name row (fill-forward style)
    trend_row = [""]
    last = ""
    for _, trend in columns:
        if trend != last:
            trend_row.append(trend)
            last = trend
        else:
            trend_row.append("")
    w.writerow(trend_row)

    # Code row
    w.writerow(["ClockDateTime"] + [code for code, _ in columns])

    # Data rows
    for i in range(n_rows):
        dt = start + timedelta(seconds=2 * i)
        row = [f"{_to_serial(dt):.10f}"] + ["1.0"] * len(columns)
        w.writerow(row)

    path.write_text(buf.getvalue(), encoding="utf-8-sig")
    return path


# ---------------------------------------------------------------------------
# a) _classify_panel unit tests
# ---------------------------------------------------------------------------

def test_classify_panel_spectrograms():
    names = [
        "FFT Spectrogram Left Hemisphere",
        "FFT Spectrogram Left Hemisphere",
        "FFT Spectrogram Right Hemisphere",
        "FFT Spectrogram Right Hemisphere",
        "Rhythmicity Spectrogram Left Hemisphere",
    ]
    assert _classify_panel(names) == "spectrograms"


def test_classify_panel_time_averages():
    names = [
        "Time Avg <0,120> [Left Hemisphere]",
        "Time Avg <0,240> [Right Hemisphere]",
        "Time Avg <0,120> [Left Posterior]",
        "Time Avg <0,240> [Right Posterior]",
        "Time Avg <0,480> [Global]",
    ]
    assert _classify_panel(names) == "time_averages"


def test_classify_panel_trends_mixed():
    names = [
        "FFT Power, 1 - 4 Hz Left Anterior F3C3",
        "FFT Power, 4 - 8 Hz Right Anterior F4C4",
        "BSR Left Hemisphere",
        "Coherence_Avg 0-32 C3*C4",
        "Artifact Intensity",
    ]
    assert _classify_panel(names) == "trends"


def test_classify_panel_below_spectrogram_threshold():
    # 40% spectrogram — should NOT trigger the 50% threshold
    names = [
        "FFT Spectrogram Left Hemisphere",
        "FFT Spectrogram Right Hemisphere",
        "FFT Power, 1 - 4 Hz Left",
        "BSR Left Hemisphere",
        "Suppression Ratio Left Hemisphere",
    ]
    assert _classify_panel(names) == "trends"


def test_classify_panel_empty():
    assert _classify_panel([]) == "trends"


def test_classify_panel_coherence_only():
    names = [
        "Coherence_Avg 0-32 C3*C4",
        "Coherence_Avg 0-32 F3*F4",
        "Coherence Avg 8-13 Hz Left",
    ]
    assert _classify_panel(names) == "coherence_only"


# ---------------------------------------------------------------------------
# b) group_files_by_patient with 4 panel types
# ---------------------------------------------------------------------------

def test_group_files_all_panel_types(tmp_path: Path):
    trend_cols = [
        ("I10_1", "FFT Power, 1 - 4 Hz Left"),
        ("I10_2", "FFT Power, 4 - 8 Hz Left"),
        ("I60_1", "Suppression Ratio Left Hemisphere"),
    ]
    spec_cols = [
        ("I200_1", "FFT Spectrogram Left Hemisphere"),
        ("I200_2", "FFT Spectrogram Left Hemisphere"),
        ("I200_3", "FFT Spectrogram Left Hemisphere"),
        ("I200_4", "FFT Spectrogram Left Hemisphere"),
        ("I200_5", "FFT Spectrogram Left Hemisphere"),
    ]
    tavg_cols = [
        ("I10_1", "Time Avg <0,120> [Left Anterior F3C3]"),
        ("I10_2", "Time Avg <0,240> [Right Anterior F4C4]"),
        ("I10_3", "Time Avg <0,120> [Left Posterior C3P3]"),
        ("I10_4", "Time Avg <0,240> [Right Posterior C4P4]"),
        ("I10_5", "Time Avg <0,480> [Global]"),
    ]

    p_trend = _write_persyst_csv(tmp_path / "TEST001_1.csv", trend_cols, patient_id="TEST001")
    p_spec = _write_persyst_csv(tmp_path / "TEST001_2.csv", spec_cols, patient_id="TEST001")
    p_tavg = _write_persyst_csv(tmp_path / "TEST001_3.csv", tavg_cols, patient_id="TEST001")

    groups = group_files_by_patient([p_trend, p_spec, p_tavg])
    assert "TEST001" in groups
    g = groups["TEST001"]

    assert len(g.trend_files) == 1
    assert len(g.spectrogram_files) == 1
    assert len(g.time_average_files) == 1
    assert len(g.other_files) == 0
    assert len(g.files) == 3

    # Duration and epoch count from trend files only
    assert g.total_epochs == 5  # only trend file's 5 rows
    assert g.total_duration_hours > 0  # trend file has a valid duration


def test_group_files_trend_only(tmp_path: Path):
    trend_cols = [
        ("I10_1", "FFT Power, 1 - 4 Hz Left"),
        ("I60_1", "Suppression Ratio Left Hemisphere"),
    ]
    p = _write_persyst_csv(tmp_path / "TEST002_1.csv", trend_cols, patient_id="TEST002")
    groups = group_files_by_patient([p])
    g = groups["TEST002"]
    assert len(g.trend_files) == 1
    assert len(g.spectrogram_files) == 0
    assert len(g.time_average_files) == 0


# ---------------------------------------------------------------------------
# c) Integration: empty trend_files when only spectrogram CSV is present
# ---------------------------------------------------------------------------

def test_spectrogram_only_group_has_empty_trend_files(tmp_path: Path):
    spec_cols = [
        ("I200_1", "FFT Spectrogram Left Hemisphere"),
        ("I200_2", "FFT Spectrogram Left Hemisphere"),
        ("I200_3", "FFT Spectrogram Left Hemisphere"),
        ("I200_4", "FFT Spectrogram Left Hemisphere"),
        ("I200_5", "FFT Spectrogram Left Hemisphere"),
    ]
    p = _write_persyst_csv(tmp_path / "TEST003_1.csv", spec_cols, patient_id="TEST003")
    groups = group_files_by_patient([p])
    g = groups["TEST003"]
    assert g.trend_files == []
    assert len(g.spectrogram_files) == 1
    assert g.total_epochs == 0
    assert g.total_duration_hours == 0.0


def test_trends_csv_processes_normally(tmp_path: Path, synthetic_csv: Path):
    """Existing trend CSV must still work after grouper refactor (no regression)."""
    groups = group_files_by_patient([synthetic_csv])
    pid = list(groups.keys())[0]
    g = groups[pid]
    assert len(g.trend_files) == 1
    assert g.total_epochs > 0


# ---------------------------------------------------------------------------
# d) quick_scan detects spectrogram panel type from synthetic CSV
# ---------------------------------------------------------------------------

def test_quick_scan_spectrogram_panel(tmp_path: Path):
    spec_cols = [
        ("I200_1", "FFT Spectrogram Left Hemisphere"),
        ("I200_2", "FFT Spectrogram Left Hemisphere"),
        ("I200_3", "FFT Spectrogram Left Hemisphere"),
        ("I200_4", "FFT Spectrogram Left Hemisphere"),
        ("I200_5", "FFT Spectrogram Left Hemisphere"),
        ("I201_1", "Rhythmicity Spectrogram Left Hemisphere"),
        ("I201_2", "Rhythmicity Spectrogram Left Hemisphere"),
        ("I201_3", "Rhythmicity Spectrogram Left Hemisphere"),
    ]
    p = _write_persyst_csv(tmp_path / "spec.csv", spec_cols)
    result = quick_scan(p)
    assert result.csv_panel_type == "spectrograms"


def test_quick_scan_trend_panel(tmp_path: Path, synthetic_csv: Path):
    result = quick_scan(synthetic_csv)
    assert result.csv_panel_type == "trends"


def test_quick_scan_time_averages_panel(tmp_path: Path):
    tavg_cols = [
        ("I10_1", "Time Avg <0,120> [Left Anterior F3C3]"),
        ("I10_2", "Time Avg <0,240> [Right Anterior F4C4]"),
        ("I10_3", "Time Avg <0,120> [Left Posterior C3P3]"),
        ("I10_4", "Time Avg <0,240> [Right Posterior C4P4]"),
        ("I10_5", "Time Avg <0,480> [Global]"),
    ]
    p = _write_persyst_csv(tmp_path / "tavg.csv", tavg_cols)
    result = quick_scan(p)
    assert result.csv_panel_type == "time_averages"
