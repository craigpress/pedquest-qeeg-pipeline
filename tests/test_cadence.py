"""Tests for feature-to-engine cadence mapping."""
from qeeg.ingestion.cadence import FAMILY_ENGINE_MAP, get_family_cadence, get_engine_window


def test_known_family_cadences():
    """Each feature family must map to its producing engine."""
    assert FAMILY_ENGINE_MAP["fft_power"] == "FFTEngine01"
    assert FAMILY_ENGINE_MAP["fft_power_ratio"] == "FFTEngine01"
    assert FAMILY_ENGINE_MAP["suppression_ratio"] == "Amplitude01"
    assert FAMILY_ENGINE_MAP["aeeg"] == "aEEG01"
    assert FAMILY_ENGINE_MAP["seizure_probability"] == "SeizureProbabilityP1401"
    assert FAMILY_ENGINE_MAP["artifact_intensity"] == "Artifact01"
    assert FAMILY_ENGINE_MAP["rhythmicity"] == "RhythmicityEngine01"


def test_get_family_cadence_with_engines():
    """get_family_cadence returns rows_per_independent_obs for a family."""
    from qeeg.ingestion.mmx_parser import EngineConfig
    engines = {
        "FFTEngine01": EngineConfig("FFTEngine01", 4.0, 8.0),
        "Amplitude01": EngineConfig("Amplitude01", 10.0, 10.0),
        "aEEG01": EngineConfig("aEEG01", 1.0, 1.0),
    }
    assert get_family_cadence("fft_power", engines) == 8
    assert get_family_cadence("suppression_ratio", engines) == 10
    assert get_family_cadence("aeeg", engines) == 1


def test_get_family_cadence_defaults_without_engines():
    """Without engine configs, use hardcoded defaults from PedQuEST MMX."""
    assert get_family_cadence("fft_power", None) == 8
    assert get_family_cadence("suppression_ratio", None) == 10
    assert get_family_cadence("aeeg", None) == 1


def test_get_engine_window_defaults():
    """EpochDuration defaults from PedQuEST MMX."""
    assert get_engine_window("fft_power", None) == 4.0
    assert get_engine_window("suppression_ratio", None) == 10.0
    assert get_engine_window("rhythmicity", None) == 3.0
    assert get_engine_window("artifact_intensity", None) == 1.2
    assert get_engine_window("aeeg", None) == 1.0
    assert get_engine_window("seizure_probability", None) == 1.0
    assert get_engine_window("spike_density", None) == 1.0


def test_get_engine_window_with_engines():
    """get_engine_window prefers parsed MMX values over defaults."""
    from qeeg.ingestion.mmx_parser import EngineConfig
    engines = {
        "FFTEngine01": EngineConfig("FFTEngine01", 4.0, 8.0),
        "Amplitude01": EngineConfig("Amplitude01", 10.0, 10.0),
    }
    assert get_engine_window("fft_power", engines) == 4.0
    assert get_engine_window("suppression_ratio", engines) == 10.0


def test_get_engine_window_unknown_family():
    """Unknown families return 1.0 (conservative default)."""
    assert get_engine_window("totally_unknown", None) == 1.0
