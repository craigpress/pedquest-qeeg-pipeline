from __future__ import annotations

import pandas as pd
from dataclasses import dataclass

MAX_ROSC_TO_EEG_HOURS = 22.0


@dataclass
class AlignmentResult:
    is_aligned: bool
    hours_from_rosc_to_eeg: float | None
    rosc_time: pd.Timestamp | None
    eeg_start: pd.Timestamp | None
    warning: str = ""
    has_pre_rosc_data: bool = False
    pre_rosc_hours: float = 0.0  # how many hours of data exist before ROSC


def check_rosc_alignment(rosc_time: pd.Timestamp | None, eeg_start: pd.Timestamp | None) -> AlignmentResult:
    """Validate that EEG starts within MAX_ROSC_TO_EEG_HOURS of ROSC."""
    if rosc_time is None or eeg_start is None:
        return AlignmentResult(
            is_aligned=False, hours_from_rosc_to_eeg=None,
            rosc_time=rosc_time, eeg_start=eeg_start,
            warning="ROSC time or EEG start not available; using recording-relative time"
        )

    diff = eeg_start - rosc_time
    hours = diff.total_seconds() / 3600.0

    if hours < 0:  # EEG started before ROSC — align and trim
        return AlignmentResult(
            is_aligned=True, hours_from_rosc_to_eeg=hours,
            rosc_time=rosc_time, eeg_start=eeg_start,
            warning=f"EEG started {abs(hours):.1f}h before ROSC — pre-ROSC data will be trimmed",
            has_pre_rosc_data=True, pre_rosc_hours=abs(hours),
        )

    if hours > MAX_ROSC_TO_EEG_HOURS:
        return AlignmentResult(
            is_aligned=False, hours_from_rosc_to_eeg=hours,
            rosc_time=rosc_time, eeg_start=eeg_start,
            warning=f"EEG started {hours:.1f}h after ROSC (>{MAX_ROSC_TO_EEG_HOURS}h) — possible date-shift mismatch"
        )

    return AlignmentResult(
        is_aligned=True, hours_from_rosc_to_eeg=hours,
        rosc_time=rosc_time, eeg_start=eeg_start
    )


def parse_rosc_time(value) -> pd.Timestamp | None:
    """Parse ROSC time from various formats (string datetime, Excel serial, etc.).

    Handles: ISO strings, US date strings, Excel serial numbers (float/int),
    and numeric strings that represent Excel serials (e.g. "45366.395833").
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    # Excel serial number (float or int)
    if isinstance(value, (int, float)):
        from qeeg.ingestion.timestamps import excel_serial_to_datetime
        return pd.Timestamp(excel_serial_to_datetime(value))
    # String that looks like an Excel serial (e.g. from JSON round-trip)
    s = str(value).strip()
    try:
        numeric = float(s)
        if 1 < numeric < 2_958_465:
            from qeeg.ingestion.timestamps import excel_serial_to_datetime
            return pd.Timestamp(excel_serial_to_datetime(numeric))
    except ValueError:
        pass
    # Let pandas parse the string (handles ISO, US dates, etc.)
    try:
        return pd.Timestamp(s)
    except (ValueError, TypeError):
        pass
    # Explicit format fallback using stdlib datetime
    from datetime import datetime as dt
    for fmt in ["%m/%d/%y %H:%M", "%m/%d/%Y %H:%M", "%m/%d/%y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S"]:
        try:
            return pd.Timestamp(dt.strptime(s, fmt))
        except ValueError:
            continue
    return None
