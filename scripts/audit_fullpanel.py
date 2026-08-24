"""Process and verify the full-research-panel export for patient subject-1.

`20260708_1400_.csv` (2.44 GB, 4,103 I-code columns, 369 instruments) is the
full-panel counterpart to the three limited-panel CSVs audited by
`audit_columns.py`. Same checks, one file:

  --parquet  full parse + Parquet conversion + CSV↔Parquet verification
  --stats    column assignment, value stats, spectrogram-family checks

Outputs land in output/audit_fullpanel/.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from audit_columns import read_header_block, _raw_data_lines
from qeeg.ingestion.column_mapper import build_column_schema
from qeeg.ingestion.subcol_validator import validate_subcol_counts, classify_trend
from qeeg.ingestion.identity import derive_patient_id
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import recording_dir  # noqa: E402

CSV_PATH = recording_dir("subject-1_rec") / "20260708_1400_.csv"
OUT = Path(__file__).resolve().parents[1] / "output" / "audit_fullpanel"


def convert_and_verify() -> None:
    from qeeg.ingestion.parser import parse_persyst_csv
    from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
    from qeeg.ingestion.sidecar import read_sidecar
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    hb = read_header_block(CSV_PATH)

    print(f"converting {CSV_PATH.name} ({CSV_PATH.stat().st_size/1e9:.20f} GB) …",
          flush=True)
    pq_path = convert_csv_to_parquet(CSV_PATH)
    print(f"  parquet written: {pq_path.name}", flush=True)

    pf = pq.ParquetFile(pq_path)
    pq_cols = list(pf.schema_arrow.names)
    pq_rows = pf.metadata.num_rows

    header_codes = [c.strip() for c in hb["code_row"] if c.strip()]
    dropped = [c for c in header_codes if c not in pq_cols]
    extra = [c for c in pq_cols if c not in header_codes]

    # Cell-level verification against raw CSV text on a deterministic row sample.
    parsed = parse_persyst_csv(CSV_PATH)   # served from Parquet via DuckDB
    df = parsed.data
    skip = hb["code_row_index"] + 1
    n = pq_rows
    idxs = sorted({0, 1, n // 4, n // 2, (3 * n) // 4, n - 2, n - 1} & set(range(n)))
    raw = _raw_data_lines(CSV_PATH, hb["encoding"], skip, set(idxs))
    pos = {c.strip(): i for i, c in enumerate(hb["code_row"]) if c.strip()}

    checks = {"compared": 0, "match": 0, "mismatch": []}
    for j in idxs:
        cells = raw.get(j)
        if cells is None:
            continue
        for code in pq_cols:
            if code == "ClockDateTime":
                continue
            i = pos.get(code)
            if i is None or i >= len(cells):
                continue
            raw_v = cells[i].strip()
            pq_v = df.iloc[j][code]
            checks["compared"] += 1
            if raw_v == "":
                ok = pd.isna(pq_v)
            else:
                try:
                    ok = (not pd.isna(pq_v)) and abs(float(raw_v) - float(pq_v)) <= \
                        1e-9 * max(1.0, abs(float(raw_v)))
                except (TypeError, ValueError):
                    ok = str(raw_v) == str(pq_v)
            if ok:
                checks["match"] += 1
            elif len(checks["mismatch"]) < 25:
                checks["mismatch"].append(
                    {"row": j, "code": code, "csv": raw_v, "parquet": str(pq_v)})

    clock = {}
    if "ClockDateTime" in pq_cols:
        d = df["ClockDateTime"].diff().dt.total_seconds().iloc[1:]
        gaps = d[d > 1.5]
        clock = {
            "parquet_first": str(df["ClockDateTime"].iloc[0]),
            "parquet_last": str(df["ClockDateTime"].iloc[-1]),
            "csv_header_TestDate": hb["metadata"].test_date,
            "csv_header_TestTime": hb["metadata"].test_time,
            "monotonic_increasing": bool(df["ClockDateTime"].is_monotonic_increasing),
            "median_step_seconds": float(d.median()),
            "step_min": round(float(d.min()), 4),
            "step_max": round(float(d.max()), 1),
            "n_gaps_gt_1_5s": int(len(gaps)),
            "total_gap_seconds": round(float(gaps.sum() - len(gaps)), 1) if len(gaps) else 0.0,
            "largest_gap_seconds": round(float(gaps.max()), 1) if len(gaps) else 0.0,
            "span_seconds": round(float(
                (df["ClockDateTime"].iloc[-1] - df["ClockDateTime"].iloc[0]).total_seconds()), 1),
        }

    sc = read_sidecar(CSV_PATH)
    report = {
        "csv": CSV_PATH.name,
        "csv_bytes": CSV_PATH.stat().st_size,
        "source_dat": hb["metadata"].file_path,
        "derived_patient_id": derive_patient_id(Path(hb["metadata"].file_path).stem),
        "encoding": hb["encoding"],
        "code_row_index": hb["code_row_index"],
        "parquet_path": str(pq_path),
        "parquet_bytes": pq_path.stat().st_size,
        "parquet_columns": len(pq_cols),
        "csv_header_cells": len(header_codes),
        "columns_dropped_all_null": dropped,
        "columns_in_parquet_not_in_header": extra,
        "parquet_rows": pq_rows,
        "sidecar_n_columns": sc.n_columns if sc else None,
        "sidecar_n_data_rows": sc.n_data_rows if sc else None,
        "sidecar_parquet_status": sc.parquet_status if sc else None,
        "spot_check_rows": idxs,
        "spot_check": checks,
        "clock": clock,
        "dtype_counts": {str(k): int(v) for k, v in df.dtypes.value_counts().items()},
    }
    (OUT / "parquet_verification.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"  rows={pq_rows:,} cols={len(pq_cols)} dropped={len(dropped)} "
          f"spot {checks['match']}/{checks['compared']} "
          f"mismatch={len(checks['mismatch'])}", flush=True)
    print(f"wrote {OUT/'parquet_verification.json'}")


def build_stats() -> None:
    from qeeg.ingestion.subcol_schema import get_spectrogram_bin_freq

    OUT.mkdir(parents=True, exist_ok=True)
    info = json.loads((OUT / "parquet_verification.json").read_text(encoding="utf-8"))
    hb = read_header_block(CSV_PATH)
    c2d = hb["code_to_description"]

    schema = build_column_schema(c2d)
    mismatches = validate_subcol_counts(c2d)
    by_code = {e.code: e for e in schema}

    df = pd.read_parquet(info["parquet_path"])
    n = len(df)

    rows = []
    for code, trend in c2d.items():
        e = by_code.get(code)
        s = df[code] if code in df.columns else None
        vals = s.dropna() if s is not None else None
        rows.append({
            "csv_col_index": hb["col_pos"][code],
            "code": code,
            "i_group": e.i_group if e else "",
            "sub_index": e.sub_index if e else "",
            "trend_name": trend,
            "validator_family": classify_trend(trend) or "",
            "mapper_family": e.family if e else "",
            "band": e.frequency_band if e else "",
            "freq_min_hz": e.freq_min_hz if e else "",
            "freq_max_hz": e.freq_max_hz if e else "",
            "hemisphere": e.hemisphere if e else "",
            "region": e.region if e else "",
            "electrode": e.electrode if e else "",
            "sub_column_name": e.sub_column_name if e else "",
            "common_name": e.common_name if e else "",
            "dtype": str(s.dtype) if s is not None else "",
            "pct_null": round(100 * float(s.isna().mean()), 3) if s is not None else "",
            "min": float(vals.min()) if vals is not None and len(vals) else None,
            "median": float(vals.median()) if vals is not None and len(vals) else None,
            "max": float(vals.max()) if vals is not None and len(vals) else None,
            "n_distinct": int(vals.nunique()) if vals is not None else "",
        })
    rows.sort(key=lambda r: r["csv_col_index"])

    cnt = Counter(r["common_name"] for r in rows)
    for r in rows:
        f = []
        if r["mapper_family"] in ("", "other"):
            f.append("UNCLASSIFIED")
        if cnt[r["common_name"]] > 1:
            f.append(f"COLLISION(x{cnt[r['common_name']]})")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(r["common_name"])):
            f.append("INVALID_IDENTIFIER")
        r["review_flag"] = ";".join(f) if f else "OK"
    pd.DataFrame(rows).to_csv(OUT / "column_review_table.csv", index=False)

    collisions = {k: v for k, v in cnt.items() if v > 1}

    # ---- spectrogram-family checks (absent from the limited panel) ----
    spec = {}
    fam_groups = {
        "fft_spectrogram": ("I241", 40), "asymmetry_spectrogram": ("I229", 40),
        "coherence_spectrogram": ("I236", 63), "rhythmicity_spectrogram": ("I270", 97),
        "rhythmicity_freqpow": ("I266", 16),
    }
    for fam, (grp, width) in fam_groups.items():
        cols = [f"{grp}_{i}" for i in range(1, width + 1)]
        cols = [c for c in cols if c in df.columns]
        if not cols:
            continue
        sub = df[cols]
        prof = sub.median()
        peak = int(np.argmax(prof.to_numpy())) + 1
        key = {"fft_spectrogram": "fft_spectrogram",
               "asymmetry_spectrogram": "asymmetry_spectrogram",
               "coherence_spectrogram": "coherence_spectrogram",
               "rhythmicity_spectrogram": "rhythmicity_spectrogram"}.get(fam)
        spec[fam] = {
            "i_group": grp,
            "observed_width": len(cols),
            "expected_width": width,
            "width_ok": len(cols) == width,
            "global_min": round(float(sub.min().min()), 6),
            "global_max": round(float(sub.max().max()), 6),
            "median_profile_peak_bin": peak,
            "peak_bin_freq_hz": (round(get_spectrogram_bin_freq(key, peak), 3)
                                 if key else None),
            "all_null": bool(sub.isna().all().all()),
            "pct_null": round(100 * float(sub.isna().to_numpy().mean()), 3),
        }

    summary = {
        "n_icode_columns": len([c for c in c2d if re.fullmatch(r"I\d+_\d+", c)]),
        "n_instruments": len({r["i_group"] for r in rows if r["i_group"] != ""}),
        "n_rows": n,
        "subcol_mismatches": [
            {"instrument": f"I{m.instrument_index}", "trend_name": m.trend_name,
             "family": m.family, "expected": m.expected, "observed": m.observed,
             "severity": m.severity} for m in mismatches],
        "family_counts": dict(Counter(r["mapper_family"] for r in rows).most_common()),
        "flag_counts": dict(Counter(r["review_flag"] for r in rows).most_common()),
        "n_unclassified": sum(1 for r in rows if r["mapper_family"] in ("", "other")),
        "n_collisions": len(collisions),
        "n_columns_in_collision": sum(collisions.values()),
        "worst_collisions": sorted(collisions.items(), key=lambda x: -x[1])[:15],
        "spectrogram_checks": spec,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                      encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("worst_collisions", "spectrogram_checks")}, indent=1))
    print("\nspectrogram checks:")
    print(json.dumps(spec, indent=1))
    print(f"\nwrote {OUT/'summary.json'}, {OUT/'column_review_table.csv'}")


LIMITED_OUT = Path(__file__).resolve().parents[1] / "output" / "audit_subject-1"


def audit_seam() -> None:
    """Characterise the concatenation seam and identify each block's source segment."""
    OUT.mkdir(parents=True, exist_ok=True)
    info = json.loads((OUT / "parquet_verification.json").read_text(encoding="utf-8"))
    lim = json.loads((LIMITED_OUT / "parquet_verification.json").read_text(encoding="utf-8"))

    f = pd.read_parquet(info["parquet_path"], columns=["ClockDateTime", "Time"])
    t = f["Time"].to_numpy()
    drops = np.where(np.diff(t) <= 0)[0]
    seam_rows = [int(i) + 1 for i in drops]

    # Raw width of every row at/near a seam — a short row means a truncated write.
    hb = read_header_block(CSV_PATH)
    skip = hb["code_row_index"] + 1
    want = set()
    for s in seam_rows:
        want |= {s - 1, s, s + 1}
    widths = {}
    with open(CSV_PATH, "r", encoding=hb["encoding"], newline="") as fh:
        for i, row in enumerate(csv.reader(fh)):
            j = i - skip
            if j in want:
                widths[j] = len(row)
            if want and j > max(want):
                break

    # Block boundaries exclude the seam rows themselves, which are the truncated
    # partial writes and belong to neither block.
    blocks = []
    starts = [0] + [s + 1 for s in seam_rows]
    ends = [s - 1 for s in seam_rows] + [len(f) - 1]
    for a, b in zip(starts, ends):
        blk = f.iloc[a:b + 1]
        blk = blk[blk["ClockDateTime"].notna()]
        if not len(blk):
            continue
        blocks.append({
            "rows": [int(a), int(b)], "n_rows": int(b - a + 1),
            "time_min": int(blk["Time"].min()), "time_max": int(blk["Time"].max()),
            "first_ts": str(blk["ClockDateTime"].iloc[0]),
            "last_ts": str(blk["ClockDateTime"].iloc[-1]),
        })

    # Match each block's timestamp sequence against the limited-panel exports.
    matches = []
    for bi, blk in enumerate(blocks):
        a, b = blk["rows"]
        seq = f["ClockDateTime"].iloc[a:b + 1].reset_index(drop=True)
        seq = seq[seq.notna()].reset_index(drop=True)
        for name, li in lim.items():
            s = pd.read_parquet(li["parquet_path"], columns=["ClockDateTime", "Time"])
            off = int(blk["time_min"])
            tail = s.iloc[off:off + len(seq)]["ClockDateTime"].reset_index(drop=True)
            if len(tail) == len(seq) and tail.equals(seq):
                matches.append({
                    "block": bi, "matches_csv": name,
                    "source_dat": Path(lim[name].get("source_dat", "")).name
                    if lim[name].get("source_dat") else None,
                    "offset_rows_into_that_export": off,
                    "that_export_total_rows": int(len(s)),
                    "rows_missing_before_offset": off,
                    "identical": True,
                })
    out = {
        "csv": CSV_PATH.name,
        "declared_source_dat_in_header": hb["metadata"].file_path,
        "n_rows": int(len(f)),
        "n_seams": len(seam_rows),
        "seam_data_row_indices": seam_rows,
        "row_widths_at_seam": {str(k): v for k, v in sorted(widths.items())},
        "expected_row_width": hb["n_header_cells"],
        "blocks": blocks,
        "block_provenance": matches,
        "null_clockdatetime_rows": [int(i) for i in
                                    f.index[f["ClockDateTime"].isna()].tolist()],
    }
    (OUT / "segment_seam.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))
    print(f"\nwrote {OUT/'segment_seam.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--seam", action="store_true")
    a = ap.parse_args()
    if a.parquet:
        convert_and_verify()
    if a.stats:
        build_stats()
    if a.seam:
        audit_seam()
    if not (a.parquet or a.stats or a.seam):
        ap.print_help()
