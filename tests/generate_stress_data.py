#!/usr/bin/env python3
"""Generate synthetic 48-hour PedQuEST stress test data for 5 patients.

Each patient has a distinct post-cardiac-arrest clinical trajectory.
Produces Persyst-format CSV files that the pipeline can parse end-to-end.

Usage:
    python tests/generate_stress_data.py
"""
from __future__ import annotations

import csv
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXCEL_EPOCH = datetime(1899, 12, 30)
DURATION_HOURS = 48
ROWS_PER_HOUR = 3600  # 1-second epochs
N_ROWS = DURATION_HOURS * ROWS_PER_HOUR  # 172800

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "test_data" / "stress_test"

# ---------------------------------------------------------------------------
# Column definitions — (i_code, trend_name) tuples
# Order matters: trend_name row uses fill-forward gaps
# ---------------------------------------------------------------------------

# Artifact Intensity (3 BSS components)
ARTIFACT_INTENSITY_COLS = [
    ("I1_1", "Artifact Intensity"),
    ("I1_2", "Artifact Intensity"),
    ("I1_3", "Artifact Intensity"),
]

# Artifact Detector (18 electrodes)
ARTIFACT_DETECTOR_COLS = [
    (f"I2_{i}", "Artifact Detector") for i in range(1, 19)
]

# Electrode Signal Quality (24 electrodes)
ELECTRODE_QUALITY_COLS = [
    (f"I3_{i}", "Electrode Signal Quality") for i in range(1, 25)
]

# FFT Power: 4 bands x 6 regions = 24 columns
_FFT_BANDS = [
    ("1 - 4", "delta"),
    ("4 - 8", "theta"),
    ("8 - 13", "alpha"),
    ("13 - 30", "beta"),
]
_FFT_REGIONS = [
    ("Left Anterior", "Fp1F3C3"),
    ("Right Anterior", "Fp2F4C4"),
    ("Left Posterior", "C3P3O1"),
    ("Right Posterior", "C4P4O2"),
    ("Left Hemisphere", ""),
    ("Right Hemisphere", ""),
]

FFT_POWER_COLS = []
_fft_sub = 1
for band_hz, _band_name in _FFT_BANDS:
    for region, elec_chain in _FFT_REGIONS:
        elec_suffix = f" {elec_chain}" if elec_chain else ""
        trend = f"FFT Power, {band_hz} Hz {region}{elec_suffix}"
        FFT_POWER_COLS.append((f"I10_{_fft_sub}", trend))
        _fft_sub += 1

# FFT Power Ratio (ADR): 6 regions
FFT_RATIO_COLS = []
_ratio_sub = 1
for region, elec_chain in _FFT_REGIONS:
    elec_suffix = f" {elec_chain}" if elec_chain else ""
    trend = f"FFT PowerRatio, 8 - 13/1 - 4 Hz {region}{elec_suffix}"
    FFT_RATIO_COLS.append((f"I14_{_ratio_sub}", trend))
    _ratio_sub += 1

# aEEG Left/Right (5 sub-channels each)
AEEG_LEFT_COLS = [(f"I20_{i}", "aEEG Left Hemisphere") for i in range(1, 6)]
AEEG_RIGHT_COLS = [(f"I21_{i}", "aEEG Right Hemisphere") for i in range(1, 6)]

# Suppression Ratio L/R
SUPPRESSION_COLS = [
    ("I60_1", "Suppression Ratio Left Hemisphere"),
    ("I60_2", "Suppression Ratio Right Hemisphere"),
]

# Seizure
SEIZURE_COLS = [
    ("I121_1", "Seizure Probability P14"),
    ("I122_1", "Seizure Detection P14"),
]

# Spike Density
SPIKE_COLS = [("I131_1", "Spike Burst Bilateral")]

# FFT Spectrogram Left (5 bins, enough for parser/column_mapper test)
FFT_SPEC_COLS = [
    (f"I200_{i}", "FFT Spectrogram Left Hemisphere") for i in range(1, 6)
]

# All columns in order
ALL_COLUMNS = (
    ARTIFACT_INTENSITY_COLS
    + ARTIFACT_DETECTOR_COLS
    + ELECTRODE_QUALITY_COLS
    + FFT_POWER_COLS
    + FFT_RATIO_COLS
    + AEEG_LEFT_COLS
    + AEEG_RIGHT_COLS
    + SUPPRESSION_COLS
    + SEIZURE_COLS
    + SPIKE_COLS
    + FFT_SPEC_COLS
)

ALL_CODES = [code for code, _ in ALL_COLUMNS]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def to_excel_serial(dt: datetime) -> float:
    return (dt - EXCEL_EPOCH).total_seconds() / 86400.0


