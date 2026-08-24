"""Patient-ID derivation: one rule, consumed by parser/quick_scan/upload/grouper."""
import pytest

from qeeg.ingestion.identity import derive_patient_id


@pytest.mark.parametrize("stem,expected", [
    # PedQuEST: numeric studyID_eegNumber
    ("2046_1", "2046"),
    ("2046_1_2", "2046"),       # continuation segment
    ("2046", "2046"),           # no underscore
    # POCCA: siteID-patientID_UUID_eegNumber (hyphen is part of the identity)
    ("01-001_UUID_2", "01-001"),
    ("01-001", "01-001"),
    # Persyst .dat stems: patientID_hash
    ("subject-10_rec", "subject-10"),
    ("subject-1_rec", "subject-1"),     # distinct patient from subject-10
    ("subject-10", "subject-10"),
    # Synthetic
    ("SYNTH001_1", "SYNTH001"),
    # Degenerate
    ("", ""),
    ("   ", ""),
    ("_leading", "_leading"),   # pathological leading underscore -> whole stem (safe fallback)
])
def test_derive_patient_id(stem, expected):
    assert derive_patient_id(stem) == expected


def test_subject_1_and_subject_10_are_distinct():
    """Regression: hyphenated suffix is identity, not a segment to merge away.

    The prefix collision is the point — `subject-1` is a prefix of
    `subject-10`, so a rule that splits on the first separator merges two
    unrelated patients. Any future renaming of these fixtures must keep one ID
    a prefix of the other or this test stops testing anything.
    """
    assert derive_patient_id("subject-1_h") != derive_patient_id("subject-10_h")


def test_pocca_not_collapsed_to_site():
    """Regression (H3): the old upload regex collapsed '01-001...' to '01'."""
    assert derive_patient_id("01-001_UUID_2") == "01-001"
    assert derive_patient_id("01-002_UUID_1") == "01-002"
    assert derive_patient_id("01-001_a") != derive_patient_id("01-002_a")


def test_all_call_sites_agree():
    """parser, quick_scan, upload, grouper must all produce the same id."""
    from api.routes.upload import _stem_to_patient_id
    stem = "01-001_3F2A_2"
    assert derive_patient_id(stem) == "01-001"
    assert _stem_to_patient_id(stem) == "01-001"
