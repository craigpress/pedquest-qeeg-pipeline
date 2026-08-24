"""Validate the region-wise null / AR-rejection rule against exported CSVs.

Implements docs/_project/plans/NULL_ZERO_AND_METADATA_SPEC.md §2.

The mask is built from ZERO_IMPOSSIBLE instruments only — measures that are
physically positive-definite, so an exact 0 cannot be a measurement. Measures
that are legitimately zero (suppression ratio, asymmetry) must never seed the
mask or they null their own valid data; on subject-4, Suppression Ratio All 10-20
is 0 in 74% of *clean* rows.

Granularity is the REGION (Left Anterior, Right Hemisphere, All 10-20, …) rather
than the electrode derivation, so the same rule works on both panels: Research
Trends carries regional aggregates but only 3-5 electrode-specific instruments.

Usage:
    python scripts/validate_null_rule.py <export.csv> [<export.csv> ...]
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys

import numpy as np

# Physically positive-definite: an exact 0 is impossible as a measurement, so a
# 0 here IS the suppression signal. Everything else is either legitimately zero
# (suppression ratio, asymmetry, ratios) or binary/count, and must not seed it.
ZERO_IMPOSSIBLE = (
    "FFT Spectrogram", "FFT Power", "aEEG", "PeakEnvelope",
    "Rhythmicity Spectrogram", "Coherence_Spectrogram", "Coherence_Avg",
)

# Region tokens, longest first so "Left Anterior" wins over "Anterior".
REGIONS = (
    "Left Anterior", "Right Anterior", "Left Posterior", "Right Posterior",
    "Left Hemisphere", "Right Hemisphere",
    "Asym Anterior", "Asym Posterior", "Asym Parasagittal", "Asym Temporal",
    "Asym Hemi", "All 10-20", "Anterior", "Posterior",
)


def _region_of(label: str) -> str:
    for r in REGIONS:
        if r.lower() in label.lower():
            return r
    return ""


def _is_zero_impossible(label: str) -> bool:
    return any(label.startswith(p) or f", {p}" in label for p in ZERO_IMPOSSIBLE)


def analyse(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        r = csv.reader(fh)
        head = [next(r) for _ in range(8)]
        cur, fill = "", []
        for h in head[6]:
            if h.strip():
                cur = h.strip()
            fill.append(cur)
        codes = head[7]
        groups: "collections.OrderedDict[int, list[int]]" = collections.OrderedDict()
        for i, c in enumerate(codes):
            if c.startswith("I"):
                groups.setdefault(int(c.split("_")[0][1:]), []).append(i)
        for g in sorted(groups)[-2:]:          # Comment + Time are scaffolding
            groups.pop(g)
        labels = {g: fill[c[0]] for g, c in groups.items()}
        sel = sorted({i for c in groups.values() for i in c})
        idx = {c: k for k, c in enumerate(sel)}
        rows = []
        for row in r:
            try:
                rows.append([float(row[c]) if row[c] not in ("", "nan") else np.nan
                             for c in sel])
            except (IndexError, ValueError):
                pass

    a = np.array(rows, dtype=float)
    if a.size == 0:
        return {"err": "no data rows"}

    null = {g: (a[:, [idx[i] for i in cols]] == 0).all(axis=1)
            for g, cols in groups.items()}

    # Mask sources: zero-impossible instruments that carry a region and are not
    # dead in this recording (a channel off the whole time cannot inform).
    by_region: dict[str, list[np.ndarray]] = collections.defaultdict(list)
    for g, lbl in labels.items():
        reg = _region_of(lbl)
        if reg and _is_zero_impossible(lbl) and null[g].mean() < 0.95:
            by_region[reg].append(null[g])
    if not by_region:
        # Every zero-impossible instrument is >=95% zero, so there is no clean
        # reference to build a mask from. That is not a parsing failure — the
        # segment itself is essentially empty and should be excluded upstream.
        dead = [(labels[g], round(100 * float(null[g].mean()), 2))
                for g in labels if _is_zero_impossible(labels[g]) and _region_of(labels[g])]
        worst = sorted(dead, key=lambda x: x[1])[:3]
        return {
            "rows": int(a.shape[0]),
            "verdict": "SEGMENT EMPTY — exclude",
            "min_zero_pct_of_any_reference": worst[0][1] if worst else None,
            "note": "no zero-impossible regional instrument is non-zero in >5% of rows",
        }

    regions = sorted(by_region)
    # A region is rejected at t when every zero-impossible measure on it is 0.
    M = np.stack([np.stack(by_region[r], axis=1).all(axis=1) for r in regions], axis=1)
    k = M.sum(axis=1)
    n = M.shape[1]
    per = M.mean(axis=0)
    allrej = k == n

    runs_src = k > 0
    d = np.diff(np.concatenate(([0], runs_src.view(np.int8), [0])))
    runs = np.where(d == -1)[0] - np.where(d == 1)[0]
    worst = sorted(zip(regions, per), key=lambda x: -x[1])[:3]

    return {
        "rows": int(a.shape[0]),
        "instruments": len(groups),
        "regions": n,
        "mask_sources": sum(len(v) for v in by_region.values()),
        "reject_pct_min": round(100 * float(per.min()), 2),
        "reject_pct_max": round(100 * float(per.max()), 2),
        "spread_x": round(float(per.max() / per.min()), 1) if per.min() > 0 else None,
        "rows_all_regions_pct": round(100 * float(allrej.mean()), 2),
        "rows_partial_pct": round(100 * float(((k > 0) & ~allrej).mean()), 2),
        "mean_regions_rejected": round(float(k.mean()), 2),
        "runs": int(len(runs)),
        "runs_mult_8s_pct": (round(100 * float((runs % 8 == 0).mean()), 1)
                             if len(runs) else None),
        "worst_regions": [f"{r} {v*100:.1f}%" for r, v in worst],
    }


def main() -> None:
    for p in sys.argv[1:]:
        name = os.path.join(*p.replace("\\", "/").split("/")[-2:])
        try:
            print(json.dumps({"file": name, **analyse(p)}))
        except Exception as exc:                      # noqa: BLE001
            print(json.dumps({"file": name, "err": f"{type(exc).__name__}: {exc}"[:80]}))


if __name__ == "__main__":
    main()
