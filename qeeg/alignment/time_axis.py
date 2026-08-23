from __future__ import annotations

import pandas as pd
from dataclasses import dataclass


@dataclass
class TimeAxisInfo:
    reference: str  # "rosc" or "recording_start"
    reference_time: pd.Timestamp
    column_name: str = "hours_relative"


def compute_hours_relative(timestamps: pd.Series, reference_time: pd.Timestamp) -> pd.Series:
    """Compute hours relative to a reference time."""
    return (timestamps - reference_time).dt.total_seconds() / 3600.0


def build_time_axis(timestamps: pd.Series, rosc_time: pd.Timestamp | None = None) -> tuple[pd.Series, TimeAxisInfo]:
    """Build a unified time axis. Uses ROSC if available, otherwise recording start."""
    if len(timestamps) == 0:
        raise ValueError(
            "build_time_axis: no timestamps — the recording is empty after parse/merge/"
            "filtering. Check segment merge and de-identification corrections."
        )
    if rosc_time is not None:
        hours = compute_hours_relative(timestamps, rosc_time)
        info = TimeAxisInfo(reference="rosc", reference_time=rosc_time)
    else:
        start = timestamps.iloc[0]
        hours = compute_hours_relative(timestamps, start)
        info = TimeAxisInfo(reference="recording_start", reference_time=start)
    return hours, info
