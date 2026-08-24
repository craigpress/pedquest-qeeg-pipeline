"""Reprocess the cardiac-arrest cohort from the V10 afternoon exports.

Drives PipelineService rather than calling process_patient directly, so the
de-identified-date correction and synthetic-ROSC reconstruction happen exactly as
they do in the app. These exports carry no real dates — PatientBirthDate is the
string "16 yo" — so ROSC alignment only works once each segment's
eeg_date_correction.csv has been applied; calling the pipeline without that path
trims every row as "pre-ROSC" and produces an empty frame.

Only the post-rename ("afternoon") exports are used. The morning set predates the
V10 trend renames and still carries duplicate labels for rhythmic delta and the
spike laterality instruments.

Usage:
    python scripts/reprocess_cohort.py [--limit N]
"""
from __future__ import annotations

import csv
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.disable(logging.WARNING)

from api.services.pipeline_service import (            # noqa: E402
    ClinicalMetadata, EEGCorrection, PipelineService,
)
from qeeg.config import PipelineConfig                 # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import export_dir  # noqa: E402

COHORT = export_dir()
CLINICAL = export_dir() / "clinical.csv"
MMX = Path(r"C:\ProgramData\Persyst\PedQuEST_Pennsieve_V10_research.mmx")
STUDY = "PedQuEST-V10"
RENAME_CUTOFF = "20260821_12"


def _clinical() -> list[ClinicalMetadata]:
    """clinical.csv has a corrupt header — "rosc_timeage_at_arrest_days" is two
    column names run together — so fields are read positionally:
    [patient_id, rosc_time, age_at_arrest_days]."""
    out = []
    with open(CLINICAL, encoding="utf-8", errors="replace", newline="") as fh:
        for i, row in enumerate(csv.reader(fh)):
            if i == 0 or len(row) < 3 or not row[0].strip():
                continue
            try:
                age = int(float(row[2]))
            except ValueError:
                continue
            t = row[1].strip()
            if not t:
                continue
            if t.count(":") == 1:                 # HH:MM -> HH:MM:SS
                t = f"{t}:00"
            out.append(ClinicalMetadata(patient_id=row[0].strip(),
                                        rosc_time=t, age_at_arrest_days=age))
    return out


def _corrections() -> list[EEGCorrection]:
    out = []
    for f in COHORT.glob("*/eeg_date_correction.csv"):
        with open(f, encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                if not (row.get("new_name") or "").strip():
                    continue
                try:
                    age = int(float(row["age_in_days_at_time_of_eeg"]))
                except (KeyError, ValueError):
                    continue
                out.append(EEGCorrection(
                    new_name=row["new_name"].strip(),
                    age_in_days_at_time_of_eeg=age,
                    eeg_start_time=(row.get("eeg_start_time") or "").strip(),
                    eeg_duration=(row.get("eeg_duration") or "").strip(),
                    date_of_csv_creation=(row.get("date_of_csv_creation") or "").strip(),
                ))
    return out


def _cache_evidence(pid: str) -> tuple[str, dict]:
    """Read the AR warning and per-class NaN/zero counts from the written cache."""
    import glob
    import pandas as pd

    dirs = sorted(glob.glob(f".qeeg_cache/*_{pid}"), key=lambda d: Path(d).stat().st_mtime)
    if not dirs:
        return "", {}
    d = Path(dirs[-1])
    warn = ""
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        warn = next((w for w in meta.get("warnings", []) if w.startswith("AR rejection")), "")
    except Exception:                                    # noqa: BLE001
        pass
    probe: dict = {}
    try:
        df = pd.read_parquet(d / "epochs.parquet")
        # One representative column per zero-semantics class.
        for label, col in (("impossible", "fft_delta_all"),
                           ("legitimate", "suppression_all"),
                           ("never_null", "rhythmic_delta_lad")):
            if col in df.columns:
                probe[f"{label}_zeros"] = int((df[col] == 0).sum())
                probe[f"{label}_nan"] = int(df[col].isna().sum())
    except Exception:                                    # noqa: BLE001
        pass
    return warn, probe


def main() -> None:
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None

    svc = PipelineService(upload_dir=ROOT / ".uploads")
    svc.store_clinical_metadata(_clinical())
    corr = _corrections()
    svc.store_eeg_corrections(corr)

    import hashlib
    from qeeg.ingestion.mmx_parser import parse_mmx
    cfg_mmx = parse_mmx(MMX)
    svc.store_mmx_config(STUDY, cfg_mmx.engines,
                         hashlib.sha256(MMX.read_bytes()).hexdigest(), str(MMX))
    svc.create_study(STUDY, mmx_study=STUDY, date_shifted=True)

    folders = sorted(p for p in COHORT.iterdir() if p.is_dir())
    if limit:
        folders = folders[:limit]

    results = []
    for folder in folders:
        pid = folder.name.split("_")[0]
        paths = sorted(p for p in folder.glob("2026*.csv") if p.stem >= RENAME_CUTOFF)
        if not paths:
            results.append({"patient_id": pid, "err": "no afternoon exports"})
            print(json.dumps(results[-1]), flush=True)
            continue

        file_ids = []
        for p in paths:
            fid = f"{p.stem}_{hashlib.sha1(str(p).encode()).hexdigest()[:8]}"
            (svc.upload_dir / f"{fid}.ptr").write_text(str(p), encoding="utf-8")
            file_ids.append(fid)

        t0 = time.time()
        status = svc.run_pipeline(file_ids, pid, PipelineConfig(),
                                  mmx_study=STUDY, study_name=STUDY)
        while not status.complete:
            time.sleep(2)
            status = svc.get_job(status.job_id)

        if status.error:
            results.append({"patient_id": pid, "segments": len(paths),
                            "err": (status.error or "failed")[:140],
                            "seconds": round(time.time() - t0, 1)})
            print(json.dumps(results[-1]), flush=True)
            continue

        # get_result() rebuilds PatientResult from the disk cache, which does not
        # persist ARRejectionResult — so read what the run recorded instead: the
        # warning line in meta.json and the NaN counts actually written to the
        # parquet. That also proves the nulling reached storage, not just memory.
        res = svc.get_result(pid)
        ar_warn, probe = _cache_evidence(pid)
        row = {
            "patient_id": pid,
            "segments": len(paths),
            "epochs": len(res.epochs) if res is not None else None,
            "ar_summary": ar_warn,
            **probe,
            "artifact_method": res.artifact_result.method if res is not None else None,
            "artifact_excluded_pct": (round(res.artifact_result.artifact_pct, 2)
                                      if res is not None else None),
            "seconds": round(time.time() - t0, 1),
        }
        results.append(row)
        print(json.dumps(row), flush=True)

    outdir = ROOT / "docs" / "_project" / "diagnostics"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "REPROCESS_V10_AR.json"
    out.write_text(json.dumps({
        "template": MMX.name, "cohort": str(COHORT),
        "export_set": f"afternoon (stem >= {RENAME_CUTOFF})",
        "corrections_loaded": len(corr),
        "patients": results,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(out), "patients": len(results)}), flush=True)


if __name__ == "__main__":
    main()