def sigmoid(x: np.ndarray, center: float, width: float) -> np.ndarray:
    """Smooth sigmoid transition centered at `center` with given `width`."""
    return 1.0 / (1.0 + np.exp(-(x - center) / max(width, 0.01)))


def phase_blend(hours: np.ndarray, transitions: list[tuple[float, float, float]]) -> np.ndarray:
    """Create smooth multi-phase envelope.

    transitions: list of (center_hour, width_hours, target_value)
    Returns array blending between target values.
    """
    result = np.full_like(hours, transitions[0][2])
    for i in range(1, len(transitions)):
        _, _, prev_val = transitions[i - 1]
        center, width, target_val = transitions[i]
        blend = sigmoid(hours, center, width)
        result = result * (1 - blend) + target_val * blend
    return result


def step_hold(arr: np.ndarray, step: int = 4) -> np.ndarray:
    """Hold values in blocks of `step` rows (mimics FFT engine cadence)."""
    out = arr.copy()
    for i in range(0, len(arr), step):
        out[i:i + step] = arr[i]
    return out


# ---------------------------------------------------------------------------
# Patient scenario generators
# Each returns dict[str, np.ndarray] keyed by I-code
# ---------------------------------------------------------------------------

def _base_artifact(rng: np.random.RandomState, n: int, hours: np.ndarray,
                   intensity_mean: float = 3.0,
                   quality_base: float = 0.001,
                   bad_electrodes: list[int] | None = None,
                   bad_quality: float = 0.6) -> dict[str, np.ndarray]:
    """Generate artifact/quality columns common to all patients."""
    d: dict[str, np.ndarray] = {}

    # Artifact Intensity (3 BSS, scale 0-30+)
    for i in range(1, 4):
        base = rng.exponential(intensity_mean, n).astype(np.float32)
        # Periodic care interventions every ~2 hours
        for h in range(0, DURATION_HOURS, 2):
            start = int(h * ROWS_PER_HOUR + rng.uniform(0, 600))
            end = min(start + int(rng.uniform(120, 600)), n)
            base[start:end] += rng.uniform(3, 12)
        d[f"I1_{i}"] = np.clip(base, 0, None)

    # Artifact Detector (18 electrodes, binary)
    for i in range(1, 19):
        prob = 0.05 + rng.uniform(0, 0.1)
        d[f"I2_{i}"] = (rng.random(n) < prob).astype(np.float32)

    # Electrode Signal Quality (24 electrodes, scale 0-1, low=good)
    for i in range(1, 25):
        base_q = rng.exponential(quality_base, n).astype(np.float32)
        if bad_electrodes and i in bad_electrodes:
            # Intermittent bad quality on selected electrodes
            for h in range(0, DURATION_HOURS, 4):
                start = int(h * ROWS_PER_HOUR + rng.uniform(0, 1800))
                end = min(start + int(rng.uniform(100, 500)), n)
                base_q[start:end] = rng.uniform(bad_quality, 1.0, end - start)
        d[f"I3_{i}"] = np.clip(base_q, 0, 1)

    return d


def _base_fft_spec(rng: np.random.RandomState, n: int) -> dict[str, np.ndarray]:
    """Generate FFT Spectrogram Left columns (5 bins)."""
    d: dict[str, np.ndarray] = {}
    for i in range(1, 6):
        d[f"I200_{i}"] = rng.exponential(5.0, n).astype(np.float32)
    return d


