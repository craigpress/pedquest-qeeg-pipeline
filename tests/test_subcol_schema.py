"""Schema integrity tests for qeeg.ingestion.subcol_schema.

Verifies that the canonical schema:
- declares the counts that the CSV Format Reference §3.0 documents,
- is internally consistent (positions are 1..N, slugs are unique per family),
- agrees with the constants.py re-exports used by column_mapper.
"""
from __future__ import annotations

import pytest

from qeeg.ingestion import subcol_schema as schema
from qeeg import constants as const


# ---------------------------------------------------------------------------
# Schema self-consistency
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("family_schema", schema.SCHEMAS.values(), ids=lambda s: s.family)
def test_schema_positions_are_1_to_n(family_schema):
    """If a family has explicit subcolumns, positions must be 1..N in order."""
    if not family_schema.subcolumns:
        return  # formulaic spectrogram — no static sub-col list
    positions = [s.position for s in family_schema.subcolumns]
    assert positions == list(range(1, len(positions) + 1)), (
        f"{family_schema.family} subcolumn positions out of order: {positions}"
    )


@pytest.mark.parametrize("family_schema", schema.SCHEMAS.values(), ids=lambda s: s.family)
def test_schema_slugs_unique_per_family(family_schema):
    if not family_schema.subcolumns:
        return
    slugs = [s.slug for s in family_schema.subcolumns]
    assert len(slugs) == len(set(slugs)), (
        f"{family_schema.family} has duplicate slug(s): {slugs}"
    )


@pytest.mark.parametrize("family_schema", schema.SCHEMAS.values(), ids=lambda s: s.family)
def test_schema_expected_count_matches_subcolumns(family_schema):
    """For families with an explicit subcolumns list, count = len(subcolumns)."""
    if not family_schema.subcolumns:
        return  # formulaic
    assert family_schema.expected_count == len(family_schema.subcolumns), (
        f"{family_schema.family}: declared count {family_schema.expected_count} "
        f"!= len(subcolumns) {len(family_schema.subcolumns)}"
    )


# ---------------------------------------------------------------------------
# Cross-checks against the CSV Format Reference §3.0 contract
# ---------------------------------------------------------------------------

def test_schema_counts_match_csv_ref_section_3_0():
    """Counts must match the canonical doc §3.0 table verbatim."""
    expected = {
        "artifact_intensity":           3,
        "electrode_signal_quality":    22,
        "aeeg":                         5,
        "seizure_detection_notif_pair": 2,
        "rhythmicity_freqpow":         16,
        "fft_spectrogram":             40,
        "asymmetry_spectrogram":       40,
        "coherence_spectrogram":       63,
        "rhythmicity_spectrogram":     97,
    }
    for family, count in expected.items():
        assert schema.SCHEMAS[family].expected_count == count, (
            f"{family}: schema count {schema.SCHEMAS[family].expected_count} "
            f"disagrees with CSV ref §3.0 ({count})"
        )


# ---------------------------------------------------------------------------
# Spectrogram bin frequencies (sanity)
# ---------------------------------------------------------------------------

def test_fft_spectrogram_bin_frequencies():
    """FFT spec: bin k centered at k × 0.5 Hz; 40 bins covering 0.5–20 Hz."""
    assert schema.get_spectrogram_bin_freq("fft_spectrogram", 1) == 0.5
    assert schema.get_spectrogram_bin_freq("fft_spectrogram", 20) == 10.0
    assert schema.get_spectrogram_bin_freq("fft_spectrogram", 40) == 20.0


def test_rhythmicity_spectrogram_sqrt_bin_frequencies():
    """Rhythmicity (V7 default): sqrt-scaled. Bin 1 = 1 Hz; bin 49 ≈ 9 Hz; bin 97 = 25 Hz."""
    assert schema.get_spectrogram_bin_freq("rhythmicity_spectrogram", 1) == pytest.approx(1.0)
    assert schema.get_spectrogram_bin_freq("rhythmicity_spectrogram", 49) == pytest.approx(9.0, rel=1e-3)
    assert schema.get_spectrogram_bin_freq("rhythmicity_spectrogram", 97) == pytest.approx(25.0)


def test_coherence_spectrogram_linear_bin_frequencies():
    """Coherence: linear, bin k = (k-1) × 32/62 Hz. Bin 1 = 0 Hz; bin 63 = 32 Hz."""
    assert schema.get_spectrogram_bin_freq("coherence_spectrogram", 1) == pytest.approx(0.0)
    assert schema.get_spectrogram_bin_freq("coherence_spectrogram", 32) == pytest.approx(16.0, rel=1e-2)
    assert schema.get_spectrogram_bin_freq("coherence_spectrogram", 63) == pytest.approx(32.0)


