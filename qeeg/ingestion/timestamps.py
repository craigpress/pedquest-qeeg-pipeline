from __future__ import annotations

import pandas as pd
from datetime import datetime

EXCEL_EPOCH = datetime(1899, 12, 30)


def excel_serial_to_datetime(serial: float) -> datetime:
    """Convert Excel serial date number to Python datetime."""
    return EXCEL_EPOCH + pd.Timedelta(days=serial)


def excel_serial_to_timestamp(series: pd.Series) -> pd.Series:
    """Convert a pandas Series of Excel serial dates to Timestamps.

    Values outside the plausible Excel serial range (1 .. 2_958_465,
    i.e. 1900-01-01 through 9999-12-31) are replaced with NaT.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    # Plausible range: Excel serial 1 (~1900) to ~2_958_465 (~9999)
    valid = numeric.between(1, 2_958_465)
    clean = numeric.where(valid)
    epoch = pd.Timestamp(EXCEL_EPOCH)
    return epoch + pd.to_timedelta(clean, unit="D")
