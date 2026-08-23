"""Tests for qeeg.ingestion.column_mapper — family classification, naming, schema."""

from __future__ import annotations

import pytest

from qeeg.ingestion.column_mapper import (
    ColumnEntry,
    build_column_schema,
    classify_family,
    extract_electrode,
    extract_frequency_range,
    extract_hemisphere,
    extract_region,
    generate_common_name,
    get_columns_by_family,
    get_fft_power_columns,
    get_subcolumn_name,
    map_to_band,
)


class TestClassifyFamily:
    """classify_family() matches trend names to feature families via regex."""

    @pytest.mark.parametrize(
        "trend_name, expected_family",
        [
            ("Artifact Intensity", "artifact_intensity"),
            ("Artifact Detector", "artifact_detector"),
            ("Electrode Signal Quality", "electrode_quality"),
            ("FFT Power, 1 - 4 Hz Left Anterior F3C3", "fft_power"),
            # Power ratios classify by denominator (see classify_ratio):
            ("FFT PowerRatio, 8-13/1-4 Hz Left Anterior", "adr"),          # ADR
            ("FFT PowerRatio, 4-8/1-4 Hz Left Anterior", "adr"),           # TDR (adr family)
            ("FFT PowerRatio, 6-14/1-20 Hz Left Anterior", "alpha_variability"),  # RAV
            ("FFT PowerRatio, 8-13/1-30 Hz Anterior", "relative_power"),   # rel alpha
            ("FFT PowerRatio, 1-4/1-30 Hz Posterior", "relative_power"),   # rel delta
            ("FFT Spectrogram Left Hemisphere", "fft_spectrogram"),
            ("aEEG Left Hemisphere", "aeeg"),
            ("Seizure Probability P14", "seizure_probability"),
            ("Seizure Detection P14", "seizure_detection"),
            ("Suppression Ratio Left Hemisphere", "suppression_ratio"),
            ("Spike Burst Bilateral", "spike_density"),
            ("Rhythmic delta indicator (blue), Left", "rda"),
            ("Rhythmicity Spectrogram Left Hemisphere", "rhythmicity"),
            ("Asymmetry Spectrogram Asym Hemi", "asymmetry"),
            ("Coherence Spectrogram F3C3 F4C4", "coherence_spectrogram"),
            ("Sleep Stage", "sleep"),
            ("Boolean LAD+", "rhythmic_delta"),
            ("Heart Rate", "heart_rate"),
            ("PeakEnvelope Left Hemisphere", "peak_envelope"),
            ("SEF95 Left Hemisphere", "spectral_edge"),
            ("RAV, 6-14/1-20 Hz Left Anterior", "alpha_variability"),
        ],
    )
    def test_family_classification(self, trend_name: str, expected_family: str):
        assert classify_family(trend_name) == expected_family

    def test_unknown_trend_returns_other(self):
        assert classify_family("Something completely unknown") == "other"

    def test_order_matters_rav_before_fft_power(self):
        # RAV contains "FFT PowerRatio" in real data — must match alpha_variability first
        assert classify_family("RAV, 6-14/1-20 Hz") == "alpha_variability"

    def test_order_matters_rda_before_rhythmicity(self):
        # RDA matches "Rhythmic" but should hit rda first
        assert classify_family("Rhythmic delta indicator") == "rda"


class TestExtractFrequencyRange:
    def test_simple_range(self):
        assert extract_frequency_range("FFT Power, 1 - 4 Hz") == (1.0, 4.0)

    def test_ratio_range(self):
        # Takes numerator only
        assert extract_frequency_range("FFT PowerRatio, 8-13/1-4 Hz") == (8.0, 13.0)

    def test_no_frequency(self):
        assert extract_frequency_range("aEEG Left Hemisphere") == (None, None)

    def test_decimal_range(self):
        assert extract_frequency_range("0.5 - 32.0 Hz") == (0.5, 32.0)