def generate_patient_2046(rng: np.random.RandomState) -> dict[str, np.ndarray]:
    """Seizure evolution: ramp 6-12h → SE 12-18h → resolution."""
    n = N_ROWS
    hours = np.linspace(0, DURATION_HOURS, n)
    d: dict[str, np.ndarray] = {}

    # Seizure probability envelope
    seiz_env = phase_blend(hours, [
        (0, 1, 0.02), (6, 1.5, 0.1), (9, 1.5, 0.4),
        (12, 1, 0.75), (15, 0.5, 0.8), (18, 1.5, 0.3),
        (21, 1.5, 0.05), (30, 2, 0.02),
    ])
    seiz_noise = rng.normal(0, 0.05, n)
    seiz_prob = np.clip(seiz_env + seiz_noise, 0, 1).astype(np.float32)
    d["I121_1"] = seiz_prob
    d["I122_1"] = (seiz_prob > 0.5).astype(np.float32)

    # FFT Power: delta dominant during seizures, alpha suppressed
    delta_env = phase_blend(hours, [
        (0, 1, 40), (12, 2, 150), (18, 2, 60), (30, 3, 30),
    ])
    theta_env = phase_blend(hours, [
        (0, 1, 15), (12, 2, 80), (18, 2, 25), (30, 3, 15),
    ])
    alpha_env = phase_blend(hours, [
        (0, 1, 5), (12, 2, 3), (18, 2, 8), (30, 3, 12),
    ])
    beta_env = phase_blend(hours, [
        (0, 1, 3), (12, 2, 2), (18, 2, 5), (30, 3, 6),
    ])

    band_envs = {"delta": delta_env, "theta": theta_env, "alpha": alpha_env, "beta": beta_env}
    for band_idx, (band_hz, band_name) in enumerate(_FFT_BANDS):
        env = band_envs[band_name]
        for reg_idx in range(6):
            sub = band_idx * 6 + reg_idx + 1
            vals = env * rng.uniform(0.8, 1.2, n)
            vals = step_hold(np.clip(vals + rng.normal(0, 2, n), 0, 500).astype(np.float32))
            d[f"I10_{sub}"] = vals

    # ADR (alpha/delta ratio)
    for i in range(1, 7):
        alpha_col = d[f"I10_{12 + i}"] if f"I10_{12 + i}" in d else d["I10_13"]
        delta_col = d[f"I10_{i}"]
        adr = np.where(delta_col > 0, alpha_col / delta_col * 100, 0)
        d[f"I14_{i}"] = step_hold(np.clip(adr, 0, 100).astype(np.float32))

    # aEEG: suppressed early, recovering late
    aeeg_upper_env = phase_blend(hours, [
        (0, 1, 12), (12, 2, 8), (18, 2, 18), (30, 3, 30),
    ])
    aeeg_lower_env = phase_blend(hours, [
        (0, 1, 4), (12, 2, 2), (18, 2, 6), (30, 3, 12),
    ])
    # aEEG sub-cols per CSV Format Reference §3.4: _1=max, _2=min, _3=p50, _4=p75, _5=p25 (µV)
    for prefix, i_group in [("L", 20), ("R", 21)]:
        upper = np.clip(aeeg_upper_env + rng.normal(0, 2, n), 1, 100).astype(np.float32)
        lower = np.clip(aeeg_lower_env + rng.normal(0, 1, n), 0, upper * 0.8).astype(np.float32)
        span = upper - lower
        d[f"I{i_group}_1"] = upper                                       # max
        d[f"I{i_group}_2"] = lower                                       # min
        d[f"I{i_group}_3"] = (lower + 0.50 * span).astype(np.float32)    # p50 (median)
        d[f"I{i_group}_4"] = (lower + 0.75 * span).astype(np.float32)    # p75
        d[f"I{i_group}_5"] = (lower + 0.25 * span).astype(np.float32)    # p25

    # Suppression ratio
    supp_env = phase_blend(hours, [
        (0, 1, 0.3), (12, 2, 0.15), (18, 2, 0.25), (30, 3, 0.1),
    ])
    for i, code in enumerate(["I60_1", "I60_2"], 1):
        # BSR is PERCENT (0-100), not a 0-1 fraction (matches real Persyst output)
        d[code] = np.clip((supp_env + rng.normal(0, 0.05, n)) * 100, 0, 100).astype(np.float32)

    # Spike density: high during seizure phase
    spike_env = phase_blend(hours, [
        (0, 1, 1), (12, 2, 15), (18, 2, 3), (30, 3, 1),
    ])
    d["I131_1"] = np.clip(rng.poisson(spike_env), 0, 50).astype(np.float32)

    # Artifacts
    d.update(_base_artifact(rng, n, hours, intensity_mean=4.0, bad_electrodes=[1, 2]))
    d.update(_base_fft_spec(rng, n))

    return d


