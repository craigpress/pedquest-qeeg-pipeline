from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .identity import derive_patient_id
from .timestamps import excel_serial_to_timestamp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExportMetadata:
    file_path: str = ""
    patient_name: str = ""      # Stripped for PHI
    patient_id: str = ""
    test_date: str = ""
    test_time: str = ""
    source_path: Optional[str] = None
    persyst_version: str = ""   # Software version from CSV header (e.g., "Persyst 14")


@dataclass
class ParsedExport:
    data: pd.DataFrame
    code_to_description: dict[str, str]       # I-code -> trend name
    description_to_codes: dict[str, list[str]] # trend name -> list of I-codes
    metadata: ExportMetadata
    code_row_index: int
    trend_row_index: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ICODE_RE = re.compile(r"^I\d+_\d+$")

ENCODING_ORDER = ["utf-8-sig", "utf-16", "cp1252", "latin-1"]

# Metadata keys we look for in the first few rows (case-insensitive match
# against the first cell of each row).
_META_KEYS = {
    "file":             "file_path",
    "patientname":      "patient_name",
    "patientid":        "patient_id",
    "patientbirthdate": "_skip",       # PHI – do not store
    "testdate":         "test_date",
    "testtime":         "test_time",
}


def detect_encoding(path: Path) -> str:
    """Try encodings in order, return first that works."""
    for enc in ENCODING_ORDER:
        try:
            with open(path, "r", encoding=enc) as f:
                f.readline()
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def _fill_forward(values: list[str]) -> list[str]:
    """Fill empty strings with the previous non-empty value.

    Replicates the effect of merged cells in Excel where a trend name
    spans several columns: only the leftmost cell has text; the rest
    are empty until the next trend name appears.
    """
    result: list[str] = []
    last = ""
    for v in values:
        v = v.strip()
        if v:
            last = v
        result.append(last)
    return result


def _extract_metadata(rows: list[list[str]], limit: int = 6) -> ExportMetadata:
    """Pull metadata from the first *limit* rows of the CSV."""
    meta = ExportMetadata()
    for row in rows[:limit]:
        if not row:
            continue
        key = row[0].strip().lower().replace(" ", "")
        if key in _META_KEYS:
            attr = _META_KEYS[key]
            if attr == "_skip":
                continue
            value = row[1].strip() if len(row) > 1 else ""
            setattr(meta, attr, value)
    # Strip PHI: never keep patient name even if parsed
    meta.patient_name = ""

    # Try to extract Persyst version from header rows
    # The "File" row often contains the version, or it may appear in any cell
    _persyst_ver_re = re.compile(r"Persyst\s+\d+[\.\d]*", re.IGNORECASE)
    for row in rows[:limit]:
        for cell in row:
            m = _persyst_ver_re.search(cell)
            if m:
                meta.persyst_version = m.group(0)
                break
        if meta.persyst_version:
            break

    return meta