class TestMapToBand:
    def test_delta(self):
        assert map_to_band(1, 4) == "delta"

    def test_theta(self):
        assert map_to_band(4, 8) == "theta"

    def test_alpha(self):
        assert map_to_band(8, 13) == "alpha"

    def test_beta(self):
        assert map_to_band(13, 20) == "beta"

    def test_no_match(self):
        assert map_to_band(50, 100) == ""

    def test_custom_bands(self):
        assert map_to_band(1, 4, {"low": (0, 5)}) == "low"


class TestExtractHemisphere:
    def test_left(self):
        assert extract_hemisphere("aEEG Left Hemisphere") == "left"

    def test_right(self):
        assert extract_hemisphere("aEEG Right Hemisphere") == "right"

    def test_none(self):
        assert extract_hemisphere("Suppression Ratio All 10-20") == ""


class TestExtractRegion:
    def test_anterior(self):
        assert extract_region("FFT Power Left Anterior") == "anterior"

    def test_posterior(self):
        assert extract_region("FFT Power Left Posterior") == "posterior"

    def test_hemisphere(self):
        assert extract_region("aEEG Left Hemisphere") == "hemisphere"

    def test_none(self):
        assert extract_region("Artifact Intensity") == ""


class TestExtractElectrode:
    def test_chain(self):
        assert extract_electrode("FFT Power, 1 - 4 Hz Left Anterior F3C3") == "F3C3"

    def test_single_electrode(self):
        assert extract_electrode("Artifact Detector Fp1") == "Fp1"

    def test_no_electrode(self):
        assert extract_electrode("aEEG Left Hemisphere") == ""

    def test_long_chain(self):
        assert extract_electrode("Something F3C3P3 here") == "F3C3P3"


class TestGetSubcolumnName:
    def test_artifact_intensity_from_lookup(self):
        assert get_subcolumn_name(1, 1, "Artifact Intensity", "artifact_intensity") == "emg"
        assert get_subcolumn_name(1, 2, "Artifact Intensity", "artifact_intensity") == "eye_vertical"
        assert get_subcolumn_name(1, 3, "Artifact Intensity", "artifact_intensity") == "eye_horizontal"

    def test_aeeg_from_lookup(self):
        # aEEG sub-cols per CSV Format Reference §3.4:
        # _1=max, _2=min, _3=p50, _4=p75, _5=p25 (statistical percentiles of envelope)
        assert get_subcolumn_name(20, 1, "aEEG Left", "aeeg") == "max"
        assert get_subcolumn_name(20, 2, "aEEG Left", "aeeg") == "min"
        assert get_subcolumn_name(20, 3, "aEEG Left", "aeeg") == "p50"
        assert get_subcolumn_name(20, 4, "aEEG Left", "aeeg") == "p75"
        assert get_subcolumn_name(20, 5, "aEEG Left", "aeeg") == "p25"

    def test_spike_density_from_trend(self):
        result = get_subcolumn_name(999, 1, "Spike Generalized per sec", "spike_density")
        assert "generalized" in result

    def test_fft_power_derives_from_trend(self):
        result = get_subcolumn_name(10, 1, "FFT Power, 1 - 4 Hz Left Anterior F3C3", "fft_power")
        assert result == "f3c3"