def generate_patient_3640(rng: np.random.RandomState) -> dict[str, np.ndarray]:
    """Burst-suppression → flat/isoelectric by 24h."""
    n = N_ROWS
    hours = np.linspace(0, DURATION_HOURS, n)
    d: dict[str, np.ndarray] = {}

    # No seizures
    d["I121_1"] = np.clip(rng.exponential(0.02, n), 0, 1).astype(np.float32)
    d["I122_1"] = np.zeros(n, dtype=np.float32)

    # FFT Power: burst-suppression pattern → declining → flat
    # Burst-suppression creates oscillating power; model as envelope × burst pattern
    burst_period = rng.uniform(8, 15)  # seconds between bursts
    burst_pattern = 0.5 + 0.5 * np.sin(2 * np.pi * np.arange(n) / (burst_period * 1))
    # Burst amplitude declines over time
    burst_amp = phase_blend(hours, [
        (0, 1, 1.0), (12, 3, 0.6), (24, 3, 0.1), (36, 3, 0.02),
    ])
    burst_mod = burst_pattern * burst_amp

    delta_base = phase_blend(hours, [
        (0, 1, 60), (12, 3, 30), (24, 3, 3), (36, 3, 1),
    ])
    theta_base = phase_blend(hours, [
        (0, 1, 20), (12, 3, 10), (24, 3, 1), (36, 3, 0.5),
    ])
    alpha_base = phase_blend(hours, [
        (0, 1, 5), (12, 3, 2), (24, 3, 0.3), (36, 3, 0.1),
    ])
    beta_base = phase_blend(hours, [
        (0, 1, 3), (12, 3, 1.5), (24, 3, 0.2), (36, 3, 0.1),
    ])

    band_bases = {"delta": delta_base, "theta": theta_base, "alpha": alpha_base, "beta": beta_base}
    for band_idx, (band_hz, band_name) in enumerate(_FFT_BANDS):
        base = band_bases[band_name]
        for reg_idx in range(6):
            sub = band_idx * 6 + reg_idx + 1
            vals = base * (0.5 + burst_mod) * rng.uniform(0.8, 1.2, n)
            vals = step_hold(np.clip(vals + rng.normal(0, 0.5, n), 0, 500).astype(np.float32))
            d[f"I10_{sub}"] = vals

    # ADR
    for i in range(1, 7):
        delta_col = d[f"I10_{i}"]
        alpha_col = d.get(f"I10_{12 + i}", d["I10_13"])
        adr = np.where(delta_col > 0.1, alpha_col / delta_col * 100, 0)
        d[f"I14_{i}"] = step_hold(np.clip(adr, 0, 100).astype(np.float32))

    # aEEG: burst-suppression signature declining to flat
    for i_group in [20, 21]:
        upper = phase_blend(hours, [
            (0, 1, 25), (12, 3, 15), (24, 3, 5), (36, 3, 2),
        ])
        upper = np.clip(upper * (0.5 + burst_mod) + rng.normal(0, 1, n), 1, 100).astype(np.float32)
        lower = np.clip(upper * 0.2 + rng.normal(0, 0.5, n), 0, upper * 0.9).astype(np.float32)
        d[f"I{i_group}_1"] = upper
        d[f"I{i_group}_2"] = lower
        d[f"I{i_group}_3"] = upper - lower
        pbs = phase_blend(hours, [
            (0, 1, 50), (12, 3, 65), (24, 3, 85), (36, 3, 95),
        ])
        d[f"I{i_group}_4"] = np.clip(pbs + rng.normal(0, 3, n), 0, 100).astype(np.float32)
        d[f"I{i_group}_5"] = np.clip(upper * 0.6 + rng.normal(0, 1, n), 0, 100).astype(np.float32)

    # Suppression ratio: increasing over time
    supp_env = phase_blend(hours, [
        (0, 1, 0.5), (12, 3, 0.65), (24, 3, 0.85), (36, 3, 0.95),
    ])
    for code in ["I60_1", "I60_2"]:
        d[code] = np.clip((supp_env + rng.normal(0, 0.03, n)) * 100, 0, 100).astype(np.float32)

    # Spike density: minimal
    d["I131_1"] = rng.poisson(0.5, n).astype(np.float32)

    # Clean recording, but intermittent A1 electrode issues
    d.update(_base_artifact(rng, n, hours, intensity_mean=1.5, quality_base=0.0005,
                            bad_electrodes=[17], bad_quality=0.8))
    d.update(_base_fft_spec(rng, n))

    return d


