from __future__ import annotations

import pandas as pd
import json
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PatientRecord:
    patient_id: str
    export_files: list[str] = field(default_factory=list)
    age_days: Optional[float] = None
    rosc_time: Optional[str] = None  # ISO format string
    metadata: dict = field(default_factory=dict)


class SubjectRegistry:
    """JSON-based patient registry."""

    def __init__(self, path: Path | None = None):
        self.patients: dict[str, PatientRecord] = {}
        self.path = path
        if path and path.exists():
            self.load(path)

    def add_patient(self, record: PatientRecord) -> None:
        self.patients[record.patient_id] = record

    def get_patient(self, patient_id: str) -> PatientRecord | None:
        return self.patients.get(patient_id)

    def load_from_csv(self, csv_path: Path, id_column: str = "studyID",
                      filename_column: str | None = None,
                      age_column: str | None = None,
                      rosc_column: str | None = None) -> int:
        """Load patient data from a subject alignment CSV. Returns count of patients loaded."""
        df = pd.read_csv(csv_path)
        # Flexible column detection
        id_col = _find_column(df, [id_column, "study_id", "studyid", "patient_id", "numid", "record_id"])
        if id_col is None:
            raise ValueError(f"Could not find ID column in {csv_path}")

        fn_col = _find_column(df, [filename_column or "", "filename", "eeg_file", "file"])
        age_col = _find_column(df, [age_column or "", "age_days", "age", "ageenrday"])
        rosc_col = _find_column(df, [rosc_column or "", "rosc_time", "rosc", "rosc_datetime"])

        count = 0
        for _, row in df.iterrows():
            pid = str(row[id_col]).strip()
            if not pid:
                continue
            record = PatientRecord(patient_id=pid)
            if fn_col and pd.notna(row.get(fn_col)):
                record.export_files = [str(row[fn_col])]
            if age_col and pd.notna(row.get(age_col)):
                record.age_days = float(row[age_col])
            if rosc_col and pd.notna(row.get(rosc_col)):
                # Convert to ISO datetime at ingest time so the value survives
                # JSON round-trips (avoids storing raw Excel serial as string).
                from qeeg.validation.alignment_check import parse_rosc_time
                parsed = parse_rosc_time(row[rosc_col])
                record.rosc_time = parsed.isoformat() if parsed else str(row[rosc_col])
            self.add_patient(record)
            count += 1
        return count

    def save(self, path: Path | None = None) -> None:
        p = path or self.path
        if p is None:
            raise ValueError("No path specified")
        data = {pid: asdict(rec) for pid, rec in self.patients.items()}
        p.write_text(json.dumps(data, indent=2, default=str))

    def load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        self.patients = {pid: PatientRecord(**rec) for pid, rec in data.items()}
        self.path = path

    def extract_patient_id(self, filename: str) -> str | None:
        """Extract patient ID from filename like '2046_1.csv' -> '2046'."""
        stem = Path(filename).stem
        match = re.match(r"^(\d+)", stem)
        return match.group(1) if match else None


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find first matching column name (case-insensitive)."""
    cols_lower = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if not candidate:
            continue
        if candidate.lower() in cols_lower:
            return cols_lower[candidate.lower()]
    return None
