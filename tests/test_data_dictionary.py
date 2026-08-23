"""Tests for enhanced data dictionary and chart metadata (WS2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qeeg.storage.export import build_data_dictionary, build_chart_metadata


# -- Data dictionary tests --


class TestDataDictionaryNewFields:
    """Every dictionary entry must include the 6 new WS2 fields."""

    REQUIRED_KEYS = {
        "persyst_engine",
        "cadence_seconds",
        "window_seconds",
        "n_observed_definition",
        "n_effective_definition",
        "category_code_map",
        "allowed_values",
    }

    def test_framework_entries_have_new_fields(self):
        """Hard-coded framework entries have all 6 new keys."""
        entries = build_data_dictionary()
        for entry in entries:
            for key in self.REQUIRED_KEYS:
                assert key in entry, (
                    f"Entry '{entry['variable_name']}' missing '{key}'"
                )

    def test_schema_entries_have_new_fields(self, synthetic_csv: Path):
        """Schema-derived entries from a real parse have all 6 new keys."""
        from qeeg.pipeline import process_patient
        result = process_patient(synthetic_csv)
        entries = build_data_dictionary(result.schema)
        schema_entries = [e for e in entries if e.get("original_code")]
        assert len(schema_entries) > 0, "Should have schema-derived entries"
        for entry in schema_entries:
            for key in self.REQUIRED_KEYS:
                assert key in entry, (
                    f"Schema entry '{entry['variable_name']}' missing '{key}'"
                )

    def test_framework_categoricals_have_code_map(self):
        """Categorical framework entries have non-empty category_code_map."""
        entries = build_data_dictionary()
        categoricals = [e for e in entries if e["is_categorical"] and e["categories"]]
        assert len(categoricals) >= 5, "Expected missingness_flag, n_effective_basis, meets_minimum, has_status_epilepticus, status_epilepticus_screen_flag"
        for entry in categoricals:
            assert isinstance(entry["category_code_map"], dict)
            assert len(entry["category_code_map"]) > 0, (
                f"'{entry['variable_name']}' should have non-empty category_code_map"
            )
            assert isinstance(entry["allowed_values"], list)
            assert len(entry["allowed_values"]) > 0

    def test_non_categorical_entries_have_empty_code_map(self):
        """Non-categorical entries have empty category_code_map and None allowed_values."""
        entries = build_data_dictionary()
        numerics = [e for e in entries if not e["is_categorical"]]
        assert len(numerics) > 0
        for entry in numerics:
            assert entry["category_code_map"] == {}
            assert entry["allowed_values"] is None

    def test_eeg_families_have_cadence_and_window(self, synthetic_csv: Path):
        """Schema entries from EEG families have non-null cadence/window."""
        from qeeg.pipeline import process_patient
        result = process_patient(synthetic_csv)
        entries = build_data_dictionary(result.schema)
        schema_entries = [e for e in entries if e.get("original_code")]
        for entry in schema_entries:
            assert entry["cadence_seconds"] is not None, (
                f"'{entry['variable_name']}' (family={entry['family']}) should have cadence_seconds"
            )
            assert entry["window_seconds"] is not None
            assert isinstance(entry["cadence_seconds"], int)
            assert isinstance(entry["window_seconds"], float)

    def test_framework_non_eeg_have_null_timing(self):
        """Framework entries (identifier, time, export, etc.) have null cadence/window."""
        entries = build_data_dictionary()
        for entry in entries:
            if entry["family"] in ("identifier", "time", "export", "time_binning", "seizure"):
                assert entry["cadence_seconds"] is None, (
                    f"'{entry['variable_name']}' (framework) should have null cadence"
                )
                assert entry["window_seconds"] is None

    def test_fft_entries_have_cadence_adjusted_definition(self, synthetic_csv: Path):
        """FFT-family entries report cadence-adjusted n_effective definition."""
        from qeeg.pipeline import process_patient
        result = process_patient(synthetic_csv)
        entries = build_data_dictionary(result.schema)
        fft_entries = [
            e for e in entries
            if e.get("variable_name", "").startswith(("fft_", "adr_", "rav_"))
        ]
        assert len(fft_entries) > 0, "Should have FFT entries in synthetic data"
        for entry in fft_entries:
            assert "Cadence-adjusted" in entry["n_effective_definition"]
            assert entry["cadence_seconds"] == 8  # FFT default

    def test_slow_non_fft_entries_have_cadence_adjusted_definition(self):
        """Slow non-FFT engines such as suppression also report engine-adjusted effective N."""
        from qeeg.ingestion.mmx_parser import EngineConfig
        from qeeg.ingestion.column_mapper import ColumnEntry

        schema = [
            ColumnEntry(
                col_index=0,
                code="suppression_left",
                i_group=1,
                sub_index=1,
                trend_name="BSR Left",
                family="suppression_ratio",
                frequency_band="",
                freq_min_hz=None,
                freq_max_hz=None,
                hemisphere="left",
                region="hemisphere",
                electrode="",
                common_name="suppression_left",
            )
        ]
        engines = {
            "Amplitude01": EngineConfig(
                name="Amplitude01",
                epoch_duration=10.0,
                epoch_step=10.0,
            )
        }
        entries = build_data_dictionary(schema, engines=engines)
        suppression = next(e for e in entries if e["variable_name"] == "suppression_left")
        assert suppression["persyst_engine"] == "Amplitude01"
        assert suppression["cadence_seconds"] == 10
        assert suppression["window_seconds"] == 10.0
        assert "suppression_ratio_cadence_adjusted" in suppression["n_effective_definition"]

    def test_missingness_flag_code_map_matches_categories(self):
        """missingness_flag category_code_map has all 5 coverage levels."""
        entries = build_data_dictionary()
        mf = next(e for e in entries if e["variable_name"] == "missingness_flag")
        assert len(mf["category_code_map"]) == 5
        assert "complete" in mf["category_code_map"]
        assert "no_data" in mf["category_code_map"]
        assert mf["allowed_values"] == [c["code"] for c in mf["categories"]]

    def test_n_effective_basis_values_include_engine_specific_labels(self):
        entries = build_data_dictionary()
        basis = next(e for e in entries if e["variable_name"] == "n_effective_basis")
        allowed = set(basis["allowed_values"])
        assert "row_count" in allowed
        assert "fft_power_cadence_adjusted" in allowed
        assert "suppression_ratio_cadence_adjusted" in allowed
        assert "rhythmicity_cadence_adjusted" in allowed

    def test_persyst_families_have_units(self, synthetic_csv: Path):
        """Every schema-derived Persyst column must have a non-empty unit string."""
        from qeeg.pipeline import process_patient
        from qeeg.ingestion.cadence import FAMILY_ENGINE_MAP
        result = process_patient(synthetic_csv)
        entries = build_data_dictionary(result.schema)
        schema_entries = [e for e in entries if e.get("original_code")]
        assert len(schema_entries) > 0
        for entry in schema_entries:
            if entry["family"] in FAMILY_ENGINE_MAP:
                assert entry["unit"], (
                    f"Schema entry '{entry['variable_name']}' (family={entry['family']}) "
                    f"has empty unit"
                )

    def test_derived_features_have_dictionary_entries(self):
        """Each pipeline-derived feature family has a dictionary row per region."""
        entries = build_data_dictionary()
        names = {e["variable_name"] for e in entries}
        for region in ("anterior", "posterior"):
            assert f"total_power_{region}" in names
            for band in ("delta", "theta", "alpha", "beta"):
                assert f"fft_{band}_{region}" in names
                assert f"fft_{band}_{region}_sides_contributing" in names
                assert f"rel_{band}_{region}" in names
            for rb in ("theta", "alpha"):
                assert f"{rb}_delta_ratio_{region}" in names
                assert f"log_{rb}_delta_ratio_{region}" in names

    def test_derived_features_inherit_fft_cadence(self):
        """Derived features inherit FFTEngine01 cadence/window."""
        entries = build_data_dictionary()
        total = next(e for e in entries if e["variable_name"] == "total_power_anterior")
        assert total["persyst_engine"] == "FFTEngine01"
        assert total["cadence_seconds"] == 8
        assert total["window_seconds"] == 4.0
        # FFT power units follow the MMX PowerType setting, which the V10
        # template sets to 1 = µV (amplitude). This assertion previously required
        # "µV²" and so encoded the bug: the export was labelling 54 amplitude
        # columns as squared power. Confirmed against the Persyst Power Scale
        # selector (enum 0=µV², 1=µV, 2=dB, 3=sqrt(µV)) and Persyst (Mike),
        # 2026-08-20/21. Assert the physical prefix, and that it is NOT squared.
        assert total["unit"].startswith("µV")
        assert not total["unit"].startswith("µV²")

    def test_sides_contributing_is_categorical_with_three_codes(self):
        """sides_contributing has codes 0, 1, 2 with labels."""
        entries = build_data_dictionary()
        sc = next(e for e in entries if e["variable_name"] == "fft_delta_anterior_sides_contributing")
        assert sc["is_categorical"]
        assert set(sc["allowed_values"]) == {0, 1, 2}
        assert sc["category_code_map"][1].startswith("One hemisphere")

    def test_seizure_burden_hours_in_dictionary(self):
        entries = build_data_dictionary()
        entry = next(e for e in entries if e["variable_name"] == "seizure_burden_hours")
        assert entry["unit"] == "hours"
        assert entry["family"] == "seizure"
        assert entry["cadence_seconds"] is None

    def test_n_effective_cadence_adjusted_in_dictionary(self):
        entries = build_data_dictionary()
        entry = next(e for e in entries if e["variable_name"] == "n_effective_cadence_adjusted")
        assert entry["unit"] == "observations"
        assert entry["family"] == "time_binning"

    def test_trend_engine_reference_matches_cadence_module(self):
        """Human documentation must stay aligned with the code's engine table."""
        from qeeg.ingestion.cadence import (
            FAMILY_ENGINE_MAP,
            get_family_cadence,
            get_engine_window,
            get_family_effective_basis,
        )

        doc = Path("docs/TREND_ENGINE_REFERENCE.md").read_text(encoding="utf-8")
        rows = {}
        for line in doc.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 6:
                continue
            family = cells[0].strip("`")
            rows[family] = {
                "engine": cells[2].strip("`"),
                "window": float(cells[3]),
                "step": int(cells[4]),
                "basis": cells[5].strip("`"),
            }

        assert set(rows) == set(FAMILY_ENGINE_MAP)
        for family, engine_name in FAMILY_ENGINE_MAP.items():
            assert rows[family]["engine"] == engine_name
            assert rows[family]["window"] == get_engine_window(family)
            assert rows[family]["step"] == get_family_cadence(family)
            assert rows[family]["basis"] == get_family_effective_basis(family)