def generate_patient_3848(rng: np.random.RandomState) -> dict[str, np.ndarray]:
    """Slow disorganized → gradual recovery, brief early seizures."""
    n = N_ROWS
    hours = np.linspace(0, DURATION_HOURS, n)
    d: dict[str, np.ndarray] = {}

    # Seizures: brief events in first 6 hours
    seiz_prob = np.full(n, 0.02, dtype=np.float32)
    # 3 seizure events in hours 1-6, each 2-5 minutes
    for event_hour in [1.5, 3.2, 5.0]:
        duration_min = rng.uniform(2, 5)
        start = int(event_hour * ROWS_PER_HOUR)
        end = min(start + int(duration_min * 60), n)
        seiz_prob[start:end] = rng.uniform(0.5, 0.85, end - start)
    seiz_prob += rng.normal(0, 0.02, n)
    seiz_prob = np.clip(seiz_prob, 0, 1).astype(np.float32)
    d["I121_1"] = seiz_prob
    d["I122_1"] = (seiz_prob > 0.5).astype(np.float32)

    # FFT Power: disorganized (high delta, low alpha) → recovering
    delta_env = phase_blend(hours, [
        (0, 1, 80), (12, 3, 50), (24, 3, 30), (36, 3, 20),
    ])
    theta_env = phase_blend(hours, [
        (0, 1, 25), (12, 3, 20), (24, 3, 15), (36, 3, 12),
    ])
    alpha_env = phase_blend(hours, [
        (0, 1, 3), (12, 3, 8), (24, 3, 15), (36, 3, 25),
    ])
    beta_env = phase_blend(hours, [
        (0, 1, 2), (12, 3, 4), (24, 3, 6), (36, 3, 8),
    ])

    band_envs = {"delta": delta_env, "theta": theta_env, "alpha": alpha_env, "beta": beta_env}
    for band_idx, (band_hz, band_name) in enumerate(_FFT_BANDS):
        env = band_envs[band_name]
        for reg_idx in range(6):
            sub = band_idx * 6 + reg_idx + 1
            vals = env * rng.uniform(0.8, 1.2, n)
            vals = step_hold(np.clip(vals + rng.normal(0, 2, n), 0, 500).astype(np.float32))
            d[f"I10_{sub}"] = vals

    # ADR rising toward recovery
    for i in range(1, 7):
        delta_col = d[f"I10_{i}"]
        alpha_col = d.get(f"I10_{12 + i}", d["I10_13"])
        adr = np.where(delta_col > 0.1, alpha_col / delta_col * 100, 0)
        d[f"I14_{i}"] = step_hold(np.clip(adr, 0, 100).astype(np.float32))

    # aEEG: improving
    for i_group in [20, 21]:
        upper = phase_blend(hours, [
            (0, 1, 18), (12, 3, 25), (24, 3, 35), (36, 3, 42),
        ])
        upper = np.clip(upper + rng.normal(0, 2, n), 1, 100).astype(np.float32)
        lower = phase_blend(hours, [
            (0, 1, 5), (12, 3, 8), (24, 3, 12), (36, 3, 16),
        ])
        lower = np.clip(lower + rng.normal(0, 1, n), 0, upper * 0.9).astype(np.float32)
        d[f"I{i_group}_1"] = upper
        d[f"I{i_group}_2"] = lower
        d[f"I{i_group}_3"] = upper - lower
        d[f"I{i_group}_4"] = np.clip(
            phase_blend(hours, [(0, 1, 15), (12, 3, 10), (24, 3, 5), (36, 3, 2)])
            + rng.normal(0, 2, n), 0, 100
        ).astype(np.float32)
        d[f"I{i_group}_5"] = np.clip(rng.uniform(8, 35, n), 0, 100).astype(np.float32)

    # Suppression ratio: declining
    supp_env = phase_blend(hours, [
        (0, 1, 0.2), (12, 3, 0.12), (24, 3, 0.06), (36, 3, 0.03),
    ])
    for code in ["I60_1", "I60_2"]:
        d[code] = np.clip((supp_env + rng.normal(0, 0.02, n)) * 100, 0, 100).astype(np.float32)

    # Spike density: moderate early, declining
    spike_env = phase_blend(hours, [(0, 1, 5), (12, 3, 2), (24, 3, 1), (36, 3, 0.5)])
    d["I131_1"] = np.clip(rng.poisson(spike_env), 0, 50).astype(np.float32)

    d.update(_base_artifact(rng, n, hours, intensity_mean=5.0, bad_electrodes=[1, 2, 9, 10]))
    d.update(_base_fft_spec(rng, n))

    return d


