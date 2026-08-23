from __future__ import annotations

from pathlib import Path

import pandas as pd

from qeeg.storage.parquet_io import load_epochs, parquet_bytes, save_epochs


def test_save_and_load_epochs_preserves_metadata_and_nullability(tmp_path: Path):
    df = pd.DataFrame(
        {
            "Raw Column (Hz)": [1.0, None, 3.5],
            "category": pd.Series(["a", None, "b"], dtype="string"),
            "flag": pd.Series([True, None, False], dtype="boolean"),
        }
    )
    path = tmp_path / "epochs.parquet"

    save_epochs(df, path, patient_id="P001")
    loaded = load_epochs(path)

    assert "Raw Column (Hz)" in loaded.columns
    assert loaded.attrs["patient_id"] == "P001"
    assert loaded.attrs["parquet_compression"] == "zstd"
    assert loaded.attrs["missing_value_policy"]["sentinel_codes_used"] is False
    assert loaded["Raw Column (Hz)"].isna().sum() == 1
    assert loaded["category"].isna().sum() == 1
    assert loaded["flag"].isna().sum() == 1


def test_parquet_bytes_produces_nonempty_payload():
    df = pd.DataFrame({"a": [1, 2, 3]})
    payload = parquet_bytes(df, patient_id="P002")
    assert isinstance(payload, bytes)
    assert len(payload) > 0