class TestGenerateCommonName:
    def test_artifact_intensity(self):
        entry = _make_entry(family="artifact_intensity", sub_column_name="emg")
        assert generate_common_name(entry) == "artifact_intensity_emg"

    def test_aeeg(self):
        entry = _make_entry(family="aeeg", hemisphere="left", sub_column_name="max")
        assert generate_common_name(entry) == "aeeg_left_max"

    def test_seizure_probability_i121(self):
        entry = _make_entry(
            family="seizure_probability", i_group=121,
            trend_name="Seizure Probability P14",
        )
        assert generate_common_name(entry) == "seizure_probability_p14"

    def test_seizure_detection_family(self):
        # With MMX-first resolution, "SeizureProbabilityP14 Detections" instruments get
        # family="seizure_detection" directly — no I-group gating needed.
        entry = _make_entry(
            family="seizure_detection", i_group=122,
            trend_name="SeizureProbabilityP14 Detections",
        )
        assert generate_common_name(entry) == "seizure_detection"

    def test_fft_power(self):
        entry = _make_entry(
            family="fft_power", frequency_band="delta",
            hemisphere="left", region="anterior",
            trend_name="FFT Power, 1 - 4 Hz Left Anterior F3C3",
        )
        assert generate_common_name(entry) == "fft_delta_left_anterior"

    def test_fft_power_native_anterior(self):
        # V8+: non-lateralized Anterior channel power → natural fft_{band}_anterior
        entry = _make_entry(
            family="fft_power", frequency_band="delta", region="anterior",
            trend_name="FFT Power, 1 - 4 Hz, Anterior",
        )
        assert generate_common_name(entry) == "fft_delta_anterior"

    def test_fft_power_asym_anterior_suffixed(self):
        # Asymmetry-region power keeps the _asym suffix to stay distinct from
        # the non-lateralized Anterior channel and the bilateral aggregate.
        entry = _make_entry(
            family="fft_power", frequency_band="delta", region="anterior",
            trend_name="FFT Power, 1 - 4 Hz, Asym Anterior",
        )
        assert generate_common_name(entry) == "fft_delta_anterior_asym"

    def test_relative_power_alpha_anterior(self):
        # FFT PowerRatio band/1-30 → relative band power
        entry = _make_entry(
            family="relative_power", region="anterior",
            trend_name="FFT PowerRatio, 8-13/1-30 Hz, Anterior",
        )
        assert generate_common_name(entry) == "rel_alpha_anterior"

    def test_relative_power_delta_all(self):
        entry = _make_entry(
            family="relative_power",
            trend_name="FFT PowerRatio, 1-4/1-30 Hz, All 10-20",
        )
        assert generate_common_name(entry) == "rel_delta_all"

    def test_adr_anterior(self):
        # 8-13/1-4 = ADR
        entry = _make_entry(
            family="adr", region="anterior",
            trend_name="FFT PowerRatio, 8-13/1-4 Hz, Anterior",
        )
        assert generate_common_name(entry) == "adr_anterior"

    def test_tdr_anterior(self):
        # 4-8/1-4 = TDR — distinct slug, no longer collides onto adr
        entry = _make_entry(
            family="adr", region="anterior",
            trend_name="FFT PowerRatio, 4-8/1-4 Hz, Anterior",
        )
        assert generate_common_name(entry) == "tdr_anterior"

    def test_rav_all(self):
        entry = _make_entry(
            family="alpha_variability",
            trend_name="FFT PowerRatio, 6-14/1-20 Hz, All 10-20",
        )
        assert generate_common_name(entry) == "rav_all"

    def test_aeeg_anterior_region(self):
        # Non-lateralized aEEG Anterior → region in slug (not collapsed to aeeg_max)
        entry = _make_entry(
            family="aeeg", region="anterior", sub_column_name="max",
            trend_name="aEEG, Anterior",
        )
        assert generate_common_name(entry) == "aeeg_anterior_max"

    def test_status_epilepticus_persyst_variants(self):
        # Persyst-native ESE — distinct _persyst slugs, never the calculated name.
        cases = {
            "Status Epilepticus ACNS Metric (Binary)": "status_epilepticus_persyst_acns_binary",
            "Status Epilepticus Combined Metric (Percent)": "status_epilepticus_persyst_combined_percent",
            "Electrographic Status Epilepticus03": "status_epilepticus_persyst_03",
        }
        for trend, expected in cases.items():
            assert classify_family(trend) == "status_epilepticus"
            e = _make_entry(family="status_epilepticus", trend_name=trend)
            slug = generate_common_name(e)
            assert slug == expected
            assert slug not in ("status_epilepticus_screen_flag", "has_status_epilepticus")

    def test_seizure_burden_persyst_variants(self):
        cases = {
            "Seizure Burden - 5 min - Percentage": "seizure_burden_persyst_percentage",
            "Seizure Burden - 5 min- Category": "seizure_burden_persyst_category",
        }
        for trend, expected in cases.items():
            assert classify_family(trend) == "seizure_burden"
            e = _make_entry(family="seizure_burden", trend_name=trend)
            slug = generate_common_name(e)
            assert slug == expected
            assert slug not in ("seizure_burden_pct", "seizure_burden_hours")

    def test_fft_spectrogram(self):
        # Slug format is center-frequency, 2-decimal, decimal point written as
        # "_" so the slug is a safe identifier in R/SQL/parquet: bin 1 = 0.5 Hz
        # → "0_50hz".
        entry = _make_entry(
            family="fft_spectrogram", hemisphere="left", region="hemisphere",
            sub_index=1,
        )
        name = generate_common_name(entry)
        assert name.startswith("fft_spec_")
        assert "0_50hz" in name
        assert "." not in name, f"slug must not contain '.': {name}"

    def test_rhythmicity_spectrogram_uses_sqrt_formula(self):
        # Rhythmicity is sqrt-scaled per CSV ref §3.28: f_k = (1 + (k-1)/24)²
        # Bin 49 = (1 + 48/24)² = 9.00 Hz (NOT 13 Hz as the old linear formula
        # claimed).
        entry = _make_entry(
            family="rhythmicity", hemisphere="left", region="hemisphere",
            sub_index=49,
        )
        name = generate_common_name(entry)
        assert "9_00hz" in name, f"expected 9_00hz center freq, got: {name}"
        assert "." not in name, f"slug must not contain '.': {name}"

    def test_suppression_ratio(self):
        entry = _make_entry(
            family="suppression_ratio", hemisphere="left",
            trend_name="Suppression Ratio Left Hemisphere",
        )
        assert generate_common_name(entry) == "suppression_left"

    def test_suppression_ratio_hemisphere_region(self):
        # region=Hemisphere → bare `suppression_{hemi}` (whole-hemisphere is canonical).
        entry = _make_entry(
            family="suppression_ratio", hemisphere="right", region="hemisphere",
            trend_name="Suppression Ratio, Right Hemisphere",
        )
        assert generate_common_name(entry) == "suppression_right"

    def test_suppression_ratio_anterior_region(self):
        # region=Anterior → explicit region suffix; focal regions are not canonical.
        entry = _make_entry(
            family="suppression_ratio", hemisphere="left", region="anterior",
            trend_name="Suppression Ratio, Left Anterior",
        )
        assert generate_common_name(entry) == "suppression_left_anterior"

    def test_suppression_ratio_posterior_region(self):
        entry = _make_entry(
            family="suppression_ratio", hemisphere="right", region="posterior",
            trend_name="Suppression Ratio, Right Posterior",
        )
        assert generate_common_name(entry) == "suppression_right_posterior"

    def test_suppression_ratio_all_brain(self):
        entry = _make_entry(
            family="suppression_ratio",
            trend_name="Suppression Ratio, All 10-20",
        )
        assert generate_common_name(entry) == "suppression_all"

    def test_heart_rate_i72(self):
        entry = _make_entry(family="heart_rate", i_group=72)
        assert generate_common_name(entry) == "heart_rate"


