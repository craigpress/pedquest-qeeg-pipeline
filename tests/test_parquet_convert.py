"""Tests for qeeg.ingestion.parquet_convert — CSV→Parquet conversion."""
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


class TestConvertCsvToParquet:
    def test_produces_parquet_file(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        out = convert_csv_to_parquet(synthetic_csv)
        assert out.exists()
        assert out.suffix == ".parquet"

    def test_columns_match_csv_parse(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        from qeeg.ingestion.parser import parse_persyst_csv

        out = convert_csv_to_parquet(synthetic_csv)
        df_pq = pd.read_parquet(out)
        df_csv = parse_persyst_csv(synthetic_csv).data

        assert set(df_pq.columns) == set(df_csv.columns)

    def test_row_count_matches(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        from qeeg.ingestion.parser import parse_persyst_csv

        out = convert_csv_to_parquet(synthetic_csv)
        df_pq = pd.read_parquet(out)
        df_csv = parse_persyst_csv(synthetic_csv).data
        assert len(df_pq) == len(df_csv)

    def test_clockdatetime_stored_as_timestamps(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet

        out = convert_csv_to_parquet(synthetic_csv)
        df_pq = pd.read_parquet(out)
        assert "ClockDateTime" in df_pq.columns
        # Should be datetime, not raw float serial
        assert pd.api.types.is_datetime64_any_dtype(df_pq["ClockDateTime"])

    def test_sidecar_updated_to_ready(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        from qeeg.ingestion.sidecar import read_sidecar

        convert_csv_to_parquet(synthetic_csv)
        sidecar = read_sidecar(synthetic_csv)
        assert sidecar is not None
        assert sidecar.parquet_status == "ready"
        assert sidecar.parquet_path != ""
        assert Path(sidecar.parquet_path).exists()

    def test_sidecar_phase_is_full_after_conversion(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        from qeeg.ingestion.sidecar import read_sidecar

        convert_csv_to_parquet(synthetic_csv)
        sidecar = read_sidecar(synthetic_csv)
        assert sidecar is not None
        assert sidecar.phase == "full"
        assert sidecar.code_row_index >= 0
        assert sidecar.code_to_description  # non-empty

    def test_compression_is_zstd(self, synthetic_csv: Path):
        import pyarrow.parquet as pq

        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet

        out = convert_csv_to_parquet(synthetic_csv)
        meta = pq.read_metadata(out)
        for rg in range(meta.num_row_groups):
            for col in range(meta.num_columns):
                cc = meta.row_group(rg).column(col)
                assert cc.compression == "ZSTD"

    def test_idempotent(self, synthetic_csv: Path):
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet

        out1 = convert_csv_to_parquet(synthetic_csv)
        out2 = convert_csv_to_parquet(synthetic_csv)
        assert out1 == out2
        assert out1.exists()

    def test_utf8_sig_encoding_preserved(self, synthetic_csv: Path):
        """The synthetic CSV is utf-8-sig — conversion must handle it correctly."""
        from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
        from qeeg.ingestion.sidecar import read_sidecar

        convert_csv_to_parquet(synthetic_csv)
        sidecar = read_sidecar(synthetic_csv)
        assert sidecar is not None
        assert sidecar.encoding == "utf-8-sig"
