"""Shared fixtures for qEEG pipeline tests.

The synthetic CSV fixture mimics a real Persyst CSV export with:
- 6 metadata rows (File, PatientName, PatientID, PatientBirthDate, TestDate, TestTime)
- 1 trend name row (fill-forward merged cells)
- 1 code row (I-codes + ClockDateTime)
- 50 data rows (epochs) with numeric values

Column families covered:
- Artifact Intensity (I1_1..I1_3)
- Artifact Detector (I2_1..I2_18)
- aEEG Left (I20_1..I20_5), aEEG Right (I21_1..I21_5)
- Seizure Probability (I121_1)
- Seizure Detection (I122_1)
- FFT Power (I10_1..I10_6) - 6 band×region combos
- FFT Spectrogram Left (I200_1..I200_5) - first 5 of 40 bins
- Suppression Ratio (I60_1..I60_2) - L/R
- Spike Density (I131_1)
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Excel serial date helpers (matching qeeg.ingestion.timestamps)
# ---------------------------------------------------------------------------
_EXCEL_EPOCH = datetime(1899, 12, 30)


def _to_excel_serial(dt: datetime) -> float:
    delta = dt - _EXCEL_EPOCH
    return delta.total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# Synthetic CSV builder
# ---------------------------------------------------------------------------

# Column definitions: (i_code, trend_name)
# Grouped by family — trend_name determines family classification
SYNTHETIC_COLUMNS = [
    # Artifact Intensity (3 BSS components)
    ("I1_1", "Artifact Intensity"),
    ("I1_2", "Artifact Intensity"),
    ("I1_3", "Artifact Intensity"),
    # Artifact Detector (first 4 of 18 electrodes — enough to test)
    ("I2_1", "Artifact Detector"),
    ("I2_2", "Artifact Detector"),
    ("I2_3", "Artifact Detector"),
    ("I2_4", "Artifact Detector"),
    # aEEG Left Hemisphere (5 sub-channels)
    ("I20_1", "aEEG Left Hemisphere"),
    ("I20_2", "aEEG Left Hemisphere"),
    ("I20_3", "aEEG Left Hemisphere"),
    ("I20_4", "aEEG Left Hemisphere"),
    ("I20_5", "aEEG Left Hemisphere"),
    # aEEG Right Hemisphere (5 sub-channels)
    ("I21_1", "aEEG Right Hemisphere"),
    ("I21_2", "aEEG Right Hemisphere"),
    ("I21_3", "aEEG Right Hemisphere"),
    ("I21_4", "aEEG Right Hemisphere"),
    ("I21_5", "aEEG Right Hemisphere"),
    # Seizure Probability
    ("I121_1", "Seizure Probability P14"),
    # Seizure Detection
    ("I122_1", "Seizure Detection P14"),
    # FFT Power — 6 combos of band × region
    ("I10_1", "FFT Power, 1 - 4 Hz Left Anterior F3C3"),
    ("I10_2", "FFT Power, 1 - 4 Hz Right Anterior F4C4"),
    ("I10_3", "FFT Power, 4 - 8 Hz Left Anterior F3C3"),
    ("I10_4", "FFT Power, 4 - 8 Hz Right Anterior F4C4"),
    ("I10_5", "FFT Power, 8 - 13 Hz Left Anterior F3C3"),
    ("I10_6", "FFT Power, 8 - 13 Hz Right Anterior F4C4"),
    # FFT Spectrogram Left Hemisphere (first 5 of 40 bins)
    ("I200_1", "FFT Spectrogram Left Hemisphere"),
    ("I200_2", "FFT Spectrogram Left Hemisphere"),
    ("I200_3", "FFT Spectrogram Left Hemisphere"),
    ("I200_4", "FFT Spectrogram Left Hemisphere"),
    ("I200_5", "FFT Spectrogram Left Hemisphere"),
    # Suppression Ratio L/R
    ("I60_1", "Suppression Ratio Left Hemisphere"),
    ("I60_2", "Suppression Ratio Right Hemisphere"),
    # Spike Density
    ("I131_1", "Spike Burst Bilateral"),
]

N_EPOCHS = 50
START_TIME = datetime(2025, 3, 15, 10, 0, 0)  # 10:00 AM
EPOCH_INTERVAL = timedelta(seconds=2)  # 2-second epochs


def _generate_synthetic_csv_content() -> str:
    """Generate a complete synthetic Persyst CSV as a string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # --- Metadata rows (6 rows) ---
    writer.writerow(["File", "C:\\Data\\SYNTH001_001.eeg"])
    writer.writerow(["PatientName", "Synthetic Patient"])
    writer.writerow(["PatientID", "SYNTH001"])
    writer.writerow(["PatientBirthDate", "01/01/2020"])
    writer.writerow(["TestDate", "03/15/2025"])
    writer.writerow(["TestTime", "10:00:00"])

    # --- Trend name row (row 6, 0-indexed) ---
    # Fill-forward: only write trend name at first column of each group
    trend_row = [""]  # ClockDateTime column has no trend name
    last_trend = ""
    for _code, trend_name in SYNTHETIC_COLUMNS:
        if trend_name != last_trend:
            trend_row.append(trend_name)
            last_trend = trend_name
        else:
            trend_row.append("")  # merged cell — empty
    writer.writerow(trend_row)

    # --- Code row (row 7, 0-indexed) ---
    code_row = ["ClockDateTime"] + [code for code, _trend in SYNTHETIC_COLUMNS]
    writer.writerow(code_row)

    # --- Data rows (50 epochs) ---
    rng = np.random.RandomState(42)
    for i in range(N_EPOCHS):
        dt = START_TIME + i * EPOCH_INTERVAL
        serial = _to_excel_serial(dt)

        row = [f"{serial:.10f}"]

        # Artifact Intensity: low values (0-10), with some high artifact epochs
        for _ in range(3):
            val = rng.exponential(2.0) if i % 10 != 0 else rng.uniform(15, 30)
            row.append(f"{val:.4f}")

        # Artifact Detector: binary-ish (0 or 1 per electrode)
        for _ in range(4):
            row.append(f"{rng.choice([0.0, 1.0]):.1f}")

        # aEEG Left (per CSV Format Reference §3.4: max, min, p50, p75, p25 — µV)
        aeeg_max_l = rng.uniform(10, 50)
        aeeg_min_l = rng.uniform(2, aeeg_max_l * 0.5)
        # synthesize plausible percentiles between min and max
        _p25_l = aeeg_min_l + (aeeg_max_l - aeeg_min_l) * 0.25
        _p50_l = aeeg_min_l + (aeeg_max_l - aeeg_min_l) * 0.5
        _p75_l = aeeg_min_l + (aeeg_max_l - aeeg_min_l) * 0.75
        row.append(f"{aeeg_max_l:.20f}")   # _1 max
        row.append(f"{aeeg_min_l:.20f}")   # _2 min
        row.append(f"{_p50_l:.20f}")       # _3 p50
        row.append(f"{_p75_l:.20f}")       # _4 p75
        row.append(f"{_p25_l:.20f}")       # _5 p25

        # aEEG Right (same structure)
        aeeg_max_r = rng.uniform(10, 50)
        aeeg_min_r = rng.uniform(2, aeeg_max_r * 0.5)
        _p25_r = aeeg_min_r + (aeeg_max_r - aeeg_min_r) * 0.25
        _p50_r = aeeg_min_r + (aeeg_max_r - aeeg_min_r) * 0.5
        _p75_r = aeeg_min_r + (aeeg_max_r - aeeg_min_r) * 0.75
        row.append(f"{aeeg_max_r:.20f}")
        row.append(f"{aeeg_min_r:.20f}")
        row.append(f"{_p50_r:.20f}")
        row.append(f"{_p75_r:.20f}")
        row.append(f"{_p25_r:.20f}")

        # Seizure probability (mostly 0, some elevated)
        seiz_prob = 0.0 if i % 15 != 0 else rng.uniform(0.3, 0.9)
        row.append(f"{seiz_prob:.4f}")

        # Seizure detection (binary: 1 where prob > 0.5)
        seiz_det = 1.0 if seiz_prob > 0.5 else 0.0
        row.append(f"{seiz_det:.1f}")

        # FFT Power (6 values, log-normal-ish)
        for _ in range(6):
            row.append(f"{rng.lognormal(2, 1):.4f}")

        # FFT Spectrogram Left (5 bins, positive values)
        for _ in range(5):
            row.append(f"{rng.exponential(5.0):.4f}")

        # Suppression Ratio L/R (0-1 range)
        row.append(f"{rng.uniform(0, 0.3):.4f}")
        row.append(f"{rng.uniform(0, 0.3):.4f}")

        # Spike Density (count per 10s, Poisson-like)
        row.append(f"{rng.poisson(1.5):.1f}")

        writer.writerow(row)

    return buf.getvalue()


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> Path:
    """Write a synthetic Persyst CSV to a temp file and return its path."""
    csv_path = tmp_path / "SYNTH001_1.csv"
    csv_path.write_text(_generate_synthetic_csv_content(), encoding="utf-8-sig")
    return csv_path


@pytest.fixture
def synthetic_csv_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Two synthetic CSVs for testing multi-file concatenation."""
    content = _generate_synthetic_csv_content()
    p1 = tmp_path / "SYNTH001_1.csv"
    p2 = tmp_path / "SYNTH001_2.csv"
    p1.write_text(content, encoding="utf-8-sig")
    # Second file: same structure, different random data
    p2.write_text(
        _generate_synthetic_csv_content(),  # same seed = same data (ok for structure test)
        encoding="utf-8-sig",
    )
    return p1, p2


@pytest.fixture
def default_config():
    """Default PipelineConfig for testing."""
    from qeeg.config import PipelineConfig
    return PipelineConfig()


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Temp directory for cache tests."""
    d = tmp_path / ".qeeg_cache"
    d.mkdir()
    return d


@pytest.fixture
def parsed_export(synthetic_csv):
    """Pre-parsed synthetic CSV for tests that don't need to test parsing."""
    from qeeg.ingestion.parser import parse_persyst_csv
    return parse_persyst_csv(synthetic_csv)


@pytest.fixture
def column_schema(parsed_export):
    """Column schema built from synthetic CSV."""
    from qeeg.ingestion.column_mapper import build_column_schema
    return build_column_schema(parsed_export.code_to_description)
