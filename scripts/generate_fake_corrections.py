"""Generate fake EEG date-correction CSVs for the <EXPORT-DIR>\\ cohort.

For each patient folder, finds the .dat segments, then writes
`eeg_date_correction.csv` with:
  - segment 1 starting at a random offset of -6 to +12 h from cardiac-arrest time
  - subsequent segments following chronologically with a 0-30 min gap
  - random per-segment duration between 6 and 18 h

Re-creates the corrections files the user accidentally deleted. Values are
synthetic — the goal is plausible, processable inputs, not ground truth.
"""

from __future__ import annotations

import csv
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import export_dir  # noqa: E402

ROOT = export_dir()
SEED = 20260823   # arbitrary; was a number that read like the study ID
random.seed(SEED)


def load_clinical(path: Path) -> dict[str, tuple[str, str]]:
    """Return {patient_id: (rosc_HHMM, age_at_arrest_days)}.

    The Y:\\ clinical.csv has a malformed header but the data is consistent:
    col 1 = patient_id, col 2 = rosc_time (HH:MM), col 3 = age_at_arrest_days.
    """
    out: dict[str, tuple[str, str]] = {}
    with path.open(newline="") as f:
        rd = csv.reader(f)
        next(rd, None)  # skip header
        for row in rd:
            if len(row) < 3:
                continue
            pid, rosc, age = row[0].strip(), row[1].strip(), row[2].strip()
            if pid and rosc and age:
                out[pid] = (rosc, age)
    return out


SEG_RE = re.compile(r"^(?P<base>.+?)(?:-(?P<seg>\d+))?$")


def list_segments(folder: Path) -> list[str]:
    """List .dat stems in chronological order (base first, then -2, -3, ...)."""
    stems = [p.stem for p in folder.glob("*.dat")]

    def sort_key(stem: str) -> tuple[str, int]:
        m = SEG_RE.match(stem)
        if not m:
            return (stem, 0)
        return (m.group("base"), int(m.group("seg") or "1"))

    return sorted(stems, key=sort_key)


def fmt_time(t: datetime) -> str:
    return t.strftime("%H:%M:%S")


def fmt_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def patient_id_from_folder(folder: Path) -> str | None:
    """Folder names look like 'subject-1_rec' — extract 'subject-1'."""
    name = folder.name
    if "_" in name:
        return name.split("_", 1)[0]
    return name


def write_correction_for_patient(
    folder: Path, rosc_hhmm: str, age_at_arrest: int
) -> None:
    stems = list_segments(folder)
    if not stems:
        print(f"  skip {folder.name}: no .dat files")
        return

    rosc_h, rosc_m = (int(x) for x in rosc_hhmm.split(":")[:2])
    arrest_dt = datetime(2000, 1, 1, rosc_h, rosc_m, 0)  # date is synthetic

    offset_h = random.uniform(-6.0, 12.0)
    cur_start = arrest_dt + timedelta(hours=offset_h)

    out_path = folder / "eeg_date_correction.csv"
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "new_name", "age_in_days_at_time_of_eeg", "eeg_start_time",
            "eeg_duration", "date_of_csv_creation",
        ])
        for stem in stems:
            duration = timedelta(hours=random.uniform(6.0, 18.0))
            day_offset = (cur_start.date() - arrest_dt.date()).days
            age_at_eeg = age_at_arrest + day_offset
            # Normalize trailing -N segment suffix to _N to match pipeline's
            # `_dat_stem_from_csv` normalization (see error_corrections_lookup_stem.md).
            new_name = re.sub(r"-(\d+)$", r"_\1", stem)
            w.writerow([
                new_name,
                age_at_eeg,
                fmt_time(cur_start),
                fmt_duration(duration),
                datetime.now().strftime("%Y-%m-%d"),
            ])
            cur_start = cur_start + duration + timedelta(
                minutes=random.uniform(0, 30)
            )

    print(f"  wrote {out_path.name} with {len(stems)} segment(s)")


def main() -> None:
    clinical_path = ROOT / "clinical.csv"
    if not clinical_path.exists():
        raise SystemExit(f"clinical.csv not found at {clinical_path}")

    clinical = load_clinical(clinical_path)
    print(f"Loaded {len(clinical)} clinical rows")

    folders = sorted(p for p in ROOT.iterdir() if p.is_dir())
    print(f"Scanning {len(folders)} patient folders\n")

    for folder in folders:
        pid = patient_id_from_folder(folder)
        if not pid or pid not in clinical:
            print(f"{folder.name}: no clinical row for '{pid}', skip")
            continue
        rosc, age_str = clinical[pid]
        try:
            age = int(age_str)
        except ValueError:
            print(f"{folder.name}: bad age '{age_str}', skip")
            continue
        print(f"{folder.name} (pid={pid}, rosc={rosc}, age_at_arrest={age}):")
        write_correction_for_patient(folder, rosc, age)


if __name__ == "__main__":
    main()
