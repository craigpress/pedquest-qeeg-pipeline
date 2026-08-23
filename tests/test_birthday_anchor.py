"""D.4 — birthday anchor preserves ROSC clock time (no normalize drift)."""
from __future__ import annotations

import pandas as pd


def test_birthday_preserves_rosc_time_of_day():
    """rosc_dt - age_days should keep the exact clock time of ROSC."""
    rosc_dt = pd.Timestamp("2024-01-15 08:30:00")
    age_days = 100

    birthday = rosc_dt - pd.Timedelta(days=age_days)

    assert birthday == pd.Timestamp("2023-10-07 08:30:00")


def test_birthday_formula_matches_pipeline_service():
    """The arithmetic in api/services/pipeline_service.py lines ~1192-1193
    must subtract age_days without normalizing rosc_dt first.
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "api" / "services" / "pipeline_service.py"
    text = src.read_text(encoding="utf-8")
    # Must NOT contain rosc_dt.normalize() - pd.Timedelta(...)
    assert ".normalize() - pd.Timedelta(days=clinical.age_days)" not in text, (
        "birthday derivation must not call rosc_dt.normalize() — it drops sub-day time"
    )
    # Must contain the expected arithmetic
    assert re.search(r"birthday\s*=\s*rosc_dt\s*-\s*pd\.Timedelta\(days=clinical\.age_days\)", text), (
        "expected `birthday = rosc_dt - pd.Timedelta(days=clinical.age_days)`"
    )
