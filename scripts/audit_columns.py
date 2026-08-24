"""Column-assignment audit for patient subject-1 (three limited-research-panel CSVs).

Stage 1 (--headers): header-only scan. Builds the column schema from the CSV
code row + trend row, runs the sub-column contract validator, cross-checks
family/channel assignment against every MMX in scope, and writes the raw
evidence tables. No data rows are read.

Stage 2 (--parquet): full parse + Parquet conversion, then verifies the Parquet
against the CSV (column identity, row count, dtypes, and cell-level equality on
a deterministic sample of rows/columns read straight from the CSV text).

Outputs land in output/audit_subject-1/.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from qeeg.ingestion.parser import (
    ExportMetadata,
    detect_encoding,
    _extract_metadata,
    _fill_forward,
    _find_code_row,
)
from qeeg.ingestion.column_mapper import build_column_schema, build_column_schema_with_mmx
from qeeg.ingestion.subcol_validator import validate_subcol_counts, classify_trend
from qeeg.ingestion.identity import derive_patient_id
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import export_dir, recording_dir  # noqa: E402

PATIENT_DIR = recording_dir("subject-1_rec")
SHARE_ROOT = export_dir()
CSVS = [
    "20260707_1358_.csv",
    "20260707_1413_.csv",
    "20260707_1449_.csv",
]
OUT = Path(__file__).resolve().parents[1] / "output" / "audit_subject-1"


def read_header_block(path: Path) -> dict:
    """Return metadata + code row + fill-forwarded trend row, reading only the header."""
    encoding = detect_encoding(path)
    with open(path, "r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 61:
                break
    meta = _extract_metadata(rows)
    code_idx = _find_code_row(rows)
    if code_idx is None:
        raise SystemExit(f"no code row found in {path}")
    code_row = rows[code_idx]
    trend_row = list(rows[code_idx - 1])
    while len(trend_row) < len(code_row):
        trend_row.append("")
    filled = _fill_forward(trend_row)

    code_to_description: dict[str, str] = {}
    col_pos: dict[str, int] = {}
    for i, code in enumerate(code_row):
        code = code.strip()
        if not code or code == "ClockDateTime":
            continue
        code_to_description[code] = filled[i] if i < len(filled) else ""
        col_pos[code] = i

    return {
        "encoding": encoding,
        "metadata": meta,
        "code_row_index": code_idx,
        "trend_row_index": code_idx - 1,
        "code_row": code_row,
        "raw_trend_row": rows[code_idx - 1],
        "filled_trends": filled,
        "code_to_description": code_to_description,
        "col_pos": col_pos,
        "n_header_cells": len(code_row),
    }


def load_mmx_candidates() -> dict[str, object]:
    from qeeg.ingestion.mmx_parser import parse_mmx

    out = {}
    cands = sorted(SHARE_ROOT.glob("*.mmx")) + sorted(PATIENT_DIR.glob("*.mmx"))
    for p in cands:
        try:
            out[str(p)] = parse_mmx(p)
        except Exception as exc:  # noqa: BLE001
            out[str(p)] = f"PARSE FAILED: {exc}"
    return out


def audit_headers() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mmxs = load_mmx_candidates()

    summary = {}
    per_file_rows: dict[str, list[dict]] = {}

    for name in CSVS:
        path = PATIENT_DIR / name
        hb = read_header_block(path)
        c2d = hb["code_to_description"]
        meta: ExportMetadata = hb["metadata"]

        schema = build_column_schema(c2d)
        mismatches = validate_subcol_counts(c2d)

        # MMX cross-check: which MMX (if any) contains every trend name?
        mmx_cover = {}
        for mp, mm in mmxs.items():
            if isinstance(mm, str):
                mmx_cover[mp] = {"error": mm}
                continue
            names = set(mm.instruments.keys())
            trends = {t for t in c2d.values() if t}
            hit = trends & names
            mmx_cover[mp] = {
                "mmx_instruments": len(names),
                "csv_distinct_trends": len(trends),
                "matched": len(hit),
                "unmatched": sorted(trends - names)[:20],
                "unmatched_count": len(trends - names),
            }

        # Pick the template by PROVENANCE, not by trend-name match count.
        #
        # Scoring on `matched` picks whichever candidate happens to share the most
        # trend names with the CSV — but MMX instrument names are internal
        # expressions and the CSV carries display labels, so that metric tops out
        # near zero and effectively chooses at random among the V6/V7/.mg2 files
        # sitting on the share. It selected a template whose Research-Trends panel
        # is not 230, which disabled ordinal resolution and silently regenerated
        # this audit with the pre-remediation behaviour (pd_max, sleep_stage_display
        # x7 all came back).
        #
        # Preference order: the per-recording .mg2.mmx snapshot Persyst wrote for
        # this recording, then the committed template. Each candidate is checked
        # against the ordinal invariant, which is self-validating: only the right
        # template has a panel of size max(i_group) - 2.
        from qeeg.ingestion.column_mapper import resolve_export_panel

        max_ig = max((int(c[1:].split("_")[0]) for c in c2d
                      if c.startswith("I") and "_" in c
                      and c[1:].split("_")[0].isdigit()), default=0)

        def _rank(path: str) -> tuple:
            name = Path(path).name.lower()
            return (0 if name.endswith(".mg2.mmx") else
                    1 if "v8" in name else 2, name)

        best_mmx = None
        for mp in sorted((p for p, i in mmx_cover.items() if "error" not in i), key=_rank):
            cfg = mmxs[mp]
            if resolve_export_panel(cfg, max_ig) is not None:
                best_mmx = mp
                break
        if best_mmx is None:
            print(f"  !! no candidate MMX satisfies the ordinal invariant for "
                  f"max I{max_ig}; column identity is NOT trustworthy")

        mmx_schema = None
        if best_mmx:
            mmx_schema = build_column_schema_with_mmx(c2d, mmxs[best_mmx])
            print(f"  mmx: {Path(best_mmx).name}")

        by_code = {e.code: e for e in schema}
        mmx_by_code = {e.code: e for e in (mmx_schema or [])}

        rows = []
        for code, trend in c2d.items():
            e = by_code.get(code)
            m = mmx_by_code.get(code)
            rows.append({
                "csv": name,
                "csv_col_index": hb["col_pos"][code],
                "code": code,
                "i_group": e.i_group if e else "",
                "sub_index": e.sub_index if e else "",
                "trend_name": trend,
                "validator_family": classify_trend(trend) or "",
                "mapper_family": e.family if e else "",
                "mmx_family": m.family if m else "",
                "family_agrees": (bool(m) and m.family == e.family) if e else "",
                "band": e.frequency_band if e else "",
                "freq_min_hz": e.freq_min_hz if e else "",
                "freq_max_hz": e.freq_max_hz if e else "",
                "hemisphere": e.hemisphere if e else "",
                "region": e.region if e else "",
                "electrode": e.electrode if e else "",
                "sub_column_name": e.sub_column_name if e else "",
                "common_name": e.common_name if e else "",
                "mmx_common_name": m.common_name if m else "",
                "common_name_agrees": (bool(m) and m.common_name == e.common_name) if e else "",
            })
        rows.sort(key=lambda r: r["csv_col_index"])
        per_file_rows[name] = rows

        # Collision analysis on common_name (the export identifier)
        cn = Counter(r["common_name"] for r in rows)
        collisions = {k: v for k, v in cn.items() if v > 1}
        coll_detail = defaultdict(list)
        for r in rows:
            if r["common_name"] in collisions:
                coll_detail[r["common_name"]].append(
                    {"code": r["code"], "trend_name": r["trend_name"]}
                )

        unclassified = [r for r in rows if r["mapper_family"] in ("", "other")]
        no_common = [r for r in rows if not r["common_name"]]

        summary[name] = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "encoding": hb["encoding"],
            "source_dat": meta.file_path,
            "dat_stem": Path(meta.file_path).stem if meta.file_path else "",
            "derived_patient_id": derive_patient_id(
                Path(meta.file_path).stem if meta.file_path else ""
            ),
            "test_date": meta.test_date,
            "test_time": meta.test_time,
            "code_row_index": hb["code_row_index"],
            "trend_row_index": hb["trend_row_index"],
            "header_cells": hb["n_header_cells"],
            "n_icode_columns": len(c2d),
            "n_instruments": len({r["i_group"] for r in rows}),
            "n_distinct_trend_names": len({r["trend_name"] for r in rows}),
            "family_counts": dict(Counter(r["mapper_family"] for r in rows).most_common()),
            "subcol_mismatches": [
                {
                    "instrument": f"I{m.instrument_index}",
                    "trend_name": m.trend_name,
                    "family": m.family,
                    "expected": m.expected,
                    "observed": m.observed,
                    "severity": m.severity,
                    "detail": m.detail,
                }
                for m in mismatches
            ],
            "mmx_coverage": mmx_cover,
            "best_mmx": best_mmx,
            "n_unclassified": len(unclassified),
            "unclassified": [
                {"code": r["code"], "trend_name": r["trend_name"]} for r in unclassified
            ],
            "n_empty_common_name": len(no_common),
            "n_common_name_collisions": len(collisions),
            "common_name_collisions": {k: coll_detail[k] for k in sorted(collisions)},
            "n_family_disagreements_vs_mmx": sum(
                1 for r in rows if r["family_agrees"] is False
            ),
            "family_disagreements_vs_mmx": [
                {
                    "code": r["code"],
                    "trend_name": r["trend_name"],
                    "mapper_family": r["mapper_family"],
                    "mmx_family": r["mmx_family"],
                }
                for r in rows
                if r["family_agrees"] is False
            ][:50],
        }

    # Cross-file consistency: is the column layout identical across the 3 CSVs?
    sigs = {}
    for name, rows in per_file_rows.items():
        sigs[name] = [(r["code"], r["trend_name"]) for r in rows]
    ref_name = CSVS[0]
    cross = {}
    for name in CSVS[1:]:
        cross[name] = {
            "identical_to_" + ref_name: sigs[name] == sigs[ref_name],
            "n_columns": len(sigs[name]),
            "n_columns_ref": len(sigs[ref_name]),
            "first_difference": next(
                (
                    {"index": i, "ref": sigs[ref_name][i], "this": sigs[name][i]}
                    for i in range(min(len(sigs[name]), len(sigs[ref_name])))
                    if sigs[name][i] != sigs[ref_name][i]
                ),
                None,
            ),
        }

    (OUT / "header_audit.json").write_text(
        json.dumps({"per_file": summary, "cross_file": cross}, indent=2, default=str),
        encoding="utf-8",
    )

    all_rows = [r for name in CSVS for r in per_file_rows[name]]
    pd.DataFrame(all_rows).to_csv(OUT / "column_assignments.csv", index=False)
    print(f"wrote {OUT/'header_audit.json'}")
    print(f"wrote {OUT/'column_assignments.csv'} ({len(all_rows)} rows)")
    for name in CSVS:
        s = summary[name]
        print(
            f"{name}: {s['n_icode_columns']} cols / {s['n_instruments']} instruments, "
            f"subcol mismatches={len(s['subcol_mismatches'])}, "
            f"unclassified={s['n_unclassified']}, collisions={s['n_common_name_collisions']}, "
            f"mmx_family_disagreements={s['n_family_disagreements_vs_mmx']}"
        )


def _raw_data_lines(path: Path, encoding: str, skip: int, wanted: set[int]) -> dict[int, list[str]]:
    """Return {data_row_index: raw split cells} for the requested data-row indices."""
    out: dict[int, list[str]] = {}
    if not wanted:
        return out
    last = max(wanted)
    with open(path, "r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            j = i - skip
            if j < 0:
                continue
            if j in wanted:
                out[j] = row
            if j >= last:
                break
    return out


def convert_and_verify() -> None:
    from qeeg.ingestion.parser import parse_persyst_csv
    from qeeg.ingestion.parquet_convert import convert_csv_to_parquet
    from qeeg.ingestion.sidecar import read_sidecar
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    report = {}

    for name in CSVS:
        path = PATIENT_DIR / name
        hb = read_header_block(path)
        print(f"--- {name}: converting …", flush=True)
        pq_path = convert_csv_to_parquet(path)
        parsed = parse_persyst_csv(path)          # now served from Parquet via DuckDB
        df = parsed.data
        sc = read_sidecar(path)

        pf = pq.ParquetFile(pq_path)
        pq_cols = list(pf.schema_arrow.names)
        pq_rows = pf.metadata.num_rows

        header_codes = [c.strip() for c in hb["code_row"] if c.strip()]
        dropped = [c for c in header_codes if c not in pq_cols]
        extra = [c for c in pq_cols if c not in header_codes]

        # ---- cell-level spot check against the raw CSV text ----
        skip = hb["code_row_index"] + 1
        n = pq_rows
        idxs = sorted({0, 1, n // 4, n // 2, (3 * n) // 4, n - 2, n - 1} & set(range(n)))
        raw = _raw_data_lines(path, hb["encoding"], skip, set(idxs))
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
                        ok = (not pd.isna(pq_v)) and abs(float(raw_v) - float(pq_v)) <= 1e-9 * max(
                            1.0, abs(float(raw_v))
                        )
                    except (TypeError, ValueError):
                        ok = str(raw_v) == str(pq_v)
                if ok:
                    checks["match"] += 1
                elif len(checks["mismatch"]) < 25:
                    checks["mismatch"].append(
                        {"row": j, "code": code, "csv": raw_v, "parquet": str(pq_v)}
                    )

        # ---- ClockDateTime: Excel serial → timestamp ----
        clock = {}
        if "ClockDateTime" in pq_cols:
            ci = pos["ClockDateTime"]
            serials = {j: raw[j][ci] for j in idxs if j in raw and ci < len(raw[j])}
            first_serial = float(serials[idxs[0]])
            clock = {
                "raw_serial_first": first_serial,
                "parquet_first": str(df["ClockDateTime"].iloc[0]),
                "parquet_last": str(df["ClockDateTime"].iloc[-1]),
                "dtype": str(df["ClockDateTime"].dtype),
                "monotonic_increasing": bool(df["ClockDateTime"].is_monotonic_increasing),
                "csv_header_TestDate": hb["metadata"].test_date,
                "csv_header_TestTime": hb["metadata"].test_time,
                "median_step_seconds": float(
                    df["ClockDateTime"].diff().dt.total_seconds().median()
                ),
                "duration_hours": float(
                    (df["ClockDateTime"].iloc[-1] - df["ClockDateTime"].iloc[0]).total_seconds()
                    / 3600.0
                ),
            }

        report[name] = {
            "parquet_path": str(pq_path),
            "parquet_bytes": pq_path.stat().st_size,
            "csv_bytes": path.stat().st_size,
            "parquet_columns": len(pq_cols),
            "csv_header_codes": len(header_codes),
            "columns_dropped_all_null": dropped,
            "columns_in_parquet_not_in_header": extra,
            "parquet_rows": pq_rows,
            "dataframe_rows": len(df),
            "sidecar_n_columns": sc.n_columns if sc else None,
            "sidecar_n_data_rows": sc.n_data_rows if sc else None,
            "sidecar_parquet_status": sc.parquet_status if sc else None,
            "sidecar_code_row_index": sc.code_row_index if sc else None,
            "spot_check_rows": idxs,
            "spot_check": checks,
            "clock": clock,
            "dtype_counts": {str(k): int(v) for k, v in df.dtypes.value_counts().items()},
            "all_null_columns_in_parquet": [
                c for c in pq_cols if c != "ClockDateTime" and df[c].isna().all()
            ],
        }
        print(
            f"    parquet={pq_path.name} rows={pq_rows} cols={len(pq_cols)} "
            f"dropped={len(dropped)} spot {checks['match']}/{checks['compared']} "
            f"mismatch={len(checks['mismatch'])}",
            flush=True,
        )

    (OUT / "parquet_verification.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"wrote {OUT/'parquet_verification.json'}")


def build_stats() -> None:
    """Stage 3: per-column value stats, semantic checks, and the merged review table."""
    import re
    import numpy as np

    pqv = json.loads((OUT / "parquet_verification.json").read_text(encoding="utf-8"))
    assign = pd.read_csv(OUT / "column_assignments.csv")
    by_file = {c: g.set_index("code").to_dict("index") for c, g in assign.groupby("csv")}

    stats_rows: list[dict] = []
    sem: dict[str, dict] = {}
    slp: dict[str, dict] = {}
    tax: dict[str, dict] = {}

    for name, info in pqv.items():
        df = pd.read_parquet(info["parquet_path"])
        n = len(df)

        # ---- per-column value stats ----
        for code in df.columns:
            if code == "ClockDateTime":
                continue
            s = df[code]
            vals = s.dropna()
            uniq = vals.unique()
            a = by_file[name].get(code, {})
            stats_rows.append({
                "csv": name, "code": code,
                "common_name": a.get("common_name", ""),
                "family": a.get("mapper_family", ""),
                "sub_column_name": a.get("sub_column_name", ""),
                "trend_name": a.get("trend_name", ""),
                "dtype": str(s.dtype), "n": n, "n_null": int(s.isna().sum()),
                "pct_null": round(100 * s.isna().sum() / n, 3),
                "min": float(vals.min()) if len(vals) else None,
                "p01": float(vals.quantile(.01)) if len(vals) else None,
                "median": float(vals.median()) if len(vals) else None,
                "p99": float(vals.quantile(.99)) if len(vals) else None,
                "max": float(vals.max()) if len(vals) else None,
                "n_distinct": int(len(uniq)),
                "is_binary_01": bool(len(uniq) and set(np.unique(uniq)).issubset({0, 1})),
            })

        # ---- semantic checks (§4) ----
        r: dict = {}
        for grp, lab in [("I1", "all"), ("I2", "left"), ("I3", "right"),
                         ("I4", "anterior"), ("I5", "posterior")]:
            mx, mn, p50, p75, p25 = [df[f"{grp}_{i}"] for i in (1, 2, 3, 4, 5)]
            ok = (mn <= p25) & (p25 <= p50) & (p50 <= p75) & (p75 <= mx)
            r[f"aeeg_{lab}_order_ok_pct"] = round(100 * ok.mean(), 4)
            r[f"aeeg_{lab}_violations"] = int((~ok).sum())
        s4 = df["I213_1"] + df["I222_1"] + df["I195_1"] + df["I204_1"]
        r["relpower_all_sum_median"] = round(float(s4.median()), 6)
        r["relpower_all_sum_min"] = round(float(s4.min()), 6)
        r["relpower_all_sum_max"] = round(float(s4.max()), 6)
        r["relpower_all_sum_within_1pct"] = round(100 * float(((s4 - 1).abs() < 0.01).mean()), 4)
        r["rav_I94_vs_relalpha_I195_identical"] = bool(df["I94_1"].equals(df["I195_1"]))
        r["rav_I94_vs_relalpha_I195_corr"] = round(float(df["I94_1"].corr(df["I195_1"])), 4)
        r["rav_I94_vs_relalpha_I195_max_absdiff"] = round(
            float((df["I94_1"] - df["I195_1"]).abs().max()), 6)
        ok = ((df["I139_1"] <= df["I140_1"]) & (df["I140_1"] <= df["I141_1"])
              & (df["I141_1"] <= df["I130_1"]))
        r["sef_monotonic_pct"] = round(100 * ok.mean(), 4)
        r["sef_violations"] = int((~ok).sum())
        r["pd_cols_binary"] = {c: sorted(map(float, pd.unique(df[c].dropna())))
                               for c in ["I19_1", "I20_1", "I21_1", "I22_1", "I23_1", "I24_1"]}
        r["seizure_cols_allzero"] = {c: bool((df[c] == 0).all())
                                     for c in ["I142_1", "I142_2", "I143_1", "I144_1", "I145_1"]}
        for a_, b_ in [("I144_1", "I145_1"), ("I166_1", "I167_1"), ("I168_1", "I169_1"),
                       ("I156_1", "I164_1"), ("I163_1", "I165_1")]:
            r[f"{a_[:-2]}_equals_{b_[:-2]}"] = bool(df[a_].equals(df[b_]))
        eq = [f"I30_{i}" for i in range(1, 23)]
        ad = [f"I6_{i}" for i in range(1, 19)]
        r["electrode_quality_global_max"] = round(float(df[eq].max().max()), 6)
        r["artifact_detector_global_max"] = round(float(df[ad].max().max()), 6)
        r["artifact_detector_binary"] = bool(np.isin(df[ad].to_numpy(), [0, 1]).all())
        sem[name] = r

        # ---- sleep one-hot (§4.5) ----
        ind = [f"I{i}_1" for i in range(147, 153)]
        slp[name] = {
            "onehot_sum_is_1_pct": round(100 * float((df[ind].sum(axis=1) == 1).mean()), 4),
            "I146_equals_I153": bool(df["I146_1"].equals(df["I153_1"])),
            "indicator_to_I146_code": {
                c: sorted(map(int, pd.unique(df.loc[df[c] == 1, "I146_1"]))) for c in ind
            },
        }

        # ---- time axis (§3.3, §5.3) ----
        d = df["ClockDateTime"].diff().dt.total_seconds().iloc[1:]
        gaps = d[d > 1.5]
        icodes = [c for c in df.columns if re.fullmatch(r"I\d+_\d+", str(c))]
        tax[name] = {
            "parquet_columns": info["parquet_columns"],
            "n_icode_columns": len(icodes),
            "n_non_icode_named_columns": sorted(
                set(df.columns) - set(icodes) - {"ClockDateTime"}),
            "time_is_row_counter": bool((df["Time"].to_numpy() == range(n)).all()),
            "n_gaps_gt_1_5s": int(len(gaps)),
            "total_gap_seconds": round(float(gaps.sum() - len(gaps)), 1),
            "largest_gap_seconds": round(float(gaps.max()), 1) if len(gaps) else 0.0,
            "step_min": round(float(d.min()), 4), "step_max": round(float(d.max()), 1),
            "rows": n,
            "span_seconds": round(float(
                (df["ClockDateTime"].iloc[-1] - df["ClockDateTime"].iloc[0]).total_seconds()), 1),
        }

    st = pd.DataFrame(stats_rows)
    st.to_csv(OUT / "column_value_stats.csv", index=False)
    (OUT / "semantic_checks.json").write_text(json.dumps(sem, indent=2), encoding="utf-8")
    (OUT / "sleep_onehot_check.json").write_text(json.dumps(slp, indent=2), encoding="utf-8")
    (OUT / "time_axis_check.json").write_text(json.dumps(tax, indent=2), encoding="utf-8")

    # ---- merged review table with flags ----
    import re as _re
    m = assign.merge(
        st[["csv", "code", "dtype", "pct_null", "min", "p01", "median", "p99", "max",
            "n_distinct", "is_binary_01"]],
        on=["csv", "code"], how="left")
    flag_by_key: dict[tuple, str] = {}
    for csv_name, grp in m.groupby("csv"):
        cnt = Counter(grp["common_name"])
        for _, row in grp.iterrows():
            f = []
            if row["mapper_family"] in ("", "other"):
                f.append("UNCLASSIFIED")
            if cnt[row["common_name"]] > 1:
                f.append(f"COLLISION(x{cnt[row['common_name']]})")
            if not _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(row["common_name"])):
                f.append("INVALID_IDENTIFIER")
            flag_by_key[(csv_name, row["code"])] = ";".join(f) if f else "OK"
    m["review_flag"] = [flag_by_key[(c, k)] for c, k in zip(m["csv"], m["code"])]
    m = m.sort_values(["csv", "csv_col_index"])
    cols = ["csv", "csv_col_index", "code", "i_group", "sub_index", "trend_name",
            "mapper_family", "validator_family", "sub_column_name", "common_name",
            "review_flag", "band", "freq_min_hz", "freq_max_hz", "hemisphere", "region",
            "electrode", "dtype", "pct_null", "min", "p01", "median", "p99", "max",
            "n_distinct", "is_binary_01"]
    m[cols].to_csv(OUT / "column_review_table.csv", index=False)
    print(f"wrote column_value_stats.csv, semantic_checks.json, sleep_onehot_check.json, "
          f"time_axis_check.json, column_review_table.csv ({len(m)} rows)")


V8_MMX = Path(__file__).resolve().parents[1] / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"
EXPORT_PANEL = "Research-Trends"

# Persyst appends these two pseudo-columns after the panel instruments; they
# have no MMX instrument by design. Mirrors column_mapper.TAIL_PSEUDO_COLUMNS.
TAIL_PSEUDO_COLUMNS = 2

# Persyst omits 2-D spectrogram instruments from a trend CSV export. Identified by
# MMX instrument Name prefix.
_SPECTROGRAM_PREFIXES = (
    "Asymmetry, Relative Spectrogram",
    "FFT_Spectrogram",
    "Rhythmicity Spectrogram",
    "Coherence_Spectrogram",
)


def _load_export_panel(mmx_path: Path, panel_name: str) -> tuple[list[dict], list[dict]]:
    """Return (kept, dropped) instrument attribute dicts for *panel_name*, in panel order.

    Each dict gains `_panel_pos` (1-based position within the panel).
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(mmx_path).getroot()
    inst_el = root.find("Instruments")
    defs: dict[str, dict] = {}
    for container in [inst_el] + list(inst_el.findall("Montage")):
        for el in container:
            if el.tag == "Instrument":
                defs[el.get("InstanceID")] = dict(el.attrib)

    panels = [p for p in root.findall("Panel") if p.get("Name") == panel_name]
    if not panels:
        raise SystemExit(f"panel {panel_name!r} not found in {mmx_path}")

    kept, dropped = [], []
    for i, ref in enumerate(panels[0]):
        d = dict(defs.get(ref.get("InstanceID"), {"Name": ref.get("Name", ""),
                                                  "GraphTitle": "", "Channels": ""}))
        d["_panel_pos"] = i + 1
        (dropped if d.get("Name", "").startswith(_SPECTROGRAM_PREFIXES) else kept).append(d)
    return kept, dropped