def _find_code_row(rows: list[list[str]], max_scan: int = 61) -> int | None:
    """Scan up to *max_scan* rows for the code row.

    The code row is the one where the majority of non-empty cells match the
    ``I\\d+_\\d+`` pattern **and** a ``ClockDateTime`` cell is present.
    """
    for idx, row in enumerate(rows[:max_scan]):
        non_empty = [c.strip() for c in row if c.strip()]
        if not non_empty:
            continue
        has_clock = any(c == "ClockDateTime" for c in non_empty)
        if not has_clock:
            continue
        icode_count = sum(1 for c in non_empty if _ICODE_RE.match(c))
        # Require that a meaningful fraction are I-codes (at least half of
        # non-empty cells excluding ClockDateTime itself).
        threshold = max(1, (len(non_empty) - 1) / 2)
        if icode_count >= threshold:
            return idx
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_persyst_csv(path: str | Path) -> ParsedExport:
    """Parse a Persyst CSV/TSV export into a ``ParsedExport``.

    Fast path: if a full sidecar exists and Parquet is ready, reads from local
    .qeeg_cache/parquet/ via DuckDB without opening the network CSV at all.

    Slow path (first encounter or after CSV change):
    1. Detect file encoding.
    2. Read all rows with ``csv.reader`` to locate structural landmarks.
    3. Extract metadata from the first few rows.
    4. Find the *code row* (I-codes + ClockDateTime) and the *trend name
       row* immediately above it.
    5. Build code-to-description mappings using fill-forward on the trend
       name row.
    6. Re-read the data section efficiently with ``pd.read_csv``.
    7. Convert the ``ClockDateTime`` column from Excel serial dates.
    8. Write/upgrade full-phase sidecar for future DuckDB reads.
    """
    path = Path(path)

    # Fast path: Parquet is ready — read from local cache via DuckDB
    try:
        from qeeg.ingestion.sidecar import read_sidecar
        _sidecar = read_sidecar(path)
        if (
            _sidecar is not None
            and _sidecar.phase == "full"
            and _sidecar.parquet_status == "ready"
        ):
            _pq_path = Path(_sidecar.parquet_path)
            if _pq_path.exists():
                from qeeg.ingestion.duckdb_reader import load_from_parquet
                logger.debug("DuckDB fast path: %s", path.name)
                return load_from_parquet(_pq_path, _sidecar)
            # Parquet was deleted; reset so it gets re-queued
            _sidecar.parquet_status = "pending"
            _sidecar.parquet_path = ""
            from qeeg.ingestion.sidecar import write_sidecar
            write_sidecar(path, _sidecar)
    except Exception:
        logger.warning("DuckDB fast path failed for %s; falling back to CSV parse", path.name, exc_info=True)

    encoding = detect_encoding(path)
    logger.info("Reading %s with encoding=%s", path, encoding)

    # ------------------------------------------------------------------
    # Phase 1 – header row scan (only first 61 rows, not the entire file)
    # ------------------------------------------------------------------
    MAX_HEADER_SCAN = 61
    with open(path, "r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh)
        raw_rows: list[list[str]] = []
        for i, row in enumerate(reader):
            raw_rows.append(row)
            if i >= MAX_HEADER_SCAN:
                break

    # ------------------------------------------------------------------
    # Phase 2 – metadata
    # ------------------------------------------------------------------
    metadata = _extract_metadata(raw_rows)
    metadata.source_path = str(path)
    # Prefer the source .dat filename (File: row) over PatientId field — the
    # .dat name is consistent across all panel CSVs from the same recording.
    # Patient identity is derived by the shared rule (see qeeg.ingestion.identity).
    _dat_stem = Path(metadata.file_path).stem if metadata.file_path else ""
    _pid = derive_patient_id(_dat_stem)
    if _pid:
        metadata.patient_id = _pid

    # ------------------------------------------------------------------
    # Phase 3 – locate code row & trend name row
    # ------------------------------------------------------------------
    code_row_idx = _find_code_row(raw_rows)
    if code_row_idx is None:
        raise ValueError(
            f"Could not find the code row (I-codes + ClockDateTime) in the "
            f"first 60 rows of {path}"
        )

    trend_row_idx = code_row_idx - 1
    if trend_row_idx < 0:
        raise ValueError(
            f"Code row found at row 0; no trend name row above it in {path}"
        )

    code_row = raw_rows[code_row_idx]
    trend_row = raw_rows[trend_row_idx]

    # Pad trend row to match code row length (ragged CSVs)
    while len(trend_row) < len(code_row):
        trend_row.append("")

    filled_trends = _fill_forward(trend_row)

    # ------------------------------------------------------------------
    # Phase 4 – build mappings
    # ------------------------------------------------------------------
    code_to_description: dict[str, str] = {}
    description_to_codes: dict[str, list[str]] = {}

    for col_idx, code in enumerate(code_row):
        code = code.strip()
        if not code or code == "ClockDateTime":
            continue
        desc = filled_trends[col_idx] if col_idx < len(filled_trends) else ""
        code_to_description[code] = desc
        description_to_codes.setdefault(desc, []).append(code)

    # ------------------------------------------------------------------
    # Phase 5 – read data with pandas
    # ------------------------------------------------------------------
    # Data starts on the row immediately after the code row.
    data_start = code_row_idx + 1

    # Use the code row values as column names.
    col_names = [c.strip() for c in code_row]

    df = pd.read_csv(
        path,
        encoding=encoding,
        skiprows=data_start,
        header=None,
        names=col_names,
        on_bad_lines="warn",
    )

    # Drop fully-empty columns that may appear from trailing delimiters
    df = df.dropna(axis=1, how="all")

    # ------------------------------------------------------------------
    # Phase 6 – timestamp conversion
    # ------------------------------------------------------------------
    if "ClockDateTime" in df.columns:
        try:
            df["ClockDateTime"] = excel_serial_to_timestamp(
                df["ClockDateTime"]
            )
        except Exception:
            logger.warning(
                "Could not convert ClockDateTime to timestamps; "
                "leaving as raw values."
            )

    # Write/upgrade full-phase sidecar so future calls can use the DuckDB fast path
    # after convert_csv_to_parquet() has run in the background.
    try:
        from qeeg.ingestion.sidecar import read_sidecar, write_sidecar, SidecarMeta

        # Compute panel type from the already-available filled trend names
        _panel_type = ""
        try:
            from qeeg.ingestion.quick_scan import _classify_panel
            _panel_type = _classify_panel([t for t in filled_trends if t])
        except Exception:
            pass

        # Re-read to preserve any parquet_status set by the conversion worker
        _fresh = read_sidecar(path)
        _existing_panel = _fresh.csv_panel_type if _fresh and _fresh.csv_panel_type else _panel_type

        write_sidecar(
            path,
            SidecarMeta(
                source_csv=str(path),
                source_mtime=path.stat().st_mtime,
                file_type="persyst_csv",
                csv_panel_type=_existing_panel,
                patient_id=metadata.patient_id,
                test_date=metadata.test_date,
                test_time=metadata.test_time,
                encoding=encoding,
                n_columns=len(code_to_description),
                n_data_rows=len(df),
                code_row_index=code_row_idx,
                trend_row_index=trend_row_idx,
                persyst_version=metadata.persyst_version,
                code_to_description=code_to_description,
                description_to_codes=description_to_codes,
                parquet_status=_fresh.parquet_status if _fresh else "pending",
                parquet_path=_fresh.parquet_path if _fresh else "",
                phase="full",
            ),
        )
    except Exception:
        # Sidecar failure must never break parsing, but it should be visible
        # so a regression doesn't silently force the slow path forever.
        logger.warning("Sidecar write failed for %s", path.name, exc_info=True)

    return ParsedExport(
        data=df,
        code_to_description=code_to_description,
        description_to_codes=description_to_codes,
        metadata=metadata,
        code_row_index=code_row_idx,
        trend_row_index=trend_row_idx,
    )