# -- Chart metadata tests --


class TestChartMetadata:
    """build_chart_metadata returns panel metadata for all dashboard panels."""

    ALL_PANEL_IDS = {
        "artifact_intensity", "seizure_probability", "aeeg",
        "fft_spectrogram_left", "fft_spectrogram_right",
        "coherence_spectrogram", "rhythmicity_spectrogram", "reasi",
        "band_power_anterior", "band_power_posterior",
        "adr_hemisphere", "adr_tdr_anterior", "adr_tdr_posterior",
        "suppression_ratio", "spike_density",
        "asymmetry_spectrogram_ant", "asymmetry_spectrogram_post",
        "asymmetry_spectrogram_hemi", "asymmetry_spectrogram_temp",
        "asymmetry_spectrogram_parasag",
    }

    def test_all_panels_returned(self):
        """All 20 dashboard panel IDs are present."""
        panels = build_chart_metadata()
        returned_ids = {p["panel_id"] for p in panels}
        assert returned_ids == self.ALL_PANEL_IDS

    def test_panel_fields_complete(self):
        """Each panel has all required fields."""
        required = {
            "panel_id", "display_name", "description", "source_families",
            "variables", "units", "derivation", "cadence_seconds",
            "window_seconds", "filtering",
        }
        panels = build_chart_metadata()
        for panel in panels:
            for key in required:
                assert key in panel, f"Panel '{panel['panel_id']}' missing '{key}'"

    def test_panels_have_variables_with_schema(self, synthetic_csv: Path):
        """With a real schema, at least some panels have matched variables."""
        from qeeg.pipeline import process_patient
        result = process_patient(synthetic_csv)
        panels = build_chart_metadata(result.schema)
        panels_with_vars = [p for p in panels if p["variables"]]
        assert len(panels_with_vars) > 0, "At least some panels should have matched variables"

    def test_band_power_anterior_filters_region(self, synthetic_csv: Path):
        """band_power_anterior only includes anterior-region variables."""
        from qeeg.pipeline import process_patient
        result = process_patient(synthetic_csv)
        panels = build_chart_metadata(result.schema)
        bp_ant = next(p for p in panels if p["panel_id"] == "band_power_anterior")
        for var in bp_ant["variables"]:
            assert "anterior" in var, f"Expected 'anterior' in variable name: {var}"

    def test_cadence_seconds_matches_primary_family(self):
        """Panel cadence_seconds reflects the primary source family."""
        panels = build_chart_metadata()
        fft_panel = next(p for p in panels if p["panel_id"] == "band_power_anterior")
        assert fft_panel["cadence_seconds"] == 8  # FFT default
        supp_panel = next(p for p in panels if p["panel_id"] == "suppression_ratio")
        assert supp_panel["cadence_seconds"] == 10  # Amplitude01 default
        sz_panel = next(p for p in panels if p["panel_id"] == "seizure_probability")
        assert sz_panel["cadence_seconds"] == 1

    def test_without_schema_variables_empty(self):
        """Without schema, panels have empty variable lists."""
        panels = build_chart_metadata()
        for panel in panels:
            assert panel["variables"] == []