class TestBuildColumnSchema:
    def test_schema_length(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        assert len(schema) == 33

    def test_entries_have_family(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        families = {e.family for e in schema}
        assert "artifact_intensity" in families
        assert "aeeg" in families
        assert "seizure_probability" in families
        assert "fft_power" in families
        assert "fft_spectrogram" in families

    def test_entries_sorted_by_col_index(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        indices = [e.col_index for e in schema]
        assert indices == sorted(indices)

    def test_common_names_non_empty(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        for entry in schema:
            assert entry.common_name, f"{entry.code} has empty common_name"

    def test_common_names_unique(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        names = [e.common_name for e in schema]
        assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_fft_spectrogram_has_freq_range(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        spec_cols = [e for e in schema if e.family == "fft_spectrogram"]
        assert len(spec_cols) == 5
        for e in spec_cols:
            assert e.freq_min_hz is not None
            assert e.freq_max_hz is not None

    def test_fft_power_has_band(self, parsed_export):
        schema = build_column_schema(parsed_export.code_to_description)
        power_cols = [e for e in schema if e.family == "fft_power"]
        assert len(power_cols) == 6
        for e in power_cols:
            assert e.frequency_band in ("delta", "theta", "alpha")


class TestGetColumnsByFamily:
    def test_filter(self, column_schema):
        aeeg = get_columns_by_family(column_schema, "aeeg")
        assert len(aeeg) == 10  # 5 left + 5 right
        assert all(e.family == "aeeg" for e in aeeg)

    def test_empty_family(self, column_schema):
        assert get_columns_by_family(column_schema, "nonexistent") == []


class TestGetFftPowerColumns:
    def test_structure(self, column_schema):
        result = get_fft_power_columns(column_schema)
        assert "delta" in result
        assert "theta" in result
        assert "alpha" in result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(**overrides) -> ColumnEntry:
    """Build a ColumnEntry with defaults, overriding specified fields."""
    defaults = dict(
        col_index=0,
        code="I0_0",
        i_group=0,
        sub_index=1,
        trend_name="",
        family="other",
        frequency_band="",
        freq_min_hz=None,
        freq_max_hz=None,
        hemisphere="",
        region="",
        electrode="",
        sub_column_name="",
        common_name="",
    )
    defaults.update(overrides)
    return ColumnEntry(**defaults)


# ---------------------------------------------------------------------------
# Uniqueness backstop regressions
#
# The `__dupN` suffix is the last-resort guard that keeps a schema addressable
# when two columns would otherwise share a name. It is never an acceptable
# shipped identifier: it names nothing, so an analyst cannot tell which
# instrument they are reading. Each case below produced one before the fix.
# ---------------------------------------------------------------------------


class TestNoUniquenessBackstopNames:
    def test_three_seizure_detection_instruments_get_distinct_names(self):
        """SeizureEventsP14, the P14 Detections channel, and a running max of it.

        All three classify as family ``seizure_detection`` and all three carry
        the same sub-column, so before the fix they collapsed onto
        seizure_detection_event / __dup2 / __dup3.
        """
        overlay_detect = _make_entry(
            family="seizure_detection", sub_column_name="detection_event",
            mmx_name="SeizureEventsP14")
        overlay_notify = _make_entry(
            family="seizure_detection", sub_column_name="notification_event",
            sub_index=2, mmx_name="SeizureEventsP14")
        detections = _make_entry(
            family="seizure_detection", sub_column_name="detection_event",
            mmx_name="SeizureProbabilityP14 Detections")
        running_max = _make_entry(
            family="seizure_detection", sub_column_name="detection_event",
            mmx_name="Time Max <0,120> [SeizureProbabilityP14 Detections]")

        names = [generate_common_name(e) for e in
                 (overlay_detect, overlay_notify, detections, running_max)]

        assert names == [
            "seizure_detection_event",
            "seizure_notification_event",
            "seizure_detection_p14",
            "seizure_detection_p14_max120s",
        ]
        assert len(set(names)) == 4

    def test_running_max_never_takes_its_source_name(self):
        """A 2-minute max of the detections channel is a different variable."""
        source = _make_entry(family="seizure_detection",
                             sub_column_name="detection_event",
                             mmx_name="SeizureProbabilityP14 Detections")
        smoothed = _make_entry(family="seizure_detection",
                               sub_column_name="detection_event",
                               mmx_name="Time Max <0,120> [SeizureProbabilityP14 Detections]")
        assert generate_common_name(source) != generate_common_name(smoothed)

    def test_two_heart_rate_instruments_get_distinct_names(self):
        """The template ships "Heart Rate" and its "Heart Rate01" alias.

        Both export, under CSV headers "Heart Rate 1" and "Heart Rate 2", and
        neither carries a channel — so the second fell to heart_rate__dup2.
        The ordinal comes from the header, never from an I-number.
        """
        first = _make_entry(family="heart_rate", mmx_name="Heart Rate",
                            trend_name="Heart Rate 1")
        second = _make_entry(family="heart_rate", mmx_name="Heart Rate01",
                             trend_name="Heart Rate 2")
        assert generate_common_name(first) == "heart_rate"
        assert generate_common_name(second) == "heart_rate_2"

    def test_named_heart_rate_channel_still_wins_over_the_ordinal(self):
        """Where a channel is populated it is the better identity."""
        entry = _make_entry(family="heart_rate", electrode="EKG",
                            trend_name="Heart Rate 2")
        assert generate_common_name(entry) == "heart_rate_ekg"
