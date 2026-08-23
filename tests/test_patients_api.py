"""C.4 — spectrogram endpoint must enforce fft_spectrogram family literally.

If a patient's schema has NO fft_spectrogram columns, requesting fft_left or
fft_right must return empty (no frequencies, no hours, no matrix) — never
leak asymmetry or fft_power data through.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from api.services.pipeline_service import PipelineService
from qeeg.ingestion.column_mapper import ColumnEntry


def _stub_result_no_fft_spectrogram():
    """Build a minimal PatientResult-shaped object whose schema has asymmetry
    and fft_power entries but no fft_spectrogram columns at all.
    """
    schema = [
        # fft_power (different family — should NEVER satisfy an fft_left request)
        ColumnEntry(
            col_index=1, code="I10_1", i_group=10, sub_index=1,
            trend_name="FFT Power, 1 - 4 Hz Left Anterior F3C3",
            family="fft_power",
            frequency_band="delta", freq_min_hz=1.0, freq_max_hz=4.0,
            hemisphere="left", region="anterior", electrode="F3C3",
        ),
        # asymmetry spectrogram (also wrong family for fft_left)
        ColumnEntry(
            col_index=2, code="I300_1", i_group=300, sub_index=1,
            trend_name="Asymmetry Spectrogram Hemisphere",
            family="asymmetry",
            frequency_band="", freq_min_hz=None, freq_max_hz=None,
            hemisphere="", region="hemisphere", electrode="",
        ),
    ]
    df = pd.DataFrame({
        "_hours_relative": [0.0, 1.0, 2.0],
        "I10_1": [1.0, 2.0, 3.0],
        "I300_1": [0.5, 0.6, 0.7],
    })
    return SimpleNamespace(epochs=df, schema=schema)


@pytest.fixture
def service(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return PipelineService(upload_dir=upload_dir)


def test_fft_left_returns_empty_when_no_fft_spectrogram(service):
    result = _stub_result_no_fft_spectrogram()
    frequencies, hours, matrix = service.get_spectrogram_data(result, "fft_left")
    assert frequencies == []
    assert hours == []
    assert matrix == []


def test_fft_right_returns_empty_when_no_fft_spectrogram(service):
    result = _stub_result_no_fft_spectrogram()
    frequencies, hours, matrix = service.get_spectrogram_data(result, "fft_right")
    assert frequencies == []
    assert hours == []
    assert matrix == []


def test_fft_left_works_when_fft_spectrogram_present(service):
    """Sanity check: adding a proper fft_spectrogram entry makes fft_left work."""
    base = _stub_result_no_fft_spectrogram()
    schema = list(base.schema) + [
        ColumnEntry(
            col_index=3, code="I200_1", i_group=200, sub_index=1,
            trend_name="FFT Spectrogram Left Hemisphere",
            family="fft_spectrogram",
            frequency_band="", freq_min_hz=None, freq_max_hz=None,
            hemisphere="left", region="hemisphere", electrode="",
        ),
    ]
    df = base.epochs.copy()
    df["I200_1"] = [1.0, 2.0, 3.0]
    result = SimpleNamespace(epochs=df, schema=schema)

    frequencies, hours, matrix = service.get_spectrogram_data(result, "fft_left")
    assert len(frequencies) == 1
    assert hours == [0.0, 1.0, 2.0]
    assert matrix == [[1.0, 2.0, 3.0]]