# ---------------------------------------------------------------------------
# constants.py re-export integrity
# ---------------------------------------------------------------------------

def test_constants_artifact_intensity_components_match_schema():
    assert const.ARTIFACT_INTENSITY_COMPONENTS == list(schema.ARTIFACT_INTENSITY.slugs)


def test_artifact_detector_has_no_schema():
    """The family is discarded, so it must not carry invented sub-column names."""
    assert not hasattr(schema, "ARTIFACT_DETECTOR")
    assert not hasattr(const, "ARTIFACT_DETECTOR_ELECTRODES")
    assert 2 not in const.I_GROUP_SUBCOLUMN_NAMES


def test_constants_electrode_quality_electrodes_match_schema():
    """ESQ list must come from the schema (22 entries, no T3/T7 duplicates)."""
    assert const.ELECTRODE_QUALITY_ELECTRODES == list(schema.ELECTRODE_SIGNAL_QUALITY.slugs)
    assert len(const.ELECTRODE_QUALITY_ELECTRODES) == 22


def test_i_group_subcolumn_names_for_aeeg_match_schema():
    """I20 (aEEG L) and I21 (aEEG R) lookup lists come from schema.AEEG."""
    assert const.I_GROUP_SUBCOLUMN_NAMES[20] == list(schema.AEEG.slugs)
    assert const.I_GROUP_SUBCOLUMN_NAMES[21] == list(schema.AEEG.slugs)


def test_aeeg_slugs_match_csv_ref_section_3_4():
    """aEEG sub-col slugs come from CSV Format Reference §3.4: the five
    statistical percentiles of the smoothed envelope, in fixed order across
    every MMX version.

    Pre-2026-05-21 the pipeline used Persyst-specific guesses
    (upper_margin / lower_margin / bandwidth / percent_bs / amplitude); these
    were corrected to the percentile names below to match the canonical doc.
    """
    assert const.I_GROUP_SUBCOLUMN_NAMES[20] == [
        "max", "min", "p50", "p75", "p25",
    ]
    assert const.I_GROUP_SUBCOLUMN_NAMES[21] == [
        "max", "min", "p50", "p75", "p25",
    ]


# ---------------------------------------------------------------------------
# Schema → validator wiring
# ---------------------------------------------------------------------------

def test_validator_imports_counts_from_schema():
    """subcol_validator's EXPECTED_SUBCOL_COUNTS_FIXED must come from schema."""
    from qeeg.ingestion import subcol_validator as v
    # identity check: should be the same dict object
    assert v.EXPECTED_SUBCOL_COUNTS_FIXED is schema.EXPECTED_COUNTS
    assert v.EXPECTED_SUBCOL_COUNTS_VARIABLE is schema.VARIABLE_COUNTS


# ---------------------------------------------------------------------------
# MMX-version independence: same family + sub-index → same slug regardless
# of I-group number. Verifies an older MMX (where aEEG might land at I47
# instead of V7's I20/I21) still produces the canonical slugs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("i_group", [20, 21, 47, 999, 1])
def test_aeeg_slugs_independent_of_i_group(i_group):
    """aEEG sub-col slugs are determined by family, not by I-code."""
    from qeeg.ingestion.column_mapper import get_subcolumn_name
    assert get_subcolumn_name(i_group, 1, "aEEG Left Hemisphere", "aeeg") == "max"
    assert get_subcolumn_name(i_group, 2, "aEEG Left Hemisphere", "aeeg") == "min"
    assert get_subcolumn_name(i_group, 3, "aEEG Left Hemisphere", "aeeg") == "p50"
    assert get_subcolumn_name(i_group, 4, "aEEG Left Hemisphere", "aeeg") == "p75"
    assert get_subcolumn_name(i_group, 5, "aEEG Left Hemisphere", "aeeg") == "p25"


@pytest.mark.parametrize("i_group", [1, 99, 42])
def test_artifact_intensity_slugs_independent_of_i_group(i_group):
    from qeeg.ingestion.column_mapper import get_subcolumn_name
    assert get_subcolumn_name(i_group, 1, "Artifact Intensity", "artifact_intensity") == "emg"
    assert get_subcolumn_name(i_group, 2, "Artifact Intensity", "artifact_intensity") == "eye_vertical"
    assert get_subcolumn_name(i_group, 3, "Artifact Intensity", "artifact_intensity") == "eye_horizontal"


@pytest.mark.parametrize("i_group", [2, 50, 200])
def test_artifact_detector_sub_columns_get_no_electrode_name(i_group):
    """No fabricated electrode identity survives for the discarded family."""
    from qeeg.ingestion.column_mapper import get_subcolumn_name
    for sub in (1, 18):
        name = get_subcolumn_name(i_group, sub, "Artifact Detector", "artifact_detector")
        assert name not in ("Fp1", "A2")
