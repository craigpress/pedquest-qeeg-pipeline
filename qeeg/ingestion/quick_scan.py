"""Lightweight file scan — extracts metadata and time range without full parsing."""
from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .identity import derive_patient_id
from .parser import detect_encoding, _extract_metadata, _find_code_row, _ICODE_RE
from .timestamps import excel_serial_to_timestamp

# How many bytes to read from the tail to find the last data row
_TAIL_BYTES = 8192

_TIME_AVG_RE = re.compile(r"^Time Avg <", re.IGNORECASE)


@dataclass
class QuickScanResult:
    patient_id: str
    test_date: str
    test_time: str
    n_columns: int
    n_data_rows: int
    eeg_start: Optional[str]  # ISO timestamp string
    eeg_end: Optional[str]
    duration_hours: Optional[float]
    file_size_mb: float
    file_path: str = ""
    csv_panel_type: str = "trends"
    encoding: str = ""
    code_row_index: int = -1


def _classify_panel(trend_names: list[str]) -> str:
    """Infer panel type from the human-readable trend description row."""
    if not trend_names:
        return "trends"
    n = len(trend_names)
    spectrogram_count = sum(1 for t in trend_names if "Spectrogram" in t)
    if spectrogram_count / n >= 0.5:
        return "spectrograms"
    time_avg_count = sum(1 for t in trend_names if _TIME_AVG_RE.match(t))
    if time_avg_count / n >= 0.8:
        return "time_averages"
    has_coherence = any("Coherence_Avg" in t or "Coherence Avg" in t for t in trend_names)
    has_fft_power = any("FFT Power" in t or "FFT_Power" in t for t in trend_names)
    if has_coherence and not has_fft_power:
        return "coherence_only"
    return "trends"


def _count_data_rows(path: Path, encoding: str, header_lines: int) -> int:
    """Count data rows by counting newlines in the file minus header lines.

    Fast: reads the file in chunks, never builds a full list.
    """
    total_newlines = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)  # 1 MB chunks
            if not chunk:
                break
            total_newlines += chunk.count(b"\n")
    # Subtract header rows (each ends with \n); data rows = total - header_lines
    # Also handle files that don't end in \n (last row has no trailing newline)
    return max(0, total_newlines - header_lines)


def _read_last_clock_value(path: Path, encoding: str, clock_idx: int) -> Optional[str]:
    """Seek near end of file and parse the last non-empty ClockDateTime value."""
    file_size = path.stat().st_size
    read_size = min(_TAIL_BYTES, file_size)

    with open(path, "rb") as fh:
        fh.seek(file_size - read_size)
        tail_bytes = fh.read()

    # Decode, drop the first (possibly partial) line
    tail_text = tail_bytes.decode(encoding, errors="replace")
    lines = tail_text.splitlines()
    if len(lines) > 1:
        lines = lines[1:]  # drop potentially partial first line

    last_val: Optional[str] = None
    for line in reversed(lines):
        if not line.strip():
            continue
        # Fast CSV parse of a single line
        try:
            row = next(csv.reader(io.StringIO(line)))
        except StopIteration:
            continue
        if len(row) > clock_idx:
            val = row[clock_idx].strip()
            if val:
                last_val = val
                break

    return last_val


def quick_scan(path: str | Path) -> QuickScanResult:
    """Scan a Persyst CSV for metadata and time range.

    Reads the first ~61 lines for headers, then uses fast newline counting
    for epoch count and a tail-seek for the last timestamp.
    Does NOT iterate all rows.
    """
    path = Path(path)
    encoding = detect_encoding(path)
    file_size_mb = path.stat().st_size / (1024 * 1024)

    # Read header rows (first 61 lines)
    header_rows: list[list[str]] = []
    with open(path, "r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            header_rows.append(row)
            if i >= 60:
                break

    metadata = _extract_metadata(header_rows)
    code_row_idx = _find_code_row(header_rows)

    if code_row_idx is None:
        raise ValueError(f"Could not find code row in {path}")

    code_row = header_rows[code_row_idx]
    n_columns = sum(1 for c in code_row if c.strip() and _ICODE_RE.match(c.strip()))

    # Classify panel type from trend-name row (one row above the code row)
    csv_panel_type = "trends"
    if code_row_idx > 0:
        trend_names = [c.strip() for c in header_rows[code_row_idx - 1] if c.strip()]
        csv_panel_type = _classify_panel(trend_names)

    # Find ClockDateTime column index
    clock_idx = None
    for ci, c in enumerate(code_row):
        if c.strip() == "ClockDateTime":
            clock_idx = ci
            break

    # Fast epoch count via newline counting
    # header_lines = code_row_idx + 1 (0-indexed rows through code row)
    n_data_rows = _count_data_rows(path, encoding, header_lines=code_row_idx + 1)

    # Get first timestamp from already-read header rows (first data row follows code row)
    first_clock: Optional[str] = None
    if clock_idx is not None and code_row_idx + 1 < len(header_rows):
        first_data = header_rows[code_row_idx + 1]
        if len(first_data) > clock_idx:
            val = first_data[clock_idx].strip()
            if val:
                first_clock = val

    # If first data row wasn't buffered yet, read it from file
    if first_clock is None and clock_idx is not None:
        with open(path, "r", encoding=encoding, newline="") as fh:
            reader = csv.reader(fh)
            for i, row in enumerate(reader):
                if i <= code_row_idx:
                    continue
                if len(row) > clock_idx:
                    val = row[clock_idx].strip()
                    if val:
                        first_clock = val
                break

    # Get last timestamp via tail seek
    last_clock: Optional[str] = None
    if clock_idx is not None:
        last_clock = _read_last_clock_value(path, encoding, clock_idx)

    # Convert Excel serial dates
    eeg_start = None
    eeg_end = None
    duration_hours = None

    if first_clock:
        try:
            ts = excel_serial_to_timestamp(pd.Series([float(first_clock)]))
            eeg_start = str(ts.iloc[0])
        except Exception:
            eeg_start = first_clock
    if last_clock:
        try:
            ts = excel_serial_to_timestamp(pd.Series([float(last_clock)]))
            eeg_end = str(ts.iloc[0])
        except Exception:
            eeg_end = last_clock

    if eeg_start and eeg_end:
        try:
            start_ts = pd.Timestamp(eeg_start)
            end_ts = pd.Timestamp(eeg_end)
            duration_hours = (end_ts - start_ts).total_seconds() / 3600
        except Exception:
            pass

    # Use the source .dat filename (File: row) as patient_id — it is consistent
    # across all panel CSVs exported from the same recording, unlike PatientId
    # (which may be a date/label) or the CSV filename (which the user controls).
    # Identity derived by the shared rule (see qeeg.ingestion.identity).
    dat_stem = Path(metadata.file_path).stem if metadata.file_path else ""
    patient_id = derive_patient_id(dat_stem) or metadata.patient_id or path.stem

    return QuickScanResult(
        patient_id=patient_id,
        test_date=metadata.test_date,
        test_time=metadata.test_time,
        n_columns=n_columns,
        n_data_rows=n_data_rows,
        eeg_start=eeg_start,
        eeg_end=eeg_end,
        duration_hours=duration_hours,
        file_size_mb=file_size_mb,
        file_path=str(path),
        csv_panel_type=csv_panel_type,
        encoding=encoding,
        code_row_index=code_row_idx if code_row_idx is not None else -1,
    )
