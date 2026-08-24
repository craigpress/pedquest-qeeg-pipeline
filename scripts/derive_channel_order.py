"""Derive the sub-column → channel mapping for Artifact Detector (I6, 18 cols) and
Electrode Signal Quality (I30, 22 cols) from the data, without assuming an order.

Both instruments are outputs of the same Artifact Reduction algorithm. If I6 is a
per-derivation artifact flag and I30 is a per-electrode quality value, then for each
derivation the two most-correlated electrode-quality columns must be exactly the two
electrodes of that derivation. That makes the montage's graph topology recoverable
from the correlation matrix alone — and the recovered graph can then be checked
against the candidate orderings.

Writes output/audit_subject-1/channel_order_derivation.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import export_dir  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "output" / "audit_subject-1"

AD = [f"I6_{i}" for i in range(1, 19)]      # Artifact Detector, 18 sub-cols
EQ = [f"I30_{i}" for i in range(1, 23)]     # Electrode Signal Quality, 22 sub-cols

# ---- candidate orderings -------------------------------------------------
# E1: acquisition ChannelMap order, entries 1-22, from subject-1_rec.lay [ChannelMap]
LAY_CHANNELMAP_22 = ["Fp1", "F7", "T3", "T5", "O1", "F3", "C3", "P3", "A1", "Fz",
                     "Cz", "Fp2", "F8", "T4", "T6", "O2", "F4", "C4", "P4", "A2",
                     "Fpz", "Pz"]
# E2: what qeeg/ingestion/subcol_schema.py currently asserts
SCHEMA_ESQ_22 = ["Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T3", "C3", "Cz", "C4",
                 "T4", "T5", "P3", "Pz", "P4", "T6", "O1", "O2", "A1", "A2", "EKG"]

# D1: trending montage order, from subject-1_rec.lay [Record Montage 1] (EEG pairs only)
LAY_MONTAGE_18 = [("Fp1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
                  ("Fp2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2"),
                  ("Fp1", "F7"), ("F7", "T3"), ("T3", "T5"), ("T5", "O1"),
                  ("Fp2", "F8"), ("F8", "T4"), ("T4", "T6"), ("T6", "O2"),
                  ("Fz", "Cz"), ("Cz", "Pz")]
# D2: the legacy 18-derivation order printed in PersystTrendCSV_Format_Reference.md §3.3
#     (T7/P7/T8/P8 are the modern aliases of T3/T5/T4/T6)
FMTREF_18 = [("Fp1", "F7"), ("F7", "T3"), ("T3", "T5"), ("T5", "O1"),
             ("Fp2", "F8"), ("F8", "T4"), ("T4", "T6"), ("T6", "O2"),
             ("Fp1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
             ("Fp2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2"),
             ("Fz", "Cz"), ("Cz", "Pz")]
# D3: what qeeg/ingestion/subcol_schema.py currently asserts — single electrodes
SCHEMA_AD_18 = ["Fp1", "F3", "C3", "P3", "O1", "F7", "T3", "T5",
                "Fp2", "F4", "C4", "P4", "O2", "F8", "T4", "T6", "A1", "A2"]


def corr_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlation of every AD column against every EQ column."""
    sub = df[AD + EQ]
    r = sub.corr(method="spearman")
    return r.loc[AD, EQ]