def generate_patient_4458(rng: np.random.RandomState) -> dict[str, np.ndarray]:
    """State cycling + sleep spindles by 36h — good prognosis (happy path)."""
    n = N_ROWS
    hours = np.linspace(0, DURATION_HOURS, n)
    d: dict[str, np.ndarray] = {}

    # No seizures
    d["I121_1"] = np.clip(rng.exponential(0.01, n), 0, 1).astype(np.float32)
    d["I122_1"] = np.zeros(n, dtype=np.float32)

    # State cycling: sinusoidal modulation with ~90 min period emerging by 24h
    cycle_period_hours = 1.5  # ~90 minutes
    cycle_amp = phase_blend(hours, [
        (0, 1, 0.0), (12, 3, 0.1), (24, 3, 0.3), (36, 3, 0.5),
    ])
    cycle_mod = cycle_amp * np.sin(2 * np.pi * hours / cycle_period_hours)

    # FFT Power: mild suppression → normal with state cycling
    delta_env = phase_blend(hours, [
        (0, 1, 40), (12, 3, 30), (24, 3, 20), (36, 3, 15),
    ])
    theta_env = phase_blend(hours, [
        (0, 1, 10), (12, 3, 12), (24, 3, 15), (36, 3, 18),
    ])
    alpha_env = phase_blend(hours, [
        (0, 1, 5), (12, 3, 10), (24, 3, 18), (36, 3, 25),
    ])
    beta_env = phase_blend(hours, [
        (0, 1, 3), (12, 3, 5), (24, 3, 8), (36, 3, 10),
    ])

    band_envs = {"delta": delta_env, "theta": theta_env, "alpha": alpha_env, "beta": beta_env}
    for band_idx, (band_hz, band_name) in enumerate(_FFT_BANDS):
        env = band_envs[band_name]
        # State cycling modulates power: "sleep" = more delta, "wake" = more alpha/beta
        if band_name in ("delta", "theta"):
            mod = env * (1 + cycle_mod * 0.3)
        else:
            mod = env * (1 - cycle_mod * 0.2)
        for reg_idx in range(6):
            sub = band_idx * 6 + reg_idx + 1
            vals = mod * rng.uniform(0.9, 1.1, n)
            vals = step_hold(np.clip(vals + rng.normal(0, 1, n), 0, 500).astype(np.float32))
            d[f"I10_{sub}"] = vals

    # ADR
    for i in range(1, 7):
        delta_col = d[f"I10_{i}"]
        alpha_col = d.get(f"I10_{12 + i}", d["I10_13"])
        adr = np.where(delta_col > 0.1, alpha_col / delta_col * 100, 0)
        d[f"I14_{i}"] = step_hold(np.clip(adr, 0, 100).astype(np.float32))

    # aEEG: improving with state cycling (bandwidth variation)
    for i_group in [20, 21]:
        upper = phase_blend(hours, [
            (0, 1, 20), (12, 3, 28), (24, 3, 38), (36, 3, 45),
        ])
        upper_mod = upper * (1 + cycle_mod * 0.2)
        upper_val = np.clip(upper_mod + rng.normal(0, 1.5, n), 1, 100).astype(np.float32)
        lower = phase_blend(hours, [
            (0, 1, 8), (12, 3, 10), (24, 3, 14), (36, 3, 18),
        ])
        lower_mod = lower * (1 - cycle_mod * 0.15)
        lower_val = np.clip(lower_mod + rng.normal(0, 1, n), 0, upper_val * 0.9).astype(np.float32)
        d[f"I{i_group}_1"] = upper_val
        d[f"I{i_group}_2"] = lower_val
        d[f"I{i_group}_3"] = upper_val - lower_val
        d[f"I{i_group}_4"] = np.clip(
            phase_blend(hours, [(0, 1, 10), (12, 3, 5), (24, 3, 2), (36, 3, 1)])
            + rng.normal(0, 1, n), 0, 100
        ).astype(np.float32)
        d[f"I{i_group}_5"] = np.clip(rng.uniform(10, 40, n), 0, 100).astype(np.float32)

    # Suppression ratio: low throughout, declining
    supp_env = phase_blend(hours, [
        (0, 1, 0.15), (12, 3, 0.08), (24, 3, 0.03), (36, 3, 0.01),
    ])
    for code in ["I60_1", "I60_2"]:
        d[code] = np.clip((supp_env + rng.normal(0, 0.01, n)) * 100, 0, 100).astype(np.float32)

    # Spike density: minimal
    d["I131_1"] = rng.poisson(0.3, n).astype(np.float32)

    # Very clean recording
    d.update(_base_artifact(rng, n, hours, intensity_mean=1.0, quality_base=0.0003))
    d.update(_base_fft_spec(rng, n))

    return d


