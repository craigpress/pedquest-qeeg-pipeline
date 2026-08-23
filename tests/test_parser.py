"""Tests for qeeg.ingestion.parser — CSV parsing, header extraction, data shape."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qeeg.ingestion.parser import (
    ParsedExport,
    _extract_metadata,
    _fill_forward,
    _find_code_row,
    detect_encoding,
    parse_persyst_csv,
)


class TestDetectEncoding:
    def test_utf8_sig(self, synthetic_csv: Path):
        assert detect_encoding(synthetic_csv) == "utf-8-sig"

    def test_latin1_fallback(self, tmp_path: Path):
        p = tmp_path / "latin.csv"
        p.write_bytes(b"\xe9\n")  # é in latin-1, invalid utf-8
        enc = detect_encoding(p)
        assert enc in ("cp1252", "latin-1")


class TestFillForward:
    def test_basic(self):
        assert _fill_forward(["A", "", "", "B", ""]) == ["A", "A", "A", "B", "B"]

    def test_empty_input(self):
        assert _fill_forward([]) == []

    def test_all_empty(self):
        assert _fill_forward(["", "", ""]) == ["", "", ""]

    def test_strips_whitespace(self):
        assert _fill_forward(["  X  ", "", " Y "]) == ["X", "X", "Y"]


class TestExtractMetadata:
    def test_extracts_fields(self):
        rows = [
            ["File", "C:\\test.eeg"],
            ["PatientName", "John Doe"],
            ["PatientID", "P001"],
            ["PatientBirthDate", "01/01/2000"],
            ["TestDate", "03/15/2025"],
            ["TestTime", "10:00:00"],
        ]
        meta = _extract_metadata(rows)
        assert meta.file_path == "C:\\test.eeg"
        assert meta.patient_name == ""  # PHI stripped
        assert meta.patient_id == "P001"
        assert meta.test_date == "03/15/2025"
        assert meta.test_time == "10:00:00"

    def test_phi_stripped(self):
        rows = [["PatientName", "Sensitive Name"]]
        meta = _extract_metadata(rows)
        assert meta.patient_name == ""

    def test_case_insensitive_keys(self):
        rows = [["patientid", "ID123"]]
        meta = _extract_metadata(rows)
        assert meta.patient_id == "ID123"

    def test_missing_fields_default_empty(self):
        meta = _extract_metadata([])
        assert meta.patient_id == ""
        assert meta.file_path == ""


class TestFindCodeRow:
    def test_finds_correct_row(self):
        rows = [
            ["File", "test.eeg"],
            ["PatientID", "P001"],
            ["", "Trend A", "", "Trend B"],
            ["ClockDateTime", "I1_1", "I1_2", "I2_1"],
        ]
        assert _find_code_row(rows) == 3

    def test_returns_none_when_missing(self):
        rows = [
            ["File", "test.eeg"],
            ["no", "icodes", "here"],
        ]
        assert _find_code_row(rows) is None

    def test_requires_clockdatetime(self):
        rows = [
            ["I1_1", "I1_2", "I2_1"],  # I-codes but no ClockDateTime
        ]
        assert _find_code_row(rows) is None


class TestParsePersystCsv:
    def test_returns_parsed_export(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert isinstance(result, ParsedExport)

    def test_metadata_extraction(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert result.metadata.patient_id == "SYNTH001"
        assert result.metadata.test_date == "03/15/2025"
        assert result.metadata.test_time == "10:00:00"
        assert result.metadata.patient_name == ""  # PHI stripped

    def test_data_shape(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert result.data.shape[0] == 50  # 50 epochs
        assert result.data.shape[1] == 34  # ClockDateTime + 33 I-codes

    def test_code_row_indices(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert result.code_row_index == 7
        assert result.trend_row_index == 6

    def test_clockdatetime_converted(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert "ClockDateTime" in result.data.columns
        assert pd.api.types.is_datetime64_any_dtype(result.data["ClockDateTime"])

    def test_code_to_description_complete(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert len(result.code_to_description) == 33
        assert result.code_to_description["I1_1"] == "Artifact Intensity"
        assert result.code_to_description["I20_1"] == "aEEG Left Hemisphere"
        assert result.code_to_description["I121_1"] == "Seizure Probability P14"
        assert result.code_to_description["I200_1"] == "FFT Spectrogram Left Hemisphere"

    def test_description_to_codes_grouping(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert len(result.description_to_codes["Artifact Intensity"]) == 3
        assert len(result.description_to_codes["aEEG Left Hemisphere"]) == 5

    def test_fill_forward_works(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        # I1_2 and I1_3 should get "Artifact Intensity" from fill-forward
        assert result.code_to_description["I1_2"] == "Artifact Intensity"
        assert result.code_to_description["I1_3"] == "Artifact Intensity"

    def test_numeric_data(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        # I-code columns should be numeric
        assert pd.api.types.is_numeric_dtype(result.data["I1_1"])
        assert pd.api.types.is_numeric_dtype(result.data["I121_1"])

    def test_source_path_set(self, synthetic_csv: Path):
        result = parse_persyst_csv(synthetic_csv)
        assert result.metadata.source_path == str(synthetic_csv)

    def test_nonexistent_file_raises(self, tmp_path: Path):
        with pytest.raises(Exception):
            parse_persyst_csv(tmp_path / "nonexistent.csv")

    def test_invalid_csv_raises(self, tmp_path: Path):
        p = tmp_path / "bad.csv"
        p.write_text("just,some,random,data\nno,icodes,here,at all\n")
        with pytest.raises(ValueError, match="Could not find the code row"):
            parse_persyst_csv(p)