def analyse(name: str, pq_path: str) -> dict:
    df = pd.read_parquet(pq_path, columns=AD + EQ)
    C = corr_matrix(df)

    top2 = {}
    for j, a in enumerate(AD, start=1):
        s = C.loc[a].sort_values(ascending=False)
        picks = [int(x.split("_")[1]) for x in s.index[:2]]
        top2[j] = {
            "eq_indices": sorted(picks),
            "r_top2": [round(float(v), 4) for v in s.values[:2]],
            "r_3rd": round(float(s.values[2]), 4),
            "separation": round(float(s.values[1] - s.values[2]), 4),
        }

    # Recovered graph: 18 edges over the EQ indices actually used.
    edges = [tuple(v["eq_indices"]) for v in top2.values()]
    deg = Counter(i for e in edges for i in e)
    used = sorted(deg)
    unused = [k for k in range(1, 23) if k not in deg]

    def score(deriv_pairs, eq_order) -> dict:
        """How many of the 18 recovered edges match the candidate montage?"""
        if len(eq_order) < 22:
            return {"matched": 0, "of": 18, "detail": ["eq order too short"]}
        idx = {name: i + 1 for i, name in enumerate(eq_order)}
        hits, detail = 0, []
        for j, pair in enumerate(deriv_pairs, start=1):
            want = sorted(idx.get(p, -1) for p in pair)
            got = top2[j]["eq_indices"]
            ok = want == got
            hits += ok
            if not ok:
                detail.append(f"AD_{j} {pair}: expected EQ{want} got EQ{got}")
        return {"matched": hits, "of": len(deriv_pairs), "detail": detail[:6]}

    combos = {
        "montage=lay  /  eq=lay_channelmap": score(LAY_MONTAGE_18, LAY_CHANNELMAP_22),
        "montage=lay  /  eq=subcol_schema": score(LAY_MONTAGE_18, SCHEMA_ESQ_22),
        "montage=fmtref / eq=lay_channelmap": score(FMTREF_18, LAY_CHANNELMAP_22),
        "montage=fmtref / eq=subcol_schema": score(FMTREF_18, SCHEMA_ESQ_22),
    }

    # Under the winning EQ order, name the recovered edges.
    named = {}
    for label, eq_order in (("lay_channelmap", LAY_CHANNELMAP_22),
                            ("subcol_schema", SCHEMA_ESQ_22)):
        rev = {i + 1: nm for i, nm in enumerate(eq_order)}
        named[label] = {f"I6_{j}": "-".join(rev.get(i, f"?{i}") for i in v["eq_indices"])
                        for j, v in top2.items()}

    return {
        "csv": name,
        "n_rows": len(df),
        "top2_per_artifact_subcol": top2,
        "recovered_edges_eq_indices": edges,
        "eq_degree": {str(k): v for k, v in sorted(deg.items())},
        "eq_indices_used": used,
        "eq_indices_never_selected": unused,
        "ordering_scores": combos,
        "recovered_edges_named": named,
        "min_separation": round(min(v["separation"] for v in top2.values()), 4),
        "min_r_top2": round(min(v["r_top2"][1] for v in top2.values()), 4),
    }


SHARE = export_dir()
TEST_EEGS = SHARE / "Test EEGs"
PATIENT_DIR = SHARE / "subject-1_rec"
NON_EEG_PREFIX = ("X", "DC", "OSAT", "PR", "Event")


def _lay_channelmap(lay: Path) -> list[str]:
    names, inmap = [], False
    for line in lay.read_text(errors="replace").splitlines():
        if line.startswith("["):
            inmap = line.strip() == "[ChannelMap]"
            continue
        if inmap and "=" in line:
            names.append(line.split("=")[0].replace("-Ref", ""))
    return names


def _is_eeg_like(n: str) -> bool:
    import re as _re
    return not _re.match(r"^(X\d+|DC\d+|OSAT|PR|Event)$", n)