def generate_patient_4682(rng: np.random.RandomState) -> dict[str, np.ndarray]:
    """Mixed: burst-supp → seizures → improvement. Edge cases: 15 leading zeros,
    120s timestamp gap, impossible electrode_quality >1.0."""
    n = N_ROWS
    hours = np.linspace(0, DURATION_HOURS, n)
    d: dict[str, np.ndarray] = {}

    # Seizures: mid-recording events (12-24h), NOT meeting SE criteria
    seiz_prob = np.full(n, 0.03, dtype=np.float32)
    # 4 seizure events, each 5-12 minutes, spread over 12-24h
    for event_hour in [14.0, 17.5, 20.0, 23.0]:
        duration_min = rng.uniform(5, 12)
        start = int(event_hour * ROWS_PER_HOUR)
        end = min(start + int(duration_min * 60), n)
        seiz_prob[start:end] = rng.uniform(0.4, 0.75, end - start)
    seiz_prob = np.clip(seiz_prob + rng.normal(0, 0.02, n), 0, 1).astype(np.float32)
    d["I121_1"] = seiz_prob
    d["I122_1"] = (seiz_prob > 0.5).astype(np.float32)

    # FFT Power: burst-supp early, then seizure-related changes, then improvement
    delta_env = phase_blend(hours, [
        (0, 1, 30), (12, 3, 70), (18, 2, 90), (24, 3, 40), (36, 3, 25),
    ])
    theta_env = phase_blend(hours, [
        (0, 1, 10), (12, 3, 30), (18, 2, 45), (24, 3, 18), (36, 3, 12),
    ])
    alpha_env = phase_blend(hours, [
        (0, 1, 2), (12, 3, 4), (18, 2, 3), (24, 3, 10), (36, 3, 18),
    ])
    beta_env = phase_blend(hours, [
        (0, 1, 1), (12, 3, 3), (18, 2, 2), (24, 3, 5), (36, 3, 7),
    ])

    band_envs = {"delta": delta_env, "theta": theta_env, "alpha": alpha_env, "beta": beta_env}
    for band_idx, (band_hz, band_name) in enumerate(_FFT_BANDS):
        env = band_envs[band_name]
        for reg_idx in range(6):
            sub = band_idx * 6 + reg_idx + 1
            vals = env * rng.uniform(0.8, 1.2, n)
            vals = step_hold(np.clip(vals + rng.normal(0, 2, n), 0, 500).astype(np.float32))
            d[f"I10_{sub}"] = vals

    # ADR
    for i in range(1, 7):
        delta_col = d[f"I10_{i}"]
        alpha_col = d.get(f"I10_{12 + i}", d["I10_13"])
        adr = np.where(delta_col > 0.1, alpha_col / delta_col * 100, 0)
        d[f"I14_{i}"] = step_hold(np.clip(adr, 0, 100).astype(np.float32))

    # aEEG: suppressed → mixed → improving
    for i_group in [20, 21]:
        upper = phase_blend(hours, [
            (0, 1, 10), (12, 3, 15), (18, 2, 12), (24, 3, 22), (36, 3, 32),
        ])
        upper = np.clip(upper + rng.normal(0, 2, n), 1, 100).astype(np.float32)
        lower = np.clip(upper * 0.25 + rng.normal(0, 1, n), 0, upper * 0.9).astype(np.float32)
        d[f"I{i_group}_1"] = upper
        d[f"I{i_group}_2"] = lower
        d[f"I{i_group}_3"] = upper - lower
        d[f"I{i_group}_4"] = np.clip(
            phase_blend(hours, [(0, 1, 40), (12, 3, 20), (24, 3, 10), (36, 3, 5)])
            + rng.normal(0, 3, n), 0, 100
        ).astype(np.float32)
        d[f"I{i_group}_5"] = np.clip(rng.uniform(5, 30, n), 0, 100).astype(np.float32)

    # Suppression ratio: high early, declining
    supp_env = phase_blend(hours, [
        (0, 1, 0.55), (12, 3, 0.3), (24, 3, 0.15), (36, 3, 0.08),
    ])
    for code in ["I60_1", "I60_2"]:
        d[code] = np.clip((supp_env + rng.normal(0, 0.03, n)) * 100, 0, 100).astype(np.float32)

    # Spike density
    spike_env = phase_blend(hours, [(0, 1, 2), (12, 3, 6), (24, 3, 2), (36, 3, 1)])
    d["I131_1"] = np.clip(rng.poisson(spike_env), 0, 50).astype(np.float32)

    # Artifacts with edge cases
    d.update(_base_artifact(rng, n, hours, intensity_mean=3.5, bad_electrodes=[1, 9]))
    d.update(_base_fft_spec(rng, n))

    # EDGE CASE 1: 15 leading zero rows (FFT engine startup)
    for code in ALL_CODES:
        if code.startswith("I10_") or code.startswith("I14_"):
            d[code][:15] = 0.0

    # EDGE CASE 2: Inject impossible electrode quality values > 1.0
    # These should be caught by validation but won't be (bug #6b)
    for eq_idx in [5, 12]:
        d[f"I3_{eq_idx}"][1000:1100] = rng.uniform(1.5, 5.0, 100).astype(np.float32)

    return d


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_persyst_csv(filepath: Path, patient_id: str, start_dt: datetime,
                      data: dict[str, np.ndarray],
                      test_date: str, test_time: str,
                      gap_at_row: int | None = None,
                      gap_seconds: float = 120.0) -> None:
    """Write a Persyst-format CSV file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    n = N_ROWS

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")

        # 6 metadata rows
        w.writerow(["File", f"C:\\Data\\{patient_id}_1.dat"])
        w.writerow(["PatientName", "Test Patient"])  # triggers PHI check
        w.writerow(["PatientID", patient_id])
        w.writerow(["PatientBirthDate", "01/01/2020"])
        w.writerow(["TestDate", test_date])
        w.writerow(["TestTime", test_time])

        # Trend name row (fill-forward: only first column of each group gets name)
        trend_row = [""]  # ClockDateTime has no trend name
        last_trend = ""
        for _code, trend_name in ALL_COLUMNS:
            if trend_name != last_trend:
                trend_row.append(trend_name)
                last_trend = trend_name
            else:
                trend_row.append("")
        w.writerow(trend_row)

        # Code row
        code_row = ["ClockDateTime"] + [code for code, _ in ALL_COLUMNS]
        w.writerow(code_row)

        # Data rows
        for i in range(n):
            dt = start_dt + timedelta(seconds=i)
            # Optional timestamp gap
            if gap_at_row is not None and i >= gap_at_row:
                dt = dt + timedelta(seconds=gap_seconds)
            serial = to_excel_serial(dt)
            row = [f"{serial:.10f}"]
            for code in ALL_CODES:
                row.append(f"{data[code][i]:.4f}")
            w.writerow(row)

            if i % 50000 == 0 and i > 0:
                pct = i / n * 100
                print(f"  {filepath.name}: {pct:.0f}% ({i}/{n} rows)", flush=True)

    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  {filepath.name}: done ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Metadata CSV generators
# ---------------------------------------------------------------------------

PATIENTS = {
    "2046": {
        "age_days": 2920, "sex": "M", "etiology": "cardiac",
        "rosc_time": "09:30:00", "rosc_date": "2025-01-10",
        "eeg_start": datetime(2025, 1, 10, 10, 30, 0),
        "pcpc": 2, "site": "CHOP",
        "generator": generate_patient_2046,
    },
    "3640": {
        "age_days": 4380, "sex": "F", "etiology": "drowning",
        "rosc_time": "06:30:00", "rosc_date": "2025-02-15",
        "eeg_start": datetime(2025, 2, 15, 9, 30, 0),
        "pcpc": 4, "site": "BCH",
        "generator": generate_patient_3640,
    },
    "3848": {
        "age_days": 1825, "sex": "M", "etiology": "cardiac",
        "rosc_time": "05:00:00", "rosc_date": "2025-03-20",
        "eeg_start": datetime(2025, 3, 20, 11, 0, 0),
        "pcpc": 1, "site": "CCHMC",
        "generator": generate_patient_3848,
    },
    "4458": {
        "age_days": 365, "sex": "F", "etiology": "asphyxia",
        "rosc_time": "01:00:00", "rosc_date": "2025-04-05",
        "eeg_start": datetime(2025, 4, 5, 3, 0, 0),
        "pcpc": 5, "site": "CHOP",
        "generator": generate_patient_4458,
    },
    "4682": {
        "age_days": 5475, "sex": "M", "etiology": "cardiac",
        "rosc_time": "01:20:00", "rosc_date": "2025-05-12",
        "eeg_start": datetime(2025, 5, 12, 11, 20, 0),
        "pcpc": 3, "site": "LURIE",
        "generator": generate_patient_4682,
    },
}


def write_clinical_csv(outdir: Path) -> None:
    """Write clinical metadata CSV.

    Columns: patient_id, age_days (age in days at ROSC), rosc_datetime.
    age_days = age at time of arrest/ROSC (matches the API endpoint expectation).
    rosc_datetime = ISO combined date+time of ROSC.
    """
    with open(outdir / "clinical_data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["patient_id", "age_days", "rosc_datetime"])
        for pid, info in PATIENTS.items():
            rosc_dt = f"{info['rosc_date']}T{info['rosc_time']}"
            w.writerow([pid, info["age_days"], rosc_dt])


def write_eeg_correction_csv(outdir: Path) -> None:
    with open(outdir / "eeg_date_correction.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "new_name", "age_in_days_at_time_of_eeg", "eeg_start_time",
            "eeg_duration", "date_of_csv_creation",
        ])
        for pid, info in PATIENTS.items():
            eeg_start = info["eeg_start"]
            w.writerow([
                f"{pid}_1",
                info["age_days"] + 1,
                eeg_start.strftime("%H:%M:%S"),
                "48:00:00",
                "12:33.4",
            ])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write metadata
    write_clinical_csv(OUTPUT_DIR)
    print("clinical_data.csv written")
    write_eeg_correction_csv(OUTPUT_DIR)
    print("eeg_date_correction.csv written")

    # Generate each patient
    for pid, info in PATIENTS.items():
        print(f"\nGenerating patient {pid}...")
        rng = np.random.RandomState(int(pid))
        gen_fn = info["generator"]
        data = gen_fn(rng)

        # Verify all columns present
        missing = [c for c in ALL_CODES if c not in data]
        if missing:
            print(f"  ERROR: Missing columns: {missing}")
            sys.exit(1)

        csv_path = OUTPUT_DIR / pid / f"{pid}_1.csv"
        eeg_start = info["eeg_start"]
        test_date = eeg_start.strftime("%m/%d/%Y")
        test_time = eeg_start.strftime("%H:%M:%S")

        # Patient 4682 gets a timestamp gap at hour 20
        gap_at_row = int(20 * ROWS_PER_HOUR) if pid == "4682" else None

        write_persyst_csv(
            csv_path, pid, eeg_start, data,
            test_date, test_time,
            gap_at_row=gap_at_row, gap_seconds=120.0,
        )

    print(f"\nDone. All files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