def audit_mmx() -> None:
    """Stage 4: align CSV I-groups to the V8 MMX export panel and adjudicate assignments."""
    import re

    OUT.mkdir(parents=True, exist_ok=True)
    kept, dropped = _load_export_panel(V8_MMX, EXPORT_PANEL)

    import xml.etree.ElementTree as _ET
    n_panels = len(_ET.parse(V8_MMX).getroot().findall("Panel"))

    alignment: dict = {
        "mmx_path": str(V8_MMX),
        "mmx_bytes": V8_MMX.stat().st_size,
        "mmx_panel_count": n_panels,
        "export_panel": EXPORT_PANEL,
        "panel_instruments": len(kept) + len(dropped),
        "spectrogram_excluded": [
            {"panel_pos": d["_panel_pos"], "mmx_name": d.get("Name", "")} for d in dropped
        ],
        "exported_instruments": len(kept),
        "per_file": {},
    }

    rows: list[dict] = []
    for name in CSVS:
        hb = read_header_block(PATIENT_DIR / name)
        groups: dict[int, dict] = {}
        for code, trend in hb["code_to_description"].items():
            m = re.fullmatch(r"I(\d+)_(\d+)", code)
            if not m:
                continue
            g, sub = int(m.group(1)), int(m.group(2))
            rec = groups.setdefault(g, {"trend": trend, "n_sub": 0})
            rec["n_sub"] = max(rec["n_sub"], sub)

        order = sorted(groups)
        # Persyst appends Comment and Time after the panel's instruments, so the
        # export carries exactly two more I-groups than the panel has. Comparing
        # the raw counts made this read False on every well-formed export.
        n_match = len(order) == len(kept) + TAIL_PSEUDO_COLUMNS
        mismatches = []
        if n_match:
            for k, g in enumerate(order[:len(kept)]):
                d = kept[k]
                # The CSV trend name always begins with the instrument's display
                # label, which is GraphTitle when set and the instrument Name when
                # GraphTitle is empty. That is the alignment assertion.
                label = d.get("GraphTitle", "").strip() or d.get("Name", "").strip()
                trend = groups[g]["trend"]
                if not (label and trend.startswith(label)):
                    mismatches.append({
                        "i_group": f"I{g}", "panel_pos": d["_panel_pos"],
                        "mmx_label": label, "mmx_name": d.get("Name", "")[:120],
                        "csv_trend_name": trend,
                    })

        alignment["per_file"][name] = {
            "csv_i_groups": len(order),
            "count_matches_panel": n_match,
            "graph_title_prefix_mismatches": len(mismatches),
            "mismatch_detail": mismatches[:20],
        }

        if name == CSVS[0] and n_match and not mismatches:
            # Only the panel instruments have an MMX definition; the trailing
            # Comment/Time groups do not, so stop at len(kept).
            for k, g in enumerate(order[:len(kept)]):
                d = kept[k]
                rows.append({
                    "i_group": f"I{g}",
                    "panel_pos": d["_panel_pos"],
                    "n_sub_columns": groups[g]["n_sub"],
                    "csv_trend_name": groups[g]["trend"],
                    "mmx_name": d.get("Name", ""),
                    "mmx_graph_title": d.get("GraphTitle", ""),
                    "mmx_channels": d.get("Channels", ""),
                    "mmx_freq_min": d.get("FreqMin", ""),
                    "mmx_freq_max": d.get("FreqMax", ""),
                    "mmx_freq_min_denom": d.get("FreqMinDenom", ""),
                    "mmx_freq_max_denom": d.get("FreqMaxDenom", ""),
                    "mmx_cls_id": d.get("ClsId", ""),
                })

    (OUT / "mmx_alignment.json").write_text(
        json.dumps(alignment, indent=2), encoding="utf-8")
    imap = pd.DataFrame(rows)
    imap.to_csv(OUT / "mmx_instrument_map.csv", index=False)

    # Fold the MMX identity into the per-column review table (join on I-group;
    # every sub-column of an instrument inherits its MMX definition).
    rt_path = OUT / "column_review_table.csv"
    if rt_path.exists() and len(imap):
        tbl = pd.read_csv(rt_path)
        tbl = tbl.drop(columns=[c for c in tbl.columns if c.startswith("mmx_")
                                or c == "panel_pos"], errors="ignore")
        keep = ["i_group", "panel_pos", "mmx_name", "mmx_graph_title", "mmx_channels",
                "mmx_freq_min", "mmx_freq_max", "mmx_freq_min_denom", "mmx_freq_max_denom"]
        tbl["_ig"] = tbl["i_group"].apply(
            lambda v: f"I{int(v)}" if pd.notna(v) else "")
        tbl = tbl.merge(imap[keep].rename(columns={"i_group": "_ig"}), on="_ig", how="left")
        tbl = tbl.drop(columns=["_ig"]).sort_values(["csv", "csv_col_index"])
        tbl.to_csv(rt_path, index=False)
        print(f"merged MMX identity into {rt_path.name}")

    print(f"panel={alignment['panel_instruments']} "
          f"excluded={len(dropped)} exported={len(kept)}")
    for name, info in alignment["per_file"].items():
        print(f"  {name}: I-groups={info['csv_i_groups']} "
              f"count_match={info['count_matches_panel']} "
              f"prefix_mismatches={info['graph_title_prefix_mismatches']}")
    print(f"wrote mmx_alignment.json, mmx_instrument_map.csv ({len(rows)} instruments)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--headers", action="store_true")
    ap.add_argument("--parquet", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--mmx", action="store_true")
    args = ap.parse_args()
    if args.headers:
        audit_headers()
    if args.parquet:
        convert_and_verify()
    if args.stats:
        build_stats()
    if args.mmx:
        audit_mmx()
    if not (args.headers or args.parquet or args.stats or args.mmx):
        ap.print_help()