def structural_evidence() -> dict:
    """Corroborating evidence that does not depend on the trend values."""
    import re as _re
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_columns import read_header_block

    ev: dict = {}

    # (a) Per-instrument raw outputs: byte size is proportional to channel count.
    pdir = PATIENT_DIR / "subject-1_rec.Persyst"
    sizes = {f.name: f.stat().st_size for f in pdir.glob("mg2.*.raw")
             if f.name in ("mg2.Artifact.raw", "mg2.ElectrodeSignalQuality.raw",
                           "mg2.ArtifactIntensity.raw")}
    ev["raw_output_sizes"] = sizes
    if {"mg2.Artifact.raw", "mg2.ElectrodeSignalQuality.raw"} <= sizes.keys():
        ev["esq_over_ad_size_ratio"] = round(
            sizes["mg2.ElectrodeSignalQuality.raw"] / sizes["mg2.Artifact.raw"], 6)
        ev["expected_22_over_18"] = round(22 / 18, 6)

    # (b) Persyst's own per-channel file naming = the trending montage.
    pairs = sorted(
        _re.sub(r"^mg2\.Rhythmicity_Spectrogram_3\.00_|_avg\.raw$", "", f.name)
        for f in pdir.glob("mg2.Rhythmicity_Spectrogram_3.00_*_avg.raw")
    )
    ev["persyst_per_channel_names"] = pairs
    ev["persyst_bipolar_pairs"] = [p for p in pairs if _re.fullmatch(r"[A-Za-z]+\d*-[A-Za-z]+\d*", p)]
    ev["n_persyst_bipolar_pairs"] = len(ev["persyst_bipolar_pairs"])

    # (c) Cross-recording: does ESQ width follow the acquisition channel count?
    cross = []
    dirs = [PATIENT_DIR] + sorted(d for d in TEST_EEGS.iterdir() if d.is_dir())
    for d in dirs:
        lays = sorted(d.glob("*.lay"))
        csvs = [c for c in sorted(d.glob("*.csv")) if c.name != "eeg_date_correction.csv"]
        if not lays or not csvs:
            continue
        chans = _lay_channelmap(lays[0])
        eeg_like = [c for c in chans if _is_eeg_like(c)]
        try:
            hb = read_header_block(csvs[0])
        except SystemExit:
            continue
        widths: dict[str, int] = {}
        for code, trend in hb["code_to_description"].items():
            m = _re.fullmatch(r"I(\d+)_(\d+)", code)
            if not m:
                continue
            for label, key in (("Electrode Signal Quality", "esq"),
                               ("Artifact Detector", "artifact_detector"),
                               ("Artifact Intensity", "artifact_intensity")):
                if trend.startswith(label):
                    widths[key] = max(widths.get(key, 0), int(m.group(2)))
        cross.append({
            "recording": d.name,
            "csv": csvs[0].name,
            "channelmap_total": len(chans),
            "eeg_like_channels": len(eeg_like),
            "first_22_channelmap": chans[:22],
            "extra_named_channels": [c for c in eeg_like[22:]],
            **widths,
        })
    ev["cross_recording"] = cross
    ev["esq_width_constant"] = len({c.get("esq") for c in cross}) == 1
    ev["acquisition_counts_vary"] = len({c["eeg_like_channels"] for c in cross}) > 1
    return ev


def main() -> None:
    pqv = json.loads((OUT / "parquet_verification.json").read_text(encoding="utf-8"))
    results = {
        "correlation_attempt": {name: analyse(name, info["parquet_path"])
                                for name, info in pqv.items()},
        "structural_evidence": structural_evidence(),
    }

    (OUT / "channel_order_derivation.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")

    ev = results["structural_evidence"]
    print("\n--- structural evidence ---")
    print(" raw sizes:", ev["raw_output_sizes"])
    print(f" ESQ/AD size ratio = {ev.get('esq_over_ad_size_ratio')} "
          f"(22/18 = {ev.get('expected_22_over_18')})")
    print(f" Persyst per-channel bipolar pairs: {ev['n_persyst_bipolar_pairs']}")
    print(" ", " ".join(ev["persyst_bipolar_pairs"]))
    print(" cross-recording widths:")
    for c in ev["cross_recording"]:
        print(f"   {c['recording']:<22} eeg_like={c['eeg_like_channels']:<3} "
              f"esq={c.get('esq')} ad={c.get('artifact_detector')} "
              f"ai={c.get('artifact_intensity')} extra={c['extra_named_channels']}")
    print(f" ESQ width constant across recordings: {ev['esq_width_constant']}; "
          f"acquisition counts vary: {ev['acquisition_counts_vary']}")
    results = results["correlation_attempt"]

    for name, r in results.items():
        print(f"\n=== {name} ({r['n_rows']:,} rows) ===")
        print(f"  min r of 2nd pick = {r['min_r_top2']}, "
              f"min separation vs 3rd = {r['min_separation']}")
        print(f"  EQ indices never selected: {r['eq_indices_never_selected']}")
        print(f"  EQ degree sequence: {r['eq_degree']}")
        for k, v in r["ordering_scores"].items():
            print(f"  {k:<38} {v['matched']}/{v['of']}")
    print(f"\nwrote {OUT/'channel_order_derivation.json'}")


if __name__ == "__main__":
    main()
