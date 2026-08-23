"""Map feature families to their producing engines and cadence metadata."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qeeg.ingestion.mmx_parser import EngineConfig

# Feature family -> engine name mapping
FAMILY_ENGINE_MAP: dict[str, str] = {
    # FFTEngine01: EpochDuration=4, EpochStep=8
    "fft_power": "FFTEngine01",
    "fft_power_ratio": "FFTEngine01",
    "adr": "FFTEngine01",              # band-vs-delta ratios (ADR 8-13/1-4, TDR 4-8/1-4)
    "relative_power": "FFTEngine01",   # band / total 1-30 Hz (V8+)
    "alpha_variability": "FFTEngine01",
    "fft_spectrogram": "FFTEngine01",
    "spectral_edge": "FFTEngine01",

    # Amplitude01: EpochDuration=10, EpochStep=10
    "suppression_ratio": "Amplitude01",

    # RhythmicityEngine01: EpochDuration=3, EpochStep=2
    "rhythmicity": "RhythmicityEngine01",
    "rda": "RhythmicityEngine01",
    "rhythmic_delta": "RhythmicityEngine01",

    # Artifact01: EpochDuration=1.2, EpochStep=1
    "artifact_intensity": "Artifact01",
    "electrode_quality": "Artifact01",

    # aEEG01: EpochDuration=1, EpochStep=1
    "aeeg": "aEEG01",

    # PeakEnvelope01: EpochDuration=1, EpochStep=1
    "peak_envelope": "PeakEnvelope01",

    # SeizureProbabilityP1401: EpochDuration=1, EpochStep=1
    "seizure_probability": "SeizureProbabilityP1401",
    "seizure_detection": "SeizureProbabilityP1401",
    "seizure_notification": "SeizureProbabilityP1401",

    # SpikeDensityV101: EpochDuration=1, EpochStep=1
    "spike_density": "SpikeDensityV101",

    # Asymmetry: derived from FFT
    "asymmetry": "FFTEngine01",
}

# Hardcoded defaults (rows per independent observation) from PedQuEST MMX
# Used when no MMX file is provided
_DEFAULT_CADENCE: dict[str, int] = {
    "FFTEngine01": 8,
    "Amplitude01": 10,
    "RhythmicityEngine01": 2,
    "Artifact01": 1,
    "aEEG01": 1,
    "PeakEnvelope01": 1,
    "SeizureProbabilityP1401": 1,
    "SpikeDensityV101": 1,
}

# Hardcoded defaults (EpochDuration in seconds) from PedQuEST MMX
# Used when no MMX file is provided
_DEFAULT_WINDOW: dict[str, float] = {
    "FFTEngine01": 4.0,
    "Amplitude01": 10.0,
    "RhythmicityEngine01": 3.0,
    "Artifact01": 1.2,
    "aEEG01": 1.0,
    "PeakEnvelope01": 1.0,
    "SeizureProbabilityP1401": 1.0,
    "SpikeDensityV101": 1.0,
}


def get_family_cadence(
    family: str,
    engines: dict[str, "EngineConfig"] | None = None,
) -> int:
    """Get the number of CSV rows per independent observation for a feature family.

    Args:
        family: Feature family name (e.g., "fft_power", "suppression_ratio")
        engines: Engine configs from MMX parsing. If None, uses hardcoded defaults.

    Returns:
        Number of 1-second rows per independent observation. 1 = every row is independent.
    """
    engine_name = FAMILY_ENGINE_MAP.get(family)
    if engine_name is None:
        return 1  # Unknown family — assume 1-second cadence (conservative for counts)

    if engines is not None and engine_name in engines:
        return engines[engine_name].rows_per_independent_obs

    return _DEFAULT_CADENCE.get(engine_name, 1)


def get_family_engine_name(family: str) -> str | None:
    """Return the Persyst engine name that produces a feature family."""
    return FAMILY_ENGINE_MAP.get(family)


def get_family_effective_basis(
    family: str,
    engines: dict[str, "EngineConfig"] | None = None,
) -> str:
    """Return the export label used to interpret per-feature effective N."""
    cadence = get_family_cadence(family, engines)
    return f"{family}_cadence_adjusted" if cadence > 1 else "row_count"


def get_effective_basis_values() -> list[str]:
    """Return all known n_effective_basis values for the data dictionary."""
    values = ["row_count"]
    for family in FAMILY_ENGINE_MAP:
        basis = get_family_effective_basis(family)
        if basis not in values:
            values.append(basis)
    values.append("not_estimated")
    return values


def get_engine_window(
    family: str,
    engines: dict[str, "EngineConfig"] | None = None,
) -> float:
    """Get the analysis window duration (EpochDuration) in seconds for a feature family.

    Args:
        family: Feature family name (e.g., "fft_power", "suppression_ratio")
        engines: Engine configs from MMX parsing. If None, uses hardcoded defaults.

    Returns:
        EpochDuration in seconds. 1.0 for unknown families.
    """
    engine_name = FAMILY_ENGINE_MAP.get(family)
    if engine_name is None:
        return 1.0

    if engines is not None and engine_name in engines:
        return engines[engine_name].epoch_duration

    return _DEFAULT_WINDOW.get(engine_name, 1.0)
