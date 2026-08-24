"""Diagnose schema-drift for patient subject-1 across all epoch families + spectrograms.

Computes NaN fraction and column coverage in hour windows:
  early [0,30), pre_boundary [30,35), boundary [35,37), late [37,44).
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE = "http://localhost:8000"
PATIENT = "subject-1"

WINDOWS = [
    ("early_0_30", 0.0, 30.0),
    ("pre_30_35", 30.0, 35.0),
    ("boundary_35_37", 35.0, 37.0),
    ("late_37_44", 37.0, 44.0),
]


def fetch(url: str, timeout: int = 60):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def nan_frac(vals):
    if not vals:
        return None, 0, 0
    total = len(vals)
    n_nan = sum(1 for v in vals if v is None or (isinstance(v, float) and math.isnan(v)))
    return (n_nan / total) if total else None, n_nan, total


def window_indices(hours, lo, hi):
    return [i for i, h in enumerate(hours) if h is not None and lo <= h < hi]


def summarize_columns(hours, columns, windows):
    """Per column, compute NaN frac + value range in each window."""
    result = {}
    for col, vals in columns.items():
        per_win = {}
        for name, lo, hi in windows:
            idxs = window_indices(hours, lo, hi)
            if not idxs:
                per_win[name] = {"n": 0, "nan_frac": None, "n_nan": 0, "mean": None, "min": None, "max": None}
                continue
            sub = [vals[i] for i in idxs]
            n = len(sub)
            non_nan = [v for v in sub if v is not None and not (isinstance(v, float) and math.isnan(v))]
            nn = n - len(non_nan)
            if non_nan:
                mn = min(non_nan)
                mx = max(non_nan)
                avg = sum(non_nan) / len(non_nan)
            else:
                mn = mx = avg = None
            per_win[name] = {
                "n": n,
                "nan_frac": nn / n if n else None,
                "n_nan": nn,
                "non_nan": len(non_nan),
                "mean": avg,
                "min": mn,
                "max": mx,
            }
        result[col] = per_win
    return result


def spectrogram_window_stats(frequencies, hours, matrix, windows):
    """matrix[freq_index][time_index]. For each window, compute:
      - time points with >=1 populated freq bin
      - mean populated freqs per time (i.e., avg column count)
      - overall NaN frac across all (freq,time) cells
    """
    out = {}
    n_freq = len(frequencies)
    for name, lo, hi in windows:
        idxs = window_indices(hours, lo, hi)
        if not idxs:
            out[name] = {"n_time": 0, "mean_freqs_populated": None, "nan_frac": None}
            continue
        total_cells = 0
        nan_cells = 0
        per_time_populated = []
        for t in idxs:
            populated = 0
            for fi in range(n_freq):
                v = matrix[fi][t] if fi < len(matrix) and t < len(matrix[fi]) else None
                total_cells += 1
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    nan_cells += 1
                else:
                    populated += 1
            per_time_populated.append(populated)
        mean_pop = sum(per_time_populated) / len(per_time_populated) if per_time_populated else None
        out[name] = {
            "n_time": len(idxs),
            "n_freq": n_freq,
            "mean_freqs_populated": mean_pop,
            "nan_frac": nan_cells / total_cells if total_cells else None,
        }
    return out


def analyze_family(family: str, results: dict):
    """Hit /epochs?families=<family>, summarize NaN + column coverage."""
    url = f"{BASE}/api/patients/{PATIENT}/epochs?families={family}&max_points=2000"
    try:
        data = fetch(url, timeout=60)
    except HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url}
    except URLError as e:
        return {"error": f"URL error: {e}", "url": url}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "url": url}

    hours = data.get("hours", [])
    columns = data.get("columns", {})
    n_cols = len(columns)

    # Per-column NaN/range
    per_col = summarize_columns(hours, columns, WINDOWS)

    # Per-window: columns that are "populated" (>=50% non-NaN)
    def populated_cols(win_name):
        out = []
        for col, wins in per_col.items():
            w = wins[win_name]
            nf = w["nan_frac"]
            if nf is not None and nf < 0.5:
                out.append(col)
        return sorted(out)

    cols_early = set(populated_cols("early_0_30"))
    cols_late = set(populated_cols("late_37_44"))

    lost = sorted(cols_early - cols_late)  # populated early, dead late
    gained = sorted(cols_late - cols_early)

    # Columns that flip from <5% NaN to >80% NaN
    flipped = []
    for col, wins in per_col.items():
        e = wins["early_0_30"]["nan_frac"]
        l = wins["late_37_44"]["nan_frac"]
        if e is not None and l is not None and e < 0.05 and l > 0.80:
            flipped.append(col)

    # Value-range shift detection (for spike detection of "inflated generalized")
    range_shifts = []
    for col, wins in per_col.items():
        e = wins["early_0_30"]
        l = wins["late_37_44"]
        if e["non_nan"] and l.get("non_nan"):
            if e["mean"] is not None and l["mean"] is not None and abs(e["mean"]) > 1e-9:
                ratio = l["mean"] / e["mean"] if e["mean"] != 0 else None
                if ratio is not None and (ratio > 2.0 or ratio < 0.5):
                    range_shifts.append({
                        "col": col,
                        "early_mean": e["mean"], "late_mean": l["mean"],
                        "early_min_max": [e["min"], e["max"]],
                        "late_min_max": [l["min"], l["max"]],
                        "ratio": ratio,
                    })

    # Aggregate NaN frac per window across all columns
    agg = {}
    for win_name, _, _ in [(w[0], w[1], w[2]) for w in WINDOWS]:
        n_tot = 0
        n_nan = 0
        for col, wins in per_col.items():
            w = wins[win_name]
            n_tot += w["n"]
            n_nan += w["n_nan"]
        agg[win_name] = {"nan_frac": (n_nan / n_tot if n_tot else None), "n_cells": n_tot}

    return {
        "n_columns": n_cols,
        "n_epochs_returned": len(hours),
        "agg_nan_frac_per_window": agg,
        "cols_populated_early": len(cols_early),
        "cols_populated_late": len(cols_late),
        "cols_lost_at_boundary": lost,
        "cols_gained_at_boundary": gained,
        "cols_flipped_lo_to_hi_nan": flipped,
        "range_shifts_2x": range_shifts,
        "per_col": per_col,
    }


def analyze_spectrogram(spec_type: str):
    url = f"{BASE}/api/patients/{PATIENT}/spectrogram/{spec_type}?max_time_points=2000"
    try:
        data = fetch(url, timeout=120)
    except HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url}
    except URLError as e:
        return {"error": f"URL error: {e}", "url": url}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "url": url}

    freqs = data.get("frequencies", [])
    hours = data.get("hours", [])
    matrix = data.get("matrix", [])

    stats = spectrogram_window_stats(freqs, hours, matrix, WINDOWS)
    return {
        "n_freq": len(freqs),
        "n_time": len(hours),
        "window_stats": stats,
    }


def main():
    epoch_families = [
        "aeeg", "artifact_intensity", "seizure_probability", "spike_density",
        "suppression_ratio", "fft_power", "fft_power_ratio", "alpha_variability",
        "spectral_edge", "rhythmic_delta", "rda", "sleep", "peak_envelope",
        "electrode_quality", "artifact_detector", "seizure_detection", "heart_rate",
    ]
    spec_types = [
        "fft_left", "fft_right", "asymmetry", "asymmetry_post", "asymmetry_temp",
        "asymmetry_parasag", "coherence", "rhythmicity", "asymmetry_hemi", "asymmetry_ant",
    ]

    out = {"patient": PATIENT, "windows": [{"name": n, "lo": lo, "hi": hi} for n, lo, hi in WINDOWS]}

    print("=== FAMILIES ===", file=sys.stderr)
    fam_results = {}
    for fam in epoch_families:
        print(f"Fetching family {fam}...", file=sys.stderr)
        fam_results[fam] = analyze_family(fam, {})
    out["families"] = fam_results

    print("=== SPECTROGRAMS ===", file=sys.stderr)
    spec_results = {}
    for spec in spec_types:
        print(f"Fetching spectrogram {spec}...", file=sys.stderr)
        spec_results[spec] = analyze_spectrogram(spec)
    out["spectrograms"] = spec_results

    json.dump(out, sys.stdout, indent=2, default=str)


if __name__ == "__main__":
    main()
