"""Tests for the DuckDB fast path in parse_persyst_csv()."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import qeeg.ingestion.sidecar as sidecar_mod


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    sidecar_dir = tmp_path / ".qeeg_cache" / "sidecars"
    parquet_dir = tmp_path / ".qeeg_cache" / "parquet"
    monkeypatch.setattr(sidecar_mod, "_SIDECAR_DIR", sidecar_dir)
    monkeypatch.setattr(sidecar_mod, "_PARQUET_DIR", parquet_dir)


@pytest.fixture
def converted_csv(synthetic_csv: Path):
    """Convert synthetic CSV to Parquet (ready state) and return the CSV path."""
    from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
    convert_csv_to_parquet(synthetic_csv)
    return synthetic_csv


class TestDuckDBFastPath:
    def test_parse_uses_duckdb_when_parquet_ready(self, converted_csv: Path, caplog):
        import logging
        from qeeg.ingestion.parser import parse_persyst_csv

        with caplog.at_level(logging.DEBUG, logger="qeeg.ingestion.parser"):
            parse_persyst_csv(converted_csv)

        assert any("DuckDB fast path" in r.message for r in caplog.records)

    def test_returns_correct_interface(self, converted_csv: Path):
        from qeeg.ingestion.parser import ParsedExport, parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert isinstance(result, ParsedExport)
        assert isinstance(result.data, pd.DataFrame)
        assert isinstance(result.code_to_description, dict)
        assert isinstance(result.description_to_codes, dict)

    def test_columns_identical_to_csv_path(self, synthetic_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv

        # Parse via CSV slow path before conversion exists
        csv_result = parse_persyst_csv(synthetic_csv)
        csv_cols = set(csv_result.data.columns)

        # Convert so Parquet is ready
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        convert_csv_to_parquet(synthetic_csv)

        # Second parse should use DuckDB
        pq_result = parse_persyst_csv(synthetic_csv)
        pq_cols = set(pq_result.data.columns)

        assert csv_cols == pq_cols

    def test_row_count_identical_to_csv_path(self, synthetic_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet

        csv_rows = len(parse_persyst_csv(synthetic_csv).data)
        convert_csv_to_parquet(synthetic_csv)
        pq_rows = len(parse_persyst_csv(synthetic_csv).data)

        assert csv_rows == pq_rows

    def test_code_to_description_preserved(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert "I1_1" in result.code_to_description
        assert result.code_to_description["I1_1"] == "Artifact Intensity"

    def test_description_to_codes_preserved(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert "Artifact Intensity" in result.description_to_codes
        assert "I1_1" in result.description_to_codes["Artifact Intensity"]

    def test_metadata_patient_id_preserved(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert result.metadata.patient_id == "SYNTH001"

    def test_metadata_test_date_preserved(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert result.metadata.test_date == "03/15/2025"

    def test_code_row_index_preserved(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert result.code_row_index >= 0

    def test_clockdatetime_is_datetime_type(self, converted_csv: Path):
        from qeeg.ingestion.parser import parse_persyst_csv
        result = parse_persyst_csv(converted_csv)
        assert "ClockDateTime" in result.data.columns
        assert pd.api.types.is_datetime64_any_dtype(result.data["ClockDateTime"])

    def test_falls_back_to_csv_when_parquet_deleted(self, converted_csv: Path):
        from qeeg.ingestion.sidecar import parquet_cache_path, read_sidecar
        from qeeg.ingestion.parser import parse_persyst_csv

        pq_path = parquet_cache_path(converted_csv)
        assert pq_path.exists()
        pq_path.unlink()

        # parse_persyst_csv must still succeed via the slow CSV path
        result = parse_persyst_csv(converted_csv)
        assert result is not None
        assert len(result.data) > 0

        # Sidecar should have been reset to pending
        sidecar = read_sidecar(converted_csv)
        assert sidecar is not None
        assert sidecar.parquet_status == "pending"


class TestLoadFromParquet:
    def test_direct_load_from_parquet(self, converted_csv: Path):
        from qeeg.ingestion.sidecar import parquet_cache_path, read_sidecar
        from qeeg.ingestion.duckdb_reader import load_from_parquet

        sidecar = read_sidecar(converted_csv)
        assert sidecar is not None and sidecar.phase == "full"

        pq_path = parquet_cache_path(converted_csv)
        result = load_from_parquet(pq_path, sidecar)

        assert isinstance(result.data, pd.DataFrame)
        assert len(result.data) == 50  # N_EPOCHS from conftest
        assert result.metadata.patient_id == "SYNTH001"
