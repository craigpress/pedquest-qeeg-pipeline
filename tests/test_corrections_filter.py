"""Regression test: EEG corrections filter must not leak between patients with
prefix-overlapping IDs (e.g. '4290-1' vs '4290-10').

Past bug (see memory 'error_corrections_lookup_stem'): lookups keyed on CSV
stem vs dat stem leaked one patient's corrections into another's view. The
filter in api/routes/patients.py (lines ~131-134) guards against a separate
but related leak: when matching by prefix, '4290-1' must not pick up
'4290-10*' keys. The trailing underscore in `startswith(f"{patient_id}_")`
is what enforces this.

Note on tightening the filter: EEGCorrection (see
api/services/pipeline_service.py) has no `patient_id` field — only
`new_name`, `age_in_days_at_time_of_eeg`, `eeg_start_time`, `eeg_duration`,
and `date_of_csv_creation`. So a secondary `c.patient_id == patient_id`
check is not possible without schema changes. The key-prefix filter is the
only defense and must be tested directly.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.main import pipeline_service
from api.services.pipeline_service import EEGCorrection
from qeeg.alignment.time_axis import TimeAxisInfo


# The exact collision case from the memory: patient_id "4290-1" vs
# neighbour "4290-10" with continuation segments.
COLLISION_KEYS = {
    "4290-1": EEGCorrection("4290-1", 100, "08:00:00", "02:00:00"),
    "4290-1_seg2": EEGCorrection("4290-1_seg2", 101, "09:00:00", "02:00:00"),
    "4290-10": EEGCorrection("4290-10", 50, "12:00:00", "01:00:00"),
    "4290-10_seg1": EEGCorrection("4290-10_seg1", 51, "13:00:00", "01:00:00"),
}


@pytest.fixture
def isolated_service():
    """Snapshot & clear service state for the duration of one test."""
    svc = pipeline_service
    saved = {
        "corr": dict(svc._eeg_corrections),
        "clin": dict(svc._clinical_metadata),
        "studies": dict(svc._studies),
        "patient_studies": dict(svc._patient_studies),
    }
    svc._eeg_corrections = {}
    svc._clinical_metadata = {}
    svc._patient_studies = {}
    try:
        yield svc
    finally:
        svc._eeg_corrections = saved["corr"]
        svc._clinical_metadata = saved["clin"]
        svc._studies = saved["studies"]
        svc._patient_studies = saved["patient_studies"]


class TestCorrectionFilterCrossPatientLeak:
    """Directly exercise the filter expression against the collision keys."""

    def test_filter_expression_rejects_neighbour_prefix(self):
        """`4290-1` must not match `4290-10` nor `4290-10_seg1`."""
        patient_id = "4290-1"
        matches = {
            name: c
            for name, c in COLLISION_KEYS.items()
            if name == patient_id or name.startswith(f"{patient_id}_")
        }
        assert set(matches.keys()) == {"4290-1", "4290-1_seg2"}

    def test_filter_expression_for_neighbour_patient(self):
        """`4290-10` must match only its own entries, not `4290-1*`."""
        patient_id = "4290-10"
        matches = {
            name: c
            for name, c in COLLISION_KEYS.items()
            if name == patient_id or name.startswith(f"{patient_id}_")
        }
        assert set(matches.keys()) == {"4290-10", "4290-10_seg1"}

    def test_exact_match_without_segment(self):
        """Patient with only an exact-name correction key still matches."""
        keys = {"4290-1": EEGCorrection("4290-1", 100, "08:00:00", "02:00:00")}
        matches = [
            c for name, c in keys.items()
            if name == "4290-1" or name.startswith("4290-1_")
        ]
        assert len(matches) == 1
        assert matches[0].new_name == "4290-1"

    def test_no_underscore_means_no_false_positive(self):
        """`4290-10` without underscore must never match `4290-1`."""
        assert not "4290-10".startswith("4290-1_")


class TestBuildTimeAxisResponseEndToEnd:
    """Invoke the real _build_time_axis_response to confirm the filter is
    wired correctly in production code, not just in the test's local copy.
    """

    def test_build_time_axis_picks_only_own_patient_corrections(self, isolated_service):
        from api.routes.patients import _build_time_axis_response

        # Seed both patients' corrections into the service.
        isolated_service._eeg_corrections = dict(COLLISION_KEYS)

        time_info = TimeAxisInfo(
            reference="recording_start",
            reference_time=pd.Timestamp("2025-01-01 00:00:00"),
        )

        resp_1 = _build_time_axis_response("4290-1", time_info)
        # The earliest correction for patient 4290-1 is "4290-1" (age 100, 08:00).
        assert resp_1.age_at_eeg_start_days == 100
        assert resp_1.eeg_start_time == "08:00:00"

        resp_10 = _build_time_axis_response("4290-10", time_info)
        # The earliest correction for patient 4290-10 is "4290-10" (age 50, 12:00).
        # If the filter leaked, it would pick "4290-1" (age 100) instead.
        assert resp_10.age_at_eeg_start_days == 50
        assert resp_10.eeg_start_time == "12:00:00"
